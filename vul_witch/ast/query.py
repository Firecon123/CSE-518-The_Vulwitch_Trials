from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import importlib
import importlib.util
import inspect
from pathlib import Path
from pycparser.c_ast import Node, NodeVisitor
from pycparser.plyparser import Coord
import sexpdata
from types import ModuleType
from typing import Any, List, Tuple, Type
from typing_extensions import override
import yaml

from vul_witch.ast.pattern import (
    AbstractPattern, AbstractPatternContext, AstPattern, WildcardPattern,
)
from vul_witch.ast.pattern import extension as pattern_extension_module


class VulnerabilitySeverity(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class Confidence(Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True)
class Rule:
    id: str
    pattern: "AbstractPattern[Any]"
    message: str
    severity: VulnerabilitySeverity
    confidence: Confidence


_builder_registry: List[Type[AbstractPattern[Any]]] = [
    AstPattern, WildcardPattern,
]


class PatternContextImpl(AbstractPatternContext):
    @override
    def build(self, data: Any) -> AbstractPattern[Any]:
        for pattern_cls in _builder_registry:
            pattern = pattern_cls.try_build(self, data)
            if pattern is not None:
                return pattern
        raise ValueError(f"unrecognized pattern: {data}")


def register_custom_pattern(t: Type[AbstractPattern[Any]]) -> None:
    _builder_registry.append(t)


def register_plugins_in_module(module: ModuleType) -> None:
    for _, member in inspect.getmembers(module):
        if not inspect.isclass(member):
            continue
        if member.__module__ != module.__name__:
            continue
        if issubclass(member, AbstractPattern):
            _builder_registry.append(member)


def import_and_register_plugins(module_path: Path) -> None:
    module_path = module_path.resolve()
    module_name = module_path.stem
    module_spec = importlib.util.spec_from_file_location(
        module_name, module_path,
    )
    if module_spec is None or module_spec.loader is None:
        raise ImportError(f"Cannot create spec for {module_path}")
    module = importlib.util.module_from_spec(module_spec)
    register_plugins_in_module(module)


register_plugins_in_module(pattern_extension_module)


def parse_pattern(s_exp: str) -> AbstractPattern[Any]:
    data = sexpdata.loads(s_exp)
    context = PatternContextImpl()
    return context.build(data)


def load_rules(rule_path: Path) -> List[Rule]:
    if not rule_path.exists():
        raise FileNotFoundError(f"rule path does not exist: {rule_path}")
    with rule_path.open() as f:
        rule_data_list = yaml.safe_load(f)["rules"]
    rules: List[Rule] = []
    for rule_data in rule_data_list:
        rule_data["pattern"] = parse_pattern(rule_data["pattern"])
        rules.append(Rule(**rule_data))
    return rules


@dataclass(frozen=True)
class MatchResult:
    location: Coord
    message: str
    severity: VulnerabilitySeverity


class PatternMatcher(NodeVisitor):
    _rules: Tuple[Rule, ...]
    _res: List[MatchResult]

    def __init__(self, rules: Sequence[Rule]) -> None:
        super().__init__()
        self._rules = tuple(rules)
        self._res = []

    @override
    def generic_visit(self, node: Node) -> None:
        for rule in self._rules:
            if rule.pattern.match(node):
                self._res.append(
                    MatchResult(node.coord, rule.message, rule.severity),
                )
        super().generic_visit(node)

    def get_result(self) -> Sequence[MatchResult]:
        return self._res
