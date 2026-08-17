# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Phase 6: instance resolution (phases 6+7 fused -- expression evaluation
happens inline at the point each statement executes, rather than as a
fully separate later pass).

Implements the single Nested Field Semantics rule, recursively, at
every depth:

    field = SourceInstance   -> full replace-then-modify
    field  (bare)            -> modify-only: enter existing/blank scope,
                                 touch only the listed children
    scalar assign/op         -> plain overwrite / read-modify-write

No merge mode exists anywhere, by design.

Confirmed rules:
  - modify vs. calculate are not separate mechanisms. Both assign
    (`field = expr`) and op-stmt (`field <op> expr`) scalar forms go
    through one expression evaluator. Op-stmt is just assign where
    "current value of field" is implicitly prepended to the expression.
  - Reading an uninitialized field is ALWAYS a compile-time error, no
    delete-instance carve-out. `delete` only tolerates fields that are
    never assigned (a phase-8 concern); it never relaxes read-validity.

Cross-field expression references: a bare or dotted identifier token
inside an expression means "the current value of that field, at this
point in the instance's sequential execution" -- same rule that governs
self-modification, generalized to any field name. Dotted paths walk
nested struct fields at any depth, within the CURRENT instance only.
Dot syntax is shared between nested-field access (`object.weight`) and
identifier-domain member access (`ActionAttack.melee_weapon`);
disambiguation checks whether the first segment is a struct-typed field
on the CURRENT scope first, only falling back to identifier-domain
lookup if it isn't a field at all.

Expression evaluation is strictly left-to-right (§6.3.1) -- no standard
precedence table -- via a hand-rolled recursive-descent evaluator, never
Python's own eval(). Op-statements pass the field's current value through
as a REAL Python number, never stringified and re-tokenized -- that
string-splice-then-retokenize pattern was the root cause behind three
separate-looking bugs (standard-precedence-via-eval(), unary minus,
scientific notation): every one was a different way round-tripping a
value through text could silently mangle it.

