"""
Z80 export, z88dk C-mode renderer (§16.1 third output path).

Implementation style follows C++ (§14) and 68000 (§15) -- real structs,
a real compiler doing codegen -- while the *identity system* stays
6502-style (§10): dense declaration-order indices, no logical IDs, no
instance stable IDs. §16.1 is explicit that these are independent axes:
C-vs-assembly is an implementation-style choice, whereas the Z80's
missing hardware multiply is a CPU-level fact that no language choice
changes.

**Target: C89 via `zsdcc` only.** Same language tier as 68000's `vbcc`
target (§15.1), for the same "avoid 'partial C99' as a fuzzy target"
reasoning. `sccz80` is deliberately unsupported (§16.1): it inlines
constant multiplication only for an enumerated, hardcoded set of
multipliers (1-10, 12, 14, 15, 16, 20, 32, 40, 64, 256, 512, 1024,
2048 -- from its own `quikmult()`), and any struct size outside that
list falls through to a ~500+ T-state runtime multiply call. GDDL
cannot constrain what struct sizes a project's data produces, so the
cliff is unacceptable; `zsdcc` strength-reduces every constant multiply
with no such cliff. **This means invoking `zcc` with `-compiler=sdcc`
explicitly -- `sccz80` is `zcc`'s silent default otherwise**, which is
the single easiest way to accidentally get unsupported output that
still compiles.

Header/`.c` split (§16.2.1) follows 68000's reasoning, NOT C++'s: there
is no `constexpr`-retention problem to solve here (C has none). It is
the ordinary C rule -- a definition can only live in one `.c` file, and
a second translation unit including the same definitions breaks with
duplicate-symbol linker errors. A single directly-`#include`d file is
test-harness convenience only, never what this emits for real use.

  - Header: struct/type definitions, domain index constants, `extern`
    declarations for `{Type}_Instances`, `{Type}_Registry` (only when
    §16.2's flag is on), and `{Type}_Find`'s signature.
  - `.c`: the actual `{Type}_Instances` definitions, the actual
    `{Type}_Registry` contents (if emitted), and `{Type}_Find`'s body.

Naming is shared with both assembly paths (§16.1.1): `{Type}_Instances`,
`{Type}_Registry`, `{Type}_Find`.
"""

from export_z80 import type_sizeof, ExportZ80Error, _string_n


# C89 types for zsdcc/Z80. `int` is 16-bit on this target, so u16/i16
# map to (unsigned) int rather than anything wider. Confirmed against
# the real built zsdcc rather than assumed from the flag name -- the
# same discipline applied to vbcc's +tos giving 32-bit int (§15).
_C_TYPES = {
    "u8": "unsigned char",
    "i8": "signed char",
    "u16": "unsigned int",
    "i16": "int",
}


def _c_string_literal(s: str) -> str:
    """Escapes a Python string for a C89 string literal. Same rule as
    export_cpp.py's _cpp_string_literal (backslash then quote) --
    confirmed by direct compile+execute with real zsdcc (not assumed
    identical just because the syntax looks the same as C++) that a
    plain C string literal containing raw multi-byte UTF-8 bytes
    round-trips correctly, and that C89's own implicit zero-padding of
    a `char field[N] = "text";` initializer (shorter than N) fills the
    rest with zero bytes -- so unlike the assembly paths, no explicit
    padding is emitted here; the language does it for free."""
    escaped = s.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _c_type(type_tokens: str, reg) -> str:
    """C type for one flattened leaf. Identifier-typed leaves take their
    DOMAIN's declared width -- what's stored is the dense domain index,
    not the field's nominal type, exactly as on the assembly paths.

    `string N` returns `"char[{n}]"` -- handled specially at the
    declaration site (_render_header's field loop), exactly mirroring
    export_cpp.py's `_cpp_field_type`: a C array's size goes after the
    identifier (`char name[12];`), never interpolated before it like a
    normal type name, so the caller can't just do
    `f"{_c_type(...)} {field_name};"` for this one case."""
    t = type_tokens.strip()
    if t.startswith("@"):
        t = t[1:].strip()
    if t in reg.identifier_widths:
        t = reg.identifier_widths[t]
    n = _string_n(t)
    if n is not None:
        return f"char[{n}]"
    if t not in _C_TYPES:
        raise ExportZ80Error(
            f"z88dk C mode doesn't support field type {type_tokens!r} yet "
            "(scalar u8/u16/i8/i16, identifier-typed, and string N leaf "
            "fields only)")
    return _C_TYPES[t]


