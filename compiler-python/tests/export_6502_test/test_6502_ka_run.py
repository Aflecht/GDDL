# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated 6502/KickAssembler output (rename: {Type}_Find)
by assembling with the real KickAssembler jar and executing via py65.

KickAssembler-specific notes:
  - Output is always a PRG file with a 2-byte load-address header;
    load_prg_kickassembler() handles this transparently.
  - Symbol file format: .label NAME=$HEX (confirmed directly).
  - KickAssembler cannot be apt-installed or fetched (theweb.dk blocked);
    the jar must be manually placed at a known path.

Run from export_6502_test/ after:
  java -jar /path/to/KickAss.jar test_6502_harness_ka.asm \
       -o test_6502_harness_ka.prg
  (the .sym file is written automatically alongside the .prg)
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import (
    load_symbols_kickassembler, run_to_brk, load_prg_kickassembler)


def main():
    symbols = load_symbols_kickassembler("test_6502_harness_ka.sym")
    m = MPU()
    load_prg_kickassembler(m, "test_6502_harness_ka.prg", expected_org=0xC000)
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
        raise SystemExit("6502/KickAssembler rename check FAILED")
    print("All 6502/KickAssembler rename checks passed.")


if __name__ == "__main__":
    main()
