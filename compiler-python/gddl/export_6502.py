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

from .export_cpp import (
    _flatten_leaves, _flatten_value, _string_n, export_instances_for_type,
)
from .registry import _try_parse_array_type
from .resolve import IdentifierRef
from .validate import check_and_report


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
    members: List[Tuple[str, int]]  # identifier: (key, 0-based index); flags: (key, real bit value)
    kind: str = "identifier"  # 'identifier' or 'flags' -- flags domains get no jump
                               # table/Dispatch subroutine at all (§10.2's dispatch
                               # machinery is specifically for identifier-typed fields
                               # selecting a handler; flags fields are combinable data,
                               # never dispatched on), just the plain constant lines
                               # every renderer's `for key, value in d.members` loop
                               # already emits unconditionally regardless of kind.


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
class PoolInfo:
    """§22: one `pool TypeName PoolName : N` declaration's shared IR.
    `leaves` is the exact same (path, type_tokens) shape TypeInfo.leaves
    already uses (§13.1 flattening, via _flatten_leaves) -- a pool's
    storage shape must match a named instance's own leaf layout
    field-for-field to ever be usable as the same kind of data."""
    name: str
    type_name: str
    count: int
    leaves: List[Tuple[str, str]]


@dataclass
class PoolFieldRegion:
    """One leaf field's reserved address region within a pool -- either
    one `count`-byte-wide region (byte-width fields, or a `string N`/
    array field's own total byte span), or two parallel `count`-byte
    regions for anything wider than a byte (§10.2's existing Lo/Hi
    split convention, extended to reservation: real values never
    exist to split here, but keeping the SAME two-array shape named
    instances' own SoA columns already use means game code written
    against one works unchanged against the other -- `LDA Field_Lo,X`
    reaches a pool's data exactly the way it reaches a named instance's
    SoA column)."""
    lo_addr: int
    hi_addr: Optional[int]  # None for byte-width (and string/array) fields -- no split needed


@dataclass
class PoolAllocation:
    """§22.4 6502 export: pool_name -> {leaf_path: PoolFieldRegion},
    built by allocate_pool_space. SoA layout only, this pass (AoS pool
    export needs its own pointer-table design, not yet built -- see
    allocate_pool_space's own docstring)."""
    fields: dict  # pool_name -> dict[leaf_path, PoolFieldRegion]


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
        if d.kind != "identifier":
            # flags domains have no Dispatch subroutine at all (§10.2's
            # dispatch machinery only exists for identifier-typed
            # fields selecting a handler) -- allocating a zero-page
            # pointer for one would waste this small, contested
            # resource on something never referenced.
            continue
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


def _leaf_flags_domain_name(type_tokens: str, reg) -> Optional[str]:
    """The flags domain a leaf field refers to, or None. No '@' handling
    needed here (unlike _leaf_domain_name) -- flags never had a
    hash-vs-index duality to carry an '@' prefix for in the first place;
    a plain flags-typed field's type_tokens is always just the bare
    domain name."""
    t = type_tokens.strip()
    if t in reg.flags:
        return t
    return None


def gather_flags_domains_used(reg, type_names) -> set:
    """Every flags domain referenced by any leaf field of any type being
    exported -- same shape as gather_domains_used, separate namespace."""
    used = set()
    for type_name in type_names:
        for _path, type_tokens in _flatten_leaves(type_name, reg):
            domain = _leaf_flags_domain_name(type_tokens, reg)
            if domain is not None:
                used.add(domain)
    return used


def gather_flags_domain_info(reg, type_names, emit_all_domains: bool = False) -> List[DomainInfo]:
    """Per-domain member constant tables for flags domains, same
    DomainInfo shape gather_domain_info already produces for identifier
    domains -- but `members` holds each entry's REAL bit-claim value
    (0, or 1 << claimed bit), not a dense index, and `kind='flags'`
    tells every renderer to skip the jump-table/Dispatch machinery
    (identifier-only, §10.2) while still emitting the plain constant
    lines through the exact same code path. A flags domain always has a
    declared width by construction (§ flags/bN, the grammar requires
    it) -- unlike identifier's optional width, there is no missing-width
    case to check or skip here.

    A member with no registered value (registry.py skipped it -- an
    invalid or losing-duplicate bit claim, already a phase-4 error) is
    omitted here too, matching _render_flags_namespace's identical
    reasoning in export_cpp.py: the build is already blocked regardless
    of what this function does with it."""
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


