# Numeric Type Coercion — Fixture Manifest

Rule group: GDDL Spec v4 §5 (Numeric Type Coercion). Landed as a real, enforced rule in
Compiler Core partway through this project (see `op_statements/MANIFEST.md` and
`GOLDEN_STATUS.md` batch 3 for its introduction) -- this is the first dedicated fixture
group for it. Previously the only thing exercising coercion at all was
`op_statements/op_statement_three_operator_chain.gddl`, incidentally (built for
evaluation-order/precedence coverage, before the rule existed).

Status: source written, **no golden output captured yet**.

Known phase/check, not a fresh assumption: coercion is enforced in phase 6 (Resolve),
at the literal point of storage, reported with `check: "numeric_coercion"` when it
fires -- established directly in an earlier golden batch's `_meta.numeric_coercion_note`
(2026-07-03, batch 3), not guessed at here.

| File | Isolates |
|---|---|
| `numeric_coercion_widening_basic.gddl` | Basic widening: an int literal and a pure-int expression result, both stored into float-typed fields for the first time. |
| `numeric_coercion_narrowing_rejected.gddl` | Negative path: genuine fractional loss (a non-exact division result, and a fractional literal) stored into integer-typed fields -- compile error, not silent truncation. |
| `numeric_coercion_whole_float_accepted.gddl` | Positive-path companion to the fixture above: a float value with NO fractional part (literal or expression result) stored into an integer field -- must be accepted, not rejected just for being syntactically float. |
| `numeric_coercion_via_crossfield_reference.gddl` | Coercion keyed on the TARGET field's declared type at the point of storage, not the source field's type -- tested in both directions (widening and narrowing-rejection) through a cross-field reference (§6.7), to rule out the indirection bypassing the check. |
| `numeric_coercion_through_sequential_chain.gddl` | An op-statement chain on an int field with a float operand mid-chain (`count * 1.5` then `+ 2`) -- confirms the field's declared type governs at each storage point, not whatever type the intermediate arithmetic produced. |

## Coverage check against this round's request

- [x] Basic widening (literal and op-statement/expression result).
- [x] Narrowing rejected (division result and literal, both genuinely fractional).
- [x] Whole-number float accepted (literal and expression result).
- [x] Coercion through cross-field reference (both directions).
- [x] Coercion through a sequential chain with a mid-chain float operand.

## Fixture-construction fix (2026-07-03, post-first-run)

First run against Compiler Core surfaced a shared-root-cause issue across 3 fixtures,
correctly caught by phase 8, not a bug anywhere: `numeric_coercion_widening_basic.gddl`
(`FromIntExpression`), `numeric_coercion_whole_float_accepted.gddl` (both instances),
and `numeric_coercion_via_crossfield_reference.gddl` (both instances) each used a
shared `define` with more than one field, but individual instances only ever set the
one field under test -- leaving the `define`'s other field(s) genuinely untouched.
Every coercion *value* under test was already correct in all three; this was purely a
fixture-completeness gap, not a coercion bug. Fixed by adding a throwaway value
(clearly commented as such, and unrelated to the coercion behavior under test) to
close each instance's other field(s). `numeric_coercion_narrowing_rejected.gddl` and
`numeric_coercion_through_sequential_chain.gddl` were unaffected -- both already fully
initialize every field their shared `define`s declare -- and were captured as-is on
the first run.

## Notes

No genuine spec ambiguities surfaced while building this group -- the rule as stated
this round, combined with the phase/check already established in an earlier golden
batch, was specific enough to build all 5 fixtures with grounded, non-guessed
predictions. One assumption worth surfacing anyway (not blocking, just noted): this
group assumes coercion is checked once per op-statement/assign STATEMENT (i.e. once per
storage event), not per sub-operation within a single multi-operator expression. This
follows from "at the literal point of storage" being singular per statement, and is
exercised concretely by `numeric_coercion_through_sequential_chain.gddl`'s two-statement
chain -- if that assumption is wrong, that fixture's golden result would be the first
place it shows up.
