# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
6502 export, phase 1: shared, assembler-agnostic resolution step (§10.3).

Computes exactly what needs to be emitted -- flattened instance data,
per-domain index tables, registry/lookup tables -- identical regardless
of which assembler dialect will render it. Mirrors how the C++ exporter
(export_cpp.py) already separates flattening logic from output
rendering; reuses that module's flattening/registry helpers directly,
since the underlying data model doesn't change between targets, only
what emits text does.

Three rules are unique to this target, neither of which exist in the
front-end (the front-end has no notion of "which export target" at
all, so these can't be phase 4/5 checks -- they're 6502-export-time
checks, raised or applied here, when a 6502 export is actually
attempted). The lens for all three, worth re-checking against for any
future 6502 design question too: 6502 (§9) is fully static -- no
mod/DLC, every rebuild is a full rebuild, physical media is never
live-patched -- so cross-build save/persistence compatibility, the
entire reason logical IDs and instance stable IDs exist at all, simply
never arises on this target, for identifiers OR instances:

  §10.1: No 64-bit IDs on 6502, identifiers or instances. Every
  identifier-typed field -- whether declared `Domain` or `@Domain` in
  source -- always exports using its domain's indexed form; `@` and
  plain become indistinguishable on this target, the same "source
  carries zero target-specific hints" principle as AoS/SoA (§13.6).
  Instances get the identical treatment: no FNV-1a-64 stable ID at all
  on this target -- see InstanceInfo.index below -- a dense,
  declaration-order position IS the instance's identity here, not a
  key that resolves to one.

  §10.1: every identifier domain referenced by anything being exported
  to 6502 must have a declared width. A domain with no width is
  completely valid for C++ (logical-ID mode needs none) -- but
  exporting that domain to 6502 specifically is an error here, naming
  the domain, not a crash or silent misbehavior.

  Consequence of the first rule, not a separate rule: since instance
  references are dense declaration-order indices rather than a sparse
  64-bit key space, registry/lookup on this target is direct O(1)
  indexed array access, never a search -- there is nothing to search
  FOR once the index itself is the identity.
