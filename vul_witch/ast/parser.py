from abc import ABCMeta, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from pycparser import preprocess_file
from pycparser.c_ast import FileAST
from pycparser.c_parser import CParser
from typing import List, Optional, Tuple

from vul_witch.ast.node import TranslationUnit


class CParserInterface(metaclass=ABCMeta):
    @abstractmethod
    def parse_module(self) -> TranslationUnit:
        pass

@dataclass(frozen=True)
class ParserOptions:
    preprocessor: Path
    preprocessor_args: Tuple[str, ...]
    include_dirs: Tuple[Path, ...]
    defines: Tuple[str, ...]
    std_version_arg: Optional[str]


def parse(filename: Path, options: ParserOptions, debug=False) -> FileAST:
    cpp_args: List[str] = list(options.preprocessor_args)
    if options.std_version_arg is not None:
        cpp_args.append(options.std_version_arg)
    cpp_args.extend(map(lambda m: f"-D{m}", options.defines))
    cpp_args.extend(map(lambda d: f"-I{d}", options.include_dirs))
    content = preprocess_file(
      str(filename), str(options.preprocessor), cpp_args,
    )
    parser = CParser()
    return parser.parse(content, str(filename), debug=debug)
