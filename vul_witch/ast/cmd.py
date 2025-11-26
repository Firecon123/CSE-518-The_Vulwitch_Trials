import click
from collections.abc import Sequence
from concurrent.futures import Future, ProcessPoolExecutor
from dataclasses import asdict, dataclass
from datetime import datetime
import os
from pathlib import Path
from pycparser.plyparser import ParseError
import shutil
from subprocess import CalledProcessError
import sys
from typing import List, Optional, Tuple
import yaml

from vul_witch.ast.compdb import CompilationDatabase
from vul_witch.ast.parser import parse, ParserOptions
from vul_witch.ast.printer import print_ast, PrinterOptions
from vul_witch.ast.query import (
    import_and_register_plugins, load_rules, PatternMatcher, Rule,
    VulnerabilitySeverity,
)


class PathConverter:
    _mappings: List[Tuple[str, str]]

    def __init__(self, mappings: Sequence[str]) -> None:
        self._mappings = []
        for mapping in mappings:
            src, dst = mapping.split(":")
            self._mappings.append((src, dst))

    def convert(self, path: Path) -> Path:
        path_str = str(path)
        for src, dst in self._mappings:
            if path_str.startswith(src):
                return Path(dst + path_str[len(src):])
        return path

    def reverse_convert(self, path: Path) -> Path:
        path_str = str(path)
        for src, dst in self._mappings:
            if path_str.startswith(dst):
                return Path(src + path_str[len(dst):])
        return path


def _look_up_c_preprocessor(cpp: str) -> Path:
    if os.path.sep not in cpp:
        cpp_path = shutil.which(cpp)
        if cpp_path is None:
            raise FileNotFoundError(f"c preprocessors does not exist: {cpp}")
        return Path(cpp_path)
    else:
        cpp_path = Path(cpp).resolve()
        if not cpp_path.exists():
            raise FileNotFoundError(f"c preprocessors does not exist: {cpp}")
        return cpp_path


@click.group()
def cli():
    pass


@dataclass(frozen=True)
class Preprocessor:
    cpp: Path
    args: Tuple[str, ...]

    @staticmethod
    def from_str(cpp_cmd: str) -> "Preprocessor":
        cpp_and_args = cpp_cmd.split()
        cpp = cpp_and_args[0]
        cpp_args = cpp_and_args[1:]
        return Preprocessor(
            cpp=_look_up_c_preprocessor(cpp),
            args=tuple(cpp_args),
        )


def common_options(func):
    func = click.option(
        "--preprocessor", "preprocessor",
        default="cpp",
        help="C preprocessor",
        show_default=True,
    )(func)
    func = click.option(
        "--include-dir", "include_dirs",
        type=Path,
        multiple=True,
        help="Directory containing C header files",
    )(func)
    func = click.option(
        "--use-fake-include-dir", "use_fake_include_dir",
        default=False,
        is_flag=True,
        help="Use fake include directories",
    )(func)
    func = click.option(
        "--output", "output",
        default="-",
        help="Path to output file",
    )(func)
    func = click.option(
        "--enable-parsing-debug", "enable_parsing_debug",
        default="False",
        is_flag=True,
        help="Enable debug info for parsing",
    )(func)
    return func


@cli.command("dump-ast")
@click.argument("filename")
@click.option("--show-location", "show_location", is_flag=True)
@click.option(
    "--ast-no-attr-name", "show_attribute_name",
    default=True, is_flag=True,
)
@click.option("--indent", "indent", default=0, type=int)
@common_options
def print(
    preprocessor: str,
    include_dirs: Tuple[Path, ...],
    show_location: bool,
    show_attribute_name: bool,
    indent: int,
    output: str,
    use_fake_include_dir: bool,
    enable_parsing_debug: bool,
    filename: str,
) -> None:
    cpp = Preprocessor.from_str(preprocessor)
    parser_options = ParserOptions(
        preprocessor=cpp.cpp,
        preprocessor_args=cpp.args,
        include_dirs=tuple([d.resolve() for d in include_dirs]),
        defines=tuple(),
        std_version_arg=None,
    )
    printer_options = PrinterOptions(
        indent, show_location, show_attribute_name,
    )
    tu = parse(Path(filename).resolve(), parser_options, enable_parsing_debug)
    if output == "-":
        print_ast(tu, sys.stdout, printer_options)
    else:
        output_path = Path(output).resolve()
        output_dir = output_path.parent
        output_dir.mkdir(parents=True, exist_ok=True)
        with output_path.open(mode="w") as f:
            print_ast(tu, f, printer_options)


