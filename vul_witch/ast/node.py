from dataclasses import dataclass
from enum import auto, Enum
from typing import Optional, Sequence

from vul_witch.ast.location import CodeRange


@dataclass(frozen=True)
class AstNode:
    code_range: CodeRange


@dataclass(frozen=True)
class TranslationUnit(AstNode):
    nodes: Sequence[AstNode]
    pass


@dataclass(frozen=True)
class StringLiteral(AstNode):
    literal: str


@dataclass(frozen=True)
class Identifier(AstNode):
    name: str


@dataclass(frozen=True)
class ExternalDeclaration(AstNode):
    pass


@dataclass(frozen=True)
class Declaration(ExternalDeclaration):
    specifiers: Sequence["DeclarationSpecifierBase"]
    init_declarators: Optional[Sequence["DeclaratorBase"]]


@dataclass(frozen=True)
class StaticAssert(AstNode):
    expression: "ExpressionBase"
    message: StringLiteral


@dataclass(frozen=True)
class FunctionDefinition(ExternalDeclaration):
    pass


@dataclass(frozen=True)
class StaticAssertDeclaration(ExternalDeclaration):
    static_assert: StaticAssert


@dataclass(frozen=True)
class PreprocessNode(AstNode):
    pass


@dataclass(frozen=True)
class DefineDirective(PreprocessNode):
    identifier: str
    replacement: Optional[str]


@dataclass(frozen=True)
class FunctionDefineDirective(PreprocessNode):
    identifier: str
    params: Sequence[str]
    replacement: Optional[str]


@dataclass(frozen=True)
class UndefineDirective(PreprocessNode):
    identifier: str


@dataclass(frozen=True)
class PreprocessExpression(PreprocessNode):
    pass


@dataclass(frozen=True)
class ParenthesizedPreprocessExpression(PreprocessExpression):
    expression: PreprocessExpression


class PreprocessPrimitiveType(Enum):
    Identifier = "identifier"
    NumberLiteral = "number_literal"
    CharLiteral = "char_literal"


@dataclass(frozen=True)
class PreprocessPrimitive(PreprocessExpression):
    type_: PreprocessPrimitiveType
    value: str


@dataclass(frozen=True)
class PreprocessDefined(PreprocessExpression):
    identifier: str


class PreprocessUnaryOperator(Enum):
    Not = "!"
    Negate = "~"
    Minus = "-"
    Plus = "+"


@dataclass(frozen=True)
class PreprocessUnaryExpression(PreprocessExpression):
    operator: PreprocessUnaryOperator
    operand: PreprocessExpression


class PreprocessBinaryOperator(Enum):
    Add = "+"
    Sub = "-"
    Mul = "*"
    Div = "/"
    Mod = "%"
    ShortOr = "||"
    ShortAnd = "&&"
    Or = "|"
    Xor = "^"
    And = "&"
    Equal = "=="
    NotEqual = "!="
    Greater = ">"
    GreaterEq = ">="
    LessEq = "<="
    Less = "<"
    LeftShift = "<<"
    RightShift = ">>"


@dataclass(frozen=True)
class PreprocessBinaryExpression(PreprocessExpression):
    operator: PreprocessBinaryOperator
    lhs: PreprocessExpression
    rhs: PreprocessExpression


@dataclass(frozen=True)
class PreprocessCallExpression(PreprocessExpression):
    callee: str
    arguments: Sequence[PreprocessExpression]


class IncludeTargetType(Enum):
    SystemLibString = "system_lib_string"
    StringLiteral = "string_literal"
    Identifier = "identifier"
    CallExpression = "preproc_call_expression"


@dataclass(frozen=True)
class IncludeDirective(PreprocessNode):
    type_: IncludeTargetType
    target: str | PreprocessCallExpression

    def to_system_lib_string(self) -> str:
        assert self.type_ == IncludeTargetType.SystemLibString
        assert isinstance(self.target, str)
        return self.target

    def to_string_literal(self) -> str:
        assert self.type_ == IncludeTargetType.StringLiteral
        assert isinstance(self.target, str)
        return self.target

    def to_identifier(self) -> str:
        assert self.type_ == IncludeTargetType.Identifier
        assert isinstance(self.target, str)
        return self.target

    def to_call_expression(self) -> PreprocessCallExpression:
        assert self.type_ == IncludeTargetType.CallExpression
        assert isinstance(self.target, PreprocessCallExpression)
        return self.target


