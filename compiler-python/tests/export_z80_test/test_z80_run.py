# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated Z80/SjASMPlus output (dispatch subroutine +
dense-index registry lookup) by actually assembling with the real
sjasmplus binary and executing the result with the z80 PyPI library --
same standard as every other target (real assemble, real execute, not
just "should work").

Run from /home/claude/gddl (or wherever the project root is) after
regenerating generated_z80_minimal.asm and re-assembling
test_z80_harness.asm with sjasmplus --sym=.
"""

import z80
from z80_test_helper import load_symbols, run_to_pc


def main():
    with open("test_z80_harness.bin", "rb") as f:
        code = f.read()
    symbols = load_symbols("test_z80_harness.sym")

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)
    m.pc = symbols["Main"]

    failures = []

    def check(name, actual, expected):
        if actual != expected:
            failures.append(f"{name}: got {actual!r}, expected {expected!r}")

    run_to_pc(m, symbols["AfterDispatch1"])
    check("Test 1 (melee dispatch) Signal", m.memory[symbols["Signal"]], 1)

    run_to_pc(m, symbols["AfterDispatch2"])
    check("Test 2 (ranged dispatch) Signal", m.memory[symbols["Signal"]], 2)

    run_to_pc(m, symbols["AfterLookup1"])
    hl = (m.h << 8) | m.l
    check("Test 3 (Goblin lookup) HL", hl, symbols["Creature_Goblin"])

    run_to_pc(m, symbols["AfterLookup2"])
    hl = (m.h << 8) | m.l
    check("Test 4 (Archer lookup) HL", hl, symbols["Creature_Archer"])

    if failures:
        print("FAILURES:")
        for f in failures:
            print(" ", f)
        raise SystemExit(1)

    print("All Z80/SjASMPlus checks passed.")


if __name__ == "__main__":
    main()
