"""
Validates the generated 6502/ACME string-field output by assembling
with the real `acme` binary and executing via py65.

Run from export_6502_test/ after:
  acme -o test_6502_string_field_harness.bin --format plain \
       --symbollist test_6502_string_field_harness.sym \
       test_6502_string_field_harness.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_acme, run_to_brk, load_binary_at


def main():
    symbols = load_symbols_acme("test_6502_string_field_harness.sym")
    m = MPU()
    load_binary_at(m, "test_6502_string_field_harness.bin", 0xC000)
    m.pc = symbols["Main"]
    run_to_brk(m)

    result_base = symbols["ResultAddr"]
    result_bytes = bytes(m.memory[result_base + i] for i in range(12))
    expected = "Grübnik".encode("utf-8") + b"\x00" * 4

    print(f"  got:      {result_bytes.hex(' ')}")
    print(f"  expected: {expected.hex(' ')}")
    if result_bytes != expected:
        raise SystemExit("String field (6502/ACME) byte check FAILED")

    decoded = result_bytes.split(b"\x00")[0].decode("utf-8")
    print(f"  decoded (up to first NUL): {decoded!r}  (want 'Grübnik')")
    if decoded != "Grübnik":
        raise SystemExit("String field (6502/ACME) decode check FAILED")

    print("All 6502/ACME string-field checks passed.")


if __name__ == "__main__":
    main()
