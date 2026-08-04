"""
Validates the generated 6502/ACME output (dispatch subroutines +
dense-index registry lookup, now named `{Type}_Find`) by actually
assembling with the real `acme` binary and executing the result with
`py65` -- same standard as every other target: real assemble, real
execute, not just "should work".

Run from export_6502_test/ after:
  acme -o test_6502_harness.bin --format plain \
       --symbollist test_6502_harness.sym test_6502_harness.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_acme, run_to_brk, load_binary_at


def main():
    symbols = load_symbols_acme("test_6502_harness.sym")
    m = MPU()
    load_binary_at(m, "test_6502_harness.bin", 0xC000)
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
        raise SystemExit("6502/ACME check FAILED")
    print("All 6502/ACME checks passed.")


if __name__ == "__main__":
    main()
