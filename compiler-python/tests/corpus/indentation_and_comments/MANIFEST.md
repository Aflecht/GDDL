# Indentation / Structural Rules — Fixture Manifest

Rule group: GDDL Spec v4 §3 (Lexical Structure — Indentation and Comments), §12 phases 2-3.
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `indentation_tabs_only_valid.gddl` | Positive/clean-compile: consistent tab-only indentation throughout every scope, at multiple nesting depths. |
| `indentation_spaces_only_valid.gddl` | Positive/clean-compile: identical structure to the tabs-only fixture, using spaces exclusively instead. Golden output content should match the tabs-only fixture exactly. |
| `indentation_mixed_tabs_spaces_error.gddl` | Negative path: a tab-indented statement and a space-indented statement within the *same* scope. Built with verified literal whitespace bytes (checked with `cat -A`, not just visual alignment) to guarantee the mixing is real, not a rendering artifact. |
| `comments_nested_block_and_code_lookalike.gddl` | Two things in one file: (1) a block comment nested inside another block comment, 2+ levels deep, confirming nesting depth is handled correctly; (2) a comment containing content that looks like valid GDDL statements/instance declarations, confirming it's fully ignored and never registered. |
| `indentation_deep_nesting_valid.gddl` | **Depth pass.** Five levels of consistent struct-typed field composition, one indentation character throughout, beyond the two-level depth of existing coverage. |
| `indentation_nested_scope_differs_from_parent_error.gddl` | **Depth pass, negative path (rebuilt).** A top-level line is tab-indented; its own nested block is space-indented, internally consistent on its own but not with its parent. Confirms a "scope" for this rule is the whole top-level block including everything nested, not each nested block independently — a different failure shape from `indentation_mixed_tabs_spaces_error.gddl` (which mixes at the same depth, not across a depth boundary). |

## Coverage check against seed-context rule list

- [x] Valid: consistent tabs-only fixture.
- [x] Valid: consistent spaces-only fixture.
- [x] Invalid: mixed tabs/spaces within a single scope, compile error, fixture proving it's caught.
- [x] Valid: nested block comments.
- [x] Valid: comments containing code-lookalike content that must be fully ignored.
- [x] Depth pass: indentation nesting deeper than existing coverage.
- [x] Depth pass: tabs/spaces consistency checked across nesting depth within one scope (resolved as negative path — see below).

## Resolved: what counts as one "scope" for the single-indentation-character rule

Previously flagged, now written into the spec directly. Resolution: a "scope" for this
rule means one ENTIRE top-level `define`/instance block, including everything nested
inside it -- not each individual nested field block independently. A nested block
cannot switch indentation characters from its parent, even if that nested block is
internally self-consistent on its own.

This inverted the original fixture's expected outcome: it was first built as a
POSITIVE case (sibling nested blocks legally differing from each other and from their
parent), which the resolution confirms is wrong. Rebuilt as
`indentation_nested_scope_differs_from_parent_error.gddl`, a negative-path fixture --
still a genuinely new failure shape versus the existing `indentation_mixed_tabs_spaces_error.gddl`
(same-depth sibling mismatch): this one is a depth-mismatch between a parent line and
its own nested block, where the nested block is internally consistent but still wrong
because it doesn't match its parent's character.

## Notes

- `indentation_mixed_tabs_spaces_error.gddl`'s expected phase (3, Parse) is directly
  supported by spec text (§12 phase 3: "Enforce single-indentation-character-per-scope"),
  not an assumption.
- Byte-level verification matters for any fixture mixing tabs and spaces deliberately
  (both `indentation_mixed_tabs_spaces_error.gddl` and
  `indentation_consistent_per_scope_varies_across_siblings.gddl`), since tabs and spaces
  are visually indistinguishable in most viewers. Anyone re-deriving or editing these
  fixtures should re-verify with `cat -A` (or equivalent) rather than trusting the
  rendered appearance -- this was done for both when originally built.
