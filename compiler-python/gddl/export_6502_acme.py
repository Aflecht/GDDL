# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
6502 export, phase 2: ACME dialect renderer (§10.3).

Translates the shared, assembler-agnostic IR (export_6502.gather_ir)
into ACME assembly syntax. The first of three planned renderers
(ACME, then KickAssembler, then 64tass, §10.3) -- each consumes the
same shared IR; adding a dialect later must never require re-deriving
anything this module or export_6502.py already computed.

Design decisions made here (not dictated by the spec, since §10 doesn't
give ACME syntax specifics the way §14.0 gave a literal worked C++
example) -- flagged as decisions, not just asserted:

  - Both the domain jump table and the instance registry use a SPLIT
    low-byte-array / high-byte-array layout, not an interleaved array
    of 2-byte words. This is what makes both NMOS-6502-compatible:
    with parallel single-byte-stride arrays, `LDA Table_Lo,X` /
    `LDA Table_Hi,X` addresses entry X directly with plain absolute-
    indexed loads -- no doubling of the index, no indexed-indirect JMP
    (a 65C02-only addressing mode, confirmed unavailable on the base/
    NMOS 6502 both at the ACME assembler level and the py65 emulator
    level; see the validation notes in the commit history). A real C64
    (6510, NMOS-family) can run this.

  - Jump table entries reference externally-defined handler labels,
    one per domain member, named "{Domain}_{member}_Handler". GDDL has
    no notion of game-specific dispatch code -- a real project defines
    these labels itself elsewhere and links/assembles them together
    with this generated file.

  - `{Domain}_Dispatch` IS now generated output (§10.2, updated) -- one
    per identifier domain that has a jump table (every referenced
    domain, since 6502 always uses indexed form, §10.1). Previously
    this was left as hand-written example code in test harnesses only;
    that was a gap, since hand-copying this exact pattern per project
    risks silently reintroducing the 65C02-only indexed-indirect-JMP
    bug this exact pattern was built to avoid, with nothing to catch
    it. Calling convention: caller loads X = domain member index, then
    JSR's in; the routine ends with a plain JMP (not RTS) through its
    own zero-page pointer -- the ORIGINAL caller's JSR return address
    is what the jumped-to handler's own RTS eventually returns through
    (tail-call/trampoline pattern, verified correct via real execution).

  - Instance registry/lookup also generated, as it always has been --
    trivial now, since instance references are dense declaration-order
    indices (§10.1, extended to instances), not a sparse 64-bit key
    space. `{Type}_Find` takes the index directly in X and
    returns the address via two indexed loads -- no comparison loop,
    no miss case (an out-of-range index is a caller bug, consistent
    with plain array indexing everywhere else on this target).

  - §10.2: zero-page pointers (both Dispatch's and Find's) are
    no longer hardcoded addresses -- each consumer gets its own
    non-overlapping 2-byte block from export_6502.allocate_zero_page,
    derived from the required --zp-base parameter (no default). Each
    block is emitted as a named constant ({Type}_RegistryPtr /
    {Domain}_DispatchPtr) so the generated code is self-documenting
    rather than referencing bare hex addresses.

  - Table size is assumed to fit in 8 bits (<=256 entries/members) for
    this first pass -- a straightforward, not-yet-needed generalization
    for larger tables would use 16-bit indices.
"""

from .export_6502 import (
    DomainInfo, TypeInfo, ZeroPageAllocation, PoolInfo, PoolAllocation,
    gather_soa_columns, flatten_array_ir_value,
)
from .export_cpp import _string_n
from .registry import _try_parse_array_type


_WIDTH_TO_DIRECTIVE = {"u8": "!byte", "u16": "!word", "u32": "!32", "u64": None}


def _leaf_directive(type_tokens: str, domain_widths: dict) -> str:
    """The ACME storage directive for one leaf field. Scalars map by
    their own declared type; identifier-typed leaves (plain Domain or
    @Domain -- indistinguishable on this target, §10.1) map by their
    DOMAIN's declared width, since what's actually stored is the
    domain's index, not the field's nominal type.

    `string N` leaves are NOT handled here -- they need a multi-line
    `!text "..."` + `!byte 0, 0, ...` block (§13.2; confirmed directly
    against the real ACME binary that `!byte "text", 0` is a hard error:
    "There's more than one character" -- ACME's !byte only accepts
    single characters or integers, never a string literal). The AoS
    emission loop checks `_string_n()` first and calls
    `render_string_leaf_acme()` directly, bypassing this function."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in domain_widths:
        width = domain_widths[t]
        directive = _WIDTH_TO_DIRECTIVE.get(width)
        if directive is None:
            raise ValueError(f"6502 first pass doesn't support {width}-wide domains yet")
        return directive
    if t in ("u8", "i8"):
        return "!byte"
    if t in ("u16", "i16"):
        return "!word"
    raise ValueError(f"6502 first pass doesn't support field type {type_tokens!r} yet "
                      "(scalar u8/u16, identifier-typed, and string N leaf fields only)")


