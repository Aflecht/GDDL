# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated 6502/64tass string-field output by assembling
with the real `64tass` binary and executing via py65.

Run from export_6502_test/ after:
  64tass --nostart -o test_6502_string_field_harness_tass.bin \
         -l test_6502_string_field_harness_tass.lst \
         test_6502_string_field_harness_tass.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_64tass, run_to_brk, load_binary_at


def main():
    symbols = load_symbols_64tass("test_6502_string_field_harness_tass.lst")
    m = MPU()
    load_binary_at(m, "test_6502_string_field_harness_tass.bin", 0xC000)
    m.pc = symbols["Main"]
    run_to_brk(m)

    result_bytes = bytes(m.memory[symbols["ResultAddr"] + i] for i in range(12))
    expected = "Grübnik".encode("utf-8") + b"\x00" * 4

    print(f"  got:      {result_bytes.hex(' ')}")
    print(f"  expected: {expected.hex(' ')}")
    if result_bytes != expected:
        raise SystemExit("String field (6502/64tass) byte check FAILED")

    decoded = result_bytes.split(b"\x00")[0].decode("utf-8")
    print(f"  decoded (up to first NUL): {decoded!r}  (want 'Grübnik')")
    if decoded != "Grübnik":
        raise SystemExit("String field (6502/64tass) decode check FAILED")

    print("All 6502/64tass string-field checks passed.")


if __name__ == "__main__":
    main()
