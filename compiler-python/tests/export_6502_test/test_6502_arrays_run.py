# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated 6502/ACME array output by actually assembling with
the real `acme` binary and reading the resulting bytes back directly from
memory -- pure data check, no code execution needed (array fields are just
bytes, laid out row-major/contiguous, per the arrays design).

Run from export_6502_test/ after:
  acme -o test_6502_arrays_harness.bin --format plain \
       --symbollist test_6502_arrays_harness.sym test_6502_arrays_harness.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_acme, load_binary_at


def main():
    symbols = load_symbols_acme("test_6502_arrays_harness.sym")
    m = MPU()
    load_binary_at(m, "test_6502_arrays_harness.bin", 0xC000)

    base = symbols["Enemy_Goblin"]
    raw = bytes(m.memory[base:base + 24])

    damage_min_max = list(raw[0:2])
    grid = list(raw[2:8])
    name0 = raw[8:16].split(b"\x00", 1)[0].decode("ascii")
    name1 = raw[16:24].split(b"\x00", 1)[0].decode("ascii")

    checks = [
        ("damage_min_max", damage_min_max, [10, 30]),
        ("grid (row-major)", grid, [1, 2, 3, 4, 5, 6]),
        ("names[0]", name0, "Al"),
        ("names[1]", name1, "Bo"),
    ]

    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got}, want {want}  [{status}]")

    if failed:
        raise SystemExit("6502/ACME arrays check FAILED")
    print("All 6502/ACME arrays checks passed.")


if __name__ == "__main__":
    main()
