# z88dk C mode (§16.1-16.3) — validation assets

Real-toolchain validated, same discipline as every other target: compiled
with the real `zsdcc` and executed on a real Z80 emulator, not reviewed
visually.

## Toolchain

`zsdcc` is NOT stock SDCC. Build from `https://github.com/z88dk/sdcc.git`,
branch **`zsdcc`** (SourceForge, the upstream home, is egress-blocked;
`master` on that mirror is unmodified SDCC). The built binary identifies
itself as `ZSDCC IS A MODIFICATION OF SDCC FOR Z88DK`. See HANDOFF.md for
the full dependency list and the `MAKEINFO=true` workaround.

**`zcc` must be invoked with `-compiler=sdcc`.** `sccz80` is `zcc`'s
silent default and is explicitly unsupported (§16.1) — its inline
constant-multiply list is enumerated and hardcoded, so any struct size
outside it falls through to a ~500+ T-state runtime multiply.

## What was validated

- `gddl_z80_export.{h,c}` compile under `sdcc -mz80` (C89).
- `consumer_a.c` + `consumer_b.c` + the generated `.c` link as **three
  separate translation units** with no duplicate symbols.
- Executed on the `z80` emulator: `Creature_Find(Archer)->hp == 8` and
  `->attack == ActionAttack_ranged_weapon`, for both
  `--z80-pointer-table=on` and `=off`.
- **Negative control** (`single/` in the scratch tree, not committed):
  collapsing the header/.c split into one header included by two TUs
  fails with `Multiple definition of _Creature_Instances /
  _Creature_Registry / _Creature_Find` — confirming §16.2.1's split is
  load-bearing rather than stylistic.

Note SDCC compiles only one source file per invocation (`warning 120`);
compile each TU to `.rel` with `-c`, then link.

## Scripts

- `verify_shift_add.py` — checks the `--z80-pointer-table=off` shift-add
  index computation for every sizeof 1..64 against the emulator. The one
  Z80 fixture has sizeof 2 (a power of two), so the `add hl,de`
  accumulation path is otherwise unexercised.
- `crossover_sweep.py` — re-runs §16.2's crossover table against real
  zsdcc instead of the stock-SDCC stand-in. **Result differs from the
  spec: see HANDOFF/report.**
- `measure_ptr_load.py` — T-state comparison of `{Type}_Find` pointer-load
  sequences under the fixed-HL-return constraint.

All three use a trailing-NOP trick: the emulator's `run()` stops only
once the in-flight instruction completes, so a naive tick search
undercounts by (last instruction's T − 1).
