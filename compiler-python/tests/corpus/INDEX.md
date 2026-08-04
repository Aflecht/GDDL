# GDDL Test Corpus — First Pass (28 fixtures, 9 rule groups)

Handoff package for Compiler Core: run each `.gddl` fixture below against the Python
reference implementation and capture its actual output (resolved instance data, or the
specific error/blocked state) as the golden result for that fixture.

Every fixture file contains its own "Expected" comment block with a prediction of what
the golden output should look like. **These are predictions, not golden truth** — they
were derived from reading GDDL Specification v4, not from running any compiler. Where
real output diverges from a fixture's prediction, that's exactly the kind of finding
this corpus exists to surface. Per project process: bring mismatches back to this
session rather than resolving them unilaterally — some may be corpus bugs (a fixture
misread the spec), others may be reference-implementation bugs, and some may point to
spec ambiguity that needs another round with the lead session. All three are handled
differently, so the mismatch itself needs to come back before any fix is made.

Each group's own `MANIFEST.md` has the full per-fixture rationale, the specific spec
section each fixture targets, and notes on anything that was flagged and resolved along
the way. This file is just the routing index.

## Groups

| Group | Fixtures | Spec section(s) |
|---|---|---|
| `nested_field_semantics/` | 9 | §6.4, §6.5 |
| `delete_templates/` | 6 | §6.6, §7, §12 phase 8 |
| `initialization/` | 4 | §7, §12 phases 6 & 8 |
| `domains/` | 5 | §4.2 |
| `crossfield_references/` | 5 | §6.3, §6.7 |
| `op_statements/` | 7 | §6.3 |
| `sequential_execution/` | 3 | §6.2 |
| `indentation_and_comments/` | 6 | §3, §12 phases 2–3 |
| `composition_no_inheritance/` | 3 | §5.2–§5.3 |
| `numeric_coercion/` | 5 | §5 |
| `cross_rule_interactions/` | 3 | multiple (see group manifest) |
| `numeric_range/` | 4 | §5 |

**Total: 60 fixtures** (56 golden-locked from prior batches, 4 new numeric-range
fixtures pending golden capture).

### numeric_coercion/ (§5)
- `numeric_coercion_widening_basic.gddl`
- `numeric_coercion_narrowing_rejected.gddl` (negative path)
- `numeric_coercion_whole_float_accepted.gddl`
- `numeric_coercion_via_crossfield_reference.gddl`
- `numeric_coercion_through_sequential_chain.gddl`

## Depth pass, round 1 (nested/delete/domains/indentation) — both flagged questions resolved

1. **`delete` + `= Source` combined grammar**: confirmed correct as assumed --
   `TypeName InstanceName = Source delete` (`delete` trailing). No changes needed.
2. **What counts as one "scope" for the single-indentation-character rule**: resolved
   as the whole top-level `define`/instance block, including everything nested inside
   it. Inverted one fixture's expected outcome; rebuilt as
   `indentation_nested_scope_differs_from_parent_error.gddl` (negative path). See
   `indentation_and_comments/MANIFEST.md` for the full resolution note.

All 41 fixtures from this round are golden-locked as of batch 5 (see `GOLDEN_STATUS.md`).

## Depth pass, round 2 (numeric coercion) — no ambiguities surfaced

5 new fixtures covering GDDL Spec v4 §5 in full: widening, narrowing-rejection,
whole-float acceptance, coercion through cross-field references (both directions), and
coercion through a sequential op-statement chain. Built with grounded predictions using
the phase/check (phase 6, `check: numeric_coercion`) already established in an earlier
golden batch's `_meta` note -- no fresh spec ambiguity required flagging this round. See
`numeric_coercion/MANIFEST.md` for one non-blocking assumption noted for transparency
(coercion checked once per statement/storage event, not per sub-operation).

## Fixture manifest (flat list)

### nested_field_semantics/ (§6.4–6.5)
- `nested_replace_basic.gddl`
- `nested_modify_only_basic.gddl`
- `nested_modify_only_two_levels.gddl`
- `nested_replace_discards_prior_modify.gddl`
- `nested_scalar_vs_struct_fork.gddl`
- `nested_bare_scalar_field_error.gddl` (negative path)
- `nested_modify_only_three_levels.gddl` (depth pass)
- `nested_level2_replace_sibling_level1_untouched.gddl` (depth pass)
- `nested_mixed_replace_and_modify_across_levels.gddl` (depth pass)

### delete_templates/ (§6.6, §7)
- `delete_template_incomplete_ok.gddl`
- `delete_descendant_completes_and_resolves.gddl`
- `delete_descendant_incomplete_error.gddl` (negative path)
- `delete_own_uninitialized_read_error.gddl` (negative path)
- `delete_multi_generation_chain.gddl` (depth pass — grammar flagged)
- `delete_chain_partial_completion_at_each_generation.gddl` (depth pass — grammar flagged)

### initialization/ (§7, §12 phase 6 vs. 8)
- `init_uninitialized_only_caught_at_export.gddl`
- `init_nested_uninitialized_dotted_path.gddl` (depth pass)
- `init_multiple_uninitialized_fields_all_reported.gddl` (depth pass)
- `init_gap_persists_across_4gen_chain.gddl` (depth pass)

### domains/ (§4.2)
- `domain_field_accepts_valid_member.gddl`
- `domain_field_literal_type_mismatch_error.gddl` (negative path)
- `domain_field_wrong_domain_error.gddl` (negative path)
- `domain_field_nonexistent_member_error.gddl` (depth pass, negative path)
- `domain_multiple_domains_side_by_side.gddl` (depth pass)

