# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated Z80/SjASMPlus output for §13.7 SoA support.
Closes the gap flagged in HANDOFF.md ("--layout=soa is not
implemented for Z80 yet"). Same standard as every other target: real
assemble, real execute, not just "should work".

Run from export_z80_test/ after:
  sjasmplus --raw=test_z80_soa_harness.bin \\
            --sym=test_z80_soa_harness.sym \\
            test_z80_soa_harness.asm
"""

import z80
from z80_test_helper import load_symbols, run_to_pc


def main():
    with open("test_z80_soa_harness.bin", "rb") as f:
        code = f.read()
    symbols = load_symbols("test_z80_soa_harness.sym")

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)
    m.pc = symbols["Main"]

    run_to_pc(m, symbols["AfterReads"])

    def u16(addr):
        return m.memory[addr] | (m.memory[addr + 1] << 8)

    checks = [
        ("Bow power (u16 SoA array, shift-indexed)", u16(symbols["Result_bow_power"]), 15),
        ("Sword rarity (u8/domain SoA array, direct-indexed)",
         m.memory[symbols["Result_sword_rarity"]], 1),  # Rarity_rare = 1
        ("Shield power", u16(symbols["Result_shield_power"]), 8),
    ]
    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got}, want {want}  [{status}]")

    if failed:
        raise SystemExit("Z80 SoA (SjASMPlus) check FAILED")
    print("All Z80/SjASMPlus SoA checks passed.")


if __name__ == "__main__":
    main()
