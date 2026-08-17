# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Phase 9 (export): C++ header exporter, first pass.

Deliberately minimal scope, per the "start small, validate against
reality before generalizing" approach used for every other phase:
- Single header file: every enum, struct, instance, and registry for
  the whole compiled project, in one .h, in dependency order.
- Target: C++17 (per spec §13, for inline constexpr's cross-TU safety).
- Only fully-resolved, non-delete instances are exported (§6.6) --
  anything in resolver.errors/blocked/still-delete never appears.
- Every type gets a registry, unconditionally, even with zero exported
  instances -- uniform codegen, no conditional-emission special case.
- Registry table sorted by instance_id (§13.2), hand-written constexpr
  binary search (no <algorithm>, not constexpr-guaranteed until C++20).

Naming conventions (from spec §13.2, extended per this session's
conventions message):
  - Everything under `namespace GDDL { }`.
  - Structs: GDDL::TypeName
  - Enums:   GDDL::DomainName (enum class ... : uint64_t)
  - Instances:  GDDL::TypeName_Instances::InstanceName
  - Registries: GDDL::TypeName_Registry::{Table, Find(uint64_t), Find(string_view)}

NOT yet handled (explicitly out of scope for this first pass, per the
"minimal starting scope" instruction -- revisit once this is validated):
  - `indexed` mode (§8.3) -- only logical-ID-style export, the default.
  - Multi-file output, metadata manifest (§13.5).

RESOLVED since the first pass: instance stable IDs are now computed and
collision-checked at registration (phase 4, Registry.__init__), for
every declared instance regardless of delete-marked status or eventual
resolve/export success -- sharing the exact same collision table
identifier logical IDs use. This exporter now reads the precomputed ID
via reg.get_instance_id(type_name, instance_name) rather than
recomputing it independently.

Indexed mode (§8.3 language, §13.6 export) is implemented: a domain that
declares a width gets a companion `Domain_Indexed` enum (0-based,
declaration order) ONLY IF something actually uses '@Domain' somewhere
in the compiled defines -- see _domains_used_indexed. A field typed
'@Domain' gets 'Domain_Indexed' as its C++ struct member type, not
'Domain'. Explicitly NOT implemented (per this task's own scoping, not
an oversight): the planned force-emit flag (§13.6) that would emit the
companion enum for every width-declared domain regardless of whether
'@' is used anywhere -- that's a separate, later task.

Code style (§13.0): every block-opening brace (functions, if/while/for,
struct, namespace, enum class) goes on its own line, except in an
if/else-if/else chain: only the very first `if` gets its opening brace
on its own new line. Every subsequent `else if (condition)` or `else`
cuddles EVERYTHING onto one line -- the preceding block's closing brace,
the `else`/`else if` keyword, the condition if there is one, and that
branch's own opening brace, all together (e.g. `} else if (cond) {`,
`} else {`). This governs statement/declaration blocks only --
aggregate-initializer braces (instance values like `{ 100, 50 }`,
`Entry{ ... }` table rows) are expression-level literals, not
block-opening constructs, and are deliberately left as compact
single-line initializers rather than reformatted under this rule.
"""

from .resolve import StructValue, IdentifierRef
from .registry import fnv1a_64, _try_parse_array_type
from .validate import check_and_report


_CPP_INT_TYPES = {
    "u8": "uint8_t", "u16": "uint16_t", "u32": "uint32_t", "u64": "uint64_t",
    "i8": "int8_t", "i16": "int16_t", "i32": "int32_t", "i64": "int64_t",
}
_CPP_FLOAT_TYPES = {"f32": "float", "f64": "double"}


def _string_n(type_tokens: str):
    """Returns N if type_tokens is 'string N', else None."""
    t = type_tokens.strip()
    if t.startswith("string"):
        rest = t[len("string"):].strip()
        if rest.isdigit():
            return int(rest)
    return None


def _align_columns(rows):
    """Column-aligns a block's worth of rows for readability, requested
    directly from real usage (struct fields, enum entries): every column
    except the last is padded to the width of its own longest entry
    *within this call*, never globally across the whole file, so one
    type's fields don't get dragged wide by some unrelated type's long
    field name elsewhere in the output. `rows` is a list of tuples,
    each tuple one row's already-formatted column pieces; the last
    column is deliberately never padded, so a row with nothing in its
    final column (no trailing comment, say) doesn't leave invisible
    trailing whitespace on that line."""
    if not rows:
        return []
    n_cols = len(rows[0])
    widths = [0] * (n_cols - 1)
    for row in rows:
        for i in range(n_cols - 1):
            widths[i] = max(widths[i], len(row[i]))
    result = []
    for row in rows:
        parts = [row[i].ljust(widths[i]) for i in range(n_cols - 1)]
        parts.append(row[-1])
        result.append(" ".join(parts))
    return result


def _cpp_field_type(type_tokens: str, reg):
    """Maps a declared GDDL field type to a C++ type string, per §13.1
    (and §13.6 for the '@Domain' indexed-mode case)."""
    t = type_tokens.strip()
    if t.startswith("@"):
        domain = t[1:].strip()
        if domain not in reg.identifiers or domain not in reg.identifier_widths:
            # Should already be caught as a phase 4 error
            # (indexed_wrong_type / indexed_no_width) before export ever
            # runs -- this is a defensive backstop, not the primary
            # detection mechanism, same pattern used elsewhere in this
            # project (e.g. phase 5's checks staying as backstops in
            # phase 6). Never silently emit meaningless C++ for this.
            raise ValueError(
                f"'@{domain}' is not a valid indexed-domain field type -- "
                f"'{domain}' either isn't a known identifier domain or "
                "declared no indexed width (§8.3). This should already have "
                "been caught as a phase 4 error.")
        return f"{domain}_Indexed"
    if t in _CPP_INT_TYPES:
        return _CPP_INT_TYPES[t]
    if t in _CPP_FLOAT_TYPES:
        return _CPP_FLOAT_TYPES[t]
    n = _string_n(t)
    if n is not None:
        return f"char[{n}]"  # handled specially at declaration site
    if t in reg.defines:
        return t  # nested struct, same name (composition, §5.2)
    if t in reg.identifiers:
        return t  # enum class, same name as the domain
    if t in reg.flags:
        # Settled design (confirmed via real compiled testing, see
        # HANDOFF.md): the field itself is the raw width type, NOT a
        # named/wrapped type -- unlike identifier's enum class, a flags
        # domain has no type of its own in the emitted C++ at all, only
        # a `namespace Domain { constexpr WIDTH member = ...; }` of bit
        # constants (see _render_flags_namespace).
        return _CPP_INT_TYPES[reg.flags_widths[t]]
    array_info = _try_parse_array_type(t)
    if array_info is not None:
        return _cpp_array_field_type(array_info, reg)
    raise ValueError(f"unrecognized field type {type_tokens!r} -- can't export")


def _cpp_array_field_type(array_info, reg):
    """Arrays design: 'ElementType : dim1 : dim2 : ...' -> nested
    std::array, built from the innermost dimension outward
    (dims=[2, 3] -> std::array<std::array<int32_t, 3>, 2>, matching
    the value shape '{a,b,c},{d,e,f}': two outer groups of three).
    A 'string N' element becomes std::array<char, N> at the innermost
    level, not the raw C-array 'char[N]' a plain (non-array) string
    field gets -- a raw array can't be a std::array's own element type,
    only another aggregate class can."""
    n = _string_n(array_info.element_type)
    if n is not None:
        elem_cpp = f"std::array<char, {n}>"
    else:
        elem_cpp = _cpp_field_type(array_info.element_type, reg)
    t = elem_cpp
    for dim in reversed(array_info.dims):
        t = f"std::array<{t}, {dim}>"
    return t


def _cpp_type_is_aggregate(type_tokens: str, reg) -> bool:
    """True if _cpp_field_type(type_tokens, reg) is itself a C++
    aggregate class (needs the well-known std::array double-brace
    treatment -- {{ ... }}, not { ... } -- when wrapped in an OUTER
    std::array<T, N>, since std::array wraps a raw C array internally
    and a single brace layer only initializes that ONE member).
    Every C++ type this exporter produces for a non-array field
    (int/float, an enum class, a flags width's plain int) is NOT an
    aggregate in this sense; only an array-typed field's std::array<...>
    is. Confirmed against a real MSVC compile before this distinction
    was added -- see HANDOFF.md."""
    return _try_parse_array_type(type_tokens.strip()) is not None


def _cpp_array_value_literal(value, dims, element_type, reg) -> str:
    """Renders a (possibly nested) array VALUE as a C++ aggregate
    initializer. Mirrors _cpp_array_field_type's own type-side logic:
    a level needs double bracing whenever its own contained type is
    itself an aggregate -- true for every non-innermost dimension
    (the contained type is another std::array), and true at the
    innermost dimension too when the element type is 'string N' (the
    contained type is std::array<char, N>, still an aggregate); single
    bracing suffices only when the innermost level holds a genuinely
    primitive C++ type (a plain number). Verified against a real MSVC
    compile for the 1D/2D/3D-numeric and 1D-string cases before this
    was written -- see HANDOFF.md."""
    is_leaf_level = len(dims) == 1
    n = _string_n(element_type)
    contained_is_aggregate = (not is_leaf_level) or (n is not None)

    if is_leaf_level:
        if n is not None:
            parts = [f"{{ {_cpp_string_literal(v)} }}" for v in value]
        else:
            parts = [_cpp_value_literal(v, element_type, reg) for v in value]
    else:
        parts = [_cpp_array_value_literal(v, dims[1:], element_type, reg) for v in value]

    inner = ", ".join(parts)
    if contained_is_aggregate:
        return "{{ " + inner + " }}"
    return "{ " + inner + " }"


def _render_flags_namespace(domain_name, block, reg):
    """Renders one flags domain as `namespace Domain { constexpr WIDTH
    member = ...; }` (settled design, confirmed via real compiled
    testing -- see HANDOFF.md's "C++ export shape" entry for the three
    alternatives tried and why this one won: unlike `enum class`, a
    plain namespace of constexpr values gives real bitwise operators
    for free while still scoping members the same way `enum class`
    would, avoiding the cross-domain name collision a plain unscoped
    `enum` has). Shared between generate_header and generate_split --
    the namespace's own content never differs between single-header and
    split modes, only where the surrounding lines list ends up (the
    header in both cases, since C++ has no way to split a namespace's
    constexpr definitions from their values the way a .cpp/.h pair
    splits ordinary function bodies).

    A member with no registered value (registry.py skipped it -- an
    invalid or losing-duplicate bit claim, already reported as its own
    phase-4 error) is silently omitted here, not emitted with a
    fabricated value -- the build is already blocked by that error
    regardless of what this function does."""
    cpp_width = _CPP_INT_TYPES[reg.flags_widths[domain_name]]
    lines = [f"namespace {domain_name}", "{"]
    member_rows = []
    for entry in block.entries:
        value = reg.get_flags_value(domain_name, entry.name)
        if value is None:
            continue
        bit = reg.get_flags_bit(domain_name, entry.name)
        rhs = f"1ULL << {bit}" if bit is not None else "0"
        member_rows.append((f"constexpr {cpp_width}", entry.name, f"= {rhs};"))
    for row in _align_columns(member_rows):
        lines.append(f"    {row}")
    lines.append("}")
    lines.append("")
    return lines


def _domains_used_indexed(reg):
    """Every domain actually referenced via a valid '@Domain' field
    somewhere in the compiled defines -- this is a structural property
    of the struct declarations themselves (a field's C++ type demands
    the enum exist for the struct to compile at all), independent of
    what any specific instance's data holds. Only VALID usages count;
    a misuse (already a hard phase-4 error) doesn't trigger enum
    emission for something that was never a legitimate reference."""
    used = set()
    for d in reg.defines.values():
        for f in d.fields:
            t = f.type_tokens.strip()
            if t.startswith("@"):
                domain = t[1:].strip()
                if domain in reg.identifier_widths:
                    used.add(domain)
    return used


def _flatten_leaves(type_name, reg, prefix=""):
    """§13.1: full flattening through composition, all the way down --
    not just top-level fields. Returns an ordered list of
    (path, type_tokens) for every LEAF field of `type_name`, recursing
    into nested struct-typed fields. Path segments join with '_'
    (e.g. 'object_something1' for Item.object.something1) -- a nested
    struct-typed field never becomes its own array; only its own leaves
    do, all the way down."""
    d = reg.defines[type_name]
    leaves = []
    for f in d.fields:
        path = f"{prefix}{f.name}"
        t = f.type_tokens.strip()
        if t in reg.defines:
            leaves.extend(_flatten_leaves(t, reg, prefix=f"{path}_"))
        else:
            leaves.append((path, f.type_tokens))
    return leaves


def _flatten_value(value, type_name, reg):
    """Matching walk over an actual resolved StructValue -- returns an
    ordered list of leaf values in EXACTLY the same order _flatten_leaves
    produces paths, so the two can be zipped by position."""
    d = reg.defines[type_name]
    out = []
    for f in d.fields:
        t = f.type_tokens.strip()
        if t in reg.defines:
            out.extend(_flatten_value(value.fields[f.name], t, reg))
        else:
            out.append(value.fields[f.name])
    return out


# ---------------------------------------------------------------------
# §17.4 schema-hash / record-size computation. Lives HERE, not in
# export_binary.py, specifically so export_cpp.py's own §17.5
# compile-time table can call these functions directly rather than
# import them from export_binary.py -- export_binary.py already
# imports composition-flattening from this module, so putting the
# computation here instead of there avoids a circular import
# (export_cpp -> export_binary -> export_cpp) while keeping ONE
# implementation that both the .gddldata.bin writer and the C++
# compile-time table call, never two that merely happen to agree.
# export_binary.py imports these back from here -- see its own
# imports -- rather than defining a second copy.
#
# This is the exact failure mode §17.4's own spec text names directly:
# "a bug in the hash computation itself... two pieces of code that are
# each supposed to compute 'this type's schema hash' diverge even
# slightly." Moving this here instead of duplicating it in export_cpp.py
# is what makes that structurally impossible rather than merely unlikely.
# ---------------------------------------------------------------------

_BINARY_INT_TYPES = {
    "u8": ("B", 1), "i8": ("b", 1),
    "u16": ("H", 2), "i16": ("h", 2),
    "u32": ("I", 4), "i32": ("i", 4),
    "u64": ("Q", 8), "i64": ("q", 8),
}
_BINARY_FLOAT_TYPES = {"f32": ("f", 4), "f64": ("d", 8)}


class SchemaComputationError(Exception):
    pass


def _leaf_binary_kind(type_tokens: str, reg):
    """Classifies one flattened leaf's type for packing/sizing purposes
    (§17.3/§17.4). Returns one of:
      ("scalar", struct_fmt_char, width_bytes)
      ("string", None, n)
      ("logical_id", "Q", 8)                 -- plain Domain, no '@'
      ("indexed", struct_fmt_char, width)    -- '@Domain'

    Mirrors THIS module's own _cpp_field_type's '@' vs plain distinction
    (§8.3's default-is-always-logical-ID rule) -- deliberately NOT
    export_z80.py's _leaf_size_bytes model, which erases that
    distinction entirely (correct for Z80, which has no logical-ID form
    at all; wrong for this target, which must preserve it)."""
    t = type_tokens.strip()

    if t.startswith("@"):
        domain = t[1:].strip()
        if domain not in reg.identifiers or domain not in reg.identifier_widths:
            raise SchemaComputationError(
                f"'@{domain}' is not a valid indexed-domain field type -- "
                f"'{domain}' either isn't a known identifier domain or "
                "declared no indexed width (§8.3). Should already have "
                "been caught as a phase 4 error before export ever ran.")
        width_type = reg.identifier_widths[domain]
        fmt, width = _BINARY_INT_TYPES[width_type]
        return ("indexed", fmt, width)

    if t in reg.identifiers:
        # Plain Domain, no '@' -- always the full 8-byte logical ID,
        # never inferred, never narrowed (§8.3).
        return ("logical_id", "Q", 8)

    if t in reg.flags:
        # A flags-typed field is a plain unsigned integer of its
        # declared width -- no hash-vs-index duality to preserve here,
        # flags never had one (unlike identifier's plain-vs-'@' split
        # just above). Packs exactly like an ordinary scalar u8/u16/
        # u32/u64 field of the same width.
        width_type = reg.flags_widths[t]
        fmt, width = _BINARY_INT_TYPES[width_type]
        return ("scalar", fmt, width)

    if t in _BINARY_INT_TYPES:
        fmt, width = _BINARY_INT_TYPES[t]
        return ("scalar", fmt, width)
    if t in _BINARY_FLOAT_TYPES:
        fmt, width = _BINARY_FLOAT_TYPES[t]
        return ("scalar", fmt, width)

    n = _string_n(t)
    if n is not None:
        return ("string", None, n)

    array_info = _try_parse_array_type(t)
    if array_info is not None:
        # Arrays design, first-pass scope: scalar and string elements
        # only (already enforced at registration -- struct/identifier/
        # flags elements never reach here). Total width is simply
        # element_width * total_element_count -- row-major, contiguous,
        # no padding, exactly the "match how C++ does this" layout the
        # design calls for (confirmed against a real MSVC pointer-
        # arithmetic stride check before this was written -- see
        # HANDOFF.md), which naturally falls out of plain concatenation.
        elem_kind, _elem_fmt, elem_width = _leaf_binary_kind(array_info.element_type, reg)
        if elem_kind not in ("scalar", "string"):
            raise SchemaComputationError(
                f"array element type {array_info.element_type!r} isn't "
                "supported for binary/schema export (scalar or string N "
                "only -- should already have been caught as a phase 4 "
                "error before export ever ran)")
        total_count = 1
        for d in array_info.dims:
            total_count *= d
        return ("array", array_info, elem_width * total_count)

    raise SchemaComputationError(
        f"binary/schema export doesn't support field type {type_tokens!r} -- "
        "scalar u8/u16/u32/u64/i8/i16/i32/i64/f32/f64, string N, "
        "identifier-typed (plain or @Domain), array, and composition only")


def leaf_binary_width(type_tokens: str, reg) -> int:
    """Byte width of one flattened leaf. Used by record_size -- an
    INDEPENDENT code path from schema_hash, per §17.4."""
    _kind, _fmt, width = _leaf_binary_kind(type_tokens, reg)
    return width


def canonical_schema_string(leaves) -> str:
    """The exact canonical serialization schema_hash is computed over
    (§17.4). For each flattened leaf, in _flatten_leaves order:
    "{path}\\x1f{type.strip()}", joined with "\\x1e" between leaves.
    \\x1f/\\x1e chosen specifically because no GDDL identifier or type
    token can ever contain them, making the join unambiguous by
    construction. export_binary.py's own module docstring's "SCHEMA
    HASH" section describes this same definition in prose -- this
    function and that docstring must never drift from each other."""
    parts = [f"{path}\x1f{type_tokens.strip()}" for path, type_tokens in leaves]
    return "\x1e".join(parts)


def compute_schema_hash(leaves) -> int:
    """FNV-1a-64 over the canonical schema string (§17.4). Calls
    registry.fnv1a_64 -- the one hash implementation in this codebase --
    never a second implementation."""
    return fnv1a_64(canonical_schema_string(leaves).encode("utf-8"))


def compute_record_size(leaves, reg) -> int:
    """Sum of flattened leaf byte widths -- computed by a path that
    shares NO intermediate value with compute_schema_hash (§17.4)."""
    return sum(leaf_binary_width(tokens, reg) for _path, tokens in leaves)


def _cpp_hex_u64_literal(value: int) -> str:
    """Renders a 64-bit unsigned value as a C++ hex literal with the
    ULL suffix -- readable in generated output (matches the C++
    exporter's existing convention for logical IDs elsewhere in this
    module), not a bare decimal that's unreadable for a hash."""
    return f"0x{value:016x}ULL"


def render_schema_table(reg) -> list:
    """§17.5: the C++ compile-time (type_name, schema_hash, record_size)
    table, for every type in the schema -- generated by calling
    compute_schema_hash/compute_record_size DIRECTLY, the exact same
    functions export_binary.py's .gddldata.bin writer calls for the
    same computation, so the two literally cannot drift apart: this is
    not "two implementations that happen to agree today," it is one
    implementation called from two call sites.

    Returns a list of already-formatted C++ lines, meant to be spliced
    into the GDDL namespace body alongside the rest of a generated
    header -- never its own output file (there's no reason to invent a
    second output artifact for eight bytes and a name per type), and
    always emitted as `inline constexpr` directly in the header
    regardless of single-header vs. split mode, the same convention
    already used for domain enums and other small compile-time metadata
    that split mode still keeps header-resident (no ODR-splitting
    reasoning applies to a small, fixed-size, purely compile-time table).

    Order: _topo_sort_defines' own order (nested types before whatever
    composes them) -- the same ordering every other part of this
    exporter already uses, not a separately-invented order that could
    drift from it."""
    define_order = _topo_sort_defines(reg)

    lines = []
    lines.append("// §17.5: compile-time schema table, for comparison against")
    lines.append("// whatever a loaded .gddldata.bin/.gddlmeta.json pair claims at")
    lines.append("// runtime (§17.6). schema_hash/record_size here are computed by")
    lines.append("// the EXACT SAME functions the .gddldata.bin exporter calls --")
    lines.append("// see export_cpp.py's compute_schema_hash/compute_record_size,")
    lines.append("// shared with export_binary.py, never a second implementation.")
    lines.append("struct SchemaEntry")
    lines.append("{")
    lines.append("    std::string_view type_name;")
    lines.append("    uint64_t schema_hash;")
    lines.append("    uint32_t record_size;")
    lines.append("};")
    lines.append("")
    lines.append(f"inline constexpr std::array<SchemaEntry, {len(define_order)}> SchemaTable =")
    lines.append("{")
    for type_name in define_order:
        leaves = _flatten_leaves(type_name, reg)
        schema_hash = compute_schema_hash(leaves)
        record_size = compute_record_size(leaves, reg)
        hash_lit = _cpp_hex_u64_literal(schema_hash)
        lines.append(f'    SchemaEntry{{ "{type_name}", {hash_lit}, {record_size} }},')
    lines.append("};")
    return lines


def _cpp_char_literal(b: int) -> str:
    """Render a single byte as a safe C++ char literal."""
    if b == 0:
        return "'\\0'"
    c = chr(b)
    if 32 <= b < 127 and c not in ("'", "\\"):
        return f"'{c}'"
    return f"'\\x{b:02x}'"


def emit_soa_type(lines, type_name, reg, resolver, is_last_type):
    """§13: Struct-of-Arrays projection for one type -- every leaf field
    (after full composition flattening, §13.1) gets its own flat array,
    string fields become one flat N*count byte array (§13.2), and a
    parallel lookup table (§13.4) mirrors the AoS registry's exact
    shape/style but returns a row INDEX rather than a pointer (there's
    no single struct object to point to in SoA). The not-found sentinel
    is static_cast<std::size_t>(-1) -- numerically identical to
    std::string::npos, and deliberately loud if misused unchecked as an
    index: an out-of-bounds crash or an ASan catch, not the silent
    one-past-the-end read a Table.size() sentinel would risk instead."""
    d = reg.defines[type_name]
    instances = export_instances_for_type(type_name, reg, resolver)
    leaves = _flatten_leaves(type_name, reg)
    count = len(instances)
    flat_per_instance = [_flatten_value(value, type_name, reg) for _name, value in instances]

    lines.append(f"namespace {type_name}_SoA")
    lines.append("{")
    for li, (path, type_tokens) in enumerate(leaves):
        n = _string_n(type_tokens)
        if n is not None:
            # §13.2: one flat byte array, N*count bytes total, each
            # instance's string in its own fixed N-byte slice.
            total = n * count
            combined = bytearray()
            for k in range(count):
                s = flat_per_instance[k][li]
                encoded = s.encode("utf-8")
                combined += encoded + b"\x00" * (n - len(encoded))
            if count == 0:
                lines.append(f"    inline constexpr std::array<char, 0> {path} = {{}};")
            else:
                byte_literals = ", ".join(_cpp_char_literal(b) for b in combined)
                lines.append(f"    inline constexpr std::array<char, {total}> {path} =")
                lines.append("    {")
                lines.append(f"        {byte_literals}")
                lines.append("    };")
        else:
            cpp_type = _cpp_field_type(type_tokens, reg)
            if count == 0:
                lines.append(f"    inline constexpr std::array<{cpp_type}, 0> {path} = {{}};")
            else:
                values = ", ".join(
                    _cpp_value_literal(flat_per_instance[k][li], type_tokens, reg)
                    for k in range(count)
                )
                # Arrays design: an array-typed leaf's cpp_type is itself
                # std::array<...>, an aggregate -- this outer per-field
                # SoA array then needs the same double-brace treatment
                # any std::array<AggregateType, N> does (confirmed against
                # a real MSVC compile, see HANDOFF.md). Every prior leaf
                # type this exporter ever produced (int/float, enum
                # class, a flags width's plain int) was NOT an aggregate,
                # so this is purely additive -- the existing single-brace
                # form is untouched for every non-array leaf.
                if _cpp_type_is_aggregate(type_tokens, reg):
                    lines.append(f"    inline constexpr std::array<{cpp_type}, {count}> {path} = {{{{ {values} }}}};")
                else:
                    lines.append(f"    inline constexpr std::array<{cpp_type}, {count}> {path} = {{ {values} }};")
        if li != len(leaves) - 1:
            lines.append("")  # between field-array decls; not after the last (registry follows)
    lines.append("}")
    lines.append("")  # always followed by this type's SoA registry namespace -- never a closer

    # parallel lookup table (§13.4): row index into the arrays above,
    # sorted by instance_id like the AoS registry, for the same
    # binary-search compatibility.
    entries = []
    for idx, (name, _value) in enumerate(instances):
        iid = reg.get_instance_id(type_name, name)
        entries.append((iid, name, idx))
    entries.sort(key=lambda e: e[0])

    lines.append(f"namespace {type_name}_SoA_Registry")
    lines.append("{")
    lines.append("    struct Entry")
    lines.append("    {")
    lines.append("        uint64_t instance_id;")
    lines.append("        std::string_view name;")
    lines.append("        std::size_t row;")
    lines.append("    };")
    lines.append("")

    if entries:
        lines.append(f"    inline constexpr std::array<Entry, {len(entries)}> Table =")
        lines.append("    {")
        for iid, name, row in entries:
            lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", {row} }},")
        lines.append("    };")
    else:
        lines.append("    inline constexpr std::array<Entry, 0> Table = {};")
    lines.append("")

    lines.append("    constexpr std::size_t Find(uint64_t instance_id)")
    lines.append("    {")
    lines.append("        std::size_t lo = 0, hi = Table.size();")
    lines.append("")
    lines.append("        while (lo < hi)")
    lines.append("        {")
    lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
    lines.append("")
    lines.append("            if (Table[mid].instance_id < instance_id)")
    lines.append("            {")
    lines.append("                lo = mid + 1;")
    lines.append("            } else {")
    lines.append("                hi = mid;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
    lines.append("        {")
    lines.append("            return Table[lo].row;")
    lines.append("        }")
    lines.append("")
    lines.append("        return static_cast<std::size_t>(-1);")
    lines.append("    }")
    lines.append("")

    lines.append("    constexpr std::size_t Find(std::string_view name)")
    lines.append("    {")
    lines.append("        for (const auto& entry : Table)")
    lines.append("        {")
    lines.append("            if (entry.name == name)")
    lines.append("            {")
    lines.append("                return entry.row;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        return static_cast<std::size_t>(-1);")
    lines.append("    }")
    lines.append(f"}} // namespace {type_name}_SoA_Registry")
    if not is_last_type:
        lines.append("")


def _topo_sort_defines(reg, roots=None):
    """Dependency order: nested types before whatever composes them.
    Simple DFS-based topological sort over 'define X has a field of
    type define Y' edges.

    roots=None (default, UNCHANGED from before this parameter existed):
    visits every define in reg.defines -- "every type in the schema."
    This is deliberately what every EXISTING caller wants: C++'s
    generate_header/generate_split have no subset-request concept at
    all (everything is always exported), and §17.5's schema table is
    explicitly "for every type in the schema" per spec text, not a
    per-request view.

    roots=[...] (new): visits ONLY those names and whatever they
    transitively compose, in the same dependency order -- for a
    genuinely per-request caller (export_68000.py's AoS struct
    emission) that must NOT pull in an unrelated type's struct just
    because it happens to sit elsewhere in the same registry. Fixes a
    real bug: requesting a subset of types from a file that also
    defines unrelated types used to fail outright, because the
    unrelated type's own domain/composition needs were never gathered
    for the request in the first place -- confirmed directly, not
    assumed, before this fix existed."""
    order = []
    visited = set()
    visiting = set()

    def visit(name):
        if name in visited:
            return
        if name in visiting:
            raise ValueError(f"circular define composition involving '{name}' "
                              "-- should be impossible (defines can't reference "
                              "each other's own types in a cycle without one "
                              "being declared after the other, but flagging "
                              "rather than silently mis-ordering)")
        visiting.add(name)
        d = reg.defines[name]
        for f in d.fields:
            t = f.type_tokens.strip()
            if t in reg.defines:
                visit(t)
        visiting.discard(name)
        visited.add(name)
        order.append(name)

    for name in (reg.defines if roots is None else roots):
        visit(name)
    return order


def _cpp_string_literal(s: str) -> str:
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _cpp_value_literal(value, type_tokens: str, reg) -> str:
    """Render a resolved field value as a C++ initializer expression."""
    t = type_tokens.strip()

    if isinstance(value, IdentifierRef):
        # The field's DECLARED type decides which enum to reference, not
        # just the value's own domain -- a value is always "member X of
        # domain Y" regardless of mode (phases 6-8 don't distinguish),
        # but an '@Domain'-typed field must render against the indexed
        # enum here, at the one place mode actually matters.
        if t.startswith("@"):
            return f"{value.domain}_Indexed::{value.key}"
        return f"{value.domain}::{value.key}"

    if isinstance(value, StructValue):
        d = reg.defines[t]
        parts = [_cpp_value_literal(value.fields[f.name], f.type_tokens, reg)
                 for f in d.fields]
        return t + "{ " + ", ".join(parts) + " }"

    if isinstance(value, list):
        array_info = _try_parse_array_type(t)
        if array_info is None:
            raise ValueError(
                f"array value {value!r} but declared type {type_tokens!r} "
                "isn't array-shaped -- can't export")
        return _cpp_array_value_literal(value, array_info.dims, array_info.element_type, reg)

    if isinstance(value, str):
        return _cpp_string_literal(value)

    if isinstance(value, bool):
        return "true" if value else "false"

    if isinstance(value, float):
        if t in ("f32",):
            return f"{value!r}f"
        return repr(value)

    if isinstance(value, int):
        # A flags-typed field's declared type is the domain name, not
        # "u64" -- resolve to its real width before deciding on a
        # suffix. Matters for real correctness, not just style: a bare
        # decimal literal at or above 2**63 (a legitimate u64-width
        # flags value, e.g. a claimed high bit) has no signed integer
        # type it fits in, which real compilers reject or truncate
        # without the ULL suffix forcing an unsigned type instead.
        if t in reg.flags:
            if reg.flags_widths[t] == "u64":
                return f"{value}ULL"
            return str(value)
        if t in ("u64",):
            return f"{value}ULL"
        if t in ("i64",):
            return f"{value}LL"
        return str(value)

    raise ValueError(f"can't render value {value!r} of declared type {type_tokens!r}")


def export_instances_for_type(type_name, reg, resolver):
    """Every non-delete instance of this exact type that fully resolved.
    (Instances that are errored/blocked never made it into resolver.cache
    at all; delete instances are excluded per §6.6 regardless of whether
    they resolved.)"""
    result = []
    for name, decl in reg.instances.items():
        if decl.type_name != type_name:
            continue
        if decl.is_delete:
            continue
        if name not in resolver.cache:
            continue
        result.append((name, resolver.cache[name]))
    return result


def generate_header(reg, resolver, guard_name="GDDL_GENERATED_H", layout="aos",
                    emit_all_domains: bool = False):
    """Blank-line placement is hand-placed at each call site below,
    matching the spec's worked reference example exactly -- deliberately
    NOT done via a generic "does this line end with a closing brace"
    text-pattern post-processing pass. That would be fragile: a line
    like `Table = {};` (an empty aggregate initializer) ends with the
    same characters as a real block-closing line, but isn't one, and a
    generic pattern-matcher can't tell the difference reliably. Since
    this function already knows structurally what each line IS, the
    correct blank line placement is baked in directly instead.

    `layout`: "aos" (default) or "soa" (§13). This is the ONLY place
    this choice exists -- there is no .gddl source syntax for it at all
    (§13.6). The "aos" branch below is byte-for-byte the same code that
    existed before SoA support was added -- verified as an explicit
    regression check, not just assumed, since this is a correctness
    requirement, not a nice-to-have."""
    if layout not in ("aos", "aos-linear", "soa"):
        raise ValueError(f"layout must be 'aos', 'aos-linear', or 'soa', got {layout!r}")

    lines = []
    lines.append(f"#ifndef {guard_name}")
    lines.append(f"#define {guard_name}")
    lines.append("")
    lines.append("// Auto-generated by the GDDL compiler. Do not edit by hand.")
    lines.append("")
    lines.append("#include <cstdint>")
    lines.append("#include <array>")
    lines.append("#include <string_view>")
    lines.append("")
    lines.append("namespace GDDL")
    lines.append("{")
    lines.append("")

    # ---- 1. identifier domains -> enum class ----
    indexed_domains_used = _domains_used_indexed(reg)
    for domain_name, block in reg.identifiers.items():
        lines.append(f"enum class {domain_name} : uint64_t")
        lines.append("{")
        entry_rows = []
        for entry in block.entries:
            lid = reg.get_logical_id(domain_name, entry.key)
            entry_rows.append((entry.key, f"= 0x{lid}ULL,", f"// {entry.description}"))
        for row in _align_columns(entry_rows):
            lines.append(f"    {row}")
        lines.append("};")
        lines.append("")  # always followed by another enum, or the first struct -- never a closer

        # §13.6 / §14.7: companion enum, only if this domain declared a
        # width AND (something actually uses '@Domain' in the compiled
        # defines OR --emit-all-domains is on). Off by default: a
        # companion is only emitted for a domain actually referenced via
        # '@', keeping silent about unused width declarations. On: emit
        # for every width-declared domain regardless of usage, for
        # hand-written C++ dispatch code that never stores a value from
        # the domain in any GDDL struct.
        if domain_name in reg.identifier_widths and (
                domain_name in indexed_domains_used or emit_all_domains):
            width = reg.identifier_widths[domain_name]
            cpp_width = _CPP_INT_TYPES[width]
            lines.append(f"enum class {domain_name}_Indexed : {cpp_width}")
            lines.append("{")
            indexed_rows = []
            for index, entry in enumerate(block.entries):  # 0-based, declaration order, §8.4
                indexed_rows.append((entry.key, f"= {index},", f"// {entry.description}"))
            for row in _align_columns(indexed_rows):
                lines.append(f"    {row}")
            lines.append("};")
            lines.append("")

    # ---- 1b. flags domains -> namespace { constexpr WIDTH member = ...; } ----
    for domain_name, block in reg.flags.items():
        lines.extend(_render_flags_namespace(domain_name, block, reg))

    # ---- 2. defines -> structs, in dependency order. AoS ONLY: SoA
    # fully flattens through composition (§13.1) all the way down, so no
    # struct is ever used as an array element type at any level in pure
    # SoA output -- every SoA array holds a scalar or an enum, never a
    # struct. Emitting struct definitions there was dead code (caught by
    # inspection, not by any test failing, since nothing in SoA mode
    # ever references them either). define_order itself is still needed
    # by BOTH layouts below (section 3 iterates it either way) -- only
    # the struct TEXT emission is AoS-only (aos or aos-linear; SoA
    # never needs the plain struct, aos-linear needs it since
    # std::array<T,N> requires T to be a defined type). ----
    define_order = _topo_sort_defines(reg)
    if layout in ("aos", "aos-linear"):
        for type_name in define_order:
            d = reg.defines[type_name]
            lines.append(f"struct {type_name}")
            lines.append("{")
            field_rows = []
            for f in d.fields:
                n = _string_n(f.type_tokens)
                if n is not None:
                    field_rows.append(("char", f"{f.name}[{n}];"))
                else:
                    cpp_type = _cpp_field_type(f.type_tokens, reg)
                    field_rows.append((cpp_type, f"{f.name};"))
            for row in _align_columns(field_rows):
                lines.append(f"    {row}")
            lines.append("};")
            lines.append("")  # always followed by another struct, or the first instances namespace

    # ---- 3. per-type instances + registry (AoS) OR field arrays +
    # parallel lookup (SoA) -- the only place layout actually matters ----
    for i, type_name in enumerate(define_order):
        is_last_type = (i == len(define_order) - 1)
        d = reg.defines[type_name]
        instances = export_instances_for_type(type_name, reg, resolver)

        if layout == "soa":
            emit_soa_type(lines, type_name, reg, resolver, is_last_type)
            continue

        if layout == "aos-linear":
            _emit_aos_linear_type(lines, type_name, d, instances, reg, is_last_type)
            continue

        # ---- AoS (default): byte-for-byte identical to the code that
        # existed before SoA support was added -- do not touch this
        # block without re-running the byte-exact regression check
        # against the spec's worked example. ----

        # instances namespace -- single-line initializers stay compact
        lines.append(f"namespace {type_name}_Instances")
        lines.append("{")
        for name, value in instances:
            parts = [_cpp_value_literal(value.fields[f.name], f.type_tokens, reg)
                      for f in d.fields]
            init = ", ".join(parts)
            lines.append(f"    inline constexpr {type_name} {name} = {{ {init} }};")
        lines.append("}")
        lines.append("")  # always followed by this type's own _Registry namespace -- never a closer

        # registry namespace
        entries = []
        for name, _value in instances:
            iid = reg.get_instance_id(type_name, name)
            entries.append((iid, name))
        entries.sort(key=lambda e: e[0])  # sorted by instance_id, §13.2

        lines.append(f"namespace {type_name}_Registry")
        lines.append("{")
        lines.append("    struct Entry")
        lines.append("    {")
        lines.append("        uint64_t instance_id;")
        lines.append("        std::string_view name;")
        lines.append(f"        const {type_name}* data;")
        lines.append("    };")
        lines.append("")  # always followed by the Table declaration -- never a closer

        if entries:
            # Multi-line initializer: own-line opening brace, per §13.0.
            lines.append(f"    inline constexpr std::array<Entry, {len(entries)}> Table =")
            lines.append("    {")
            for iid, name in entries:
                lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", "
                              f"&{type_name}_Instances::{name} }},")
            lines.append("    };")
        else:
            # Genuinely single-line (empty) initializer: stays compact.
            lines.append(f"    inline constexpr std::array<Entry, 0> Table = {{}};")
        lines.append("")  # always followed by Find(uint64_t) -- never a closer

        lines.append(f"    constexpr const {type_name}* Find(uint64_t instance_id)")
        lines.append("    {")
        lines.append("        std::size_t lo = 0, hi = Table.size();")
        lines.append("")  # blank line after variable-declaration group, before logic
        lines.append("        while (lo < hi)")
        lines.append("        {")
        lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
        lines.append("")  # blank line after variable-declaration group, before logic
        lines.append("            if (Table[mid].instance_id < instance_id)")
        lines.append("            {")
        lines.append("                lo = mid + 1;")
        # Only the first `if` gets its own-line brace; this `else`
        # cuddles everything onto one line (§13.0).
        lines.append("            } else {")
        lines.append("                hi = mid;")
        lines.append("            }")
        lines.append("        }")
        # The while-loop's closing brace is immediately followed by
        # another closing-brace-ending line ONLY if nothing else lies
        # between them -- here, the next line is a fresh `if`, so a
        # blank line follows, same as any closer not immediately
        # followed by another closer.
        lines.append("")
        lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
        lines.append("        {")
        lines.append("            return Table[lo].data;")
        lines.append("        }")
        lines.append("")  # this closer is followed by a plain statement, not another closer
        lines.append("        return nullptr;")
        lines.append("    }")
        lines.append("")  # always followed by Find(string_view) -- never a closer

        lines.append(f"    constexpr const {type_name}* Find(std::string_view name)")
        lines.append("    {")
        lines.append("        for (const auto& entry : Table)")
        lines.append("        {")
        lines.append("            if (entry.name == name)")
        lines.append("            {")
        lines.append("                return entry.data;")
        lines.append("            }")
        lines.append("        }")
        lines.append("")  # for-loop's closer followed by a plain statement, not another closer
        lines.append("        return nullptr;")
        lines.append("    }")
        # Find(string_view)'s closing brace IS immediately followed by
        # another closing-brace-ending line (this namespace's own
        # closer) -- no blank line between stacked closers.
        lines.append(f"}} // namespace {type_name}_Registry")
        if not is_last_type:
            # Followed by the next type's _Instances namespace -- not a
            # closer, so a blank line is needed. (The LAST type's
            # registry-close is immediately followed by the closing
            # `} // namespace GDDL` -- another closer -- so no blank
            # line there; see below.)
            lines.append("")

    # `} // namespace GDDL` immediately follows the last type's
    # `} // namespace TypeName_Registry` (or `_SoA_Registry`) -- both
    # closers, stacked, no blank line between them.

    # §17.5: compile-time schema table, always emitted (independent of
    # AoS/SoA -- it's about each type's declared field list, not how
    # instances happen to be stored). Follows the last registry's
    # closing brace, so IS preceded by a blank line (its own opening
    # `struct SchemaEntry` line is not a closer).
    lines.append("")
    lines.extend(render_schema_table(reg))
    lines.append("")

    lines.append("} // namespace GDDL")
    lines.append("")  # followed by #endif, not a closer
    lines.append(f"#endif // {guard_name}")
    lines.append("")
    return "\n".join(lines)


def _emit_aos_linear_type(lines, type_name, d, instances, reg, is_last_type):
    """§13.7 AoS-linear layout, single-header mode: instances stored
    contiguously in one `std::array<T, N> All`, not as separate named
    globals plus a pointer-holding Entry registry.

    KEY IMPLEMENTATION DETAIL -- double-brace initializer is REQUIRED,
    not optional: `std::array<T, N>` wraps a raw C array internally,
    and the outer `{` opens the `std::array` itself while the inner
    `{{` opens the C array it contains. Using a single `{` gives "too
    many initializers" on g++17 even with -Wall (confirmed directly by
    attempting it -- see HANDOFF.md). This is a known subtlety with
    `std::array` aggregate initialization that's easy to get wrong on
    first pass.

    Find() returns `const T*` (= `&All[i]`), NOT an index -- this
    preserves the existing AoS signature exactly. SoA has no choice
    (there's no single struct left to point at after full flattening);
    aos-linear still has real T records in the array, so there's no
    reason to break calling code that was already working against
    regular AoS. Confirmed in the spec: §13.7 explicitly states the
    pointer-returning Find() signature is preserved.

    Contiguity guaranteed structurally by std::array (confirmed
    directly with pointer arithmetic: &All[1] - &All[0] == 1, i.e.
    exactly sizeof(T) bytes apart -- see test_generated_aos_linear.cpp).
    """
    n = len(instances)

    # ---- instances namespace: one constexpr std::array<T, N> All ----
    lines.append(f"namespace {type_name}_Instances")
    lines.append("{")
    if n > 0:
        lines.append(f"    inline constexpr std::array<{type_name}, {n}> All = {{{{")
        for name, value in instances:
            parts = [_cpp_value_literal(value.fields[f.name], f.type_tokens, reg)
                      for f in d.fields]
            init = ", ".join(parts)
            lines.append(f"        {{ {init} }},  // {name}")
        lines.append("    }};")
    else:
        lines.append(f"    inline constexpr std::array<{type_name}, 0> All = {{}};")

    # per-instance index constants: same 0-based dense ordering as AoS.
    # Placed inside _Instances namespace rather than at file scope to
    # keep them next to what they index, same discipline as §13.2's
    # _Index constants that already live in _Instances.
    lines.append("")
    for i, (name, _value) in enumerate(instances):
        lines.append(f"    inline constexpr std::size_t {name}_Index = {i};")
    lines.append("}")
    lines.append("")

    # ---- registry namespace: lookup by ID and by name ----
    entries = []
    for name, _value in instances:
        iid = reg.get_instance_id(type_name, name)
        entries.append((iid, name))
    entries.sort(key=lambda e: e[0])

    lines.append(f"namespace {type_name}_Registry")
    lines.append("{")
    lines.append("    struct Entry")
    lines.append("    {")
    lines.append("        uint64_t instance_id;")
    lines.append("        std::string_view name;")
    lines.append("        std::size_t index;")
    lines.append("    };")
    lines.append("")

    if entries:
        lines.append(f"    inline constexpr std::array<Entry, {len(entries)}> Table =")
        lines.append("    {")
        for iid, name in entries:
            idx = next(i for i, (nm, _) in enumerate(instances) if nm == name)
            lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", {idx} }},")
        lines.append("    };")
    else:
        lines.append(f"    inline constexpr std::array<Entry, 0> Table = {{}};")
    lines.append("")

    lines.append(f"    constexpr const {type_name}* Find(uint64_t instance_id)")
    lines.append("    {")
    lines.append("        std::size_t lo = 0, hi = Table.size();")
    lines.append("")
    lines.append("        while (lo < hi)")
    lines.append("        {")
    lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
    lines.append("")
    lines.append("            if (Table[mid].instance_id < instance_id)")
    lines.append("            {")
    lines.append("                lo = mid + 1;")
    lines.append("            } else {")
    lines.append("                hi = mid;")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
    lines.append("        {")
    lines.append(f"            return &{type_name}_Instances::All[Table[lo].index];")
    lines.append("        }")
    lines.append("")
    lines.append("        return nullptr;")
    lines.append("    }")
    lines.append("")

    lines.append(f"    constexpr const {type_name}* Find(std::string_view name)")
    lines.append("    {")
    lines.append("        for (const auto& entry : Table)")
    lines.append("        {")
    lines.append("            if (entry.name == name)")
    lines.append("            {")
    lines.append(f"                return &{type_name}_Instances::All[entry.index];")
    lines.append("            }")
    lines.append("        }")
    lines.append("")
    lines.append("        return nullptr;")
    lines.append("    }")
    lines.append(f"}} // namespace {type_name}_Registry")
    if not is_last_type:
        lines.append("")


