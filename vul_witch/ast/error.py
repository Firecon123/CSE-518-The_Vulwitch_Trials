from typing import NoReturn, Optional

from vul_witch.ast.location import CodeRange


class CodeError(Exception):
    _error_message: str
    _code_range: CodeRange

    def __init__(self, error_message: str, code_range: CodeRange) -> None:
        start = code_range.start
        end = code_range.end
        message = (
            f"a code error occurs at {code_range.file}, "
            f"from position {start.line}:{start.column} "
            f"to position {end.line}:{end.column}: {error_message}"
        )
        super().__init__(message)
        self._error_message = error_message
        self._code_range = code_range

    @property
    def code_range(self) -> CodeRange:
        return self._code_range

    @property
    def error_message(self) -> str:
        return self._error_message


class Unreachable(Exception):
    pass


def unreachable(error_message: Optional[str] = None) -> NoReturn:
    if error_message is None:
        raise Unreachable()
    else:
        raise Unreachable(error_message)
