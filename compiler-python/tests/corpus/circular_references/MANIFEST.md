# Circular Reference Detection — Fixture Manifest

New group. Circular reference detection (DFS-based, over the instance-copy graph
built during registration) was implemented and confirmed by Compiler Core: phase 4
(Register), check `circular_dependency`, correctly handles both top-level and nested
full-replace cycles, zero false positives on valid chains.

Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `circular_reference_direct_two_instance.gddl` | The simplest case: a direct, mutual `A = B`, `B = A` cycle between two instances via full replace. Neither can resolve without the other, with no base case. |
| `circular_reference_longer_chain.gddl` | Three-instance cycle (`A = B`, `B = C`, `C = A`) -- rules out a detector that's correct for the minimal 2-instance case specifically but mishandles path reconstruction for a longer cycle. Phase/check predicted with the same confidence as the 2-instance fixture; the exact 3-element path string format is the fixture's actual point of verification. |

## Coverage check against this round's request

- [x] Direct `A = B`, `B = A` cycle, predicted at phase 4, check `circular_dependency`
      with confidence (spec-grounded/specified, not guessed).
- [x] Longer 3+-instance cycle (`A = B`, `B = C`, `C = A`), same confidence level.

## Notes

- This fixture's phase/check prediction is stated with the same confidence as the
  corrected prediction in `domains/domain_logical_id_collision_error.gddl` -- both are
  documented, confirmed implementation details communicated directly, not genuinely
  open questions requiring an implementation run to resolve first.
- As a side effect of building this fixture, it implicitly confirms (rather than
  sidesteps, as earlier fixtures in this corpus generally did by always declaring a
  copy's source before the copier) that forward-referencing an instance not yet
  declared later in the same file is legal at the registration level -- necessarily
  true for ANY two-instance mutual cycle to even be reachable for phase 4 to reject,
  since one direction must be a "forward" reference relative to file order. Worth
  keeping in mind if a future fixture wants to isolate that specific sub-claim on its
  own (a NON-circular forward reference, e.g. `A = B` declared before `B`, with no
  cycle, confirming plain forward-reference is legal independent of the cycle
  question) -- not built yet, not asked for, just noted as a natural companion.
- Not yet built (not asked for this round, but a natural next fixture given "handles
  both top-level and nested full-replace cycles" was specifically called out as
  verified): a cycle occurring through a NESTED struct field's full replace, rather
  than at the top-level instance-copy layer. Would isolate the "nested" half of what's
  already confirmed implemented, the way this fixture isolates the "top-level" half.
  Genuinely non-trivial to construct correctly (the natural-seeming constructions
  collapse into being structurally identical to the top-level case rather than
  testing something new) -- worth a design discussion before guessing at one, not a
  quick follow-up.