def _emit_aos_split_type(header_lines, cpp_lines, type_name, d, instances, reg, is_last_type):
    """§14.3, AoS: extern declarations + Find() signatures in the
    header; actual const definitions + Find() bodies (no longer
    constexpr) in the .cpp. Mirrors generate_header's AoS block
    structurally, but is a fresh implementation, not a refactor of it --
    that one must stay completely untouched for the regression
    guarantee --force-single-header depends on."""
    # ---- header: extern decls ----
    header_lines.append(f"namespace {type_name}_Instances")
    header_lines.append("{")
    for name, _value in instances:
        header_lines.append(f"    extern const {type_name} {name};")
    header_lines.append("}")
    header_lines.append("")

    entries = []
    for name, _value in instances:
        iid = reg.get_instance_id(type_name, name)
        entries.append((iid, name))
    entries.sort(key=lambda e: e[0])

    header_lines.append(f"namespace {type_name}_Registry")
    header_lines.append("{")
    header_lines.append("    struct Entry")
    header_lines.append("    {")
    header_lines.append("        uint64_t instance_id;")
    header_lines.append("        std::string_view name;")
    header_lines.append(f"        const {type_name}* data;")
    header_lines.append("    };")
    header_lines.append("")
    header_lines.append(f"    extern const std::array<Entry, {len(entries)}> Table;")
    header_lines.append("")
    header_lines.append(f"    const {type_name}* Find(uint64_t instance_id);")
    header_lines.append("")
    header_lines.append(f"    const {type_name}* Find(std::string_view name);")
    header_lines.append(f"}} // namespace {type_name}_Registry")
    if not is_last_type:
        header_lines.append("")

    # ---- cpp: actual definitions + Find() bodies ----
    cpp_lines.append(f"namespace {type_name}_Instances")
    cpp_lines.append("{")
    for name, value in instances:
        parts = [_cpp_value_literal(value.fields[f.name], f.type_tokens, reg)
                  for f in d.fields]
        init = ", ".join(parts)
        cpp_lines.append(f"    const {type_name} {name} = {{ {init} }};")
    cpp_lines.append(f"}} // namespace {type_name}_Instances")
    cpp_lines.append("")

    cpp_lines.append(f"namespace {type_name}_Registry")
    cpp_lines.append("{")
    if entries:
        cpp_lines.append(f"    const std::array<Entry, {len(entries)}> Table =")
        cpp_lines.append("    {")
        for iid, name in entries:
            cpp_lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", "
                              f"&{type_name}_Instances::{name} }},")
        cpp_lines.append("    };")
    else:
        cpp_lines.append(f"    const std::array<Entry, 0> Table = {{}};")
    cpp_lines.append("")

    cpp_lines.append(f"    const {type_name}* Find(uint64_t instance_id)")
    cpp_lines.append("    {")
    cpp_lines.append("        std::size_t lo = 0, hi = Table.size();")
    cpp_lines.append("")
    cpp_lines.append("        while (lo < hi)")
    cpp_lines.append("        {")
    cpp_lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
    cpp_lines.append("")
    cpp_lines.append("            if (Table[mid].instance_id < instance_id)")
    cpp_lines.append("            {")
    cpp_lines.append("                lo = mid + 1;")
    cpp_lines.append("            } else {")
    cpp_lines.append("                hi = mid;")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
    cpp_lines.append("        {")
    cpp_lines.append("            return Table[lo].data;")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return nullptr;")
    cpp_lines.append("    }")
    cpp_lines.append("")

    cpp_lines.append(f"    const {type_name}* Find(std::string_view name)")
    cpp_lines.append("    {")
    cpp_lines.append("        for (const auto& entry : Table)")
    cpp_lines.append("        {")
    cpp_lines.append("            if (entry.name == name)")
    cpp_lines.append("            {")
    cpp_lines.append("                return entry.data;")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return nullptr;")
    cpp_lines.append("    }")
    cpp_lines.append(f"}} // namespace {type_name}_Registry")
    if not is_last_type:
        cpp_lines.append("")


