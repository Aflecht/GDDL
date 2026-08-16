# flags / bN Bit Literals -- Fixture Manifest

Rule group: the `flags` construct and `bN` bit literals, designed and implemented
across stages 1-4 (see `compiler-python/HANDOFF.md`'s "flags/bN work" entries and
`GDDL_Session_Handover.md` sections 4/6 for the full design history and the
`Entity.gddl` reference example these fixtures draw from).

Status: all seven fixtures captured against the real, current implementation --
`capture_status: "captured"` throughout, not predictions. Single-session
design-and-implementation, unlike this corpus's original two-role (Test
Corpus / Compiler Core) process -- output was verified against real compiler
runs before being locked, not hand-derived from the `.gddl` source's own
comments.

| File | Isolates |
|---|---|
| `flags_auto_assignment_valid.gddl` | Positive baseline: every real member auto-assigned (no explicit `bN` at all), confirming sequential bit assignment starting at 0, and that a `= 0` sentinel consumes no bit position. |
| `flags_explicit_bit_mixed_with_auto.gddl` | **Depth pass.** Explicit `bN` and auto-assigned members mixed, with the explicit claim declared AFTER some of the auto members it must still cause them to skip -- proves auto-assignment accounts for every explicit claim domain-wide, not just ones already seen (the property that makes explicit-vs-auto collisions structurally impossible). Also exercises real combining: an assign-time `\|` and a later op-statement `& ~` clearing one inherited bit -- the "copy a base, then toggle one flag" scenario stage 3 was specifically asked to confirm. |
| `flags_duplicate_bit_claim_error.gddl` | Negative path: two members explicitly claim the same bit -- the one collision that CAN actually occur under the two-pass algorithm (explicit-vs-explicit). Domain-only fixture, no instances needed, same convention as `corpus/domains/domain_logical_id_collision_error.gddl`. |
| `flags_bit_exceeds_width_error.gddl` | Negative path, distinct failure shape from width-overflow below: a single explicit `bN` naming a position that doesn't exist at the domain's declared width (`u8`, `b8` is one past the end). |
| `flags_width_overflow_error.gddl` | Negative path: the domain-wide capacity check -- more real bit-flag members than the declared width can address. Different formula from identifier's own `indexed_width_overflow` (`bits` addressable positions for a bitmask, not `2**bits` distinct index values), same shape, deliberately not confused with it. |
| `flags_arithmetic_rejected_error.gddl` | Negative path: arithmetic operators are a compile-time error on a flags-typed field, no exceptions. Isolates the op-statement form. |
| `flags_bitwise_rejected_on_non_flags_error.gddl` | Negative path, the other direction: bitwise operators are a compile-time error on any field that ISN'T flags-typed -- there is no other bitmask mechanism in the language. Isolates the op-statement form. |

## Coverage check against the stage 5 task list

- [x] Valid auto-assignment.
- [x] Explicit `bN` mixed with auto-assignment (plus the ordering-independence
      depth pass beyond what was strictly asked for).
- [x] Duplicate-bit-claim error.
- [x] The width-overflow error (plus the bit-exceeds-width bonus negative path --
      a distinct failure shape found during stage 3's own implementation, not
      reducible to width-overflow).
- [x] Arithmetic-rejected-on-flags.
- [x] Bitwise-rejected-elsewhere.
- [x] A real combined value read back from real compiled/run output -- NOT in
      this folder (corpus fixtures only exercise phases 1-8, never export).
      See `export_cpp_test/export_test_flags.gddl` (a variant of
      `flags_explicit_bit_mixed_with_auto.gddl`, real MSVC-compiled and
      executed, wired into `run_all_cpp_tests.py`).

## Notes

Every fixture's `check` name in its `.golden.json` was added directly to
`resolve.py`/`registry.py` as part of stage 3's own implementation
(`flags_bit_collision`, `flags_bit_exceeds_width`, `flags_width_overflow`,
`flags_arithmetic_rejected`, `flags_bitwise_rejected`) -- confirmed present on
the real `CompileError` objects (not just embedded in message text) before
these fixtures were locked, closing a real gap found while preparing this
batch: the arithmetic/bitwise-rejection errors originally had no `check` name
at all (`None`), unlike every other error in this codebase.

All values in each fixture's "Expected" comment were computed by hand first,
then confirmed byte-for-byte against `export_golden.py`'s real output before
the `.golden.json` was written -- never the reverse.
