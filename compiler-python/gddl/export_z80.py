# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Z80 export (§16): shared, toolchain-agnostic IR.

Mirrors export_6502.py's architecture directly, per §16.1's own framing:
"following the 6502 exporter's architecture directly ... the same
design, a different assembler syntax to target." The Z80 has no
hardware multiply instruction at all -- the same fundamental limitation
as 6502, not 68000's "available but slow" -- so the identity system
(dense declaration-order indices, no logical IDs, no instance stable
IDs) and the multiply-avoidance discipline both carry over unchanged.
This is not a new design decision; §9's "fully static, no live
patching" reasoning is about physical-media distribution, not CPU
capability, and applies identically to Z80/ZX Spectrum's tape/disk
model.

Two toolchains, three output paths total (§16.1) -- this module is the
ONE shared IR all of them read from, mirroring how export_6502.py is
shared across ACME/KickAssembler/64tass:
  - SjASMPlus (assembly only) -- export_z80_sjasmplus.py, built first.
  - z88dk assembly mode -- export_z80_z88dk_asm.py, built second, its
    own renderer against this same IR (a genuinely different assembler
    from SjASMPlus, needing its own real syntax investigation).
  - z88dk C mode -- export_z80_z88dk_c.py, built third. Follows the
    C++/68000 implementation *style* (real structs, real compiler) but
    keeps this SAME 6502-style identity/multiply-avoidance IR
    underneath, per §16.1's explicit call-out that C-vs-asm is an
    implementation-style choice, independent of the identity system,
    which is a CPU-level fact. Targets C89 via zsdcc ONLY (sccz80 is
    ruled out by §16.1's enumerated-multiplier cliff), and emits a
    header/.c pair rather than a single file (§16.2.1).

Deliberately duplicates the small amount of domain-identity logic from
export_6502.py rather than cross-importing it -- consistent with this
project's established practice of keeping each target's shared module
self-contained (the same reasoning already applied to keeping
export_68000.py independent of export_6502.py, even though their
identity systems are related).

One genuine simplification versus 6502, not carried over blindly:
**no zero-page-equivalent scratch-memory allocation is needed at all.**
6502's registry/dispatch design needed a hand-managed 2-byte zero-page
pointer per consumer specifically because the 6502 is register-starved
(effectively one 8-bit accumulator plus X/Y index registers) and has
no register-only way to hold a computed 16-bit address. The Z80 has a
genuinely richer register set -- HL/DE/BC as real 16-bit pairs, plus
IX/IY -- so the whole address computation can happen entirely in
registers (see each renderer's Dispatch/Find bodies), with no
scratch memory, no --zp-base equivalent, and no per-consumer allocation
step at all. This isn't a design choice made a priori -- it's a direct
consequence of what registers the Z80 actually has, checked before
assuming 6502's zero-page scheme would transfer literally.

Table shape, Z80-only, deliberately NOT shared with 6502: both
renderers use a single combined table of 2-byte (`dw`) entries per
domain/type, indexed by `index * 2` (one cheap `add hl,hl` -- doubling
is not the multiply this whole discipline exists to avoid; an
*arbitrary* per-entry-size multiply is), read via `ld a,(hl) / inc hl /
ld h,(hl) / ld l,a`. This replaces an earlier split Lo/Hi two-array
design (still exactly what 6502 uses, unchanged) -- the two CPUs
genuinely diverge here: Z80's richer register set makes zero-extending
the index into HL once, then doubling it, cheaper than 6502's
constraints allow, while 6502's native indexed addressing already
gives free two-array access with no equivalent doubling cost to avoid
by combining them. Switching 6502 to match would cost an extra shift
with no offsetting savings -- so 6502 stays exactly as it was, and this
is not "the Z80 way is generally better," just what actually fits each
CPU's real register set.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .export_cpp import export_instances_for_type, _flatten_leaves, _flatten_value, _string_n
from .registry import _try_parse_array_type
from .resolve import IdentifierRef
from .validate import check_and_report


class ExportZ80Error(Exception):
    """A Z80-export-time error -- distinct from anything phase 4-8
    already raises, since the front-end has no concept of export
    targets at all. Always names the specific thing that's wrong."""
    pass


@dataclass
class DomainInfo:
    name: str
    width: str
    members: List[Tuple[str, int]]  # identifier: (key, 0-based index); flags: (key, real bit value)
    kind: str = "identifier"  # 'identifier' or 'flags' -- see export_6502.py's DomainInfo
                               # for the full reasoning (flags domains get no jump
                               # table/dispatch machinery at all, just constant lines)


@dataclass
class InstanceInfo:
    name: str
    index: int              # dense, declaration-order position -- the identity itself
    leaf_values: list        # rendered per-leaf: int, or ('domain_index', domain_name, index)


@dataclass
class TypeInfo:
    name: str
    leaves: List[Tuple[str, str]]   # (path, type_tokens), fully flattened per §13.1
    instances: List[InstanceInfo]


@dataclass
class PoolInfo:
    """§22: one `pool TypeName PoolName : N` declaration's shared IR --
    mirrors export_6502.py's PoolInfo (same shape, this target's own
    module per this file's own established "duplicate rather than
    cross-import" convention)."""
    name: str
    type_name: str
    count: int
    leaves: List[Tuple[str, str]]


@dataclass
class PoolFieldRegion:
    """One leaf field's reserved address region within a pool -- a
    SINGLE `count`-byte-wide (or 2*count-byte-wide, for a u16 field)
    region, never Lo/Hi split -- unlike 6502, this target has real
    16-bit register pairs, so a u16 SoA field array is already one
    contiguous array on this target (see this module's own docstring,
    'Table shape, Z80-only... indexed by index * 2, one cheap add
    hl,hl'), and pool reservation follows that exact same shape."""
    addr: int
    width_bytes: int  # 1 or 2 -- how many bytes ONE slot occupies in this region


@dataclass
class PoolAllocation:
    """§22.4 Z80 export: pool_name -> {leaf_path: PoolFieldRegion},
    built by allocate_pool_space. SoA layout only, this pass -- see
    that function's own docstring for why AoS is deferred here too."""
    fields: dict  # pool_name -> dict[leaf_path, PoolFieldRegion]


def _leaf_domain_name(type_tokens: str, reg):
    """The identifier domain a leaf field refers to, regardless of
    whether source wrote 'Domain' or '@Domain' -- on Z80, exactly as
    on 6502 (§16's own opening paragraph), these are indistinguishable:
    every identifier-typed field is always a dense index."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in reg.identifiers:
        return t
    return None


def gather_domains_used(reg, type_names) -> set:
    """Every identifier domain referenced by any leaf field (after full
    composition flattening, §13.1) of any type being exported."""
    used = set()
    for type_name in type_names:
        for _path, type_tokens in _flatten_leaves(type_name, reg):
            domain = _leaf_domain_name(type_tokens, reg)
            if domain is not None:
                used.add(domain)
    return used


def check_z80_domain_widths(reg, type_names):
    """Every identifier domain referenced by anything exported to Z80
    must have a declared width -- same requirement and same reason as
    6502/68000: something has to determine the storage width (and
    therefore the split-array element size) for the domain's index,
    and there's no other source for that decision."""
    used = gather_domains_used(reg, type_names)
    missing = sorted(d for d in used if d not in reg.identifier_widths)
    if missing:
        names = ", ".join(f"'{d}'" for d in missing)
        raise ExportZ80Error(
            f"Z80 export requires every referenced identifier domain to "
            f"have a declared width (§16, §8.3) -- {names} "
            f"{'has' if len(missing) == 1 else 'have'} no declared width. "
            f"Add one at the domain's own declaration (e.g. 'identifier "
            f"{missing[0]} u8') before Z80 export can proceed."
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
    """The flags domain a leaf field refers to, or None. No '@' handling
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
    index, and `kind='flags'` tells every renderer to skip jump-table/
    dispatch emission (see export_6502.py's identical function for the
    full reasoning, shared verbatim across every target)."""
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
    this target (no logical IDs, ever), exactly as on 6502.

    Arrays design: an array-typed leaf's value stays a (possibly
    nested) Python list, recursively converted through this SAME
    function at each leaf position, exactly mirroring export_6502.py's
    own array handling (identifier/struct/flags elements are impossible
    here -- rejected at registration -- so only the plain-scalar/string
    passthrough below is ever actually reached at the innermost level)."""
    if isinstance(value, IdentifierRef):
        domain = value.domain
        block = reg.identifiers[domain]
        index = next(i for i, e in enumerate(block.entries) if e.key == value.key)
        return ("domain_index", domain, index)
    if isinstance(value, list):
        array_info = _try_parse_array_type(type_tokens.strip())
        if array_info is None:
            raise ExportZ80Error(
                f"array value {value!r} but declared type {type_tokens!r} "
                "isn't array-shaped -- can't export")
        return _render_array_leaf_value(value, array_info.dims, array_info.element_type, reg)
    return value


def _render_array_leaf_value(value, dims, element_type, reg):
    if len(dims) == 1:
        return [_render_leaf_value(v, element_type, reg) for v in value]
    return [_render_array_leaf_value(v, dims[1:], element_type, reg) for v in value]


def flatten_array_ir_value(value, dims):
    """Row-major flatten of an array leaf's (possibly nested) IR value
    into a flat Python list -- see export_6502.py's identical helper
    for the full reasoning (assembly data directives have no nesting
    concept)."""
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


def gather_soa_columns(type_info):
    """§13.7/§13.4: transpose row-major (per-instance) leaf_values,
    already fully flattened through composition by gather_type_info
    regardless of layout, into column-major (per-field) arrays -- one
    per leaf, values in the same declaration order the dense AoS index
    already uses (§13.4: SoA needs no separate lookup at all on a
    dense-index target; the same index that finds an AoS instance
    indexes every SoA field array too). No re-flattening or re-
    rendering here -- leaf_values already went through
    _render_leaf_value once in gather_type_info; reused as-is."""
    columns = []
    for li, (path, type_tokens) in enumerate(type_info.leaves):
        values = [inst.leaf_values[li] for inst in type_info.instances]
        columns.append((path, type_tokens, values))
    return columns


def gather_ir(reg, resolver, type_names, emit_all_domains: bool = False):
    """Full shared IR for a Z80 export of the given types. Validates
    the width rule first (fails fast, before gathering anything), same
    discipline as 6502/68000. Returns (domains, types)."""
    check_z80_domain_widths(reg, type_names)
    ordered_type_names = [t for t in reg.defines if t in type_names]
    domains = gather_domain_info(reg, ordered_type_names,
                                  emit_all_domains=emit_all_domains)
    domains += gather_flags_domain_info(reg, ordered_type_names,
                                         emit_all_domains=emit_all_domains)
    types = [gather_type_info(reg, resolver, t) for t in ordered_type_names]
    return domains, types


def gather_pool_info(reg, ordered_type_names) -> List[PoolInfo]:
    """§22: every declared pool whose own TypeName is among the types
    actually being exported this run (--type selection) -- same
    reasoning as export_6502.py's identical function: a pool needs its
    type's leaf layout to mean anything, and there's no separate --pool
    selection flag."""
    return [
        PoolInfo(name=name, type_name=node.type_name, count=node.count,
                 leaves=_flatten_leaves(node.type_name, reg))
        for name, node in reg.pools.items()
        if node.type_name in ordered_type_names
    ]


_POOL_SCALAR_WIDTH_BYTES = {"u8": 1, "i8": 1, "u16": 2, "i16": 2}
_POOL_DOMAIN_WIDTH_BYTES = {"u8": 1, "u16": 2, "u32": 4, "u64": None}


def _pool_leaf_width_bytes(type_tokens: str, domain_widths: dict) -> int:
    """Byte width of ONE leaf value for pool reservation -- §22.4.

    `string N` and array-typed leaves are REJECTED, not sized -- the
    identical reason (and identical mistake first made, then corrected,
    on the 6502 target -- see HANDOFF.md's own correction entry) applies
    here just as directly, in fact more explicitly, since THIS module's
    own docstring already states it plainly for named instances: 'string
    N fields are not yet supported in --layout=soa... the field's width
    isn't guaranteed a power of two, so indexing it would need a real
    multiply, not the cheap shift every scalar SoA field uses.' A pool's
    reserved string/array field would need the exact same `base + i *
    stride` indexing at runtime a named instance's would, so it gets the
    exact same rejection, for the exact same reason -- this was designed
    correctly from the start on THIS target specifically because the
    6502 mistake was caught and fixed first."""
    t = type_tokens.strip()
    if _string_n(t) is not None:
        raise ExportZ80Error(
            f"Z80 pool export doesn't support string N leaf fields under "
            f"--layout soa yet (field type {type_tokens!r}) -- matching "
            "this target's existing named-instance SoA limitation: a "
            "string field's width isn't guaranteed a power of two, so "
            "indexing pool slot i's string would need a real multiply, "
            "not the cheap shift every scalar SoA field uses.")
    if _try_parse_array_type(t) is not None:
        raise ExportZ80Error(
            f"Z80 pool export doesn't support array-typed leaf fields "
            f"under --layout soa yet (field type {type_tokens!r}) -- same "
            "reason as string N fields just above: indexing pool slot "
            "i's array would need a real multiply for a non-power-of-two "
            "element stride.")
    domain = t[1:].strip() if t.startswith("@") else t
    if domain in domain_widths:
        width = domain_widths[domain]
        nbytes = _POOL_DOMAIN_WIDTH_BYTES.get(width)
        if nbytes is None:
            raise ExportZ80Error(f"Z80 pool export doesn't support {width}-wide domains yet")
        return nbytes
    if t in _POOL_SCALAR_WIDTH_BYTES:
        return _POOL_SCALAR_WIDTH_BYTES[t]
    raise ExportZ80Error(f"Z80 pool export doesn't support field type {type_tokens!r} yet")


def _validate_pool_base(pool_base):
    """§22.4: required only when at least one pool is actually being
    exported (checked at the call site) -- same 'no silent claim'
    discipline as export_6502.py's --zp-base/--pool-base, over the full
    16-bit address space (this target has no zero-page-equivalent
    scratch concept at all, per this module's own docstring, but pool
    DATA still needs a real memory address somewhere -- an orthogonal
    need, unaffected by that simplification)."""
    if pool_base is None:
        raise ExportZ80Error(
            "--pool-base is required when exporting a pool (§22.4) -- "
            "pool storage is real RAM the exporter must never silently "
            "claim an address for. Supply an explicit base address "
            "(e.g. --pool-base=0xa000) naming RAM your project has "
            "actually reserved for this.")
    if not (0 <= pool_base <= 0xFFFF):
        raise ExportZ80Error(
            f"--pool-base must be a valid 16-bit address (0-65535 / "
            f"$0000-$ffff), got {pool_base}")


def allocate_pool_space(pool_base, pools: List[PoolInfo], layout: str,
                         domains: List[DomainInfo]) -> PoolAllocation:
    """§22.4: assigns every pool leaf field its own non-overlapping
    address region, as plain symbolic constants (`EQU`, both SjASMPlus
    and z88dk-asm) -- confirmed directly against real SjASMPlus (v1.24.0)
    that this costs zero output bytes under --raw output, mirroring the
    identical finding already confirmed on 6502 (ACME/64tass/
    KickAssembler all agree: a bare constant assignment costs nothing;
    a PC-advancing directive still emits real bytes under a flat binary
    format).

    SoA layout only, this pass -- unlike 6502, this target's existing
    AoS --z80-pointer-table=off path already has a general shift-add
    multiply routine (shift_add_multiply, this module) for arbitrary
    record sizes, so an AoS pool is more tractable here than on 6502 in
    principle, but wiring it up (precomputing/reusing that sequence for
    pool-slot indexing specifically, plus deciding how a pointer-table
    AoS pool would even work with no named instances to point at) is
    real, separate, unbuilt design -- deferred here too, for scope
    consistency with the 6502 pass, not because it's equally hard."""
    if not pools:
        return PoolAllocation(fields={})
    if layout != "soa":
        raise ExportZ80Error(
            "Z80 AoS pool export is not implemented yet (§22.4) -- use "
            "--layout soa for pools on this target for now; AoS pool "
            "indexing (via a pointer table or this target's own "
            "shift-add multiply routine) is real, separate, unbuilt "
            "design.")
    _validate_pool_base(pool_base)
    domain_widths = {d.name: d.width for d in domains}
    addr = pool_base
    fields = {}
    for pool in pools:
        field_regions = {}
        for path, type_tokens in pool.leaves:
            width_bytes = _pool_leaf_width_bytes(type_tokens, domain_widths)
            field_regions[path] = PoolFieldRegion(addr=addr, width_bytes=width_bytes)
            addr += width_bytes * pool.count
        fields[pool.name] = field_regions

    if addr - 1 > 0xFFFF:
        needed = addr - pool_base
        available = 0x10000 - pool_base
        raise ExportZ80Error(
            f"pool allocation starting at ${pool_base:04x} needs {needed} "
            f"bytes total, which would reach up to ${addr - 1:04x} -- only "
            f"{available} bytes are available from ${pool_base:04x} before "
            "the 16-bit address space runs out. Pick a lower --pool-base "
            "or export fewer/smaller pools in this run.")

    return PoolAllocation(fields=fields)


def _leaf_size_bytes(type_tokens: str, reg) -> int:
    """Storage width of one flattened leaf, in bytes. Identifier-typed
    leaves size by their DOMAIN's declared width (what's stored is the
    domain index, not the field's nominal type) -- the same rule
    _leaf_directive already applies when picking db/dw."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in reg.identifier_widths:
        t = reg.identifier_widths[t]
    if t in ("u8", "i8"):
        return 1
    if t in ("u16", "i16"):
        return 2
    n = _string_n(type_tokens)
    if n is not None:
        # §13.2: a `string N` field is N bytes total, fixed-size,
        # never a pointer or length-prefixed scheme -- the same rule
        # export_cpp.py already follows for POD/trivial-copyability.
        # This is very often NOT a power of two (unlike most u8/u16
        # combinations), which is exactly what exercises the
        # --z80-pointer-table=off shift-add path's `add hl,de`
        # accumulation branch (shift_add_multiply/needs_index_copy
        # below), already verified for every size 1..64 on the real
        # emulator.
        return n

    array_info = _try_parse_array_type(type_tokens.strip())
    if array_info is not None:
        # Arrays design: total width = element width * total element
        # count, row-major/contiguous, no padding -- the same
        # computation export_cpp.py's binary/schema path uses.
        elem_width = _leaf_size_bytes(array_info.element_type, reg)
        total_count = 1
        for d in array_info.dims:
            total_count *= d
        return elem_width * total_count

    raise ExportZ80Error(
        f"Z80 export doesn't support field type {type_tokens!r} yet "
        "(scalar u8/u16/i8/i16, identifier-typed, string N, and array "
        "leaf fields only)")


def type_sizeof(type_info, reg) -> int:
    """sizeof({Type}) in bytes -- the AoS stride. Needed by the
    direct-indexing path (--z80-pointer-table=off), where {Type}_Find
    computes Instances + index*sizeof instead of dereferencing a
    pointer table, and by §16.2's crossover guidance."""
    return sum(_leaf_size_bytes(tokens, reg) for _path, tokens in type_info.leaves)


def asm_string_literal(s: str) -> str:
    """Escapes a Python string for a Z80 assembler `db "..."` literal
    (§13.2). Confirmed directly on both real built assemblers
    (SjASMPlus and z88dk-z80asm), not assumed identical from the spec
    text alone, given this project's repeated experience of these two
    dialects disagreeing on small points:
      - Both pass raw multi-byte UTF-8 sequences straight through
        byte-for-byte inside a quoted literal (e.g. U+00FC 'u-umlaut'
        -> 0xC3 0xBC unchanged) -- confirmed by writing a source file
        containing the literal UTF-8 bytes and checking the assembled
        output byte-for-byte, on both assemblers.
      - Both accept a backslash-escaped embedded double quote (\\")
        identically -- confirmed the same way.
    So the only escaping needed is backslash-then-quote, the same rule
    export_cpp.py's _cpp_string_literal already uses for C++ -- nothing
    UTF-8-specific required, since neither assembler reinterprets or
    reencodes non-ASCII bytes."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def render_string_leaf(value: str, n: int, path: str, directive: str = "db") -> str:
    """One §13.2-compliant instance-data line for a `string N` leaf: a
    quoted, human-readable literal followed by exactly enough explicit
    zero bytes to reach N total -- e.g. `db "Grubnik", 0, 0` for a
    `string 9` field holding a 7-byte value. NEVER a byte-by-byte hex
    list for the readable content -- that defeats the entire point of
    generated output being human-checkable.

    Length/encoding are NOT re-validated here: by the time a value
    reaches export it has already passed phase 1-8 validation (UTF-8
    byte length <= N-1, checked at point of storage). The len(content)
    > n check below is a defensive backstop matching this project's
    established pattern elsewhere (e.g. phase 5's checks staying as
    backstops in phase 6) -- it should never actually fire."""
    content = value.encode("utf-8")
    if len(content) > n:
        raise ExportZ80Error(
            f"string field {path!r} has a {len(content)}-byte UTF-8 value, "
            f"which doesn't fit in string {n} ({n - 1} usable bytes) -- "
            "this should already have been rejected before export ever ran")
    padding = n - len(content)
    if content:
        items = [asm_string_literal(value)] + ["0"] * padding
    else:
        items = ["0"] * n
    return f"\t{directive} {', '.join(items)}\t; {path}"


def shift_add_multiply(n: int) -> list:
    """Decompose a constant multiply into doublings and adds -- the
    "exporter-emitted shift-add index computation" §16.1.1 refers to
    for the --z80-pointer-table=off path.

    Contract: on entry HL = index and (when n is not a power of two)
    DE = index too; on exit HL = index * n. Returns mnemonic suffixes
    only, so each renderer applies its own indentation/formatting.

    Doubling is a shift, not the arbitrary runtime multiply this whole
    target exists to avoid (§16.1) -- and unlike sccz80's enumerated
    inline-multiply list, this works for every n, which is exactly why
    §16.1 rules sccz80 out and zsdcc in."""
    if n < 1:
        raise ExportZ80Error(f"type size must be >= 1, got {n}")
    bits = bin(n)[3:]           # binary minus the leading '1' (the MSB)
    seq = []
    for bit in bits:
        seq.append("add hl, hl")
        if bit == "1":
            seq.append("add hl, de")
    return seq


def needs_index_copy(n: int) -> bool:
    """Whether the shift-add sequence for n ever reads DE (i.e. n is not
    a power of two). Lets the renderers skip the `ld d,h / ld e,l`
    index copy entirely in the common power-of-two case."""
    return bin(n).count("1") > 1


def render(domains, types, toolchain: str = "sjasmplus", z88dk_output: str = "asm",
           pointer_table: bool = None, find_macro: bool = False, reg=None,
           layout: str = "aos", pools=None, pool_base=None):
    """Single dispatch point (§16.3): --z80-toolchain=sjasmplus|z88dk,
    --z88dk-output=asm|c (meaningful only for z88dk; rejected otherwise,
    same "flag combination must make sense together" discipline as
    --dialect/--layout for 6502), --z80-pointer-table=on|off,
    --layout=aos|soa (§13.7).

    `pointer_table` is deliberately `None`-by-default rather than True or
    False: §16.2 makes it a mandatory, no-default flag (the --zp-base
    precedent), so omitting it is an error rather than something the
    exporter quietly guesses. Returns a str for the assembly paths, and
    a {filename_suffix: text} dict for C mode's header/.c split (§16.2.1)."""
    if layout not in ("aos", "soa"):
        raise ValueError(f"layout must be 'aos' or 'soa', got {layout!r}")
    if pointer_table is None:
        raise ExportZ80Error(
            "--z80-pointer-table=on|off is required for every Z80 export "
            "(§16.2/§16.3) -- it is a resource/performance tradeoff the "
            "exporter cannot make on the developer's behalf, following the "
            "same precedent as --zp-base (§10.2). Pass =on to emit a "
            "{Type}_Registry pointer table alongside {Type}_Instances, or "
            "=off for direct index*sizeof addressing.")
    pool_alloc = allocate_pool_space(pool_base, pools or [], layout, domains)
    if toolchain == "sjasmplus":
        if z88dk_output != "asm":
            raise ValueError(
                "--z88dk-output is only meaningful with "
                "--z80-toolchain=z88dk (§16.3)")
        from .export_z80_sjasmplus import render_sjasmplus
        return render_sjasmplus(domains, types, pointer_table=pointer_table,
                                find_macro=find_macro, reg=reg, layout=layout,
                                pools=pools, pool_alloc=pool_alloc)
    if toolchain == "z88dk":
        if z88dk_output == "asm":
            from .export_z80_z88dk_asm import render_z88dk_asm
            return render_z88dk_asm(domains, types, pointer_table=pointer_table,
                                    find_macro=find_macro, reg=reg, layout=layout,
                                    pools=pools, pool_alloc=pool_alloc)
        if z88dk_output == "c":
            # §16.3: --z80-find-macro is meaningless for C mode (the
            # compiler makes its own inlining decision) and is a
            # configuration error when combined with --z88dk-output=c,
            # same "flag combination must make sense together"
            # discipline as --z88dk-output itself just above. Enforced
            # HERE, not only in _cli(): a caller going through the
            # library API directly (not argparse) must hit the same
            # rejection, not have find_macro silently dropped.
            if find_macro:
                raise ValueError(
                    "--z80-find-macro is not valid with --z88dk-output=c "
                    "(§16.3) -- in C mode {Type}_Find is an ordinary "
                    "function and inlining is the compiler's own decision, "
                    "not the exporter's to make via a MACRO/ENDM block")
            from .export_z80_z88dk_c import render_z88dk_c
            return render_z88dk_c(domains, types, pointer_table=pointer_table, reg=reg,
                                  layout=layout, pools=pools, pool_alloc=pool_alloc)
        raise ValueError(f"unknown z88dk_output {z88dk_output!r} -- must be 'asm' or 'c'")
    raise ValueError(f"unknown toolchain {toolchain!r} -- must be 'sjasmplus' or 'z88dk'")


def _parse_pool_base(text):
    """Accepts '0xa000', '$a000', or plain decimal -- same shape as
    export_6502.py's _parse_zp_base, this target just never needed a
    hex-address CLI parameter before pools existed."""
    if text is None:
        return None
    t = text.strip()
    if t.startswith("0x") or t.startswith("0X"):
        return int(t, 16)
    if t.startswith("$"):
        return int(t[1:], 16)
    return int(t, 10)


def _cli():
    import argparse
    import sys
    from .combine import resolve_inputs, compile_multi, CombineError
    from .export_ids import write_ids_manifest

    ap = argparse.ArgumentParser(description="GDDL -> Z80 exporter")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--type", dest="types", action="append", required=True,
                     help="type to export (repeatable)")
    ap.add_argument("--z80-toolchain", choices=["sjasmplus", "z88dk"],
                     default="sjasmplus", help="Z80 toolchain")
    ap.add_argument("--z88dk-output", choices=["asm", "c"], default="asm",
                     help="z88dk output form (only with --z80-toolchain=z88dk)")
    # Mandatory, no default -- §16.2/§16.3, following --zp-base (§10.2).
    # argparse `required=True` is what actually enforces "no default";
    # render() independently rejects None so the library API can't be
    # called without a decision either.
    ap.add_argument("--z80-pointer-table", choices=["on", "off"], required=True,
                     help="pointer table (on) or direct addressing (off), required")
    ap.add_argument("--layout", choices=["aos", "soa"], default="aos",
                     help="aos (default) or soa data layout")
    ap.add_argument("--pool-base", default=None,
                     help="RAM base address for pool storage (§22.4), required only "
                          "if the exported types have any pools (e.g. 0xa000)")
    ap.add_argument("--z80-find-macro", choices=["on", "off"], default="off",
                     help="also emit an inline macro variant of Find (default: off)")
    ap.add_argument("--emit-all-domains", action="store_true",
                     help="emit every domain's constants, even unreferenced ones (default: off)")
    ap.add_argument("--emit-ids-manifest", action="store_true",
                     help="also write <output>.gddlids.json, every identifier/flags "
                          "domain declared, for cross-mod script references (default: off)")
    ap.add_argument("-o", "--output", default=None,
                     help="output path (default: stdout; stem for --z88dk-output=c)")
    ap.add_argument("--verbose-errors", action="store_true",
                     help="tag each error with its internal [phase N, check] (default: off)")
    args = ap.parse_args()

    if args.emit_ids_manifest and not args.output:
        ap.error("--emit-ids-manifest requires -o/--output -- there is no "
                 "output stem to name the manifest after when writing to stdout")

    pointer_table = args.z80_pointer_table == "on"
    pool_base = _parse_pool_base(args.pool_base) if args.pool_base is not None else None

    # §16.2: the flag is AoS-only. Under --layout=soa there are no
    # instance structs to hold addresses of, so this WARNS and is
    # ignored rather than erroring -- the two flags are independent axes
    # that simply don't compose in this one direction.
    if args.layout == "soa":
        print("warning: --z80-pointer-table is ignored under --layout=soa "
              "(§16.2) -- SoA data is already flattened into per-field "
              "arrays with nothing to point at.", file=sys.stderr)
        pointer_table = False

    if args.z88dk_output == "c" and args.z80_find_macro == "on":
        ap.error("--z80-find-macro applies to the assembly output paths "
                 "only; in C mode {Type}_Find is an ordinary function the "
                 "compiler may inline on its own (§16.1.1)")

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
    ordered_type_names = [t.name for t in types]
    pools = gather_pool_info(resolver.reg, ordered_type_names)
    out = render(domains, types, toolchain=args.z80_toolchain,
                 z88dk_output=args.z88dk_output, pointer_table=pointer_table,
                 find_macro=args.z80_find_macro == "on", reg=resolver.reg,
                 layout=args.layout, pools=pools, pool_base=pool_base)

    if isinstance(out, dict):
        # C mode: header/.c split (§16.2.1), never a single file for real
        # use -- a definition can only live in one .c file.
        if not args.output:
            for suffix, text in out.items():
                print(f"/* ==== {suffix} ==== */")
                print(text)
            return
        stem = args.output
        for suffix, text in out.items():
            with open(stem + suffix, "w", encoding="utf-8") as f:
                f.write(text)
        if args.emit_ids_manifest:
            manifest_path = write_ids_manifest(resolver.reg, stem, resolver=resolver)
            print(f"wrote {manifest_path}")
        return

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
    else:
        print(out)

    if args.emit_ids_manifest:
        manifest_path = write_ids_manifest(resolver.reg, args.output, resolver=resolver)
        print(f"wrote {manifest_path}")


if __name__ == "__main__":
    _cli()
