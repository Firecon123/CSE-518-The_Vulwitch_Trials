from dataclasses import dataclass
from enum import auto, Enum
from typing import Optional, Sequence

from vul_witch.ast.location import CodeRange


@dataclass(frozen=True)
class AstNodeBase:
    code_range: CodeRange


@dataclass(frozen=True)
class TranslationUnit(AstNodeBase):
    nodes: Sequence[AstNodeBase]
    pass


@dataclass(frozen=True)
class Identifier(AstNodeBase):
    name: str


@dataclass(frozen=True)
class ExternalDeclarationBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class DeclarationBase(ExternalDeclarationBase):
    pass


@dataclass(frozen=True)
class ConcreteDeclaration(DeclarationBase):
    specifiers: Sequence["DeclarationSpecifierBase"]
    init_declarators: Optional[Sequence["DeclaratorBase"]]


@dataclass(frozen=True)
class StaticAssert(DeclarationBase):
    expression: "ExpressionBase"
    message: "StringLiteral"


@dataclass(frozen=True)
class FunctionDefinition(ExternalDeclarationBase):
    specifiers: Sequence["DeclarationSpecifierBase"]
    declarator: "DeclaratorBase"
    compound_statement: "CompoundStatement"


@dataclass(frozen=True)
class PreprocessNodeBase(AstNodeBase):
    pass


TopLevelType = PreprocessNodeBase | ExternalDeclarationBase


@dataclass(frozen=True)
class DefineDirective(PreprocessNodeBase):
    identifier: str
    replacement: Optional[str]


@dataclass(frozen=True)
class FunctionDefineDirective(PreprocessNodeBase):
    identifier: str
    params: Sequence[str]
    replacement: Optional[str]


@dataclass(frozen=True)
class UndefineDirective(PreprocessNodeBase):
    identifier: str


@dataclass(frozen=True)
class PreprocessExpression(PreprocessNodeBase):
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


class BinaryOperator(Enum):
    Add = "+"
    Sub = "-"
    Mul = "*"
    Div = "/"
    Mod = "%"
    LogicalOr = "||"
    LogicalAnd = "&&"
    BitwiseOr = "|"
    Xor = "^"
    BitwiseAnd = "&"
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
    operator: BinaryOperator
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
    CallExpression = "call_expression"


@dataclass(frozen=True)
class IncludeDirective(PreprocessNodeBase):
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
class DirectiveWithOptionalGroup(PreprocessNodeBase):
    group: Optional[Sequence[AstNodeBase]]


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
class EndIfDirective(PreprocessNodeBase):
    pass


@dataclass(frozen=True)
class IfSectionDirective(PreprocessNodeBase):
    if_group: IfGroupDirective
    elif_groups: Optional[Sequence[ElifDirective]]
    else_group: Optional[ElseDirective]
    endif: EndIfDirective


@dataclass(frozen=True)
class LineDirective(PreprocessNodeBase):
    raw_directive: str


@dataclass(frozen=True)
class ErrorDirective(PreprocessNodeBase):
    message: Optional[str]


@dataclass(frozen=True)
class PragmaDirective(PreprocessNodeBase):
    raw_directive: Optional[str]


@dataclass(frozen=True)
class EmptyDirective(PreprocessNodeBase):
    pass


@dataclass(frozen=True)
class DeclarationSpecifierBase(AstNodeBase):
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
class StructDeclarationBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class StructField(StructDeclarationBase):
    specifier_qualifier_list: Sequence["TypeSpecifier | TypeQualifier"]
    declarators: Sequence["StructDeclarator"]
    attribute: Optional["Attribute"]


@dataclass(frozen=True)
class StructDeclarator(AstNodeBase):
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
    call: PreprocessNodeBase


@dataclass(frozen=True)
class MacroStructDeclarationGroupBase(AstNodeBase):
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
class EnumeratorBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class Enumerator(EnumeratorBase):
    identifier: Identifier
    expression: Optional["ExpressionBase"]


@dataclass(frozen=True)
class MacroEnumeratorGroupBase(AstNodeBase):
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
    call: PreprocessNodeBase


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
class AbstractDeclaratorBase(AstNodeBase):
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