def _emit_aos_linear_split_type(header_lines, cpp_lines, type_name, d, instances, reg, is_last_type):
    """§13.7 AoS-linear layout, split mode: extern declaration for one
    std::array<T, N> All (header) + the actual array + Find() bodies
    (no longer constexpr, matching _emit_aos_split_type's own reasoning
    for why split-mode bodies aren't constexpr) in the .cpp. Mirrors
    _emit_aos_linear_type's single-header shape structurally, same as
    _emit_aos_split_type mirrors generate_header's inline AoS block --
    a fresh implementation, not a refactor, so single-header mode's
    regression guarantee stays untouched.

    Same two properties as the single-header version, unchanged by the
    split: double-brace initializer required for std::array<T, N>
    aggregate init, and Find() returns const T* (= &All[i]), not an
    index, preserving the existing AoS Find() signature exactly.
    """
    n = len(instances)

    # ---- header: extern decl for the one instance array ----
    header_lines.append(f"namespace {type_name}_Instances")
    header_lines.append("{")
    header_lines.append(f"    extern const std::array<{type_name}, {n}> All;")
    header_lines.append("")
    for i, (name, _value) in enumerate(instances):
        header_lines.append(f"    inline constexpr std::size_t {name}_Index = {i};")
    header_lines.append("}")
    header_lines.append("")

    entries = []
    for name, _value in instances:
        iid = reg.get_instance_id(type_name, name)
        entries.append((iid, name))
    entries.sort(key=lambda e: e[0])

    header_lines.append(f"namespace {type_name}_Registry")
    header_lines.append("{")
    header_lines.append("    struct Entry")
    header_lines.append("    {")
    header_lines.append("        uint64_t instance_id;")
    header_lines.append("        std::string_view name;")
    header_lines.append("        std::size_t index;")
    header_lines.append("    };")
    header_lines.append("")
    header_lines.append(f"    extern const std::array<Entry, {len(entries)}> Table;")
    header_lines.append("")
    header_lines.append(f"    const {type_name}* Find(uint64_t instance_id);")
    header_lines.append("")
    header_lines.append(f"    const {type_name}* Find(std::string_view name);")
    header_lines.append(f"}} // namespace {type_name}_Registry")
    if not is_last_type:
        header_lines.append("")

    # ---- cpp: actual array contents + Find() bodies ----
    cpp_lines.append(f"namespace {type_name}_Instances")
    cpp_lines.append("{")
    if n > 0:
        cpp_lines.append(f"    const std::array<{type_name}, {n}> All = {{{{")
        for name, value in instances:
            parts = [_cpp_value_literal(value.fields[f.name], f.type_tokens, reg)
                      for f in d.fields]
            init = ", ".join(parts)
            cpp_lines.append(f"        {{ {init} }},  // {name}")
        cpp_lines.append("    }};")
    else:
        cpp_lines.append(f"    const std::array<{type_name}, 0> All = {{}};")
    cpp_lines.append(f"}} // namespace {type_name}_Instances")
    cpp_lines.append("")

    cpp_lines.append(f"namespace {type_name}_Registry")
    cpp_lines.append("{")
    if entries:
        cpp_lines.append(f"    const std::array<Entry, {len(entries)}> Table =")
        cpp_lines.append("    {")
        for iid, name in entries:
            idx = next(i for i, (nm, _) in enumerate(instances) if nm == name)
            cpp_lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", {idx} }},")
        cpp_lines.append("    };")
    else:
        cpp_lines.append(f"    const std::array<Entry, 0> Table = {{}};")
    cpp_lines.append("")

    cpp_lines.append(f"    const {type_name}* Find(uint64_t instance_id)")
    cpp_lines.append("    {")
    cpp_lines.append("        std::size_t lo = 0, hi = Table.size();")
    cpp_lines.append("")
    cpp_lines.append("        while (lo < hi)")
    cpp_lines.append("        {")
    cpp_lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
    cpp_lines.append("")
    cpp_lines.append("            if (Table[mid].instance_id < instance_id)")
    cpp_lines.append("            {")
    cpp_lines.append("                lo = mid + 1;")
    cpp_lines.append("            } else {")
    cpp_lines.append("                hi = mid;")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
    cpp_lines.append("        {")
    cpp_lines.append(f"            return &{type_name}_Instances::All[Table[lo].index];")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return nullptr;")
    cpp_lines.append("    }")
    cpp_lines.append("")

    cpp_lines.append(f"    const {type_name}* Find(std::string_view name)")
    cpp_lines.append("    {")
    cpp_lines.append("        for (const auto& entry : Table)")
    cpp_lines.append("        {")
    cpp_lines.append("            if (entry.name == name)")
    cpp_lines.append("            {")
    cpp_lines.append(f"                return &{type_name}_Instances::All[entry.index];")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return nullptr;")
    cpp_lines.append("    }")
    cpp_lines.append(f"}} // namespace {type_name}_Registry")
    if not is_last_type:
        cpp_lines.append("")