@dataclass(frozen=True)
class AnalysisUnit:
    source_file: Path
    include_dirs: Tuple[Path, ...]
    defines: Tuple[str, ...]
    std_version_arg: Optional[str]


@dataclass(frozen=True)
class CodeLocation:
    line: int
    column: Optional[int]


@dataclass(frozen=True)
class Vulnerability:
    location: CodeLocation
    message: str
    severity: VulnerabilitySeverity


@dataclass(frozen=True)
class AnalysisResult:
    source_file: str
    vulnerbilities: List[Vulnerability]


_builtin_defines = (
    "__attribute__(x)=",
    "__restrict=",
    "__thread=",
    "__inline__=",
    "_Atomic(x)=(x)",
    "_Bool=char",
    "__signed__=signed",
    "__inline=",
    "__extension__=",
    "__attribute_deprecated_msg__(x)=",
    "__asm__(x)=",
    "__builtin_va_list=int",
    "_Float32=float",
    "_Float64=double",
    "__typeof__(x)=void",
    "typeof=__typeof__",
    "_Mdouble_=double",
    "_Float128=double",
    "_Float32x=float",
    "_Float64x=double",
    "__uint128_t=long",
    "__int128_t=long",
    "bool=_Bool",
    "va_end(_list)=",
)


class AnalyzerWrapper:
    _rules: Tuple[Rule, ...]
    _parallel_jobs: int
    _preprocessor: Preprocessor
    _enable_parsing_debug: bool
    _depress_warnings: bool

    def __init__(
        self,
        preprocessor: Preprocessor,
        rules: Sequence[Rule],
        parallel_jobs: int,
        enable_parsing_debug: bool,
        depress_warnings: bool,
    ) -> None:
        self._enable_parsing_debug = enable_parsing_debug
        self._depress_warnings = depress_warnings
        self._preprocessor = preprocessor
        self._rules = tuple(rules)
        if parallel_jobs < 1:
            raise ValueError(
                "Number of parallel jobs should be greater than 0: "
                f"{parallel_jobs}",
            )
        self._parallel_jobs = parallel_jobs

    def _do_analyze(self, unit: AnalysisUnit) -> AnalysisResult:
        matcher = PatternMatcher(self._rules)
        parser_options = ParserOptions(
            self._preprocessor.cpp,
            self._preprocessor.args,
            unit.include_dirs,
            unit.defines,
            unit.std_version_arg,
        )
        tu = parse(unit.source_file, parser_options, self._enable_parsing_debug)
        matcher.visit(tu)
        res = matcher.get_result()
        vulnerabilities = [
            Vulnerability(
                CodeLocation(r.location.line, r.location.column),
                r.message,
                r.severity,
            ) for r in res
        ]
        return AnalysisResult(str(unit.source_file), vulnerabilities)

    def _analyze_in_sequential(
        self,
        units: Sequence[AnalysisUnit],
    ) -> List[AnalysisResult]:
        res = []
        skip = 0
        for unit in units:
            try:
                res.append(self._do_analyze(unit))
            except (ParseError, CalledProcessError) as e:
                if not self._depress_warnings:
                    click.echo(
                        f"warning: unable to parse {unit.source_file}: {e}",
                    )
                skip += 1
        total = len(units)
        processed = total - skip
        click.echo(f"processed {processed}/{total} source files")
        return res

    def _analyze_in_parallel(
        self,
        units: Sequence[AnalysisUnit],
    ) -> List[AnalysisResult]:
        executor = ProcessPoolExecutor(max_workers=self._parallel_jobs)
        futures: List[Future[AnalysisResult]] = []
        for unit in units:
            futures.append(executor.submit(self._do_analyze, unit))
        res: List[AnalysisResult] = []
        skip = 0
        for index, future in enumerate(futures):
            try:
                res.append(future.result())
            except (ParseError, CalledProcessError) as e:
                file = units[index].source_file
                if not self._depress_warnings:
                    click.echo(
                        f"warning: unable to parse {file}: {e}",
                    )
                skip += 1
        executor.shutdown()
        total = len(units)
        processed = total - skip
        click.echo(f"analyzed {processed}/{total} source files")
        return list(res)

    def analyze(self, units: Sequence[AnalysisUnit]) -> List[AnalysisResult]:
        filtered_units = []
        for unit in units:
            if unit.source_file.suffix != ".c":
                continue
            try:
                if not unit.source_file.exists():
                    continue
            except PermissionError:
                continue
            filtered_units.append(unit)
        if self._parallel_jobs == 1:
            return self._analyze_in_sequential(filtered_units)
        else:
            return self._analyze_in_parallel(filtered_units)


