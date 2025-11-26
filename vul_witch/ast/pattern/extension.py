from collections.abc import Sequence
from sexpdata import Symbol
from typing import Any, Optional, Tuple
from typing_extensions import override, Self

from vul_witch.ast.pattern import AbstractPattern, AbstractPatternContext


class AnyPattern(AbstractPattern[Any]):
    _patterns: Tuple[AbstractPattern[Any], ...]

    def __init__(self, patterns: Sequence[AbstractPattern[Any]]) -> None:
        self._patterns = tuple(patterns)

    @override
    def match(self, subject: Any) -> bool:
        return any(map(lambda p: p.match(subject), self._patterns))

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) == 0:
            return None
        if data[0] != Symbol("#any"):
            return None
        patterns = []
        for subdata in data[1:]:
            patterns.append(context.build(subdata))
        return cls(patterns)


class AllPattern(AbstractPattern[Any]):
    _patterns: Tuple[AbstractPattern[Any], ...]

    def __init__(self, patterns: Sequence[AbstractPattern[Any]]) -> None:
        self._patterns = tuple(patterns)

    @override
    def match(self, subject: Any) -> bool:
        return all(map(lambda p: p.match(subject), self._patterns))

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) == 0:
            return None
        if data[0] != Symbol("#all"):
            return None
        patterns = []
        for subdata in data[1:]:
            patterns.append(context.build(subdata))
        return cls(patterns)


class EqPattern(AbstractPattern[Any]):
    _value: Any

    def __init__(self, value: Any) -> None:
        self._value = value

    @override
    def match(self, subject: Any) -> bool:
        return self._value == subject

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) != 2:
            return None
        if data[0] != Symbol("#eq"):
            return None
        return cls(data[1])


class NotPattern(AbstractPattern[Any]):
    _pattern: AbstractPattern[Any]

    def __init__(self, pattern: AbstractPattern[Any]) -> None:
        self._pattern = pattern

    @override
    def match(self, subject: Any) -> bool:
        return not self._pattern.match(subject)

    @override
    @classmethod
    def try_build(
        cls,
        context: AbstractPatternContext,
        data: Any,
    ) -> Optional[Self]:
        if not isinstance(data, list) or len(data) != 2:
            return None
        if data[0] != Symbol("#not"):
            return None
        return cls(context.build(data[1]))
