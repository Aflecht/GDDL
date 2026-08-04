# `define` Composition, No Inheritance — Fixture Manifest

Rule group: GDDL Spec v4 §5.2-§5.3 (define composition, no inheritance).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `composition_multi_level.gddl` | Nested struct-typed fields (composition) working correctly across three levels of `define` nesting (Character -> Equipment -> Weapon), fully resolved in one instance. |
| `composition_same_type_reused_multiple_fields.gddl` | **Depth pass.** Composition BREADTH rather than depth: the same `define` type reused as the field type for two separate sibling fields in one structure, confirming no interference between them. |
| `composition_with_delete_partial_then_completed.gddl` | **Depth pass.** Composition + delete templates combined: a composed sub-field (not top-level) left incomplete inside a `delete` template, closed by a real descendant. |

## Coverage check against seed-context rule list

- [x] Fixture confirming nested struct-typed fields (composition) at multiple levels.
- [x] Depth pass: composition breadth (same type reused as multiple sibling fields).
- [x] Depth pass: composition combined with delete-template partial completeness at a composed sub-level.
- [ ] `define`-level inheritance-like syntax, confirmed parse/compile error -- **not built,
      flagged instead** (see below), per the seed context's own note that this may
      belong to Compiler Core's parser error-path tests rather than this corpus.

## Flagged back through the user (not guessed at)

**Should `define`-level inheritance-like syntax get a fixture in this corpus at all?**
The seed context marks this as optional and explicitly says to coordinate with Compiler
Core first, since it's a parser-level rule (not a resolution-level one) and may already
be covered by their own parser error-path tests. There's an added wrinkle: since GDDL
has no inheritance syntax at all, any fixture attempting to exercise this would have to
invent a plausible-but-invalid syntax to reject (e.g. `define Derived : Base` or
`define Derived extends Base`) -- there's no canonical "the" invalid syntax to test
against, since the spec never defines one (correctly, since the feature doesn't exist).
Building a fixture here would mean guessing at what syntax a user might mistakenly try,
which seems like exactly the kind of guessing this session is meant to avoid. Holding
off on this one pending word from Compiler Core on whether they already cover it, and if
not, what invented syntax would actually be a useful negative-path case to lock in.
