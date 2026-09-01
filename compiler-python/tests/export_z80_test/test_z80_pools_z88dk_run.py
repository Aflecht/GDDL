# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
z88dk-z80asm counterpart of test_z80_pools_run.py. Same
write-then-read-back reasoning (a pool has no compiled-in values,
section 22.2).

The pool's `equ`-defined constants (ActiveEnemies_hp/ActiveEnemies_mp)
are parsed directly out of generated_z80_pools_z88dk.asm's own text,
NOT from the -m map-file output -- confirmed directly during this
project's own 6502/Z80 pool export work that z88dk-z80asm's map output
only ever lists real address labels, never equ-defined constants, so
load_symbols_z88dk_map would silently find nothing for either symbol
here.

Run from export_z80_test/ after:
  z88dk-z80asm -b -m -otest_z80_pools_harness_z88dk_out test_z80_pools_harness_z88dk.asm
"""

import re

_EQU_RE = re.compile(r"^(\S+)\s+equ\s+\$([0-9A-Fa-f]+)", re.MULTILINE)


def load_equ_constants(asm_path):
    with open(asm_path, encoding="utf-8") as f:
        text = f.read()
    return {name: int(hexval, 16) for name, hexval in _EQU_RE.findall(text)}


def main():
    symbols = load_equ_constants("generated_z80_pools_z88dk.asm")

    with open("test_z80_pools_harness_z88dk_out", "rb") as f:
        code = f.read()

    import z80
    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)

    hp_base = symbols["ActiveEnemies_hp"]
    mp_base = symbols["ActiveEnemies_mp"]

    checks = []
    checks.append(("ActiveEnemies_hp base", hp_base, 0xA000))
    checks.append(("ActiveEnemies_mp base", mp_base, 0xA004))

    m.memory[hp_base + 2] = 42
    m.memory[mp_base + 1 * 2] = 0x34
    m.memory[mp_base + 1 * 2 + 1] = 0x12

    got_hp = m.memory[hp_base + 2]
    got_mp = m.memory[mp_base + 2] | (m.memory[mp_base + 3] << 8)
    checks.append(("slot 2 hp readback", got_hp, 42))
    checks.append(("slot 1 mp readback (little-endian column entry)", got_mp, 0x1234))

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
        raise SystemExit("Z80/z88dk-z80asm pools check FAILED")
    print("All Z80/z88dk-z80asm pools checks passed.")


if __name__ == "__main__":
    main()