class ArraySizeKind(Enum):
    Unknown = auto()  # []
    VariableUnknown = auto()  # [*]
    VariableExpression = auto()  # [expression]
    StaticExpression = auto()  # [static expression]


@dataclass(frozen=True)
class ArraySize(AstNodeBase):
    kind: ArraySizeKind
    type_qualifiers: Optional[Sequence[TypeQualifier]]
    expression: Optional["ExpressionBase"]


@dataclass(frozen=True)
class ParameterDeclaration(AstNodeBase):
    specifiers: Sequence[DeclarationSpecifierBase]
    declarator: "DeclaratorBase" | Optional[AbstractDeclaratorBase]
    attribute_list: Optional[Sequence["Attribute"]]


@dataclass(frozen=True)
class TypeName(AstNodeBase):
    specifier_qualifier_list: Sequence[TypeSpecifier | TypeQualifier]
    declarator: Optional[AbstractDeclaratorBase]


@dataclass(frozen=True)
class DeclaratorBase(AstNodeBase):
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
class InitDeclarator(DeclaratorBase):
    declarator: "DeclaratorBase"
    initializer: "InitializerBase"


@dataclass(frozen=True)
class InitializerBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class ExpressionInitializer(InitializerBase):
    expression: "ExpressionBase"


@dataclass(frozen=True)
class InitializerList(InitializerBase):
    items: Sequence["InitializerListItem"]


@dataclass(frozen=True)
class InitializerListItem(AstNodeBase):
    designators: Optional[Sequence["DesignatorBase"]]
    initializer: InitializerBase


@dataclass(frozen=True)
class DesignatorBase(AstNodeBase):
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
class ExpressionBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class StringLiteral(ExpressionBase):
    literal: str


class ConstantKind(Enum):
    Integer = auto()
    Float = auto()
    Character = auto()


@dataclass(frozen=True)
class Constant(ExpressionBase):
    kind: ConstantKind
    value: str


@dataclass(frozen=True)
class BinaryExpression(ExpressionBase):
    operator: BinaryOperator
    lhs: ExpressionBase
    rhs: ExpressionBase


@dataclass(frozen=True)
class GenericAssociation(AstNodeBase):
    type_name: TypeName
    expression: ExpressionBase


@dataclass(frozen=True)
class GenericSelection(ExpressionBase):
    # C11 6.5.1.1 Generic selection
    expression: ExpressionBase
    association_list: Optional[Sequence[GenericAssociation]]
    default: ExpressionBase


@dataclass(frozen=True)
class ConditionalExpression(ExpressionBase):
    # C11 6.5.15 Conditional operator
    condition: ExpressionBase
    first: ExpressionBase
    second: ExpressionBase


@dataclass(frozen=True)
class CommaExpression(ExpressionBase):
    # C11 6.5.17 Comma operator
    expressions: Sequence[ExpressionBase]


class AssignmentOperator(Enum):
    Assign = "="
    AssignMul = "*="
    AssignDiv = "/="
    AssignMod = "%="
    AssignAdd = "+="
    AssignSub = "-="
    AssignLeftShift = "<<="
    AssignRightShift = ">>="
    AsiggnBitwiseAnd = "&="
    AsiggnBitwiseXor = "^="
    AsiggnBitwiseOr = "|="


@dataclass(frozen=True)
class AssignmentExpression(ExpressionBase):
    # C11 6.5.16 Assignment operators
    operator: AssignmentOperator
    lhs: ExpressionBase
    rhs: ExpressionBase


@dataclass(frozen=True)
class CompoundLiteral(ExpressionBase):
    type_name: TypeName
    initializer_list: Sequence[InitializerListItem]


@dataclass(frozen=True)
class IdentifierExpression(ExpressionBase):
    identifier: Identifier


@dataclass(frozen=True)
class CallExpression(ExpressionBase):
    # C11 6.5.2 Postfix operators
    callee: ExpressionBase
    arguments: Optional[Sequence[ExpressionBase]]


class MemberExpressionKind(Enum):
    Direct = auto()
    Indirect = auto()


@dataclass(frozen=True)
class MemberExpression(ExpressionBase):
    kind: MemberExpressionKind
    object_: ExpressionBase
    field: Identifier


