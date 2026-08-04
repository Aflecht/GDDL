# Initialization — Fixture Manifest

Rule group: GDDL Spec v4 §7 (Initialization Rules), read together with §12 phases 6 and 8.
Status: source written, **no golden output captured yet**.

Scoped tightly per instruction: this group does NOT re-test the general "reading an
uninitialized field is a compile error" rule, since that's already exercised elsewhere:

- Delete-template case: `delete_own_uninitialized_read_error.gddl` (delete_templates group).
- Same-instance sequential/forward-reference case: planned in the cross-field expression
  references group (not yet built).

This group covers only the one genuinely new thing in the seed-context rule list for
Initialization: the **phase 6 vs. phase 8 boundary**.

| File | Isolates |
|---|---|
| `init_uninitialized_only_caught_at_export.gddl` | A field never touched anywhere in a two-instance copy chain. Nothing fails during resolve (phase 6) since nothing ever reads it during resolution; the gap is only caught at final export validation (phase 8). Confirms the error surfaces at the correct *phase*, not just that it surfaces. |
| `init_nested_uninitialized_dotted_path.gddl` | **Depth pass.** Uninitialized field inside a nested struct, confirming phase 8 reports the full dotted path (`object.inner.value`) at real depth, not just a bare field name. |
| `init_multiple_uninitialized_fields_all_reported.gddl` | **Depth pass.** Multiple distinct uninitialized fields in one instance, confirming ALL are reported, not just the first one found. |
| `init_gap_persists_across_4gen_chain.gddl` | **Depth pass.** A gap introduced at generation 1 of a 4-generation plain (non-`delete`) copy chain, never touched by any descendant -- confirms it's still caught independently at every generation, not lost or silently accepted partway through a longer chain than previously tested. |

## Coverage check against seed-context rule list

- [x] Reading an uninitialized field is a compile error — covered elsewhere (see scoping note above), not duplicated here.
- [x] Fixture confirming phase 6 vs. phase 8 boundary specifically.
- [x] Depth pass: nested uninitialized field, full dotted path reported.
- [x] Depth pass: multiple uninitialized fields, all reported.
- [x] Depth pass: gap persists uncaught-until-export across a 4-generation chain.

## Resolved questions

**Does a phase-8 export-validation failure cascade through a copy chain the way a
phase-6 resolve failure does?**
Resolved: no. By phase 8, every instance that reached that point already has a fully
resolved tree (phase 6 succeeded for all of them) -- phase 8 checks a property of that
finished tree (is everything required for export actually initialized?), not the
resolution process itself, so there is nothing to "block" on the way phase 6's
collect-and-report policy blocks derived instances after a resolve-time failure. Each
non-`delete` instance is validated for export-completeness independently. Confirmed
now documented directly in the spec (previously this distinction lived only in this
fixture's manifest note).
`StatsBase` and `StatsChild` in `init_uninitialized_only_caught_at_export.gddl` should
therefore each produce their own separate `mp`-uninitialized error at phase 8 -- two
independent errors, not one root-cause plus one blocked-marker. The fixture itself
required no changes; only this manifest's framing did.
