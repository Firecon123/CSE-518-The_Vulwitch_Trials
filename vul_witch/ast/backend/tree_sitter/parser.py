from abc import ABCMeta, abstractmethod
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from tree_sitter import Language, Node, Parser, Tree, TreeCursor
import tree_sitter_c as tsc
from typing import Dict, List, Optional, Tuple
from typing_extensions import override

from vul_witch.ast import node
from vul_witch.ast.backend.tree_sitter.utils import TreeSitterHelper
from vul_witch.ast.error import CodeError, unreachable
from vul_witch.ast.location import CodeLocation, CodeRange
from vul_witch.ast.node import AstNode, TranslationUnit
from vul_witch.ast.parser import CParserInterface


class TreeSitterCDeclarationModifierType(Enum):
    StorageClassSpecifier = "storage_class_specifier"
    TypeQualifier = "type_qualifier"
    AlignasQualifier = "alignas_qualifier"
    AttributeSpecifier = "attribute_specifier"
    AttributeDeclaration = "attribute_declaration"
    MsDeclspecModifier = "ms_declspec_modifier"


class TreeSitterCTypeQualifierType(Enum):
    Const = "const"
    Constexpr = "constexpr"  # C23
    Volatile = "volatile"
    Restrict = "restrict"
    GCCRestrict = "__restrict__"
    # A GCC keyword to suppress warnings about extensions
    GCCExtesion = "__extension__"
    Atomic = "_Atomic"  # C11
    Noreturn = "_Noreturn"  # C11
    NoreturnMacro = "noreturn"  # A macro in <stdnoreturn.h> introduced in C11
    Nonnull = "_Nonnull"  # A Clang extension


class TreeSitterCStorageClassSpecifier(Enum):
    Extern = "extern"
    Static = "static"
    Auto = "auto"
    Register = "register"
    # For inline variants, see https://stackoverflow.com/questions/2765164/inline-vs-inline-vs-inline-vs-forceinline
    Inline = "inline"  # C99
    MSVCInline = "__inline"  # MSVC C90
    GCCInline = "__line__"  # GCC C90
    MSVCForceInline = "__forceinline"  # MSVC
    # Thread-local
    ThreadLocal = "thread_local"  # C23
    GCCThreadLocal = "__thread"


class TreeSitterCTypeSpecifierType(Enum):
    # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4728-L4760
    StructSpecifier = "struct_specifier"
    UnionSpecifier = "union_specifier"
    EnumSpecifier = "enum_specifier"
    MacroTypeSpecifier = "macro_type_specifier"
    SizedTypeSpecifier = "sized_type_specifier"
    PrimitiveType = "primitive_type"
    TypeIdentifier = "type_identifier"


class TreeSitterCPrimitivType(Enum):
    # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4937-L5048
    Bool = "bool"
    Char = "char"
    Int = "int"
    Float = "float"
    Double = "double"
    Void = "void"
    SizeT = "size_t"
    SsizeT = "ssize_t"
    PtrdiffT = "ptrdiff_t"
    IntptrT = "intptr_t"
    UintptrT = "uintptr_t"
    CharptrT = "charptr_t"
    NullptrT = "nullptr_t"
    MaxAlignT = "max_align_t"
    Int8T = "int8_t"
    Int16T = "int16_t"
    Int32T = "int32_t"
    Int64T = "int64_t"
    Uint8T = "uint8_t"
    Uint16T = "uint16_t"
    Uint32T = "uint32_t"
    Uint64T = "uint64_t"
    Char8T = "char8_t"
    Char16T = "char16_t"
    Char32T = "char32_t"
    Char64T = "char64_t"


class TreeSitterPreprocessElseType(Enum):
    # The unsupoorted type `preproc_elifdef` represents `#elifdef` and `#elifndef`
    # directives introduced in C23, see https://en.cppreference.com/w/c/preprocessor/conditional.html
    Else = "preproc_else"
    Elif = "proproc_elif"


class TreeSitterTopLevelPreprocessType(Enum):
    If = "preproc_if"
    IfDef = "preproc_ifdef"
    Include = "preproc_include"
    Def = "preproc_def"
    FunctionDef = "preproc_function_def"
    Call = "preproc_call"


class TreeSitterTopLevelCNodeType(Enum):
    # The types of top-level items, i.e., those can be direct children of an
    # instance of `TranslationUnit`, except for preprocessing directives.
    # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L13-L78
    Declaration = "declaration"
    FunctionDefinition = "function_definition"
    LinkageSpecification = "linkage_specification"
    AttributedStatement = "attributed_statement"
    TypeDefinition = "type_definition"
    ExpressionStatement = "expression_statement"


class TreeSitterCMsCallModifier(Enum):
    # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3345-L3373
    CDecl = "__cdecl"
    ClrCall = "__clrcall"
    StdCall = "__stdcall"
    FastCall = "__fastcall"
    ThisCall = "__thiscall"
    VectorCall = "__vectorcall"


class TreeSitterAbstractDeclaratorType(Enum):
    # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3641-L3661
    PointerDeclarator = "abstract_pointer_declarat"
    FunctionDeclarator = "abstract_function_declarator"
    ArrayDeclarator = "abstract_array_declarator"
    ParenthesizedDeclarator = "abstract_parenthesized_declarator"


@dataclass(frozen=True)
class CodeFix:
    byte_start: int  # inclusive
    byte_end: int  # exclusive
    replacement: bytes


class ParsingFixerInterface(metaclass=ABCMeta):
    @abstractmethod
    def node_type(self) -> str:
        pass

    @abstractmethod
    def can_fix(self, tree: Tree, curosr: TreeCursor) -> bool:
        pass

    @abstractmethod
    def fix(self, tree: Tree, cursor: TreeCursor) -> CodeFix:
        pass


class ParsingFixerRegistry:
    _registry: Dict[str, List[ParsingFixerInterface]] = defaultdict(list)

    @classmethod
    def register(cls, fixer: ParsingFixerInterface) -> bool:
        node_type = fixer.node_type()
        fixer_list = cls._registry[node_type]

        if fixer in fixer_list:
            return False
        else:
            fixer_list.append(fixer)
            return True

    @classmethod
    def lookup_fixer(
        cls,
        tree: Tree,
        cursor: TreeCursor,
    ) -> Optional[ParsingFixerInterface]:
        if cursor.node is None:
            return None

        node_type = cursor.node.type
        for fixer in cls._registry[node_type]:
            if fixer.can_fix(tree, cursor):
                return fixer

        return None


