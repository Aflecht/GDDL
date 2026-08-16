# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
6502 export, phase 2: 64tass dialect renderer (§10.3).

Translates the shared, assembler-agnostic IR (export_6502.gather_ir /
gather_soa_columns) into 64tass syntax -- the third of three planned
renderers (ACME, KickAssembler, 64tass, §10.3). No changes to the
shared resolution step at all; this file only differs from
export_6502_acme.py / export_6502_kickassembler.py in how the SAME
already-gathered data gets rendered as text.

64tass's syntax was learned from its actual, complete reference manual
(fetched from the project's own official host, tass64.sourceforge.net,
since this sandbox's packaged doc files are stripped by image
minimization) and confirmed directly against the real installed
`64tass` binary -- not assumed to resemble either prior dialect.
Genuinely different from BOTH ACME and KickAssembler in ways worth
recording:

  - Data directives are dot-prefixed (`.byte` / `.word`), like
    KickAssembler, unlike ACME's `!byte` / `!word`.
  - Named compile-time constants use bare `Name = value` (confirmed
    directly), like ACME, unlike KickAssembler's mandatory `.label`.
  - Include directive is `.include "file.asm"` -- a third, distinct
    spelling from both ACME's `!source` and KickAssembler's `#import`.
  - Mnemonics are confirmed case-INSENSITIVE by default -- the opposite
    situation from KickAssembler's lowercase-only requirement.
  - Labels tolerate an optional trailing colon (`Name:` and bare `Name`
    both work, colon stripped) -- confirmed directly.
  - `-C, --case-sensitive` exists; default (no `-C`) is case-
    INSENSITIVE label matching, confirmed directly. This project's test
    harness passes `-C` anyway, matching the manual's own recommended
    invocation. Confirmed separately: under `-C`, the register-index
    LETTER itself must be lowercase (`,x` not `,X`) -- uppercase `X`
    becomes a genuinely different, unrecognized symbol once case-
    sensitivity is on, not the addressing-mode keyword. All register-
    index usage here is lowercase `,x` for exactly this reason.

Confirmed IDENTICAL to both prior dialects, verified directly rather
than assumed:
  - Origin directive `*=$addr`.
  - Low/high byte operators `<label` / `>label`.
  - Comment character `;`.
  - The 65C02-only indexed-indirect JMP (`jmp (Table,x)`) is rejected
    under 64tass's DEFAULT CPU target (`--m65xx`) -- confirmed
    directly, tested against explicit `--m6502` (also rejects) and
    explicit `--m65c02` (accepts).