@dataclass(frozen=True)
class DirectiveWithOptionalGroup(PreprocessNode):
    group: Optional[Sequence[AstNode]]


@dataclass(frozen=True)
class IfGroupDirective(DirectiveWithOptionalGroup):
    pass


@dataclass(frozen=True)
class IfDirective(IfGroupDirective):
    condition: PreprocessExpression


@dataclass(frozen=True)
class IfDefDirective(IfGroupDirective):
    identifier: str


@dataclass(frozen=True)
class IfUndefDirective(IfGroupDirective):
    identifier: str


@dataclass(frozen=True)
class ElifDirective(DirectiveWithOptionalGroup):
    condition: PreprocessExpression


@dataclass(frozen=True)
class ElseDirective(DirectiveWithOptionalGroup):
    pass


@dataclass(frozen=True)
class EndIfDirective(PreprocessNode):
    pass


@dataclass(frozen=True)
class IfSectionDirective(PreprocessNode):
    if_group: IfGroupDirective
    elif_groups: Optional[Sequence[ElifDirective]]
    else_group: Optional[ElseDirective]
    endif: EndIfDirective


@dataclass(frozen=True)
class LineDirective(PreprocessNode):
    raw_directive: str


@dataclass(frozen=True)
class ErrorDirective(PreprocessNode):
    message: Optional[str]


@dataclass(frozen=True)
class PragmaDirective(PreprocessNode):
    raw_directive: Optional[str]


@dataclass(frozen=True)
class EmptyDirective(PreprocessNode):
    pass


@dataclass(frozen=True)
class DeclarationSpecifierBase(AstNode):
    pass


class StorageClassSpecifierKind(Enum):
    # Typedef = "typedef"
    Extern = "extern"
    Static = "static"
    ThreadLocal = "_Thread_local"
    Auto = "auto"
    Register = "register"


@dataclass(frozen=True)
class StorageClassSpecifier(DeclarationSpecifierBase):
    kind: StorageClassSpecifierKind


@dataclass(frozen=True)
class TypeSpecifier(DeclarationSpecifierBase):
    pass


class PrimitiveTypeSpecifierKind(Enum):
    Void = "void"
    Char = "char"
    Short = "short"
    Int = "int"
    Long = "long"
    Float = "float"
    Double = "double"
    Signed = "signed"
    Unsigned = "unsigned"
    Bool = "_Bool"
    Complex = "_Complex"


@dataclass(frozen=True)
class PrimitiveTypeSpecifier(TypeSpecifier):
    kind: PrimitiveTypeSpecifierKind


@dataclass(frozen=True)
class AtomicTypeSpecifier(TypeSpecifier):
    type_name: "TypeName"


@dataclass(frozen=True)
class StructOrUnionSpecifier(TypeSpecifier):
    is_struct: bool
    identifier: Optional[Identifier]
    declarations: Optional[Sequence["StructDeclarationBase"]]


@dataclass(frozen=True)
class StructDeclarationBase(AstNode):
    pass


@dataclass(frozen=True)
class StructField(StructDeclarationBase):
    specifier_qualifier_list: Sequence["TypeSpecifier | TypeQualifier"]
    declarators: Sequence["StructDeclarator"]
    attribute: Optional["Attribute"]


@dataclass(frozen=True)
class StructDeclarator(AstNode):
    declarator: "DeclaratorBase"
    bit_width: Optional["ExpressionBase"]


@dataclass(frozen=True)
class StructStaticAssert(StructDeclarationBase):
    assertion: StaticAssert


@dataclass(frozen=True)
class MacroStructDeclarationBase(StructDeclarationBase):
    pass


@dataclass(frozen=True)
class MacroDefStructDeclaration(MacroStructDeclarationBase):
    define: DefineDirective


@dataclass(frozen=True)
class MacroFunctionDefStructDeclaration(MacroStructDeclarationBase):
    function_def: FunctionDefineDirective


@dataclass(frozen=True)
class MacroDirectiveStructDeclaration(MacroStructDeclarationBase):
    call: PreprocessNode


@dataclass(frozen=True)
class MacroStructDeclarationGroupBase(AstNode):
    declarations: Optional[Sequence[StructDeclarationBase]]


@dataclass(frozen=True)
class MacroStructDeclarationIfGroup(MacroStructDeclarationGroupBase):
    condition: PreprocessExpression


@dataclass(frozen=True)
class MacroStructDeclarationIfdefGroup(MacroStructDeclarationGroupBase):
    identifier: Identifier
    is_ifndef: bool


