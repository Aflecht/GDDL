# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
GDDL parser -- phases 2 (preprocess) and 3 (parse) of the compiler-core
pipeline.
"""

import re
from typing import List, Tuple, Optional
from .ast_nodes import (
    Node, Program, IdentifierBlock, IdentifierEntry, FlagsBlock, FlagsEntry,
    DefineBlock, FieldDef, InstanceDecl, PoolDecl, AssignStmt, OpStmt, BareFieldStmt, RawStmt,
)
from .errors import CompileWarning

OPERATORS = ("+", "-", "*", "/", "|", "&", "^")

_FLAGS_WIDTHS = ("u8", "u16", "u32", "u64")
_BIT_LITERAL_RE = re.compile(r"^b(\d+)$")
_POOL_COUNT_RE = re.compile(r"^\d+$")


def _is_quote_escaped(s: str, i: int) -> bool:
    """True if the double-quote at s[i] is escaped -- i.e. immediately
    preceded by an ODD number of consecutive backslashes. Standard
    backslash-run parity resolution, not a novel algorithm: every
    complete `\\\\` pair is a satisfied "literal backslash" escape with
    nothing left dangling, so an EVEN count (including zero) means the
    quote is a real boundary; a single unpaired trailing backslash
    actively escapes the quote, so an ODD count means it doesn't
    terminate the string.

    This replaces a naive single-character lookback (`s[i-1] != "\\\\"`)
    that was wrong at both of its call sites: it cannot distinguish "one
    backslash before this quote" (escaped, correct) from "two
    backslashes before this quote" (a complete `\\\\` pair, NOT escaped
    -- but the naive check treated it as escaped anyway). Confirmed
    directly: a string legitimately ending in an escaped backslash
    immediately before its real closing quote (e.g. `"C:\\\\Users\\\\"`,
    a Windows-style path) failed to parse at all under the old check,
    even though the spec's own String Literal Escaping section cites
    exactly this case as the reason `\\\\` needs to exist."""
    count = 0
    j = i - 1
    while j >= 0 and s[j] == "\\":
        count += 1
        j -= 1
    return count % 2 == 1


class GDDLParseError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(f"line {line}: {message}")
        self.line = line
        # Purely additive (§18 multi-file support): str(e)/e.args[0] are
        # UNCHANGED from before this line existed -- every existing
        # caller that only ever used those two continues to see
        # identical output. This is for combine.py's line-remapping,
        # which needs the message body WITHOUT the "line N:" prefix
        # baked in at construction time (unlike CompileError below,
        # whose __str__ computes that prefix fresh on every call from
        # a mutable .line, GDDLParseError bakes it into the frozen
        # exception string immediately -- there was no raw-message
        # attribute to remap from before this addition).
        self.raw_message = message


class _StringEscapeError(Exception):
    """Internal signal only, raised by _unescape_string_content and
    immediately caught at each call site. Carries just the raw message
    with no line-number prefix baked in, so each call site (parser.py's
    own GDDLParseError, or resolve.py's GDDLResolveError for field-value
    strings) can attach its own line number and error-class formatting
    without doubling up "line N:" prefixes."""

    def __init__(self, message):
        self.message = message


def _unescape_string_content(content: str) -> str:
    """Processes a string literal's content (with the surrounding quote
    pair already removed) per the spec's String Literal Escaping rule:
    exactly two escape sequences, `\\"` -> `"` and `\\\\` -> `\\`,
    processed left-to-right as atomic two-character units. Any other
    backslash usage -- a lone trailing `\\`, or `\\` followed by any
    character other than `"` or `\\` -- is rejected, not passed through.

    Deliberately has no knowledge of line numbers or GDDL-specific error
    classes: this is the one shared implementation used by both
    _strip_quotes (identifier descriptions, phase 3) and resolve.py's
    field-value string handling (phase 6) -- each call site catches
    _StringEscapeError and re-raises with its own line number and error
    type, since the two callers are at different compile phases and use
    different error classes."""
    out = []
    i = 0
    n = len(content)
    while i < n:
        c = content[i]
        if c == "\\":
            if i + 1 >= n:
                raise _StringEscapeError(
                    "string literal ends with a lone '\\' (incomplete "
                    "escape sequence) -- only \\\" and \\\\ are valid "
                    "escape sequences; a bare trailing backslash is a "
                    "compile-time error, not a passthrough (spec: String "
                    "Literal Escaping)")
            nxt = content[i + 1]
            if nxt == '"':
                out.append('"')
            elif nxt == "\\":
                out.append("\\")
            else:
                raise _StringEscapeError(
                    f"invalid escape sequence '\\{nxt}' in string literal "
                    "-- only \\\" (literal quote) and \\\\ (literal "
                    "backslash) are valid; any other character after a "
                    "backslash is a compile-time error, not a passthrough "
                    "(spec: String Literal Escaping)")
            i += 2
        else:
            out.append(c)
            i += 1
    return "".join(out)


# ---------------------------------------------------------------------
# Phase 2: preprocess -- strip comments, drop empty lines
# ---------------------------------------------------------------------

def strip_comments(source: str) -> str:
    """Remove // line comments and nestable /* */ block comments.
    Quote-aware: a // or /* inside a "..." string is not a comment start."""
    out = []
    i = 0
    n = len(source)
    in_string = False
    block_depth = 0
    line = 1

    while i < n:
        c = source[i]

        if c == "\n":
            line += 1
            if block_depth == 0:
                out.append(c)
            i += 1
            continue

        if block_depth > 0:
            if source[i:i + 2] == "/*":
                block_depth += 1
                i += 2
                continue
            if source[i:i + 2] == "*/":
                block_depth -= 1
                i += 2
                continue
            i += 1
            continue

        if in_string:
            out.append(c)
            if c == '"' and not _is_quote_escaped(source, i):
                in_string = False
            i += 1
            continue

        if c == '"':
            in_string = True
            out.append(c)
            i += 1
            continue

        if source[i:i + 2] == "//":
            while i < n and source[i] != "\n":
                i += 1
            continue

        if source[i:i + 2] == "/*":
            block_depth = 1
            i += 2
            continue

        out.append(c)
        i += 1

    if block_depth > 0:
        raise GDDLParseError("unterminated block comment", line)
    if in_string:
        raise GDDLParseError("unterminated string literal", line)

    return "".join(out)


