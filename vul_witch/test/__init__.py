from pycparser.c_ast import FileAST
from pycparser.c_parser import CParser
from unittest import TestCase


class AstTestCaseBase(TestCase):
    @staticmethod
    def parse_c_source(
        c_source: str,
        filename: str = "",
    ) -> FileAST:
        parser = CParser()
        return parser.parse(c_source, filename)
