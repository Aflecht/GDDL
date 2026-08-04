# Delete Templates — Fixture Manifest

Rule group: GDDL Spec v4 §6.6 (Deleted Instances / Templates), read together with §7
(Initialization Rules) and §12 phase 8 (final validation).
Status: source written, **no golden output captured yet** — pending a run against the
Python reference implementation. "Expected" blocks inside each fixture are predictions
to check the reference compiler against, not golden results.

| File | Isolates |
|---|---|
| `delete_template_incomplete_ok.gddl` | Positive/clean-compile. A `delete` instance left genuinely incomplete compiles with zero errors — incompleteness alone is not a fault at template scope. |
| `delete_descendant_completes_and_resolves.gddl` | Positive/clean-compile. A non-`delete` instance copying from an incomplete template, and explicitly closing the gap, fully resolves and is exportable. |
| `delete_descendant_incomplete_error.gddl` | Negative path. A non-`delete` instance copying from an incomplete template, but never closing the gap, must fail at phase 8 (export validation) — not earlier, and the error must attach to the descendant, not the template. |
| `delete_own_uninitialized_read_error.gddl` | Negative path, the subtle one. A `delete` template's own body reading one of its *own* still-uninitialized fields is an error — no exception for delete templates, distinct from the "may remain untouched" allowance. |
| `delete_multi_generation_chain.gddl` | **Depth pass.** Three-generation chain: delete template -> delete template (copying the first) -> real instance. Isolates a `delete` instance copying from another `delete` instance, and confirms incompleteness tolerance survives multiple hops, not just one. |
| `delete_chain_partial_completion_at_each_generation.gddl` | **Depth pass.** A different shape of the same rule: three fields, each filled in at a different generation across a four-instance chain, confirming *partial* completion (not just total incompleteness) carries forward correctly across `delete` generations. |

## Coverage check against seed-context rule list

- [x] `delete` instance with a genuinely uninitialized field, confirmed not an error at template level.
- [x] Not exported; non-`delete` instance copying from a `delete` template must still fully resolve by export time (both positive and negative paths covered).
- [x] `delete` instance's own body reading one of its own uninitialized fields is an error, isolated from the "may remain incomplete" case.
- [x] Depth pass: multi-generation delete chain, including delete-copying-delete.
- [x] Depth pass: partial completion carried forward across multiple delete generations.

## Resolved: grammar for combining `delete` with `= Source` on an instance header

Previously flagged, now written into the spec directly. Confirmed correct as assumed:
`Type Name = Source delete` (trailing `delete`, consistent with the existing
single-keyword pattern). No changes needed to either fixture --
`delete_multi_generation_chain.gddl` and
`delete_chain_partial_completion_at_each_generation.gddl` both stand as originally
written.

## Notes / assumptions worth confirming

- `delete_descendant_incomplete_error.gddl` assumes the collect-and-report policy (§12
  phase 6) means the error attaches to `StatsIncomplete`, not `StatsTemplate` — this
  follows directly from the spec text ("a direct failure inside an instance's own body
  is recorded once, against that instance"), but is worth double-checking against the
  actual golden output since it's a compiler-behavior detail (error attribution), not
  just a pass/fail outcome.
- No fixture in this group directly targets "delete instance itself absent from
  exported output" as a standalone assertion — it's implicitly covered by
  `delete_descendant_completes_and_resolves.gddl` (StatsTemplate should not appear in
  that fixture's exported data, only StatsFull should). Flagging this so whoever
  captures golden output checks for StatsTemplate's absence explicitly, not just
  StatsFull's presence.