def preprocess(source: str) -> List[Tuple[int, str]]:
    stripped = strip_comments(source)
    result = []
    for idx, raw in enumerate(stripped.split("\n"), start=1):
        if raw.strip() != "":
            result.append((idx, raw))
    return result


# ---------------------------------------------------------------------
# Phase 3: parse -- indentation -> tree, then classify each line
# ---------------------------------------------------------------------

def _leading_whitespace(line: str) -> str:
    i = 0
    while i < len(line) and line[i] in " \t":
        i += 1
    return line[:i]


class _LineRec:
    __slots__ = ("lineno", "indent", "content")

    def __init__(self, lineno: int, indent: str, content: str):
        self.lineno = lineno
        self.indent = indent
        self.content = content


def _build_line_records(pairs: List[Tuple[int, str]]) -> List[_LineRec]:
    recs = []
    for lineno, raw in pairs:
        indent = _leading_whitespace(raw)
        content = raw[len(indent):].rstrip()
        if " " in indent and "\t" in indent:
            raise GDDLParseError(
                "indentation mixes spaces and tabs within a single line", lineno)
        recs.append(_LineRec(lineno, indent, content))
    return recs


def split_top_level_equals(content: str) -> Optional[Tuple[str, str]]:
    """Find the first '=' not inside a quoted string. Returns (lhs, rhs)
    stripped, or None if no top-level '=' exists."""
    in_string = False
    for i, c in enumerate(content):
        if c == '"' and not _is_quote_escaped(content, i):
            in_string = not in_string
        elif c == "=" and not in_string:
            return content[:i].strip(), content[i + 1:].strip()
    return None


