# Golden Output Status Index

Auto-derived from each fixture's paired `.golden.json`. Regenerate this table
whenever golden files are updated, rather than hand-editing it out of sync.

Status legend: `pending` = no data yet. `captured` = locked, authoritative,
verbatim from Compiler Core. `blocked` = data may be present but
deliberately held out of golden-lock, see `blocked_reason` in that
fixture's `.golden.json`.

| Group | Fixture | Status |
|---|---|---|
| `circular_references/` | `circular_reference_direct_two_instance.gddl` | **captured** |
| `circular_references/` | `circular_reference_longer_chain.gddl` | **captured** |
| `composition_no_inheritance/` | `composition_multi_level.gddl` | **captured** |
| `composition_no_inheritance/` | `composition_nested_u16_fields.gddl` | **captured** |
| `composition_no_inheritance/` | `composition_same_type_reused_multiple_fields.gddl` | **captured** |
| `composition_no_inheritance/` | `composition_with_delete_partial_then_completed.gddl` | **captured** |
| `cross_rule_interactions/` | `cri_coercion_multigen_crossfield.gddl` | **captured** |
| `cross_rule_interactions/` | `cri_delete_composition_crossfield.gddl` | **captured** |
| `cross_rule_interactions/` | `cri_indentation_depth_with_replace_modify.gddl` | **captured** |
| `crossfield_references/` | `crossfield_basic_reference.gddl` | **captured** |
| `crossfield_references/` | `crossfield_dot_syntax_disambiguation.gddl` | **captured** |
| `crossfield_references/` | `crossfield_forward_reference_error.gddl` | **captured** |
| `crossfield_references/` | `crossfield_nested_path_reference.gddl` | **captured** |
| `crossfield_references/` | `crossfield_self_reference_non_leading.gddl` | **captured** |
| `delete_templates/` | `delete_chain_partial_completion_at_each_generation.gddl` | **captured** |
| `delete_templates/` | `delete_descendant_completes_and_resolves.gddl` | **captured** |
| `delete_templates/` | `delete_descendant_incomplete_error.gddl` | **captured** |
| `delete_templates/` | `delete_multi_generation_chain.gddl` | **captured** |
| `delete_templates/` | `delete_own_uninitialized_read_error.gddl` | **captured** |
| `delete_templates/` | `delete_template_incomplete_ok.gddl` | **captured** |
| `domains/` | `domain_field_accepts_valid_member.gddl` | **captured** |
| `domains/` | `domain_field_literal_type_mismatch_error.gddl` | **captured** |
| `domains/` | `domain_field_nonexistent_member_error.gddl` | **captured** |
| `domains/` | `domain_field_wrong_domain_error.gddl` | **captured** |
| `domains/` | `domain_logical_id_collision_error.gddl` | **captured** |
| `domains/` | `domain_multiple_domains_side_by_side.gddl` | **captured** |
| `indentation_and_comments/` | `comments_nested_block_and_code_lookalike.gddl` | **captured** |
| `indentation_and_comments/` | `indentation_deep_nesting_valid.gddl` | **captured** |
| `indentation_and_comments/` | `indentation_mixed_tabs_spaces_error.gddl` | **captured** |
| `indentation_and_comments/` | `indentation_nested_scope_differs_from_parent_error.gddl` | **captured** |
| `indentation_and_comments/` | `indentation_spaces_only_valid.gddl` | **captured** |
| `indentation_and_comments/` | `indentation_tabs_only_valid.gddl` | **captured** |
| `initialization/` | `init_gap_persists_across_4gen_chain.gddl` | **captured** |
| `initialization/` | `init_multiple_uninitialized_fields_all_reported.gddl` | **captured** |
| `initialization/` | `init_nested_uninitialized_dotted_path.gddl` | **captured** |
| `initialization/` | `init_uninitialized_only_caught_at_export.gddl` | **captured** |
| `nested_field_semantics/` | `nested_bare_scalar_field_error.gddl` | **captured** |
| `nested_field_semantics/` | `nested_level2_replace_sibling_level1_untouched.gddl` | **captured** |
| `nested_field_semantics/` | `nested_mixed_replace_and_modify_across_levels.gddl` | **captured** |
| `nested_field_semantics/` | `nested_modify_only_basic.gddl` | **captured** |
| `nested_field_semantics/` | `nested_modify_only_three_levels.gddl` | **captured** |
| `nested_field_semantics/` | `nested_modify_only_two_levels.gddl` | **captured** |
| `nested_field_semantics/` | `nested_replace_basic.gddl` | **captured** |
| `nested_field_semantics/` | `nested_replace_discards_prior_modify.gddl` | **captured** |
| `nested_field_semantics/` | `nested_scalar_vs_struct_fork.gddl` | **captured** |
| `numeric_coercion/` | `numeric_coercion_narrowing_rejected.gddl` | **captured** |
| `numeric_coercion/` | `numeric_coercion_through_sequential_chain.gddl` | **captured** |
| `numeric_coercion/` | `numeric_coercion_via_crossfield_reference.gddl` | **captured** |
| `numeric_coercion/` | `numeric_coercion_whole_float_accepted.gddl` | **captured** |
| `numeric_coercion/` | `numeric_coercion_widening_basic.gddl` | **captured** |
| `numeric_range/` | `numeric_range_computed_expression_overflow.gddl` | **captured** |
| `numeric_range/` | `numeric_range_float_boundary_overflow.gddl` | **captured** |
| `numeric_range/` | `numeric_range_signed_boundary.gddl` | **captured** |
| `numeric_range/` | `numeric_range_unsigned_boundary.gddl` | **captured** |
| `op_statements/` | `op_statement_assign_equivalence.gddl` | **captured** |
| `op_statements/` | `op_statement_leading_operator_error.gddl` | **captured** |
| `op_statements/` | `op_statement_missing_leading_field_error.gddl` | **captured** |
| `op_statements/` | `op_statement_operator_precedence.gddl` | **captured** |
| `op_statements/` | `op_statement_parens_basic.gddl` | **captured** |
| `op_statements/` | `op_statement_parens_override_left_to_right.gddl` | **captured** |
| `op_statements/` | `op_statement_three_operator_chain.gddl` | **captured** |
| `sequential_execution/` | `sequential_chained_ops_order_matters.gddl` | **captured** |
| `sequential_execution/` | `sequential_crossfield_reference_sees_current_value.gddl` | **captured** |
| `sequential_execution/` | `sequential_longer_chain_order_dependent.gddl` | **captured** |
| `string_fields/` | `string_empty_accepted.gddl` | **captured** |
| `string_fields/` | `string_escape_invalid_sequence.gddl` | **captured** |
| `string_fields/` | `string_escape_lone_trailing_backslash.gddl` | **captured** |
| `string_fields/` | `string_escaped_quote.gddl` | **captured** |
| `string_fields/` | `string_escaped_trailing_backslash.gddl` | **captured** |
| `string_fields/` | `string_escaping_through_composition.gddl` | **captured** |
| `string_fields/` | `string_length_boundary.gddl` | **captured** |
| `string_fields/` | `string_utf8_byte_vs_char_length.gddl` | **captured** |

