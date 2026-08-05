# Golden Output File Format

Each fixture `<name>.gddl` has a paired `<name>.golden.json` file in the same directory.
The `.golden.json` is the authoritative acceptance record for that fixture once
captured -- it is what a second (e.g. C++) implementation is graded against, not the
"Expected" prediction comment inside the `.gddl` file itself. Prediction comments are
a first-pass guess written before any compiler ran; golden files are the real thing.

**Revision note:** this schema was revised after the first real data delivery to align
with Compiler Core's actual structured-export conventions, rather than the earlier,
speculative shape this file originally described. Two conventions in particular are now
load-bearing and must be preserved verbatim wherever they appear in captured data:

- **Uninitialized fields are represented explicitly**, as `{"__uninitialized__": true}`,
  never simply omitted from a `resolved` object. An omitted key and an explicit
  "this field exists but has no value" marker are different facts; the corpus preserves
  that distinction rather than collapsing it.
- **Identifier-domain values are objects, not bare strings**:
  `{"__identifier_ref__": true, "domain": "...", "key": "...", "logical_id": "..."}`.
  Never flatten this to just the key or just the logical ID -- all three pieces are
  part of the golden value.

## Wrapper schema

```json
{
  "fixture": "<name>.gddl",
  "capture_status": "pending | captured | blocked",
  "blocked_reason": "string, present only when capture_status is \"blocked\"",
  "captured_at": "ISO 8601 date, or null if not yet captured",
  "compiler_core_version": "string identifying the reference implementation build/commit, or null if not yet supplied",
  "output": { }
}
```

`capture_status` is this corpus's own tracking field (distinct from Compiler Core's
internal `status` field inside `output`, described below -- don't confuse the two).

- `"pending"` -- no captured output yet. `output` is `null`.
- `"captured"` -- `output` holds a real, verbatim export from Compiler Core. Locked,
  authoritative.
- `"blocked"` -- distinct from `"pending"`. Used when a fixture's correct expected
  behavior is itself expected to change soon (e.g. known, planned upstream work), such
  that locking output now would just need to be redone shortly. `output` MAY still be
  populated with real data Compiler Core already produced (useful for reference), but a
  `"blocked"` fixture must NOT be casually promoted to `"captured"` just because data
  exists for it -- check `blocked_reason` first, and re-verify against current behavior
  before promoting.

## `output` -- verbatim passthrough from Compiler Core

`output` is Compiler Core's own per-fixture object, copied through unmodified -- not
re-derived or restructured into a corpus-invented shape. This keeps every future batch
a direct drop-in with no transformation step to get subtly wrong. Two top-level shapes
appear, matching Compiler Core's own `status` field.

**Revision note (2026-07-03, batch 3):** phase 4 (Register) and phase 5 (Validate) are
now real, separate passes in the reference implementation, not folded into phase 6.
This added two fields to the shape below: a top-level `duplicate_errors` array and a
per-instance `check` field alongside `phase`, naming which independently-attributable
check produced a given result or error (e.g. `field_shape`, `domain_typing` for phase
5; `uninitialized_read` for phase 6; `final_completeness` for phase 8;
`numeric_coercion`/`numeric_range`/`string_length`/`string_escape` for phase 6;
`id_collision`/`circular_dependency` for phase 4).

**`duplicate_errors` is broader than its name suggests** -- confirmed from real data,
not just the original "phase 4 duplicate-name detection" guess. It holds ANY
phase-4/Register-level structural error, each as `{phase, check, line, message}`:
- Duplicate instance/type names (the original motivating case).
- `id_collision` -- a logical ID collision between two identifier-domain entries
  (§4.1.1/§4.1). These have NO corresponding entry in `instances` at all -- the
  collision is a property of the identifier domain's own declaration, independent of
  any instance ever referencing it, so `instances` can be `{}` for a file that's
  nothing but a colliding identifier block.