"""

from dataclasses import dataclass, field as dc_field
from typing import List, Tuple, Optional

from export_cpp import (
    _flatten_leaves, _flatten_value, _string_n, export_instances_for_type,
)
from resolve import IdentifierRef
from validate import check_and_report


class Export6502Error(Exception):
    """A 6502-export-time error -- distinct from anything phase 4-8
    already raises, since the front-end has no concept of export
    targets at all. Always names the specific thing that's wrong
    (a domain, a field), never a bare crash."""
    pass


@dataclass
class DomainInfo:
    name: str
    width: str            # 'u8'/'u16'/'u32'/'u64'
    members: List[Tuple[str, int]]  # (key, 0-based index), declaration order


@dataclass
class InstanceInfo:
    name: str
    index: int              # dense, declaration-order position -- §10.1 extended:
                             # no stable IDs on 6502 either, same reasoning as
                             # identifiers (no cross-build save compatibility on
                             # this target). This index IS the instance's identity
                             # here, not a lookup key resolving to one.
    leaf_values: list       # rendered per-leaf: int, or ('domain_index', domain_name, index)


@dataclass
class TypeInfo:
    name: str
    leaves: List[Tuple[str, str]]   # (path, type_tokens), fully flattened per §13.1
    instances: List[InstanceInfo]


@dataclass
class ZeroPageAllocation:
    """§10.2: deterministic, non-overlapping 2-byte zero-page blocks,
    one per consumer -- a registry pointer (AoS types only, §13.4: SoA
    needs none) or a dispatch pointer (one per domain with a jump
    table, which on 6502 is every referenced domain, §10.1). Assigned
    in two clearly separated groups, in this fixed order: all
    registry blocks first (declaration order of types), then all
    dispatch blocks (declaration order of domains). Non-overlapping by
    default so a dispatched handler that itself triggers a registry
    lookup or another dispatch is safe rather than merely assumed
    safe."""
    registry_blocks: dict   # type_name -> zero-page base address (2 bytes: base, base+1)
    dispatch_blocks: dict   # domain_name -> zero-page base address (2 bytes: base, base+1)


def _validate_zp_base(zp_base):
    """§10.2: shared validation, used by both gather_ir (fail-fast,
    before gathering anything) and allocate_zero_page (defensive, in
    case it's ever called directly without going through gather_ir
    first)."""
    if zp_base is None:
        raise Export6502Error(
            "--zp-base is required for 6502 export, with no default (§10.2) -- "
            "zero-page is a small, heavily contested resource on real C64 "
            "projects, and the exporter must never silently claim an address "
            "that could collide with a project's existing usage. Supply an "
            "explicit zero-page base address (e.g. --zp-base=0x02).")
    if not (0 <= zp_base <= 0xFF):
        raise Export6502Error(
            f"--zp-base must be a valid zero-page address (0-255 / $00-$FF), "
            f"got {zp_base}")


def allocate_zero_page(zp_base, domains: List[DomainInfo], types: List[TypeInfo],
                        layout: str) -> ZeroPageAllocation:
    """§10.2: --zp-base has no default -- zero-page is small and
    heavily contested on real C64 projects (KERNAL/BASIC routines
    banked in or out, existing hand-managed reservations), so the
    exporter must never silently assume an address is safe. Export
    refuses to proceed without an explicit, valid base."""
    _validate_zp_base(zp_base)

    addr = zp_base
    registry_blocks = {}
    if layout == "aos":
        # SoA needs no registry at all (§13.4) -- no blocks assigned
        # for it regardless of layout.
        for t in types:
            registry_blocks[t.name] = addr
            addr += 2
    dispatch_blocks = {}
    for d in domains:
        dispatch_blocks[d.name] = addr
        addr += 2

    if addr - 1 > 0xFF:
        needed = addr - zp_base
        available = 0x100 - zp_base
        highest_addr = addr - 1
        raise Export6502Error(
            f"zero-page allocation starting at ${zp_base:02x} needs {needed} "
            f"bytes total ({len(registry_blocks) + len(dispatch_blocks)} "
            f"consumers x 2 bytes each), which would reach up to "
            f"${highest_addr:02x} -- only {available} bytes are available "
            f"from ${zp_base:02x} before the zero page ($00-$FF) runs out. "
            "Pick a lower --zp-base or export fewer types/domains in this run.")

    return ZeroPageAllocation(registry_blocks=registry_blocks, dispatch_blocks=dispatch_blocks)


def _leaf_domain_name(type_tokens: str, reg) -> Optional[str]:
    """The identifier domain a leaf field refers to, regardless of
    whether source wrote 'Domain' or '@Domain' -- on 6502 these are
    indistinguishable (§10.1), so this is the single place that
    distinction gets erased for good."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in reg.identifiers:
        return t
    return None


def gather_domains_used(reg, type_names) -> set:
    """Every identifier domain referenced by ANY leaf field (after full
    composition flattening, §13.1) of any type being exported --
    regardless of plain-Domain vs @Domain in source, per §10.1."""
    used = set()
    for type_name in type_names:
        for _path, type_tokens in _flatten_leaves(type_name, reg):
            domain = _leaf_domain_name(type_tokens, reg)
            if domain is not None:
                used.add(domain)
    return used


def check_6502_domain_widths(reg, type_names):
    """§10.1: every identifier domain referenced by anything being
    exported to 6502 must have a declared width. Raises Export6502Error
    naming the domain if not -- checked unconditionally before any
    rendering happens, so a missing width is caught cleanly rather than
    surfacing as some downstream KeyError or silently-wrong index."""
    used = gather_domains_used(reg, type_names)
    missing = sorted(d for d in used if d not in reg.identifier_widths)
    if missing:
        names = ", ".join(f"'{d}'" for d in missing)
        raise Export6502Error(
            f"6502 export requires every referenced identifier domain to "
            f"have a declared width (§10.1, §8.3) -- {names} "
            f"{'has' if len(missing) == 1 else 'have'} no declared width. "
            f"Add one at the domain's own declaration (e.g. 'identifier "
            f"{missing[0]} u8') before 6502 export can proceed."
        )