class TreeSitterCParser(CParserInterface):
    _source: bytes
    _source_file: str
    _parser: Parser
    _tree: Tree
    _cursor: TreeCursor

    def __init__(self, source_file: str) -> None:
        source_path = Path(source_file).resolve()
        self._source_file = str(source_path)

        if not source_path.exists() or not source_path.is_file():
            raise ValueError(f"invalid C source file: {self._source_file}")

        with source_path.open(mode="rb") as f:
            self._source = f.read()

        self._parser = Parser(Language(tsc.language()))
        self._tree = self._parser.parse(self._source)
        self._cursor = self._tree.walk()

    def _has_error(self) -> bool:
        if self._cursor.node is None:
            return False

        return self._cursor.node.has_error

    def _try_fix_error(self) -> bool:
        raise NotImplementedError()

    def _parse_node(self) -> AstNode:
        raise NotImplementedError()

    def _create_code_error(self, err_msg: str) -> CodeError:
        return CodeError(err_msg, self._get_current_code_range())

    @override
    def parse_module(self) -> TranslationUnit:
        tu = self._cursor.node
        assert tu is not None and tu.type == "translation_unit"
        tu_code_range = self._get_current_code_range()

        if self._cursor.node is None:
            return TranslationUnit(tu_code_range, [])

        self._cursor.goto_first_child()
        nodes = []
        while True:
            if self._has_error() and not self._try_fix_error():
                raise self._create_code_error(f"{self._cursor.node.type}")
            if not self._should_skip():
                nodes.append(self._parse_top_level_ast_node())

            if not self._cursor.goto_next_sibling():
                break

        return TranslationUnit(tu_code_range, nodes)

    def _get_first_child(self) -> Node:
        assert self._cursor.node is not None
        return self._cursor.node.children[0]

    def _get_child_count(self) -> int:
        assert self._cursor.node is not None
        return self._cursor.node.child_count

    def _get_sibling_count(self) -> int:
        node = self._cursor.node
        assert node is not None
        parent = node.parent
        assert parent is not None
        return parent.child_count

    def _get_current_code_range(self) -> CodeRange:
        return TreeSitterHelper.from_ts_node(self._source_file, self._cursor)

    def _get_current_code_start(self) -> CodeLocation:
        return TreeSitterHelper.from_ts_node_start(self._cursor)

    def _get_current_code_end(self) -> CodeLocation:
        return TreeSitterHelper.from_ts_node_end(self._cursor)

    def _should_skip(self) -> bool:
        assert self._cursor.node is not None
        return self._cursor.node.type in (
            "comment",
        )

    def _parse_top_level_ast_node(self) -> AstNode:
        ast_node = self._try_parse_top_level_ast_node()
        if ast_node is None:
            assert self._cursor.node is not None
            raise self._create_code_error(
                f"unsupported node type: {self._cursor.node.type}",
            )
        return ast_node

    def _try_parse_top_level_ast_node(self) -> Optional[AstNode]:
        if self._is_top_level_preprocess_directive():
            return self._parse_top_level_preprocess_directive()
        elif self._is_top_level_c_ordinary_node():
            return self._parse_top_level_c_node()
        else:
            return None

    def _is_top_level_c_ordinary_node(self) -> bool:
        for c_node_type in TreeSitterTopLevelCNodeType:
            if self._is_node_type(c_node_type.value):
                return True
        return False

    def _is_tree_sitter_type_definition(self) -> bool:
        return self._is_node_type(
            TreeSitterTopLevelCNodeType.TypeDefinition.value,
        )

    def _is_tree_sitter_function_definition(self) -> bool:
        return self._is_node_type(
            TreeSitterTopLevelCNodeType.FunctionDefinition.value,
        )

    def _parse_c_function_definition(self):
        raise NotImplementedError()

    def _parse_c_type_definition(self) -> node.Declaration:
        raise NotImplementedError()

    def _parse_top_level_c_node(self) -> AstNode:
        if self._is_c_declaration():
            return self._parse_c_declaration()
        elif self._is_tree_sitter_type_definition():
            return self._parse_c_type_definition()
        elif self._is_tree_sitter_function_definition():
            return self._parse_c_function_definition()
        raise NotImplementedError()

    def _is_c_declaration(self) -> bool:
        return self._is_node_type(TreeSitterTopLevelCNodeType.Declaration.value)

    def _is_c_declaration_modifier(self) -> bool:
        for t in TreeSitterCDeclarationModifierType:
            if self._is_node_type(t.value):
                return True
        return False

    def _is_c_storage_class_specifier(self) -> bool:
        if not self._is_node_type(
            TreeSitterCDeclarationModifierType.StorageClassSpecifier.value,
        ):
            return False

        specifier = self._get_first_child().type
        if specifier in (
            TreeSitterCStorageClassSpecifier.Extern.value,
            TreeSitterCStorageClassSpecifier.Static.value,
            TreeSitterCStorageClassSpecifier.Auto.value,
            TreeSitterCStorageClassSpecifier.Register.value,
            TreeSitterCStorageClassSpecifier.ThreadLocal.value,
            TreeSitterCStorageClassSpecifier.GCCThreadLocal.value,
        ):
            return True
        else:
            return False

    def _consume_c_storage_class_specifier(self) -> node.StorageClassSpecifier:
        code_range = self._get_current_code_range()

        specifier = self._get_first_child().type
        kind: node.StorageClassSpecifierKind
        if specifier == TreeSitterCStorageClassSpecifier.Extern.value:
            kind = node.StorageClassSpecifierKind.Extern
        elif specifier == TreeSitterCStorageClassSpecifier.Static.value:
            kind = node.StorageClassSpecifierKind.Static
        elif specifier == TreeSitterCStorageClassSpecifier.Auto.value:
            kind = node.StorageClassSpecifierKind.Auto
        elif specifier == TreeSitterCStorageClassSpecifier.Register.value:
            kind = node.StorageClassSpecifierKind.Register
        elif specifier in (
            TreeSitterCStorageClassSpecifier.ThreadLocal.value,
            TreeSitterCStorageClassSpecifier.GCCThreadLocal.value,
        ):
            kind = node.StorageClassSpecifierKind.ThreadLocal
        else:
            unreachable()

        self._cursor.goto_next_sibling()
        return node.StorageClassSpecifier(code_range, kind)

    def _is_c_type_qualifier(self) -> bool:
        if not self._is_node_type(
            TreeSitterCDeclarationModifierType.TypeQualifier.value,
        ):
            return False

        qualifier = self._get_first_child().type
        return qualifier in (
            TreeSitterCTypeQualifierType.Const.value,
            TreeSitterCTypeQualifierType.Volatile.value,
            TreeSitterCTypeQualifierType.Restrict.value,
            TreeSitterCTypeQualifierType.GCCRestrict.value,
            TreeSitterCTypeQualifierType.Atomic.value,
            TreeSitterCTypeQualifierType.Nonnull.value,
        )

    def _consume_c_type_qualifier(self) -> node.TypeQualifier:
        code_range = self._get_current_code_range()
        qualifier = self._get_first_child().type

        kind: node.TypeQualifierKind
        if qualifier == TreeSitterCTypeQualifierType.Const.value:
            kind = node.TypeQualifierKind.Const
        elif qualifier == TreeSitterCTypeQualifierType.Volatile.value:
            kind = node.TypeQualifierKind.Volatile
        elif qualifier in (
            TreeSitterCTypeQualifierType.Restrict.value,
            TreeSitterCTypeQualifierType.GCCRestrict.value,
        ):
            kind = node.TypeQualifierKind.Restrict
        elif qualifier == TreeSitterCTypeQualifierType.Atomic.value:
            kind = node.TypeQualifierKind.Atomic
        elif qualifier == TreeSitterCTypeQualifierType.Nonnull.value:
            kind = node.TypeQualifierKind.Nonnull
        else:
            raise self._create_code_error(
                f"unsupported type qualifier {qualifier}"
            )

        self._cursor.goto_next_sibling()
        return node.TypeQualifier(code_range, kind)

    def _is_c_struct_or_union_specifier(self) -> bool:
        return self._is_node_type_in(
            TreeSitterCTypeSpecifierType.StructSpecifier.value,
            TreeSitterCTypeSpecifierType.UnionSpecifier.value,
        )

    def _is_c_enum_specifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCTypeSpecifierType.EnumSpecifier.value,
        )

    def _is_tree_sitter_macro_type_specifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCTypeSpecifierType.MacroTypeSpecifier.value,
        )

    def _is_tree_sitter_sized_type_specifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCTypeSpecifierType.SizedTypeSpecifier.value,
        )

    def _is_c_primitive_type_specifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCTypeSpecifierType.PrimitiveType.value,
        )

    def _is_tree_sitter_type_identifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCTypeSpecifierType.TypeIdentifier.value,
        )

    def _consume_tree_sitter_type_identifier_as_c_identifier(
        self
    ) -> node.Identifier:
        assert self._is_tree_sitter_type_identifier()
        code_range = self._get_current_code_range()

        name = self._consume_raw_content()

        return node.Identifier(code_range, name)

    def _is_c_type_specifier(self) -> bool:
        return (
            self._is_c_struct_or_union_specifier() or
            self._is_c_enum_specifier() or
            self._is_tree_sitter_macro_type_specifier() or
            self._is_tree_sitter_sized_type_specifier() or
            self._is_c_primitive_type_specifier() or
            self._is_tree_sitter_type_identifier()
        )

    def _is_tree_sitter_field_declaration_list(self) -> bool:
        return self._is_node_type(node_type="field_declaration_list")

    def _is_c_struct_field_declaration(self) -> bool:
        return self._is_node_type(node_type="field_declaration")

    def _is_c_bitfield_clause(self) -> bool:
        return self._is_node_type(node_type="bitfield_clause")

    def _consume_c_bitfield_caluse(self) -> node.ExpressionBase:
        self._cursor.goto_first_child()

        self._consume_colon()
        exp = self._consume_c_expression()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return exp

    def _consume_c_struct_declarator(self) -> node.StructDeclarator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5512-L5578
        declarator = self._consume_tree_sitter_declarator()
        bit = (
            self._consume_c_bitfield_caluse()
            if self._is_c_bitfield_clause() else None
        )
        code_range = CodeRange(
            self._source_file,
            declarator.code_range.start,
            bit.code_range.end if bit else declarator.code_range.end,
        )
        return node.StructDeclarator(code_range, declarator, bit)

    def _consume_c_struct_field_declaration(self) -> node.StructField:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5475-L5511
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        type_specs = self._consume_c_type_specifier_qualifier_list(
            at_most=self._get_sibling_count(),
        )

        declarators = []
        if self._is_tree_sitter_declarator():
            declarators.append(self._consume_c_struct_declarator())
        while self._is_comma():
            self._consume_comma()
            declarators.append(self._consume_c_struct_declarator())
        attribute = (
            self._consume_c_attribute() if self._is_c_attribute() else None
        )
        self._consume_semicolon()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.StructField(code_range, type_specs, declarators, attribute)

    def _is_preproc_if_field_declaration_list(self) -> bool:
        return self._is_node_type(
            node_type="preproc_if_in_field_declaration_list",
        )

    def _is_preproc_ifdef_field_declaration_list(self) -> bool:
        return self._is_node_type(
            node_type="preproc_ifdef_in_field_declaration_list"
        )

    def _consume_preproc_field_declaratin_if_group(
        self,
    ) -> node.MacroStructDeclarationIfGroup:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L724-L813
        code_start = self._get_current_code_start()
        self._consume_node_with_type(node_type="#if")
        condition = self._consume_preprocess_expression()
        self._consume_new_line()
        declarations = []
        while self._is_tree_sitter_field_declaration():
            declarations.append(self._consume_c_struct_field_declaration())
        code_end = (
            declarations[-1].code_range.end
            if declarations else condition.code_range.end
        )

        return node.MacroStructDeclarationIfGroup(
            CodeRange(self._source_file, code_start, code_end),
            declarations, condition,
        )

    def _consume_preproc_field_declaratin_ifdef_group(
        self,
    ) -> node.MacroStructDeclarationIfdefGroup:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L814-L913
        code_start = self._get_current_code_start()
        is_ifndef = self._is_node_type(node_type="#ifndef")
        self._cursor.goto_next_sibling()
        identifier = self._consume_c_identifier()
        declarations = []
        while self._is_tree_sitter_field_declaration():
            declarations.append(self._consume_c_struct_field_declaration())
        code_end = (
            declarations[-1].code_range.end
            if declarations else identifier.code_range.end
        )

        return node.MacroStructDeclarationIfdefGroup(
            CodeRange(self._source_file, code_start, code_end),
            declarations, identifier, is_ifndef,
        )

    def _is_preproc_elif_field_declaration_list(self) -> bool:
        return self._is_node_type(
            node_type="preproc_elif_in_field_declaration_list",
        )

    def _consume_preproc_elif_field_declaration_list(
        self,
    ) -> node.MacroStructDeclarationElifGroup:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L939-L1019
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#elif")
        condition = self._consume_preprocess_expression()
        self._consume_new_line()

        declarations = []
        while self._is_tree_sitter_field_declaration():
            declarations.append(self._consume_tree_sitter_field_declaration())

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroStructDeclarationElifGroup(
            code_range, declarations if declarations else None, condition,
        )

    def _is_preproc_elifdef_field_declaration_list(self) -> bool:
        return self._is_node_type(
            node_type="preproc_elifdef_in_field_declaration_list",
        )

    def _is_preproc_else_field_declaration_list(self) -> bool:
        return self._is_node_type(
            node_type="preproc_else_in_field_declaration_list",
        )

    def _consume_preproc_else_field_declaration_list(
        self,
    ) -> node.MacroStructDeclarationElseGroup:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L914-L938
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#else")
        declarations = []
        while self._is_tree_sitter_field_declaration():
            declarations.append(self._consume_tree_sitter_field_declaration())

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroStructDeclarationElseGroup(
            code_range, declarations if declarations else None,
        )

    def _consume_preproc_condtional_field_declaration_list(
        self,
    ) -> node.MacroConditionalStructDeclaration:
        is_ifdef = self._is_preproc_ifdef_field_declaration_list()
        self._cursor.goto_first_child()

        if_group = (
            self._consume_preproc_field_declaratin_ifdef_group()
            if is_ifdef
            else self._consume_preproc_field_declaratin_if_group()
        )
        elif_groups: List[node.MacroStructDeclarationElifGroup] = []
        while (
            self._is_preproc_elif_field_declaration_list() or
            self._is_preproc_elifdef_field_declaration_list()
        ):
            if self._is_preproc_elifdef_field_declaration_list():
                raise self._create_code_error(
                    "#elifdef or #elifndef is not supported"
                )
            else:
                elif_groups.append(
                    self._consume_preproc_elif_field_declaration_list(),
                )
        else_group = (
            self._consume_preproc_else_field_declaration_list()
            if self._is_preproc_else_field_declaration_list() else None
        )
        code_end = self._get_current_code_end()
        self._consume_node_with_type(node_type="#endif")

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroConditionalStructDeclaration(
            CodeRange(self._source_file, if_group.code_range.start, code_end),
            if_group, elif_groups if elif_groups else None, else_group,
        )

    def _is_tree_sitter_field_declaration(self) -> bool:
        return (
            self._is_c_struct_field_declaration() or
            self._is_preprocess_define() or
            self._is_preprocess_function_define() or
            self._is_preprocess_call() or
            self._is_preproc_if_field_declaration_list() or
            self._is_preproc_ifdef_field_declaration_list()
        )

    def _consume_tree_sitter_field_declaration(
        self,
    ) -> node.StructDeclarationBase:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5436-L5474
        if self._is_c_struct_field_declaration():
            return self._consume_c_struct_field_declaration()
        elif self._is_preprocess_define():
            define = self._parse_preprocess_define()
            self._cursor.goto_next_sibling()
            return node.MacroDefStructDeclaration(define.code_range, define)
        elif self._is_preprocess_function_define():
            function_define = self._parse_preprocess_function_define()
            self._cursor.goto_next_sibling()
            return node.MacroFunctionDefStructDeclaration(
                function_define.code_range, function_define,
            )
        elif self._is_preprocess_call():
            directive = self._parse_preprocess_call()
            self._cursor.goto_next_sibling()
            return node.MacroDirectiveStructDeclaration(
                directive.code_range, directive,
            )
        elif (
            self._is_preproc_if_field_declaration_list() or
            self._is_preproc_ifdef_field_declaration_list()
        ):
            return self._consume_preproc_condtional_field_declaration_list()
        else:
            raise self._create_code_error(
                "unsupported field declaration of struct or union",
            )

    def _consume_tree_sitter_field_declaration_list(
        self,
    ) -> Sequence[node.StructDeclarationBase]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5416-L5435
        self._cursor.goto_first_child()

        self._consume_left_brace()
        declarations = []
        while not self._is_right_brace():
            declarations.append(self._consume_tree_sitter_field_declaration())
        self._consume_right_brace()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return declarations

    def _consume_c_struct_or_union_specifier(
        self,
    ) -> node.StructOrUnionSpecifier:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5246-L5415
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        is_struct = True
        if self._is_node_type(
            TreeSitterCTypeSpecifierType.UnionSpecifier.value,
        ):
            is_struct = False
            self._consume_node_with_type(node_type="union")
        else:
            self._consume_node_with_type(node_type="struct")

        if self._is_node_type_in("attribute_specifier", "ms_declspec_modifier"):
            raise self._create_code_error("unsupported tree-sitter-c node")

        id_ = None
        if self._is_tree_sitter_type_identifier():
            id_ = self._consume_tree_sitter_type_identifier_as_c_identifier()
        declarations = None
        if self._is_tree_sitter_field_declaration_list():
            declarations = self._consume_tree_sitter_field_declaration_list()

        if id_ is None and declarations is None:
            raise self._create_code_error(
                "both identifier and declaration list of "
                f"{'struct' if is_struct else 'union'} are empty"
            )

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.StructOrUnionSpecifier(
            code_range, is_struct, id_, declarations,
        )

    def _is_tree_sitter_enumerator_list(self) -> bool:
        return self._is_node_type(node_type="enumerator_list")

    def _is_tree_sitter_enumerator(self) -> bool:
        return self._is_node_type(node_type="enumerator")

    def _consume_tree_sitter_enumerator(self) -> node.Enumerator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5592-L5629
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        identifier = self._consume_c_identifier()
        expression = None
        if self._is_equal_sign():
            expression = self._consume_c_expression()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.Enumerator(code_range, identifier, expression)

    def _is_tree_sitter_preproc_if_enumerator(self) -> bool:
        return self._is_node_type(node_type="preproc_if_in_enumerator_list")

    def _is_tree_sitter_preproc_ifdef_enumerator(self) -> bool:
        return self._is_node_type(node_type="preproc_ifdef_in_enumerator_list")

    def _is_tree_sitter_preproc_if_enumerator_no_comma(self) -> bool:
        return self._is_node_type(
            node_type="preproc_if_in_enumerator_list_no_comma",
        )

    def _is_tree_sitter_preproc_ifdef_enumerator_no_comma(self) -> bool:
        return self._is_node_type(
            node_type="preproc_ifdef_in_enumerator_list_no_comma",
        )

    def _is_tree_sitter_preproc_else_enumerator(self) -> bool:
        return self._is_node_type_in(
            "preproc_else_in_enumerator_list",
            "preproc_else_in_enumerator_list_no_comma",
        )

    def _consume_tree_sitter_preproc_else_enumerator(
        self,
    ) -> node.MacroEnumeratorElseGroup:
        # For `preproc_else_in_enumerator_list`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1319-L1352
        # For `preproc_else_in_enumerator_list_no_comma`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1733-L1757
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#else")
        count = self._get_sibling_count() - 1
        enumerators = []
        for _ in range(count):
            if self._is_tree_sitter_enumerator():
                enumerators.append(self._consume_tree_sitter_enumerator())
            else:
                assert self._is_comma()
                self._consume_comma()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroEnumeratorElseGroup(
            code_range,
            enumerators if enumerators else None,
        )

    def _is_tree_sitter_preproc_elif_enumerator(self) -> bool:
        return self._is_node_type_in(
            "preproc_elif_in_enumerator_list",
            "preproc_elif_in_enumerator_list_no_comma",
        )

    def _consume_tree_sitter_preproc_elif_enumerator(
        self,
    ) -> node.MacroEnumeratorElifGroup:
        # For `preproc_elif_in_enumerator_list`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1353-L1442
        # For `preproc_elif_in_enumerator_list_no_comma`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1758-L1838
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#elif")
        condition = self._consume_preprocess_expression()
        self._consume_new_line()
        enumerators = []
        while self._is_tree_sitter_enumerator():
            enumerators.append(self._consume_tree_sitter_enumerator())
            if self._is_comma():
                self._consume_comma()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroEnumeratorElifGroup(
            code_range,
            enumerators if enumerators else None,
            condition,
        )

    def _is_tree_sitter_preproc_elifdef_enumerator(self) -> bool:
        return self._is_node_type_in(
            "preproc_elifdef_in_enumerator_list",
            "preproc_elifdef_in_enumerator_list_no_comma",
        )

    def _consume_tree_sitter_preproc_if_enumerator(
        self, is_ifdef: bool = False,
    ) -> node.MacroEnumeratorList:
        # For `preproc_if_in_enumerator_list`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1111-L1209
        # For `preproc_if_in_enumerator_list_no_comma`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1543-L1632
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        if_code_start = self._get_current_code_start()
        is_ifndef = False
        if is_ifdef:
            is_ifndef = self._is_node_type(node_type="#ifndef")
            self._cursor.goto_next_sibling()
            if_condition_or_id = self._consume_c_identifier()
        else:
            self._consume_node_with_type(node_type="#if")
            if_condition_or_id = self._consume_preprocess_expression()
        self._consume_new_line()
        if_enumerators = []
        while self._is_tree_sitter_enumerator():
            if_enumerators.append(self._consume_tree_sitter_enumerator())
            if self._is_comma():
                self._consume_comma()
        if_code_end = (
            if_enumerators[-1].code_range.end
            if if_enumerators
            else if_condition_or_id.code_range.end
        )

        if_code_range = CodeRange(self._source_file, if_code_start, if_code_end)
        if is_ifdef:
            assert isinstance(if_condition_or_id, node.Identifier)
            if_group = node.MacroEnumeratorIfdefGroup(
                if_code_range,
                if_enumerators if if_enumerators else None,
                if_condition_or_id,
                is_ifndef,
            )
        else:
            assert isinstance(if_condition_or_id, node.PreprocessExpression)
            if_group = node.MacroEnumeratorIfGroup(
                if_code_range,
                if_enumerators if if_enumerators else None,
                if_condition_or_id,
            )

        elif_groups = []
        while (
            self._is_tree_sitter_preproc_elif_enumerator() or
            self._is_tree_sitter_preproc_elifdef_enumerator()
        ):
            if self._is_tree_sitter_preproc_elifdef_enumerator():
                raise self._create_code_error(
                    "#elifdef and #elifndef is not supported",
                )
            elif_groups.append(
                self._consume_tree_sitter_preproc_elif_enumerator(),
            )

        else_group = None
        if self._is_tree_sitter_preproc_else_enumerator():
            else_group = self._consume_tree_sitter_preproc_else_enumerator()

        self._consume_node_with_type(node_type="#endif")

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroEnumeratorList(
            code_range,
            if_group,
            elif_groups if elif_groups else None,
            else_group,
        )

    # def _consume_tree_sitter_preproc_ifdef_enumerator(
    #     self,
    # ) -> node.MacroEnumeratorList:
    #     raise NotImplementedError()

    def _consume_tree_sitter_preproc_call_enumerator(
        self,
    ) -> node.MacroDirectiveEnumerator:
        directive = self._parse_preprocess_call()
        self._cursor.goto_next_sibling()
        return node.MacroDirectiveEnumerator(directive.code_range, directive)

    def _consume_tree_sitter_enumerator_list(
        self,
    ) -> Sequence[node.EnumeratorBase]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/master/src/grammar.json#L5137-L5245
        assert self._is_tree_sitter_enumerator_list()
        self._cursor.goto_first_child()
        self._consume_left_brace()

        list_ = []
        while not self._is_right_brace():
            if self._is_tree_sitter_enumerator():
                list_.append(self._consume_tree_sitter_enumerator())
            elif (
                self._is_tree_sitter_preproc_if_enumerator() or
                self._is_tree_sitter_preproc_if_enumerator_no_comma()
            ):
                list_.append(self._consume_tree_sitter_preproc_if_enumerator())
            elif (
                self._is_tree_sitter_preproc_ifdef_enumerator() or
                self._is_tree_sitter_preproc_ifdef_enumerator_no_comma()
            ):
                list_.append(
                    self._consume_tree_sitter_preproc_if_enumerator(
                        is_ifdef=True,
                    ),
                )
            elif self._is_preprocess_call():
                list_.append(
                    self._consume_tree_sitter_preproc_call_enumerator(),
                )
            else:
                assert self._is_comma()
                self._consume_comma()

        self._consume_right_brace()
        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return list_

    def _consume_c_enum_specifier(
        self,
    ) -> node.EnumSpecifier:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5049-L5136
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_enum_keyword()

        id_ = None
        if self._is_tree_sitter_type_identifier():
            id_ = self._consume_tree_sitter_type_identifier_as_c_identifier()
            if self._is_colon():
                raise self._create_code_error(
                    "enum of fixed underlying type is not supported",
                )
        enumerator_list = None
        if self._is_tree_sitter_enumerator_list():
            enumerator_list = self._consume_tree_sitter_enumerator_list()

        if id_ is None and enumerator_list is None:
            raise self._create_code_error(
                "missing both enum name and enumerator list",
            )

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.EnumSpecifier(code_range, id_, enumerator_list)

    def _consume_c_type_specifier_qualifier_list(
        self, at_most: int,
    ) -> Sequence[node.TypeSpecifier | node.TypeQualifier]:
        res: Sequence[node.TypeSpecifier | node.TypeQualifier] = []
        count = 0

        while count < at_most:
            if self._is_c_type_specifier():
                res.append(self._consume_c_type_specifier())
                count += 1
            elif self._is_c_type_qualifier():
                res.append(self._consume_c_type_qualifier())
                count +=1
            else:
                break

        return res

    def _consume_c_type_qualifier_list(
        self, at_most: int,
    ) -> Sequence[node.TypeQualifier]:
        res: Sequence[node.TypeQualifier] = []
        count = 0

        while count < at_most and self._is_c_type_qualifier():
            res.append(self._consume_c_type_qualifier())
            count += 1

        return res

    def _is_c_abstract_declarator(self) -> bool:
        return self._is_node_type_in(
            *(t.value for t in TreeSitterAbstractDeclaratorType),
        )

    def _is_c_abstract_pointer_declarator(self) -> bool:
        return self._is_node_type(
            TreeSitterAbstractDeclaratorType.PointerDeclarator.value,
        )

    def _is_star_sign(self) -> bool:
        return self._is_node_type(node_type="*")

    def _is_equal_sign(self) -> bool:
        return self._is_node_type(node_type="=")

    def _consume_equal_sign(self):
        self._consume_node_with_type(node_type="=")

    def _is_static_keyword(self) -> bool:
        return self._is_node_type(node_type="static")

    def _consume_static_keyword(self) -> None:
        self._consume_node_with_type(node_type="static")

    def _consume_enum_keyword(self) -> None:
        self._consume_node_with_type(node_type="enum")

    def _consume_c_pointer_token(self) -> None:
        return self._consume_node_with_type(node_type="*")

    def _is_tree_sitter_ms_based_modifier(self) -> bool:
        return self._is_node_type(node_type="ms_based_modifier")

    def _is_tree_sitter_ms_pointer_modifier(self) -> bool:
        return self._is_node_type(node_type="ms_pointer_modifier")

    def _is_tree_sitter_ms_call_modifier(self) -> bool:
        return self._is_node_type(node_type="ms_call_modifier")

    def _consume_c_abstract_pointer_declarator(
        self,
    ) -> node.AbstractPointerDeclarator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4007-L4053
        code_range = self._get_current_code_range()
        child_count = self._get_child_count()
        self._cursor.goto_first_child()

        self._consume_c_pointer_token()
        if self._is_tree_sitter_ms_pointer_modifier():
            raise self._create_code_error(
                err_msg="MSCV point modifier is not supported",
            )
        qualifiers = self._consume_c_type_qualifier_list(child_count - 1)
        declarator = self._try_consume_c_abstract_declarator()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.AbstractPointerDeclarator(
            code_range,
            qualifiers if qualifiers else None,
            declarator,
        )

    def _is_c_abstract_function_declarator(self) -> bool:
        return self._is_node_type(
            TreeSitterAbstractDeclaratorType.FunctionDeclarator.value,
        )

    def _is_c_parameter_type_list(self) -> bool:
        return self._is_node_type(node_type="parameter_list")

    def _is_c_parameter_declaration(self) -> bool:
        return self._is_node_type(node_type="parameter_declaration")

    def _is_c_attribute(self) -> bool:
        return self._is_node_type(node_type="attribute_specifier")

    def _is_c_expression(self) -> bool:
        raise NotImplementedError()

    def _consume_c_expression(self) -> node.ExpressionBase:
        raise NotImplementedError()

    def _is_c_argument_list(self) -> bool:
        return self._is_node_type(node_type="argument_list")

    def _consume_c_argument_list(
        self
    ) -> Sequence[node.ExpressionBase]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8468C6-L8531
        self._assert_current_node_type(node_type="argument_list")
        self._cursor.goto_first_child()

        list_ = []
        self._consume_left_parenthesis()
        if not self._is_right_parenthesis():
            list_.append(self._consume_c_expression())
        while not self._is_right_parenthesis():
            self._consume_comma()
            list_.append(self._consume_c_expression())
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return list_

    def _consume_c_attribute(self) -> node.Attribute:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3193-L3222
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="__attribute__")
        self._consume_left_parenthesis()
        arguments = self._consume_c_argument_list()
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.Attribute(code_range, arguments)

    def _try_consume_c_attribute_list(
        self, at_most: int,
    ) -> Optional[Sequence[node.Attribute]]:
        list_ = []
        count = 0

        while count < at_most and self._is_c_attribute():
            list_.append(self._consume_c_attribute())
            count += 1

        return list_ if list_ else None

    def _consume_c_parameter_declaration(self) -> node.ParameterDeclaration:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5771-L5811
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()
        sibling_count = self._get_sibling_count()

        specifiers = self._consume_c_declaration_specifiers(sibling_count)
        if self._is_c_declaration():
            declarator = self._consume_tree_sitter_declarator()
        elif self._is_c_abstract_declarator():
            declarator = self._consume_c_abstract_declarator()
        else:
            declarator = None
        attributes = self._try_consume_c_attribute_list(
            sibling_count - len(specifiers) - 1 if declarator else 0,
        )

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.ParameterDeclaration(
            code_range, specifiers, declarator, attributes,
        )

    def _consume_c_parameter_type_list(
        self,
    ) -> Tuple[Sequence[node.ParameterDeclaration], bool]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L5634-L5706
        self._assert_current_node_type(node_type="parameter_list")
        self._cursor.goto_first_child()

        list_ = []
        variadic = False
        self._consume_left_parenthesis()

        if not self._is_right_parenthesis():
            list_.append(self._consume_c_parameter_declaration())
        while not self._is_right_parenthesis():
            self._consume_comma()
            if self._is_c_parameter_declaration():
                list_.append(self._consume_c_parameter_declaration())
            else:
                self._consume_node_with_type(node_type="variadic_parameter")
                variadic = True
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return list_, variadic

    def _consume_c_abstract_function_declarator(
        self,
    ) -> node.AbstractFunctionDeclarator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4210-L4242
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        declarator = self._try_consume_c_abstract_declarator()
        parameter_type_list, variadic = self._consume_c_parameter_type_list()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.AbstractFunctionDeclarator(
            code_range, declarator, parameter_type_list, variadic,
        )

    def _is_c_abstract_array_declarator(self) -> bool:
        return self._is_node_type(
            TreeSitterAbstractDeclaratorType.ArrayDeclarator.value,
        )

    def _consume_c_abstract_array_declarator(
        self,
    ) -> node.AbstractArrayDeclarator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4467-L4540
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()
        sibling_count = self._get_sibling_count()

        declarator = self._try_consume_c_abstract_declarator()
        array_size_start = self._get_current_code_start()
        self._consume_left_bracket()

        expression = None
        qualifiers = None
        size_kind: node.ArraySizeKind
        if self._is_star_sign():
            size_kind = node.ArraySizeKind.VariableUnknown
        elif self._is_static_keyword():
            size_kind = node.ArraySizeKind.StaticExpression
            self._consume_static_keyword()
            if self._is_c_type_qualifier():
                qualifiers = self._consume_c_type_qualifier_list(sibling_count)
            expression = self._consume_c_expression()
        elif self._is_c_type_qualifier():
            qualifiers = self._consume_c_type_qualifier_list(sibling_count)
            if self._is_static_keyword():
                size_kind = node.ArraySizeKind.StaticExpression
                self._consume_static_keyword()
                expression = self._consume_c_expression()
            elif self._is_c_expression():
                size_kind = node.ArraySizeKind.VariableExpression
                expression = self._consume_c_expression()
            else:
                size_kind = node.ArraySizeKind.Unknown
                assert self._is_right_bracket()
        elif self._is_c_expression():
            size_kind = node.ArraySizeKind.VariableExpression
            expression = self._consume_c_expression()
        else:
            size_kind = node.ArraySizeKind.Unknown
            assert self._is_right_bracket()

        array_size_end = self._get_current_code_end()
        self._consume_right_bracket()
        array_size = node.ArraySize(
            CodeRange(self._source_file, array_size_start, array_size_end),
            size_kind, qualifiers, expression,
        )

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.AbstractArrayDeclarator(code_range, declarator, array_size)

    def _is_c_abstract_parenthesized_declarator(self) -> bool:
        return self._is_node_type(
            TreeSitterAbstractDeclaratorType.ParenthesizedDeclarator.value,
        )

    def _consume_c_abstract_parenthesized_declarator(self):
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3761-L3793
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_parenthesis()
        if self._is_tree_sitter_ms_call_modifier():
            raise self._create_code_error("MSVC call modifier is not supported")
        declarator = self._consume_c_abstract_declarator()
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.AbstractParenthesizedDeclarator(code_range, declarator)

    def _consume_c_abstract_declarator(self) -> node.AbstractDeclaratorBase:
        if self._is_c_abstract_pointer_declarator():
            return self._consume_c_abstract_pointer_declarator()
        elif self._is_c_abstract_function_declarator():
            return self._consume_c_abstract_function_declarator()
        elif self._is_c_abstract_array_declarator():
            return self._consume_c_abstract_array_declarator()
        elif self._is_c_abstract_parenthesized_declarator():
            return self._consume_c_abstract_parenthesized_declarator()
        else:
            raise self._create_code_error("not a C abstract declarator")

    def _try_consume_c_abstract_declarator(
        self,
    ) -> Optional[node.AbstractDeclaratorBase]:
        if not self._is_c_abstract_declarator():
            return None
        return self._consume_c_abstract_declarator()

    def _consume_c_type_name(self) -> node.TypeName:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L7661-L7703
        code_range = self._get_current_code_range()
        child_count = self._get_child_count()
        self._cursor.goto_first_child()

        list_ = self._consume_c_type_specifier_qualifier_list(child_count)
        declarator = self._try_consume_c_abstract_declarator()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.TypeName(code_range, list_, declarator)

    def _consume_tree_sitter_macro_type_specifier(
        self
    ) -> node.MacroTypeSpecifier:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L9565-L9597
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        identifier = self._consume_c_identifier()
        self._consume_left_parenthesis()
        type_name = self._consume_c_type_name()
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MacroTypeSpecifier(code_range, identifier, type_name)

    def _is_tree_sitter_sized_type_item(self) -> bool:
        return self._is_node_type_in(
            node.PrimitiveTypeSpecifierKind.Signed.value,
            node.PrimitiveTypeSpecifierKind.Unsigned.value,
            node.PrimitiveTypeSpecifierKind.Long.value,
            node.PrimitiveTypeSpecifierKind.Short.value,
        )

    def _consume_tree_sitter_size_type_item(
        self,
    ) -> node.PrimitiveTypeSpecifier:
        assert self._cursor.node is not None
        code_range = self._get_current_code_range()

        kind = node.PrimitiveTypeSpecifierKind(self._cursor.node.type)

        self._cursor.goto_next_sibling()
        return node.PrimitiveTypeSpecifier(code_range, kind)

    def _consume_tree_sitter_sized_type_specifier(
        self,
    ) -> Sequence[node.TypeSpecifier | node.TypeQualifier]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4761-L4936
        count = self._get_child_count()
        specifiers: List[node.TypeSpecifier | node.TypeQualifier] = []
        index = 0
        self._cursor.goto_first_child()

        while index < count and self._is_tree_sitter_sized_type_item():
            specifiers.append(self._consume_tree_sitter_size_type_item())
            index += 1

        while index < count and self._is_c_type_qualifier():
            specifiers.append(self._consume_c_type_qualifier())
            index += 1

        if self._is_tree_sitter_type_identifier():
            specifiers.append(self._consume_c_typedef_name())
            index += 1
        elif self._is_c_primitive_type_specifier():
            specifiers.append(self._consume_c_primitive_type_specifier())
            index += 1

        while index < count and self._is_tree_sitter_sized_type_item():
            specifiers.append(self._consume_tree_sitter_size_type_item())
            index += 1

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return specifiers

    def _consume_c_primitive_type_specifier(
        self,
    ) -> node.TypeSpecifier:
        assert self._is_c_primitive_type_specifier()
        code_range = self._get_current_code_range()
        type_ = self._consume_raw_content()

        if type_ == TreeSitterCPrimitivType.Char:
            return node.PrimitiveTypeSpecifier(
                code_range,
                node.PrimitiveTypeSpecifierKind.Char,
            )
        elif type_ == TreeSitterCPrimitivType.Int:
            return node.PrimitiveTypeSpecifier(
                code_range,
                node.PrimitiveTypeSpecifierKind.Int,
            )
        elif type_ == TreeSitterCPrimitivType.Float:
            return node.PrimitiveTypeSpecifier(
                code_range,
                node.PrimitiveTypeSpecifierKind.Float,
            )
        elif type_ == TreeSitterCPrimitivType.Double:
            return node.PrimitiveTypeSpecifier(
                code_range,
                node.PrimitiveTypeSpecifierKind.Double,
            )
        elif type_ == TreeSitterCPrimitivType.Void:
            return node.PrimitiveTypeSpecifier(
                code_range,
                node.PrimitiveTypeSpecifierKind.Void,
            )
        else:
            return node.TypedefName(code_range, type_)

    def _consume_c_identifier(self) -> node.Identifier:
        code_range = self._get_current_code_range()
        name = self._consume_tree_sitter_identifier()
        return node.Identifier(code_range, name)

    def _consume_c_identifier_expression(self) -> node.IdentifierExpression:
        code_range = self._get_current_code_range()
        identifier = self._consume_c_identifier()
        return node.IdentifierExpression(code_range, identifier)

    def _consume_c_typedef_name(self) -> node.TypedefName:
        assert self._is_tree_sitter_type_identifier()
        code_range = self._get_current_code_range()
        identifier = self._consume_raw_content()
        return node.TypedefName(code_range, identifier)


    def _consume_c_type_specifier(self) -> node.TypeSpecifier:
        if self._is_c_struct_or_union_specifier():
            return self._consume_c_struct_or_union_specifier()
        elif self._is_c_enum_specifier():
            return self._consume_c_enum_specifier()
        elif self._is_tree_sitter_macro_type_specifier():
            return self._consume_tree_sitter_macro_type_specifier()
        # elif self._is_tree_sitter_sized_type_specifier():
        #     return self._consume_tree_sitter_sized_type_specifier()
        elif self._is_c_primitive_type_specifier():
            return self._consume_c_primitive_type_specifier()
        elif self._is_tree_sitter_type_identifier():
            return self._consume_c_typedef_name()
        else:
            unreachable()

    def _is_c_function_specifier(self) -> bool:
        res = False
        if self._is_node_type_in(
            TreeSitterCDeclarationModifierType.StorageClassSpecifier.value,
            TreeSitterCDeclarationModifierType.TypeQualifier.value,
        ):
            self._cursor.goto_first_child()
            res = self._is_node_type_in(
                TreeSitterCStorageClassSpecifier.Inline.value,
                TreeSitterCStorageClassSpecifier.MSVCInline.value,
                TreeSitterCStorageClassSpecifier.GCCInline.value,
                TreeSitterCTypeQualifierType.Noreturn.value,
            )
            self._cursor.goto_parent()
        return res

    def _consume_c_function_specifier(self) -> node.FunctionSpecifier:
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        if self._is_node_type_in(
            TreeSitterCStorageClassSpecifier.Inline.value,
            TreeSitterCStorageClassSpecifier.MSVCInline.value,
            TreeSitterCStorageClassSpecifier.GCCInline.value,
        ):
            kind = node.FunctionSpecifierKind.Inline
        else:
            self._assert_current_node_type(
                TreeSitterCTypeQualifierType.Noreturn.value,
            )
            kind = node.FunctionSpecifierKind.Noreturn

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.FunctionSpecifier(code_range, kind)

    def _is_c_alignment_specifier(self) -> bool:
        return self._is_node_type(
            TreeSitterCDeclarationModifierType.AlignasQualifier.value,
        )

    def _consume_c_alignment_specifier(self) -> node.AlignmentSpecifierBase:
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._assert_current_node_type_in("alignas", "_Alignas")
        self._consume_left_parenthesis()
        if self._is_c_expression():
            align_specifier = node.AlignmentConstExpressionSpecifier(
                code_range, self._consume_c_expression(),
            )
        else:
            align_specifier = node.AlignmentTypeSpecifier(
                code_range, self._consume_c_type_name(),
            )
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return align_specifier

    def _is_c_declaration_specifier(self) -> bool:
        return (
            self._is_c_storage_class_specifier() or
            self._is_c_type_specifier() or
            self._is_c_type_qualifier() or
            self._is_c_function_specifier() or
            self._is_c_alignment_specifier()
        )

    def _consume_c_declaration_specifier(self) -> node.DeclarationSpecifierBase:
        if self._is_c_storage_class_specifier():
            return self._consume_c_storage_class_specifier()
        elif self._is_c_type_specifier():
            return self._consume_c_type_specifier()
        elif self._is_c_type_qualifier():
            return self._consume_c_type_qualifier()
        elif self._is_c_function_specifier():
            return self._consume_c_function_specifier()
        elif self._is_c_alignment_specifier():
            return self._consume_c_alignment_specifier()
        else:
            unreachable()

    def _consume_c_declaration_specifiers(
        self, at_most: int,
    ) -> Sequence[node.DeclarationSpecifierBase]:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3124-L3154
        specifiers = []
        count = 0

        while count < at_most and self._is_c_declaration_specifier():
            if self._is_tree_sitter_sized_type_specifier():
                specs = self._consume_tree_sitter_sized_type_specifier()
                specifiers.extend(specs)
                count += len(specs)
            else:
                specifiers.append(self._consume_c_declaration_specifier())
                count += 1

        return specifiers

    def _is_tree_sitter_init_declarator(self) -> bool:
        return self._is_node_type(node_type="init_declarator")

    def _is_tree_sitter_attributed_declarator(self) -> bool:
        return self._is_node_type(node_type="attributed_declarator")

    def _is_tree_sitter_pointer_declarator(self) -> bool:
        return self._is_node_type(node_type="pointer_declarator")

    def _is_tree_sitter_function_declarator(self) -> bool:
        return self._is_node_type(node_type="function_declarator")

    def _is_tree_sitter_array_declarator(self) -> bool:
        return self._is_node_type(node_type="array_declarator")

    def _is_tree_sitter_parenthesized_declarator(self) -> bool:
        return self._is_node_type(node_type="parenthesized_declarator")

    def _is_tree_sitter_declarator(self) -> bool:
        return (
            self._is_tree_sitter_init_declarator() or
            self._is_tree_sitter_attributed_declarator() or
            self._is_tree_sitter_pointer_declarator() or
            self._is_tree_sitter_function_declarator() or
            self._is_tree_sitter_array_declarator() or
            self._is_tree_sitter_parenthesized_declarator() or
            self._is_identifier()
        )

    def _consume_identifier_as_declarator(self) -> node.IdentifierDeclarator:
        identifier = self._consume_c_identifier()
        return node.IdentifierDeclarator(identifier.code_range, identifier)

    def _is_tree_sitter_initializer_list(self) -> bool:
        return self._is_node_type(node_type="initializer_list")

    def _is_tree_sitter_initializer_pair(self) -> bool:
        return self._is_node_type(node_type="initializer_pair")

    def _consume_tree_sitter_initializer_list(self) -> node.InitializerList:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8638-L8721
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_brace()
        items: List[node.InitializerListItem] = []
        while not self._is_right_brace():
            if self._is_c_expression():
                items.append(self._consume_c_expression_as_initializer_item())
            elif self._is_tree_sitter_initializer_list():
                items.append(self._consume_init_list_as_initializer_item())
            elif self._is_tree_sitter_initializer_pair():
                items.append(self._consume_init_pair_as_initializer_item())
            else:
                assert self._is_comma()
                self._consume_comma()
        self._consume_right_brace()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.InitializerList(code_range, items)

    def _is_tree_sitter_subscript_designator(self) -> bool:
        return self._is_node_type(node_type="subscript_designator")

    def _consume_tree_sitter_subscript_designator(self) -> node.IndexDesignator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8811-L8827
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_bracket()
        exp = self._consume_c_expression()
        self._consume_right_bracket()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.IndexDesignator(code_range, exp)

    def _is_tree_sitter_field_designator(self) -> bool:
        return self._is_node_type(node_type="field_designator")

    def _consume_tree_sitter_field_identifier(self) -> node.Identifier:
        self._assert_current_node_type(node_type="field_identifier")
        code_range = self._get_current_code_range()

        field = self._consume_raw_content()
        self._cursor.goto_next_sibling()
        return node.Identifier(code_range, field)

    def _consume_tree_sitter_field_designator(self) -> node.MemberDesignator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8861-L8873
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type=".")
        member = self._consume_tree_sitter_field_identifier()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.MemberDesignator(code_range, member)

    def _is_tree_sitter_subscript_range_designator(self) -> bool:
        return self._is_node_type(node_type="subscript_range_designator")

    def _consume_tree_sitter_subscript_range_designator(
        self,
    ) -> node.RangeDesignator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8828-L8860
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_bracket()
        start = self._consume_c_expression()
        self._consume_node_with_type(node_type="...")
        end = self._consume_c_expression()
        self._consume_right_bracket()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.RangeDesignator(code_range, start, end)

    def _consume_init_pair_as_initializer_item(
        self,
    ) -> node.InitializerListItem:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L8722-L8810
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        designators: List[node.DesignatorBase] = []
        while not self._is_equal_sign():
            if self._is_tree_sitter_subscript_designator():
                designators.append(
                    self._consume_tree_sitter_subscript_designator(),
                )
            elif self._is_tree_sitter_field_designator():
                designators.append(self._consume_tree_sitter_field_designator())
            elif self._is_tree_sitter_subscript_range_designator():
                designators.append(
                    self._consume_tree_sitter_subscript_range_designator(),
                )
            else:
                raise self._create_code_error(
                    "unsupported initialization designator",
                )

        if self._is_c_expression():
            init = self._consume_c_expression_as_initializer()
        elif self._is_tree_sitter_initializer_list():
            init = self._consume_tree_sitter_initializer_list()
        else:
            unreachable()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.InitializerListItem(code_range, designators, init)

    def _consume_init_list_as_initializer_item(
        self,
    ) -> node.InitializerListItem:
        init = self._consume_tree_sitter_initializer_list()
        return node.InitializerListItem(
            init.code_range, None, init,
        )

    def _consume_c_expression_as_initializer_item(
        self,
    ) -> node.InitializerListItem:
        init = self._consume_c_expression_as_initializer()
        return node.InitializerListItem(
            init.code_range, None, init,
        )

    def _consume_c_expression_as_initializer(
        self,
    ) -> node.ExpressionInitializer:
        expression = self._consume_c_expression()
        return node.ExpressionInitializer(expression.code_range, expression)

    def _consume_tree_sitter_init_declarator(self) -> node.InitDeclarator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4541-L4574
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        declarator = self._consume_tree_sitter_declarator()
        self._consume_equal_sign()
        if self._is_c_expression():
            init = self._consume_c_expression_as_initializer()
        else:
            init = self._consume_tree_sitter_initializer_list()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.InitDeclarator(code_range, declarator, init)

    def _consume_tree_sitter_attributed_declarator(self) -> node.DeclaratorBase:
        raise self._create_code_error(
            "declarator with attribute is not supported",
        )

    def _consume_tree_sitter_pointer_declarator(self) -> node.PointerDeclarator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L3854-L3904
        code_range = self._get_current_code_range()
        child_count = self._get_child_count()
        self._cursor.goto_first_child()

        if self._is_tree_sitter_ms_based_modifier():
            raise self._create_code_error(
                err_msg="MSCV based modifier is not supported",
            )
        self._consume_c_pointer_token()
        if self._is_tree_sitter_ms_pointer_modifier():
            raise self._create_code_error(
                err_msg="MSCV point modifier is not supported",
            )
        qualifiers = self._consume_c_type_qualifier_list(child_count - 1)
        declarator = self._consume_tree_sitter_declarator()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.PointerDeclarator(
            code_range,
            qualifiers if qualifiers else None,
            declarator,
        )

    def _consume_tree_sitter_function_declarator(
        self,
    ) -> node.FunctionDeclarator:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4054-L4115
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        declarator = self._consume_tree_sitter_declarator()
        parameter_type_list, variadic = self._consume_c_parameter_type_list()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.FunctionDeclarator(
            code_range, declarator, parameter_type_list, variadic,
        )

    def _consume_tree_sitter_array_declarator(self) -> node.ArrayDeclarator:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L4269-L4334
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()
        sibling_count = self._get_sibling_count()

        declarator = self._consume_tree_sitter_declarator()
        array_size_start = self._get_current_code_start()
        self._consume_left_bracket()

        expression = None
        qualifiers = None
        size_kind: node.ArraySizeKind
        if self._is_star_sign():
            size_kind = node.ArraySizeKind.VariableUnknown
        elif self._is_static_keyword():
            size_kind = node.ArraySizeKind.StaticExpression
            self._consume_static_keyword()
            if self._is_c_type_qualifier():
                qualifiers = self._consume_c_type_qualifier_list(sibling_count)
            expression = self._consume_c_expression()
        elif self._is_c_type_qualifier():
            qualifiers = self._consume_c_type_qualifier_list(sibling_count)
            if self._is_static_keyword():
                size_kind = node.ArraySizeKind.StaticExpression
                self._consume_static_keyword()
                expression = self._consume_c_expression()
            elif self._is_c_expression():
                size_kind = node.ArraySizeKind.VariableExpression
                expression = self._consume_c_expression()
            else:
                size_kind = node.ArraySizeKind.Unknown
                assert self._is_right_bracket()
        elif self._is_c_expression():
            size_kind = node.ArraySizeKind.VariableExpression
            expression = self._consume_c_expression()
        else:
            size_kind = node.ArraySizeKind.Unknown
            assert self._is_right_bracket()

        array_size_end = self._get_current_code_end()
        self._consume_right_bracket()
        array_size = node.ArraySize(
            CodeRange(self._source_file, array_size_start, array_size_end),
            size_kind, qualifiers, expression,
        )

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.ArrayDeclarator(code_range, declarator, array_size)

    def _consume_tree_sitter_parenthesized_declarator(
        self,
    ) -> node.ParenthesizedDeclarator:
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_parenthesis()
        if self._is_tree_sitter_ms_call_modifier():
            raise self._create_code_error("MSVC call modifier is not supported")
        declarator = self._consume_tree_sitter_declarator()
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.ParenthesizedDeclarator(code_range, declarator)

    def _consume_tree_sitter_declarator(self) -> node.DeclaratorBase:
        if self._is_identifier():
            return self._consume_identifier_as_declarator()
        elif self._is_tree_sitter_init_declarator():
            return self._consume_tree_sitter_init_declarator()
        elif self._is_tree_sitter_attributed_declarator():
            return self._consume_tree_sitter_attributed_declarator()
        elif self._is_tree_sitter_pointer_declarator():
            return self._consume_tree_sitter_pointer_declarator()
        elif self._is_tree_sitter_array_declarator():
            return self._consume_tree_sitter_array_declarator()
        elif self._is_tree_sitter_parenthesized_declarator():
            return self._consume_tree_sitter_parenthesized_declarator()
        else:
            raise self._create_code_error("unsupported declarator")

    def _parse_c_declaration(self) -> node.Declaration:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L2877-L2998
        assert self._is_c_declaration()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()
        sibling_count = self._get_sibling_count()

        decl_specifiers = self._consume_c_declaration_specifiers(sibling_count)
        declarators = []
        while self._is_tree_sitter_declarator():
            declarators.append(self._consume_tree_sitter_declarator())
        self._consume_semicolon()

        self._cursor.goto_parent()
        return node.Declaration(
            code_range, decl_specifiers, declarators if declarators else None,
        )

    def _is_top_level_preprocess_directive(self) -> bool:
        if self._cursor.node is None:
            return False

        for type_ in TreeSitterTopLevelPreprocessType:
            if self._cursor.node.type == type_.value:
                return True

        return False

    def _parse_top_level_preprocess_directive(self) -> node.PreprocessNode:
        assert self._is_top_level_preprocess_directive()

        if self._is_preprocess_include():
            return self._parse_preprocess_include()
        elif self._is_preprocess_call():
            return self._parse_preprocess_call()
        elif self._is_preprocess_if_section():
            return self._parse_preprocess_if_section()
        elif self._is_preprocess_define():
            return self._parse_preprocess_define()
        elif self._is_preprocess_function_define():
            return self._parse_preprocess_function_define()
        else:
            unreachable()

    def _consume_node_with_type(self, node_type: str) -> None:
        if not self._is_node_type(node_type):
            raise self._create_code_error(
                f"expect node with type {node_type}",
            )
        self._cursor.goto_next_sibling()

    def _is_comma(self) -> bool:
        return self._is_node_type(node_type=",")

    def _consume_comma(self) -> None:
        self._consume_node_with_type(node_type=",")

    def _consume_raw_content(self) -> str:
        raw_content = TreeSitterHelper.parse_raw_content(self._cursor)
        if raw_content is None:
            raise self._create_code_error("empty code region")

        self._cursor.goto_next_sibling()
        return raw_content

    def _parse_raw_content(self) -> Optional[str]:
        return TreeSitterHelper.parse_raw_content(self._cursor)

    def _is_identifier(self) -> bool:
        return self._is_node_type(node_type="identifier")

    def _consume_tree_sitter_identifier(self) -> str:
        if not self._is_identifier():
            raise self._create_code_error("not an identifier node")

        identifier = TreeSitterHelper.parse_raw_content(self._cursor)
        if identifier is None:
            raise self._create_code_error("an empty identifier")

        self._cursor.goto_next_sibling()
        return identifier

    def _get_current_node_type(self) -> str:
        assert self._cursor.node is not None
        return self._cursor.node.type

    def _is_preprocess_include(self) -> bool:
        return self._is_node_type(
            TreeSitterTopLevelPreprocessType.Include.value,
        )

    def _parse_preprocess_include(self) -> node.IncludeDirective:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L145-L186
        assert self._is_preprocess_include()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#include")
        self._assert_current_node_type_in(
            *(t.value for t in node.IncludeTargetType),
        )
        code_range = self._get_current_code_range()
        target_type = node.IncludeTargetType(self._get_current_node_type())
        include_directive: node.IncludeDirective
        if target_type == node.IncludeTargetType.CallExpression:
            include_directive = node.IncludeDirective(
                code_range, target_type,
                self._consume_preprocess_call_expression(),
            )
        else:
            include_directive = node.IncludeDirective(
                code_range, target_type, self._consume_raw_content(),
            )

        self._cursor.goto_parent()
        return include_directive

    def _assert_current_node_type(self, node_type:str) -> None:
        assert self._is_node_type(node_type)

    def _assert_current_node_type_in(self, *node_types: str) -> None:
        assert TreeSitterHelper.is_node_type_in(self._cursor, *node_types)

    def _consume_preprocess_call_expression(
        self,
    ) -> node.PreprocessCallExpression:
        assert self._is_preprocess_call_expression()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        callee = self._consume_tree_sitter_identifier()
        arguments = self._consume_preprocess_argument_list()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.PreprocessCallExpression(code_range, callee, arguments)

    def _is_node_type(self, node_type: str) -> bool:
        return TreeSitterHelper.is_node_type(self._cursor, node_type)

    def _is_node_type_in(self, *node_types: str) -> bool:
        return TreeSitterHelper.is_node_type_in(self._cursor, *node_types)

    def _is_left_parenthesis(self) -> bool:
        return self._is_node_type(node_type="(")

    def _is_right_parenthesis(self) -> bool:
        return self._is_node_type(node_type=")")

    def _is_end_of_params(self) -> bool:
        return self._is_right_parenthesis()

    def _is_end_of_argument_list(self) -> bool:
        return self._is_right_parenthesis()

    def _consume_left_parenthesis(self) -> None:
        self._consume_node_with_type(node_type="(")

    def _consume_right_parenthesis(self) -> None:
        self._consume_node_with_type(node_type=")")

    def _consume_left_bracket(self) -> None:
        self._consume_node_with_type(node_type="[")

    def _consume_right_bracket(self) -> None:
        self._consume_node_with_type(node_type="]")

    def _is_colon(self) -> bool:
        return self._is_node_type(node_type=":")

    def _consume_colon(self) -> None:
        self._consume_node_with_type(node_type=":")

    def _is_semicolon(self) -> bool:
        return self._is_node_type(node_type=";")

    def _consume_semicolon(self) -> None:
        self._consume_node_with_type(node_type=";")

    def _is_left_bracket(self) -> bool:
        return self._is_node_type(node_type="[")

    def _is_right_bracket(self) -> bool:
        return self._is_node_type(node_type="]")

    def _is_left_brace(self) -> bool:
        return self._is_node_type(node_type="{")

    def _is_right_brace(self) -> bool:
        return self._is_node_type(node_type="}")

    def _consume_left_brace(self) -> None:
        self._consume_node_with_type(node_type="{")

    def _consume_right_brace(self) -> None:
        self._consume_node_with_type(node_type="}")

    def _is_new_line(self) -> bool:
        return self._is_node_type(node_type="\n")

    def _consume_new_line(self) -> None:
        self._consume_node_with_type(node_type="\n")

    def _consume_preprocess_argument_list(
        self,
    ) -> Sequence[node.PreprocessExpression]:
        self._assert_current_node_type(node_type="argument_list")
        self._cursor.goto_first_child()

        arguments: List[node.PreprocessExpression] = []
        if not self._is_end_of_argument_list():
            arguments.append(self._consume_preprocess_expression())
        while not self._is_end_of_argument_list():
            self._consume_comma()
            arguments.append(self._consume_preprocess_expression())

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return arguments

    def _is_preprocess_primitive_expression(self) -> bool:
        return self._is_node_type_in(
            *(t.value for t in node.PreprocessPrimitiveType),
        )

    def _is_preprocess_call_expression(self) -> bool:
        return self._is_node_type(node_type="preproc_call_expression")

    def _consume_preprocess_expression(self) -> node.PreprocessExpression:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L1945-L2001
        if self._is_preprocess_primitive_expression():
            return self._consume_preprocess_primitive()
        elif self._is_preprocess_call_expression():
            return self._consume_preprocess_call_expression()
        elif self._is_preprocess_defined_call():
            return self._consume_preprocess_defined()
        elif self._is_preprocess_unary_expression():
            return self._consume_preprocess_unary_expression()
        elif self._is_preprocess_binary_expression():
            return self._consume_preprocess_binary_expression()
        elif self._is_preprocess_parenthesized_expression():
            return self._consume_preprocess_parenthesized_expression()
        else:
            unreachable()

    def _consume_preprocess_primitive(self) -> node.PreprocessPrimitive:
        assert self._is_preprocess_primitive_expression()
        code_range = self._get_current_code_range()

        if self._is_identifier():
            identifier = self._consume_tree_sitter_identifier()
            return node.PreprocessPrimitive(
                code_range, node.PreprocessPrimitiveType.Identifier,
                identifier,
            )
        elif self._is_node_type(
            node.PreprocessPrimitiveType.NumberLiteral.value,
        ):
            num_literal = self._consume_raw_content()
            return node.PreprocessPrimitive(
                code_range, node.PreprocessPrimitiveType.NumberLiteral,
                num_literal,
            )
        else:
            char_literal = self._consume_raw_content()
            return node.PreprocessPrimitive(
                code_range, node.PreprocessPrimitiveType.NumberLiteral,
                char_literal,
            )

    def _is_preprocess_defined_call(self) -> bool:
        return self._is_node_type(node_type="preproc_defined")

    def _consume_preprocess_defined(self) -> node.PreprocessDefined:
        # For example, `#if defined (__vax__) || defined (__ns16000__)`
        # See https://gcc.gnu.org/onlinedocs/cpp/Defined.html
        assert self._is_preprocess_defined_call()

        start = self._get_current_code_start()
        end: CodeLocation
        identifier: str
        self._consume_node_with_type(node_type="#defined")
        if self._is_left_parenthesis():
            self._consume_left_parenthesis()
            identifier = self._consume_tree_sitter_identifier()
            end = self._get_current_code_end()
            self._consume_right_parenthesis()
        else:
            end = self._get_current_code_end()
            identifier = self._consume_tree_sitter_identifier()
        return node.PreprocessDefined(
            CodeRange(self._source_file, start, end), identifier,
        )

    def _is_preprocess_unary_expression(self) -> bool:
        return self._is_node_type(node_type="preproc_unary_expression")

    def _consume_preprocess_unary_operator(
        self,
    ) -> node.PreprocessUnaryOperator:
        self._assert_current_node_type_in(
            *(op.value for op in node.PreprocessUnaryOperator),
        )

        assert self._cursor.node is not None
        op = node.PreprocessUnaryOperator(self._cursor.node.type)

        self._cursor.goto_next_sibling()
        return op

    def _consume_preprocess_unary_expression(
        self,
    ) -> node.PreprocessUnaryExpression:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L2062-L2103
        assert self._is_preprocess_unary_expression()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        operator = self._consume_preprocess_unary_operator()
        operand = self._consume_preprocess_expression()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.PreprocessUnaryExpression(code_range, operator, operand)

    def _is_preprocess_binary_expression(self) -> bool:
        return self._is_node_type(node_type="preproc_binary_expression")

    def _consume_preprocess_binary_operator(
        self,
    ) -> node.PreprocessBinaryOperator:
        self._assert_current_node_type_in(
            *(op.value for op in node.PreprocessBinaryOperator),
        )

        assert self._cursor.node is not None
        op = node.PreprocessBinaryOperator(self._cursor.node.type)

        self._cursor.goto_next_sibling()
        return op

    def _consume_preprocess_binary_expression(
        self,
    ) -> node.PreprocessBinaryExpression:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L2180-L2778
        assert self._is_preprocess_binary_expression()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        lhs = self._consume_preprocess_expression()
        operator = self._consume_preprocess_binary_operator()
        rhs = self._consume_preprocess_expression()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.PreprocessBinaryExpression(code_range, operator, lhs, rhs)

    def _is_preprocess_parenthesized_expression(self) -> bool:
        return self._is_node_type(node_type="preproc_parenthesized_expression")

    def _consume_preprocess_parenthesized_expression(
        self
    ) -> node.ParenthesizedPreprocessExpression:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L2002-L2018
        assert self._is_preprocess_parenthesized_expression()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_left_parenthesis()
        exp = self._consume_preprocess_expression()
        self._consume_right_parenthesis()

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.ParenthesizedPreprocessExpression(code_range, exp)

    def _is_preprocess_call(self) -> bool:
        return self._is_node_type(TreeSitterTopLevelPreprocessType.Call.value)

    def _is_preprocess_directive(self) -> bool:
        return self._is_node_type(node_type="preproc_directive")

    @staticmethod
    def _is_preprocess_directive_eq(directive: str, target: str) -> bool:
        if directive[0] != "#":
            return False
        start = 1
        while directive[start] in (" ", "\t"):
            start += 1
        return directive[start:] == target

    def _try_consume_preprocess_arg(self) -> Optional[str]:
        if self._is_node_type(node_type="preproc_arg"):
            return self._consume_raw_content()
        else:
            return None

    def _parse_preprocess_call(self) -> node.PreprocessNode:
        assert self._is_preprocess_call()
        self._cursor.goto_first_child()

        start = self._get_current_code_start()
        assert self._is_preprocess_directive()
        directive = self._consume_raw_content()
        directive_arg = self._try_consume_preprocess_arg()
        end = self._get_current_code_end()
        code_range = CodeRange(self._source_file, start, end)
        res: node.PreprocessNode
        if self._is_preprocess_directive_eq(directive, target="undef"):
            # For `#undef` directives
            assert directive_arg is not None
            res = node.UndefineDirective(code_range, directive_arg)
        elif self._is_preprocess_directive_eq(directive, target="error"):
            res = node.ErrorDirective(code_range, directive_arg)
        elif self._is_preprocess_directive_eq(directive, target="pragma"):
            res = node.PragmaDirective(code_range, directive_arg)
        elif self._is_preprocess_directive_eq(directive, target="line"):
            assert directive_arg is not None
            res = node.LineDirective(code_range, directive_arg)
        else:
            raise self._create_code_error(
                f"unsupoorted preprocessing directive #{directive}",
            )

        self._cursor.goto_parent()
        return res

    def _is_preprocess_if_section(self) -> bool:
        return self._is_node_type_in(
            TreeSitterTopLevelPreprocessType.If.value,
            TreeSitterTopLevelPreprocessType.IfDef.value,
        )

    def _parse_preprocess_if_section(self) -> node.IfSectionDirective:
        # For `#if`, refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L397-L471
        # For `#ifdef` and `#ifndef`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L472-L556
        assert self._is_preprocess_if_section()
        code_range = self._get_current_code_range()
        is_if_directive = self._is_preprocess_if_directive()
        self._cursor.goto_first_child()

        if_head_node = (
            self._consume_preprocess_if_directive_head() if is_if_directive
            else self._consume_preprocess_ifdef_directive_head()
        )

        elif_groups: List[node.ElifDirective] = []
        while self._is_preprocess_elif():
            elif_groups.append(self._consume_preprocess_elif())

        else_group: Optional[node.ElseDirective] = None
        if self._is_preprocess_else():
            else_group = self._consume_preprocess_else()

        endif_code_range = self._get_current_code_range()
        self._consume_node_with_type(node_type="#endif")
        endif = node.EndIfDirective(endif_code_range)

        self._cursor.goto_parent()
        return node.IfSectionDirective(
            code_range,
            if_head_node,
            elif_groups if elif_groups else None,
            else_group,
            endif,
        )

    def _is_preprocess_if_directive(self) -> bool:
        return self._is_node_type(TreeSitterTopLevelPreprocessType.If.value)

    def _try_consume_preprocess_group(self) -> Optional[Sequence[node.AstNode]]:
        group: List[node.AstNode] = []

        while True:
            ast_node = self._try_parse_top_level_ast_node()
            if ast_node is not None:
                group.append(ast_node)
            if ast_node is None :
                break
            if not self._cursor.goto_next_sibling():
                break

        return group if group else None

    def _consume_preprocess_if_directive_head(self) -> node.IfGroupDirective:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L397-L471
        start = self._get_current_code_start()
        self._consume_node_with_type(node_type="#if")
        cond_end = self._get_current_code_end()
        condition = self._consume_preprocess_expression()
        self._consume_new_line()
        group = self._try_consume_preprocess_group()
        end = group[-1].code_range.end if group else cond_end

        return node.IfDirective(
            CodeRange(self._source_file, start, end), group, condition,
        )

    def _consume_preprocess_ifdef_directive_head(self) -> node.IfGroupDirective:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L472-L556
        # _check_node_type(cursor, TreeSitterTopLevelPreprocessType.IfDef.value)
        self._assert_current_node_type_in("#ifdef", "#ifndef")

        is_ifdef = self._is_node_type(node_type="#ifdef")
        start = self._get_current_code_start()
        self._cursor.goto_next_sibling()

        id_end = self._get_current_code_end()
        identifier = self._consume_tree_sitter_identifier()
        group = self._try_consume_preprocess_group()
        end = group[-1].code_range.end if group else id_end
        code_range = CodeRange(self._source_file, start, end)

        if is_ifdef:
            return node.IfDefDirective(code_range, group, identifier)
        else:
            return node.IfUndefDirective(code_range, group, identifier)

    def _is_preprocess_elif(self) -> bool:
        return self._is_node_type(TreeSitterPreprocessElseType.Elif.value)

    def _consume_preprocess_elif(self) -> node.ElifDirective:
        # For the tree structure of `preproc_elif`, refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L582-L647
        assert self._is_preprocess_elif()
        self._cursor.goto_first_child()

        elif_start = self._get_current_code_start()
        self._consume_node_with_type(node_type="#elif")

        cond_end = self._get_current_code_end()
        condition = self._consume_preprocess_expression()
        group = self._try_consume_preprocess_group()

        elif_end = group[-1].code_range.end if group else cond_end

        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        return node.ElifDirective(
            CodeRange(self._source_file, elif_start, elif_end),
            group,
            condition,
        )

    def _is_preprocess_else(self) -> bool:
        return self._is_node_type(TreeSitterPreprocessElseType.Else.value)

    def _consume_preprocess_else(self) -> node.ElseDirective:
        # For the structure of `preproc_else`, see https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L557-L581
        assert self._is_preprocess_else()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        # start = CodeLocation.from_ts_node_start(cursor)
        # else_end = CodeLocation.from_ts_node_end(cursor)

        self._consume_node_with_type(node_type="#else")
        group = self._try_consume_preprocess_group()

        # end = group[-1].code_range.end if group else else_end
        self._cursor.goto_parent()
        self._cursor.goto_next_sibling()
        # return ElseDirective(CodeRange(file_name, start, end), group)
        return node.ElseDirective(code_range, group)

    def _is_preprocess_define(self) -> bool:
        return self._is_node_type(
            node_type=TreeSitterTopLevelPreprocessType.Def.value,
        )

    def _parse_preprocess_define(self) -> node.DefineDirective:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L196-L240
        assert self._is_preprocess_define()
        start = self._get_current_code_start()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#define")
        identifier = self._consume_tree_sitter_identifier()
        end = self._get_current_code_end()
        replacement = self._try_consume_preprocess_arg()

        self._cursor.goto_parent()
        return node.DefineDirective(
            CodeRange(self._source_file, start, end),
            identifier, replacement,
        )

    def _consume_preprocess_param(self) -> str:
        if self._is_identifier():
            return self._consume_tree_sitter_identifier()
        elif self._is_node_type(node_type="..."):
            self._cursor.goto_next_sibling()
            return "..."

        raise self._create_code_error("not a preprocessing param")

    def _consume_preprocess_params(self) -> Sequence[str]:
        # Refer to https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L294-L360
        self._assert_current_node_type(node_type="preproc_params")
        self._cursor.goto_first_child()

        self._consume_left_parenthesis()

        params: List[str] = []
        if not self._is_end_of_params():
            params.append(self._consume_preprocess_param())
        while not self._is_end_of_params():
            self._consume_comma()
            params.append(self._consume_preprocess_param())

        self._cursor.goto_parent()

        for index, param in enumerate(params):
            if param == "..." and index + 1 != len(params):
                raise self._create_code_error(
                    "... should be the last parameter of "
                    "a function define directive",
                )

        self._cursor.goto_next_sibling()
        return params

    def _is_preprocess_function_define(self) -> bool:
        return self._is_node_type(
            TreeSitterTopLevelPreprocessType.FunctionDef.value,
        )

    def _parse_preprocess_function_define(self) -> node.FunctionDefineDirective:
        # See https://github.com/tree-sitter/tree-sitter-c/blob/ae19b676b13bdcc13b7665397e6d9b14975473dd/src/grammar.json#L241-L293
        assert self._is_preprocess_function_define()
        code_range = self._get_current_code_range()
        self._cursor.goto_first_child()

        self._consume_node_with_type(node_type="#define")
        identifier = self._consume_tree_sitter_identifier()
        params = self._consume_preprocess_params()
        replacement = self._try_consume_preprocess_arg()

        self._cursor.goto_parent()
        return node.FunctionDefineDirective(
            code_range, identifier, params, replacement,
        )


def _fix_function_definition(file_name: str, cursor: TreeCursor) -> Sequence[AstNode]:
    """
    libc_hidden_def (INTERNAL (strtol))


    INT
    __strtol (const STRING_TYPE *nptr, STRING_TYPE **endptr, int base)
    {
      return INTERNAL (__strtol_l) (nptr, endptr, base, 0, false,
    				_NL_CURRENT_LOCALE);
    }

    tree-sitter-c parses the above code to a function definition as follows:

    function_definition
        macro_type_specifier: "libc_hidden_def (INTERNAL (strtol))"
    """
    assert cursor.node is not None and cursor.node.has_error
    raise NotImplementedError()
