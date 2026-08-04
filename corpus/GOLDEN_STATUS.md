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
| `numeric_range/` | `numeric_range_computed_expression_overflow.gddl` | pending |
| `numeric_range/` | `numeric_range_float_boundary_overflow.gddl` | pending |
| `numeric_range/` | `numeric_range_signed_boundary.gddl` | pending |
| `numeric_range/` | `numeric_range_unsigned_boundary.gddl` | pending |
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
| `string_fields/` | `string_escape_invalid_sequence.gddl` | **captured** |
| `string_fields/` | `string_escape_lone_trailing_backslash.gddl` | **captured** |
| `string_fields/` | `string_escaped_quote.gddl` | **captured** |
| `string_fields/` | `string_escaped_trailing_backslash.gddl` | **captured** |

**Totals: 68 fixtures — 64 captured, 4 pending, 0 blocked.**

## Capture history

- **Prior batches:** first-pass through depth-pass round 3 fixtures all
  captured. Corpus reached a clean 56/56.
- **Numeric range enforcement added:** 4 new fixtures under
  `numeric_range/`, GDDL Spec v4 §5. Built against the confirmed shape
  (`phase 6, check: "numeric_range"`) from the start -- no prediction/
  reconciliation cycle needed for the phase/check itself. All captured.
- **Two long-missing locks discovered and closed:**
  `circular_references/circular_reference_direct_two_instance.gddl` and
  `domains/domain_logical_id_collision_error.gddl` had no `.golden.json` at
  all for an extended period -- absent from this table's totals too, not
  just from disk, so the staleness was invisible to anyone reading only
  this file. Resolved by pulling both locks from Test Corpus's own
  corpus (`captured_at: 2026-07-20`), confirmed byte-for-byte against a
  fresh reference run in this tree before being placed, not accepted on
  trust.
- **`circular_references/circular_reference_longer_chain.gddl` and
  `string_fields/` (4 fixtures: `string_escaped_quote.gddl`,
  `string_escaped_trailing_backslash.gddl`,
  `string_escape_invalid_sequence.gddl`,
  `string_escape_lone_trailing_backslash.gddl`) added** since the
  original 56/56 baseline -- all captured against the real reference
  implementation, not hand-derived.
- **This table itself was stale before this regeneration**, still
  showing the original "60 fixtures -- 56 captured, 4 pending" total
  from before ANY of the additions above, missing entire groups
  (`circular_references/`, `string_fields/`) rather than just the two
  fixtures explicitly being fixed -- a stronger version of the exact
  silent-divergence failure this whole exercise was about. Regenerated
  in full from actual `.golden.json` capture_status on disk, not
  hand-patched, per this file's own header instruction.
