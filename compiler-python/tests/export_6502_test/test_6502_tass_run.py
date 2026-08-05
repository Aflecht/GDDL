# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
64tass counterpart of test_6502_run.py -- same logic, real second
assembler, since the two dialects have confirmed genuine differences
elsewhere (label-list format, NMOS-vs-CPU-target flags) and are never
assumed to behave alike without direct verification.

Run from export_6502_test/ after:
  64tass --nostart -o test_6502_harness_tass.bin \
         -l test_6502_harness_tass.lst test_6502_harness_tass.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_64tass, run_to_brk, load_binary_at


def main():
    symbols = load_symbols_64tass("test_6502_harness_tass.lst")
    m = MPU()
    load_binary_at(m, "test_6502_harness_tass.bin", 0xC000)
    m.pc = symbols["Main"]
    run_to_brk(m)

    def byte_at(sym):
        return m.memory[symbols[sym]]

    def ptr16(lo_sym, hi_sym):
        return byte_at(lo_sym) | (byte_at(hi_sym) << 8)

    checks = [
        ("GoblinSignal", byte_at("GoblinSignal"), 1),
        ("ArcherSignal", byte_at("ArcherSignal"), 2),
        ("FireSignal", byte_at("FireSignal"), 3),
        ("IceSignal", byte_at("IceSignal"), 4),
        ("LightningSignal", byte_at("LightningSignal"), 5),
        ("Creature_Find(Goblin)",
         ptr16("CreatureGoblinPtrLo", "CreatureGoblinPtrHi"),
         symbols["Creature_Goblin"]),
        ("Creature_Find(Archer)",
         ptr16("CreatureArcherPtrLo", "CreatureArcherPtrHi"),
         symbols["Creature_Archer"]),
        ("Item_Find(Sword)",
         ptr16("ItemSwordPtrLo", "ItemSwordPtrHi"),
         symbols["Item_Sword"]),
        ("Item_Find(Shield)",
         ptr16("ItemShieldPtrLo", "ItemShieldPtrHi"),
         symbols["Item_Shield"]),
    ]

    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got:#06x}, want {want:#06x}  [{status}]"
              if got > 0xFF or want > 0xFF else
              f"  {name}: got {got}, want {want}  [{status}]")

    if failed:
        raise SystemExit("6502/64tass check FAILED")
    print("All 6502/64tass checks passed.")


if __name__ == "__main__":
    main()
