from dataclasses import dataclass
from enum import auto, Enum
from typing import List, Optional


class CType:
    _is_const: bool

    @property
    def is_const(self) -> bool:
        return self._is_const


class Void(CType):
    pass


class Bool(CType):
    pass


class Char(CType):
    _is_signed: Optional[bool]

    @property
    def is_signed(self) -> Optional[bool]:
        return self._is_signed


class Short(CType):
    _is_signed: bool

    @property
    def is_signed(self) -> bool:
        return self._is_signed


class Int(CType):
    _is_signed: bool

    @property
    def is_signed(self) -> bool:
        return self._is_signed


class Long(CType):
    _is_signed: bool
    _has_long_specifier: bool

    @property
    def is_signed(self) -> bool:
        return self._is_signed

    @property
    def has_long_specifier(self) -> bool:
        return self._has_long_specifier


class FloatingType(CType):
    pass


class Float(FloatingType):
    pass


class Double(FloatingType):
    _has_long_specifier: bool

    @property
    def has_long_specifier(self) -> bool:
        return self._has_long_specifier


class VagueType(CType):
    _name: str

    def name(self) -> str:
        return self._name


class Complex(CType):
    _base_type: FloatingType

    @property
    def base_type(self) -> FloatingType:
        return self._base_type


class Imaginary(CType):
    _base_type: FloatingType

    @property
    def base_type(self) -> FloatingType:
        return self._base_type


class Pointer(CType):
    _inner_type: CType


@dataclass(frozen=True)
class NamedField:
    name: str
    type_: CType


class StructOrUnion(CType):
    _fields: Optional[List[NamedField]]
    _is_struct: bool

    @property
    def fields(self) -> Optional[List[NamedField]]:
        if self._fields is None:
            return None
        else:
            return self._fields.copy()

    @property
    def is_struct(self) -> bool:
        return self._is_struct


class TypeQualifier(Enum):
    Const = auto()
    Restrict = auto()
    Volatile = auto()