def _leaf_byte_width(type_tokens: str, domain_widths: dict) -> int:
    """1, 2, or N -- how many bytes this leaf occupies. Used to decide
    whether a SoA array needs a Lo/Hi split (matching the jump table
    and AoS registry's existing pattern) or stays a single byte array.
    N (from string N) is a special case: SoA string support is not yet
    implemented and will raise at the emission site."""
    n = _string_n(type_tokens)
    if n is not None:
        return n  # string fields are N bytes wide; SoA raises at use site
    directive = _leaf_directive(type_tokens, domain_widths)
    return {"!byte": 1, "!word": 2}[directive]


def render_string_leaf_acme(value: str, n: int, path: str) -> list:
    """§13.2-compliant multi-line emission for a `string N` leaf in
    ACME dialect. ACME's `!byte` directive accepts ONLY single
    characters or integers -- NOT a quoted string literal (confirmed
    directly: `!byte "Grübnik"` gives "There's more than one
    character"). The correct form is `!text "..."` for the content
    bytes, then `!byte 0, 0, ...` for the explicit NUL terminator and
    any further zero padding to reach N total.

    UTF-8 multi-byte content passes through correctly: `!text` treats
    the source file's raw bytes as the output, confirmed by assembling
    a source file containing real UTF-8 bytes (e.g. U+00FC ü -> 0xC3
    0xBC) and comparing the binary output byte-for-byte.

    Length/encoding NOT re-validated here -- upstream phases 1-8
    already enforced it."""
    content = value.encode("utf-8")
    if len(content) > n:
        raise ValueError(
            f"string field {path!r}: {len(content)}-byte UTF-8 value "
            f"doesn't fit in string {n}")
    padding = n - len(content)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    lines = [f'\t!text "{escaped}"\t; {path}']
    if padding:
        lines.append(f"\t!byte {', '.join(['0'] * padding)}")
    return lines


def render_pools_acme(pools: list, pool_alloc: PoolAllocation) -> list:
    """§22.4: one plain constant assignment per pool leaf field region --
    NEVER a data directive (`!byte`/`!fill`/etc). Confirmed directly
    against the real ACME binary (0.97): a PC-advancing directive like
    `* = * + N` still costs N real zero-bytes in a `--format plain`
    output (ACME can't represent a gap in a flat binary), but a bare
    `Label = expression` constant assignment costs nothing at all --
    this is what makes pool reservation genuinely free of file/tape/disk
    cost, matching §22.4's stated design goal. `pool_alloc` already
    resolved every field's real address (export_6502.allocate_pool_space)
    -- this function only renders it, never computes an address itself."""
    lines = []
    for pool in pools:
        lines.append(f"; --- pool: {pool.name} ({pool.type_name} x {pool.count}, "
                      "SoA reservation, uninitialized -- §22.4) ---")
        regions = pool_alloc.fields[pool.name]
        for path, _type_tokens in pool.leaves:
            region = regions[path]
            label = f"{pool.name}_{path}"
            if region.hi_addr is not None:
                lines.append(f"{label}_Lo = ${region.lo_addr:04x}")
                lines.append(f"{label}_Hi = ${region.hi_addr:04x}")
            else:
                lines.append(f"{label} = ${region.lo_addr:04x}")
        lines.append("")
    return lines


