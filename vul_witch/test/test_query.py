from vul_witch.ast.pattern import AstPattern
from vul_witch.ast.pattern.extension import AnyPattern, EqPattern
from vul_witch.ast.query import (
    AstPattern, parse_pattern, PatternMatcher, Rule, VulnerabilitySeverity,
)
from vul_witch.test import AstTestCaseBase


class QueryTestCase(AstTestCaseBase):
    def test_match_gets(self) -> None:
        c_source = """
        int main(void) {
          char buffer[100];
          char *s = gets(buffer);
          return 0;
        }
        """
        tu = AstTestCaseBase.parse_c_source(c_source)
        pattern = AstPattern(
            ast_node_type="FuncCall",
            name=AstPattern(
                ast_node_type="ID",
                name=EqPattern(value="gets"),
            ),
        )
        rule = Rule(
            id="unsafe c functions",
            pattern=pattern,
            severity=VulnerabilitySeverity.HIGH,
            message="gets is unsafe",
        )
        matcher = PatternMatcher([rule])
        matcher.visit(tu)
        res = matcher.get_result()
        self.assertEqual(1, len(res))
        self.assertEqual(res[0].severity, VulnerabilitySeverity.HIGH)


class PatternBuildingTestCase(AstTestCaseBase):
    def test_build_ast_pattern(self) -> None:
        s_exp = """
        (FuncCall
          name: (ID name: (#eq "gets")))"""
        pattern = parse_pattern(s_exp)
        self.assertIsInstance(pattern, AstPattern)

    def test_build_any_pattern(self) -> None:
        s_exp = """
        (#any
          (BinaryOp
            op: (#any (#eq "&&") (#eq "||"))
            lhs: (Assignment))
          (BinaryOp
            op: (#any (#eq "&&") (#eq "||"))
            rhs: (Assignment)))"""
        pattern = parse_pattern(s_exp)
        self.assertIsInstance(pattern, AnyPattern)