**Totals: 72 fixtures — 72 captured, 0 pending, 0 blocked.**

## Corrected after a new lead session's direct-check request

A new lead session (replacing the prior one) flagged a stale baseline from an earlier
check: 60 fixtures, 56 captured, 4 `numeric_range/` fixtures stub-pending, and 2
fixtures (`circular_reference_direct_two_instance`, `domain_logical_id_collision_error`)
with no `.golden.json` at all -- also noting this file's own totals line never
accounted for those 2 missing fixtures.

Direct re-check against actual files (not against that summary) found the numeric part
of that baseline already stale in this corpus's favor: all 4 `numeric_range/`
fixtures and both previously-missing fixtures had already been captured earlier in
this same session, after whatever check the lead's information was based on -- see
the "Both new fixtures captured" section below for that capture's own record.

**But the same direct check surfaced a genuinely new, more recent discrepancy nobody
had reported yet**: a 63rd `.gddl` fixture,
`circular_references/circular_reference_longer_chain.gddl`, existed complete and
well-formed, but with no paired `.golden.json`, no entry anywhere in this file,
`INDEX.md`, or its group's `MANIFEST.md`, and was never synced to the persisted
output directory. This was genuine unfinished work-in-progress from earlier in this
same conversation thread -- a fixture-building task interrupted mid-completion, not
something any prior summary could have known about. Closed out properly: `pending`
`.golden.json` placeholder added, all docs updated to match, synced to outputs. This
file's totals now correctly read 63 total, 62 captured, 1 pending -- that one fixture,
genuinely awaiting a Compiler Core run, not blocked on anything else.

## Both new fixtures captured -- clean 62/62 (historical -- corpus has since grown to 63/62/1, see above)

