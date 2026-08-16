# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
GDDL AST node definitions.

Kept deliberately thin: nodes carry enough structure for phases 4-8 to
walk, but no semantic interpretation happens here. In particular, the
parser does NOT try to distinguish "modify" vs "calculate" field
operations (see OpStmt) -- both are unified at evaluation time: an
op-statement is just an assign where "current value of field" is
implicitly prepended to the expression.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Node:
    line: int  # 1-indexed source line, for error messages


# ---- top level ----

@dataclass
class Program(Node):
    children: List[Node] = field(default_factory=list)
    warnings: List = field(default_factory=list)  # List[errors.CompileWarning]


@dataclass
class IdentifierEntry(Node):
    key: str
    description: str  # raw string literal, quotes stripped


@dataclass
class IdentifierBlock(Node):
    name: str
    entries: List[IdentifierEntry] = field(default_factory=list)
    width: Optional[str] = None  # §8.3: 'u8'/'u16'/'u32'/'u64' if this domain opted into indexed form


@dataclass
class FlagsEntry(Node):
    """One member of a `flags` domain. Three mutually exclusive value
    shapes, distinguished by `kind`:
      'auto'   -- bare name, no '='. Next unclaimed bit, in declaration
                  order (actual assignment is a registration-time
                  concern, not decided here).
      'bit'    -- '= bN'. explicit_bit holds N; the claimed bit position
                  is 1 << N (also computed later, not here).
      'number' -- '= 0'. The zero/none sentinel; explicit_number is
                  always 0 by construction (any other literal number is
                  a parse-time error -- a flags member's value is a bit
                  or zero, no exceptions, per spec)."""
    name: str
    kind: str
    explicit_bit: Optional[int] = None
    explicit_number: Optional[int] = None


@dataclass
class FlagsBlock(Node):
    name: str
    width: str  # 'u8'/'u16'/'u32'/'u64' -- required (unlike IdentifierBlock.width, which is optional)
    entries: List[FlagsEntry] = field(default_factory=list)


@dataclass
class FieldDef(Node):
    name: str
    type_tokens: str  # raw text, e.g. "u32", "string 32", "Object"


@dataclass
class DefineBlock(Node):
    name: str
    fields: List[FieldDef] = field(default_factory=list)


@dataclass
class InstanceDecl(Node):
    type_name: str
    instance_name: str
    source_name: Optional[str]   # None if no "= Source"
    is_delete: bool
    body: List[Node] = field(default_factory=list)


# ---- statements (inside instance bodies / nested struct fields) ----

@dataclass
class AssignStmt(Node):
    """field = rhs   (plain overwrite for scalars, full replace-then-modify
    for struct fields when rhs names a source instance and children follow)"""
    field_name: str
    rhs: str
    children: List[Node] = field(default_factory=list)


@dataclass
class OpStmt(Node):
    """field <op> rhs   e.g. `hitpoints * 2` or `x / 2 + 60`.
    op is the first operator token; rhs is everything after it, raw."""
    field_name: str
    op: str
    rhs: str


@dataclass
class BareFieldStmt(Node):
    """field with no '=' and no operator, followed by an indented block.
    Modify-only: enters existing/blank scope, touches only listed children.
    May legitimately have zero children (§12.1 warning, not an error)."""
    field_name: str
    children: List[Node] = field(default_factory=list)


@dataclass
class RawStmt(Node):
    """Fallback for a line that didn't match any known statement shape."""
    text: str