def _emit_soa_split_type(header_lines, cpp_lines, type_name, reg, resolver, is_last_type):
    """§14.3, SoA: extern declarations for every flattened field array
    (§13.1) + Find() signatures in the header; the actual array
    contents + Find() bodies in the .cpp."""
    d = reg.defines[type_name]
    instances = export_instances_for_type(type_name, reg, resolver)
    leaves = _flatten_leaves(type_name, reg)
    count = len(instances)
    flat_per_instance = [_flatten_value(value, type_name, reg) for _name, value in instances]

    # ---- header: extern decls for every flattened array ----
    header_lines.append(f"namespace {type_name}_SoA")
    header_lines.append("{")
    for path, type_tokens in leaves:
        n = _string_n(type_tokens)
        if n is not None:
            total = n * count
            header_lines.append(f"    extern const std::array<char, {total}> {path};")
        else:
            cpp_type = _cpp_field_type(type_tokens, reg)
            header_lines.append(f"    extern const std::array<{cpp_type}, {count}> {path};")
    header_lines.append("}")
    header_lines.append("")

    entries = []
    for idx, (name, _value) in enumerate(instances):
        iid = reg.get_instance_id(type_name, name)
        entries.append((iid, name, idx))
    entries.sort(key=lambda e: e[0])

    header_lines.append(f"namespace {type_name}_SoA_Registry")
    header_lines.append("{")
    header_lines.append("    struct Entry")
    header_lines.append("    {")
    header_lines.append("        uint64_t instance_id;")
    header_lines.append("        std::string_view name;")
    header_lines.append("        std::size_t row;")
    header_lines.append("    };")
    header_lines.append("")
    header_lines.append(f"    extern const std::array<Entry, {len(entries)}> Table;")
    header_lines.append("")
    header_lines.append("    std::size_t Find(uint64_t instance_id);")
    header_lines.append("")
    header_lines.append("    std::size_t Find(std::string_view name);")
    header_lines.append(f"}} // namespace {type_name}_SoA_Registry")
    if not is_last_type:
        header_lines.append("")

    # ---- cpp: actual array contents + Find() bodies ----
    cpp_lines.append(f"namespace {type_name}_SoA")
    cpp_lines.append("{")
    for li, (path, type_tokens) in enumerate(leaves):
        n = _string_n(type_tokens)
        if n is not None:
            total = n * count
            combined = bytearray()
            for k in range(count):
                s = flat_per_instance[k][li]
                encoded = s.encode("utf-8")
                combined += encoded + b"\x00" * (n - len(encoded))
            if count == 0:
                cpp_lines.append(f"    const std::array<char, 0> {path} = {{}};")
            else:
                byte_literals = ", ".join(_cpp_char_literal(b) for b in combined)
                cpp_lines.append(f"    const std::array<char, {total}> {path} =")
                cpp_lines.append("    {")
                cpp_lines.append(f"        {byte_literals}")
                cpp_lines.append("    };")
        else:
            cpp_type = _cpp_field_type(type_tokens, reg)
            if count == 0:
                cpp_lines.append(f"    const std::array<{cpp_type}, 0> {path} = {{}};")
            else:
                values = ", ".join(
                    _cpp_value_literal(flat_per_instance[k][li], type_tokens, reg)
                    for k in range(count)
                )
                cpp_lines.append(f"    const std::array<{cpp_type}, {count}> {path} = {{ {values} }};")
        if li != len(leaves) - 1:
            cpp_lines.append("")
    cpp_lines.append(f"}} // namespace {type_name}_SoA")
    cpp_lines.append("")

    cpp_lines.append(f"namespace {type_name}_SoA_Registry")
    cpp_lines.append("{")
    if entries:
        cpp_lines.append(f"    const std::array<Entry, {len(entries)}> Table =")
        cpp_lines.append("    {")
        for iid, name, row in entries:
            cpp_lines.append(f"        Entry{{ 0x{iid}ULL, \"{name}\", {row} }},")
        cpp_lines.append("    };")
    else:
        cpp_lines.append("    const std::array<Entry, 0> Table = {};")
    cpp_lines.append("")

    cpp_lines.append("    std::size_t Find(uint64_t instance_id)")
    cpp_lines.append("    {")
    cpp_lines.append("        std::size_t lo = 0, hi = Table.size();")
    cpp_lines.append("")
    cpp_lines.append("        while (lo < hi)")
    cpp_lines.append("        {")
    cpp_lines.append("            std::size_t mid = lo + (hi - lo) / 2;")
    cpp_lines.append("")
    cpp_lines.append("            if (Table[mid].instance_id < instance_id)")
    cpp_lines.append("            {")
    cpp_lines.append("                lo = mid + 1;")
    cpp_lines.append("            } else {")
    cpp_lines.append("                hi = mid;")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        if (lo < Table.size() && Table[lo].instance_id == instance_id)")
    cpp_lines.append("        {")
    cpp_lines.append("            return Table[lo].row;")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return static_cast<std::size_t>(-1);")
    cpp_lines.append("    }")
    cpp_lines.append("")

    cpp_lines.append("    std::size_t Find(std::string_view name)")
    cpp_lines.append("    {")
    cpp_lines.append("        for (const auto& entry : Table)")
    cpp_lines.append("        {")
    cpp_lines.append("            if (entry.name == name)")
    cpp_lines.append("            {")
    cpp_lines.append("                return entry.row;")
    cpp_lines.append("            }")
    cpp_lines.append("        }")
    cpp_lines.append("")
    cpp_lines.append("        return static_cast<std::size_t>(-1);")
    cpp_lines.append("    }")
    cpp_lines.append(f"}} // namespace {type_name}_SoA_Registry")
    if not is_last_type:
        cpp_lines.append("")


