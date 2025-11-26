from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from typing_extensions import override


@dataclass(frozen=True)
class CompDbEntry:
    file: Path
    directory: Path
    arguments: Tuple[str, ...]
    output: Optional[Path]


@dataclass(frozen=True)
class CompilationInfo:
    file: Path
    directory: Path
    include_dirs: Tuple[Path, ...]
    output: Optional[Path]
    defines: Tuple[str, ...]
    std_version_arg: Optional[str]


class CompilationDatabase(Iterable[CompilationInfo]):
    _info: Dict[Path, List[CompilationInfo]]

    def __init__(self, compdb_path: Path):
        if not compdb_path.exists():
            raise FileNotFoundError(
                f"compilation database does not exist: {compdb_path}",
            )
        with compdb_path.open() as f:
            data = json.load(f)
        self._info = defaultdict(list)
        for entry_data in data:
            output = entry_data.get("output")
            entry = CompDbEntry(
                file=Path(entry_data["file"]),
                directory=Path(entry_data["directory"]),
                arguments=tuple(entry_data["arguments"]),
                output=Path(output) if output is not None else None,
            )
            if entry.file in self._info:
                continue
            include_dirs = CompilationDatabase._extract_include_directories(
                entry,
            )
            defines = CompilationDatabase._extract_defines(entry)
            std_version = CompilationDatabase._extract_std_version(entry)
            info = CompilationInfo(
                file=entry.file,
                directory=entry.directory,
                include_dirs=include_dirs,
                defines=defines,
                output=entry.output,
                std_version_arg=std_version
            )
            assert info.file not in self._info
            self._info[info.file].append(info)

    @override
    def __iter__(self) -> Iterator[CompilationInfo]:
        for _, info_list in self._info.items():
            for info in info_list:
                yield info

    def query(self, source_file: Path) -> Optional[List[CompilationInfo]]:
        return self._info.get(source_file)

    @staticmethod
    def _resolve_include_directory(
        entry: CompDbEntry, include_dir: str,
    ) -> Path:
        dir_path = Path(include_dir)
        if dir_path.is_absolute():
            return dir_path
        else:
            return entry.directory / include_dir

    @staticmethod
    def _extract_defines(entry: CompDbEntry) -> Tuple[str, ...]:
        index = 0
        size = len(entry.arguments)
        defines: List[str] = []
        while index < size:
            argument = entry.arguments[index]
            if argument == "-D":
                if index + 1 >= size:
                    raise ValueError(
                        f"macro not specified for {argument}",
                    )
                index += 1
                defines.append(entry.arguments[index])
            elif argument.startswith("-D"):
                defines.append(argument[len("-D"):])
            index += 1
        return tuple(defines)

    @staticmethod
    def _extract_std_version(entry: CompDbEntry) -> Optional[str]:
        for argument in entry.arguments:
            if argument.startswith("-std="):
                return argument
        return None

    @staticmethod
    def _extract_include_directories(entry: CompDbEntry) -> Tuple[Path, ...]:
        index = 0
        size = len(entry.arguments)
        include_directories: List[Path] = []
        while index < size:
            argument = entry.arguments[index]
            if argument == "-I" or argument == "-isystem":
                if index + 1 >= size:
                    raise ValueError(
                        f"include directory not specified for {argument}",
                    )
                index += 1
                include_directories.append(
                    CompilationDatabase._resolve_include_directory(
                        entry, entry.arguments[index],
                    ),
                )
            elif argument.startswith("-I"):
                include_directories.append(
                    CompilationDatabase._resolve_include_directory(
                        entry, argument[len("-I"):],
                    ),
                )
            elif argument.startswith("-isystem"):
                include_directories.append(
                    CompilationDatabase._resolve_include_directory(
                        entry, argument[len("-isystem"):],
                    ),
                )
            index += 1
        return tuple(include_directories)
