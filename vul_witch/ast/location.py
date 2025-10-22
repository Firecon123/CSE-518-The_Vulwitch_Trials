from dataclasses import dataclass


@dataclass(frozen=True)
class CodeLocation:
    line: int
    column: int


@dataclass(frozen=True)
class CodeRange:
    file: str
    start: CodeLocation
    end: CodeLocation