@dataclass(frozen=True)
class MacroStructDeclarationElifGroup(MacroStructDeclarationGroupBase):
    condition: PreprocessExpression


@dataclass(frozen=True)
class MacroStructDeclarationElseGroup(MacroStructDeclarationGroupBase):
    pass


@dataclass(frozen=True)
class MacroConditionalStructDeclaration(MacroStructDeclarationBase):
    if_group: MacroStructDeclarationIfGroup | MacroStructDeclarationIfdefGroup
    elif_groups: Optional[Sequence[MacroStructDeclarationElifGroup]]
    else_group: Optional[MacroStructDeclarationElseGroup]


@dataclass(frozen=True)
class EnumSpecifier(TypeSpecifier):
    # C11 6.7.2.2 Enumeration specifiers
    identifier: Optional[Identifier]
    enumerators: Optional[Sequence["EnumeratorBase"]]


@dataclass(frozen=True)
class EnumeratorBase(AstNode):
    pass


@dataclass(frozen=True)
class Enumerator(EnumeratorBase):
    identifier: Identifier
    expression: Optional["ExpressionBase"]


@dataclass(frozen=True)
class MacroEnumeratorGroupBase(AstNode):
    enumerators: Optional[Sequence[Enumerator]]


@dataclass(frozen=True)
class MacroEnumeratorIfGroup(MacroEnumeratorGroupBase):
    condition: PreprocessExpression


@dataclass(frozen=True)
class MacroEnumeratorIfdefGroup(MacroEnumeratorGroupBase):
    identifier: Identifier
    is_ifndef: bool


@dataclass(frozen=True)
class MacroEnumeratorElifGroup(MacroEnumeratorGroupBase):
    condition: PreprocessExpression


@dataclass(frozen=True)
class MacroEnumeratorElseGroup(MacroEnumeratorGroupBase):
    pass


@dataclass(frozen=True)
class MacroEnumeratorList(EnumeratorBase):
    if_group: MacroEnumeratorIfGroup | MacroEnumeratorIfdefGroup
    elif_groups: Optional[Sequence[MacroEnumeratorElifGroup]]
    else_group: Optional[MacroEnumeratorElseGroup]


@dataclass(frozen=True)
class MacroDirectiveEnumerator(EnumeratorBase):
    call: PreprocessNode


@dataclass(frozen=True)
class TypedefName(TypeSpecifier):
    type_identifier: str


@dataclass(frozen=True)
class MacroTypeSpecifier(TypeSpecifier):
    identifier: Identifier
    type_name: "TypeName"


class TypeQualifierKind(Enum):
    Const = "const"
    Restrict = "restrict"
    Volatile = "volatile"
    Atomic = "_Atomic"
    # `_Nonnull` is a Clang extension
    # See https://clang.llvm.org/docs/AttributeReference.html#nonnull
    Nonnull = "_Nonnull"
    # `_Null_unspecified` is a Clang extension
    # See https://clang.llvm.org/docs/AttributeReference.html#null-unspecified
    NullUnspecified = "_Null_unspecified"
    # `_Nullable` is a Clang extension
    # See https://clang.llvm.org/docs/AttributeReference.html#nullable
    Nullable = "_Nullable"


@dataclass(frozen=True)
class TypeQualifier(DeclarationSpecifierBase):
    kind: TypeQualifierKind


@dataclass(frozen=True)
class AbstractDeclaratorBase(AstNode):
    pass


@dataclass(frozen=True)
class AbstractPointerDeclarator(AbstractDeclaratorBase):
    type_qualifier_list: Optional[Sequence[TypeQualifier]]
    declarator: Optional[AbstractDeclaratorBase]


@dataclass(frozen=True)
class AbstractFunctionDeclarator(AbstractDeclaratorBase):
    declarator: Optional[AbstractDeclaratorBase]
    parameter_type_list: Optional[Sequence["ParameterDeclaration"]]
    is_variadic: bool


@dataclass(frozen=True)
class AbstractArrayDeclarator(AbstractDeclaratorBase):
    declarator: Optional[AbstractDeclaratorBase]
    array_size: "ArraySize"


@dataclass(frozen=True)
class AbstractParenthesizedDeclarator(AbstractDeclaratorBase):
    declarator: AbstractDeclaratorBase


class ArraySizeKind(Enum):
    Unknown = auto()  # []
    VariableUnknown = auto()  # [*]
    VariableExpression = auto()  # [expression]
    StaticExpression = auto()  # [static expression]


