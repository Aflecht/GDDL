# String Fields — Fixture Manifest

Prior corpus coverage of `string N` fields was purely incidental (one field inside
`composition_no_inheritance/composition_multi_level.gddl`, not focused on boundary or
encoding behavior at all). This group covers the language-level string-semantics gap
identified this session: length boundary enforcement, UTF-8 byte-vs-character
counting, empty string handling, and full string-literal escape processing (§5).

Status: all 8 fixtures captured. 0 pending, 0 blocked.

| File | Isolates |
|---|---|
| `string_length_boundary.gddl` | Exactly N-1 bytes accepted, N bytes rejected -- hard cutoff, not off-by-one in either direction. |
| `string_utf8_byte_vs_char_length.gddl` | Confirms length is measured in UTF-8 bytes, not characters, in both directions: an accepted case at the exact byte limit despite a mismatched char count, and a rejected case where char count alone looks safe but byte count isn't. |
| `string_empty_accepted.gddl` | Empty string always accepted (0 bytes <= N-1 for any N>=1), including the extreme `string 1` case where empty is the ONLY legal value. |
| `string_escaped_quote.gddl` | `\"` resolves to a literal double-quote, backslash consumed. Ordinary compliance test against §5. **Supersedes** the deleted `string_escaped_quote_current_behavior.gddl` -- see "Superseded fixture" note below. |
| `string_escaped_trailing_backslash.gddl` | `\\` resolves to a literal backslash, specifically in the TRAILING-backslash shape (`"C:\\Users\\"` -> `C:\Users\`) -- the exact ambiguity `\\` exists to resolve, per spec. This precise case was found broken during implementation (naive single-character lookback misidentified the real closing quote as still-escaped) and fixed via proper backslash-run parity counting. |
| `string_escape_invalid_sequence.gddl` | `\` followed by any character other than `"` or `\` (e.g. `\n`) is a compile-time error, not a passthrough -- confirms control-character escapes are deliberately out of scope, not an oversight. |
| `string_escape_lone_trailing_backslash.gddl` | A single unpaired `\` immediately before an apparent closing quote is never reachable as an escape-sequence error -- by the parity rule it's read as escaping that quote, so the tokenizer keeps scanning; with no later terminator, the result is a phase-3 "unterminated string literal," a structurally different failure from `string_escape_invalid_sequence.gddl`'s phase-6 rejection. Not originally requested; added because the parity fix surfaced this non-obvious result. |
| `string_escaping_through_composition.gddl` | Escape processing (§5) verified through a nested composed field (`equipment.weapon.name`, two hops deep, modeled on `composition_multi_level.gddl`), not just flat top-level fields. Both `\"` and the parity-rule `\\` case tested at the same nested path across two instances, isolating escape-type from nesting depth. |

## Superseded fixture: `string_escaped_quote_current_behavior.gddl` (deleted, not just recaptured)

This fixture originally golden-locked CONFIRMED-BUGGY current behavior (backslashes
surviving unescaped) at a time when the spec said nothing about escaping and the
design question was genuinely open. That gap is now resolved (§5, String Literal
Escaping) and the underlying bug (`_strip_quotes()`/the equivalent field-value site
never actually unescaping anything) is fixed.

Compiler Core didn't just fix the bug -- they replaced this single fixture with four
new ones (`string_escaped_quote.gddl`, `string_escaped_trailing_backslash.gddl`,
`string_escape_invalid_sequence.gddl`, `string_escape_lone_trailing_backslash.gddl`),
each isolating a distinct aspect of the now-resolved rule rather than one file trying
to cover all of it. The old fixture and its golden lock were deleted outright, not
recaptured under the old name -- it's superseded, not stale-and-fixed.

**Cross-copy-drift note, same root cause as an earlier incident this session:** this
corpus never received the fix delivery at all until explicitly flagged and provided --
the fix landed in Compiler Core's own copy with nothing forwarded here to ride along
with it. Caught by flagging the discrepancy rather than assuming silence meant nothing
had changed, the same discipline that caught the two originally-missing golden locks
earlier in this project.

## Coverage check against the escape-semantics gap

- [x] Length boundary: N-1 accepted, N rejected.
- [x] UTF-8 byte-vs-character length, both directions.
- [x] Empty string, confirmed accepted per spec's byte-counting logic, not guessed.
- [x] `\"` resolves correctly (literal quote, backslash consumed).
- [x] `\\` resolves correctly, specifically in the harder trailing-backslash shape.
- [x] Invalid escape sequence (`\n` and similar) is a compile-time error, not a passthrough.
- [x] Lone trailing unpaired backslash -- confirmed as a phase-3 parse error via the
      parity rule, a different mechanism from the phase-6 invalid-sequence rejection.
- [x] Escape processing verified through a nested composed field, not just flat
      top-level fields, covering both escape types at the same nested path.

## Notes

- The length-boundary and empty-string predictions are directly grounded in spec text
  (String Length Enforcement section, quoted/paraphrased in each fixture's own
  comments), not guesses -- byte-counting, the N-1 content-capacity rule, and
  compile-time (not export-time) rejection are all explicit in the spec.
- `string_escaping_through_composition.gddl`'s predictions were computed against the
  correct, resolved §5 rule from the start (it was built after that rule existed) --
  no changes needed when the superseded-fixture drift was discovered and fixed.
- Earlier, this group's escape-bug fixture's predicted character sequence was
  independently re-verified by direct computation rather than trusting a manually
  transcribed value, which turned out to be off by one character. Same discipline
  applied again here: the four replacement fixtures' captured values were checked
  directly (not inferred from a summary) before being written into this corpus.