_FIELD_NAME_RE = re.compile(r"^[A-Za-z_]\w*$")
# Arrays design: direct bracket indexing, e.g. 'damage_min_max[1]' -- an
# array-element reference is a plain field name immediately followed by
# '[N]', no whitespace between name and bracket, N a plain non-negative
# integer literal (never an expression; matches how 'bN' flags literals
# are similarly a closed, non-expression grammar at this phase).
_INDEXED_FIELD_RE = re.compile(r"^([A-Za-z_]\w*)\[(\d+)\]$")


def _require_field_name(tok: str, lineno: int):
    if not _FIELD_NAME_RE.match(tok):
        raise GDDLParseError(
            f"statement does not begin with a valid field identifier "
            f"(found {tok!r}) -- no legal statement shape (assign "
            "'field = expr', op-statement 'field op expr', or bare "
            "'field') matches this line", lineno)


def _parse_field_ref(tok: str, lineno: int) -> Tuple[str, Optional[int]]:
    """Validates a statement's leading field reference, which is either a
    plain field name or an array-element reference 'name[N]' (arrays
    design: direct bracket indexing for assign/op-statement element
    access and modification -- deliberately NOT available on the bare/
    modify-only form, see its own rejection in _classify_statement).
    Returns (base_name, index) -- index is None for a plain, non-array
    reference, which is what every statement written before arrays
    existed still produces."""
    if _FIELD_NAME_RE.match(tok):
        return tok, None
    m = _INDEXED_FIELD_RE.match(tok)
    if m:
        return m.group(1), int(m.group(2))
    raise GDDLParseError(
        f"statement does not begin with a valid field identifier "
        f"(found {tok!r}) -- no legal statement shape (assign 'field = "
        "expr', array-element assign 'field[N] = expr', op-statement "
        "'field op expr' or 'field[N] op expr', or bare 'field') matches "
        "this line", lineno)


def _classify_statement(lineno: int, content: str) -> Tuple[str, ...]:
    """Return a tag: ('assign', field, rhs, index) | ('op', field, op,
    rhs, index) | ('bare', field) | ('raw', text). Every shape requires a
    syntactically valid field identifier (or, for assign/op, an
    array-element reference 'field[N]') in leading position, checked
    uniformly here. `index` is None for every ordinary, non-array
    reference -- not just a default value nobody sets, the actual result
    for every statement that doesn't use bracket indexing."""
    eq = split_top_level_equals(content)
    if eq is not None:
        field_name, rhs = eq
        base_name, index = _parse_field_ref(field_name, lineno)
        return ("assign", base_name, rhs, index)

    tokens = content.split()
    first = tokens[0]
    base_name, index = _parse_field_ref(first, lineno)

    if len(tokens) >= 2:
        rest = content.split(None, 1)[1].strip()
        if rest and rest[0] in OPERATORS:
            return ("op", base_name, rest[0], rest[1:].strip(), index)

    if len(tokens) == 1:
        if index is not None:
            raise GDDLParseError(
                f"bare field '{first}' cannot use bracket indexing -- "
                "array element access/modification only applies to "
                "assign ('field[N] = expr') and operator ('field[N] op "
                "expr') statements, never the bare modify-only form "
                "(a struct-style nested-block alternative was "
                "considered for arrays and explicitly rejected in favor "
                "of direct bracket indexing)", lineno)
        return ("bare", first)

    return ("raw", content)


