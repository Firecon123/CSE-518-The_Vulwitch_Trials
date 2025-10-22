from argparse import ArgumentParser
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import sys
from tree_sitter import Language, Node, Parser
from typing import Sequence


class SupportedLanguage(Enum):
    C = "c"
    CXX = "c++"
    Java = "java"
    Python = "python"
    Kotlin = "kotlin"
    Scala = "scala"
    PHP = "php"
    CSharp = "c#"
    Ruby = "ruby"
    JavaScript = "javascript"
    Swift = "swift"
    Go = "go"
    Fortran = "fortran"


@dataclass(frozen=True)
class DumpOption:
    lang: SupportedLanguage
    files: Sequence[str]


def _dump_tree_sitter(node: Node, depth: int) -> None:
    indent = " " * depth
    print(f"{indent}{node.type} (from {node.start_point} to {node.end_point})")

    for child in node.children:
        _dump_tree_sitter(child, depth + 2)


def _dump_file(code_file: Path, parser: Parser) -> None:
    with code_file.open(mode="rb") as f:
        module = parser.parse(f.read())
        _dump_tree_sitter(module.root_node, depth=0)


def _get_parser(dump_option: DumpOption) -> Parser:
    lang = dump_option.lang
    lang_impl: Language
    if lang == SupportedLanguage.C:
        import tree_sitter_c as tsc
        lang_impl = Language(tsc.language())
    elif lang == SupportedLanguage.CXX:
        import tree_sitter_cpp as tscpp
        lang_impl = Language(tscpp.language())
    elif lang == SupportedLanguage.Java:
        import tree_sitter_java as tsjava
        lang_impl = Language(tsjava.language())
    elif lang == SupportedLanguage.Python:
        import tree_sitter_python as tspython
        lang_impl = Language(tspython.language())
    elif lang == SupportedLanguage.Kotlin:
        import tree_sitter_kotlin as tskotlin
        lang_impl = Language(tskotlin.language())
    elif lang == SupportedLanguage.Scala:
        import tree_sitter_scala as ts_impl
        lang_impl = Language(ts_impl.language())
    elif lang == SupportedLanguage.PHP:
        import tree_sitter_php as tsphp
        lang_impl = Language(tsphp.language_php())
    elif lang == SupportedLanguage.CSharp:
        import tree_sitter_c_sharp as tscsharp
        lang_impl = Language(tscsharp.language())
    elif lang == SupportedLanguage.Ruby:
        import tree_sitter_ruby as tsruby
        lang_impl = Language(tsruby.language())
    elif lang == SupportedLanguage.JavaScript:
        import tree_sitter_javascript as tsjavascript
        lang_impl = Language(tsjavascript.language())
    elif lang == SupportedLanguage.Swift:
        import tree_sitter_swift as tsswift
        lang_impl = Language(tsswift.language())
    elif lang == SupportedLanguage.Go:
        import tree_sitter_go as tsgo
        lang_impl = Language(tsgo.language())
    elif lang == SupportedLanguage.Fortran:
        import tree_sitter_fortran as tsfortran
        lang_impl = Language(tsfortran.language())
    else:
        raise ValueError("unreachable code")
    return Parser(lang_impl)


def _dump_files(dump_option: DumpOption) -> None:
    parser = _get_parser(dump_option)
    for file_name in dump_option.files:
        parser.reset()
        _dump_file(Path(file_name), parser)


def _parse_dump_option(prog: str, raw_args: Sequence[str]) -> DumpOption:
    arg_parser = ArgumentParser(prog, description="Dump code with tree-sitter")
    arg_parser.add_argument(
        "--lang", required=True, dest="lang",
        choices=[lang.value for lang in SupportedLanguage],
        help="Language of files to dump",
    )
    arg_parser.add_argument(
        "files", nargs="+", help="Files to dump",
    )
    args = arg_parser.parse_args(raw_args)
    return DumpOption(SupportedLanguage(args.lang), args.files)


if __name__ == "__main__":
    dump_option = _parse_dump_option(sys.argv[0], sys.argv[1:])
    _dump_files(dump_option)
