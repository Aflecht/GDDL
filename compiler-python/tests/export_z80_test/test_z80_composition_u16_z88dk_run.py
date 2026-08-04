"""
z88dk-z80asm counterpart of test_z80_composition_u16_run.py. Uses the
.map file (via -m), NOT the .sym file (via -s) -- confirmed directly
that .sym reports pre-org section-relative offsets while .map reports
the actual final absolute addresses embedded in the assembled binary.

Run from export_z80_test/ after:
  z88dk-z80asm -b -m -otest_z80_composition_u16_harness_z88dk_out \
               test_z80_composition_u16_harness_z88dk.asm
"""

import z80
from z80_test_helper import load_symbols_z88dk_map, run_to_pc


def main():
    with open("test_z80_composition_u16_harness_z88dk_out", "rb") as f:
        code = f.read()
    symbols = load_symbols_z88dk_map(
        "test_z80_composition_u16_harness_z88dk_out.map")

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)
    m.pc = symbols["Main"]

    run_to_pc(m, symbols["AfterReads"])

    def u16(addr):
        return m.memory[addr] | (m.memory[addr + 1] << 8)

    checks = [
        ("hp", u16(symbols["Result_hp"]), 60000),
        ("mp", u16(symbols["Result_mp"]), 12000),
        ("weapon_power", u16(symbols["Result_weapon_power"]), 500),
        ("level", u16(symbols["Result_level"]), 42),
    ]
    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got}, want {want}  [{status}]")

    if failed:
        raise SystemExit("Composition/u16 (z88dk-z80asm) check FAILED")
    print("All Z80/z88dk-z80asm composition+u16 checks passed.")


if __name__ == "__main__":
    main()
