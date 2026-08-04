# Cross-Rule Interactions — Fixture Manifest

New category, depth-pass round 3. Every prior fixture in this corpus isolates ONE rule
at a time (by design -- see the original seed context's naming convention). This group
is the deliberate exception: real bugs found so far in this project (operator
precedence, leading-token parsing) came from rule COMBINATIONS Compiler Core's
implementation hadn't specifically been tested against, not from isolated rules in
their own right. These fixtures combine 2-3 already-individually-tested rules in one
file, targeting interactions no single-rule fixture could surface.

Status: source written, **no golden output captured yet**.

| File | Combines |
|---|---|
| `cri_delete_composition_crossfield.gddl` | `delete` template + composition + cross-field reference. A composed sub-field is changed by a descendant without restating a cross-field-derived sibling field -- tests whether that derived field recomputes (predicted: no) or stays as originally resolved in the template. |
| `cri_coercion_multigen_crossfield.gddl` | Numeric coercion + multi-generation copy chain + cross-field reference. A coerced int value from generation 1 is read via cross-field reference in generation 3, checking the EXPORTED representation survives two generations of copying without reverting to a float-tainted form. |
| `cri_indentation_depth_with_replace_modify.gddl` | Indentation depth + nested replace/modify-only semantics, at the same real nesting depth simultaneously -- confirms both rules apply correctly together, not just in isolated shallow fixtures. |

## Notes on the highest-value fixture in this group

`cri_delete_composition_crossfield.gddl` makes an explicit, stated prediction (cross-
field-derived values do NOT live-recompute after a descendant changes an underlying
referenced field) grounded in already-established behavior from this same round
(`sequential_execution/sequential_crossfield_reference_sees_current_value.gddl`) and
from general spec principles (compile-time, deterministic, strictly sequential
execution -- no "live formula" mechanic described anywhere). This is treated as a
well-grounded prediction, not a blocking ambiguity requiring pre-emptive routing back --
but it's flagged prominently in the fixture's own comments as the single most
informative outcome to check in this whole round: if it comes back wrong, that's either
a real bug, or evidence of an actual, previously-undocumented recomputation rule this
corpus hasn't caught up to yet. Either way it's worth surfacing explicitly rather than
silently accepting whatever golden output says.

## Coverage check against this round's request

- [x] `delete` + composition + cross-field reference, all in one fixture.
- [x] Numeric coercion through a multi-generation copy chain, read via cross-field
      reference in a later generation.
- [x] Indentation depth combined with nested replace/modify-only semantics, both rules
      applying at the same real nesting depth.