### crossfield_references/ (§6.7)
- `crossfield_basic_reference.gddl`
- `crossfield_nested_path_reference.gddl`
- `crossfield_forward_reference_error.gddl` (negative path)
- `crossfield_dot_syntax_disambiguation.gddl`
- `crossfield_self_reference_non_leading.gddl`

### op_statements/ (§6.3)
- `op_statement_assign_equivalence.gddl`
- `op_statement_operator_precedence.gddl` (must-keep regression fixture)
- `op_statement_missing_leading_field_error.gddl` (negative path)

### sequential_execution/ (§6.2)
- `sequential_chained_ops_order_matters.gddl`
- `sequential_longer_chain_order_dependent.gddl` (depth pass)
- `sequential_crossfield_reference_sees_current_value.gddl` (depth pass)

### indentation_and_comments/ (§3)
- `indentation_tabs_only_valid.gddl`
- `indentation_spaces_only_valid.gddl`
- `indentation_mixed_tabs_spaces_error.gddl` (negative path)
- `comments_nested_block_and_code_lookalike.gddl`
- `indentation_deep_nesting_valid.gddl` (depth pass)
- `indentation_nested_scope_differs_from_parent_error.gddl` (depth pass, negative path — rebuilt after scope-granularity resolution)

### composition_no_inheritance/ (§5.2–5.3)
- `composition_multi_level.gddl`
- `composition_same_type_reused_multiple_fields.gddl` (depth pass)
- `composition_with_delete_partial_then_completed.gddl` (depth pass)

### cross_rule_interactions/ (multiple rules combined, see group manifest)
- `cri_delete_composition_crossfield.gddl` (delete + composition + cross-field reference)
- `cri_coercion_multigen_crossfield.gddl` (numeric coercion + multi-generation chain + cross-field reference)
- `cri_indentation_depth_with_replace_modify.gddl` (indentation depth + nested replace/modify-only)

### numeric_range/ (§5)
- `numeric_range_unsigned_boundary.gddl`
- `numeric_range_signed_boundary.gddl`
- `numeric_range_float_boundary_overflow.gddl` (boundary + overflow merged)
- `numeric_range_computed_expression_overflow.gddl`

## Known gaps / deliberately not built

- **`define`-level inheritance-like syntax error fixture** — not built. GDDL has no
  inheritance syntax at all, so there's no canonical invalid syntax to test against;
  building one would mean inventing a plausible-but-fake syntax. Flagged for
  coordination with Compiler Core (may already be covered by their own parser
  error-path tests) rather than guessed at. See `composition_no_inheritance/MANIFEST.md`.

## Not yet covered by this corpus (future rounds)

The seed context's rule list is fully covered at one-fixture-minimum depth per rule, but
several groups have room for more depth (e.g. more nested-field interaction cases, more
domain edge cases, more indentation edge cases at deeper nesting). This is a complete
first pass, not a claim of exhaustive coverage.

## Rules resolved since this handoff was cut (relevant to future fixture rounds)

- **Numeric type coercion — landed as of batch 3 (2026-07-03).** `u8`...`f64` fields
  now have enforced type coercion, real in the reference implementation, not just
  spec text: widening is automatic, narrowing-with-loss is a compile error, narrowing
  with no fractional loss is allowed. Reported via `check: numeric_coercion` at
  phase 6 (depends on a computed value, so it can't run earlier). This corpus's
  existing fixtures didn't need changes, but there's now real golden output to build
  a dedicated numeric-coercion fixture group against, rather than guessing at
  boundaries with nothing to check against (e.g. `3.0 -> i32` vs. `3.5 -> i32`,
  widen-then-narrow chains, what a rejection error actually looks like) -- this was
  explicitly deferred until real data existed; that condition is now met.

## Depth pass, round 3 — three groups brought up from minimum, plus a new category

Closes out every group still sitting at its original 1-fixture minimum after round 1
(`initialization`, `sequential_execution`, `composition_no_inheritance` -- now 4, 3,
and 3 fixtures respectively), plus a new `cross_rule_interactions/` category: fixtures
that deliberately combine 2-3 already-individually-tested rules in one file, since real
bugs found so far in this project came from combinations, not isolated rules.

No blocking spec ambiguities surfaced this round. One prediction is worth flagging as
the highest-value single outcome to check in this batch, not because it's ambiguous but
because it's the most informative if wrong:
`cross_rule_interactions/cri_delete_composition_crossfield.gddl` predicts that a
cross-field-derived value computed inside a `delete` template does NOT recompute when a
descendant later changes the field it was derived from -- grounded in this round's own
`sequential_crossfield_reference_sees_current_value.gddl` and general "no live formula
mechanic" spec principles, but stated explicitly rather than silently assumed. See
`cross_rule_interactions/MANIFEST.md` for the full reasoning.

## Numeric range enforcement (new rule, sibling group to numeric_coercion)

4 fixtures under `numeric_range/`, GDDL Spec v4 §5. Built only after Compiler Core
confirmed the exact `check` name and phase (`phase 6, check: "numeric_range"`) --
same discipline as every other new rule this session, never guessed ahead of
confirmation. Two smaller questions (group naming as a sibling to `numeric_coercion/`
rather than a subcategory; float boundary and float overflow being the same
phenomenon, merged into one fixture instead of two) were resolved as spec/naming
questions directly, without needing an implementation run first. See
`numeric_range/MANIFEST.md` for full details.