`domain_logical_id_collision_error` and
`circular_reference_direct_two_instance` both confirmed exact matches to
their predictions -- phase 4/check `id_collision` and phase 4/check
`circular_dependency` respectively, hash and cycle path exactly as
predicted. Both captured. This closes out both open questions from a few
rounds back -- circular reference detection and logical ID collision
detection are now fully implemented, tested, and verified end to end.

New schema detail learned from this batch, folded into
`GOLDEN_FORMAT.md`: `duplicate_errors` is broader than its original
"duplicate name" framing -- it holds any phase-4 structural error,
including `id_collision` (no per-instance entry at all) and
`circular_dependency` (appears BOTH in `duplicate_errors` AND per
participating instance in `instances`, all citing the identical cycle
path).

## New fixture added: composition + u16, dual-purpose (Z80 export gap)

`composition_no_inheritance/composition_nested_u16_fields.gddl` -- authored to close
a real Z80 export testing gap (no composition or `u16` field exercised end-to-end on
real Z80 toolchains before this). Resolved explicitly as a two-channel situation:
golden-locked here on its own legitimate language-level merits (composition + `u16`
at multiple nesting levels, values chosen to genuinely exercise the full 16-bit
width rather than coincidentally fit in 8 bits), and the SAME source separately
handed to Compiler Core for their own `export_z80_test/` directory and real-toolchain
validation -- an export-correctness concern this corpus's schema correctly has no
concept of and shouldn't grow one for. No string field (Z80 string storage semantics
remain a separate, unsettled design question). Corpus now at 64 total, 62 captured,
2 pending (this fixture and `circular_reference_longer_chain`, both awaiting real
Compiler Core runs, neither blocked on anything else).

## New group added: string_fields (language-level string-semantics gap)

Four fixtures: length boundary (N-1 accepted / N rejected), UTF-8 byte-vs-character
counting (both directions, using real 2-byte `é` characters), empty string (confirmed
accepted per the spec's own byte-counting logic, including the `string 1` extreme
case), and a fixture golden-locking a confirmed, real implementation finding around
escaped quotes (`\"` correctly tokenized as non-terminating, but `_strip_quotes()`
never un-escapes it, so backslashes survive into the resolved value). That last
fixture predicts CURRENT behavior deliberately, not intended/corrected behavior, and
is flagged explicitly as an undecided design gap requiring a decision elsewhere --
not resolved or fixed in this corpus. Independently re-verified the escape-bug
fixture's exact predicted character sequence by direct computation, rather than
reusing the reporting session's own manual transcription, which was off by one
character. Corpus now at 68 total, 62 captured, 6 pending (2 from the prior round,
4 new here), none blocked.

## Two of six pending fixtures captured

`circular_reference_longer_chain` and `composition_nested_u16_fields` captured --
both confirmed exact matches to predictions (cycle path `A -> B -> C -> A` for all
three participating instances, same `duplicate_errors` + per-instance dual-reporting
pattern as the 2-instance case; `Hero.stats/equipment/level` matching precisely).
The other 4 requested (`string_fields/` group) were not part of this delivery --
still `pending`, untouched, awaiting their own data. Corpus now at 68 total,
64 captured, 4 pending, none blocked.

## Clean 68/68 -- string_fields group fully captured

All 4 `string_fields/` fixtures captured, all confirmed exact matches to their
predictions: length boundary (9 bytes accepted / 10 rejected for `string 10`),
byte-vs-char distinction (`ééé` correctly rejected at 6 bytes despite being only 3
characters), both empty-string edge cases (ordinary field and the `string 1` extreme),
and the escaped-quote fixture at the corrected 20-character sequence with backslashes
intact, exactly as re-verified. New confirmed schema detail, folded into
`GOLDEN_FORMAT.md`: string length violations report `check: "string_length"` at
phase 6.

**Corpus fully golden-locked: 68/68 captured, 0 pending, 0 blocked.** The
escape-mechanism design question (proper `\"` escaping vs. no escape mechanism at
all) remains explicitly open and unresolved -- flagged to the lead session, not
decided here, per instruction.

## New fixture added: string_escaping_through_composition

Verifies §5's now-resolved escape processing (`\"`, and `\\` in its parity-rule
trailing-backslash form) specifically through a nested composed struct field
(`equipment.weapon.name`, two hops deep, modeled on `composition_multi_level.gddl`'s
structure). Built because this project already found the identical escaping bug
duplicated independently in two separate files -- worth the same standard here
rather than assuming the flat-field behavior generalizes. Predictions independently
computed via a small script, not hand-transcribed, given this project's history with
exactly this kind of transcription error.