def _render_leaf_value(value, type_tokens, reg):
    """A single flattened leaf value, in the shared IR's representation.
    Identifier values always become ('domain_index', domain, index) on
    this target (§10.1) -- never the logical ID, regardless of what the
    IdentifierRef itself carries. String values are passed through as
    plain Python str -- each renderer's own emission code handles the
    quoted literal + padding, since the directive syntax differs across
    the three dialects (ACME: `!text`/`!byte`, 64tass: `.text`/`.byte`,
    KickAssembler: `.text`/`.byte`).

    Arrays design: an array-typed leaf's value stays a (possibly
    nested) Python list, recursively converted through this SAME
    function at each leaf position -- identifier/struct/flags elements
    are impossible here (rejected at registration), so only the
    plain-scalar and string branches above are ever actually reached at
    the innermost level; this just threads the recursion down to them."""
    if isinstance(value, IdentifierRef):
        domain = value.domain
        block = reg.identifiers[domain]
        index = next(i for i, e in enumerate(block.entries) if e.key == value.key)
        return ("domain_index", domain, index)
    if isinstance(value, list):
        array_info = _try_parse_array_type(type_tokens.strip())
        if array_info is None:
            raise Export6502Error(
                f"array value {value!r} but declared type {type_tokens!r} "
                "isn't array-shaped -- can't export")
        return _render_array_leaf_value(value, array_info.dims, array_info.element_type, reg)
    if isinstance(value, str):
        return value   # string N leaf -- kept as Python str, renderer handles emission
    return value  # int/float scalars


def _render_array_leaf_value(value, dims, element_type, reg):
    if len(dims) == 1:
        return [_render_leaf_value(v, element_type, reg) for v in value]
    return [_render_array_leaf_value(v, dims[1:], element_type, reg) for v in value]


def flatten_array_ir_value(value, dims):
    """Row-major flatten of an array leaf's (possibly nested) IR value
    into a flat Python list -- every dialect renderer's own AoS
    emission loop needs this same flattening (assembly data directives
    have no nesting concept; a multi-dimensional array is just a flat,
    contiguous sequence of element values in row-major order, matching
    the design's own 'match how C++ does this' layout instruction), so
    it lives here once rather than being reimplemented per dialect."""
    if len(dims) == 1:
        return list(value)
    flat = []
    for v in value:
        flat.extend(flatten_array_ir_value(v, dims[1:]))
    return flat


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
    # flags domains share the exact same DomainInfo shape and the exact
    # same per-renderer "for d in domains: emit constant lines" code
    # path -- appended into the SAME list (kind='flags' tells each
    # renderer, and allocate_zero_page above, to skip the identifier-only
    # dispatch machinery) rather than threaded through as a separate
    # return value, so no existing caller's `domains, types = gather_ir(...)`
    # unpacking needs to change.
    domains += gather_flags_domain_info(reg, ordered_type_names,
                                         emit_all_domains=emit_all_domains)
    types = [gather_type_info(reg, resolver, t) for t in ordered_type_names]
    return domains, types


_POOL_SCALAR_WIDTH_BYTES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2}
_POOL_DOMAIN_WIDTH_BYTES = {"u8": 1, "u16": 2, "u32": 4, "u64": None}  # matches _WIDTH_TO_DIRECTIVE's own u64 gap


def gather_pool_info(reg, ordered_type_names) -> List[PoolInfo]:
    """§22: every declared pool whose own TypeName is among the types
    actually being exported this run (--type selection) -- a pool needs
    its type's leaf layout to mean anything, and there is no separate
    --pool selection flag; asking to export a type already pulls in
    whatever pools exist for it, the same way named instances need no
    separate opt-in beyond --type. Declaration order preserved (reg.pools
    is an insertion-ordered dict), matching every other construct's own
    ordering convention on this target."""
    return [
        PoolInfo(name=name, type_name=node.type_name, count=node.count,
                 leaves=_flatten_leaves(node.type_name, reg))
        for name, node in reg.pools.items()
        if node.type_name in ordered_type_names
    ]


