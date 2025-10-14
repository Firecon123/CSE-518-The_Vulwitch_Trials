import tree_sitter as ts
from typing import Optional

from vul_witch.ast.location import CodeLocation, CodeRange


class TreeSitterHelper:
    @staticmethod
    def is_node_type(cursor: ts.TreeCursor, node_type: str) -> bool:
        if cursor.node is None:
            return False
        return cursor.node.type == node_type

    @staticmethod
    def is_node_type_in(cursor: ts.TreeCursor, *node_types: str) -> bool:
        if cursor.node is None:
            return False
        return cursor.node.type in node_types

    @staticmethod
    def parse_raw_content(cursor: ts.TreeCursor) -> Optional[str]:
        if cursor.node and cursor.node.text is not None:
            return cursor.node.text.decode()
        else:
            return None

    @staticmethod
    def from_ts_point(point: ts.Point) -> CodeLocation:
        return CodeLocation(point.row, point.column)

    @staticmethod
    def from_ts_node_start(cursor: ts.TreeCursor) -> CodeLocation:
        node = cursor.node
        assert node is not None
        return TreeSitterHelper.from_ts_point(node.start_point)

    @staticmethod
    def from_ts_node_end(cursor: ts.TreeCursor) -> CodeLocation:
        node = cursor.node
        assert node is not None
        return TreeSitterHelper.from_ts_point(node.end_point)

    @staticmethod
    def from_ts_node(file: str, cursor: ts.TreeCursor) -> CodeRange:
        node = cursor.node
        assert node is not None
        return CodeRange(
            file,
            TreeSitterHelper.from_ts_point(node.start_point),
            TreeSitterHelper.from_ts_point(node.end_point),
        )