def _include_basename(path):
    """Strips any directory component from a header path before it's
    embedded in a #include line, deliberately not via os.path.basename:
    that only understands the separator convention of whatever platform
    is actually running this script, so a Linux/Mac-hosted run given a
    Windows-style backslash path would leave it completely untouched.
    Splits on both / and \\ explicitly instead, regardless of host OS.

    Exists because the header and .cpp files are always written to the
    same directory (both derived from the same -o stem, confirmed by
    generate_split's own caller), so the #include never needs a
    directory component at all -- a bare filename already resolves
    correctly, on every platform, without needing to reproduce
    whatever path the user happened to pass to -o (and without risking
    a raw backslash landing inside a C++ string literal, where it's an
    escape-sequence introducer, not a path separator, and corrupts the
    include entirely on the one platform -o backslash paths actually
    come from)."""
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def generate_split(reg, resolver, guard_name="GDDL_GENERATED_H",
                    header_filename="generated.h", layout="aos",
                    emit_all_domains: bool = False):
    """§14.3: header/.cpp split, the NEW DEFAULT. Returns (header_text,
    cpp_text).

    Deliberately a separate function from generate_header (which is now
    exactly --force-single-header's implementation), not a refactor of
    it -- generate_header must stay completely untouched so
    --force-single-header can reproduce its exact byte-for-byte output
    with zero risk, which is the whole point of that flag existing.
    Some line-building style genuinely repeats (same §14.0 brace/blank-
    line rules, same Find() binary-search body shape minus constexpr)
    but is written fresh here rather than factored into shared
    line-building code both paths would then depend on.

    Header: enum definitions (unconditional -- C++ has no way to
    declare an enum class's enumerators separately from defining them);
    struct definitions (AoS only, same as before -- SoA fully flattens,
    so no struct is ever needed there); extern declarations for every
    instance/array and every registry's Table; Find() signatures only.

    .cpp: the actual const definitions, actual Table contents, and
    Find() bodies -- ordinary runtime functions now, not constexpr,
    since nothing outside this one file needs their body visible.
    """
    if layout not in ("aos", "aos-linear", "soa"):
        raise ValueError(f"layout must be 'aos', 'aos-linear', or 'soa', got {layout!r}")

    header_lines = []
    header_lines.append(f"#ifndef {guard_name}")
    header_lines.append(f"#define {guard_name}")
    header_lines.append("")
    header_lines.append("// Auto-generated by the GDDL compiler. Do not edit by hand.")
    header_lines.append("")
    header_lines.append("#include <cstdint>")
    header_lines.append("#include <array>")
    header_lines.append("#include <string_view>")
    header_lines.append("")
    header_lines.append("namespace GDDL")
    header_lines.append("{")
    header_lines.append("")

    cpp_lines = []
    cpp_lines.append("// Auto-generated by the GDDL compiler. Do not edit by hand.")
    cpp_lines.append("")
    cpp_lines.append(f'#include "{_include_basename(header_filename)}"')
    cpp_lines.append("")
    cpp_lines.append("namespace GDDL")
    cpp_lines.append("{")
    cpp_lines.append("")

    # ---- 1. enums: header only, unconditional in BOTH layouts -- a
    # structural C++ requirement, not a choice (§14.0/§14.3: an enum
    # class's enumerators ARE its definition, no way to split them). ----
    indexed_domains_used = _domains_used_indexed(reg)
    for domain_name, block in reg.identifiers.items():
        header_lines.append(f"enum class {domain_name} : uint64_t")
        header_lines.append("{")
        entry_rows = []
        for entry in block.entries:
            lid = reg.get_logical_id(domain_name, entry.key)
            entry_rows.append((entry.key, f"= 0x{lid}ULL,", f"// {entry.description}"))
        for row in _align_columns(entry_rows):
            header_lines.append(f"    {row}")
        header_lines.append("};")
        header_lines.append("")

        if domain_name in reg.identifier_widths and (
                domain_name in indexed_domains_used or emit_all_domains):
            width = reg.identifier_widths[domain_name]
            cpp_width = _CPP_INT_TYPES[width]
            header_lines.append(f"enum class {domain_name}_Indexed : {cpp_width}")
            header_lines.append("{")
            indexed_rows = []
            for index, entry in enumerate(block.entries):
                indexed_rows.append((entry.key, f"= {index},", f"// {entry.description}"))
            for row in _align_columns(indexed_rows):
                header_lines.append(f"    {row}")
            header_lines.append("};")
            header_lines.append("")

    # ---- 1b. flags domains -> namespace { constexpr WIDTH member = ...; }
    # -- header only, same structural reason as the enums above (no way
    # to split a namespace's constexpr definitions from their values). ----
    for domain_name, block in reg.flags.items():
        header_lines.extend(_render_flags_namespace(domain_name, block, reg))

    # ---- 2. structs: header only, AoS or AoS-linear -- same rule as
    # generate_header (SoA fully flattens, never needs a struct type;
    # aos-linear needs it since std::array<T,N> requires T defined). ----
    define_order = _topo_sort_defines(reg)
    if layout in ("aos", "aos-linear"):
        for type_name in define_order:
            d = reg.defines[type_name]
            header_lines.append(f"struct {type_name}")
            header_lines.append("{")
            field_rows = []
            for f in d.fields:
                n = _string_n(f.type_tokens)
                if n is not None:
                    field_rows.append(("char", f"{f.name}[{n}];"))
                else:
                    cpp_type = _cpp_field_type(f.type_tokens, reg)
                    field_rows.append((cpp_type, f"{f.name};"))
            for row in _align_columns(field_rows):
                header_lines.append(f"    {row}")
            header_lines.append("};")
            header_lines.append("")

    # ---- 3. per-type: extern decls + Find() signatures (header) vs.
    # actual definitions + Find() bodies (.cpp) ----
    for i, type_name in enumerate(define_order):
        is_last_type = (i == len(define_order) - 1)
        d = reg.defines[type_name]
        instances = export_instances_for_type(type_name, reg, resolver)

        if layout == "soa":
            _emit_soa_split_type(header_lines, cpp_lines, type_name, reg, resolver, is_last_type)
        elif layout == "aos-linear":
            _emit_aos_linear_split_type(header_lines, cpp_lines, type_name, d, instances, reg, is_last_type)
        else:
            _emit_aos_split_type(header_lines, cpp_lines, type_name, d, instances, reg, is_last_type)

    # §17.5: compile-time schema table -- header-resident in split mode
    # too, same as domain enums and other small compile-time metadata.
    # No .cpp counterpart: there's no ODR reason to split eight bytes
    # and a name per type into a separate translation unit.
    header_lines.append("")
    header_lines.extend(render_schema_table(reg))
    header_lines.append("")

    header_lines.append("} // namespace GDDL")
    header_lines.append("")
    header_lines.append(f"#endif // {guard_name}")
    header_lines.append("")

    cpp_lines.append("} // namespace GDDL")
    cpp_lines.append("")

    return "\n".join(header_lines), "\n".join(cpp_lines)


