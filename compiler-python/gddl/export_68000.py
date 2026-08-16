# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
68000 export (§15): shared IR and C89 renderer, combined in one module.

Unlike 6502 (§10.3, three genuinely different assembler dialects, each
needing its own renderer against a shared IR), 68000 has only ONE
generated-output shape: C89 source compiled with vbcc (§15.1: "one
generated output, two vbcc target configs"). No dialect-selection axis
here, and no reason to split IR-gathering from rendering into two
files the way export_6502.py/export_6502_acme.py do.

Genuine hybrid design (§15's own framing), not a clone of either prior
exporter:
  - IMPLEMENTATION STYLE follows the C++ exporter: real structs, a real
    C compiler (vbcc) doing codegen, no hand-tuned assembly. AoS
    preserves composition as genuine nested C structs (topologically
    ordered via export_cpp.py's own _topo_sort_defines, reused as-is --
    nested-struct dependency ordering isn't C++-specific logic). SoA
    fully flattens through composition (§13.1), reusing export_cpp.py's
    _flatten_leaves/_flatten_value directly -- the exact same helpers
    both the C++ and 6502 SoA paths already use, since flattening rules
    don't vary by target.
  - IDENTITY/INDEXING PHILOSOPHY follows the 6502 exporter (§15.4,
    §10.1): fully static, no logical IDs, no instance stable IDs, dense
    declaration-order indices for both identifier-typed fields AND
    instance references. `@Domain` vs plain `Domain` is indistinguishable
    here too.
  - SoA needs NO lookup mechanism at all (§13.4, corrected: "any target
    using the dense-index identity system (6502, §10.1; 68000, §15.4)"
    -- not 6502-specific wording anymore). The same index that accesses
    an AoS instance directly indexes into every SoA field array too.
    No registry, no search, no Find() in SoA mode -- just parallel
    const arrays.

Header/`.c` split is REQUIRED (§15.2, corrected -- not merely a
readability choice): a definition can only appear in exactly one `.c`
file; anything else needing the data sees only an `extern` declaration
in a header. A single generated `.c` file directly #include'd (this
module's very first pass) only worked because the test happened to be
exactly one translation unit -- a second `.c` file needing the same
data would hit duplicate-definition linker errors. render_c89_split
always produces both a header and a `.c` file now; there is no
single-file mode anymore.

No `inline`-equivalent trickery needed (§15.2): ordinary C globals with
external linkage are always emitted regardless of reference -- this
problem is C++-specific and doesn't exist in C.

No hand-written byte-splitting tricks needed (§15.3): plain C array
indexing (`table[index]`) is idiomatic and correct on 68000; vbcc's own
codegen decides how to implement it. No Lo/Hi split arrays, no manual
pointer arithmetic.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .export_cpp import (
    export_instances_for_type, _flatten_leaves, _flatten_value, _topo_sort_defines,
    _string_n, _align_columns,
)
from .resolve import IdentifierRef, StructValue
from .validate import check_and_report


class Export68000Error(Exception):
    """A 68000-export-time error -- distinct from anything phase 4-8
    already raises, since the front-end has no concept of export
    targets at all. Always names the specific thing that's wrong."""
    pass


_WIDTH_TO_C_TYPE = {
    "u8": "unsigned char",
    "u16": "unsigned short",
    "u32": "unsigned long",
    "u64": None,  # not supported this pass -- no natural single C89 integer type mapping decided yet
}

_SCALAR_TO_C_TYPE = {
    "u8": "unsigned char", "u16": "unsigned short", "u32": "unsigned long", "u64": None,
    "i8": "signed char", "i16": "signed short", "i32": "signed long", "i64": None,
}


@dataclass
class DomainInfo:
    name: str
    width: str
    members: List[Tuple[str, int]]  # identifier: (key, 0-based index); flags: (key, real bit value)
    kind: str = "identifier"  # 'identifier' or 'flags' -- see export_6502.py's DomainInfo
                               # for the full reasoning. On THIS target specifically, kind
                               # also governs whether the domain gets its own typedef: an
                               # identifier domain becomes a real C89 named type (its own
                               # typedef + cast-to-that-type constants); a flags domain gets
                               # NO typedef at all, matching the settled cross-target design
                               # ("the field itself is the raw width type, NOT a named/
                               # wrapped type") -- just plain #define constants.


@dataclass
class FieldInfo:
    name: str
    type_tokens: str  # raw GDDL type string ('u8', 'ActionAttack', '@ActionAttack', 'Object', ...)


@dataclass
class TypeInfo:
    name: str
    fields: List[FieldInfo]
    instance_names: List[str]        # declaration order == dense index order
    instance_values: List[object]     # StructValue per instance, same order


def _leaf_domain_name(type_tokens: str, reg):
    """The identifier domain a field refers to, regardless of whether
    source wrote 'Domain' or '@Domain' -- indistinguishable on this
    target too (§15.4, same rule as 6502 §10.1)."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in reg.identifiers:
        return t
    return None


def gather_domains_used(reg, type_names) -> set:
    """Every identifier domain referenced by any LEAF field (after full
    composition flattening, §13.1) of any type being exported --
    regardless of plain-Domain vs @Domain in source. Uses
    _flatten_leaves so a domain referenced only through a nested
    composed field is still found."""
    used = set()
    for type_name in type_names:
        for _path, type_tokens in _flatten_leaves(type_name, reg):
            domain = _leaf_domain_name(type_tokens, reg)
            if domain is not None:
                used.add(domain)
    return used


def check_68000_domain_widths(reg, type_names):
    """§15.4: every identifier domain referenced by anything exported
    to 68000 must have a declared width -- same requirement as 6502,
    same reason: something has to decide the domain's C typedef
    underlying type, and there's no other source for that decision."""
    used = gather_domains_used(reg, type_names)
    missing = sorted(d for d in used if d not in reg.identifier_widths)
    if missing:
        names = ", ".join(f"'{d}'" for d in missing)
        raise Export68000Error(
            f"68000 export requires every referenced identifier domain to "
            f"have a declared width (§15.4, §8.3) -- {names} "
            f"{'has' if len(missing) == 1 else 'have'} no declared width. "
            f"Add one at the domain's own declaration (e.g. 'identifier "
            f"{missing[0]} u8') before 68000 export can proceed."
        )


def gather_domain_info(reg, type_names,
                       emit_all_domains: bool = False) -> List[DomainInfo]:
    """Per-domain member index constants -- 0-based, declaration order,
    same numbering §8.4 already establishes.

    emit_all_domains (§8.5 / --emit-all-domains): when True, every
    domain that has a declared width is included regardless of whether
    any exported type references it.  A domain with no declared width
    is unaffected either way."""
    used = gather_domains_used(reg, type_names)
    domains = []
    for domain_name in reg.identifiers:
        if domain_name not in used and not emit_all_domains:
            continue
        if domain_name not in reg.identifier_widths:
            continue
        width = reg.identifier_widths[domain_name]
        block = reg.identifiers[domain_name]
        members = [(entry.key, i) for i, entry in enumerate(block.entries)]
        domains.append(DomainInfo(name=domain_name, width=width, members=members))
    return domains


def _leaf_flags_domain_name(type_tokens: str, reg):
    """The flags domain a field refers to, or None. No '@' handling
    needed -- flags never had a hash-vs-index duality to carry an '@'
    prefix for (see export_6502.py's identical helper)."""
    t = type_tokens.strip()
    if t in reg.flags:
        return t
    return None


def gather_flags_domains_used(reg, type_names) -> set:
    used = set()
    for type_name in type_names:
        for _path, type_tokens in _flatten_leaves(type_name, reg):
            domain = _leaf_flags_domain_name(type_tokens, reg)
            if domain is not None:
                used.add(domain)
    return used


def gather_flags_domain_info(reg, type_names, emit_all_domains: bool = False) -> List[DomainInfo]:
    """Per-domain member constant tables for flags domains -- same
    DomainInfo shape gather_domain_info produces for identifier domains,
    but `members` holds each entry's REAL bit-claim value, not a dense
    index, and `kind='flags'` tells render_c89_split to skip the
    typedef/cast-constant emission entirely (see this module's DomainInfo
    docstring, and export_6502.py's identical function for the shared
    reasoning)."""
    used = gather_flags_domains_used(reg, type_names)
    domains = []
    for domain_name in reg.flags:
        if domain_name not in used and not emit_all_domains:
            continue
        width = reg.flags_widths[domain_name]
        block = reg.flags[domain_name]
        members = []
        for entry in block.entries:
            value = reg.get_flags_value(domain_name, entry.name)
            if value is None:
                continue
            members.append((entry.name, value))
        domains.append(DomainInfo(name=domain_name, width=width, members=members, kind="flags"))
    return domains


def gather_type_info(reg, resolver, type_name) -> TypeInfo:
    """Fields gathered AS DECLARED (not flattened) -- AoS preserves
    composition as real nested C structs. SoA's flattening happens
    separately at render time via gather_soa_columns, reusing
    export_cpp.py's _flatten_leaves/_flatten_value directly."""
    d = reg.defines[type_name]
    fields = [FieldInfo(name=f.name, type_tokens=f.type_tokens) for f in d.fields]
    instances = export_instances_for_type(type_name, reg, resolver)
    names = [name for name, _value in instances]
    values = [value for _name, value in instances]
    return TypeInfo(name=type_name, fields=fields, instance_names=names, instance_values=values)


def gather_soa_columns(type_info: TypeInfo, reg):
    """§13.1: full flattening through composition, reusing
    export_cpp.py's own _flatten_leaves/_flatten_value -- the exact
    same helpers the C++ and 6502 SoA paths already use. Returns a
    list of (path, type_tokens, values), one entry per leaf, values
    ordered by instance declaration order (the same dense index AoS
    uses, §13.4/§15.4 -- no separate lookup exists or is needed)."""
    leaves = _flatten_leaves(type_info.name, reg)
    columns = []
    for li, (path, type_tokens) in enumerate(leaves):
        values = []
        for value in type_info.instance_values:
            flat = _flatten_value(value, type_info.name, reg)
            values.append(flat[li])
        columns.append((path, type_tokens, values))
    return columns


def gather_ir(reg, resolver, type_names, emit_all_domains: bool = False):
    """Full shared IR for a 68000 export of the given types. Validates
    the width rule first (fails fast, before gathering anything), same
    discipline as the 6502 exporter. Returns (domains, types)."""
    check_68000_domain_widths(reg, type_names)
    ordered_type_names = [t for t in reg.defines if t in type_names]
    domains = gather_domain_info(reg, ordered_type_names,
                                  emit_all_domains=emit_all_domains)
    domains += gather_flags_domain_info(reg, ordered_type_names,
                                         emit_all_domains=emit_all_domains)
    types = [gather_type_info(reg, resolver, t) for t in ordered_type_names]
    return domains, types


def _c_field_type(type_tokens: str, reg, domain_widths: dict) -> str:
    """C89 type for one field. Scalars map directly; identifier-typed
    fields (plain Domain or @Domain -- indistinguishable here, §15.4)
    become the domain's own typedef name; struct-typed fields become
    the nested type's own C struct name (composition, AoS only);
    flags-typed fields become the domain's raw WIDTH type directly --
    deliberately NOT the domain name, unlike identifier -- a flags
    domain gets no typedef of its own at all (see this module's
    DomainInfo docstring for why: "the field itself is the raw width
    type, NOT a named/wrapped type", the same settled design every
    other target uses)."""
    t = type_tokens.strip()
    if t in reg.flags:
        width = reg.flags_widths[t]
        c_type = _WIDTH_TO_C_TYPE.get(width)
        if c_type is None:
            raise Export68000Error(
                f"68000 first pass doesn't support {width}-wide flags domains yet")
        return c_type
    if t.startswith("@"):
        t = t[1:].strip()
    if t in domain_widths:
        return t  # the domain's typedef name itself, e.g. "ActionAttack"
    if t in reg.defines:
        return t  # nested struct, same name (composition)
    c_type = _SCALAR_TO_C_TYPE.get(t)
    if c_type is None:
        raise Export68000Error(
            f"68000 first pass doesn't support field type {type_tokens!r} yet "
            "(scalar u8/u16/u32/i8/i16/i32, identifier-typed, flags-typed, "
            "and struct-typed composed fields only)")
    return c_type


def _c_string_literal(s: str) -> str:
    """C89 string literal, escaped. GDDL strings are already validated
    to fit within their field's N-1 byte capacity (§5, String Length
    Enforcement) before this is ever called -- this only needs to
    escape characters that are special in C source, not re-check length."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _c_value_literal(value, type_tokens: str, reg) -> str:
    """A single field's resolved value as a C89 initializer expression.
    Recurses into nested StructValues for composed fields (AoS only --
    SoA never calls this on a StructValue, since flattening already
    reduced everything to leaves)."""
    t = type_tokens.strip()
    if isinstance(value, IdentifierRef):
        return f"{value.domain}_{value.key}"
    if isinstance(value, StructValue):
        nested_type = t[1:].strip() if t.startswith("@") else t
        d = reg.defines[nested_type]
        parts = [_c_value_literal(value.fields[f.name], f.type_tokens, reg) for f in d.fields]
        return "{ " + ", ".join(parts) + " }"
    if isinstance(value, str):
        return _c_string_literal(value)
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, float):
        return repr(value)
    if isinstance(value, int):
        return str(value)
    raise Export68000Error(
        f"68000 first pass doesn't support value {value!r} of declared type "
        f"{type_tokens!r} yet")


def render_c89_split(domains: List[DomainInfo], types: List[TypeInfo], reg,
                      layout: str = "aos", header_filename: str = "generated.h",
                      guard_name: str = "GDDL_GENERATED_68000_H"):
    """§15.2 (corrected): always produces (header_text, c_text) -- never
    a single file. §13.6: layout is a single explicit per-run flag, no
    target-based default, mirroring C++ and 6502 exactly."""
    if layout not in ("aos", "soa"):
        raise ValueError(f"layout must be 'aos' or 'soa', got {layout!r}")

    domain_widths = {d.name: d.width for d in domains}

    header = []
    header.append(f"#ifndef {guard_name}")
    header.append(f"#define {guard_name}")
    header.append("")
    header.append("/* Auto-generated by the GDDL compiler (68000 / vbcc, C89). Do not edit by hand. */")
    header.append("")

    c = []
    c.append("/* Auto-generated by the GDDL compiler (68000 / vbcc, C89). Do not edit by hand. */")
    c.append("")
    c.append(f'#include "{header_filename}"')
    c.append("")

    # ---- 1. identifier domains: typedef + typed constants (§15.4) --
    # always in the header, unconditional, same reasoning as C++'s enum
    # definitions always being header-resident (a type/constant
    # declaration needs to be visible everywhere, and there's no C
    # mechanism to split a typedef from its meaning the way there's no
    # way to split an enum class's enumerators from its definition). ----
    for d in domains:
        c_type = _WIDTH_TO_C_TYPE.get(d.width)
        if c_type is None:
            raise Export68000Error(f"68000 first pass doesn't support {d.width}-wide domains yet")
        if d.kind != "identifier":
            # flags domain: plain constants only, no typedef at all --
            # deliberately NOT the identifier pattern's cast-to-domain-
            # type wrapper (see DomainInfo's own docstring). A flags
            # field's C type is already the raw width type directly
            # (_c_field_type), so these constants need no cast to make
            # assignment/combination type-correct.
            header.append(f"/* --- domain: {d.name} (flags, width {d.width}) --- */")
            define_rows = [(f"#define {d.name}_{key}", str(value)) for key, value in d.members]
            header.extend(_align_columns(define_rows))
            header.append("")
            continue
        header.append(f"/* --- domain: {d.name} (dense index, width {d.width}) --- */")
        header.append(f"typedef {c_type} {d.name};")
        define_rows = [
            (f"#define {d.name}_{key}", f"(({d.name}){index})")
            for key, index in d.members
        ]
        header.extend(_align_columns(define_rows))
        header.append("")

    # BUG FIX (found during independent verification, confirmed with a
    # direct repro before touching anything): _topo_sort_defines(reg)
    # with no roots visits EVERY define in the whole registry, not just
    # what's reachable from the requested `types`. Requesting a genuine
    # subset (e.g. just Item from a file that also defines an unrelated
    # Creature) used to fail outright -- this tried to emit Creature's
    # struct too, and crashed because Creature's own domain needs were
    # never gathered for the request in the first place (gathering was
    # already correctly scoped; only this struct-order computation
    # wasn't). Fixed by passing roots=[requested type names] -- pulls
    # in exactly {requested} union {everything they transitively
    # compose}, never an unrelated type that merely happens to share
    # the registry. The old "over-emitting an unused struct definition
    # is harmless" reasoning below was wrong: it's harmless ONLY when
    # the unused type's own dependencies (a domain, in the case that
    # surfaced this) were already gathered too, which isn't guaranteed
    # once gathering itself is correctly request-scoped.
    define_order = _topo_sort_defines(reg, roots=[t.name for t in types])

    if layout == "aos":
        # ---- 2. struct definitions -- AoS only. SoA never needs a
        # struct type at all (full flattening, §13.1), same rule
        # already established for C++ and 6502. define_order is now
        # already reachability-pruned to exactly {requested types} plus
        # whatever they transitively compose (see the bug-fix comment
        # above define_order's computation) -- this loop can simply
        # emit every name in it. ----
        for type_name in define_order:
            d = reg.defines[type_name]
            header.append(f"/* --- type: {type_name} --- */")
            header.append(f"typedef struct {type_name}")
            header.append("{")
            field_rows = []
            for f in d.fields:
                n = _string_n(f.type_tokens)
                if n is not None:
                    field_rows.append(("char", f"{f.name}[{n}];"))
                else:
                    c_type = _c_field_type(f.type_tokens, reg, domain_widths)
                    field_rows.append((c_type, f"{f.name};"))
            for row in _align_columns(field_rows):
                header.append(f"    {row}")
            header.append(f"}} {type_name};")
            header.append("")

    if layout == "soa":
        # ---- SoA: one extern-declared array per leaf field (§13.1),
        # no struct, no lookup at all (§13.4, corrected). ----
        for t in types:
            header.append(f"/* --- type: {t.name} (SoA field arrays) --- */")
            n = len(t.instance_names)
            for i, name in enumerate(t.instance_names):
                header.append(f"#define {t.name}_{name}_Index {i}")
            header.append("")
            c.append(f"/* --- type: {t.name} (SoA field arrays) --- */")
            for path, type_tokens, values in gather_soa_columns(t, reg):
                label = f"{t.name}_{path}"
                str_n = _string_n(type_tokens)
                if str_n is not None:
                    # §13.2: one flat byte array of size N * count --
                    # a 2D C array char[count][N] IS exactly that flat
                    # layout, just with convenient per-instance
                    # indexing (label[i] gives instance i's whole
                    # N-byte string) rather than manual i*N pointer
                    # arithmetic (§15.3: no hand-written byte-splitting
                    # tricks needed, that's the compiler's job now).
                    header.append(f"extern const char {label}[{n}][{str_n}];")
                    rendered = [_c_value_literal(v, type_tokens, reg) for v in values]
                    c.append(f"const char {label}[{n}][{str_n}] = {{ {', '.join(rendered)} }};")
                else:
                    c_type = _c_field_type(type_tokens, reg, domain_widths)
                    header.append(f"extern const {c_type} {label}[{n}];")
                    rendered = [_c_value_literal(v, type_tokens, reg) for v in values]
                    c.append(f"const {c_type} {label}[{n}] = {{ {', '.join(rendered)} }};")
            header.append("")
            c.append("")
    else:
        # ---- AoS: dense declaration-order instance array + index
        # constants + Find() (§15.4/§10.1: no stable IDs, no search --
        # the index IS the identity). ----
        for t in types:
            n = len(t.instance_names)
            header.append(f"/* --- type: {t.name} instances --- */")
            for i, name in enumerate(t.instance_names):
                header.append(f"#define {t.name}_{name}_Index {i}")
            header.append("")
            header.append(f"extern const {t.name} {t.name}_Instances[{n}];")
            header.append("")
            header.append(f"const {t.name}* {t.name}_Find(unsigned int index);")
            header.append("")

            c.append(f"/* --- type: {t.name} instances --- */")
            c.append(f"const {t.name} {t.name}_Instances[{n}] =")
            c.append("{")
            for name, value in zip(t.instance_names, t.instance_values):
                parts = [_c_value_literal(value.fields[f.name], f.type_tokens, reg) for f in t.fields]
                c.append(f"    {{ {', '.join(parts)} }},  /* {name} */")
            c.append("};")
            c.append("")
            c.append(f"const {t.name}* {t.name}_Find(unsigned int index)")
            c.append("{")
            c.append(f"    return &{t.name}_Instances[index];")
            c.append("}")
            c.append("")

    header.append(f"#endif /* {guard_name} */")
    header.append("")

    return "\n".join(header), "\n".join(c)


def _cli():
    """§18 multi-file input via combine.py, matching every other
    exporter's CLI exactly (Z80/6502/C++/binary): --type is a
    required, repeatable option rather than a second positional list,
    since argparse cannot disambiguate two adjacent variable-length
    positionals (confirmed directly during §18's own work -- a bare
    second nargs='+' silently misparses which arguments belong to
    which list, rather than erroring). -o/--output behaves like C++'s
    split mode (the only mode 68000 has: render_c89_split always
    produces a header/.c pair, never a single file) -- writes
    <stem>.h and <stem>.c, same convention as export_cpp.py's split
    output, adapted to this target's own .h/.c (C89) extensions rather
    than .h/.cpp."""
    import argparse
    import os
    import sys
    from .combine import resolve_inputs, compile_multi, CombineError
    from .export_ids import write_ids_manifest

    ap = argparse.ArgumentParser(description="GDDL -> 68000 exporter (vbcc, C89)")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--type", dest="types", action="append", required=True,
                     help="type to export (repeatable)")
    ap.add_argument("--layout", choices=["aos", "soa"], default="aos",
                     help="aos (default) or soa data layout")
    ap.add_argument("--emit-all-domains", action="store_true",
                     help="emit every domain's constants, even unreferenced ones (default: off)")
    ap.add_argument("--emit-ids-manifest", action="store_true",
                     help="also write <output>.gddlids.json, every identifier/flags "
                          "domain declared, for cross-mod script references (default: off)")
    ap.add_argument("-o", "--output", required=True,
                     help="output path stem (writes <stem>.h and <stem>.c)")
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

    domains, types = gather_ir(resolver.reg, resolver, args.types,
                                emit_all_domains=args.emit_all_domains)

    header_name = f"{args.output}.h"
    c_name = f"{args.output}.c"
    header, c = render_c89_split(domains, types, resolver.reg,
                                  layout=args.layout,
                                  header_filename=os.path.basename(header_name))
    with open(header_name, "w", encoding="utf-8") as f:
        f.write(header)
    with open(c_name, "w", encoding="utf-8") as f:
        f.write(c)
    print(f"wrote {header_name} and {c_name}")

    if args.emit_ids_manifest:
        manifest_path = write_ids_manifest(resolver.reg, args.output)
        print(f"wrote {manifest_path}")


if __name__ == "__main__":
    _cli()
