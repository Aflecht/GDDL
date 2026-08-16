# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Verify the exporter's shift-add index computation (the
--z80-pointer-table=off path) for EVERY type size 1..64, against a real
Z80 emulator.

Motivation: the only Z80 export fixture in the repo has sizeof(Creature)
== 2, a power of two, so the interesting half of shift_add_multiply --
the `add hl,de` accumulation for non-power-of-two sizes like 21 -- is
completely unexercised by the existing corpus. A wrong decomposition
here would produce silently misaligned instance addresses rather than
any kind of visible failure.
"""
import sys
import os
# Script-relative -- this hardcoded an absolute /home/claude/work/staged
# path left over from a much earlier scratch-merge session, found
# broken during the repository restructuring (that path never existed
# in the final tree at all). Fixed the same way export_golden.py's own
# path resolution already works: locate gddl/ relative to this file's
# own location. This file sits at
# compiler-python/tests/export_z80_c_test/verify_shift_add.py -- three
# directories up reaches compiler-python/, then into gddl/. Verified by
# actually running this file from its real location after the fix, not
# just by counting dirname() calls -- the first attempt at this fix
# was ONE LEVEL SHORT (two dirname() calls, not three) and only running
# it surfaced that, exactly the kind of off-by-one this restructuring's
# own stated risk ("a manual pass will miss some") was warning about.
_COMPILER_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, _COMPILER_ROOT)

import z80
from gddl.export_z80 import shift_add_multiply, needs_index_copy

ORG = 0x8000

# minimal assembler for just the mnemonics this path emits
ENC = {
    "add hl, hl": [0x29],
    "add hl, de": [0x19],
    "ld d, h":    [0x54],
    "ld e, l":    [0x5D],
}


def build(n, index):
    """Emit the exact prologue the renderers emit, then the shift-add
    sequence. Entry: A = index. Exit: HL = index * n."""
    code = [0x6F, 0x26, 0x00]          # ld l,a ; ld h,0
    if needs_index_copy(n):
        code += ENC["ld d, h"] + ENC["ld e, l"]
    for mnem in shift_add_multiply(n):
        code += ENC[mnem]
    code += [0x00]                     # trailing NOP (tick-boundary fix)
    return code


def run(code, index):
    m = z80.Z80Machine()
    m.set_memory_block(ORG, bytes(code))
    m.pc = ORG
    m.a = index
    m.ticks_to_stop = 500
    m.run()
    return m.hl


bad = []
for n in range(1, 65):
    for index in (0, 1, 3, 7):
        got = run(build(n, index), index)
        want = index * n
        if got != want:
            bad.append((n, index, got, want))

print(f"sizes 1..64 x indices {{0,1,3,7}} = {64*4} cases")
if bad:
    print("FAILURES:")
    for n, i, got, want in bad[:20]:
        print(f"  sizeof={n} index={i}: got {got}, want {want}")
    raise SystemExit(1)
print("PASS: every size decomposes to a correct index*sizeof")

print("\nInstruction cost by size (the tradeoff §16.2 measures):")
for n in (2, 8, 16, 21, 32, 64):
    seq = shift_add_multiply(n)
    copy = 2 if needs_index_copy(n) else 0
    print(f"  sizeof={n:>2}: {len(seq)+copy:>2} instructions "
          f"({len(seq)} shift/add{', + index copy' if copy else ''})")
