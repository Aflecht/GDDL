# Assign/Op-Statement Unification — Fixture Manifest

Rule group: GDDL Spec v4 §6.3 (Field Operations).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `op_statement_assign_equivalence.gddl` | Op-statement (`hitpoints * 2`) and its hand-written explicit-assign equivalent (`hitpoints = hitpoints * 2`) on two otherwise-identical instances, confirming they produce identical results empirically. |
| `op_statement_operator_precedence.gddl` | **Must-keep regression fixture.** Multi-operator expression (`hitpoints_maximum * 0.5 + 20`) — this exact shape already caused a real bug in Compiler Core. Confirms the numeric result under GDDL's strict left-to-right evaluation rule (which, for this specific operator ordering, coincidentally matches what standard precedence would also give — see next fixture for the case that actually distinguishes the two). |
| `op_statement_missing_leading_field_error.gddl` | Negative path, new rule: every statement must begin with a field name (assign, op-statement, or bare — no other shape exists). A standalone expression with no leading field/`=` is a phase 3 (Parse) syntax error, not a later-phase semantic error. |
| `op_statement_parens_basic.gddl` | **Sibling-bug fixture.** Basic sanity check that explicit paren-grouping (new evaluator code, previously uncovered) parses and evaluates correctly. |
| `op_statement_parens_override_left_to_right.gddl` | **Sibling-bug fixture.** Same operands/operators as `op_statement_operator_precedence.gddl`, but parenthesized to force a different grouping — proves parens actually change the outcome (70.0 → 2050.0), not just that they parse. |
| `op_statement_three_operator_chain.gddl` | **Sibling-bug fixture.** 3-operator / 4-operand chain (`a - b * c + d`) — existing coverage only used 2 operators, which can't rule out an evaluator that's accidentally correct only for that case. |
| `op_statement_leading_operator_error.gddl` | **Sibling-bug fixture.** Negative path companion to `op_statement_missing_leading_field_error.gddl`: a line starting with a bare operator (`* 2`) rather than a numeral literal — a different invalid-first-token shape, worth isolating in case the parser handles the two cases via different code paths. |

## Coverage check against seed-context rule list

- [x] Op-statement vs. equivalent hand-written assign, identical results.
- [x] Multi-operator expression pinning down precedence, flagged as a must-keep regression case.
- [x] Statement-shape negative path (new rule, added this round — every statement must lead with a field name).
- [x] Explicit parentheses: basic grouping, and grouping that overrides left-to-right default (sibling-bug fixtures, new evaluator code).
- [x] 3+-operator chain, beyond the 2-operator case (sibling-bug fixture).
- [x] Leading-operator negative case, companion to the leading-literal negative case (sibling-bug fixture).

## Resolved questions

**Operator precedence in multi-operator expressions.**
Resolved and now written into the spec directly: GDDL uses **strict left-to-right
evaluation**, not standard mathematical precedence. There is no "`*`/`/` bind tighter
than `+`/`-`" rule; parentheses are available for explicit grouping whenever any
particular grouping (standard-math or otherwise) is wanted. Practical impact on
`op_statement_operator_precedence.gddl`: none — its expected result stays `70.0`, since
`hitpoints_maximum * 0.5 + 20` evaluates the same way under both rules (the `*` already
comes first left-to-right). The case that actually distinguishes the two rules
(`20 + hitpoints_maximum * 0.5`, reversed operator order) is covered separately in
`crossfield_self_reference_non_leading.gddl` (crossfield references group), since it
also needed to be written via assign rather than op-statement — see that fixture and
`op_statement_missing_leading_field_error.gddl` for why.
