"""
Validates the generated Z80/SjASMPlus output for a COMPOSED type with
u16 fields -- closes the gap flagged in HANDOFF.md ("KNOWN GAP: Z80
composition, string-field, and wide-domain (u16) testing has NOT been
done"). Same standard as every other target: real assemble, real
execute, not just "should work".

Run from export_z80_test/ after:
  sjasmplus --raw=test_z80_composition_u16_harness.bin \
            --sym=test_z80_composition_u16_harness.sym \
            test_z80_composition_u16_harness.asm
"""

import z80
from z80_test_helper import load_symbols, run_to_pc


def main():
    with open("test_z80_composition_u16_harness.bin", "rb") as f:
        code = f.read()
    symbols = load_symbols("test_z80_composition_u16_harness.sym")

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
        raise SystemExit("Composition/u16 (SjASMPlus) check FAILED")
    print("All Z80/SjASMPlus composition+u16 checks passed.")


if __name__ == "__main__":
    main()