def render_acme(domains: list, types: list, zp_alloc: ZeroPageAllocation,
                 layout: str = "aos", pools: list = None,
                 pool_alloc: PoolAllocation = None) -> str:
    if layout not in ("aos", "soa"):
        raise ValueError(f"layout must be 'aos' or 'soa', got {layout!r}")
    pools = pools or []

    lines = []
    lines.append("; Auto-generated by the GDDL compiler (6502 / ACME). Do not edit by hand.")
    if layout == "soa":
        lines.append("; Scope: scalar (u8/u16) and identifier-typed leaf fields, layout=soa (string N not yet supported in SoA).")
    else:
        lines.append("; Scope: scalar (u8/u16), identifier-typed, and string N leaf fields, AoS only.")
    lines.append("")

    # ---- 1. per-domain member index constants + jump table + Dispatch
    # (§10.2/10.3) ---- unaffected by layout: domains/jump tables/
    # Dispatch exist independent of how instance data itself is laid
    # out (mirrors export_cpp.py: enum definitions are unconditional
    # regardless of AoS/SoA there too). Split Lo/Hi byte arrays: plain
    # absolute-indexed LDA reaches any entry directly (no doubling), so
    # dispatch never needs indexed-indirect JMP -- see module docstring.
    for d in domains:
        if d.kind != "identifier":
            # flags domain: plain bit-value constants only, no jump
            # table/Dispatch (§10.2's dispatch machinery is identifier-
            # only -- flags fields are combinable data, never dispatched
            # on).
            lines.append(f"; --- domain: {d.name} (flags, width {d.width}) ---")
            for key, value in d.members:
                lines.append(f"{d.name}_{key} = {value}")
            lines.append("")
            continue
        lines.append(f"; --- domain: {d.name} (indexed form, width {d.width}) ---")
        for key, index in d.members:
            lines.append(f"{d.name}_{key} = {index}")
        lines.append("")
        lines.append(f"{d.name}_JumpTable_Lo:")
        for key, _index in d.members:
            lines.append(f"\t!byte <{d.name}_{key}_Handler")
        lines.append(f"{d.name}_JumpTable_Hi:")
        for key, _index in d.members:
            lines.append(f"\t!byte >{d.name}_{key}_Handler")
        lines.append("")
        ptr_addr = zp_alloc.dispatch_blocks[d.name]
        lines.append(f"{d.name}_DispatchPtr = ${ptr_addr:02x}")
        lines.append("")
        lines.extend(_render_dispatch(d.name))
        lines.append("")

    domain_index_to_key = {
        d.name: {index: key for key, index in d.members} for d in domains
    }
    domain_widths = {d.name: d.width for d in domains}

    if layout == "soa":
        # ---- SoA: one labeled array per LEAF field (§13.1, fully
        # flattened through composition), no registry at all (§13.4 --
        # the dense declaration-order index already shared with AoS's
        # registry indexes directly into these arrays, nothing to
        # look up). Fields wider than a byte split into Lo/Hi arrays,
        # same pattern as the jump table and AoS registry. ----
        for t in types:
            lines.append(f"; --- type: {t.name} (SoA field arrays) ---")
            for inst in t.instances:
                lines.append(f"{t.name}_{inst.name}_Index = {inst.index}")
            for path, type_tokens, values in gather_soa_columns(t):
                if _try_parse_array_type(type_tokens.strip()) is not None:
                    raise ValueError(
                        f"6502 SoA layout doesn't support array-typed fields "
                        f"yet (field {path!r}) -- matching this target's "
                        "existing SoA string-field gap, arrays are AoS-only "
                        "for now; use --layout aos instead")
                width = _leaf_byte_width(type_tokens, domain_widths)
                rendered = []
                for v in values:
                    if isinstance(v, tuple) and v[0] == "domain_index":
                        _, domain, index = v
                        rendered.append(f"{domain}_{domain_index_to_key[domain][index]}")
                    else:
                        rendered.append(str(v))
                label = f"{t.name}_{path}"
                if width == 1:
                    lines.append(f"{label}:")
                    for r in rendered:
                        lines.append(f"\t!byte {r}")
                else:
                    lines.append(f"{label}_Lo:")
                    for r in rendered:
                        lines.append(f"\t!byte <{r}")
                    lines.append(f"{label}_Hi:")
                    for r in rendered:
                        lines.append(f"\t!byte >{r}")
            lines.append("")
        lines.extend(render_pools_acme(pools, pool_alloc))
        return "\n".join(lines)

    # ---- AoS (default) ----

    # ---- 2. instance data tables (AoS) ----
    for t in types:
        lines.append(f"; --- type: {t.name} (AoS instance data) ---")
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}:")
            for (path, type_tokens), value in zip(t.leaves, inst.leaf_values):
                n = _string_n(type_tokens)
                if n is not None:
                    lines.extend(render_string_leaf_acme(value, n, path))
                    continue
                array_info = _try_parse_array_type(type_tokens.strip())
                if array_info is not None:
                    # Arrays design: no nesting concept in assembly data
                    # directives -- flatten row-major (matching the
                    # design's own layout instruction) and emit one
                    # directive (or string block) per element, reusing
                    # this same dialect's own scalar/string emission for
                    # the element type.
                    flat = flatten_array_ir_value(value, array_info.dims)
                    elem_n = _string_n(array_info.element_type)
                    for i, v in enumerate(flat):
                        elem_path = f"{path}[{i}]"
                        if elem_n is not None:
                            lines.extend(render_string_leaf_acme(v, elem_n, elem_path))
                        else:
                            elem_directive = _leaf_directive(array_info.element_type, domain_widths)
                            lines.append(f"\t{elem_directive} {v}\t; {elem_path}")
                    continue
                directive = _leaf_directive(type_tokens, domain_widths)
                if isinstance(value, tuple) and value[0] == "domain_index":
                    _, domain, index = value
                    key = domain_index_to_key[domain][index]
                    lines.append(f"\t{directive} {domain}_{key}\t; {path}")
                else:
                    lines.append(f"\t{directive} {value}\t; {path}")
        lines.append("")

    # ---- 3. registry: dense-index direct lookup, no search (§10.1) ----
    for t in types:
        n = len(t.instances)
        lines.append(f"; --- type: {t.name} registry (dense declaration-order index, no stable ID) ---")
        lines.append(f"{t.name}_Registry_Count = {n}")
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}_Index = {inst.index}")
        lines.append(f"{t.name}_Registry_Lo:")
        for inst in t.instances:
            lines.append(f"\t!byte <{t.name}_{inst.name}")
        lines.append(f"{t.name}_Registry_Hi:")
        for inst in t.instances:
            lines.append(f"\t!byte >{t.name}_{inst.name}")
        lines.append("")
        ptr_addr = zp_alloc.registry_blocks[t.name]
        lines.append(f"{t.name}_RegistryPtr = ${ptr_addr:02x}")
        lines.append("")
        lines.extend(_render_index_lookup(t.name))
        lines.append("")

    return "\n".join(lines)


