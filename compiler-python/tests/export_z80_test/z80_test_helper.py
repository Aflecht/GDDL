# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Reusable Z80 test-execution helper, using the `z80` PyPI package
(kosarev/z80) -- a bare Z80 CPU emulation library, no OS/disk boot
needed, mirroring `py65`'s role for 6502.

Confirmed API usage against the library's own real examples/tests
(github.com/kosarev/z80), not guessed:
  - `m.ticks_to_stop = 1` before `m.run()` executes exactly one
    instruction (confirmed via examples/single_stepping.py and
    examples/exit_halted_state.py).
  - `m.set_memory_block(addr, bytes)` loads raw bytes directly.
  - Registers are plain attributes: `m.a`, `m.h`, `m.l`, `m.pc`, etc.

NOTE, honestly recorded rather than silently worked around:
`m.set_breakpoint(addr)` + `m.run()` (with no `ticks_to_stop` set) did
NOT behave as expected in direct testing here -- `run()` reported
`_BREAKPOINT_HIT` at an address that was NOT the one marked (the CALL
target of the immediately-preceding instruction, not the intended
breakpoint), even though the library's own test suite
(`tests/test_machine.py::test_breakpoint_trip_and_resume`) shows this
exact combination working correctly in a simpler program. The
difference wasn't tracked down -- possibly some interaction specific
to breakpoints set on the instruction immediately following a `call`,
or something about this library version's build. Given `run_to_pc`
below (built on the CONFIRMED-correct single-step mechanism) works
reliably and was cross-checked against the breakpoint version's
correct single-stepped trace (which matched expectations exactly),
this was the pragmatic choice -- a confirmed-working alternative,
not a guess -- rather than spending further effort chasing the
breakpoint discrepancy down to its root cause.
"""

import re


def load_symbols(sym_path):
    """Parses SjASMPlus's --sym= output ('NAME: EQU 0xHEXVALUE' per
    line) into a dict."""
    symbols = {}
    for line in open(sym_path):
        m = re.match(r"(\S+): EQU 0x([0-9A-Fa-f]+)", line)
        if m:
            symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def load_symbols_z88dk_map(map_path):
    """Parses z88dk-z80asm's -m map-file output ('NAME  = $HEX ; ...'
    per line) into a dict. NOT the same format as -s's .sym file --
    confirmed directly that .sym reports pre-org section-relative
    offsets (e.g. $002A), while .map reports the actual final absolute
    addresses embedded in the assembled binary (e.g. $802A, matching
    a real 'org $8000' base) -- .map is the one to use for locating
    real addresses, .sym is not, despite '.sym' sounding like the more
    obvious choice."""
    symbols = {}
    for line in open(map_path):
        m = re.match(r"(\S+)\s*=\s*\$([0-9A-Fa-f]+)", line)
        if m:
            symbols[m.group(1)] = int(m.group(2), 16)
    return symbols


def run_to_pc(m, target_pc, max_steps=10000):
    """Single-steps (the confirmed-reliable mechanism, not
    breakpoints) until PC reaches target_pc. Raises if it never does
    within max_steps, rather than looping forever on a genuine bug."""
    for _ in range(max_steps):
        if m.pc == target_pc:
            return
        m.ticks_to_stop = 1
        m.run()
    raise RuntimeError(
        f"never reached PC={target_pc:#06x} within {max_steps} steps "
        f"-- stuck at PC={m.pc:#06x}"
    )
