# Numeric Range Enforcement — Fixture Manifest

Rule group: GDDL Spec v4 §5 (Numeric Range Enforcement). Sibling group to
`numeric_coercion/`, not a subcategory of it -- separate check name (`numeric_range`
vs. `numeric_coercion`), separate failure mode (out-of-range vs. fractional-loss-on-
narrowing), matching the existing pattern of `domains/` and `numeric_coercion/` being
siblings despite both being "type enforcement at storage."

Status: source written, **no golden output captured yet**.

Known phase/check, confirmed directly (not a fresh assumption, and confirmed as a
spec/naming question rather than something requiring an implementation run): phase 6,
`check: "numeric_range"`, same attribution pattern as `numeric_coercion`.

| File | Isolates |
|---|---|
| `numeric_range_unsigned_boundary.gddl` | Representative unsigned type (`u8`): min/max accepted exactly at the limit, one step past either limit rejected -- not wrapped, not clamped. |
| `numeric_range_signed_boundary.gddl` | Representative signed type (`i16`): same shape as the unsigned fixture, specifically covering the negative-minimum boundary an unsigned type can never reach. |
| `numeric_range_float_boundary_overflow.gddl` | Float boundary and float overflow, MERGED per explicit resolution -- for floats these are the same phenomenon (out-of-range == magnitude exceeds finite representable range == becomes infinite). A value near `f32`'s max finite magnitude accepted; a computed (not literal) value pushed past it into infinity rejected. |
| `numeric_range_computed_expression_overflow.gddl` | Integer-side computed overflow: neither operand alone is out of range, only their computed sum is -- confirms the check applies to arithmetic results, not just literals, mirroring the same concern already established for `numeric_coercion`. |

## Coverage check against this round's request

- [x] Unsigned boundary (min/max accepted, one-past-either rejected).
- [x] Signed boundary (covers the negative-min case unsigned types can't reach).
- [x] Float boundary/overflow, merged per resolution (not built as two separate fixtures).
- [x] Computed-expression overflow, integer side.

## Notes

- The merge decision for the float fixture, and the group's separation from
  `numeric_coercion/`, were both resolved as spec/naming questions directly, without
  needing to wait on Compiler Core's implementation -- only the exact `check` name and
  phase required that confirmation, which arrived as `phase 6, check: "numeric_range"`
  before any of these fixtures were written. No guessed shapes anywhere in this group.
- Assumed (not flagged, low-risk): plain negative-literal syntax (e.g. `-32768`) is
  legal at the lexical level regardless of the target field's type -- range-rejection
  for a negative literal assigned to an unsigned field (e.g. `-1` into `u8`) is a
  `numeric_range` failure, not a separate "negative literals aren't valid syntax for
  unsigned fields" parse-time rule. This is unrelated to the unary-minus operator-
  chaining bug found earlier in `sequential_longer_chain_order_dependent.gddl` (now
  fixed) -- that was about a binary `-` operator's token state bleeding between
  statements, not about literal number tokens.