def _c_field_name(path: str) -> str:
    """Flattened leaf path -> a legal C identifier. Composition is
    flattened per §13.1, so a nested path like `stats.hp` becomes a
    single `stats_hp` member of one flat struct -- matching what the
    assembly paths already emit as a flat run of db/dw."""
    return path.replace(".", "_")


def render_z88dk_c(domains: list, types: list, pointer_table: bool = True,
                   reg=None) -> dict:
    """Returns {".h": text, ".c": text} -- always two files (§16.2.1).
    Never a single combined file: that is test-harness convenience only,
    and emitting it as a normal mode would invite the duplicate-symbol
    breakage the split exists to prevent."""
    if reg is None:
        raise ValueError("z88dk C mode needs the registry (`reg=`) for type sizing")

    header = _render_header(domains, types, pointer_table, reg)
    csrc = _render_c(domains, types, pointer_table, reg)
    return {".h": header, ".c": csrc}


def _banner(kind: str, pointer_table: bool) -> list:
    return [
        f"/* Auto-generated by the GDDL compiler (Z80 / z88dk C mode). Do not edit by hand. */",
        f"/* {kind} -- C89, targeting zsdcc. Compile with: zcc +<target> -compiler=sdcc ... */",
        f"/* --z80-pointer-table={'on' if pointer_table else 'off'} (SPEC S16.2) */",
        "",
    ]


def _guard(name: str) -> str:
    return f"GDDL_{name.upper()}_H"


def _render_header(domains, types, pointer_table, reg) -> str:
    guard = _guard("z80_export")
    lines = _banner("Header: declarations only", pointer_table)
    lines.append(f"#ifndef {guard}")
    lines.append(f"#define {guard}")
    lines.append("")

    # ---- domain member index constants ----
    # Plain `#define`s rather than a C89 enum: an enum's underlying type
    # is implementation-defined (`int`, so 16-bit here), which would
    # silently widen a u8 domain index in any expression it appears in.
    # A #define keeps the constant untyped and lets the struct field's
    # own declared width govern storage.
    for d in domains:
        lines.append(f"/* --- domain: {d.name} (indexed form, width {d.width}) --- */")
        for key, index in d.members:
            lines.append(f"#define {d.name}_{key} {index}")
        lines.append(f"#define {d.name}_Count {len(d.members)}")
        lines.append("")

    # ---- struct definitions + extern declarations ----
    for t in types:
        size = type_sizeof(t, reg)
        n = len(t.instances)
        lines.append(f"/* --- type: {t.name} (AoS, sizeof == {size}) --- */")
        lines.append("typedef struct {")
        for path, tokens in t.leaves:
            str_n = _string_n(tokens)
            if str_n is not None:
                # C array size goes after the identifier -- can't just
                # interpolate _c_type()'s "char[N]" before the field
                # name the way every other type is handled. Same
                # special-casing export_cpp.py does at its own
                # declaration site.
                lines.append(f"    char {_c_field_name(path)}[{str_n}];")
            else:
                lines.append(f"    {_c_type(tokens, reg)} {_c_field_name(path)};")
        lines.append(f"}} {t.name};")
        lines.append("")
        lines.append(f"#define {t.name}_Registry_Count {n}")
        for inst in t.instances:
            lines.append(f"#define {t.name}_{inst.name}_Index {inst.index}")
        lines.append("")
        # {Type}_Instances is always declared -- the data has to live
        # somewhere regardless of the flag (§16.1.1).
        lines.append(f"extern const {t.name} {t.name}_Instances[{t.name}_Registry_Count];")
        if pointer_table:
            lines.append(
                f"extern const {t.name} *const "
                f"{t.name}_Registry[{t.name}_Registry_Count];")
        lines.append(f"const {t.name} *{t.name}_Find(unsigned char index);")
        lines.append("")

    lines.append(f"#endif /* {guard} */")
    return "\n".join(lines) + "\n"


