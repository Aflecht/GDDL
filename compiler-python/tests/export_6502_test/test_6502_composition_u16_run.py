"""
Validates the generated 6502/ACME output for a COMPOSED type with u16
fields -- closes a gap this project's own audit found: no 6502 fixture
had ever exercised composition combined with a genuine scalar u16
field (only u16-as-identifier-domain-width existed). Same standard as
every other target: real assemble, real execute, not "should work".

Run from export_6502_test/ after:
  acme -o test_6502_composition_u16_harness.bin --format plain \
       --symbollist test_6502_composition_u16_harness.sym \
       test_6502_composition_u16_harness.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_acme, run_to_brk, load_binary_at


def main():
    symbols = load_symbols_acme("test_6502_composition_u16_harness.sym")
    m = MPU()
    load_binary_at(m, "test_6502_composition_u16_harness.bin", 0xC000)
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
        raise SystemExit("6502/ACME composition+u16 check FAILED")
    print("All 6502/ACME composition+u16 checks passed.")


if __name__ == "__main__":
    main()
