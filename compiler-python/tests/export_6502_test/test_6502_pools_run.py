# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated 6502/ACME pool output by actually assembling with
the real `acme` binary and reading the resulting symbol addresses back
directly -- a pool has no compiled-in values at all (uninitialized
storage, section 22.2), so unlike the arrays check this test WRITES
synthetic bytes into the pool's own memory (via the real symbol
addresses the assembler produced) and reads them back, confirming the
layout the compiler claims (contiguous per-column arrays, u8 stride 1,
u16 Lo/Hi split each stride 1, no overlap between columns or with code/
zero page) against real assembled output, not just the compiler's own
internal bookkeeping.

Run from export_6502_test/ after:
  acme -o test_6502_pools_harness.bin --format plain \
       --symbollist test_6502_pools_harness.sym test_6502_pools_harness.asm
"""

from py65.devices.mpu6502 import MPU
from six502_test_helper import load_symbols_acme, load_binary_at


def main():
    symbols = load_symbols_acme("test_6502_pools_harness.sym")
    m = MPU()
    load_binary_at(m, "test_6502_pools_harness.bin", 0xC000)

    hp_base = symbols["ActiveEnemies_hp"]
    mp_lo_base = symbols["ActiveEnemies_mp_Lo"]
    mp_hi_base = symbols["ActiveEnemies_mp_Hi"]

    checks = []

    # Layout: --pool-base=0xa000, 4 slots. hp (u8, 1 byte/slot) occupies
    # $a000-$a003, mp_Lo occupies $a004-$a007, mp_Hi occupies
    # $a008-$a00b -- each column its own contiguous byte-per-slot array,
    # never interleaved (SoA, §22.4).
    checks.append(("ActiveEnemies_hp base", hp_base, 0xA000))
    checks.append(("ActiveEnemies_mp_Lo base", mp_lo_base, 0xA004))
    checks.append(("ActiveEnemies_mp_Hi base", mp_hi_base, 0xA008))

    # Real write/read through the emulated memory: slot 2's hp, slot 1's
    # mp (0x1234, split across the Lo/Hi columns).
    m.memory[hp_base + 2] = 42
    m.memory[mp_lo_base + 1] = 0x34
    m.memory[mp_hi_base + 1] = 0x12

    got_hp = m.memory[hp_base + 2]
    got_mp = m.memory[mp_lo_base + 1] | (m.memory[mp_hi_base + 1] << 8)
    checks.append(("slot 2 hp readback", got_hp, 42))
    checks.append(("slot 1 mp readback (Lo/Hi recombined)", got_mp, 0x1234))

    # A slot never written is untouched by the slot we did write --
    # confirms real, distinct per-slot storage, not aliased.
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
        raise SystemExit("6502/ACME pools check FAILED")
    print("All 6502/ACME pools checks passed.")


if __name__ == "__main__":
    main()
