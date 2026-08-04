# Nested Field Semantics — Fixture Manifest

Rule group: GDDL Spec v4 §6.4 (Replace vs. Modify-Only) and §6.5 (No Merge Semantics).
Status: source written, **no golden output captured yet** — pending a run against the
Python reference implementation from the Compiler Core session. Every "Expected" block
inside each fixture is my own prediction from reading the spec, not a golden result;
treat it as a hypothesis to check the reference compiler against, not ground truth.

| File | Isolates |
|---|---|
| `nested_replace_basic.gddl` | `field = SourceInstance` at one nesting level: discard → copy → override, with two different sources to catch stale-data bugs. |
| `nested_modify_only_basic.gddl` | Bare `field` at one nesting level: only listed sub-fields touched, sibling keeps inherited value. |
| `nested_modify_only_two_levels.gddl` | Bare `field` nested inside bare `field` (2 levels) — confirms the modify-only rule is genuinely recursive, not just correct one level deep. |
| `nested_replace_discards_prior_modify.gddl` | **No-merge proof.** Bare-field modify followed by `field = Source` on the same field, same instance — the replace step must discard the just-written value, not merge it. This is the fixture that actually distinguishes replace-then-modify from merge; the two "basic" fixtures above do not, on their own, since nothing conflicts. |
| `nested_scalar_vs_struct_fork.gddl` | Contrasts a scalar field (plain overwrite only, no fork) against a struct field (both forms available) in the same instance, for direct comparison in one golden output. |
| `nested_bare_scalar_field_error.gddl` | **Negative path.** Bare-form syntax used on a scalar-typed field — compile error, phase 5 (Validate), not phase 3 (Parse). |
| `nested_modify_only_three_levels.gddl` | **Depth pass.** Three levels of bare-field (modify-only) nesting, one level deeper than the existing two-level fixture. |
| `nested_level2_replace_sibling_level1_untouched.gddl` | **Depth pass.** A level-2 field replaced via `=`, nested inside a bare (modify-only) level-1 entry, while a completely separate sibling field at level 1 is never entered at all. |
| `nested_mixed_replace_and_modify_across_levels.gddl` | **Depth pass.** The reverse ordering from the fixture above: outer field fully replaced, then a nested sub-field within that fresh replacement entered modify-only. Together the two fixtures cover both orderings of mixing replace and modify-only across levels. |

## Coverage check against seed-context rule list

- [x] `field = SourceInstance` full replace-then-modify, at nesting depth 1.
- [x] Bare `field` modify-only, at nesting depth 1.
- [x] Fork only observable on struct-typed fields (scalars always plain overwrite).
- [x] No merge mode — explicit fixture proving no fixture "accidentally implies" merge.
- [x] 2+ levels of nesting depth, bare `field` inside bare `field`.
- [x] Negative path: bare-form syntax on a scalar-typed field is a compile error.
- [x] Depth pass: 3+ levels of bare-field nesting.
- [x] Depth pass: level-2 replace with an untouched level-1 sibling.
- [x] Depth pass: mixed replace/modify-only across levels, both orderings.

## Resolved questions

**Bare (no `=`) syntax on a scalar-typed field — is it even legal?**
Resolved by lead session: it is a compile-time error, since the bare form's meaning
("enter existing scope, touch only what's listed") requires a scope to exist, and
scalars have none. Confirmed as a **phase 5 (Validate)** error specifically, not
phase 3 (Parse) — the parser can't tell bare-struct from bare-scalar syntactically,
since both are "field name, no `=`, indented block" until field types are known at
phase 4 (Register). Covered by `nested_bare_scalar_field_error.gddl`. Worth relaying
this phasing detail to Compiler Core if their error currently surfaces at the wrong
stage.