**Flagged, not resolved:** the spec uploaded alongside this fixture request fully
documents §5's escape rule as resolved/defined behavior. The EXISTING
`string_escaped_quote_current_behavior.gddl` fixture, however, is golden-locked with
backslashes SURVIVING unescaped -- captured as confirmed current (buggy) behavior at
the time, with the design question explicitly left open. Whether that captured data
is now stale (the fix landed since) or still accurate (spec text updated ahead of the
implementation) is unconfirmed. Not touching that fixture's golden data until this is
explicitly checked. Corpus now at 69 total, 68 captured, 1 pending (the new fixture),
0 blocked.

## Resolved: escape-fix cross-copy drift, larger than one stale fixture

The flagged staleness question resolved to the first hypothesis: the fix had landed,
and `string_escaped_quote_current_behavior.gddl`'s captured data was genuinely stale
(old: 20 chars, backslashes intact; real current behavior: 18 chars, real quote
characters -- verified character-by-character). But the real scope was bigger: this
corpus had never received the escape-fix delivery at all. Compiler Core deleted the
old fixture outright and replaced it with four new ones, each isolating a distinct
aspect of the now-resolved §5 escape rule: `string_escaped_quote.gddl` (basic `\"`),
`string_escaped_trailing_backslash.gddl` (the harder trailing-`\\` parity case that
was actually found broken during implementation), `string_escape_invalid_sequence.gddl`
(`\n` and similar rejected, not passed through), and
`string_escape_lone_trailing_backslash.gddl` (an unpaired trailing `\` is a phase-3
parse error via the parity rule, never reaching phase-6 escape validation at all).

Same root cause as the earlier missing-locks incident this session: a fix landed in
one copy with nothing forwarded here to ride along with it. Old fixture and lock
deleted, not recaptured under the old name. All four new fixtures pulled in with
their already-captured, independently-verified golden data (all `status: "captured"`
on arrival). `string_escaping_through_composition.gddl` needed no changes -- built
after the rule was already resolved, unaffected by the drift.

**Corpus now at 72 total, 71 captured, 1 pending** (`string_escaping_through_composition.gddl`,
awaiting its own real Compiler Core run), 0 blocked.

## Clean 72/72 -- string_escaping_through_composition captured, corpus fully golden-locked

Both predictions confirmed exactly, character-by-character:
`QuoteCase.equipment.weapon.name` (22 chars, real quote characters, two hops deep)
and `BackslashCase.equipment.label` (9 chars, single trailing backslash, one hop
deep). Escape processing fires correctly through composition at both depths tested,
answering the original question this whole detour started from with real captured
output rather than "the code reads like it should."

**Corpus fully golden-locked: 72/72 captured, 0 pending, 0 blocked.**

## New: mandatory lock-completeness check, wired into packaging

Received from Compiler Core, built for exactly this handoff: `tools/check_lock_completeness.py`
verifies every `.gddl` has a matching `.golden.json` sitting next to it -- EXISTENCE
only, nothing about content. A `pending`/`blocked` entry counts as present and
correctly does not trip it. Re-verified independently (not just trusting the claim):
confirmed a clean pass at 72/72, and confirmed a genuinely missing lock correctly
fails with the exact filename and a non-zero exit.

Wrapped in `tools/package_corpus.py`, which runs the check FIRST and refuses to
proceed (non-zero exit, printed missing files) if it fails -- this is now the
mandatory first step of packaging, run before any sync-to-outputs or zip, not a
second script someone has to remember to invoke separately.

**Explicit scope, so this doesn't get treated as covering more than it does:**
- Does NOT catch staleness (a lock existing but not reflecting its fixture's current
  source) -- a real, distinct, still-unsolved property this session found and named
  more than once.
- Does NOT catch cross-copy consistency (this corpus and Compiler Core's copy
  agreeing) -- no single-sandbox script can check that. This session found two real
  instances of that drift so far, both only caught by someone actually opening files
  and comparing, not by any automated check. Still a manual-verification
  responsibility, not something this tool changes.
- A broader check (orphaned files, `capture_status` tallies actually matching this
  file's own stated totals -- which would have caught the `GOLDEN_STATUS.md` staleness
  found earlier this thread) was offered as a reasonable next layer, deliberately not
  built yet -- landing this narrower piece first and confirming it actually gets used,
  rather than expanding scope before the first piece has proven itself.
