# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
6502 export, phase 2: KickAssembler dialect renderer (§10.3).

Translates the shared, assembler-agnostic IR (export_6502.gather_ir /
gather_soa_columns) into KickAssembler syntax -- the second of three
planned renderers (ACME, KickAssembler, 64tass, §10.3). No changes to
the shared resolution step at all; this file only differs from
export_6502_acme.py in how the SAME already-gathered data gets
rendered as text.

KickAssembler's syntax was learned from its actual bundled manual and
by testing directly against the real KickAss.jar (v5.25) -- not assumed
to mirror ACME. Confirmed differences that matter here:

  - Comments: `//` line, `/* */` block (ACME uses `;`).
  - Data directives: `.byte` / `.word` (ACME uses `!byte` / `!word`).
  - Named compile-time constants require the explicit `.label Name =
    value` directive -- KickAssembler has no bare `Name = value` form
    the way ACME does. `.label` (not `.const`) specifically, since
    `.label`-declared names are visible in the entire enclosing scope
    (like a real label), matching how ACME's bare assignments are
    forward-reference-safe; `.const` is only visible after its own
    declaration point, which would break several forward references
    this generator relies on (e.g. the jump table referencing handler
    labels declared later in the file).
  - File inclusion: `#import "file.asm"` (preprocessor directive; the
    older `.import source "file.asm"` also still works but the
    preprocessor form is what KickAssembler's own manual recommends).
  - Mnemonics are case-sensitive, confirmed required lowercase by
    testing directly (uppercase LDA/STA/etc. parse as an attempted,
    undefined pseudo-command, not the mnemonic).

Confirmed IDENTICAL to ACME, verified directly rather than assumed:
  - Origin directive: `*=$addr` (both accept this exact syntax).
  - Low/high byte operators: `<label` / `>label`.
  - Label declarations: `Name:` (colon-terminated, no prefix on use).
  - The 65C02-only indexed-indirect JMP (`jmp (Table,x)`) is REJECTED
    under KickAssembler's default CPU too -- confirmed by actually
    trying it. This project's NMOS-compatible dispatch pattern needed
    no changes to work here.

§10.2 update: `{Domain}_Dispatch` is now generated output, one per
identifier domain that has a jump table (every referenced domain,
since 6502 always indexes, §10.1) -- previously only hand-written
example code in test harnesses. Zero-page pointers (both Dispatch's
and Find's) are no longer hardcoded -- each consumer gets its
own non-overlapping 2-byte block from export_6502.allocate_zero_page,
derived from the required --zp-base (no default), emitted as a named
`.label` constant so the generated code stays self-documenting.

Design decisions duplicated from export_6502_acme.py rather than
shared via a common helper, deliberately -- keeping this change
strictly scoped to a new renderer file, not a refactor of shared
plumbing (see this project's own established practice: the split
between generate_header/generate_split in the C++ exporter for the
exact same reason).
"""

from .export_6502 import (
    DomainInfo, TypeInfo, ZeroPageAllocation, PoolInfo, PoolAllocation,
    gather_soa_columns, flatten_array_ir_value,
)
from .export_cpp import _string_n
from .registry import _try_parse_array_type


_WIDTH_TO_DIRECTIVE = {"u8": ".byte", "u16": ".word", "u32": None, "u64": None}


def _leaf_directive(type_tokens: str, domain_widths: dict) -> str:
    """The KickAssembler storage directive for one leaf field. Scalars
    map by their own declared type; identifier-typed leaves (plain
    Domain or @Domain -- indistinguishable on this target, §10.1) map
    by their DOMAIN's declared width, since what's actually stored is
    the domain's index, not the field's nominal type.

    `string N` leaves are NOT handled here -- they need `.text "..."`
    + `.byte 0, 0, ...` (§13.2). KickAssembler's `.text` directive is
    documented as its string-data pseudocommand; `.byte` is confirmed
    to accept integers and character literals, but NOT a multi-char
    string literal (the same restriction ACME and 64tass have, both
    confirmed directly by attempting it). NOTE: KickAssembler could NOT
    be run live in this session (theweb.dk is egress-blocked, jar not
    in the tools directory); the `.text` directive is from KA's public
    documentation and consistent with what the two confirmed assemblers
    use, but must be re-confirmed against the real binary before this
    is treated as fully validated."""
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
        return ".byte"
    if t in ("u16", "i16"):
        return ".word"
    raise ValueError(f"6502 first pass doesn't support field type {type_tokens!r} yet "
                      "(scalar u8/u16, identifier-typed, and string N leaf fields only)")


def _leaf_byte_width(type_tokens: str, domain_widths: dict) -> int:
    """1, 2, or N -- how many bytes this leaf occupies."""
    n = _string_n(type_tokens)
    if n is not None:
        return n
    directive = _leaf_directive(type_tokens, domain_widths)
    return {".byte": 1, ".word": 2}[directive]


def render_string_leaf_kickassembler(value: str, n: int, path: str) -> list:
    """§13.2-compliant string-N emission for KickAssembler.

    **Critical KickAssembler limitation, confirmed directly against the
    real v5.25 binary**: KickAssembler does NOT support raw UTF-8 bytes
    in `.text` literals. Every encoding option (ascii, petscii_upper,
    petscii_mixed, screencode_upper) treats non-ASCII source characters
    as single Latin-1 bytes -- e.g. 'ü' (U+00FC) always emits `$FC`,
    never the correct UTF-8 sequence `$C3 $BC`. No escape sequences
    work either (`\\u00fc`, `\\xc3\\xbc` are treated as literal
    backslash runs). This is confirmed by assembling real UTF-8 source
    files and checking output bytes directly.

    The correct approach: emit ASCII runs as `.text "..."` (with
    `.encoding "ascii"` in the file header) and non-ASCII code points
    as explicit `.byte $xx, $yy` hex literals. This is the only way to
    produce correct UTF-8 byte sequences in KickAssembler output.

    ACME uses `!text`/`!byte`, 64tass uses `.text`/`.byte`, and
    KickAssembler uses `.text`/`.byte` -- the directive NAMES match
    64tass but the ENCODING BEHAVIOR differs for non-ASCII content,
    which is why this required separate direct verification rather than
    assuming agreement from the name match."""
    content = value.encode("utf-8")
    if len(content) > n:
        raise ValueError(
            f"string field {path!r}: {len(content)}-byte UTF-8 value "
            f"doesn't fit in string {n}")
    padding = n - len(content)

    # Split value into runs of ASCII characters (emittable as .text
    # literals) vs non-ASCII bytes (must be .byte hex values).
    lines = []
    ascii_run = []
    for ch in value:
        if ord(ch) < 128 and ch not in ('"', "\\"):
            ascii_run.append(ch)
        else:
            if ascii_run:
                lines.append(f'\t.text "{"".join(ascii_run)}"')
                ascii_run = []
            for b in ch.encode("utf-8"):
                lines.append(f"\t.byte ${b:02x}")
    if ascii_run:
        lines.append(f'\t.text "{"".join(ascii_run)}"')

    if padding:
        lines.append(f"\t.byte {', '.join(['0'] * padding)}")

    # Annotate the first line with the path comment, or add a standalone one.
    if lines:
        lines[0] = lines[0] + f"\t// {path}"
    return lines


def render_pools_kickassembler(pools: list, pool_alloc: PoolAllocation) -> list:
    """§22.4: one `.label` constant per pool leaf field region -- never a
    data directive, same reasoning as export_6502_acme.render_pools_acme.
    `.label` (not `.const`) for the same reason every other constant in
    this renderer already uses it -- see this module's own docstring."""
    lines = []
    for pool in pools:
        lines.append(f"// --- pool: {pool.name} ({pool.type_name} x {pool.count}, "
                      "SoA reservation, uninitialized -- §22.4) ---")
        regions = pool_alloc.fields[pool.name]
        for path, _type_tokens in pool.leaves:
            region = regions[path]
            label = f"{pool.name}_{path}"
            if region.hi_addr is not None:
                lines.append(f".label {label}_Lo = ${region.lo_addr:04x}")
                lines.append(f".label {label}_Hi = ${region.hi_addr:04x}")
            else:
                lines.append(f".label {label} = ${region.lo_addr:04x}")
        lines.append("")
    return lines


def render_kickassembler(domains: list, types: list, zp_alloc: ZeroPageAllocation,
                          layout: str = "aos", pools: list = None,
                          pool_alloc: PoolAllocation = None) -> str:
    if layout not in ("aos", "soa"):
        raise ValueError(f"layout must be 'aos' or 'soa', got {layout!r}")
    pools = pools or []

    lines = []
    lines.append("// Auto-generated by the GDDL compiler (6502 / KickAssembler). Do not edit by hand.")
    # .encoding "ascii" is required for .text to emit raw ASCII bytes.
    # Without it, KickAssembler defaults to PETSCII conversion and
    # lowercase letters map to wrong byte values (e.g. 'r' -> $12, not $72).
    # This was confirmed directly against the real KickAssembler v5.25 binary.
    lines.append('.encoding "ascii"')
    if layout == "soa":
        lines.append("// Scope: scalar (u8/u16) and identifier-typed leaf fields, layout=soa (string N not yet supported in SoA).")
    else:
        lines.append("// Scope: scalar (u8/u16), identifier-typed, and string N leaf fields, AoS only.")
    lines.append("")

    # ---- 1. per-domain member index constants + jump table + Dispatch
    # (§10.2/10.3) ---- unaffected by layout.
    for d in domains:
        if d.kind != "identifier":
            lines.append(f"// --- domain: {d.name} (flags, width {d.width}) ---")
            for key, value in d.members:
                lines.append(f".label {d.name}_{key} = {value}")
            lines.append("")
            continue
        lines.append(f"// --- domain: {d.name} (indexed form, width {d.width}) ---")
        for key, index in d.members:
            lines.append(f".label {d.name}_{key} = {index}")
        lines.append("")
        lines.append(f"{d.name}_JumpTable_Lo:")
        for key, _index in d.members:
            lines.append(f"\t.byte <{d.name}_{key}_Handler")
        lines.append(f"{d.name}_JumpTable_Hi:")
        for key, _index in d.members:
            lines.append(f"\t.byte >{d.name}_{key}_Handler")
        lines.append("")
        ptr_addr = zp_alloc.dispatch_blocks[d.name]
        lines.append(f".label {d.name}_DispatchPtr = ${ptr_addr:02x}")
        lines.append("")
        lines.extend(_render_dispatch(d.name))
        lines.append("")

    domain_index_to_key = {
        d.name: {index: key for key, index in d.members} for d in domains
    }
    domain_widths = {d.name: d.width for d in domains}

    if layout == "soa":
        # ---- SoA: one labeled array per leaf field, no registry at
        # all -- identical reasoning to the ACME renderer's SoA branch,
        # see export_6502_acme.py and §13.1/§13.4. ----
        for t in types:
            lines.append(f"// --- type: {t.name} (SoA field arrays) ---")
            for inst in t.instances:
                lines.append(f".label {t.name}_{inst.name}_Index = {inst.index}")
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
                        lines.append(f"\t.byte {r}")
                else:
                    lines.append(f"{label}_Lo:")
                    for r in rendered:
                        lines.append(f"\t.byte <{r}")
                    lines.append(f"{label}_Hi:")
                    for r in rendered:
                        lines.append(f"\t.byte >{r}")
            lines.append("")
        lines.extend(render_pools_kickassembler(pools, pool_alloc))
        return "\n".join(lines)

    # ---- AoS (default) ----

    # ---- 2. instance data tables (AoS) ----
    for t in types:
        lines.append(f"// --- type: {t.name} (AoS instance data) ---")
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}:")
            for (path, type_tokens), value in zip(t.leaves, inst.leaf_values):
                str_n = _string_n(type_tokens)
                if str_n is not None:
                    lines.extend(render_string_leaf_kickassembler(value, str_n, path))
                    continue
                array_info = _try_parse_array_type(type_tokens.strip())
                if array_info is not None:
                    flat = flatten_array_ir_value(value, array_info.dims)
                    elem_n = _string_n(array_info.element_type)
                    for i, v in enumerate(flat):
                        elem_path = f"{path}[{i}]"
                        if elem_n is not None:
                            lines.extend(render_string_leaf_kickassembler(v, elem_n, elem_path))
                        else:
                            elem_directive = _leaf_directive(array_info.element_type, domain_widths)
                            lines.append(f"\t{elem_directive} {v}\t// {elem_path}")
                    continue
                directive = _leaf_directive(type_tokens, domain_widths)
                if isinstance(value, tuple) and value[0] == "domain_index":
                    _, domain, index = value
                    key = domain_index_to_key[domain][index]
                    lines.append(f"\t{directive} {domain}_{key}\t// {path}")
                else:
                    lines.append(f"\t{directive} {value}\t// {path}")
        lines.append("")

    # ---- 3. registry: dense-index direct lookup, no search (§10.1) ----
    for t in types:
        n = len(t.instances)
        lines.append(f"// --- type: {t.name} registry (dense declaration-order index, no stable ID) ---")
        lines.append(f".label {t.name}_Registry_Count = {n}")
        for inst in t.instances:
            lines.append(f".label {t.name}_{inst.name}_Index = {inst.index}")
        lines.append(f"{t.name}_Registry_Lo:")
        for inst in t.instances:
            lines.append(f"\t.byte <{t.name}_{inst.name}")
        lines.append(f"{t.name}_Registry_Hi:")
        for inst in t.instances:
            lines.append(f"\t.byte >{t.name}_{inst.name}")
        lines.append("")
        ptr_addr = zp_alloc.registry_blocks[t.name]
        lines.append(f".label {t.name}_RegistryPtr = ${ptr_addr:02x}")
        lines.append("")
        lines.extend(_render_index_lookup(t.name))
        lines.append("")

    return "\n".join(lines)


def _render_dispatch(domain_name: str) -> list:
    """§10.2: NMOS-compatible dispatch subroutine, generated once per
    domain. Input: X = domain member index. Ends with a plain jmp (not
    rts) through the domain's own zero-page pointer -- tail-call
    pattern, verified correct via real execution."""
    D = domain_name
    return [
        f"{D}_Dispatch:",
        f"\tlda {D}_JumpTable_Lo,x",
        f"\tsta {D}_DispatchPtr",
        f"\tlda {D}_JumpTable_Hi,x",
        f"\tsta {D}_DispatchPtr+1",
        f"\tjmp ({D}_DispatchPtr)",
    ]


def _render_index_lookup(type_name: str) -> list:
    """Direct O(1) indexed lookup -- identical logic/registers to the
    ACME renderer's version (§10.1: nothing to search for, dense index
    IS the identity). Input: X = dense index. Output:
    {Type}_RegistryPtr / +1 = the instance's data address.

    Mnemonics are lowercase, confirmed required by testing directly:
    KickAssembler treats uppercase LDA/STA/etc. as an attempted
    (undefined) pseudo-command invocation, not the standard mnemonic --
    'Error: Pseudo command 'LDA' not defined'. ACME accepts either
    case; this is a genuine, confirmed dialect difference, not
    something carried over by assumption."""
    T = type_name
    return [
        f"{T}_Find:",
        f"\tlda {T}_Registry_Lo,x",
        f"\tsta {T}_RegistryPtr",
        f"\tlda {T}_Registry_Hi,x",
        f"\tsta {T}_RegistryPtr+1",
        "\trts",
    ]
