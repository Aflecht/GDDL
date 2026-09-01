# Pools -- Fixture Manifest

Rule group: the pools feature (`pool TypeName PoolName : N`, a fixed-size
reservation of N uninitialized `TypeName` instances, addressed by plain
index rather than by name), designed and implemented across
`compiler-python/HANDOFF.md`'s "Pools work" stages 1-3 (parser, registry
validation, export across all five targets) and documented in
`SPEC.md` section 22 and `docs/language-basics.md`.

Status: all seven fixtures captured against the real, current
implementation -- `capture_status: "captured"` throughout, not
predictions. Every value in each fixture's "Expected" comment was
computed by hand first, then confirmed byte-for-byte against
`export_golden.py`'s real output before the `.golden.json` was written --
never the reverse, same discipline as `corpus/flags/` and `corpus/arrays/`.

| File | Isolates |
|---|---|
| `pools_declaration_valid.gddl` | Positive baseline: two side-by-side pools of two different types, one type exercising plain scalar, array, string, and nested-struct fields together -- confirms pools parse and register cleanly across the full range of field kinds the language-level (phase 1-8) pipeline supports, and confirms section 22.2's "not identity-bearing" claim directly: `instances == {}`, since a pool contributes no named instance for phase 6/8 to walk. |
| `pools_no_body_error.gddl` | Negative path, parse error (phase 3): an indented body under a `pool` line is always rejected -- there is nothing to initialize, so this is never silently accepted or silently dropped. |
| `pools_unknown_type_error.gddl` | Negative path, phase 4, check `pool_unknown_type`: a pool's `TypeName` must name a real, existing `define`. A pool has no body at all to walk, so this needs its own dedicated registration-time check (unlike an ordinary instance's type_name, which might surface a mismatch indirectly elsewhere). |
| `pools_zero_count_error.gddl` | Negative path, phase 4, check `pool_zero_count`: a pool must reserve at least one slot. The one malformed-count case that survives parsing (negative/non-integer counts are already rejected at parse time) and must be caught at registration instead. |
| `pools_duplicate_name_error.gddl` | Negative path, phase 4, check `duplicate_name`: pools are their own namespace, first declaration wins, second is ignored -- same precedent duplicate instance names already established. Deliberately uses two DIFFERENT pool types under the same pool name, to confirm the collision is on the pool's own name, not on its target type. |
| `pools_malformed_count_error.gddl` | Negative path, parse error (phase 3): a count that isn't even a well-formed non-negative integer literal (`-1`) is rejected before registration ever sees the declaration -- distinct from the zero-count case above (a well-formed integer registration separately rejects as too small). |
| `pools_malformed_grammar_error.gddl` | Negative path, parse error (phase 3): the whole `pool TypeName PoolName : N` statement is a single fixed grammar shape, not deferred to registry the way array dimensions are -- a missing `:` token is rejected outright at parse time. |

## Coverage check against the stage 4 task list

- [x] Positive baseline across the field kinds the phase 1-8 pipeline
      supports (scalar, array, string, nested struct), and confirmation
      that a pool is genuinely not identity-bearing (empty `instances`).
- [x] Every parse-time (phase 3) rejection: indented body, malformed
      count, malformed statement grammar.
- [x] Every registration-time (phase 4) rejection: unknown type, zero
      count, duplicate pool name.
- [x] Real, compiled/run output read back from real toolchains -- NOT in
      this folder (corpus fixtures only exercise phases 1-8, never
      export). See `export_cpp_test/`, `export_6502_test/`,
      `export_z80_test/`, `export_68000_test/`, `export_binary_test/`
      for the real-toolchain export fixtures wired into each driver
      suite's own `CASES` list.

## Notes

Numeric range/coercion enforcement is deliberately out of scope here: a
pool declares no values at all (section 22.2 -- pool slots are always
uninitialized), so there is nothing for `_coerce_numeric`/
`_check_string_length` to ever run against inside a pool declaration
itself. This is a real, structural difference from arrays (whose element
values DO go through those checks) rather than an oversight.

Field-type restrictions on pool contents (6502/Z80 SoA rejecting
`string N`/array-typed leaf fields, both AoS on 6502/Z80 and z88dk-C mode
deferred entirely) are export-target concerns, not language-level
(phase 1-8) ones -- `pools_declaration_valid.gddl` deliberately uses a
`string N` field and an array field together, since the language-level
pipeline itself imposes no such restriction. Those export-target
restrictions are covered by each target's own real-toolchain fixtures
under `export_6502_test/`/`export_z80_test/`, not duplicated here.