- `circular_dependency` -- a circular instance-copy reference (`A = B`, `B = A`, or
  longer). Unlike `id_collision`, this ALSO appears per-instance in `instances`, once
  for each instance participating in the cycle -- e.g. a 2-instance cycle produces TWO
  entries in `duplicate_errors` (one per participating instance's declaration line)
  AND corresponding `status: "error"` entries for both `A` and `B` in `instances`, all
  four citing the identical named cycle path (e.g. `A -> B -> A`), not a generic
  "a cycle exists somewhere" message.

### `output.status == "parsed"`

```json
{
  "status": "parsed",
  "duplicate_errors": [ ],
  "warnings": [ ],
  "instances": {
    "<InstanceName>": {
      "status": "ok | delete | incomplete | error",
      "resolved": { /* present for ok/delete/incomplete */ },
      "phase": null,
      "check": null,       /* or a string naming the specific check, see above */
      "missing_fields": [ /* present only when status == "incomplete" */ ],
      "line": 0,          /* present only when status == "error" */
      "message": "..."    /* present only when status == "error" */
    }
  }
}
```

A fixture can have more than one instance reported, including a mix of `ok`, `delete`,
and `error`/`incomplete` statuses across different instances in the same file (this is
exactly the independent-per-instance phase-8 behavior confirmed earlier in this
project). `delete`-marked instances DO appear here, with their own `resolved` data
(possibly containing `__uninitialized__` markers) -- their exclusion from a real export
build is a separate concern from whether the golden fixture surfaces their internal
state for verification purposes.

### `output.status == "parse_error"`

```json
{
  "status": "parse_error",
  "error": {
    "phase": 3,
    "line": 0,
    "message": "..."
  }
}
```

## Warnings (formalized 2026-07-03, real schema confirmed from actual data)

GDDL Spec v4 §12.1 defines warnings: a non-blocking diagnostic category distinct from
errors. Compiles clean, but flagged for the designer's attention. First defined
warning: a bare struct-field entry with zero children (§6.4).

Real, confirmed schema (from `init_nested_uninitialized_dotted_path.gddl`'s actual
captured data): a `warnings` array at the fixture level, sibling to `status` and
`instances`/`error` -- NOT nested per-instance. Present as `[]` on every fixture
without one (confirmed: fixtures with `output.status == "parse_error"` do not carry
this key at all, since they never reach instance resolution -- only
`output.status == "parsed"` fixtures have it).

```json
{
  "status": "parsed",
  "duplicate_errors": [ ],
  "warnings": [
    {
      "phase": 3,
      "check": "empty_bare_field",
      "line": 0,
      "message": "..."
    }
  ],
  "instances": { }
}
```

Each entry uses the same attribution shape as an error (`phase`/`check`/`line`/
`message`), but structurally separate: a fixture can be `status: "parsed"` with a
non-empty `warnings` array and still have every instance resolve to `status: "ok"` --
warnings never block compilation or export, by definition. Conversely, a fixture can
have both a real error AND a warning in the same file, unrelated to each other, or
(as in `init_nested_uninitialized_dotted_path.gddl`) directly caused by the same
underlying construct: a bare `field` with a zero-statement body simultaneously (a) is
allowed and produces the `empty_bare_field` warning, and (b) leaves whatever it would
have initialized still uninitialized, which can separately trigger a real phase-8
error if that field turns out to be required for export.

## Filling in real data

When a structured batch arrives, copy each fixture's Compiler Core object verbatim into
that fixture's `.golden.json` under `output`, set `capture_status` accordingly, and fill
`captured_at`. Never hand-derive `output` from the `.gddl` file's own "Expected"
comment. If the two disagree, that disagreement gets reconciled explicitly (see corpus
process established earlier this session), not silently overwritten in either
direction -- though as of the first batch, all 28 delivered fixtures were confirmed
matching what had already been established, so no reconciliation was needed this round.