class Parser:
    def __init__(self, recs: List[_LineRec]):
        self.recs = recs
        self.n = len(recs)
        self._scope_char = None  # set per top-level scope, see _enter_scope
        self.warnings: List[CompileWarning] = []

    def _enter_scope(self):
        """Called once at the start of parsing a top-level construct's
        body. Resets character tracking -- a 'scope' for indentation-
        character consistency is the WHOLE top-level define/identifier/
        instance block, including everything nested inside it, not each
        nesting level independently."""
        self._scope_char = None

    def _check_scope_char(self, rec: "_LineRec"):
        """Character-consistency check, decoupled from depth detection.
        Depth is answered purely by comparing indent LENGTH (character
        agnostic); this is the separate check both same-depth sibling
        mixing and parent/child mixing route through."""
        if not rec.indent:
            return
        char = rec.indent[0]
        if self._scope_char is None:
            self._scope_char = char
            return
        if char != self._scope_char:
            names = {"\t": "tabs", " ": "spaces"}
            raise GDDLParseError(
                "mixed indentation characters within a single scope -- this "
                f"line uses {names[char]}, but the enclosing top-level block "
                f"already established {names[self._scope_char]} (indentation "
                "character must be consistent across an entire top-level "
                "define/identifier/instance block, including everything "
                "nested inside it -- not just within one nesting level)",
                rec.lineno)

    def parse(self) -> Program:
        prog = Program(line=1)
        i, children = self._parse_block(0, indent_prefix=None)
        prog.children = children
        prog.warnings = self.warnings
        if i != self.n:
            raise GDDLParseError(
                "unexpected trailing content (indentation error?)", self.recs[i].lineno)
        return prog

    def _parse_block(self, start: int, indent_prefix: Optional[str]) -> Tuple[int, List[Node]]:
        nodes: List[Node] = []
        i = start
        if i >= self.n:
            return i, nodes

        parent_len = len(indent_prefix) if indent_prefix is not None else -1
        block_indent = None

        while i < self.n:
            rec = self.recs[i]

            if len(rec.indent) <= parent_len:
                break

            if block_indent is None:
                block_indent = rec.indent
            elif rec.indent != block_indent:
                if len(rec.indent) < len(block_indent):
                    break
                if len(rec.indent) > len(block_indent):
                    raise GDDLParseError(
                        "unexpected indent (child block without a parent "
                        "statement, or inconsistent indentation)", rec.lineno)
                raise GDDLParseError(
                    "inconsistent indentation within scope "
                    f"(expected {block_indent!r}, got {rec.indent!r})", rec.lineno)

            node, i = self._parse_one(i, block_indent)
            nodes.append(node)

        return i, nodes

    def _parse_one(self, i: int, block_indent: str) -> Tuple[Node, int]:
        rec = self.recs[i]
        content = rec.content
        tokens = content.split()

        if tokens[0] == "identifier":
            return self._parse_identifier_block(i, block_indent)
        if tokens[0] == "flags":
            return self._parse_flags_block(i, block_indent)
        if tokens[0] == "define":
            return self._parse_define_block(i, block_indent)
        if tokens[0] == "pool":
            return self._parse_pool_decl(i, block_indent)

        return self._parse_instance_decl(i, block_indent)

    def _parse_identifier_block(self, i: int, block_indent: str) -> Tuple[Node, int]:
        rec = self.recs[i]
        tokens = rec.content.split()
        if len(tokens) not in (2, 3):
            raise GDDLParseError(
                f"expected 'identifier Name' or 'identifier Name width' "
                f"(width one of u8/u16/u32/u64), got: {rec.content!r}", rec.lineno)
        width = None
        if len(tokens) == 3:
            width = tokens[2]
            if width not in ("u8", "u16", "u32", "u64"):
                raise GDDLParseError(
                    f"invalid indexed width {width!r} for domain '{tokens[1]}' -- "
                    "must be one of u8/u16/u32/u64 (§8.3)", rec.lineno)
        node = IdentifierBlock(line=rec.lineno, name=tokens[1], width=width)
        i += 1
        self._enter_scope()
        i2, entries = self._parse_identifier_entries(i, block_indent)
        node.entries = entries
        return node, i2

    def _parse_identifier_entries(self, i: int, parent_indent: str) -> Tuple[int, List[IdentifierEntry]]:
        entries: List[IdentifierEntry] = []
        if i >= self.n:
            return i, entries
        nxt = self.recs[i]
        if len(nxt.indent) <= len(parent_indent):
            return i, entries

        entry_indent = None
        while i < self.n:
            rec = self.recs[i]
            if len(rec.indent) <= len(parent_indent):
                break
            self._check_scope_char(rec)
            if entry_indent is None:
                entry_indent = rec.indent
            elif rec.indent != entry_indent:
                raise GDDLParseError(
                    "inconsistent indentation in identifier block", rec.lineno)

            eq = split_top_level_equals(rec.content)
            if eq is None:
                raise GDDLParseError(
                    f"expected 'key = \"description\"' in identifier block, got: "
                    f"{rec.content!r}", rec.lineno)
            key, desc = eq
            desc = _strip_quotes(desc, rec.lineno)
            entries.append(IdentifierEntry(line=rec.lineno, key=key, description=desc))
            i += 1
        return i, entries

    def _parse_flags_block(self, i: int, block_indent: str) -> Tuple[Node, int]:
        """`flags DomainName WidthType` -- width is REQUIRED here, unlike
        identifier's optional §8.3 width (flags has no non-indexed form
        to opt out into; the whole point of the construct is a real,
        addressable bit width)."""
        rec = self.recs[i]
        tokens = rec.content.split()
        if len(tokens) != 3:
            raise GDDLParseError(
                f"expected 'flags Name WidthType' (width one of "
                f"u8/u16/u32/u64), got: {rec.content!r}", rec.lineno)
        width = tokens[2]
        if width not in _FLAGS_WIDTHS:
            raise GDDLParseError(
                f"invalid width {width!r} for flags domain '{tokens[1]}' -- "
                "must be one of u8/u16/u32/u64", rec.lineno)
        node = FlagsBlock(line=rec.lineno, name=tokens[1], width=width)
        i += 1
        self._enter_scope()
        i2, entries = self._parse_flags_entries(i, block_indent)
        node.entries = entries
        return node, i2

    def _parse_flags_entries(self, i: int, parent_indent: str) -> Tuple[int, List[FlagsEntry]]:
        """Genuinely new grammar, not a copy of identifier entry parsing:
        a flags member's value is one of three shapes -- bare (no '=',
        auto-assigned the next unclaimed bit), '= bN' (explicit bit
        position N), or '= 0' (the zero/none sentinel; any other literal
        number is rejected here, not deferred -- "a flags member's value
        is a bit or zero, no exceptions" is a closed grammar, the same
        kind of shape check identifier's own width whitelist already
        makes at this phase). What ISN'T decided here, deliberately left
        for registration (phase 4): which bit an 'auto' member actually
        gets, whether two members' claims collide, and whether the
        domain's real member count fits its declared width -- all of
        those need to see every entry in the domain together, which a
        single-entry parse never has."""
        entries: List[FlagsEntry] = []
        if i >= self.n:
            return i, entries
        nxt = self.recs[i]
        if len(nxt.indent) <= len(parent_indent):
            return i, entries

        entry_indent = None
        while i < self.n:
            rec = self.recs[i]
            if len(rec.indent) <= len(parent_indent):
                break
            self._check_scope_char(rec)
            if entry_indent is None:
                entry_indent = rec.indent
            elif rec.indent != entry_indent:
                raise GDDLParseError(
                    "inconsistent indentation in flags block", rec.lineno)

            eq = split_top_level_equals(rec.content)
            if eq is None:
                name = rec.content.strip()
                _require_field_name(name, rec.lineno)
                entries.append(FlagsEntry(line=rec.lineno, name=name, kind="auto"))
            else:
                name, value_text = eq
                _require_field_name(name, rec.lineno)
                m = _BIT_LITERAL_RE.match(value_text)
                if m:
                    entries.append(FlagsEntry(
                        line=rec.lineno, name=name, kind="bit",
                        explicit_bit=int(m.group(1))))
                elif value_text == "0":
                    entries.append(FlagsEntry(
                        line=rec.lineno, name=name, kind="number", explicit_number=0))
                else:
                    raise GDDLParseError(
                        f"invalid flags member value {value_text!r} for "
                        f"'{name}' -- a flags member's value must be omitted "
                        "(auto-assigned the next unclaimed bit), a bit "
                        "literal 'bN' (claims bit N), or the literal '0' "
                        "(the zero/none sentinel) -- no other values are "
                        "legal for a flags member", rec.lineno)
            i += 1
        return i, entries

    def _parse_define_block(self, i: int, block_indent: str) -> Tuple[Node, int]:
        rec = self.recs[i]
        tokens = rec.content.split()
        if len(tokens) < 2:
            raise GDDLParseError(
                f"expected 'define Name', got: {rec.content!r}", rec.lineno)
        if len(tokens) > 2 or "=" in rec.content:
            raise GDDLParseError(
                "'define' blocks cannot inherit (no 'define X = Y' form); "
                f"got: {rec.content!r}", rec.lineno)
        node = DefineBlock(line=rec.lineno, name=tokens[1])
        i += 1
        self._enter_scope()
        i2, fields = self._parse_define_fields(i, block_indent)
        node.fields = fields
        return node, i2

    def _parse_define_fields(self, i: int, parent_indent: str) -> Tuple[int, List[FieldDef]]:
        fields: List[FieldDef] = []
        if i >= self.n:
            return i, fields
        nxt = self.recs[i]
        if len(nxt.indent) <= len(parent_indent):
            return i, fields

        field_indent = None
        while i < self.n:
            rec = self.recs[i]
            if len(rec.indent) <= len(parent_indent):
                break
            self._check_scope_char(rec)
            if field_indent is None:
                field_indent = rec.indent
            elif rec.indent != field_indent:
                raise GDDLParseError(
                    "inconsistent indentation in define block", rec.lineno)

            eq = split_top_level_equals(rec.content)
            if eq is None:
                raise GDDLParseError(
                    f"expected 'field = Type' in define block, got: {rec.content!r}",
                    rec.lineno)
            name, type_tokens = eq
            fields.append(FieldDef(line=rec.lineno, name=name, type_tokens=type_tokens))
            i += 1
        return i, fields

    def _parse_instance_decl(self, i: int, block_indent: str) -> Tuple[Node, int]:
        rec = self.recs[i]
        tokens = rec.content.split()
        if len(tokens) < 2:
            raise GDDLParseError(
                f"expected 'Type InstanceName [= Source] [delete]', got: "
                f"{rec.content!r}", rec.lineno)

        type_name, instance_name = tokens[0], tokens[1]
        rest = tokens[2:]
        source_name = None
        is_delete = False

        if rest and rest[0] == "=":
            if len(rest) < 2:
                raise GDDLParseError("expected source instance name after '='", rec.lineno)
            source_name = rest[1]
            rest = rest[2:]

        if rest:
            if rest == ["delete"]:
                is_delete = True
            else:
                raise GDDLParseError(
                    f"unexpected trailing tokens on instance declaration: {rest}",
                    rec.lineno)

        node = InstanceDecl(
            line=rec.lineno, type_name=type_name, instance_name=instance_name,
            source_name=source_name, is_delete=is_delete,
        )
        i += 1
        self._enter_scope()
        i2, body = self._parse_statement_block(i, block_indent)
        node.body = body
        return node, i2

    def _parse_pool_decl(self, i: int, block_indent: str) -> Tuple[Node, int]:
        """`pool TypeName PoolName : N` (§22) -- a fixed-size reservation
        of N uninitialized TypeName slots, never a field-by-field
        instance. Deliberately parsed as a single fixed shape (like
        flags' 'flags Name WidthType' width check above) rather than
        deferred to registry the way array dimensions are: this is the
        whole top-level statement's own grammar, not raw text sitting
        inside some other field's type_tokens.

        No body follows -- there is nothing to initialize, so any
        indented content directly under this line is a parse error, not
        silently accepted or silently dropped."""
        rec = self.recs[i]
        tokens = rec.content.split()
        if len(tokens) != 5 or tokens[3] != ":":
            raise GDDLParseError(
                "expected 'pool TypeName PoolName : N' (a fixed-size pool "
                f"of N uninitialized instances), got: {rec.content!r}", rec.lineno)
        type_name, pool_name, count_text = tokens[1], tokens[2], tokens[4]
        if not _POOL_COUNT_RE.match(count_text):
            raise GDDLParseError(
                f"pool count must be a plain non-negative integer literal, "
                f"got {count_text!r}", rec.lineno)
        count = int(count_text)
        node = PoolDecl(line=rec.lineno, type_name=type_name, pool_name=pool_name, count=count)
        i += 1
        self._enter_scope()
        i2, body = self._parse_statement_block(i, block_indent)
        if body:
            raise GDDLParseError(
                f"'pool {type_name} {pool_name} : {count}' cannot have an "
                "indented body -- pool slots are always uninitialized, "
                "filled in by the game at runtime, never by the compiler",
                rec.lineno)
        return node, i2

    def _parse_statement_block(self, i: int, parent_indent: str) -> Tuple[int, List[Node]]:
        stmts: List[Node] = []
        if i >= self.n:
            return i, stmts
        nxt = self.recs[i]
        if len(nxt.indent) <= len(parent_indent):
            return i, stmts

        stmt_indent = None
        while i < self.n:
            rec = self.recs[i]
            if len(rec.indent) <= len(parent_indent):
                break
            self._check_scope_char(rec)
            if stmt_indent is None:
                stmt_indent = rec.indent
            elif rec.indent != stmt_indent:
                if len(rec.indent) < len(stmt_indent):
                    break
                raise GDDLParseError(
                    "inconsistent indentation within statement block "
                    f"(expected {stmt_indent!r}, got {rec.indent!r})", rec.lineno)

            node, i = self._parse_statement(i, stmt_indent)
            stmts.append(node)

        return i, stmts

    def _parse_statement(self, i: int, stmt_indent: str) -> Tuple[Node, int]:
        rec = self.recs[i]
        tag = _classify_statement(rec.lineno, rec.content)
        i += 1

        if tag[0] == "assign":
            _, field_name, rhs, index = tag
            node = AssignStmt(line=rec.lineno, field_name=field_name, rhs=rhs, index=index)
            i2, children = self._parse_statement_block(i, stmt_indent)
            node.children = children
            return node, i2

        if tag[0] == "op":
            _, field_name, op, rhs, index = tag
            node = OpStmt(line=rec.lineno, field_name=field_name, op=op, rhs=rhs, index=index)
            i2, children = self._parse_statement_block(i, stmt_indent)
            if children:
                raise GDDLParseError(
                    "unexpected indented block under an operator statement "
                    f"('{field_name} {op} {rhs}')", self.recs[i].lineno)
            return node, i2

        if tag[0] == "bare":
            _, field_name = tag
            node = BareFieldStmt(line=rec.lineno, field_name=field_name)
            i2, children = self._parse_statement_block(i, stmt_indent)
            if not children:
                # §12.1: syntactically valid (enters scope, touches
                # nothing), but flagged -- the bare-field form signals
                # sub-fields follow. Scope: does NOT apply to an empty
                # top-level instance body (ordinary pure copy).
                self.warnings.append(CompileWarning(
                    phase=3,
                    check="empty_bare_field",
                    line=rec.lineno,
                    message=(
                        f"bare field '{field_name}' (modify-only form) has no "
                        "indented sub-statements -- this enters the field's "
                        "scope but changes nothing in it, which is valid but "
                        "usually unintentional (e.g. every statement under it "
                        "got commented out)"
                    ),
                ))
            node.children = children
            return node, i2

        return RawStmt(line=rec.lineno, text=rec.content), i


def _strip_quotes(s: str, lineno: int) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == '"' and s[-1] == '"':
        try:
            return _unescape_string_content(s[1:-1])
        except _StringEscapeError as e:
            raise GDDLParseError(e.message, lineno)
    raise GDDLParseError(f"expected quoted string, got: {s!r}", lineno)


def parse_source(source: str) -> Program:
    pairs = preprocess(source)
    recs = _build_line_records(pairs)
    return Parser(recs).parse()


def parse_file(path: str) -> Program:
    with open(path, "r", encoding="utf-8") as f:
        return parse_source(f.read())
