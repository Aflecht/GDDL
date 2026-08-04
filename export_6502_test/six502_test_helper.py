"""
Reusable 6502 test-execution helper, using the `py65` PyPI package
(pure-Python 6502/65C02 emulator) -- mirrors z80_test_helper.py's role
for the Z80 renderers, same discipline: confirmed API usage against
the real installed library, not guessed.

Confirmed directly (not assumed):
  - `MPU()` exposes a plain 64KB Python list at `.memory` -- direct
    index assignment loads code/data, no special "load" call needed.
  - `.step()` executes exactly one instruction and advances `.pc`.
  - Registers are plain attributes: `.a`, `.x`, `.y`, `.pc`.
  - Every harness in this project ends on a `BRK` (opcode $00) as an
    explicit "stop and inspect memory" marker (see each harness's own
    trailing comment). `run_to_brk` below stops BEFORE executing the
    BRK itself -- deliberately not stepping into it -- since BRK on
    NMOS 6502 pushes PC+2 and status onto the stack and jumps through
    the IRQ/BRK vector at $FFFE, which nothing in these harnesses ever
    sets up; executing it for real would jump to whatever garbage
    happens to be at $(FFFE), not stop cleanly.
"""

import re


def load_symbols_acme(sym_path):
    """Parses ACME's --symbollist output. Confirmed format directly:
    `\\tNAME\\t= $HEX` or `\\tNAME\\t= $HEX\\t; unused` per line --
    always hex with a `$` prefix, even for symbols defined as plain
    decimal constants in source (e.g. `Creature_Goblin_Index = $0`)."""
    symbols = {}
    for line in open(sym_path):
        m = re.match(r"\s*(\S+)\s*=\s*\$([0-9A-Fa-f]+)", line)
        if m:
            symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def load_symbols_64tass(lst_path):
    """Parses 64tass's -l label-list output. Confirmed format directly:
    `NAME\\t\\t= $HEX` for real addresses, but `NAME= N` (decimal, NO
    `$` prefix, no space before `=` once the name is long enough to
    butt up against the tab stop) for symbols defined as plain decimal
    constants in source -- e.g. `Creature_Goblin_Index= 0` versus
    `Creature_Find\\t= $c034`. Both forms confirmed side by side in the
    same real label file, not assumed to be consistent."""
    symbols = {}
    for line in open(lst_path):
        m = re.match(r"(\S+?)\s*=\s*(\$?)([0-9A-Fa-f]+)", line)
        if m:
            name, dollar, val = m.groups()
            symbols[name] = int(val, 16 if dollar == "$" else 10)
    return symbols


def load_symbols_kickassembler(sym_path):
    """Parses KickAssembler's .sym file output. Confirmed format:
    `.label NAME=$HEX` (with `$` always present) -- confirmed directly
    by assembling real source and reading the output, since this is
    another one of the small cross-assembler differences that matters."""
    symbols = {}
    for line in open(sym_path):
        m = re.match(r"\.label\s+(\S+)=\$([0-9A-Fa-f]+)", line.strip())
        if m:
            symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def load_prg_kickassembler(m, path, expected_org=None):
    """Loads a KickAssembler PRG output file. PRG format: first 2 bytes
    are the load address in little-endian (the machine's native byte
    order), confirmed directly. The rest is the assembled binary,
    placed starting at that load address. KickAssembler has no flat-
    binary output mode -- the PRG header is always present.

    If expected_org is given, asserts the embedded load address matches,
    catching any accidental org mismatch rather than silently loading at
    the wrong address."""
    with open(path, "rb") as f:
        data = f.read()
    if len(data) < 2:
        raise RuntimeError(f"PRG file {path!r} is too short (< 2 bytes)")
    org = data[0] | (data[1] << 8)
    if expected_org is not None and org != expected_org:
        raise RuntimeError(
            f"PRG file {path!r} has load address ${org:04X}, "
            f"expected ${expected_org:04X}")
    code = data[2:]
    for i, b in enumerate(code):
        m.memory[org + i] = b
    return org


def run_to_brk(m, max_steps=100000):
    """Single-steps until the byte about to execute is $00 (BRK),
    stopping BEFORE executing it -- see module docstring for why BRK
    itself is never actually run. Raises if BRK is never reached within
    max_steps, rather than looping forever on a genuine bug."""
    for _ in range(max_steps):
        if m.memory[m.pc] == 0x00:
            return
        m.step()
    raise RuntimeError(
        f"never reached a BRK within {max_steps} steps -- "
        f"stuck at PC={m.pc:#06x}"
    )


def run_to_pc(m, target_pc, max_steps=100000):
    """Single-steps until PC reaches target_pc exactly -- for harnesses
    that mark a specific label rather than relying on a trailing BRK.
    Raises if it never does within max_steps."""
    for _ in range(max_steps):
        if m.pc == target_pc:
            return
        m.step()
    raise RuntimeError(
        f"never reached PC={target_pc:#06x} within {max_steps} steps -- "
        f"stuck at PC={m.pc:#06x}"
    )


def load_binary_at(m, path, org):
    """Loads a flat binary (ACME's `-f plain` / 64tass's `--nostart`
    output, both confirmed to start directly at the assembled org
    address with no leading padding from $0000) into memory at `org`."""
    with open(path, "rb") as f:
        code = f.read()
    for i, b in enumerate(code):
        m.memory[org + i] = b
