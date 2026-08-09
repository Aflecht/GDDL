# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Real end-to-end toolchain validation for §18 Multi-File Compilation:
assembles the multi-file-generated Z80 output with real SjASMPlus,
executes it with the real z80 emulator, and confirms every field of
every instance -- both directions of cross-file reference -- resolves
correctly through actual assembled machine code, not just inspected
generated text.

Run from this directory after:
  sjasmplus --raw=test_multi_file_z80_harness.bin \
            --sym=test_multi_file_z80_harness.sym \
            test_multi_file_z80_harness.asm
"""

import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "gddl"))
sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "export_z80_test"))

import z80
from z80_test_helper import load_symbols, run_to_pc


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "test_multi_file_z80_harness.bin"), "rb") as f:
        code = f.read()
    symbols = load_symbols(os.path.join(here, "test_multi_file_z80_harness.sym"))

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)
    m.pc = symbols["Main"]
    run_to_pc(m, symbols["AfterReads"])

    checks = [
        ("Sword.damage", m.memory[symbols["ResultSwordDamage"]], 10),
        ("Sword.element (fire)", m.memory[symbols["ResultSwordElement"]], 0),
        ("Bow.damage", m.memory[symbols["ResultBowDamage"]], 5),
        ("Bow.element (lightning)", m.memory[symbols["ResultBowElement"]], 2),
    ]
    failed = False
    for name, got, want in checks:
        ok = got == want
        failed = failed or not ok
        print(f"  {name}: got {got}, want {want}  [{'OK' if ok else 'FAIL'}]")

    if failed:
        raise SystemExit("Multi-file Z80 end-to-end toolchain test FAILED")
    print("All multi-file Z80 end-to-end checks passed "
          "(real SjASMPlus assembly, real z80 execution).")


if __name__ == "__main__":
    main()
