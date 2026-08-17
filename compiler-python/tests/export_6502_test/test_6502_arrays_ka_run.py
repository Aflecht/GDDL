# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
KickAssembler counterpart of test_6502_arrays_run.py. Pure data check,
same reasoning.

Run from export_6502_test/ after:
  java -jar KickAss.jar test_6502_arrays_harness_ka.asm -o test_6502_arrays_harness_ka.prg
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_kickassembler, load_prg_kickassembler


def main():
    symbols = load_symbols_kickassembler("test_6502_arrays_harness_ka.sym")
    m = MPU()
    load_prg_kickassembler(m, "test_6502_arrays_harness_ka.prg", expected_org=0xC000)

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
        raise SystemExit("6502/KickAssembler arrays check FAILED")
    print("All 6502/KickAssembler arrays checks passed.")


if __name__ == "__main__":
    main()