@dataclass(frozen=True)
class SubscriptExpression(ExpressionBase):
    # 6.5.2.1 Array subscripting
    object_: ExpressionBase
    subscript: ExpressionBase


@dataclass(frozen=True)
class StatementExpression(ExpressionBase):
     # GCC supports using a compound statement as an expression if the
     # statement is wrapped inside an pair of parentheses. For example,
     #
     # ({ int y = foo (); int z;
     #    if (y > 0) z = y;
     #    else z = - y;
     #    z; })
     #
     # See https://gcc.gnu.org/onlinedocs/gcc/Statement-Exprs.html
     statement: "CompoundStatement"


class UnaryOperator(Enum):
    # C11 6.5.3 Unary operators
    PostIncrement = auto()
    PostDecrement = auto()
    PreIncrement = auto()
    PreDecrement = auto()
    Address = auto()
    Deference = auto()
    Plus = auto()
    Minus = auto()
    Complement = auto()
    LogicalNegate = auto()


@dataclass(frozen=True)
class UnaryExpression(ExpressionBase):
    operator: UnaryOperator
    expression: ExpressionBase


@dataclass(frozen=True)
class ExtensionBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class Attribute(ExtensionBase):
    # See https://gcc.gnu.org/onlinedocs/gcc/Attribute-Syntax.html
    arguments: Optional[Sequence[ExpressionBase]]


@dataclass(frozen=True)
class AsmLabel(ExtensionBase):
    # See https://gcc.gnu.org/onlinedocs/gcc/Asm-Labels.html
    string_literal: str


@dataclass(frozen=True)
class StatementBase(AstNodeBase):
    pass


@dataclass(frozen=True)
class ExpressionStatement(StatementBase):
    # C11 6.8.3 Expression and null statements
    expression: Optional[ExpressionBase]


@dataclass(frozen=True)
class LabeledStatementBase(StatementBase):
    # C11 6.8.1 Labeled statements
    pass

@dataclass(frozen=True)
class IdentifierLabeledStatement(LabeledStatementBase):
    idenfier: Identifier
    statement: StatementBase


@dataclass(frozen=True)
class CaseStatement(LabeledStatementBase):
    condition: ExpressionBase
    statement: StatementBase

@dataclass(frozen=True)
class DefaultStatement(LabeledStatementBase):
    statement: StatementBase


@dataclass(frozen=True)
class IfStatement(StatementBase):
    # C11 6.8.4.1 The if statement
    condition: ExpressionBase
    first: StatementBase
    second: Optional[StatementBase]


@dataclass(frozen=True)
class SwitchStatemen(StatementBase):
    # C11 6.8.4.2 The switch statement
    condition: ExpressionBase
    statemen: StatementBase


@dataclass(frozen=True)
class WhileStatement(StatementBase):
    # C11 6.8.5.1 The while statement
    condition: ExpressionBase
    body : StatementBase


@dataclass(frozen=True)
class DoWhileStatement(StatementBase):
    # C11 6.8.5.2 The do statement
    condition: ExpressionBase
    body: StatementBase


@dataclass(frozen=True)
class ForStatement(StatementBase):
    # C11 6.8.5.3 The forstatement
    initializer: DeclarationBase | ExpressionBase
    condition: ExpressionBase
    step: ExpressionBase
    body: StatementBase


CompoundStatementItemType = StatementBase | DeclarationBase | PreprocessNodeBase


@dataclass(frozen=True)
class CompoundStatement(StatementBase):
    items: Sequence[CompoundStatementItemType]


@dataclass(frozen=True)
class ExpressionStatment(StatementBase):
    expression: Optional[ExpressionBase]


@dataclass(frozen=True)
class GotoStatement(StatementBase):
    # C11 6.8.6.1 The goto statement
    identifier: Identifier


@dataclass(frozen=True)
class ContinueStatement(StatementBase):
    # C11 6.8.6.2 The continue statement
    pass


@dataclass(frozen=True)
class BreakStatement(StatementBase):
    # C11 6.8.6.3 The break statement
    pass


@dataclass(frozen=True)
class ReturnStatement(StatementBase):
    # C11 6.8.6.4 The return statement
    expression: Optional[ExpressionBase]
