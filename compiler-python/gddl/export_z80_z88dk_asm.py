# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Z80 export, z88dk assembly-mode renderer (§16.1: second of three
planned output paths -- z88dk's own internal assembler, `z88dk-z80asm`,
distinct from SjASMPlus, needing its own real investigation per §16.1's
explicit call-out).

Syntax confirmed directly against the real, built `z88dk-z80asm`
binary -- not assumed to resemble SjASMPlus (or ACME/KickAssembler/
64tass) despite both being Z80 assemblers. Genuinely shares a
surprising amount with SjASMPlus (more than any two of the 6502
dialects shared with each other), but with one real, confirmed
difference:

  - Comments: `;` (confirmed, same as SjASMPlus).
  - Data directives: `db` / `dw` (confirmed to work identically to
    `defb` / `defw` -- both spellings assemble the same bytes; `db`/`dw`
    used here for brevity, matching every other renderer's style).
    `dw Label` with a real forward label reference confirmed directly
    to emit the label's address as a correct little-endian word.
  - Constants: `equ` (same as SjASMPlus).
  - Origin: `org` (same as SjASMPlus).
  - Include: `include "file"` (same spelling as SjASMPlus).
  - Labels: **colon is REQUIRED, not optional** -- confirmed directly
    (a label with no trailing colon is a hard syntax error here, the
    opposite of SjASMPlus where the colon is optional). This renderer
    already emits colons on every label for stylistic consistency with
    every other renderer, so no code change was needed for this
    specific difference -- but it's a genuine, confirmed rule, not an
    assumption that happened to be harmless.
  - Instructions do NOT need to be indented -- confirmed directly (an
    instruction at column 0 assembles fine, unlike SjASMPlus's hard
    column-0-means-label rule). Indentation is kept here purely for
    readability/style consistency with every other renderer, not
    because the assembler requires it.
  - **Low/high byte extraction uses plain bitwise expressions
    (`expr & $FF`, `(expr >> 8) & $FF`), NOT SjASMPlus's `low()`/
    `high()` function-call syntax.** Confirmed both ways directly:
    the bitwise form assembles correctly (verified against a handler
    at a known address, producing the exact expected low/high bytes),
    and `low(...)`/`high(...)` is a genuine, confirmed syntax error
    here (`z88dk-z80asm` has no such builtin function) -- not just
    "didn't try it," an actual verified difference between the two
    assemblers' expression languages. (This difference no longer
    matters for the table itself, now that both renderers use a
    combined `dw`-entry table rather than split Lo/Hi byte arrays --
    but it's recorded here since it's still a real, confirmed fact
    about this assembler's expression syntax.)

Design (dispatch/registry/identity) is otherwise identical to
export_z80_sjasmplus.py -- same 6502-model architecture (§10, §16),
same register-only calling convention (no zero-page-equivalent scratch
memory needed, per export_z80.py's module docstring), same tail-call
`jp (hl)` trampoline pattern for Dispatch, same combined single-table
shape indexed by `index * 2` (see export_z80.py's module docstring for
why this is Z80-only and doesn't apply to 6502). The ONLY thing that
ever changed between the two renderers is assembler syntax, never the
underlying design.
"""

from .export_z80 import DomainInfo, TypeInfo, _string_n, render_string_leaf
from .registry import _try_parse_array_type


_WIDTH_TO_DIRECTIVE = {"u8": "db", "u16": "dw", "u32": None, "u64": None}


def _leaf_directive(type_tokens: str, domain_widths: dict) -> str:
    """The z88dk-z80asm storage directive for one leaf field. Scalars
    map by their own declared type; identifier-typed leaves (plain
    Domain or @Domain -- indistinguishable on this target) map by
    their DOMAIN's declared width, since what's actually stored is the
    domain's index, not the field's nominal type. `string N` leaves
    are NOT handled here -- see export_z80_sjasmplus.py's identical
    note: they need a multi-item db line, not a directive+value pair."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in domain_widths:
        width = domain_widths[t]
        directive = _WIDTH_TO_DIRECTIVE.get(width)
        if directive is None:
            raise ValueError(f"Z80 first pass doesn't support {width}-wide domains yet")
        return directive
    if t in ("u8", "i8"):
        return "db"
    if t in ("u16", "i16"):
        return "dw"
    raise ValueError(f"Z80 first pass doesn't support field type {type_tokens!r} yet "
                      "(scalar u8/u16, identifier-typed, and string N leaf fields only)")


def render_z88dk_asm(domains: list, types: list, pointer_table: bool = True,
                     find_macro: bool = False, reg=None, layout: str = "aos") -> str:
    from .export_z80 import type_sizeof, gather_soa_columns, ExportZ80Error, flatten_array_ir_value

    lines = []
    lines.append("; Auto-generated by the GDDL compiler (Z80 / z88dk-z80asm). Do not edit by hand.")
    if layout == "soa":
        lines.append("; Scope: scalar (u8/u16) and identifier-typed leaf fields, "
                      "layout=soa (string N not yet supported in SoA, matching 6502's own precedent).")
    else:
        lines.append("; Scope: scalar (u8/u16), identifier-typed, and string N leaf fields, AoS only.")
        lines.append(f"; --z80-pointer-table={'on' if pointer_table else 'off'} (§16.2)")
    lines.append("")

    domain_index_to_key = {
        d.name: {index: key for key, index in d.members} for d in domains
    }
    domain_widths = {d.name: d.width for d in domains}

    # ---- 1. per-domain member index constants + combined jump table +
    # Dispatch (§16, Z80-specific table shape -- identical to
    # export_z80_sjasmplus.py except for assembler syntax) -- unchanged
    # by layout, identifier-domain dispatch is orthogonal to instance
    # data layout. ----
    for d in domains:
        if d.kind != "identifier":
            lines.append(f"; --- domain: {d.name} (flags, width {d.width}) ---")
            for key, value in d.members:
                lines.append(f"{d.name}_{key} equ {value}")
            lines.append("")
            continue
        lines.append(f"; --- domain: {d.name} (indexed form, width {d.width}) ---")
        for key, index in d.members:
            lines.append(f"{d.name}_{key} equ {index}")
        lines.append("")
        lines.append(f"{d.name}_JumpTable:")
        for key, _index in d.members:
            lines.append(f"\tdw {d.name}_{key}_Handler")
        lines.append("")
        lines.extend(_render_dispatch(d.name))
        lines.append("")

    if layout == "soa":
        # ---- SoA: one array per leaf field, no struct, no registry, no
        # Find() (§13.4/§13.7) -- same reasoning as export_z80_sjasmplus.py.
        for t in types:
            lines.append(f"; --- type: {t.name} (SoA field arrays) ---")
            for inst in t.instances:
                lines.append(f"{t.name}_{inst.name}_Index equ {inst.index}")
            lines.append("")
            for path, type_tokens, values in gather_soa_columns(t):
                n = _string_n(type_tokens)
                if n is not None:
                    raise ExportZ80Error(
                        f"{t.name}.{path}: string N fields are not yet "
                        f"supported in --layout=soa (§13.7) -- see "
                        f"export_z80_sjasmplus.py's identical rejection "
                        f"for the full reasoning; left for a future pass "
                        f"rather than emitting something wrong.")
                if _try_parse_array_type(type_tokens.strip()) is not None:
                    raise ExportZ80Error(
                        f"{t.name}.{path}: array-typed fields are not yet "
                        "supported in --layout=soa -- matching this "
                        "target's own SoA string-field gap just above "
                        "(and 6502's identical precedent), arrays are "
                        "AoS-only for now; use --layout aos instead")
                directive = _leaf_directive(type_tokens, domain_widths)
                label = f"{t.name}_{path}"
                lines.append(f"{label}:")
                for inst_name, value in zip((i.name for i in t.instances), values):
                    if isinstance(value, tuple) and value[0] == "domain_index":
                        _, domain, index = value
                        key = domain_index_to_key[domain][index]
                        lines.append(f"\t{directive} {domain}_{key}\t; {inst_name}")
                    else:
                        lines.append(f"\t{directive} {value}\t; {inst_name}")
                lines.append("")
        return "\n".join(lines)

    # ---- 2. instance data tables (AoS) ----
    # {Type}_Instances (§16.1.1) labels the dense array as a whole and is
    # ALWAYS emitted, regardless of any flag -- the struct data has to
    # live somewhere. Per-instance labels are kept alongside it (harness
    # and hand-written callers reference them by name).
    for t in types:
        size = type_sizeof(t, reg) if reg is not None else None
        lines.append(f"; --- type: {t.name} (AoS instance data) ---")
        if size is not None:
            lines.append(f"{t.name}_Sizeof equ {size}")
        lines.append(f"{t.name}_Instances:")
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}:")
            for (path, type_tokens), value in zip(t.leaves, inst.leaf_values):
                n = _string_n(type_tokens)
                if n is not None:
                    lines.append(render_string_leaf(value, n, path, directive="db"))
                    continue
                array_info = _try_parse_array_type(type_tokens.strip())
                if array_info is not None:
                    flat = flatten_array_ir_value(value, array_info.dims)
                    elem_n = _string_n(array_info.element_type)
                    for i, v in enumerate(flat):
                        elem_path = f"{path}[{i}]"
                        if elem_n is not None:
                            lines.append(render_string_leaf(v, elem_n, elem_path, directive="db"))
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

    # ---- 3. registry: dense-index direct lookup, no search (§10.1,
    # carried over unchanged: "the problem simply never arises") ----
    for t in types:
        n = len(t.instances)
        lines.append(f"; --- type: {t.name} registry (dense declaration-order index, no stable ID) ---")
        lines.append(f"{t.name}_Registry_Count equ {n}")
        size = type_sizeof(t, reg) if reg is not None else None
        for inst in t.instances:
            lines.append(f"{t.name}_{inst.name}_Index equ {inst.index}")
        if pointer_table:
            lines.append(f"{t.name}_Registry:")
            for inst in t.instances:
                lines.append(f"\tdw {t.name}_{inst.name}")
        lines.append("")
        if find_macro:
            lines.extend(_render_find_macro(t.name, pointer_table, size))
            lines.append("")
        lines.extend(_render_index_lookup(t.name, pointer_table, size))
        lines.append("")

    return "\n".join(lines)


def _render_dispatch(domain_name: str) -> list:
    """§16/§10.2: identical logic/registers to
    export_z80_sjasmplus.py's version -- input A = domain member index,
    computed entirely in registers, tail-call via `jp (hl)`. Combined-
    table version: zero-extend the index into HL once, double it
    (`add hl,hl`), add the table base, read the 2-byte entry via
    `ld a,(hl) / inc hl / ld h,(hl) / ld l,a`."""
    D = domain_name
    return [
        f"{D}_Dispatch:",
        "\tld l, a",
        "\tld h, 0",
        "\tadd hl, hl",
        f"\tld de, {D}_JumpTable",
        "\tadd hl, de",
        "\tld a, (hl)",
        "\tinc hl",
        "\tld h, (hl)",
        "\tld l, a",
        "\tjp (hl)",
    ]


def _find_body(type_name: str, pointer_table: bool, size) -> list:
    """Instruction sequence shared by both forms of {Type}_Find
    (§16.1.1). Input: A = dense index. Output: HL = instance address.
    No label, no `ret` -- so the callable subroutine and the inline
    macro cannot drift apart. Identical logic and registers to
    export_z80_sjasmplus.py's version; the two renderers duplicate this
    deliberately, matching how _render_dispatch is already duplicated
    (each renderer stays self-contained per this project's convention).

    HL is the fixed output register, per §16.1.1 and the existing
    harness assertions. Measured on a real Z80 emulator: the
    `ld a,(hl) / inc hl / ld h,(hl) / ld l,a` tail costs 24 T and is
    already optimal under that constraint -- the BC form is 20 T but
    returns in BC, and moving it back to HL costs 28 T total (a
    regression); the DE + `ex de,hl` form ties at 24 T."""
    T = type_name
    if pointer_table:
        return [
            "\tld l, a",
            "\tld h, 0",
            "\tadd hl, hl",
            f"\tld de, {T}_Registry",
            "\tadd hl, de",
            "\tld a, (hl)",
            "\tinc hl",
            "\tld h, (hl)",
            "\tld l, a",
        ]

    from .export_z80 import shift_add_multiply, needs_index_copy
    if size is None:
        raise ValueError(
            "--z80-pointer-table=off needs sizeof(Type), which requires the "
            "registry (`reg=`) to be passed through to the renderer")
    body = ["\tld l, a", "\tld h, 0"]
    if needs_index_copy(size):
        body.append("\tld d, h")
        body.append("\tld e, l")
    body.extend("\t" + m for m in shift_add_multiply(size))
    body.append(f"\tld de, {T}_Instances")
    body.append("\tadd hl, de")
    return body


def _render_index_lookup(type_name: str, pointer_table: bool = True, size=None) -> list:
    """Direct O(1) indexed lookup -- nothing to search for, the dense
    index IS the identity (§10.1/§16). Callable subroutine form, which
    remains the default for every consumer (§16.1.1)."""
    return [f"{type_name}_Find:"] + _find_body(type_name, pointer_table, size) + ["\tret"]


def _render_find_macro(type_name: str, pointer_table: bool = True, size=None) -> list:
    """Opt-in inline MACRO variant, emitted alongside -- never instead
    of -- the callable subroutine. Avoids the call+ret (17 + 10 = 27
    T-states) at each call site, at the cost of code size per
    expansion, hence opt-in via --z80-find-macro=on.

    `MACRO`/`ENDM` confirmed directly against the real built
    z88dk-z80asm binary, not assumed from SjASMPlus -- the two
    assemblers genuinely differ elsewhere (label colon required here,
    no `low()`/`high()` builtins), so macro support was verified
    separately. Both expand to byte-identical code."""
    return ([f"; {type_name}_Find_Inline -- inline MACRO form of {type_name}_Find.",
             "; NOTE: a macro must be DEFINED before it is USED. If this file is",
             "; pulled in with `include`, the include must appear BEFORE any call",
             "; site -- unlike labels, macros are not forward-referenceable, and",
             "; the assembler reports the use site as an unrecognized instruction",
             "; rather than an ordering problem. Confirmed directly against both",
             "; real assemblers.",
             f"\tMACRO {type_name}_Find_Inline"]
            + _find_body(type_name, pointer_table, size)
            + ["\tENDM"])