def _leaf_total_bytes(type_tokens: str, domain_widths: dict):
    """Total byte span of ONE leaf value, and whether it's eligible for
    the Lo/Hi split convention (§10.2) -- returns (total_bytes,
    splittable). Only a plain 2-byte scalar/identifier-typed leaf is
    splittable; a `string N` or array-typed leaf is always one
    contiguous byte-run per slot (§13.2/§21 -- "low byte of a
    string" has no meaning). `domain_widths` is domain_name -> width
    string, covering identifier AND flags domains uniformly (the same
    combined dict every dialect renderer already builds from `domains:
    List[DomainInfo]`, §10.2's own "flags domains share the exact same
    DomainInfo shape" design) -- deliberately not `reg` itself, so this
    function only ever touches the shared IR, never reaches back into
    the registry the way no other renderer-adjacent code on this target
    does either. Domain-width validation itself already happened in
    check_6502_domain_widths (called from gather_ir, over the same
    _flatten_leaves output a pool's own type produces) -- this function
    trusts that already ran and just reads the now-guaranteed-present
    width."""
    t = type_tokens.strip()
    n = _string_n(t)
    if n is not None:
        return n, False
    array_info = _try_parse_array_type(t)
    if array_info is not None:
        elem_bytes, _ = _leaf_total_bytes(array_info.element_type, domain_widths)
        total_elements = 1
        for d in array_info.dims:
            total_elements *= d
        return elem_bytes * total_elements, False
    domain = t[1:].strip() if t.startswith("@") else t
    if domain in domain_widths:
        width = domain_widths[domain]
        nbytes = _POOL_DOMAIN_WIDTH_BYTES.get(width)
        if nbytes is None:
            raise Export6502Error(
                f"6502 pool export doesn't support {width}-wide domains yet")
        return nbytes, nbytes == 2
    if t in _POOL_SCALAR_WIDTH_BYTES:
        nbytes = _POOL_SCALAR_WIDTH_BYTES[t]
        return nbytes, nbytes == 2
    raise Export6502Error(f"6502 pool export doesn't support field type {type_tokens!r} yet")


def _validate_pool_base(pool_base):
    """§22.4: required only when at least one pool is actually being
    exported (checked at the call site, not here) -- same 'no silent
    claim' discipline --zp-base already established (§10.2), but over
    the full 16-bit address space (real RAM addressing), not zero page."""
    if pool_base is None:
        raise Export6502Error(
            "--pool-base is required when exporting a pool (§22.4) -- "
            "pool storage is real RAM the exporter must never silently "
            "claim an address for. Supply an explicit base address "
            "(e.g. --pool-base=0xa000) naming RAM your project has "
            "actually reserved for this.")
    if not (0 <= pool_base <= 0xFFFF):
        raise Export6502Error(
            f"--pool-base must be a valid 16-bit address (0-65535 / "
            f"$0000-$ffff), got {pool_base}")


def allocate_pool_space(pool_base, pools: List[PoolInfo], layout: str,
                         domains: List[DomainInfo]) -> PoolAllocation:
    """§22.4: assigns every pool leaf field its own non-overlapping
    address region, as plain symbolic constants (`Label = $addr`) -- NOT
    PC-tracked emitted bytes. Confirmed directly against the real ACME
    binary: a `* = * + N` PC advance under --format plain still costs N
    real zero-bytes in the output file (ACME can't represent a gap in a
    flat binary), but a plain `Label = expression` constant assignment
    costs nothing at all -- the exact same reason --zp-base's own
    registry/dispatch pointers (§10.2) are already emitted as bare
    constants, never as reserved-and-emitted bytes. This is what makes
    pool reservation genuinely free of file/tape/disk cost on this
    target, matching §22.4's own stated design goal.

    SoA layout only, this pass -- 6502's AoS mode is ALWAYS a pointer
    list (§13.7: no linear-AoS alternative exists on this target,
    unlike C++), so an AoS pool would need its own precomputed Lo/Hi
    pointer table (one entry per slot, matching the existing AoS
    registry's own shape) to avoid an arbitrary index*record_size
    multiply at runtime -- a real, separate design not yet built.
    Raises clearly rather than emitting something silently wrong if
    layout='aos' and at least one pool exists.

    Field ordering, and therefore address assignment, follows
    PoolInfo.leaves' own order (§13.1 flattening order) within each
    pool, and reg.pools' own declaration order across pools -- the same
    'declaration order, never alphabetized' discipline every other
    allocator on this target already follows."""
    if not pools:
        # Nothing to allocate -- --pool-base stays unrequired for a
        # compile with no pools, same "only required when actually
        # needed" precedent --emit-ids-manifest's -o requirement
        # already established elsewhere in this project.
        return PoolAllocation(fields={})
    if layout != "soa":
        raise Export6502Error(
            "6502 AoS pool export is not implemented yet (§22.4) -- AoS "
            "on this target is always a pointer list (§13.7), which "
            "would need its own precomputed index->address table design "
            "for anonymous, non-identity-bearing pool slots; use "
            "--layout soa for pools on 6502 for now.")
    _validate_pool_base(pool_base)
    domain_widths = {d.name: d.width for d in domains}
    addr = pool_base
    fields = {}
    for pool in pools:
        field_regions = {}
        for path, type_tokens in pool.leaves:
            total_bytes, splittable = _leaf_total_bytes(type_tokens, domain_widths)
            if splittable:
                lo = addr
                addr += pool.count
                hi = addr
                addr += pool.count
                field_regions[path] = PoolFieldRegion(lo_addr=lo, hi_addr=hi)
            else:
                lo = addr
                addr += total_bytes * pool.count
                field_regions[path] = PoolFieldRegion(lo_addr=lo, hi_addr=None)
        fields[pool.name] = field_regions

    if addr - 1 > 0xFFFF:
        needed = addr - pool_base
        available = 0x10000 - pool_base
        raise Export6502Error(
            f"pool allocation starting at ${pool_base:04x} needs {needed} "
            f"bytes total, which would reach up to ${addr - 1:04x} -- only "
            f"{available} bytes are available from ${pool_base:04x} before "
            "the 16-bit address space runs out. Pick a lower --pool-base "
            "or export fewer/smaller pools in this run.")

    return PoolAllocation(fields=fields)