def _render_dispatch(domain_name: str) -> list:
    """§10.2: NMOS-compatible dispatch subroutine, generated once per
    domain. Input: X = domain member index (caller-supplied). Ends
    with a plain JMP (not RTS) through the domain's own zero-page
    pointer -- the tail-call/trampoline pattern verified correct via
    real execution: the ORIGINAL caller's JSR return address is what
    the jumped-to handler's own RTS eventually returns through, since
    JMP never touches the stack."""
    D = domain_name
    return [
        f"{D}_Dispatch:",
        f"\tLDA {D}_JumpTable_Lo,X",
        f"\tSTA {D}_DispatchPtr",
        f"\tLDA {D}_JumpTable_Hi,X",
        f"\tSTA {D}_DispatchPtr+1",
        f"\tJMP ({D}_DispatchPtr)",
    ]


def _render_index_lookup(type_name: str) -> list:
    """Direct O(1) indexed lookup, replacing what used to be a binary
    search (§10.1: instances are dense declaration-order indices here,
    nothing to search for). Input: X = dense index (caller-supplied,
    already known valid -- no bounds check, same trust convention as
    any other array indexing on this target). Output:
    {Type}_RegistryPtr / +1 = the instance's data address."""
    T = type_name
    return [
        f"{T}_Find:",
        f"\tLDA {T}_Registry_Lo,X",
        f"\tSTA {T}_RegistryPtr",
        f"\tLDA {T}_Registry_Hi,X",
        f"\tSTA {T}_RegistryPtr+1",
        "\tRTS",
    ]