def gather_domain_info(reg, type_names, emit_all_domains: bool = False) -> List[DomainInfo]:
    """Per-domain index tables (§10.2/§10.3) for every domain actually
    used by what's being exported -- 0-based index, declaration order,
    same numbering §8.4/§13.6's _Indexed companion enum already uses.

    When emit_all_domains is True (§8.5 / --emit-all-domains): every
    domain that has a declared width is emitted regardless of whether
    anything in the exported types references it -- the identical
    constant-table form a referenced domain already produces.  A domain
    with no declared width is unaffected either way (there is nothing to
    force-emit for it).  Default False preserves current behaviour."""
    used = gather_domains_used(reg, type_names)
    domains = []
    for domain_name in reg.identifiers:
        if domain_name not in used and not emit_all_domains:
            continue
        if domain_name not in reg.identifier_widths:
            # No declared width: nothing to emit even under
            # emit_all_domains -- the spec is explicit on this.
            continue
        width = reg.identifier_widths[domain_name]  # guaranteed present, already checked
        block = reg.identifiers[domain_name]
        members = [(entry.key, i) for i, entry in enumerate(block.entries)]
        domains.append(DomainInfo(name=domain_name, width=width, members=members))
    return domains


def _render_leaf_value(value, type_tokens, reg):
    """A single flattened leaf value, in the shared IR's representation.
    Identifier values always become ('domain_index', domain, index) on
    this target (§10.1) -- never the logical ID, regardless of what the
    IdentifierRef itself carries. String values are passed through as
    plain Python str -- each renderer's own emission code handles the
    quoted literal + padding, since the directive syntax differs across
    the three dialects (ACME: `!text`/`!byte`, 64tass: `.text`/`.byte`,
    KickAssembler: `.text`/`.byte`)."""
    if isinstance(value, IdentifierRef):
        domain = value.domain
        block = reg.identifiers[domain]
        index = next(i for i, e in enumerate(block.entries) if e.key == value.key)
        return ("domain_index", domain, index)
    if isinstance(value, str):
        return value   # string N leaf -- kept as Python str, renderer handles emission
    return value  # int/float scalars


def gather_type_info(reg, resolver, type_name) -> TypeInfo:
    leaves = _flatten_leaves(type_name, reg)
    instances = export_instances_for_type(type_name, reg, resolver)
    infos = []
    for index, (name, value) in enumerate(instances):
        flat = _flatten_value(value, type_name, reg)
        rendered = [_render_leaf_value(v, leaves[i][1], reg) for i, v in enumerate(flat)]
        infos.append(InstanceInfo(name=name, index=index, leaf_values=rendered))
    return TypeInfo(name=type_name, leaves=leaves, instances=infos)


def gather_soa_columns(type_info: TypeInfo):
    """§13: SoA projection of the exact same per-instance IR AoS already
    uses -- not a separate data-gathering pass, a transpose of it. Every
    leaf field's values across all instances, in declaration order (the
    same dense index AoS's registry already uses, §13.4/§10.1 -- no
    separate lookup step exists or is needed on this target, since the
    index space is shared between AoS's registry and every SoA field
    array). Returns a list of (path, type_tokens, values), one entry
    per leaf, values ordered by instance declaration order -- kept here
    in the shared step (not per-renderer) so any future dialect reuses
    this exact transpose rather than re-deriving it."""
    columns = []
    for li, (path, type_tokens) in enumerate(type_info.leaves):
        values = [inst.leaf_values[li] for inst in type_info.instances]
        columns.append((path, type_tokens, values))
    return columns


def gather_ir(reg, resolver, type_names, zp_base,
              emit_all_domains: bool = False):
    """Full shared IR for a 6502 export of the given types: validates
    the width rule and the zero-page base first (fails fast, before
    gathering anything), then returns (domains, types) -- domains:
    List[DomainInfo], types: List[TypeInfo]. This is the ONE place all
    three rendering dialects (ACME, KickAssembler, 64tass) read from;
    neither renderer should ever recompute anything this function
    already determined.

    §10.2: zp_base is required, no default -- checked here immediately
    (same fail-fast point as the domain-width check) even though the
    actual block allocation (allocate_zero_page) only happens once
    layout is known, since layout is a render-time axis, independent
    of dialect (§13.6) -- both a bad/missing zp_base and a missing
    domain width are hard preconditions that should never be
    discovered deep into rendering.

    type_names is reordered here to match true declaration order in
    the source (reg.defines' own iteration order) regardless of what
    order the caller listed them in -- "declaration order" (§10.2's
    registry-block ordering, among others) must be a property of the
    .gddl source, not an accident of a CLI's argument order.

    First-pass scope: scalar and identifier-typed leaf fields, plus
    `string N` fields (§13.2). Composition is structurally handled by
    the shared _flatten_leaves/_flatten_value code already; string/AoS
    emission is now implemented in all three renderers. SoA string-field
    emission is not yet implemented -- each renderer currently raises
    for a string field in SoA layout (the directive split into Lo/Hi
    byte arrays doesn't apply to a char array; the right representation
    would be a single labeled region, but that hasn't been designed yet
    and is explicitly left for a future pass rather than silently
    emitting wrong output)."""
    _validate_zp_base(zp_base)
    check_6502_domain_widths(reg, type_names)
    ordered_type_names = [t for t in reg.defines if t in type_names]
    domains = gather_domain_info(reg, ordered_type_names,
                                  emit_all_domains=emit_all_domains)
    types = [gather_type_info(reg, resolver, t) for t in ordered_type_names]
    return domains, types


