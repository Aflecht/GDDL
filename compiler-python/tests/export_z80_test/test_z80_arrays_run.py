# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated Z80/SjASMPlus array output by actually assembling
with the real `sjasmplus` binary and reading the resulting bytes back
directly from memory -- pure data check, no code execution needed.

Run from export_z80_test/ after:
  sjasmplus --raw=test_z80_arrays_harness.bin --sym=test_z80_arrays_harness.sym \
            test_z80_arrays_harness.asm
"""

from z80_test_helper import load_symbols

ORG = 0x8000


def main():
    symbols = load_symbols("test_z80_arrays_harness.sym")
    base = symbols["Enemy_Goblin"]
    offset = base - ORG

    with open("test_z80_arrays_harness.bin", "rb") as f:
        data = f.read()
    raw = data[offset:offset + 24]

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
        raise SystemExit("Z80/SjASMPlus arrays check FAILED")
    print("All Z80/SjASMPlus arrays checks passed.")


if __name__ == "__main__":
    main()
