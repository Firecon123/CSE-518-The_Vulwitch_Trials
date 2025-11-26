from dataclasses import dataclass
from enum import Enum
from pycparser.c_ast import FileAST
from typing import TextIO


class PrinterFormat(Enum):
    PLAIN = "plain"
    JSON = "json"


@dataclass(frozen=True)
class PrinterOptions:
    indent: int
    show_location: bool
    show_attribute_name: bool
    output_format: PrinterFormat = PrinterFormat.PLAIN


def print_ast(tu: FileAST, output: TextIO, options: PrinterOptions) -> None:
    tu.show(
        output,
        offset=options.indent,
        attrnames=options.show_attribute_name,
        showcoord=options.show_location,
    )
