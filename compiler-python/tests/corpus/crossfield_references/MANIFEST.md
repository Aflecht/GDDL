# Cross-Field Expression References — Fixture Manifest

Rule group: GDDL Spec v4 §6.7 (Cross-Field Expression References).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `crossfield_basic_reference.gddl` | Baseline positive case: flat same-instance field reference (`total_weight = weight * count`), no nesting, no ordering wrinkle. |
| `crossfield_nested_path_reference.gddl` | Nested-path reference (`object.weight`) into a composed struct field, within the current instance's own scope. |
| `crossfield_forward_reference_error.gddl` | Negative path: referencing a field before it's set later in the same instance's sequential execution is a compile error -- the *ordinary* uninitialized-read error (§7), not a distinct "forward reference" error category. |
| `crossfield_dot_syntax_disambiguation.gddl` | Both dot-syntax meanings (nested-field access and identifier-domain access) present in the same instance scope simultaneously, confirming the stated resolution order (current-scope field checked first, then identifier domain) works correctly with both live at once. |
| `crossfield_self_reference_non_leading.gddl` | Self-reference in non-leading position (`hitpoints_maximum = 20 + hitpoints_maximum * 0.5`), only reachable via assign since op-statement syntax requires the field to lead. Doubles as the fixture that actually distinguishes GDDL's strict left-to-right evaluation from standard math precedence (companion to `op_statement_operator_precedence.gddl`, whose operator ordering doesn't distinguish the two rules). |

## Coverage check against seed-context rule list

- [x] `total_weight = weight * count`-style same-instance reference.
- [x] Nested-path case (`object.weight` style).
- [x] Forward-reference is a compile error, same category as any other uninitialized read, no special-casing.
- [x] Dot-syntax disambiguation fixture: nested struct field access + identifier domain access in the same scope.
- [x] Self-reference in non-leading position, via assign (new this round).

## Notes

- `crossfield_forward_reference_error.gddl`'s expression reads two uninitialized fields
  in one statement (`weight * count`, both unset at that point). The fixture's Expected
  comment doesn't commit to which field's error is reported first, or whether both are
  reported -- that's an evaluation-order detail of the reference implementation, not a
  spec question, so it'll be settled by whatever the golden output actually shows rather
  than needing to be resolved up front.
- `crossfield_self_reference_non_leading.gddl` also depends on a newly-resolved rule
  from the op-statements group: every statement must begin with a field name (assign,
  op-statement, or bare) -- see `op_statement_missing_leading_field_error.gddl` in the
  op_statements group for the negative-path proof of that constraint, which is why this
  fixture had to use assign rather than op-statement shorthand.