§10.2 update: `{Domain}_Dispatch` is now generated output, one per
identifier domain that has a jump table -- previously only hand-written
example code in test harnesses. Zero-page pointers (both Dispatch's and
Find's) are no longer hardcoded -- each consumer gets its own
non-overlapping 2-byte block from export_6502.allocate_zero_page,
derived from the required --zp-base (no default), emitted as a named
bare constant so the generated code stays self-documenting.
"""

from .export_6502 import DomainInfo, TypeInfo, ZeroPageAllocation, gather_soa_columns
from .export_cpp import _string_n


_WIDTH_TO_DIRECTIVE = {"u8": ".byte", "u16": ".word", "u32": None, "u64": None}


def _leaf_directive(type_tokens: str, domain_widths: dict) -> str:
    """The 64tass storage directive for one leaf field. Scalars map by
    their own declared type; identifier-typed leaves (plain Domain or
    @Domain -- indistinguishable on this target, §10.1) map by their
    DOMAIN's declared width, since what's actually stored is the
    domain's index, not the field's nominal type.

    `string N` leaves are NOT handled here -- they need `.text "..."` +
    `.byte 0, 0, ...` (§13.2; confirmed directly that 64tass rejects a
    quoted literal inside `.byte`: "Error... There's more than one
    character" is the exact ACME message but 64tass gives an equivalent
    syntax error for `.byte "Grübnik"` -- tested independently).
    The AoS emission loop checks `_string_n()` first."""
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


def render_string_leaf_64tass(value: str, n: int, path: str) -> list:
    """§13.2-compliant string-N emission for 64tass. Directive is
    `.text "..."` for the content, `.byte 0, 0, ...` for explicit
    zero-padding to reach N total. Confirmed directly: `.byte "Grübnik"`
    is a hard syntax error on 64tass (same class of restriction as
    ACME), and `.text "Grübnik"` passes raw UTF-8 bytes through
    byte-for-byte, confirmed by inspecting assembled output."""
    content = value.encode("utf-8")
    if len(content) > n:
        raise ValueError(
            f"string field {path!r}: {len(content)}-byte UTF-8 value "
            f"doesn't fit in string {n}")
    padding = n - len(content)
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    lines = [f'\t.text "{escaped}"\t; {path}']
    if padding:
        lines.append(f"\t.byte {', '.join(['0'] * padding)}")
    return lines


def render_64tass(domains: list, types: list, zp_alloc: ZeroPageAllocation,
                   layout: str = "aos") -> str:
    if layout not in ("aos", "soa"):
        raise ValueError(f"layout must be 'aos' or 'soa', got {layout!r}")

    lines = []
    lines.append("; Auto-generated by the GDDL compiler (6502 / 64tass). Do not edit by hand.")
    if layout == "soa":
        lines.append("; Scope: scalar (u8/u16) and identifier-typed leaf fields, layout=soa (string N not yet supported in SoA).")
    else:
        lines.append("; Scope: scalar (u8/u16), identifier-typed, and string N leaf fields, AoS only.")
    lines.append("")

    # ---- 1. per-domain member index constants + jump table + Dispatch
    # (§10.2/10.3) ---- unaffected by layout.
    for d in domains:
        if d.kind != "identifier":
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
            lines.append(f"\t.byte <{d.name}_{key}_Handler")
        lines.append(f"{d.name}_JumpTable_Hi:")
        for key, _index in d.members:
            lines.append(f"\t.byte >{d.name}_{key}_Handler")
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
        # ---- SoA: one labeled array per leaf field, no registry at
        # all -- identical reasoning to the other two renderers, see
        # §13.1/§13.4. ----
        for t in types:
            lines.append(f"; --- type: {t.name} (SoA field arrays) ---")
            for inst in t.instances:
                lines.append(f"{t.name}_{inst.name}_Index = {inst.index}")
            for path, type_tokens, values in gather_soa_columns(t):
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
        return "\n".join(lines)

    # ---- AoS (default) ----

    # ---- 2. instance data tables (AoS) ----
    for t in types:
        lines.append(f"; --- type: {t.name} (AoS instance data) ---")
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}:")
            for (path, type_tokens), value in zip(t.leaves, inst.leaf_values):
                str_n = _string_n(type_tokens)
                if str_n is not None:
                    lines.extend(render_string_leaf_64tass(value, str_n, path))
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
            lines.append(f"\t.byte <{t.name}_{inst.name}")
        lines.append(f"{t.name}_Registry_Hi:")
        for inst in t.instances:
            lines.append(f"\t.byte >{t.name}_{inst.name}")
        lines.append("")
        ptr_addr = zp_alloc.registry_blocks[t.name]
        lines.append(f"{t.name}_RegistryPtr = ${ptr_addr:02x}")
        lines.append("")
        lines.extend(_render_index_lookup(t.name))
        lines.append("")

    return "\n".join(lines)


def _render_dispatch(domain_name: str) -> list:
    """§10.2: NMOS-compatible dispatch subroutine, generated once per
    domain. Input: x = domain member index. Ends with a plain jmp (not
    rts) through the domain's own zero-page pointer -- tail-call
    pattern, verified correct via real execution. Register-index letter
    lowercase (,x) -- required under -C, see module docstring."""
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
    other renderers' version (§10.1: nothing to search for, dense index
    IS the identity). Input: x = dense index. Output:
    {Type}_RegistryPtr / +1 = the instance's data address."""
    T = type_name
    return [
        f"{T}_Find:",
        f"\tlda {T}_Registry_Lo,x",
        f"\tsta {T}_RegistryPtr",
        f"\tlda {T}_Registry_Hi,x",
        f"\tsta {T}_RegistryPtr+1",
        "\trts",
    ]
