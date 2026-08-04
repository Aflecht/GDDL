# Sequential Execution — Fixture Manifest

Rule group: GDDL Spec v4 §6.2 (Sequential Statement Execution).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `sequential_chained_ops_order_matters.gddl` | Two chained op-statements on the same field (multiply then add, vs. add then multiply) -- a genuinely non-commutative ordering, so the two orderings produce different results. Proves statements aren't collapsed, memoized, or reordered. |
| `sequential_longer_chain_order_dependent.gddl` | **Depth pass.** A longer, 5-operation chain on one field, still order-dependent -- rules out an implementation that's correct for short chains specifically but drops/reorders/collapses longer ones. |
| `sequential_crossfield_reference_sees_current_value.gddl` | **Depth pass.** Combines sequential execution with cross-field references: a reference to another field mid-chain sees that field's CURRENT value at that exact point, not its eventual final value -- rules out lazy/live re-evaluation. |

## Coverage check against seed-context rule list

- [x] Multiple chained op-statements on the same field, order matters, non-associative/non-commutative case (not one where reordering happens to not matter).
- [x] Depth pass: longer 5-operation chain, still order-dependent.
- [x] Depth pass: cross-field reference sees the referenced field's value at that point in the sequence, not its final value.

## Notes

No open questions for this group -- §6.2's worked example already matches this fixture's
expansion model directly, and this fixture is a direct application of it with a
deliberately order-sensitive operator pairing.