def _render_value(value, tokens, reg, domain_index_to_key) -> str:
    """One leaf's initializer. Identifier values render as the domain's
    named index constant (e.g. `ActionAttack_melee_weapon`) rather than
    a bare integer -- the generated C stays readable and stays in sync
    with the header's #defines, the same way the assembly paths emit
    `db ActionAttack_melee_weapon` rather than `db 0`.

    String values render as a plain C string literal, e.g.
    `"Grubnik"` -- NO explicit padding emitted (unlike the assembly
    paths' `db "text", 0, 0`), since C89 itself zero-pads a
    `char field[N] = "text";` initializer shorter than N for free.
    Confirmed directly against real zsdcc, not assumed."""
    if isinstance(value, tuple) and value[0] == "domain_index":
        _, domain, index = value
        return f"{domain}_{domain_index_to_key[domain][index]}"
    if isinstance(value, str):
        return _c_string_literal(value)
    return str(value)


def _render_c(domains, types, pointer_table, reg) -> str:
    domain_index_to_key = {
        d.name: {index: key for key, index in d.members} for d in domains
    }

    lines = _banner("Definitions", pointer_table)
    lines.append('#include "gddl_z80_export.h"')
    lines.append("")

    for t in types:
        # ---- {Type}_Instances: always emitted ----
        lines.append(f"/* --- type: {t.name} instance data (AoS) --- */")
        lines.append(f"const {t.name} {t.name}_Instances[{t.name}_Registry_Count] = {{")
        for inst in t.instances:
            inits = ", ".join(
                _render_value(v, tokens, reg, domain_index_to_key)
                for (_p, tokens), v in zip(t.leaves, inst.leaf_values))
            lines.append(f"    {{ {inits} }},   /* [{inst.index}] {inst.name} */")
        lines.append("};")
        lines.append("")

        # ---- {Type}_Registry: only when the flag is on (§16.2) ----
        if pointer_table:
            lines.append(
                f"const {t.name} *const {t.name}_Registry"
                f"[{t.name}_Registry_Count] = {{")
            for inst in t.instances:
                lines.append(
                    f"    &{t.name}_Instances[{t.name}_{inst.name}_Index],"
                    f"   /* {inst.name} */")
            lines.append("};")
            lines.append("")

        # ---- {Type}_Find ----
        lines.extend(_render_find(t.name, pointer_table))
        lines.append("")

    return "\n".join(lines) + "\n"


def _render_find(type_name: str, pointer_table: bool) -> list:
    """{Type}_Find: resolve a dense index to an instance pointer.

    Same job and same name as the assembly paths' subroutine (§16.1.1),
    but expressed as ordinary C and left to zsdcc to codegen -- there is
    deliberately no hand-written inline assembly here. That is the whole
    point of C mode following the C++/68000 *implementation* style: the
    multiply-avoidance discipline is satisfied structurally by the flag
    (a pointer table means index*2, never index*sizeof), not by
    hand-tuning instruction sequences the compiler is better at.

    zsdcc strength-reduces the index*sizeof form for ANY constant size,
    which is exactly why §16.1 supports it and rules out sccz80's
    enumerated-multiplier cliff.

    No macro variant is emitted here, unlike the assembly paths: in C
    the compiler already decides whether to inline this, so an
    exporter-emitted macro would be second-guessing it (and a
    function-like macro could not carry the return type safely)."""
    T = type_name
    if pointer_table:
        body = f"    return {T}_Registry[index];"
    else:
        body = f"    return &{T}_Instances[index];"
    return [
        f"const {T} *{T}_Find(unsigned char index)",
        "{",
        body,
        "}",
    ]
