# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
z88dk-z80asm counterpart of test_z80_arrays_run.py. Pure data check, same
reasoning.

Run from export_z80_test/ after:
  z88dk-z80asm -b -m -otest_z80_arrays_harness_z88dk_out test_z80_arrays_harness_z88dk.asm
"""

from z80_test_helper import load_symbols_z88dk_map

ORG = 0x8000


def main():
    symbols = load_symbols_z88dk_map("test_z80_arrays_harness_z88dk_out.map")
    base = symbols["Enemy_Goblin"]
    offset = base - ORG

    with open("test_z80_arrays_harness_z88dk_out", "rb") as f:
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
        raise SystemExit("Z80/z88dk-z80asm arrays check FAILED")
    print("All Z80/z88dk-z80asm arrays checks passed.")


if __name__ == "__main__":
    main()
