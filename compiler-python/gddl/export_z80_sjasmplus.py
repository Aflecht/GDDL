# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Z80 export, SjASMPlus renderer (§16.1: first of three planned output
paths -- assembly-only, following the 6502 exporter's architecture
directly, a different assembler syntax to target).

Syntax confirmed directly against the real, built `sjasmplus` binary
and its bundled tutorial/examples -- not assumed to resemble ACME,
KickAssembler, or 64tass (all three turned out to genuinely differ
from each other, so there was no reason to expect this one matches
any of them either). Confirmed:
  - Comments: BOTH `;` and `//` work as line comments (confirmed via
    the bundled tutorial.asm) -- using `;` here for consistency with
    every other renderer's style, not because `//` doesn't work.
  - Data directives: `db` / `dw` (byte/word) -- confirmed case-
    insensitive by direct test (uppercase in the bundled tutorial,
    lowercase tested directly here, both assemble identically).
    `dw Label` with a real forward label reference (not just a numeric
    literal) confirmed directly to emit the label's address as a
    correct little-endian word.
  - Constants: `equ` (not bare `=` like ACME/64tass, not `.label`
    like KickAssembler -- a fourth distinct spelling).
  - Origin: `org` (not `*=`).
  - Include: `include "file"` (a fourth distinct spelling, joining
    ACME's `!source`, KickAssembler's `#import`, 64tass's `.include`).
  - Labels: colon is OPTIONAL (confirmed via the tutorial's own
    comment: "labels must start at beginning of line, trailing colon
    is optional") -- kept here for consistency with every other
    renderer's style.
  - **Instructions must be indented -- a label is identified by
    starting at column 0, an instruction must NOT.** This is a real,
    confirmed syntax rule (not true of ACME/KickAssembler/64tass, all
    of which tolerate an instruction at column 0), and is respected
    throughout this renderer: every mnemonic line is emitted with
    leading whitespace, every label line has none.

Z80-specific design choice, not carried over from 6502 by default:
**no zero-page-equivalent scratch memory is used at all** -- see
export_z80.py's module docstring for the reasoning (the Z80's richer
register set makes the whole index-to-address computation possible
in registers alone). Dispatch and Find share one calling
convention: input index in A, and (for Find) output pointer
in HL. Dispatch ends with a tail-call `jp (hl)` (not `call`/`ret`) into
the resolved handler -- the same trampoline pattern already validated
for 6502/68000: the ORIGINAL caller's `call Domain_Dispatch` return
address is what the handler's own eventual `ret` returns through,
since `jp` never touches the stack.

**Table shape: single combined table of `dw`-declared 2-byte entries,
indexed by `index * 2`** -- Z80-only, deliberately NOT how 6502 does
this (6502 stays on its split Lo/Hi two-array design unchanged, see
export_z80.py's module docstring for why the two CPUs genuinely
diverge here). `index * 2` is one cheap `add hl,hl` after zero-
extending the index into HL -- doubling isn't the arbitrary multiply
this whole discipline exists to avoid, it's a shift, same category as
6502's own SoA field-width shifts (§13). The combined-table address is
then read via the classic `ld a,(hl) / inc hl / ld h,(hl) / ld l,a`
sequence -- ~10 instructions total versus the previous split-array
design's ~12, since the index only needs zero-extending into HL once
instead of twice (one lookup into one table, not two lookups into two
tables).
"""

from .export_z80 import DomainInfo, TypeInfo, _string_n, render_string_leaf, ExportZ80Error


_WIDTH_TO_DIRECTIVE = {"u8": "db", "u16": "dw", "u32": None, "u64": None}


def _leaf_directive(type_tokens: str, domain_widths: dict) -> str:
    """The SjASMPlus storage directive for one leaf field. Scalars map
    by their own declared type; identifier-typed leaves (plain Domain
    or @Domain -- indistinguishable on this target) map by their
    DOMAIN's declared width, since what's actually stored is the
    domain's index, not the field's nominal type. `string N` leaves are
    NOT handled here -- they need a multi-item db line (quoted literal
    + explicit padding, §13.2), not a single directive+value pair, so
    the instance-data emission loop below checks _string_n() first and
    calls render_string_leaf() directly, bypassing this function."""
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


def render_sjasmplus(domains: list, types: list, pointer_table: bool = True,
                     find_macro: bool = False, reg=None, layout: str = "aos") -> str:
    from .export_z80 import type_sizeof, gather_soa_columns

    lines = []
    lines.append("; Auto-generated by the GDDL compiler (Z80 / SjASMPlus). Do not edit by hand.")
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
    # Dispatch (§16, Z80-specific table shape) -- unchanged by layout,
    # identifier-domain dispatch is orthogonal to instance data layout. ----
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
        # Find() (§13.4/§13.7) -- the same dense index that would find an
        # AoS instance already indexes every one of these arrays too.
        # u16 fields need only a cheap `add hl,hl` (x2 shift) to index,
        # never lo/hi splitting the way 6502 needs -- Z80 has real 16-bit
        # loads. string N is explicitly rejected below (matching 6502's
        # own precedent): its width isn't guaranteed a power of two, so
        # indexing it would need a real multiply, not a shift, and that
        # renderer hasn't been designed yet -- left for a future pass
        # rather than silently emitting something wrong.
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
                        f"supported in --layout=soa (§13.7) -- the field's "
                        f"width isn't guaranteed a power of two, so indexing "
                        f"it would need a real multiply, not the cheap shift "
                        f"every scalar SoA field uses. Left for a future "
                        f"pass, matching 6502's identical, already-precedented "
                        f"scope limit, rather than emitting something wrong.")
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
    # ALWAYS emitted -- the struct data has to live somewhere regardless
    # of any flag. The per-instance labels are kept alongside it: they
    # cost nothing, they're what test harnesses and hand-written callers
    # reference by name, and removing them would be an unrelated breaking
    # change.
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
        size = type_sizeof(t, reg) if reg is not None else None
        lines.append(f"; --- type: {t.name} registry (dense declaration-order index, no stable ID) ---")
        lines.append(f"{t.name}_Registry_Count equ {n}")
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
    """§16/§10.2: Z80-idiom dispatch. Input: A = domain member index.
    Computes the handler address entirely in registers -- no scratch
    memory needed at all, see module docstring -- then tail-calls into
    it with `jp (hl)`, never touching the stack, so the handler's own
    eventual `ret` returns through the ORIGINAL caller's
    `call Domain_Dispatch`.

    Combined-table version: zero-extend the index into HL once,
    double it (`add hl,hl` -- a cheap shift, not the arbitrary multiply
    this discipline avoids), add the table base, then read the 2-byte
    entry with the classic `ld a,(hl) / inc hl / ld h,(hl) / ld l,a`
    sequence. ~10 instructions versus the prior split-table version's
    ~12 -- the index only needs zero-extending into HL once instead of
    twice, since there's only one table to index into now."""
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
    """The instruction sequence common to both forms of {Type}_Find
    (§16.1.1). Input: A = dense index. Output: HL = instance address.
    Emitted with no label and no `ret`, so the callable subroutine and
    the inline macro are guaranteed to share one implementation rather
    than drifting apart as two hand-maintained copies.

    HL is the fixed output register, per §16.1.1's stated convention and
    the existing harness assertions. Measured directly on a real Z80
    emulator: the classic `ld a,(hl) / inc hl / ld h,(hl) / ld l,a`
    tail below costs 24 T-states and is already optimal under that
    constraint. Loading through BC instead (`ld c,(hl) / inc hl /
    ld b,(hl)`) is 20 T but lands the pointer in BC; moving it back to
    HL costs 8 more, for 28 T and one extra byte -- a regression, not a
    saving. The DE variant plus `ex de,hl` ties at exactly 24 T, so
    there is nothing to win here by changing the sequence."""
    T = type_name
    if pointer_table:
        # Pointer table on: one flat `index * 2` (a Z80 pointer is 2
        # bytes) into {Type}_Registry, then dereference. Constant cost
        # regardless of sizeof(Type) -- that flatness is the whole
        # point of the table (§16.2).
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

    # Pointer table off: address the instance directly as
    # {Type}_Instances + index*sizeof(Type). No table, no dereference,
    # no 2-bytes-per-instance of storage -- but the index computation
    # now scales with sizeof(Type), which is exactly the tradeoff
    # §16.2's crossover table measures.
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
    index IS the identity (§10.1/§16). Input: A = dense index. Output:
    HL = the instance's data address.

    This is the callable subroutine form, which stays the default for
    every consumer (§16.1.1)."""
    return [f"{type_name}_Find:"] + _find_body(type_name, pointer_table, size) + ["\tret"]


def _render_find_macro(type_name: str, pointer_table: bool = True, size=None) -> list:
    """Opt-in inline MACRO variant of {Type}_Find, emitted alongside --
    never instead of -- the callable subroutine.

    Rationale: the callable form costs a `call` (17 T) plus the `ret`
    (10 T) = 27 T-states of pure overhead at every call site, which the
    macro avoids entirely by expanding in place. The cost is code size,
    paid once per expansion rather than once per program, so this is
    opt-in (`--z80-find-macro=on`) and the callable form remains the
    default: a lookup on a cold path should not silently grow the
    binary, and most consumers have far more call sites than hot ones.

    Both forms are generated from the same `_find_body`, so they cannot
    diverge. `MACRO`/`ENDM` syntax confirmed directly against the real
    built binaries for BOTH assemblers -- they agree here (unlike the
    label-colon and `low()`/`high()` rules, where they genuinely
    differ), and both were verified to expand to byte-identical code."""
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
