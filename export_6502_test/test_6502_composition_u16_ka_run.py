"""
Validates the generated 6502/KickAssembler output for composition + u16.

Run from export_6502_test/ after:
  java -jar /path/to/KickAss.jar test_6502_composition_u16_harness_ka.asm \
       -o test_6502_composition_u16_harness_ka.prg
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import (
    load_symbols_kickassembler, run_to_brk, load_prg_kickassembler)


def main():
    symbols = load_symbols_kickassembler("test_6502_composition_u16_harness_ka.sym")
    m = MPU()
    load_prg_kickassembler(m, "test_6502_composition_u16_harness_ka.prg",
                           expected_org=0xC000)
    m.pc = symbols["Main"]
    run_to_brk(m)

    def u16_at(sym):
        addr = symbols[sym]
        return m.memory[addr] | (m.memory[addr + 1] << 8)

    checks = [
        ("hp", u16_at("ResultHp"), 60000),
        ("mp", u16_at("ResultMp"), 12000),
        ("weapon_power", u16_at("ResultWp"), 500),
        ("level", u16_at("ResultLevel"), 42),
    ]

    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got}, want {want}  [{status}]")

    if failed:
        raise SystemExit("6502/KickAssembler composition+u16 check FAILED")
    print("All 6502/KickAssembler composition+u16 checks passed.")


if __name__ == "__main__":
    main()
