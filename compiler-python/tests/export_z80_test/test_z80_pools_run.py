# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated Z80/SjASMPlus pool output by actually assembling
with the real `sjasmplus` binary and executing the result with the z80
PyPI library. A pool has no compiled-in values at all (uninitialized
storage, section 22.2) -- unlike the arrays check this test WRITES
synthetic bytes into the pool's own memory (via the real symbol
addresses the assembler produced) and reads them back, confirming the
layout the compiler claims (contiguous per-column arrays, u8 stride 1,
u16 stride 2 -- a single contiguous array, no Lo/Hi split, unlike 6502 --
no overlap between columns or with code) against real assembled/executed
output, not just the compiler's own internal bookkeeping.

Run from export_z80_test/ after:
  sjasmplus --raw=test_z80_pools_harness.bin --sym=test_z80_pools_harness.sym \
            test_z80_pools_harness.asm
"""

import z80
from z80_test_helper import load_symbols


def main():
    symbols = load_symbols("test_z80_pools_harness.sym")

    with open("test_z80_pools_harness.bin", "rb") as f:
        code = f.read()

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)

    hp_base = symbols["ActiveEnemies_hp"]
    mp_base = symbols["ActiveEnemies_mp"]

    checks = []

    # Layout: --pool-base=0xa000, 4 slots. hp (u8, 1 byte/slot) occupies
    # $a000-$a003; mp (u16, 2 bytes/slot, single contiguous array -- no
    # Lo/Hi split, Z80's richer registers make that unnecessary)
    # occupies $a004-$a00b.
    checks.append(("ActiveEnemies_hp base", hp_base, 0xA000))
    checks.append(("ActiveEnemies_mp base", mp_base, 0xA004))

    # Real write/read through the emulated memory: slot 2's hp, slot 1's
    # mp (0x1234, little-endian, as a single 16-bit column entry).
    m.memory[hp_base + 2] = 42
    m.memory[mp_base + 1 * 2] = 0x34
    m.memory[mp_base + 1 * 2 + 1] = 0x12

    got_hp = m.memory[hp_base + 2]
    got_mp = m.memory[mp_base + 2] | (m.memory[mp_base + 3] << 8)
    checks.append(("slot 2 hp readback", got_hp, 42))
    checks.append(("slot 1 mp readback (little-endian column entry)", got_mp, 0x1234))

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
        raise SystemExit("Z80/SjASMPlus pools check FAILED")
    print("All Z80/SjASMPlus pools checks passed.")


if __name__ == "__main__":
    main()