def _cli():
    """Compile-time flags: --layout (§13.6, aos/soa) and
    --force-single-header (§14.3 -- default is now the split .h/.cpp,
    this flag reverts to the original single-header behavior). Not the
    primary interface used for testing in this project so far (that's
    calling generate_header/generate_split directly) -- added for
    completeness, matching how the task frames these as compiler
    flags."""
    import argparse
    import sys
    from .combine import resolve_inputs, compile_multi, CombineError
    from .export_ids import write_ids_manifest

    ap = argparse.ArgumentParser(description="GDDL -> C++ exporter")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--layout", choices=["aos", "aos-linear", "soa"], default="aos",
                     help="aos (default), aos-linear, or soa data layout")
    ap.add_argument("--force-single-header", action="store_true",
                     help="single header instead of split .h/.cpp")
    ap.add_argument("--emit-all-domains", action="store_true",
                     help="emit every domain's constants, even unreferenced ones (default: off)")
    ap.add_argument("--emit-ids-manifest", action="store_true",
                     help="also write <output>.gddlids.json, every identifier/flags "
                          "domain declared, for cross-mod script references (default: off)")
    ap.add_argument("-o", "--output", default="generated",
                     help="output path stem (default: stdout for single-header, 'generated' otherwise)")
    ap.add_argument("--verbose-errors", action="store_true",
                     help="tag each error with its internal [phase N, check] (default: off)")
    args = ap.parse_args()

    try:
        paths = resolve_inputs(args.source)
    except CombineError as e:
        ap.error(str(e))

    result = compile_multi(paths)
    if result["status"] == "parse_error":
        err = result["error"]
        print(f"{err['file']}:{err['line']}: {err['message']}", file=sys.stderr)
        sys.exit(1)
    resolver = result["resolver"]
    if not check_and_report(resolver, verbose=args.verbose_errors):
        sys.exit(1)

    if args.force_single_header:
        header = generate_header(resolver.reg, resolver, layout=args.layout,
                                  emit_all_domains=args.emit_all_domains)
        if args.output and args.output != "generated":
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(header)
        else:
            print(header)
    else:
        header_name = f"{args.output}.h"
        cpp_name = f"{args.output}.cpp"
        header, cpp = generate_split(resolver.reg, resolver,
                                      header_filename=header_name, layout=args.layout,
                                      emit_all_domains=args.emit_all_domains)
        with open(header_name, "w", encoding="utf-8") as f:
            f.write(header)
        with open(cpp_name, "w", encoding="utf-8") as f:
            f.write(cpp)
        print(f"wrote {header_name} and {cpp_name}")

    if args.emit_ids_manifest:
        manifest_path = write_ids_manifest(resolver.reg, args.output)
        print(f"wrote {manifest_path}")


if __name__ == "__main__":
    _cli()
