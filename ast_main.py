import sys
from typing import List

from vul_witch.ast.backend.tree_sitter.parser import TreeSitterCParser


def _build_with_tree_sitter(files: List[str]) -> None:
    for file_name in files:
        parser = TreeSitterCParser(file_name)
        tu = parser.parse_module()


if __name__ == "__main__":
    _build_with_tree_sitter(sys.argv[1:])