def render(domains, types, dialect: str = "acme", layout: str = "aos", zp_base=None) -> str:
    """Single dispatch point across every 6502 renderer -- selects by
    name, never re-deriving anything the shared IR already computed.
    Mirrors export_cpp.py's own layout/single-header dispatch pattern.
    §10.3: dialect and layout are fully independent axes; this function
    just forwards layout through to whichever renderer is selected.

    §10.2: zp_base is required, no default -- allocate_zero_page raises
    if missing/invalid. Allocation happens here (not in gather_ir)
    because it depends on layout, which is a render-time axis, known
    only once a specific dialect+layout combination is requested."""
    zp_alloc = allocate_zero_page(zp_base, domains, types, layout)
    if dialect == "acme":
        from export_6502_acme import render_acme
        return render_acme(domains, types, zp_alloc, layout=layout)
    if dialect == "kickassembler":
        from export_6502_kickassembler import render_kickassembler
        return render_kickassembler(domains, types, zp_alloc, layout=layout)
    if dialect == "64tass":
        from export_6502_64tass import render_64tass
        return render_64tass(domains, types, zp_alloc, layout=layout)
    raise ValueError(
        f"unknown dialect {dialect!r} -- must be one of 'acme', "
        "'kickassembler', '64tass'")


def _parse_zp_base(text):
    """Accepts '0x02', '$02', or plain decimal '2' -- whichever style a
    project's own build scripts happen to use."""
    if text is None:
        return None
    t = text.strip()
    if t.startswith("0x") or t.startswith("0X"):
        return int(t, 16)
    if t.startswith("$"):
        return int(t[1:], 16)
    return int(t, 10)


def _cli():
    """--dialect=acme|kickassembler|64tass (default acme, §10.3),
    composing freely with --layout=aos|soa (§13.6) and the required
    --zp-base (§10.2, no default -- argparse has no default= for it,
    so omitting the flag is a hard argparse error, not a silent
    fallback). Not the primary interface used for testing in this
    project so far (that's calling gather_ir + render directly) --
    added because a real selection mechanism is the actual point of
    this flag existing at all, not just a design description."""
    import argparse
    from combine import resolve_inputs, compile_multi, CombineError

    ap = argparse.ArgumentParser(description="GDDL -> 6502 exporter")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--type", dest="types", action="append", required=True,
                     help="type to export (repeatable)")
    ap.add_argument("--dialect", choices=["acme", "kickassembler", "64tass"],
                     default="acme", help="assembler dialect")
    ap.add_argument("--layout", choices=["aos", "soa"], default="aos",
                     help="aos (default) or soa data layout")
    ap.add_argument("--zp-base", required=True,
                     help="zero-page base address, required (e.g. 0x02)")
    ap.add_argument("--emit-all-domains", action="store_true",
                     help="emit every domain's constants, even unreferenced ones (default: off)")
    ap.add_argument("-o", "--output", default=None,
                     help="output path (default: stdout)")
    args = ap.parse_args()

    zp_base = _parse_zp_base(args.zp_base)

    try:
        paths = resolve_inputs(args.source)
    except CombineError as e:
        ap.error(str(e))

    result = compile_multi(paths)
    if result["status"] == "parse_error":
        import sys
        err = result["error"]
        print(f"{err['file']}:{err['line']}: {err['message']}", file=sys.stderr)
        sys.exit(1)
    resolver = result["resolver"]
    import sys
    if not check_and_report(resolver):
        sys.exit(1)
    domains, types = gather_ir(resolver.reg, resolver, args.types, zp_base,
                                emit_all_domains=args.emit_all_domains)
    asm = render(domains, types, dialect=args.dialect, layout=args.layout, zp_base=zp_base)

    if args.output:
        with open(args.output, "w") as f:
            f.write(asm)
    else:
        print(asm)


if __name__ == "__main__":
    _cli()