Numeric type coercion + range enforcement (spec §5) happen at the point
of storage: full-precision computation throughout the expression, then
coerce (widen int->float automatic; narrow float->int only if no
fractional loss), then range-check the final coerced value against the
type's fixed bounds, then store. Only the final stored result is
range-checked -- never intermediate sub-expression values.
"""

import copy
import math
import re

from .ast_nodes import AssignStmt, OpStmt, BareFieldStmt, RawStmt
from .registry import Registry
from .errors import CompileError
from .phase5 import run_phase5
from .parser import _unescape_string_content, _StringEscapeError, _is_quote_escaped

UNINIT_SENTINEL_DOC = None


class GDDLResolveError(CompileError):
    def __init__(self, message, line=None, check=None, open_question=None):
        self.open_question = open_question
        if open_question:
            message = f"{message} [OPEN QUESTION: {open_question}]"
        super().__init__(phase=6, message=message, line=line, check=check)


class DependencyFailedError(GDDLResolveError):
    """Raised when resolving an instance can't proceed because something
    it (transitively) copies from already failed. Carries `root` -- the
    name of the instance with the actual direct/root-cause error -- so
    every instance downstream of one failure reports the SAME root and a
    single message, instead of re-deriving its own field-level errors."""

    def __init__(self, root: str):
        self.root = root
        super().__init__(f"unresolvable: depends on '{root}', which failed to compile")


class _Uninit:
    """Deepcopy-safe singleton -- plain object() loses identity across
    copy.deepcopy, which would silently break every `is UNINIT` check
    the moment a struct value gets copied (i.e. constantly)."""

    def __repr__(self):
        return "<UNINITIALIZED>"

    def __deepcopy__(self, memo):
        return self


UNINIT = _Uninit()


class StructValue:
    """A resolved (or in-progress) struct instance: field name -> value.
    Value is either UNINIT, a scalar (int/float/str/IdentifierRef), or a
    nested StructValue."""

    def __init__(self, type_name):
        self.type_name = type_name
        self.fields = {}

    def __repr__(self):
        return f"StructValue({self.type_name}, {self.fields!r})"


class IdentifierRef:
    """Resolved value of a `Domain.member` reference: carries the
    logical ID (hash of the entry's description text) plus domain/key
    for debugging."""

    def __init__(self, domain, key, logical_id):
        self.domain = domain
        self.key = key
        self.logical_id = logical_id

    def __repr__(self):
        return f"{self.domain}.{self.key}#{self.logical_id}"

    def __eq__(self, other):
        return isinstance(other, IdentifierRef) and self.logical_id == other.logical_id


_INT_TYPES = {"u8", "u16", "u32", "u64", "i8", "i16", "i32", "i64"}
_FLOAT_TYPES = {"f32", "f64"}

# Standard two's-complement bounds (spec §5, Numeric Range Enforcement)
_INT_RANGES = {
    "u8": (0, 255),
    "u16": (0, 65535),
    "u32": (0, 4294967295),
    "u64": (0, 18446744073709551615),
    "i8": (-128, 127),
    "i16": (-32768, 32767),
    "i32": (-2147483648, 2147483647),
    "i64": (-9223372036854775808, 9223372036854775807),
}
# Finite representable magnitude (IEEE 754).
_FLOAT_MAX_MAGNITUDE = {
    "f32": 3.4028235e38,
    "f64": 1.7976931348623157e308,
}

_NUMBER_RE = re.compile(r"^-?\d+(\.\d+)?([eE][+-]?\d+)?$")
_STRING_TYPE_RE = re.compile(r"^string\s+(\d+)$")
_BIT_LITERAL_RE = re.compile(r"^b(\d+)$")


# ---- array value literal parsing (arrays design) ----
#
# Two small, quote-and-brace-aware text primitives, in the same spirit
# as parser.py's own split_top_level_equals: array element/group
# separators (',') can themselves sit inside a quoted string element
# (a 'string N : M' array), so a naive str.split(',') would mis-split
# a literal comma inside a string element's own text.

def _is_single_brace_group(text: str) -> bool:
    """True if `text` (already stripped) is exactly ONE brace-delimited
    group: starts with '{', ends with '}', and that opening brace's
    matching close is the string's LAST character -- not just "starts
    with '{' and ends with '}'", which '{1,2},{3,4}' also satisfies but
    is NOT a single group (two groups, comma-joined)."""
    if not (text.startswith("{") and text.endswith("}")):
        return False
    depth = 0
    for i, c in enumerate(text):
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i == len(text) - 1
    return False


def _split_top_level_commas(text: str):
    """Splits on commas at brace-depth 0, outside quoted strings.
    Quote-awareness mirrors parser.py's _is_quote_escaped exactly (the
    same backslash-run-parity check, imported rather than reimplemented)."""
    parts = []
    depth = 0
    in_string = False
    start = 0
    for i, c in enumerate(text):
        if c == '"' and not _is_quote_escaped(text, i):
            in_string = not in_string
        elif not in_string:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == "," and depth == 0:
                parts.append(text[start:i])
                start = i + 1
    parts.append(text[start:])
    return [p.strip() for p in parts]


class Resolver:
    def __init__(self, registry: Registry):
        self.reg = registry
        self.cache = {}          # instance name -> fully resolved StructValue
        self.errors = {}         # instance name -> CompileError: its OWN direct/root error
        self.blocked = {}        # instance name -> str: root name it's transitively blocked on
        self._resolving = set()  # cycle guard
        self.warnings = []       # List[CompileWarning], carried over from phase 3

    # ---- entry point ----

    def resolve_instance(self, name: str) -> StructValue:
        if name in self.cache:
            return self.cache[name]
        if name in self.errors:
            raise DependencyFailedError(name)
        if name in self.blocked:
            raise DependencyFailedError(self.blocked[name])
        if name in self._resolving:
            # Defensive backstop only, not the primary detection mechanism
            # anymore: circular instance-copy references are now caught
            # at registration (phase 4, Registry._detect_circular_dependencies)
            # via ordinary graph-based cycle detection, before phase 6 ever
            # starts -- every instance in a detected cycle is seeded into
            # self.errors before resolve_all() begins, so it short-circuits
            # at the "name in self.errors" check above and never reaches
            # here in practice. Kept as a genuine backstop (should the
            # dependency-graph walk ever miss a real recursive-resolve call
            # site in the future) rather than removed, matching how phase
            # 5's checks were kept as defensive assertions in phase 6
            # after phase 5 started catching the same things earlier.
            raise GDDLResolveError(
                f"circular instance-copy reference involving '{name}' "
                "(caught by the phase-6 backstop -- this should have been "
                "caught earlier at phase 4; if you're seeing this, the "
                "dependency-graph cycle detection has a gap)",
                check="circular_dependency")
        decl = self.reg.instances.get(name)
        if decl is None:
            raise GDDLResolveError(f"unknown instance '{name}'")

        self._resolving.add(name)
        try:
            if decl.source_name is not None:
                source = self.resolve_instance(decl.source_name)
                value = copy.deepcopy(source)
                value.type_name = decl.type_name
            else:
                value = self._blank_struct(decl.type_name)

            self._apply_statements(value, decl.body, allow_incomplete=decl.is_delete)
        except DependencyFailedError as e:
            self._resolving.discard(name)
            self.blocked[name] = e.root
            raise DependencyFailedError(e.root)
        except GDDLResolveError as e:
            self._resolving.discard(name)
            self.errors[name] = e
            raise DependencyFailedError(name)

        self._resolving.discard(name)
        self.cache[name] = value
        return value

    def resolve_all(self):
        """Collect-and-report: don't halt the whole pass on the first
        error. Every instance ends up in exactly one of cache / errors /
        blocked."""
        for name in self.reg.instances:
            if name in self.cache or name in self.errors or name in self.blocked:
                continue
            try:
                self.resolve_instance(name)
            except DependencyFailedError:
                pass

    # ---- helpers ----

    def _blank_struct(self, type_name: str) -> StructValue:
        sv = StructValue(type_name)
        d = self.reg.defines.get(type_name)
        if d is not None:
            for f in d.fields:
                sv.fields[f.name] = UNINIT
        return sv

    def _apply_statements(self, scope: StructValue, stmts, allow_incomplete: bool):
        for stmt in stmts:
            if isinstance(stmt, AssignStmt):
                self._apply_assign(scope, stmt, allow_incomplete)
            elif isinstance(stmt, OpStmt):
                self._apply_op(scope, stmt, allow_incomplete)
            elif isinstance(stmt, BareFieldStmt):
                self._apply_bare(scope, stmt, allow_incomplete)
            elif isinstance(stmt, RawStmt):
                raise GDDLResolveError(
                    f"unrecognized statement shape: {stmt.text!r}", stmt.line)
            else:
                raise GDDLResolveError(f"unhandled statement node {stmt!r}", stmt.line)

    def _apply_assign(self, scope: StructValue, stmt: AssignStmt, allow_incomplete: bool):
        category, type_name = self.reg.field_category(scope.type_name, stmt.field_name)

        # Defensive backstop: phase 5 (phase5.py's AssignStmt check) already
        # rejects bracket indexing on a non-array field statically, for
        # every instance that reaches phase 6 at all -- same "kept as a
        # backstop even once an earlier phase already catches it" precedent
        # this file's own resolve_instance() circular-dependency check uses.
        if stmt.index is not None and category != "array":
            raise GDDLResolveError(
                f"bracket indexing used on '{stmt.field_name}' "
                f"({category or 'unknown'}-typed) -- only array-typed "
                "fields support bracket-indexed assignment", stmt.line)

        if category == "struct":
            rhs = stmt.rhs.strip()
            if rhs not in self.reg.instances:
                raise GDDLResolveError(
                    f"'{stmt.field_name} = {rhs}': struct-typed field assigned "
                    f"a source that isn't a known instance", stmt.line)
            source = self.resolve_instance(rhs)
            new_val = copy.deepcopy(source)
            self._apply_statements(new_val, stmt.children, allow_incomplete)
            scope.fields[stmt.field_name] = new_val
            return

        if stmt.children:
            raise GDDLResolveError(
                f"scalar field '{stmt.field_name}' has an indented block "
                "under a plain assign -- only struct-typed fields can "
                "have children here", stmt.line)

        if category == "array":
            if stmt.index is not None:
                self._apply_array_element_assign(scope, stmt, type_name)
            else:
                rhs = stmt.rhs.strip()
                value = self._parse_array_literal(rhs, type_name, scope, stmt.field_name, stmt.line)
                scope.fields[stmt.field_name] = value
            return

        if category == "identifier":
            rhs = stmt.rhs.strip()
            val = self._eval_expr(rhs, scope, stmt.line)
            if not isinstance(val, IdentifierRef) or val.domain != type_name:
                raise GDDLResolveError(
                    f"'{stmt.field_name}' is typed as identifier domain "
                    f"'{type_name}', but was assigned {stmt.rhs.strip()!r} -- "
                    "a bare literal or wrong-domain reference can never "
                    "satisfy an identifier-typed field", stmt.line)
            scope.fields[stmt.field_name] = val
            return

        is_flags = category == "flags"
        rhs = stmt.rhs.strip()
        if len(rhs) >= 2 and rhs[0] == '"' and rhs[-1] == '"':
            try:
                val = _unescape_string_content(rhs[1:-1])
            except _StringEscapeError as e:
                raise GDDLResolveError(
                    f"'{stmt.field_name}': {e.message}", stmt.line,
                    check="string_escape")
        else:
            val = self._eval_expr(rhs, scope, stmt.line, is_flags=is_flags)

        if isinstance(val, str):
            scope.fields[stmt.field_name] = self._check_string_length(
                val, stmt.field_name, type_name, stmt.line)
        else:
            # A flags-typed field's declared_type (for coercion/range
            # purposes) is its WIDTH, not the domain name -- the domain
            # name means nothing to _coerce_numeric/_check_range, which
            # only understand the u8/u16/u32/u64/etc. type-token
            # vocabulary; substituting the width here reuses that
            # existing, already-correct unsigned-integer range logic
            # verbatim rather than duplicating it for flags specifically.
            coerce_type = self.reg.get_flags_width(type_name) if is_flags else type_name
            scope.fields[stmt.field_name] = self._coerce_numeric(
                val, stmt.field_name, coerce_type, stmt.line)

    def _apply_op(self, scope: StructValue, stmt: OpStmt, allow_incomplete: bool):
        category, type_name = self.reg.field_category(scope.type_name, stmt.field_name)

        # Defensive backstop: phase 5 already rejects both halves of this
        # (bracket indexing on a non-array field, and a non-indexed
        # op-statement on an array field) statically -- see phase5.py's
        # OpStmt check and _apply_assign's own matching comment above.
        if stmt.index is not None:
            if category != "array":
                raise GDDLResolveError(
                    f"bracket indexing used on '{stmt.field_name}' "
                    f"({category or 'unknown'}-typed) -- only array-typed "
                    "fields support bracket-indexed operator statements", stmt.line)
            self._apply_array_element_op(scope, stmt, type_name)
            return

        if category is not None and category not in ("scalar", "flags"):
            raise GDDLResolveError(
                f"operator statement on '{stmt.field_name}' (a {category}-typed "
                "field) -- operator statements only apply to plain scalar "
                "and flags-typed fields, which have a current numeric value "
                "to read-modify-write; struct and identifier-domain fields "
                "don't (an array-typed field's element can be, via bracket "
                "indexing)", stmt.line)

        current = scope.fields.get(stmt.field_name, UNINIT)
        if current is UNINIT:
            raise GDDLResolveError(
                f"'{stmt.field_name}' is read by an operator statement "
                f"('{stmt.op} {stmt.rhs}') before being initialized -- "
                "reading an uninitialized field is always a compile-time "
                "error, delete-marked instances included", stmt.line,
                check="uninitialized_read")

        # "current, then the operator, then the rest of the line" is ONE
        # expression evaluated strictly left to right (§6.3.1). `current`
        # is passed as a real value here, never stringified.
        is_flags = category == "flags"
        val = self._eval_op_expr(
            current, stmt.op, stmt.rhs, scope, stmt.line, is_flags=is_flags)
        coerce_type = self.reg.get_flags_width(type_name) if is_flags else type_name
        scope.fields[stmt.field_name] = self._coerce_numeric(
            val, stmt.field_name, coerce_type, stmt.line)

    def _apply_bare(self, scope: StructValue, stmt: BareFieldStmt, allow_incomplete: bool):
        category, field_type = self.reg.field_category(scope.type_name, stmt.field_name)
        if category != "struct":
            got = category or "unknown"
            raise GDDLResolveError(
                f"bare field '{stmt.field_name}' (modify-only form) used on a "
                f"{got} field -- only struct-typed fields have a scope to "
                "enter", stmt.line)

        existing = scope.fields.get(stmt.field_name, UNINIT)
        if existing is UNINIT:
            sub = self._blank_struct(field_type)
        else:
            sub = existing

        self._apply_statements(sub, stmt.children, allow_incomplete)
        scope.fields[stmt.field_name] = sub

    # ---- arrays (design: direct bracket indexing, no bare/nested-block
    # form -- see AssignStmt/OpStmt.index and their call sites above) ----

    def _apply_array_element_assign(self, scope: StructValue, stmt: AssignStmt, array_info):
        """'field[N] = expr' -- modifies ONE existing element. Requires
        the array to already hold a full value (a prior full-literal
        assign in this same instance body, or copied in from a source
        instance) -- arrays never support the bare/modify-only field's
        build-up-incrementally-leaving-the-rest-UNINIT capability (that
        form was explicitly rejected for arrays by the design in favor
        of bracket indexing), so an array field is always either UNINIT
        as a whole or fully populated as a whole, never partially."""
        if len(array_info.dims) != 1:
            raise GDDLResolveError(
                f"'{stmt.field_name}[{stmt.index}]': bracket indexing is "
                "only supported for one-dimensional arrays in this pass -- "
                f"'{stmt.field_name}' has {len(array_info.dims)} dimensions; "
                "assign the full array with a literal instead", stmt.line,
                check="array_multidim_index_unsupported")

        current = scope.fields.get(stmt.field_name, UNINIT)
        if current is UNINIT:
            raise GDDLResolveError(
                f"'{stmt.field_name}' is indexed ('[{stmt.index}]') before "
                "being initialized -- an array must already hold a full "
                "value (a literal assign, or copied in from a source "
                "instance) before an individual element can be assigned "
                "by index", stmt.line, check="uninitialized_read")

        size = array_info.dims[0]
        if not (0 <= stmt.index < size):
            raise GDDLResolveError(
                f"'{stmt.field_name}[{stmt.index}]': index out of bounds -- "
                f"'{stmt.field_name}' has {size} element(s), valid indices "
                f"are 0..{size - 1}", stmt.line, check="array_index_out_of_range")

        rhs = stmt.rhs.strip()
        val = self._parse_array_element(rhs, array_info.element_type, scope,
                                         stmt.field_name, stmt.line)
        current[stmt.index] = val

    def _apply_array_element_op(self, scope: StructValue, stmt: OpStmt, array_info):
        """'field[N] <op> expr' -- read-modify-write of ONE existing
        element, exactly the scalar op-statement rule ("current value at
        that index is the implicit leading operand") applied per-element
        instead of per-field. Reuses _eval_op_expr unchanged: a string
        element's current value naturally rejects here via that
        function's own non-numeric-current check, the same way a plain
        string-typed scalar field already does."""
        if len(array_info.dims) != 1:
            raise GDDLResolveError(
                f"'{stmt.field_name}[{stmt.index}]': bracket indexing is "
                "only supported for one-dimensional arrays in this pass -- "
                f"'{stmt.field_name}' has {len(array_info.dims)} dimensions",
                stmt.line, check="array_multidim_index_unsupported")

        current_array = scope.fields.get(stmt.field_name, UNINIT)
        if current_array is UNINIT:
            raise GDDLResolveError(
                f"'{stmt.field_name}' is indexed ('[{stmt.index}]') by an "
                f"operator statement ('{stmt.op} {stmt.rhs}') before being "
                "initialized -- an array must already hold a full value "
                "before an individual element can be read-modify-written "
                "by index", stmt.line, check="uninitialized_read")

        size = array_info.dims[0]
        if not (0 <= stmt.index < size):
            raise GDDLResolveError(
                f"'{stmt.field_name}[{stmt.index}]': index out of bounds -- "
                f"'{stmt.field_name}' has {size} element(s), valid indices "
                f"are 0..{size - 1}", stmt.line, check="array_index_out_of_range")

        current_elem = current_array[stmt.index]
        val = self._eval_op_expr(current_elem, stmt.op, stmt.rhs, scope, stmt.line,
                                  is_flags=False)
        coerced = self._coerce_numeric(
            val, f"{stmt.field_name}[{stmt.index}]", array_info.element_type, stmt.line)
        current_array[stmt.index] = coerced

    def _parse_array_literal(self, text, array_info, scope: StructValue, field_name, line):
        """Parses a full array-value literal against array_info.dims.
        The single OUTERMOST brace layer is always optional; every level
        from there inward requires explicit braces to disambiguate
        nested groups (exactly the design's own rule) -- implemented as
        peeling at most ONE optional enclosing '{...}' here, before
        dimension-based recursion begins in _parse_array_group, which
        always requires braces at every level it descends into."""
        text = text.strip()
        if _is_single_brace_group(text):
            text = text[1:-1].strip()
        return self._parse_array_group(
            text, array_info.dims, array_info.element_type, scope, field_name, line)

    def _parse_array_group(self, text, dims, element_type, scope: StructValue, field_name, line):
        parts = _split_top_level_commas(text)
        expected = dims[0]
        if len(parts) != expected:
            raise GDDLResolveError(
                f"'{field_name}': expected {expected} element(s) at this "
                f"nesting level, got {len(parts)} ({text!r})", line,
                check="array_shape_mismatch")

        if len(dims) == 1:
            return [self._parse_array_element(p, element_type, scope, field_name, line)
                    for p in parts]

        result = []
        for p in parts:
            p = p.strip()
            if not _is_single_brace_group(p):
                raise GDDLResolveError(
                    f"'{field_name}': inner grouping braces are required "
                    f"here (got {p!r}) -- only the single outermost brace "
                    "layer of an array literal is optional; every level "
                    "inward must be explicitly wrapped in '{{...}}' to "
                    "disambiguate shape", line, check="array_shape_mismatch")
            result.append(self._parse_array_group(
                p[1:-1].strip(), dims[1:], element_type, scope, field_name, line))
        return result

    def _parse_array_element(self, text, element_type, scope: StructValue, field_name, line):
        """Parses/evaluates ONE leaf element: a quoted string literal, or
        a numeric expression through the SAME evaluator scalar fields
        already use (cross-field references, bN literals, arithmetic all
        work inside an array element exactly as in a plain scalar
        assign) -- then coerces/range-checks it against the element type,
        reusing _coerce_numeric/_check_string_length verbatim, the same
        functions a plain scalar field of that type already goes
        through."""
        text = text.strip()
        if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
            try:
                val = _unescape_string_content(text[1:-1])
            except _StringEscapeError as e:
                raise GDDLResolveError(f"'{field_name}': {e.message}", line,
                                        check="string_escape")
            return self._check_string_length(val, field_name, element_type, line)

        val = self._eval_expr(text, scope, line, is_flags=False)
        if isinstance(val, str):
            return self._check_string_length(val, field_name, element_type, line)
        return self._coerce_numeric(val, field_name, element_type, line)

    # ---- numeric type coercion + range enforcement (spec §5) ----

    def _coerce_numeric(self, value, field_name, declared_type, line):
        if not isinstance(value, (int, float)):
            return value
        t = (declared_type or "").strip()
        if t in _FLOAT_TYPES:
            coerced = float(value)
            self._check_range(coerced, field_name, t, line)
            return coerced
        if t in _INT_TYPES:
            if isinstance(value, float):
                if value.is_integer():
                    coerced = int(value)
                else:
                    raise GDDLResolveError(
                        f"'{field_name}' is typed '{t}' (integer), but its "
                        f"computed value {value!r} has a fractional part -- "
                        "narrowing with fractional loss is a compile-time "
                        "error (spec §5, Numeric Type Coercion)", line,
                        check="numeric_coercion")
            else:
                coerced = value
            self._check_range(coerced, field_name, t, line)
            return coerced
        return value

    def _check_range(self, value, field_name, t, line):
        if t in _INT_RANGES:
            lo, hi = _INT_RANGES[t]
            if value < lo or value > hi:
                raise GDDLResolveError(
                    f"'{field_name}' is typed '{t}', but its computed value "
                    f"{value!r} is outside {t}'s range ({lo}..{hi}) -- "
                    "storing an out-of-range value is a compile-time error, "
                    "never silently wrapped or clamped (spec §5, Numeric "
                    "Range Enforcement)", line, check="numeric_range")
        elif t in _FLOAT_MAX_MAGNITUDE:
            if math.isnan(value) or math.isinf(value):
                raise GDDLResolveError(
                    f"'{field_name}' is typed '{t}', but its computed value "
                    f"is {value!r} -- NaN/inf can never be silently stored "
                    "(spec §5, Numeric Range Enforcement)", line,
                    check="numeric_range")
            limit = _FLOAT_MAX_MAGNITUDE[t]
            if abs(value) > limit:
                raise GDDLResolveError(
                    f"'{field_name}' is typed '{t}', but its computed value "
                    f"{value!r} exceeds {t}'s finite representable magnitude "
                    f"(+/-{limit:.6g}) -- storing an out-of-range value is a "
                    "compile-time error, never silently produced as inf "
                    "(spec §5, Numeric Range Enforcement)", line,
                    check="numeric_range")

    def _check_string_length(self, value: str, field_name, declared_type, line):
        """Spec §5, String Length Enforcement: a `string N` field can
        hold at most N-1 UTF-8 bytes (1 byte reserved for the ASCIIZ
        terminator). Storing a value whose UTF-8 byte length exceeds
        that is a compile-time error, never silent truncation. Length is
        measured as UTF-8 byte length, not character count -- consistent
        with source text being treated as UTF-8 bytes everywhere else
        (§4.1.1). Only applies when the declared type actually parses as
        `string N`; if a string somehow ends up assigned to some other
        declared type, that's a pre-existing, separate type-mismatch gap
        this doesn't newly address."""
        m = _STRING_TYPE_RE.match((declared_type or "").strip())
        if m is None:
            return value
        n = int(m.group(1))
        max_bytes = n - 1
        byte_len = len(value.encode("utf-8"))
        if byte_len > max_bytes:
            raise GDDLResolveError(
                f"'{field_name}' is typed 'string {n}', but its value "
                f"{value!r} is {byte_len} UTF-8 bytes -- exceeds the "
                f"{max_bytes}-byte capacity ('string {n}' reserves 1 byte "
                "for the ASCIIZ terminator) -- storing an over-length "
                "string is a compile-time error, never silently truncated "
                "(spec §5, String Length Enforcement)", line,
                check="string_length")
        return value

    # ---- expression evaluation (phase 7, fused into phase 6) ----

    _TOKEN_RE = re.compile(
        r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?|"
        r"b\d+(?!\w)|"
        r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|[+\-*/()~|&^]"
    )

    def _tokenize(self, expr: str, line: int):
        tokens = self._TOKEN_RE.findall(expr)
        collapsed = re.sub(r"\s+", "", expr)
        rejoined = "".join(tokens)
        if rejoined != collapsed:
            raise GDDLResolveError(f"can't parse expression {expr!r}", line)
        return tokens

    def _eval_expr(self, expr: str, scope: StructValue, line: int, is_flags: bool = False):
        """Strict left-to-right evaluation (§6.3.1). Used for
        assign-statement rhs, where the whole expression genuinely is
        source text.

        `is_flags` says whether the field THIS expression is being
        assigned to is flags-typed -- constant across the whole
        expression tree (parens included), since it describes the
        target field, not any individual sub-term. Threaded through to
        gate which operator family is legal: arithmetic (+ - * /) is a
        compile-time error on a flags-typed field, bitwise (| & ^ ~) is
        a compile-time error on anything else -- there is no other
        bitmask mechanism in the language, so bitwise operators exist
        only for flags, full stop, in both directions."""
        expr = expr.strip()
        if not expr:
            raise GDDLResolveError("empty expression", line)

        tokens = self._tokenize(expr, line)
        if not tokens:
            raise GDDLResolveError(f"can't parse expression {expr!r}", line)

        value, rest = self._parse_expr_tokens(tokens, scope, line, is_flags)
        if rest:
            raise GDDLResolveError(
                f"unexpected trailing token(s) {rest!r} in expression {expr!r}", line)
        return value

    def _eval_op_expr(self, current, op: str, rhs_text: str, scope: StructValue, line: int,
                       is_flags: bool = False):
        """Evaluate 'current <op> rest-of-line' WITHOUT ever stringifying
        `current` -- `current` is carried through as a real Python
        int/float, used directly as the leading operand; only rhs_text
        (genuine source text) is ever tokenized. See _eval_expr for what
        `is_flags` gates."""
        if not isinstance(current, (int, float)):
            raise GDDLResolveError(
                f"operator '{op}' applied to a non-numeric current value "
                f"{current!r}", line)

        tokens = self._tokenize(rhs_text.strip(), line)
        if not tokens:
            raise GDDLResolveError(f"expected an operand after operator '{op}'", line)

        rhs_val, tokens = self._parse_operand(tokens, scope, line, is_flags)
        value = self._apply_binop(current, op, rhs_val, line, is_flags)
        value, tokens = self._fold_left(value, tokens, scope, line, is_flags)
        if tokens:
            raise GDDLResolveError(
                f"unexpected trailing token(s) {tokens!r} after "
                f"'{op} {rhs_text}'", line)
        return value

    def _parse_expr_tokens(self, tokens, scope, line, is_flags: bool = False):
        value, tokens = self._parse_operand(tokens, scope, line, is_flags)
        return self._fold_left(value, tokens, scope, line, is_flags)

    def _fold_left(self, value, tokens, scope, line, is_flags: bool = False):
        while tokens and tokens[0] in ("+", "-", "*", "/", "|", "&", "^"):
            op, tokens = tokens[0], tokens[1:]
            if not tokens:
                raise GDDLResolveError(
                    f"expected an operand after operator '{op}'", line)
            rhs, tokens = self._parse_operand(tokens, scope, line, is_flags)
            value = self._apply_binop(value, op, rhs, line, is_flags)
        return value, tokens

    def _parse_operand(self, tokens, scope, line, is_flags: bool = False):
        """operand := NUMBER | BIT_LITERAL | reference | '(' expr ')'
        | '-' operand | '+' operand | '~' operand"""
        if not tokens:
            raise GDDLResolveError("expected an operand, found end of expression", line)
        tok = tokens[0]

        if tok in ("-", "+"):
            if is_flags:
                raise GDDLResolveError(
                    f"unary '{tok}' used on a flags-typed field -- arithmetic "
                    "is a compile-time error on flags-typed fields, no "
                    "exceptions; combine flags with bitwise operators "
                    "(| & ^ ~) only", line, check="flags_arithmetic_rejected")
            value, rest = self._parse_operand(tokens[1:], scope, line, is_flags)
            if not isinstance(value, (int, float)):
                raise GDDLResolveError(
                    f"unary '{tok}' applied to a non-numeric value: {value!r}", line)
            return (-value if tok == "-" else value), rest

        if tok == "~":
            if not is_flags:
                raise GDDLResolveError(
                    "unary '~' used on a field that isn't flags-typed -- "
                    "bitwise operators only apply to flags-typed fields; "
                    "there is no other bitmask mechanism in the language",
                    line, check="flags_bitwise_rejected")
            value, rest = self._parse_operand(tokens[1:], scope, line, is_flags)
            if not isinstance(value, int) or isinstance(value, bool):
                raise GDDLResolveError(
                    f"unary '~' applied to a non-integer value: {value!r} -- "
                    "bitwise operators require integer operands", line)
            return ~value, rest

        if tok == "(":
            value, rest = self._parse_expr_tokens(tokens[1:], scope, line, is_flags)
            if not rest or rest[0] != ")":
                raise GDDLResolveError("missing closing ')'", line)
            return value, rest[1:]

        if tok == ")":
            raise GDDLResolveError("unexpected ')'", line)

        m = _BIT_LITERAL_RE.match(tok)
        if m:
            return (1 << int(m.group(1))), tokens[1:]

        if _NUMBER_RE.match(tok):
            if "." in tok or "e" in tok or "E" in tok:
                return float(tok), tokens[1:]
            return int(tok), tokens[1:]

        return self._resolve_reference(tok, scope, line), tokens[1:]

    def _apply_binop(self, left, op, right, line, is_flags: bool = False):
        if is_flags and op in ("+", "-", "*", "/"):
            raise GDDLResolveError(
                f"arithmetic operator '{op}' used on a flags-typed field -- "
                "arithmetic is a compile-time error on flags-typed fields, "
                "no exceptions; combine flags with bitwise operators "
                "(| & ^ ~) only", line, check="flags_arithmetic_rejected")
        if not is_flags and op in ("|", "&", "^"):
            raise GDDLResolveError(
                f"bitwise operator '{op}' used on a field that isn't "
                "flags-typed -- bitwise operators only apply to flags-typed "
                "fields; there is no other bitmask mechanism in the "
                "language", line, check="flags_bitwise_rejected")
        if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
            raise GDDLResolveError(
                f"operator '{op}' applied to non-numeric operand(s): "
                f"{left!r} {op} {right!r}", line)
        if op in ("|", "&", "^"):
            if not isinstance(left, int) or not isinstance(right, int):
                raise GDDLResolveError(
                    f"bitwise operator '{op}' applied to a non-integer operand: "
                    f"{left!r} {op} {right!r} -- bitwise operators require "
                    "integer operands", line)
            if op == "|":
                return left | right
            if op == "&":
                return left & right
            return left ^ right
        if op == "+":
            return left + right
        if op == "-":
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            return left / right
        raise GDDLResolveError(f"unknown operator '{op}'", line)

    def _resolve_reference(self, path: str, scope: StructValue, line: int):
        """Resolve a bare or dotted identifier token. Disambiguation:
        check whether the first segment is a struct-typed field on the
        CURRENT scope first; only if it isn't a field at all do we check
        whether it names a known identifier domain."""
        parts = path.split(".")
        first = parts[0]
        category, _ = self.reg.field_category(scope.type_name, first)

        if category is not None:
            return self._resolve_field_path(scope, parts, line)

        if first in self.reg.identifiers:
            if len(parts) != 2:
                raise GDDLResolveError(
                    f"identifier domain reference {path!r} must be exactly "
                    "'Domain.member'", line)
            domain, key = parts
            block = self.reg.identifiers[domain]
            entry = next((e for e in block.entries if e.key == key), None)
            if entry is None:
                raise GDDLResolveError(f"'{domain}' has no member '{key}'", line)
            lid = self.reg.get_logical_id(domain, key)
            return IdentifierRef(domain, key, lid)

        if first in self.reg.flags:
            if len(parts) != 2:
                raise GDDLResolveError(
                    f"flags domain reference {path!r} must be exactly "
                    "'Domain.member'", line)
            domain, key = parts
            # 0 (the none/zero sentinel) is a real, legitimate value --
            # distinguished from "no such member" with an explicit `is
            # None` check, not a truthiness check that would wrongly
            # reject it.
            value = self.reg.get_flags_value(domain, key)
            if value is None:
                raise GDDLResolveError(f"'{domain}' has no member '{key}'", line)
            return value

        raise GDDLResolveError(
            f"unknown reference '{path}' -- not a field of the current "
            f"instance ('{scope.type_name}'), and not a known identifier "
            "or flags domain. Cross-field references are scoped to the "
            "current instance only.", line)

    def _resolve_field_path(self, scope: StructValue, parts, line: int):
        first = parts[0]
        category, field_type = self.reg.field_category(scope.type_name, first)
        if category is None:
            raise GDDLResolveError(
                f"'{first}' is not a field of '{scope.type_name}'", line)

        val = scope.fields.get(first, UNINIT)
        if val is UNINIT:
            raise GDDLResolveError(
                f"'{first}' is read before being initialized -- reading an "
                "uninitialized field is always a compile-time error, "
                "delete-marked instances included", line,
                check="uninitialized_read")

        if len(parts) == 1:
            return val

        if category != "struct" or not isinstance(val, StructValue):
            raise GDDLResolveError(
                f"can't access '.{parts[1]}' on '{first}' -- only "
                "struct-typed fields can be dotted into further", line)

        return self._resolve_field_path(val, parts[1:], line)


def resolve_all(program) -> Resolver:
    """Full phase 4 -> 5 -> 6 pipeline from a parsed Program. Phase-4
    (circular dependency) and phase-5 (structural) errors are both
    seeded into the resolver's error map before resolution starts, so
    anything depending on a failed instance is correctly reported as
    blocked. Seeded in phase order, and a phase-5 finding never
    overwrites an already-seeded phase-4 finding for the same instance
    -- the earlier phase's diagnosis wins if both would apply."""
    reg = Registry(program)
    resolver = Resolver(reg)
    resolver.warnings = list(getattr(program, "warnings", []))

    resolver.errors.update(reg.circular_dependency_errors)  # phase 4, seeded first

    phase5_errors = run_phase5(reg)
    for name, err in phase5_errors.items():
        resolver.errors.setdefault(name, err)  # don't clobber a phase-4 finding

    resolver.resolve_all()
    return resolver
