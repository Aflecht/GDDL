# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated 6502/KickAssembler string-field output by
assembling with the real KickAssembler jar and executing via py65.

Run from export_6502_test/ after:
  java -jar /path/to/KickAss.jar test_6502_string_field_harness_ka.asm \
       -o test_6502_string_field_harness_ka.prg
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import (
    load_symbols_kickassembler, run_to_brk, load_prg_kickassembler)


def main():
    symbols = load_symbols_kickassembler("test_6502_string_field_harness_ka.sym")
    m = MPU()
    load_prg_kickassembler(m, "test_6502_string_field_harness_ka.prg",
                           expected_org=0xC000)
    m.pc = symbols["Main"]
    run_to_brk(m)

    result_bytes = bytes(m.memory[symbols["ResultAddr"] + i] for i in range(12))
    expected = "Grübnik".encode("utf-8") + b"\x00" * 4

    print(f"  got:      {result_bytes.hex(' ')}")
    print(f"  expected: {expected.hex(' ')}")
    if result_bytes != expected:
        raise SystemExit("String field (6502/KickAssembler) byte check FAILED")

    decoded = result_bytes.split(b"\x00")[0].decode("utf-8")
    print(f"  decoded: {decoded!r}  (want 'Grübnik')")
    if decoded != "Grübnik":
        raise SystemExit("String field (6502/KickAssembler) decode check FAILED")

    print("All 6502/KickAssembler string-field checks passed.")


if __name__ == "__main__":
    main()