@cli.command("analyze")
@click.argument("files", type=Path, nargs=-1)
@click.option(
    "--compdb", "compdb_path",
    type=Path, help="Path to compile_commands.json",
)
@click.option(
    "--jobs", "-j", "parallel_jobs",
    type=int, default=1,
    help="Number of parallel jobs",
)
@click.option(
    "--path-mapping", "path_mappings",
    multiple=True,
    help="Replace source file path, in the format /src:/dst",
)
@click.option(
    "--rule", "rule_paths",
    required=True,
    multiple=True,
    type=Path,
    help="Path to a YAML file containing matching rules, such as ./rules.yaml",
)
@click.option(
    "--plugin", "plugins",
    multiple=True,
    type=Path,
    help="Path to a Python file containing custom pattern constructors",
)
@click.option(
    "--define", "extra_defines",
    multiple=True,
    help="Path to a YAML file containing matching rules, such as ./rules.yaml",
)
@click.option(
    "--depress-warnings", "depress_warnings",
    default=False,
    is_flag=True,
    help="Depress parsing and analysis warnings",
)
@common_options
def analyze(
    preprocessor: str,
    include_dirs: Tuple[Path, ...],
    use_fake_include_dir: bool,
    compdb_path: Optional[Path],
    parallel_jobs: int,
    path_mappings: Tuple[str, ...],
    rule_paths: Tuple[Path, ...],
    output: str,
    enable_parsing_debug: bool,
    extra_defines: Tuple[str, ...],
    depress_warnings: bool,
    plugins: Tuple[Path, ...],
    files: Tuple[Path, ...],
) -> None:
    start = datetime.now()

    for plugin in plugins:
        import_and_register_plugins(plugin)

    cpp = Preprocessor.from_str(preprocessor)
    database: Optional[CompilationDatabase] = None

    if compdb_path is not None:
        database = CompilationDatabase(Path(compdb_path).resolve())
    path_converter = PathConverter(path_mappings)

    units: List[AnalysisUnit] = []
    defines: Tuple[str, ...] = _builtin_defines + extra_defines
    if len(files) != 0:
        for file in files:
            header_dirs: List[Path] = list(include_dirs)
            std_version_arg = None
            db_defines = tuple()
            if database:
                file = path_converter.reverse_convert(file)
                info = database.query(file)
                if info is not None:
                    header_dirs.extend([
                        path_converter.convert(d) for d in info[0].include_dirs
                    ])
                    db_defines = info[0].defines
                    std_version_arg = info[0].std_version_arg
            units.append(AnalysisUnit(
                path_converter.convert(file),
                tuple(header_dirs),
                defines=tuple(defines + db_defines),
                std_version_arg=std_version_arg
            ))
    elif database is not None:
        for info in database:
            units.append(AnalysisUnit(
                path_converter.convert(info.file),
                tuple([
                    path_converter.convert(d) for d in
                    list(include_dirs) + list(info.include_dirs)
                ]),
                defines=defines + info.defines,
                std_version_arg=info.std_version_arg,
            ))
    else:
        raise ValueError(
            "Neither source files nor compilation database is specified",
        )

    rules = []
    for rule_path in rule_paths:
        rules.extend(load_rules(rule_path))
    analyzer = AnalyzerWrapper(
        cpp, rules, parallel_jobs,
        enable_parsing_debug, depress_warnings,
    )
    analysis_res = filter(
        lambda r: len(r.vulnerbilities) != 0,
        analyzer.analyze(units))
    res = [asdict(r) for r in analysis_res]

    if output == "-":
        yaml.dump(res, stream=sys.stdout)
    else:
        output_path = Path(output).resolve()
        output_dir = output_path.parent
        output_dir.mkdir(exist_ok=True, parents=True)
        with output_path.open(mode="w") as f:
            yaml.dump(res, stream=f)

    end = datetime.now()
    seconds_used = (end - start).total_seconds()
    click.echo(f"analysis took {seconds_used:.3f} seconds")


if __name__ == "__main__":
    cli()
