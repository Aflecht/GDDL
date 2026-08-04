# Identifier Domains as Strict Types — Fixture Manifest

Rule group: GDDL Spec v4 §4.2 (Identifier Blocks Are Types (Domains)).
Status: source written, **no golden output captured yet**.

| File | Isolates |
|---|---|
| `domain_field_accepts_valid_member.gddl` | Positive/clean-compile baseline: a domain-typed field accepts members of its own domain. |
| `domain_field_literal_type_mismatch_error.gddl` | Negative path 1/2: a bare literal (not an identifier reference at all) assigned to a domain-typed field. Isolated dedicated version of the deliberate `attack = 1` case already present in `Example.txt` (Human_Fighter) -- not duplicating that file, giving this rule its own minimal, single-purpose fixture. |
| `domain_field_wrong_domain_error.gddl` | Negative path 2/2: a syntactically valid identifier reference, but from the wrong domain. Deliberately distinct failure mode from the literal-mismatch case -- exercises domain-boundary checking specifically, not just "is this an identifier at all" checking. |
| `domain_field_nonexistent_member_error.gddl` | **Depth pass, negative path.** A typo'd/nonexistent member of the CORRECT domain -- distinct from the wrong-domain-entirely case, since the domain itself resolves fine here, only the specific member doesn't exist. |
| `domain_multiple_domains_side_by_side.gddl` | **Depth pass, positive path.** Two different identifier domains used as sibling fields on the same `define`, both correctly assigned, confirming no cross-domain interference. |

## Coverage check against seed-context rule list

- [x] Fixture(s) confirming a domain-typed field accepts only that domain's members.
- [x] At least one deliberate type mismatch fixture (bare literal case, and wrong-domain case as a bonus second negative path beyond what was strictly asked for).
- [x] Depth pass: nonexistent/typo'd domain member, distinct from wrong-domain-entirely.
- [x] Depth pass: multiple domains used side-by-side without interference.

## Notes

Original group had no open questions. New for the depth pass:
`domain_field_nonexistent_member_error.gddl`'s expected phase (5) is directly grounded
in spec text (§12 phase 5: "identifier references resolve to a valid domain member" is
explicitly listed as a Validate-phase check) -- not a guess. The exact `check` name
Compiler Core reports it under is left unpredicted, since that's an implementation
detail, not a spec question.
