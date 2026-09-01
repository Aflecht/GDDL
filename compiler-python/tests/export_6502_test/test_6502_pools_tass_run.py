# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
64tass counterpart of test_6502_pools_run.py. Same write-then-read-back
reasoning (a pool has no compiled-in values, section 22.2).

Run from export_6502_test/ after:
  64tass --nostart -o test_6502_pools_harness_tass.bin \
         -l test_6502_pools_harness_tass.lst test_6502_pools_harness_tass.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_64tass, load_binary_at


def main():
    symbols = load_symbols_64tass("test_6502_pools_harness_tass.lst")
    m = MPU()
    load_binary_at(m, "test_6502_pools_harness_tass.bin", 0xC000)

    hp_base = symbols["ActiveEnemies_hp"]
    mp_lo_base = symbols["ActiveEnemies_mp_Lo"]
    mp_hi_base = symbols["ActiveEnemies_mp_Hi"]

    checks = []
    checks.append(("ActiveEnemies_hp base", hp_base, 0xA000))
    checks.append(("ActiveEnemies_mp_Lo base", mp_lo_base, 0xA004))
    checks.append(("ActiveEnemies_mp_Hi base", mp_hi_base, 0xA008))

    m.memory[hp_base + 2] = 42
    m.memory[mp_lo_base + 1] = 0x34
    m.memory[mp_hi_base + 1] = 0x12

    got_hp = m.memory[hp_base + 2]
    got_mp = m.memory[mp_lo_base + 1] | (m.memory[mp_hi_base + 1] << 8)
    checks.append(("slot 2 hp readback", got_hp, 42))
    checks.append(("slot 1 mp readback (Lo/Hi recombined)", got_mp, 0x1234))

    m.memory[hp_base + 0] = 7
    checks.append(("slot 0 hp independent of slot 2", m.memory[hp_base + 0], 7))
    checks.append(("slot 2 hp still holds its own value", m.memory[hp_base + 2], 42))

    failed = False
    for name, got, want in checks:
        status = "OK" if got == want else "FAIL"
        if got != want:
            failed = True
        print(f"  {name}: got {got:#06x}, want {want:#06x}  [{status}]")

    if failed:
        raise SystemExit("6502/64tass pools check FAILED")
    print("All 6502/64tass pools checks passed.")


if __name__ == "__main__":
    main()