def render(domains, types, dialect: str = "acme", layout: str = "aos", zp_base=None,
           pools=None, pool_base=None) -> str:
    """Single dispatch point across every 6502 renderer -- selects by
    name, never re-deriving anything the shared IR already computed.
    Mirrors export_cpp.py's own layout/single-header dispatch pattern.
    §10.3: dialect and layout are fully independent axes; this function
    just forwards layout through to whichever renderer is selected.

    §10.2: zp_base is required, no default -- allocate_zero_page raises
    if missing/invalid. Allocation happens here (not in gather_ir)
    because it depends on layout, which is a render-time axis, known
    only once a specific dialect+layout combination is requested.

    §22.4: `pools`/`pool_base` are additive, both default to None/empty
    so every pre-existing caller (this function's own signature grew,
    not changed) keeps working unchanged with zero pools. allocate_pool_
    space is a no-op (empty PoolAllocation, no --pool-base requirement)
    when `pools` is empty, same "only required when actually needed"
    precedent --zp-base's own sibling parameter does NOT follow (zp_base
    is unconditionally required) -- deliberately different here, since
    unlike zero-page (already load-bearing for every domain's dispatch
    machinery), most compiles have no pools at all and forcing an unused
    --pool-base on every one of them would violate this project's own
    aversion to demanding input nothing downstream needs."""
    zp_alloc = allocate_zero_page(zp_base, domains, types, layout)
    pool_alloc = allocate_pool_space(pool_base, pools or [], layout, domains)
    if dialect == "acme":
        from .export_6502_acme import render_acme
        return render_acme(domains, types, zp_alloc, layout=layout,
                            pools=pools, pool_alloc=pool_alloc)
    if dialect == "kickassembler":
        from .export_6502_kickassembler import render_kickassembler
        return render_kickassembler(domains, types, zp_alloc, layout=layout,
                                     pools=pools, pool_alloc=pool_alloc)
    if dialect == "64tass":
        from .export_6502_64tass import render_64tass
        return render_64tass(domains, types, zp_alloc, layout=layout,
                              pools=pools, pool_alloc=pool_alloc)
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
    from .combine import resolve_inputs, compile_multi, CombineError
    from .export_ids import write_ids_manifest

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
    ap.add_argument("--pool-base", default=None,
                     help="RAM base address for pool storage (§22.4), required only "
                          "if the exported types have any pools (e.g. 0xa000)")
    ap.add_argument("--emit-all-domains", action="store_true",
                     help="emit every domain's constants, even unreferenced ones (default: off)")
    ap.add_argument("--emit-ids-manifest", action="store_true",
                     help="also write <output>.gddlids.json, every identifier/flags "
                          "domain declared, for cross-mod script references (default: off)")
    ap.add_argument("-o", "--output", default=None,
                     help="output path (default: stdout)")
    ap.add_argument("--verbose-errors", action="store_true",
                     help="tag each error with its internal [phase N, check] (default: off)")
    args = ap.parse_args()

    if args.emit_ids_manifest and not args.output:
        ap.error("--emit-ids-manifest requires -o/--output -- there is no "
                 "output stem to name the manifest after when writing to stdout")

    zp_base = _parse_zp_base(args.zp_base)
    pool_base = _parse_zp_base(args.pool_base) if args.pool_base is not None else None

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
    if not check_and_report(resolver, verbose=args.verbose_errors):
        sys.exit(1)
    domains, types = gather_ir(resolver.reg, resolver, args.types, zp_base,
                                emit_all_domains=args.emit_all_domains)
    ordered_type_names = [t.name for t in types]
    pools = gather_pool_info(resolver.reg, ordered_type_names)
    asm = render(domains, types, dialect=args.dialect, layout=args.layout, zp_base=zp_base,
                 pools=pools, pool_base=pool_base)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(asm)
    else:
        print(asm)

    if args.emit_ids_manifest:
        manifest_path = write_ids_manifest(resolver.reg, args.output, resolver=resolver)
        print(f"wrote {manifest_path}")


if __name__ == "__main__":
    _cli()