@dataclass(frozen=True)
class ArraySize(AstNode):
    kind: ArraySizeKind
    type_qualifiers: Optional[Sequence[TypeQualifier]]
    expression: Optional["ExpressionBase"]


@dataclass(frozen=True)
class ParameterDeclaration(AstNode):
    specifiers: Sequence[DeclarationSpecifierBase]
    declarator: "DeclaratorBase" | Optional[AbstractDeclaratorBase]
    attribute_list: Optional[Sequence["Attribute"]]


@dataclass(frozen=True)
class TypeName(AstNode):
    specifier_qualifier_list: Sequence[TypeSpecifier | TypeQualifier]
    declarator: Optional[AbstractDeclaratorBase]


@dataclass(frozen=True)
class DeclaratorBase(AstNode):
    pass


@dataclass(frozen=True)
class IdentifierDeclarator(DeclaratorBase):
    identifier: Identifier


@dataclass(frozen=True)
class PointerDeclarator(DeclaratorBase):
    type_qualifier_list: Optional[Sequence[TypeQualifier]]
    declarator: DeclaratorBase


@dataclass(frozen=True)
class FunctionDeclarator(DeclaratorBase):
    declarator: DeclaratorBase
    parameter_type_list: Optional[Sequence["ParameterDeclaration"]]
    is_variadic: bool


@dataclass(frozen=True)
class ArrayDeclarator(DeclaratorBase):
    declarator: DeclaratorBase
    array_size: "ArraySize"


@dataclass(frozen=True)
class ParenthesizedDeclarator(DeclaratorBase):
    declarator: DeclaratorBase


@dataclass(frozen=True)
class InitDeclarator(DeclaratorBase):
    declarator: "DeclaratorBase"
    initializer: "InitializerBase"


@dataclass(frozen=True)
class InitializerBase(AstNode):
    pass


@dataclass(frozen=True)
class ExpressionInitializer(InitializerBase):
    expression: "ExpressionBase"


@dataclass(frozen=True)
class InitializerList(InitializerBase):
    items: Sequence["InitializerListItem"]


@dataclass(frozen=True)
class InitializerListItem(AstNode):
    designators: Optional[Sequence["DesignatorBase"]]
    initializer: InitializerBase


@dataclass(frozen=True)
class DesignatorBase(AstNode):
    pass


@dataclass(frozen=True)
class IndexDesignator(DesignatorBase):
    index: "ExpressionBase"


@dataclass(frozen=True)
class MemberDesignator(DesignatorBase):
    member: Identifier


@dataclass(frozen=True)
class RangeDesignator(DesignatorBase):
    # A range designator is a GCC extension and has the syntax `[from ... to]`.
    # See https://gcc.gnu.org/onlinedocs/gcc/Designated-Inits.html#Designated-Inits
    from_: "ExpressionBase"
    to: "ExpressionBase"




class FunctionSpecifierKind(Enum):
    Inline = "inline"
    Noreturn = "_Noreturn"


@dataclass(frozen=True)
class FunctionSpecifier(DeclarationSpecifierBase):
    kind: FunctionSpecifierKind


@dataclass(frozen=True)
class AlignmentSpecifierBase(DeclarationSpecifierBase):
    pass


@dataclass(frozen=True)
class AlignmentTypeSpecifier(AlignmentSpecifierBase):
    type_name: TypeName


@dataclass(frozen=True)
class AlignmentConstExpressionSpecifier(AlignmentSpecifierBase):
    expression: "ExpressionBase"


@dataclass(frozen=True)
class ExtendedDeclarationSpecifier(DeclarationSpecifierBase):
    extension: "ExtensionBase"


@dataclass(frozen=True)
class ExpressionBase(AstNode):
    pass


@dataclass(frozen=True)
class CompoundLiteral(ExpressionBase):
    type_name: TypeName
    initializer_list: Sequence[InitializerListItem]


@dataclass(frozen=True)
class IdentifierExpression(ExpressionBase):
    identifier: Identifier


@dataclass(frozen=True)
class ExtensionBase(AstNode):
    pass


@dataclass(frozen=True)
class Attribute(ExtensionBase):
    # See https://gcc.gnu.org/onlinedocs/gcc/Attribute-Syntax.html
    arguments: Optional[Sequence[ExpressionBase]]


@dataclass(frozen=True)
class AsmLabel(ExtensionBase):
    # See https://gcc.gnu.org/onlinedocs/gcc/Asm-Labels.html
    string_literal: str
