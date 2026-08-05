# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Measure real T-states for candidate '{Type}_Find' pointer-load sequences.

Constraint under test (SPEC v4 §16.1.1): the index arrives in A and the
resolved instance pointer MUST be returned in HL. We measure only the
inner load -- HL already points at the 2-byte little-endian registry
entry -- since the index->address prologue (ld l,a / ld h,0 / add hl,hl /
ld de,Table / add hl,de) is identical across all candidates.

T-states are found by raising ticks_to_stop until PC reaches the end of
the sequence: the emulator stops on a tick boundary, so the smallest
ticks_to_stop that lands PC at END is the exact cycle cost.
"""
import z80

ORG = 0x8000
ENTRY_ADDR = 0x9000      # registry entry lives here
TARGET = 0x1234          # the pointer stored there (little-endian)

CANDIDATES = {
    # current, shipping in both Z80 asm renderers
    "A: ld a,(hl) / inc hl / ld h,(hl) / ld l,a": [0x7E, 0x23, 0x66, 0x6F],
    # proposed BC load, WITHOUT the move back to HL (result in BC)
    "B0: ld c,(hl) / inc hl / ld b,(hl)   [ends in BC]": [0x4E, 0x23, 0x46],
    # proposed BC load, WITH the move back to HL (honours §16.1.1)
    "B1: ld c,(hl) / inc hl / ld b,(hl) / ld h,b / ld l,c": [0x4E, 0x23, 0x46, 0x60, 0x69],
    # DE variant + exchange
    "C: ld e,(hl) / inc hl / ld d,(hl) / ex de,hl": [0x5E, 0x23, 0x56, 0xEB],
}


def measure(code):
    # Trailing NOP (4T): run() only stops once the in-flight instruction
    # completes, so measuring to the end of a NOP that follows the
    # sequence yields (total + 1). Without it the last instruction of the
    # sequence itself is undercounted by (its own T - 1).
    code = list(code) + [0x00]
    end = ORG + len(code)
    for ticks in range(1, 200):
        m = z80.Z80Machine()
        m.set_memory_block(ORG, bytes(code))
        m.set_memory_block(ENTRY_ADDR, bytes([TARGET & 0xFF, TARGET >> 8]))
        m.pc = ORG
        m.hl = ENTRY_ADDR
        m.ticks_to_stop = ticks
        m.run()
        if m.pc == end:
            return ticks - 1, m.hl, m.bc, m.de
    return None, None, None, None


print(f"{'sequence':<52} {'bytes':>5} {'T':>4}  result")
print("-" * 92)
for name, code in CANDIDATES.items():
    t, hl, bc, de = measure(code)
    # which register actually holds the resolved pointer
    holder = "HL" if hl == TARGET else ("BC" if bc == TARGET else ("DE" if de == TARGET else "??"))
    ok = "returns in HL" if hl == TARGET else f"returns in {holder} -- VIOLATES §16.1.1"
    print(f"{name:<52} {len(code):>5} {t:>4}  {ok}")
