from collections.abc import Sequence
from enum import Enum
import tree_sitter as ts
from typing import List, Optional, Set

from vul_witch.ast.location import CodeLocation, CodeRange
from vul_witch.ast.utils import create_code_range
