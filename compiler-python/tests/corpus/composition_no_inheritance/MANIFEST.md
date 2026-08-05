# `define` Composition, No Inheritance — Fixture Manifest

Rule group: GDDL Spec v4 §5.2-§5.3 (define composition, no inheritance).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `composition_multi_level.gddl` | Nested struct-typed fields (composition) working correctly across three levels of `define` nesting (Character -> Equipment -> Weapon), fully resolved in one instance. |
| `composition_same_type_reused_multiple_fields.gddl` | **Depth pass.** Composition BREADTH rather than depth: the same `define` type reused as the field type for two separate sibling fields in one structure, confirming no interference between them. |
| `composition_with_delete_partial_then_completed.gddl` | **Depth pass.** Composition + delete templates combined: a composed sub-field (not top-level) left incomplete inside a `delete` template, closed by a real descendant. |
| `composition_nested_u16_fields.gddl` | **Dual-purpose.** Composition + `u16`-typed fields at multiple nesting levels. Golden-locked here for language-level resolution (target-independent, stands on its own). The SAME source is separately handed to Compiler Core for placement under `export_z80_test/` and validation via real Z80 toolchains -- that export-correctness concern is NOT captured by this corpus's schema, deliberately. No string field (Z80 string storage semantics are an open design question this fixture doesn't depend on). |

## Coverage check against seed-context rule list

- [x] Fixture confirming nested struct-typed fields (composition) at multiple levels.
- [x] Depth pass: composition breadth (same type reused as multiple sibling fields).
- [x] Depth pass: composition combined with delete-template partial completeness at a composed sub-level.
- [x] Dual-purpose: composition + `u16` fields, motivated by a Z80 export-target gap but golden-locked here purely on its own language-level merits (see Notes below).
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

## Note on `composition_nested_u16_fields.gddl`'s origin (not an ambiguity, just context)

Motivated by a real gap found in Z80 export testing (Compiler Core/lead session
history): no Z80 export fixture had exercised composition or a `u16` field
end-to-end on real toolchains, only a single flat `u8` field. Explicitly resolved as
a dual-channel situation, not a schema question: this corpus's golden-lock schema is
target-independent by design and correctly has no concept of an export target, so it
was never going to grow one to cover this. The `.gddl` source is authored once and
used twice -- golden-locked here for its own legitimate language-level value, and
separately handed to Compiler Core for placement under their own `export_z80_test/`
directory and real-toolchain validation, which is a wholly separate artifact this
corpus doesn't track. No string field included -- Z80 string storage semantics are a
separate, not-yet-settled design question this fixture doesn't depend on.
