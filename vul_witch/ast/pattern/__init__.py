from abc import abstractmethod, ABCMeta
from collections.abc import Set
from functools import cache
import inspect
from pycparser.c_ast import Node
from sexpdata import Symbol
from typing import Any, Dict, Optional, TypeVar
from typing_extensions import override, Self


SubjectT = TypeVar("SubjectT")


class AbstractPatternContext(metaclass=ABCMeta):
    @abstractmethod
    def build(self, data: Any) -> "AbstractPattern[Any]":
        pass


class AbstractPattern[SubjectT](metaclass=ABCMeta):
    @abstractmethod
    def match(self, subject: SubjectT) -> bool:
        pass

    @classmethod
    @abstractmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        pass


class WildcardPattern(AbstractPattern[Any]):
    @override
    def match(self, subject: Any) -> bool:
        return True

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if data == Symbol("_"):
            return cls()
        else:
            return None


class AstPattern(AbstractPattern[Node]):
    _ast_node_type: str
    _patterns: Dict[str, AbstractPattern[Any]]

    def __init__(
        self,
        ast_node_type: str,
        **named_patterns: AbstractPattern[Any],
    ) -> None:
        self._ast_node_type = ast_node_type
        self._patterns = dict()
        for field_name, pattern in named_patterns.items():
            self._add_named_pattern(field_name, pattern)

    @cache
    @staticmethod
    def _get_ast_node_types() -> Set[str]:
        types: Set[str] = set()
        from pycparser import c_ast
        for name, member in inspect.getmembers(c_ast):
            if inspect.isclass(member) and issubclass(member, Node):
                types.add(name)
        return frozenset(types)

    def _add_named_pattern(
        self,
        name: str,
        pattern: AbstractPattern[Any],
    ) -> None:
        if name in self._patterns:
            raise ValueError(f"pattern already exists: {name}")
        self._patterns[name] = pattern

    @override
    def match(self, subject: Node) -> bool:
        if not isinstance(subject, Node):
            return False
        if self._ast_node_type != type(subject).__name__:
            return False
        for field_name, pattern in self._patterns.items():
            if not hasattr(subject, field_name):
                return False
            if not pattern.match(getattr(subject, field_name)):
                return False
        return True

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) == 0:
            return None
        first = data[0]
        if not isinstance(first, Symbol):
            return None

        ast_node_type = first.value()
        types = AstPattern._get_ast_node_types()
        if ast_node_type not in types:
            return None

        size = len(data)
        index = 1
        patterns: Dict[str, AbstractPattern[Any]] = dict()
        while index < size:
            field_name = cls._parse_field_name(data[index].value())
            index += 1
            if index >= size:
                raise ValueError(
                    f"pattern for AST node field `{field_name}` "
                    "is not specified",
                )
            patterns[field_name] = context.build(data[index])
            index += 1
        return cls(ast_node_type, **patterns)


    @classmethod
    def _parse_field_name(cls, data: str) -> str:
        if not data.endswith(":"):
            raise ValueError(
                f"invalid pattern to extract field name of an AST node: {data}",
            )
        field_name = data[:-1]
        if len(field_name) == 0:
            raise ValueError("field name of an AST node cannot be empty")
        return field_name
