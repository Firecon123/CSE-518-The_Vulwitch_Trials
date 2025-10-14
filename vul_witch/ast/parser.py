from abc import ABCMeta, abstractmethod

from vul_witch.ast.node import TranslationUnit


class CParserInterface(metaclass=ABCMeta):
    @abstractmethod
    def parse_module(self) -> TranslationUnit:
        pass


# def build_module(file_name: str, module: Tree) -> TranslationUnit:
#     cursor = module.walk()
#     tu = cursor.node
#     assert tu is not None and tu.type == "translation_unit"
#     cursor.goto_first_child()

#     if cursor.node is None:
#         return TranslationUnit(create_code_range(file_name, tu), [])

#     nodes = []
#     while True:
#         prev_node = cursor.node
#         if _should_skip(cursor):
#             cursor.goto_next_sibling()
#         else:
#             nodes.append(build_ast_node(file_name, cursor))
#         if cursor.node == prev_node:
#             break

#     return TranslationUnit(create_code_range(file_name, tu), nodes)
