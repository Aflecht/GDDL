# GDDL Compiler Core — Handoff / Orientation

This document exists because the working files (`.py` source + `corpus/`)
don't capture everything a fresh session would need. It's a substitute
for re-reading this entire conversation. If you're picking this project
up cold, read this first, then the code (comments are detailed and
explain *why*, not just *what*).

## Role and scope

This is the **Compiler Core** session for a project building a compiler
for **GDDL** — a compile-time, text-based data definition language for
game development (developers define typed structures with `define`, then
build data instances from them, copying/modifying/calculating everything
at compile time; the runtime never interprets GDDL, only consumes
finished resolved data).

Scope is specifically **pipeline phases 1–8**, excluding export:

1. Read source
2. Preprocess (strip comments, drop empty lines)
3. Parse (indentation-based AST)
4. Register (build lookup tables, detect duplicate names)
5. Validate (types/fields exist, structure nesting valid, domain typing)
6. Resolve instances (copy-and-modify, nested field semantics)
7. Evaluate expressions (fused into phase 6 in this implementation —
   evaluation happens inline as each statement executes, not as a fully
   separate pass)
8. Final validation (every exported field initialized)

**Phase 9 (export: C++, 6502 assembly, binary formats) is a separate
session's job, out of scope here.**

There are two other sessions this one coordinates with:

- **Project Lead** — owns the canonical spec. **The canonical spec now
  lives in this repo as `SPEC.md` (GDDL Specification v4) — that is the
  source of truth for spec questions, not this document, and not
  conversation memory.** `HANDOFF.md`'s "Confirmed spec rules" section
  below is a *summary with commentary*, useful for orientation, but if
  it ever disagrees with `SPEC.md`, `SPEC.md` wins — treat this section
  the same way a code comment describing a rule is secondary to the
  rule itself. Historically the spec only existed as things relayed
  through conversation with this session; that's no longer true as of
  `SPEC.md` being added, and this description used to say otherwise —
  which is exactly the kind of stale reference that caused the
  golden-baseline mixup earlier in this project, just for documentation
  instead of data. When in doubt, re-read `SPEC.md`, don't rely on this
  summary.
- **Test Corpus** — builds `.gddl` fixture batches (grouped into folders
  like `nested_field_semantics/`, `domains/`, `op_statements/`, etc.,
  each with a `MANIFEST.md`) and sends them here to run against the
  reference implementation. Each fixture has an "Expected" comment block
  — **that's a prediction derived from reading the spec, not golden
  truth**. This session's job is to report *actual* behavior, and
  explicitly flag any mismatch rather than deciding whether the fixture
  or the implementation is wrong — that gets sorted through the lead
  session.

## Core language recap

- **Identifiers** (`identifier X ... key = "description"`) are types
  ("domains"). Each entry's logical ID is a hash of its description text
  (see Logical IDs below). Identifier-typed fields are strictly bound to
  one domain.
- **`define`** blocks are layout only, never inherit. Composition (nesting
  one struct inside another) covers the need instead.
- **Instances** (`Name Instance = Source` or `Name Instance = Source
  delete`) copy all fields from `Source`, then execute the body's
  statements top-to-bottom against that copy, strictly in source order.
- **Nested Field Semantics** (the single most important rule, applies
  recursively at any depth):
  - `field = SourceInstance` → **full replace-then-modify**: discard
    whatever `field` currently holds, copy `SourceInstance` in, then
    execute any following statements against that copy.
  - Bare `field` (no `=`) → **modify-only**: enter `field`'s existing
    scope (or a blank instance of its type), touch only the sub-fields
    explicitly listed.
  - **No merge mode exists.** Never implement or infer merge behavior.
- **`delete`** templates may be incomplete, are never exported, but any
  non-`delete` instance copying from them must still fully resolve by
  export time.
- **Initialization**: no implicit defaults ever. Reading an uninitialized
  field is *always* a compile-time error — confirmed with no
  `delete`-instance carve-out (delete only tolerates fields that are
  *never assigned*, a phase-8 concern; it never relaxes read-validity).

## Drift check against SPEC.md (done once, on adding it to the repo; both findings below since resolved)

Read through the full canonical spec against the current implementation.
Two findings, both now resolved:

- **~~ID collision error message format doesn't match spec's exact
  wording~~ — FIXED.** `SPEC.md`'s Collision Detection subsection (under
  §4.1, just after §4.1.1) requires the error to name "both colliding
  qualified names (`Domain::description text` or `Type::InstanceName`)"
  — the exact string that gets hashed. `registry.py`'s qualified-name
  construction now uses `f"{node.name}::{entry.description}"` instead of
  the old `Domain.key` display format.
  **A second, real bug turned up while fixing this**, worth understanding:
  the collision check used to compare on the qualified-name *string*
  itself as a proxy for entry identity, which only worked by coincidence
  because the old `Domain.key` format was always unique per entry. The
  moment the display format changed to `Domain::description`, two
  entries that genuinely collide (same domain, identical description
  text, different keys) also produce *identical* qualified-name strings
  — so the old "are these the same entry" check silently stopped firing
  for exactly the case it exists to catch. Fixed by tracking a separate
  `(domain, key)` identity key in `self._id_table` alongside the display
  string, so identity and display are never conflated again. Verified
  with the same real (non-mocked) same-domain/same-description collision
  as before — now fires correctly with the spec's exact message format.
  Full 60-fixture regression: zero diffs, confirming this is still pure
  defensive infrastructure with no real-content impact.

- **~~SPEC.md numbering slip (§13 subsections labeled 14.1–14.5)~~ —
  FIXED on the lead session's end**, corrected spec re-synced into this
  repo.

Standing note, not a "finding" to resolve: **§13's C++ export design**
(type mapping, per-type registry, access patterns, scripting-manifest
approach) is preliminary, and nothing in phases 1–8 has been built
against it — phase 9/export is a separate session's scope entirely.
Keep this in mind so the "Confirmed spec rules" list below doesn't
silently drift out of sync with `SPEC.md` if/when export work starts
elsewhere and §13 gets revised further.

## Confirmed spec rules and additions (chronological, all resolved)

- **Assign/calculate unification**: `field = expr` and `field <op> expr`
  are not two mechanisms. Op-statement is just assign with "current
  value of field" implicitly prepended to the expression.
- **Cross-field expression references**: a bare or dotted identifier
  token inside an expression means "current value of that field, at this
  point in sequential execution" — same rule as self-modification,
  generalized. Dotted paths (`object.weight`) walk nested struct fields
  at any depth, current instance only. Dot syntax is shared with
  identifier-domain access (`ActionAttack.melee_weapon`); disambiguation
  checks whether the first segment is a struct-typed field on the
  current scope *first*, only falling back to identifier-domain lookup
  if it isn't a field at all.
- **Expression evaluation is strictly left-to-right (§6.3.1)** — no
  standard operator precedence table. Implemented as hand-rolled
  recursive descent, never Python's `eval()` (that silently reintroduces
  precedence). Op-statements pass the field's current value through as a
  **real Python number**, never stringified and re-tokenized — that
  string-splice-then-retokenize pattern was the root cause of three
  separate-looking bugs (precedence-via-eval, unary minus, scientific
  notation) before it was fixed structurally.
- **Collect-and-report error policy** (phase 6): don't halt the whole
  compile pass on first error. Each instance gets marked errored or
  blocked and everything not depending on it still compiles. Anything
  transitively depending on a failed instance gets exactly one
  "unresolvable: depends on X, which failed to compile" message
  pointing at the root cause — never a re-derived cascade.
- **Numeric type coercion (§5)**: widening (int→float) automatic at
  point of storage; narrowing with fractional loss is a compile-time
  error. u8/u32/f32/etc. are enforced, not cosmetic.
- **Numeric range enforcement (§5 extension)**: every numeric type has
  fixed two's-complement / finite-magnitude bounds. Out-of-range storage
  is always a compile-time error — never wrapped, clamped, or silently
  produced as inf/NaN. Checked only on the *final* coerced value at
  storage time, never on intermediate sub-expression values.
- **Warnings (§12.1)**: new diagnostic category, advisory only, never
  blocks any phase or export, same phase/location/message attribution as
  errors. Currently the only use: a bare struct-field entry with zero
  children (syntactically valid — enters scope, touches nothing — but
  usually unintentional, e.g. every statement under it got commented
  out). Scoped precisely: does NOT fire for an empty top-level instance
  body (ordinary pure copy).
- **Logical ID algorithm (§4.1.1)**: FNV-1a, 64-bit, over UTF-8 bytes of
  `"{DomainName}::{description}"` exactly as written, no normalization.
  Domain-qualified specifically to prevent cross-domain collisions on
  coincidentally-matching description text.
- **Instance stable IDs (§6.8)**: formalized in the spec for the C++
  export layer, but **not yet implemented** — phase 9 hasn't started.
  Nothing to do here until export work begins.
- **ID collision detection**: one shared table (`id → qualified name`)
  covering identifier logical IDs *and* future instance stable IDs
  together, not two pools. Checked at registration (phase 4,
  `check="id_collision"`). Pure defensive infrastructure — real content
  essentially never triggers it; verified with a real (non-mocked)
  collision using two same-domain entries with identical description
  text (key isn't part of the hash input, so this genuinely collides).
- **Circular instance-copy reference detection (§6.1 addition)**: moved
  from a runtime recursion guard to phase 4 (registration) — a
  dependency graph built from every `= Source` reference (including
  nested `field = Source` full-replaces at any depth), with ordinary
  cycle detection run on it before phase 6 ever starts. Names the exact
  cycle in the error rather than a generic recursion message. `check="circular_dependency"`.
- **String Literal Escaping (new spec section, this addition)**: exactly
  two escape sequences, `\"` -> `"` and `\\` -> `\`, processed
  left-to-right as atomic two-character units. Any other backslash
  usage (lone trailing `\`, or `\` followed by anything else) is a
  compile-time error. Length enforcement (§5) measures the value
  *after* unescaping, not the raw source span.

  **Two real bugs found and fixed while implementing this, not one:**
  - `_strip_quotes()` in `parser.py` (identifier descriptions) and a
    structurally identical, previously-unmentioned second site in
    `resolve.py` (`val = rhs[1:-1]`, the actual site producing every
    `string N` field's resolved value) both only ever stripped the
    outer quote pair -- neither unescaped anything. Fixed with one
    shared implementation, `_unescape_string_content()` in `parser.py`
    (a pure function, no line number or GDDL-error-class knowledge),
    imported by `resolve.py` and wrapped in each caller's own error
    type/phase (`GDDLParseError` at phase 3 for `_strip_quotes`,
    `GDDLResolveError(check="string_escape")` at phase 6 for field
    values) -- one source of truth instead of two copies that could
    drift.
  - **Separately, a real tokenizer bug**, found only because
    implementing `\\` required exercising the string-ends-in-a-
    backslash case the spec cites as `\\`'s own justification (a
    Windows-style path). Both quote-boundary-detection sites
    (`parser.py`'s preprocessor and `split_top_level_equals`) used a
    naive single-character lookback (`s[i-1] != "\\"`) to decide
    whether a `"` was escaped -- which cannot distinguish "one
    backslash before this quote" (escaped) from "two backslashes
    before this quote" (a *complete* `\\` pair, NOT escaped). A string
    legitimately ending in an escaped backslash immediately before its
    real closing quote (`"C:\\Users\\"`) was misdiagnosed as
    unterminated. Fixed with proper backslash-run PARITY counting
    (`_is_quote_escaped()`, `parser.py`) at both sites -- the standard
    resolution for this exact ambiguity, not a novel algorithm.
    Confirmed this was a genuine correction, not a misunderstanding: an
    instruction earlier in this same work asserted the boundary
    detection "was never the bug" as settled fact; direct testing
    against the real (unfixed) parser showed that assertion was false,
    which is why the fix happened at all rather than being accepted as
    out of scope.
  - One non-obvious consequence of the parity fix, golden-locked
    explicitly rather than left as a surprise: a **lone, unpaired**
    trailing backslash (`"abc\"`, not the paired `\\` case above) is
    *never* rejected by the new phase-6 `string_escape` check -- by the
    parity rule, an odd count before a `"` means that quote IS escaped,
    so the tokenizer correctly keeps scanning for a later real
    terminator, and (finding none) reports phase 3 "unterminated string
    literal" instead. Both are legitimate rejections the spec's "a lone
    `\` ... is rejected outright" language covers, just via two
    different mechanisms depending on exactly where in the literal the
    malformed backslash appears. See
    `corpus/string_fields/string_escape_lone_trailing_backslash.gddl`.

  Fixtures, all in `corpus/string_fields/`, all regenerated against the
  real reference implementation (not hand-derived) and confirmed to
  leave every one of the other 64 corpus fixtures byte-identical (none
  of them use a backslash at all, checked directly before this was
  judged safe):
  - `string_escaped_quote.gddl` -- renamed from
    `string_escaped_quote_current_behavior.gddl`; that name and its
    original comments described *confirmed-buggy* current behavior with
    an explicitly open design question, not a compliance test. Now an
    ordinary compliance fixture testing `\"` specifically, rewritten
    accordingly (old golden capture/expected value superseded, not a
    second value to reconcile).
  - `string_escaped_trailing_backslash.gddl` -- the real `\\` fixture,
    deliberately the trailing-backslash case (not a milder mid-string
    variant), since that's the one that actually exercises the parity
    fix and the one the spec cites as `\\`'s whole justification.
  - `string_escape_invalid_sequence.gddl` -- `\n` (a sequence that
    *would* mean something in many other languages) rejected outright,
    phase 6, `check="string_escape"`.
  - `string_escape_lone_trailing_backslash.gddl` -- not originally
    requested, added because the parity fix's consequence above was
    worth golden-locking rather than only describing in prose. Whole-
    file phase-3 parse error, not a per-instance result.

## Corpus lock-completeness check (`export_golden.py`)

Added after a real gap sat undetected for most of this thread: two
`.gddl` fixtures (`circular_references/circular_reference_direct_two_instance.gddl`,
`domains/domain_logical_id_collision_error.gddl`) had no `.golden.json`
at all, absent even from `GOLDEN_STATUS.md`'s own totals -- and
`golden_output.json`'s regression (which every session in this thread
has actually run before packaging) is structurally blind to this: it
checks whether each `.gddl` compiles to the expected structured output,
a completely different property from "does a lock exist at all." Lock
completeness had nothing watching it, in either sense -- not a
divergence-detection gap (something imperfect that eventually notices),
but an absence of any check at all.

`check_lock_completeness()`, called from `export_golden.py`'s `main()`
right after `golden_output.json` is written (never gating that write --
the golden output is useful on its own even when lock coverage isn't
complete). Scope, deliberately narrow:
  - Existence only. A `.gddl` with no sibling `.golden.json` at all is
    a hard failure (non-zero exit, exact filenames printed -- not a
    count, since a count doesn't tell anyone what to go fix).
  - A `.golden.json` that exists with `capture_status: "pending"` (the
    `numeric_range/` stubs, tracked and legitimate) is NOT flagged.
    Flagging it would train people to ignore this check the first time
    it cries wolf over something that's actually fine.
  - Proven to actually fail, not just reviewed as correct-looking:
    deliberately deleted one lock (confirmed non-zero exit + the right
    filename), then two at once (confirmed both listed, sorted), then
    restored both and confirmed a byte-identical restore plus a clean
    pass. Same standard as everything else in this project -- prove it
    by breaking it on purpose.
  - Sent to Test Corpus as a standalone, dependency-free script
    (`check_lock_completeness_for_test_corpus.py` at delivery time --
    Test Corpus may rename/relocate it into their own tooling) for
    parity, since this exact gap could open in either direction.

**What this deliberately does NOT solve**: this only verifies ONE copy
of `corpus/` against itself. It cannot detect this copy and Test
Corpus's copy diverging in some OTHER way -- e.g. both having a lock
for the same fixture, but with different captured content -- since no
single-sandbox script can hold both copies at once to compare them.
That is a cross-copy consistency problem, not a completeness problem,
and remains something no automated check in either sandbox covers.
Test Corpus has taken this on as a standing part of their own role:
diffing whatever corpus bundle passes through their session against
whichever copy they last verified, rather than a substitute for either
side keeping its own copy honest.

## RESOLVED: `--emit-all-domains` flag, all four export targets (§8.5 / §14.7)

One shared flag name, two genuinely different mechanisms, explicitly
not described as one uniform feature:

**Background:** a developer may want a domain's compact constants
available for hand-written dispatch code (a 6502 jump table, a 68000
C function-pointer table, C++ indexed dispatch) without GDDL ever
storing a value from that domain in any compiled struct. Before this
flag, all four exporters silently dropped unreferenced width-declared
domains. Confirmed directly against each exporter's code and a real
fixture (`Rarity u8` with zero field references and `Item` as the
exported type): `gather_domain_info()` on all three non-C++ targets
had a `if domain not in used: continue` guard that bypassed any such
domain entirely. On C++, the primary `Rarity` logical-ID enum was
always emitted (every domain unconditionally), but the `_Indexed`
companion (`Rarity_Indexed : uint8_t`) was gated on `@Rarity`-typed
field usage — the same underlying gap, genuinely different code path.

**The C++ / non-C++ distinction is real and matters:**
  - On **C++**: a referenced domain already always gets its default
    `enum class Domain : uint64_t`; only the `_Indexed` companion is
    missing when unused. `--emit-all-domains` force-emits the companion
    for every width-declared domain. (`generate_header()` and
    `generate_split()`, the companion gate in both.)
  - On **6502, Z80, 68000**: `Domain` and `@Domain` are
    indistinguishable — there is only one representation. The entire
    domain entry (member constants, jump table on 6502, dispatch on
    6502) was absent. `--emit-all-domains` bypasses the
    `gather_domain_info()` skip guard in all three, producing the same
    constant-table form a referenced domain already gets. (`gather_ir()`
    in all three, which passes through `emit_all_domains` to
    `gather_domain_info()`.)

**Flag name and shape:** `--emit-all-domains`, `action="store_true"`,
default off. Consistent across 6502 and Z80 CLIs (68000 has no
standalone CLI, API-only, threaded through `gather_ir()`). A domain
with no declared width is unaffected either way on every target -- the
flag is about force-emitting, not force-creating.

**Real toolchain validation, all four targets, both flag values:**
  - **6502 (ACME, 64tass, KickAssembler)**: generated output with flag
    ON assembled; harnesses loaded `Rarity_common=0`, `Rarity_rare=1`,
    `Rarity_epic=2` via py65 execution, not just visual inspection.
    Stub handlers provided for the jump-table addresses the generated
    Dispatch subroutine references (the domain is emitted in exactly
    the form a referenced domain already produces, jump table and all).
  - **Z80 (SjASMPlus)**: same check via the z80 PyPI emulator.
  - **68000**: compiled with real vbcc (+aos68k), ran under vamos.
    `sizeof(Rarity)==1` confirmed (u8 width maps to `unsigned char`).
  - **C++ (--force-single-header / split)**: `static_assert` checks at
    compile time that `Rarity_Indexed::common==0`, `::rare==1`,
    `::epic==2`, `sizeof(Rarity_Indexed)==1`. Flag-OFF header confirmed
    to compile cleanly (the primary `Rarity` enum exists; referencing
    `Rarity_Indexed` in a separate compile produces the expected missing-
    type error, confirming absence is genuine). Real `g++17` compile and
    run.
  - 68 fixture corpus regression: **0 diffs**, lock-completeness check
    passing throughout.

Assets: `export_emit_all_domains_test/` -- one shared fixture
(`emit_all_domains_minimal.gddl`), generated output for all targets in
both flag modes, harnesses, and test programs. Single fixture serves
all four targets: the gap under test is in the exporter-layer decision,
not in any language feature, so one `.gddl` file with one unreferenced
width-declared domain is all that's needed.

## New export target: §17 standalone binary format (`export_binary.py`)

First implementation pass, exactly as scoped: the core mechanism
solid and genuinely verified, not full coverage of every field-width
combination. §17.5 (the C++ compile-time header table) is
**explicitly out of scope for this pass** -- it belongs in
`export_cpp.py`, wasn't touched, and isn't implied as done by anything
below.

**Infrastructure reused, not reimplemented:**
- `registry.fnv1a_64(bytes) -> int`: a new raw primitive, extracted
  FROM `registry.logical_id` (which previously had the FNV loop
  inlined) specifically so this module could share the exact same
  implementation rather than write a second one. Verified
  byte-for-byte identical to pre-refactor behavior before anything was
  built on top of it (`logical_id('ActionAttack', '...')` still
  produces `5c96a731d7d47e03`, the same value seen throughout this
  project's C++ output), and the full 68-fixture regression stayed
  clean after the refactor landed, before any binary-export code
  existed at all.
- `export_cpp._flatten_leaves` / `_flatten_value` / `_string_n` /
  `export_instances_for_type`: reused directly, unmodified.
- **Deliberately NOT reused**: `export_z80.py`'s `_leaf_size_bytes`,
  which sizes every identifier-typed field by its domain's indexed
  width unconditionally -- correct for Z80 (no logical-ID form exists
  there at all) but wrong for this target, where §17.3 requires a
  plain `Domain` field to be the full 8-byte logical ID and only
  `@Domain` to use the domain's declared width. Modeled on
  `export_cpp._cpp_field_type`'s own `@`-vs-plain distinction instead,
  which already gets this right.

**Binary format**: fully specified in `export_binary.py`'s own module
docstring, written to be reproducible byte-for-byte by a future
independent implementation without needing to read the writer code at
all (§17.6's stated ongoing-correctness concern). Magic `b"GDBD"`,
format_version 1, little-endian throughout, per-type table
self-describing without the manifest (name/hash/size/offsets all in
the `.bin` itself, per §17.4's "pure binary-to-binary comparison" load
check), record arrays then lookup tables, `(stable_id: u64,
dense_index: u32)` pairs sorted by ID.

**One known simplification, flagged rather than silently assumed**:
`lookup_table_count` is always > 0 in this implementation. Every
instance has a stable ID (§6.8) unconditionally, so the
spec-permitted "zero/absent" case for a type not using logical-ID
lookup never actually arises here -- not tested, since there's no way
to construct it from current language semantics.

**schema_hash canonical serialization**, precisely defined (both in
the module docstring and in `canonical_schema_string()`, which must
never drift from that docstring): for each flattened leaf, in
`_flatten_leaves` order, `"{path}\x1f{type.strip()}"`, joined with
`\x1e` between leaves. `\x1f`/`\x1e` chosen specifically because no
GDDL identifier or type token can ever contain them, making the join
unambiguous by construction, not by convention.

**Test fixture**: confirmed an existing fixture already had full
coverage before building anything new, per the task's own explicit
instruction -- `export_cpp_test/export_test_indexed.gddl` (composition
via `Item` nesting `Object`, scalar `u32`, `string 16`, plain-domain
identifier, `@Domain` indexed identifier, all in one type) copied to
`export_binary_test/export_test_binary_coverage.gddl` with a
provenance note, same duplication convention already established for
`composition_nested_u16_fields.gddl` across four other target
directories.

**Validation, three genuinely separate checks** (`export_binary_test/test_binary_export.py`):
1. **Independent read-back**: `independent_reader.py`, a from-scratch
   reader built directly from the format docstring, sharing zero code
   with the writer -- deliberately, since a reader built from the same
   code that wrote the file would only confirm the writer agrees with
   itself. Every field of every instance of both exported types
   (`Item`, `Object`) checked against ground truth pulled directly
   from `resolver.cache`, not hand-derived. String fields checked
   character-by-character (`AAAAAAAAAAAAAAA`, 15 bytes, exact fit in
   `string 16`).
2. **Manifest truthfulness**: every offset and size the JSON claims is
   followed and confirmed against the `.bin`'s own per-type table and
   real file bounds -- record arrays and lookup tables both confirmed
   in-bounds, field byte offsets confirmed to tile `record_size`
   exactly with no gap or overlap, not merely present in the JSON.
3. **Schema-change discrimination**: `Item`'s `weight`/`element`
   fields reordered (an isolated, single-line change), confirmed
   `schema_hash` actually changes (`2c99385395d2d57e` ->
   `3440ec2db9e1f404`) while `record_size` does NOT (37 == 37 both
   times, same fields, same widths, just reordered) -- exactly
   demonstrating §17.4's own stated reasoning for needing both values:
   `record_size` alone would have silently accepted the reordered file
   as compatible. Also confirmed the untouched `Object` type's
   `schema_hash` is completely unaffected, proving per-type hashing
   rather than a whole-project fingerprint.

68-fixture corpus regression: unaffected (this fixture lives in
`export_binary_test/`, not `corpus/`, correctly -- its language-level
semantics are already covered by the original
`export_test_indexed.gddl` and by whatever corpus fixtures already
test delete-templates/bare-modify separately; duplicating it into
`corpus/` too would test nothing new). Lock-completeness check passing
throughout.

## §17.5: C++ compile-time schema table (`(type_name, schema_hash, record_size)`)

The one requirement that mattered most here, taken from the spec text
itself: this table must be generated by the SAME code path that
computes `schema_hash`/`record_size` for `.gddldata.bin`, never a
second implementation in `export_cpp.py` that happens to agree.

**A real refactor was needed to make that true, done with the same
byte-identical-before-and-after discipline as the `fnv1a_64` extraction
last round:**

`export_binary.py` already imports composition-flattening from
`export_cpp.py`. Having `export_cpp.py` import the hash/size functions
back FROM `export_binary.py` would create a genuine circular import
(`export_cpp -> export_binary -> export_cpp`), not just an awkward one
-- so `_leaf_binary_kind`, `leaf_binary_width`, `canonical_schema_string`,
`compute_schema_hash`, `compute_record_size`, and the exception class
(renamed `SchemaComputationError`, with `export_binary.ExportBinaryError`
kept as a subclass for backward compatibility) moved INTO
`export_cpp.py` instead -- the same direction the dependency already
ran, adding nothing new. `export_binary.py` now imports these back
from `export_cpp.py` alongside its existing imports, rather than
defining a second copy.

**Verified byte-identical before and after the move**, not assumed
correct because it compiled: regenerated `export_binary_test/`'s
existing `.gddldata.bin`/`.gddlmeta.json` output post-refactor and
diffed against the pre-refactor committed files -- `.bin` byte-for-byte
identical; `.json` identical once the (expected, filename-only)
output-stem difference was controlled for. Both binary-export test
suites re-run clean with the exact same hash/size values as before
(`Item: 2c99385395d2d57e/37`, `Object: c3b65b8d9dc943b8/8`,
reorder-discrimination hash `3440ec2db9e1f404`).

**Output**: `render_schema_table(reg)` in `export_cpp.py`, called from
both `generate_header` (single-header mode) and `generate_split`
(header only -- no `.cpp` counterpart, same convention as domain enums
and other small compile-time metadata that stays header-resident
regardless of split mode; no ODR reason to split eight bytes and a
name per type into a separate translation unit). Emits a
`SchemaEntry{ type_name, schema_hash, record_size }` struct and an
`inline constexpr std::array<SchemaEntry, N> SchemaTable`, one entry
per type in `_topo_sort_defines`' order (every type in the schema, the
same ordering every other part of this exporter already uses).

**Validation** (`export_binary_test/test_schema_table_cpp.py`), the
actual proof the "never drift apart by construction" claim is true,
not just structurally plausible:
- Parsed the `(type_name, schema_hash, record_size)` triples directly
  out of the GENERATED C++ SOURCE TEXT (regex over the emitted
  `SchemaEntry{...}` lines) -- not re-derived from the IR, an honest
  reading of what was actually emitted.
- Compared, programmatically, against `export_binary.py`'s own
  `.gddlmeta.json` for the same fixture and the same types (`Item`,
  `Object`) -- exact match, both hash and size, for both.
- Confirmed single-header and split modes produce identical table
  values as each other (both call `render_schema_table` the same way
  -- a sanity check on that claim, not a separate independence proof).
- Real `g++17` compile AND execution of both modes' emitted headers,
  iterating `SchemaTable` and printing every entry -- confirmed valid,
  well-formed C++, not just text that happens to look right.

Same fixture as the binary exporter's own first pass
(`export_test_binary_coverage.gddl`) -- no new fixture needed, per the
task's own instruction.

68-fixture corpus regression: unaffected, 0 diffs, lock-completeness
passing throughout.

## §18 Multi-File Compilation (`gddl/combine.py`)

One shared module, not per-exporter logic, exactly as scoped. Three
responsibilities: `resolve_inputs()` (CLI args -> ordered real files,
§18.4/§18.5), `combine_sources()` (concatenate + record per-file line
offsets, §18.2), `compile_multi()` (run the existing, UNMODIFIED
pipeline against the combined text, then remap every line number back
to (source file, original line) -- the one piece of new logic touching
the pipeline's output).

**Confirmed empirically before building anything, not assumed from the
spec's prose**: forward references across concatenated text (a direct
test: instance placed before its own `define` in combined text still
resolves correctly), Python `glob`'s `**`-vs-`*` distinction under
`recursive=True` (a non-`**` pattern does NOT recurse just because the
flag is set), and the 1-based line-numbering convention every existing
error already uses (tested against a cleanly-attributed duplicate-key
error, not the unterminated-string case, which has its own known
off-by-one-from-EOF quirk unrelated to this work -- caught the
difference by testing both, not assuming they behave the same).

**A small, purely-additive change to `parser.GDDLParseError`**: it now
also stores `raw_message` (the message body, without the "line N: "
prefix baked into `str(e)`/`e.args[0]` at construction time) --
`CompileError`/`CompileWarning` compute their string form fresh on
every call from a mutable `.line`, so remapping just needs to read
`.message` (already the raw body) and `.line`; `GDDLParseError` had no
such raw form to read before this. Verified byte-identical for the one
existing caller (`export_golden.py`) before building on top of it, and
the full 72-fixture regression stayed clean after this change alone,
before any of `combine.py` existed.

**A real argparse ambiguity found and solved, not worked around**:
`source` becoming `nargs="+"` alongside the existing `types`
positional (also `nargs="+"`) is genuinely ambiguous -- confirmed
directly with a minimal repro that argparse doesn't error on this, it
silently MISPARSES which arguments belong to which list. Solved by
converting `types` to a required, repeatable `--type` option
(`action="append"`) across the three exporters that have it
(`export_z80.py`, `export_6502.py`, `export_binary.py`;
`export_cpp.py` never had a `types` positional at all -- it exports
every type in the schema automatically, so `source` alone becoming
variadic there has no ambiguity to resolve).

**This is a real CLI syntax change, flagged explicitly rather than
implied as purely additive**: `export_z80.py file.gddl Creature Item`
becomes `export_z80.py file.gddl --type Creature --type Item`. Checked
before making this change that nothing committed in this repo invokes
these CLIs via subprocess (every test harness calls the underlying
Python functions directly, bypassing `_cli()`/argparse entirely) and
that no HANDOFF.md prose documents the old positional syntax as a copy-
pasteable example -- so nothing here is left broken, but anyone with an
external script calling the old `--type`-less form will need to update
it. `-o`/`--output` behavior is unchanged (§18.6), confirmed by testing
single-file invocation through every exporter, not just re-reading the
code.

**Deliberate, considered design choices, stated rather than left
implicit**:
- Glob matches across multiple patterns are deduplicated (first sorted
  occurrence kept); a glob match coinciding with a literal-argument
  file is dropped from the glob group (the literal's position wins).
  Neither is pinned down by §18's spec text; both are the obvious
  reading of "compiling the same file twice would be wrong."
- The CLI does NOT surface `duplicate_errors`/warnings to the user
  beyond what the existing single-file CLIs already did (nothing) --
  compilation proceeds and exports whatever resolved, silently, exactly
  matching pre-§18 single-file behavior for an in-file duplicate. Not
  an oversight: checked what existing single-file CLIs do today (none
  of them check `resolver.reg.duplicate_errors` at all) before deciding
  not to introduce new blocking behavior multi-file didn't ask for.
  Worth a real follow-up question for whoever owns future CLI polish --
  a multi-file collision is arguably more surprising to a user than an
  in-file one, and a stderr warning would be cheap -- but that's a
  scope decision for someone to make deliberately, not something to
  fold in unasked here.

**Fixture**: 5 files under `tests/multi_file_test/` (`weapons/`,
`domains/`, `defs/`), CLI combination order deliberately chosen so
every required reference direction is exercised: `Sword`
(`weapons/base_weapon.weapon`, a non-.gddl extension) forward-
references `Weapon` (`defs/weapon_type.gddl`) and `Element.fire`
(`domains/elements.gddl`), both declared LATER in combination order;
`Bow` (`weapons/more_weapons.gddl`) backward-references both, declared
EARLIER. `weapons/duplicate.weapon` is the deliberate collision --
redeclares `Sword`.

Exact combined-text line arithmetic computed BY HAND from each file's
real line count before ever running anything, then confirmed to match
exactly: colliding declaration at `duplicate.weapon:13`, original at
`base_weapon.weapon:17`. Both independently verifiable -- the colliding
one from the `duplicate_name` error's own remapped location, the
original from `resolver.reg.instances['Sword'].line` remapped the same
way -- not just "somewhere in the combined text."

**A real bug found in the TEST's own verification logic, not in
`combine.py`**: the first version of `test_multi_file.py` searched for
the string `"Weapon Sword"` as a substring across every line to locate
the predicted declaration line -- but `duplicate.weapon`'s own header
comment ALSO contains that exact phrase (`// Declares "Weapon Sword"
again...`), so the naive search matched the COMMENT (line 3) instead of
the real declaration (line 13). `combine.py`'s actual remapping was
already correct (line 13, confirmed independently before the test
script existed) -- this was purely a bug in how the test computed its
OWN prediction. Fixed by requiring the match to be an unindented line
start (`line.startswith("Weapon Sword")`), confirmed against real file
content that declarations and comments are structurally distinguishable
this way. Caught by running the test and getting a clear, specific
failure, not by re-reading the search logic and deciding it looked
right.

**Validation, matching every point in the task's own requirements**:
- `test_multi_file.py` (5 checks): forward/backward references in both
  directions for both defines and identifiers; the collision's
  dual-location attribution, both locations independently verified
  against hand-computed predictions; the zero-match error path, both
  forms (nonexistent literal, zero-match pattern); shell-independence,
  proven two ways -- a `subprocess.run()` list-argv call with NO
  `shell=True` at all (the OS execs python3 directly; if this succeeds,
  only the program could have expanded the pattern, since no shell was
  ever in the call chain to have done it) AND a real `bash -c`
  invocation with the pattern single-quoted so bash genuinely cannot
  expand it even though a real shell is present -- simulating the
  actual Windows cmd.exe/PowerShell case this requirement exists for;
  and the non-.gddl-extension claim, both as a literal path and via an
  extension-specific glob pattern.
- `test_multi_file_z80_harness.asm` / `test_multi_file_z80_run.py`:
  the 4-file clean fixture (no collision) compiled through the real
  `export_z80.py` CLI, assembled with real SjASMPlus, executed on the
  real z80 emulator -- both instances' both fields, accessed through
  the real `Weapon_Find` subroutine, confirmed correct. Reuses the
  existing `z80_test_helper.py` rather than reimplementing symbol
  loading a second time.
- Single-file invocation re-confirmed through all four exporters after
  the CLI changes, using already-existing fixtures, not just the new
  multi-file ones -- correct output in every case.
- 72-fixture corpus regression: unaffected, 0 diffs, lock-completeness
  passing throughout (`multi_file_test/`'s own `.gddl`/`.weapon` files
  correctly stay out of `corpus/`, confirmed by the fixture count not
  moving).

## 68000 subset-request bug fix, and `export_68000.py`'s new CLI

Two pieces, done in dependency order (the CLI's own validation reuses
the bug-fix fixture, so the fix had to land first).

### The bug

Found during independent verification, confirmed with a direct repro
before touching anything: `render_c89_split`'s AoS struct-emission used
`define_order = _topo_sort_defines(reg)` -- every define in the WHOLE
registry, not just what's reachable from the requested `type_names`.
Requesting every type in a file together worked fine (nothing to
over-include); requesting a genuine subset (e.g. just `Item` from a
file that also defines an unrelated `Creature`) failed outright -- it
still tried to emit `Creature`'s struct too, and crashed because
`Creature`'s own domain (`CreatureKind`) was never gathered for the
request in the first place. Gathering (`gather_ir`) was already
correctly scoped to the request; only this struct-order computation
wasn't. The comment sitting right above the bug said "this pass
doesn't need a reachability prune" -- it did.

**Checked every other exporter for the same class of bug before fixing
anything, per the explicit instruction not to assume**, using the same
subset-request repro against each:
  - **C++**: structurally impossible. `generate_header`/`generate_split`
    take no `type_names` parameter at all -- there is no subset-request
    concept; everything in the schema is always exported. Confirmed by
    reading the actual function signatures, not inferred.
  - **6502, Z80, binary exporter**: all three correctly isolate a
    requested subset, confirmed with the identical repro against each
    (adjusted only for field-width support -- the first attempt used
    `u32`, which 6502/Z80 don't support at all regardless of this bug;
    caught the confound and re-ran with `u16` before concluding
    anything).
  - **68000's own SoA branch**: NOT affected -- confirmed empirically
    (ran the repro under `layout="soa"`), not just by reading that it
    iterates `types` (already correctly scoped by `gather_ir`) rather
    than `define_order`.

**Fix**: `_topo_sort_defines` (in `export_cpp.py`, shared by both
targets) gained an optional `roots=None` parameter. `roots=None`
(unchanged default) preserves every EXISTING caller's behavior exactly
-- C++'s header/split generation and §17.5's schema table both
deliberately want "every type in the schema," and neither was touched.
`export_68000.py`'s call site now passes
`roots=[t.name for t in types]`, pulling in exactly {requested types}
union {everything they transitively compose} -- confirmed both halves
independently: a transitively-composed dependency (`Item` composing
`Object`) is still correctly included, and the unrelated `Creature`
never leaks in. Verified `roots=None` is byte-identical to the
pre-change behavior before building anything on top of it, and that
the existing, previously-validated `composition_nested_u16_fields.gddl`
68000 output is byte-identical after the fix (the "request everything
together" case, which the bug never affected, confirmed genuinely
unaffected by the fix too).

**Permanent fixture**: `export_68000_test/subset_request_bug.gddl` --
deliberately exercises both halves of the fix in one file, not just
the task's minimum "two independent types": `Item` composes `Object`
(must be included, transitively required) while `Creature`/
`CreatureKind` share no dependency with `Item` at all (must never leak
in). One real snag caught along the way: the first draft used invalid
inline-struct syntax (`object = { weight = 5 }`) -- caught by checking
the actual `compile_report` output rather than assuming the fixture
was fine, fixed to the real bare-field-block syntax already established
elsewhere in this project's fixtures.

Real toolchain validation: `test_68000_subset_request_bug.c` +
`run_subset_request_bug_test.sh`, real `vbcc` compile, real `vamos`
execution, confirmed working from a clean rebuild via the committed
script (not just the first ad hoc run). Notably, for this specific
bug, successfully COMPILING the generated output at all is real
evidence the fix works, not a formality -- before the fix, requesting
just `Item` crashed the exporter itself before any C file was even
written.

### The new CLI

Matches the other four exporters' shape exactly: `--type` (required,
repeatable, `action="append"`) rather than a second positional list --
same argparse ambiguity §18's own work already found and solved
(confirmed directly: a bare second `nargs="+"` alongside a variadic
`source` silently MISPARSES which arguments belong to which list,
rather than erroring). Multi-file input via `combine.py`, unmodified.
`-o`/`--output` writes `<stem>.h`/`<stem>.c` -- this target's only mode
(`render_c89_split` always produces a header/.c pair, never a single
file), same convention as C++'s split mode adapted to C89's own
extensions. `-h`/`--help` came free from `argparse` the moment a real
`ArgumentParser` existed, confirmed by actually running `--help` and
checking every flag has real, substantive help text (not a
placeholder) -- matched against the other four exporters' existing
quality bar.

Found one real bug before running anything, by checking rather than
assuming: the CLI used `os.path.basename()` but `export_68000.py`
never imports `os` anywhere in the file -- caught by grepping for the
import, not by hitting a crash first. Fixed by adding the import
locally in `_cli()`.

**Validated through the REAL CLI throughout** (`argparse`, real
subprocess invocation) -- not just the underlying `gather_ir`/
`render_c89_split` function calls piece 1 already exercised directly,
since that distinction is exactly what caught a real gap on §18's own
work and applies here too:
  - Single-file invocation: correct output.
  - Multi-file invocation (the §18 fixture, all four files, both
    forward and backward references): correct output.
  - **The subset-request bug fix, re-confirmed through the CLI
    specifically, not just the direct-function-call testing from piece
    1** -- requesting only `Item` succeeds, `Object` correctly
    included, `Creature` correctly absent.
  - Every error path: missing `--type`, nonexistent literal file,
    zero-match glob pattern -- all three correctly rejected with clear
    messages, matching the other exporters' error shape exactly.
  - Shell-independence: a `subprocess.run()` list-argv call with no
    shell anywhere in the chain, confirming the glob pattern was
    expanded by the program itself.

One more self-caught bug during this validation: the first version of
the `--help` content check compared raw substrings against
`result.stdout`, but `argparse` wraps help text across lines at its
own discretion -- "repeat for multiple types" was split across two
lines in the real output, failing a naive substring check that had
nothing wrong with the actual CLI content. Fixed by normalizing
whitespace before comparing, caught by running the check and getting a
specific, honest failure rather than trusting the check on inspection.

Permanent test suite: `export_68000_test/test_68000_cli.py`, all six
checks above, run directly as a real subprocess against the actual
`export_68000.py` file every time -- not a mock, not a direct function
call standing in for CLI behavior.

**Regression**: 72-fixture corpus, 0 diffs, lock-completeness passing
throughout both pieces.

## Known open questions

- **Lock staleness is a third, distinct property from both completeness
  and cross-copy consistency, and nothing checks it.** The
  lock-completeness check above (`check_lock_completeness()` in
  `export_golden.py`) verifies a `.golden.json` *exists* next to each
  `.gddl`; it says nothing about whether that lock is still *current*
  relative to its own source file. A `.gddl` fixture edited without its
  paired `.golden.json` being regenerated would pass the completeness
  check cleanly (the lock exists) while silently no longer matching
  what the reference implementation actually produces for that source
  today. This is not the same gap as completeness (does a lock exist at
  all) or cross-copy consistency (do two independent copies of the
  corpus agree with each other) — a lock can be complete, and two
  copies can agree with each other, and both can still be wrong
  relative to the current `.gddl` content. Not solved here, deliberately
  — flagged so it isn't mistaken for covered by the completeness check
  just because both are about "is corpus/ in a good state." A real fix
  would need some way to detect that a `.gddl`'s content changed since
  its lock was captured (a content hash of the source stored alongside
  `captured_at` in the `.golden.json` itself would be the obvious
  mechanism, checked against the live file on each `export_golden.py`
  run) — not implemented, not decided, just named as the next thing in
  this same family of gaps if anyone picks it up.

Both prior entries here are now resolved:

- ~~Whether circular instance-copy references are caught at the "right"
  phase~~ — **resolved and implemented.** Spec §6.1 now states circular
  copy references are a compile-time error detected at registration
  (phase 4), not a runtime recursion guard. Implemented in
  `registry.py::Registry._detect_circular_dependencies`: builds a
  dependency graph from every `= Source` reference (top-level AND
  nested `field = Source` full-replace, at any depth) once registration
  completes, runs ordinary DFS-based cycle detection, and names the
  exact cycle in the error (e.g. `A -> B -> C -> A`) rather than a
  generic recursion-depth message. Every participant in a cycle gets its
  own `phase 4, check="circular_dependency"` error with the same
  cycle-naming message (a cycle has no single well-defined root cause
  instance the way a linear dependency failure does). The old runtime
  recursion guard in `resolve.py::Resolver.resolve_instance` is kept as
  a defensive backstop, not removed — confirmed it's now provably
  unreachable in practice (verified the dependency-graph walk exactly
  mirrors both call sites in the codebase that ever recursively resolve
  another instance), but kept in case a future call site gets added
  without updating the graph walk to match, same pattern as phase 5's
  checks staying as backstops in phase 6.
- ~~Constructing a fixture that triggers ID collision via genuinely
  different domains/descriptions~~ — **resolved: no mocking needed.**
  The same-domain/different-keys/identical-description-text technique
  already used to verify the check (see Confirmed spec rules below) is
  itself a completely legitimate, deterministic corpus fixture, not just
  an internal test — it exercises the real detection path with
  certainty, since the key isn't part of the hash input (§4.1.1). Test
  Corpus is building against this; nothing further needed here.

## Process conventions

- When Test Corpus sends a batch: run every fixture through the real
  pipeline, report *actual* output (resolved values or exact error
  state), and explicitly flag anything that diverges from the fixture's
  "Expected" block — don't silently reconcile either direction.
- Root-cause every bug precisely before reporting it, even if only
  tangentially related to the task at hand. Don't fix something without
  saying so; don't say something's fixed without a regression sweep.
- After any fix: full regression sweep (diff full `golden_output.json`
  before/after) before considering it done. A clean diff except for the
  intended change is the bar, not "the specific fixture I was asked
  about passes."
- **A local `golden_output.json` snapshot is not automatically
  authoritative.** During the post-reset rebuild, the local copy that
  survived was compared against as if it were ground truth, and 2
  fixtures were "fixed" to match it. Test Corpus's actual current
  corpus already had the correct values, dated from before the reset —
  the local copy was simply stale, not the other way around. The fix
  landed on the right value regardless (both sides agree now), but the
  local snapshot should never be assumed current after any gap in
  session continuity (a reset, a long pause, anything). **Next time a
  rebuild-and-verify pass happens, check with Test Corpus for their
  current golden data as the comparison baseline first**, rather than
  diffing solely against whatever local copy happens to still exist.
- `golden_output.json` is the single canonical output file — new batches
  get merged into it (`_meta.batches` records provenance/notes), not
  written to separate files, except for small single-fixture "resync"
  deltas when only confirming one correction.
- Fixture keys in `golden_output.json` are `group_folder/fixture.gddl`,
  matching the corpus directory structure — not whatever wrapper folder
  name a delivery zip happened to use.

## Current state / how to resume

- **Repository status, as of the 2026-08-04 restructuring (this
  replaces the speculative version of this paragraph that stood here
  briefly during the restructuring itself, while the shared-repo
  question below was still open):**
- This is a real, single git repository (initialized during the
  restructuring — no prior git history existed anywhere in any prior
  sandbox copy of this project; that gap is recorded, not silently
  smoothed over, in the restructuring commit itself). Check `git log`
  for the actual commit history from that point forward.
- **Public repository.** Decided, not assumed: the project's own
  internal development history — everything in this file, written
  across many sessions in the voice this file has always used —
  becomes publicly visible as part of that decision, since GitHub has
  no per-branch visibility and a public `dev` branch necessarily means
  the whole repository, `main` included. `main`'s protection was never
  about secrecy — no AI session has ever held credentials to it — so
  visibility doesn't change that protection at all. Given this, a
  deliberate sensitivity pass was done on this file specifically
  before that visibility went into effect: no credentials, API keys,
  tokens, private key material, or real people's contact information
  anywhere in it (checked directly, not assumed absent). The
  `/home/claude/...` and `/mnt/user-data/...` path fragments
  throughout are sandbox filesystem artifacts from the AI coding
  sessions that built this project, not secrets — consistent with
  this file's already-established transparent voice about its own
  development process, which the public-visibility decision doesn't
  change the reasoning for.
- To regenerate golden output: `python3 export_golden.py` from
  `compiler-python/tests/` (writes `golden_output.json` alongside it,
  imports the pipeline from the sibling `compiler-python/gddl/`
  directory). Confirmed correct by actually running it from that
  location, not just edited by inspection.
- `compiler-python/tests/corpus/` currently has 72 fixtures. As of the
  last verified sweep, the implementation reproduces the canonical
  `golden_output.json` with zero unexplained diffs, and the
  lock-completeness check (`check_lock_completeness()` in
  `export_golden.py`) confirms every fixture has a matching
  `.golden.json`.

### 6502 real-toolchain validation setup

Every 6502 exporter change in this project has been validated by
actually assembling with a real cross-assembler and executing the
result in an emulator, not just visual review. Three dialects are
targeted (§10.3: ACME, 64tass, KickAssembler). After a sandbox reset,
none of this is present by default — here's how to get back to a
working state:

- **ACME**: `apt-get install acme` (Ubuntu universe repo).
- **64tass**: `apt-get install 64tass` (also Ubuntu universe). Note:
  this sandbox image strips `/usr/share/doc/*` and `/usr/share/man/*`
  (dpkg path-exclude, a minimized-image thing), so the bundled
  README/man page won't actually be on disk despite `dpkg -L` listing
  them. The real reference manual is at
  https://tass64.sourceforge.net/ (fetched directly from there when
  building the renderer, since the packaged docs weren't available).
- **py65** (pure-Python 6502/65C02 emulator, used to actually execute
  assembled binaries): `pip install py65 --break-system-packages`.
- **KickAssembler**: not packaged anywhere, not open source, and its
  official host (`theweb.dk`) is blocked by this sandbox's network
  egress proxy — there is no way to fetch it fresh after a reset. The
  user uploaded a working copy directly (`KickAss.jar` + `KickAss.cfg`,
  v5.25), which is preserved at
  `/mnt/user-data/outputs/tools/kickassembler/` specifically so it
  survives resets without needing to ask the user to re-upload it.
  Deliberately NOT committed into this git repo's history — it's
  third-party proprietary freeware, not project source, same
  reasoning as not committing compiled test binaries — but it does
  need to be copied back into a working location (e.g.
  `/home/claude/work/gddl-compiler-core/compiler-python/tools/kickassembler/ (path convention as of the 2026-08-04 restructuring; adjust if your own working root differs)`) after a reset, since
  `/home/claude` itself doesn't persist. Run via
  `java -jar /path/to/KickAss.jar <file.asm> -o out.prg`.

### RESOLVED (all 3 dialects real-toolchain validated): `{Type}_Registry_Find` → `{Type}_Find` rename

Deferred, tracked follow-up (see the Z80 side of this same rename,
which already landed) -- 6502's `{Type}_Registry_Find` now matches the
name 68000 and Z80 both use for the identical conceptual operation.
Pure symbol rename, no change to the emitted instruction sequence:
confirmed by regenerating all three fixtures via the real exporter CLI
and diffing against the pre-rename originals -- the diff is exactly
the two renamed labels (`Creature_Find`/`Item_Find`), nothing else
moved.

Blast radius: all three renderer files
(`export_6502_acme.py`/`_kickassembler.py`/`_64tass.py`, both the
emitted label and surrounding docstring references), all three
hand-written harnesses (`test_6502_harness.asm`/`_ka.asm`/`_tass.asm`),
and all three generated minimal fixtures
(`generated_6502_minimal.asm`/`_ka.asm`/`_tass.asm`). 6502's SoA
fixtures/harnesses were confirmed to reference neither `Find` nor
`Registry` at all -- unaffected, not silently skipped.

**ACME and 64tass**: real toolchain validated, both fully passing.
Built a permanent shared helper, `export_6502_test/six502_test_helper.py`
(mirrors `z80_test_helper.py`'s role) -- parses ACME's `--symbollist`
output and 64tass's `-l` label-list output, confirmed as two genuinely
different conventions directly, not assumed consistent: 64tass omits
the `$` prefix for symbols defined as plain decimal constants in
source (`Creature_Goblin_Index= 0`) but keeps it for real addresses
(`Creature_Find\t= $c034`); ACME always uses `$` for both. Permanent
runners `test_6502_run.py` (ACME) and `test_6502_tass_run.py` (64tass)
both assemble the renamed harness for real and execute via `py65`,
checking all five `Dispatch` signals and all four `{Type}_Find`
results against real resolved addresses in the assembled binary. Both
pass.

**KickAssembler: fully validated.** KickAss.jar was uploaded by the
user and the following confirmed directly against the real v5.25 binary:
  - Symbol file format is `.label NAME=$HEX` -- confirmed by assembling
    real source and reading the output.
  - Output is always PRG format (2-byte load-address header, then the
    assembled binary). No flat-binary output mode exists. The runner
    (`test_6502_ka_run.py`) handles this via `load_prg_kickassembler()`
    in `six502_test_helper.py`, which reads the org from the header
    rather than assuming a fixed address.
  - KickAssembler does NOT have ACME's ZP-forward-reference restriction
    -- `.label IndirLo = $F8` placed after the code that uses it works
    correctly (KickAssembler does a multi-pass resolve).
  - The existing `test_6502_harness_ka.asm` assembled clean and all
    9 checks passed: 5 Dispatch signals, 4 `{Type}_Find` pointer results.
  - `KickAss.jar`, `KickAss.cfg`, and `KickAssembler.pdf` preserved at
    `/mnt/user-data/outputs/tools/kickassembler/` so they survive session
    resets without needing to be re-uploaded, per the instruction in
    this HANDOFF's toolchain setup note above.

### RESOLVED (all 3 dialects real-toolchain validated): 6502 `string N` field support

**What changed**: all three 6502 renderers (`export_6502_acme.py`,
`export_6502_kickassembler.py`, `export_6502_64tass.py`) now emit
`string N` leaf fields per §13.2 -- a quoted, human-readable literal
followed by enough explicit zero bytes to reach N total, never a
byte-by-byte hex list. The shared IR (`export_6502.py`'s
`_render_leaf_value`) was updated to pass string values through as
plain Python `str` rather than the old "strings not in this first
pass" early return.

**Key confirmed findings, before any code was trusted**:

- Neither ACME (`!byte`) nor 64tass (`.byte`) accepts a multi-character
  string literal inside the byte directive. Confirmed by attempting it
  on both real binaries and reading the error: ACME says "There's more
  than one character", 64tass gives an equivalent syntax error. The
  correct form is a two-line block: directive + literal on one line
  (`!text "..."` / `.text "..."`), then explicit zero padding bytes
  (`!byte 0, 0, ...` / `.byte 0, 0, ...`) on the next.
- **ACME's zero-page detection is single-pass and does NOT work for
  ZP forward-references.** Using `LDA (IndirLo),Y` before `IndirLo`
  is defined later in the file produces "Number does not fit in 8
  bits", even though the value is a small ZP address. Fix: ZP symbols
  must be defined BEFORE the code that uses them. Confirmed by actually
  hitting the error during harness construction, not assumed. 64tass
  does not have this restriction.
- UTF-8 multi-byte content passes through `!text`/`.text`
  byte-for-byte: U+00FC ü → `0xC3 0xBC` in the assembled output,
  confirmed by assembling real UTF-8 source files and checking bytes
  directly.

**Fixture**: `export_6502_test/string_field_6502_minimal.gddl` --
`Villager.name = string 12`, value `"Grübnik"` (8 UTF-8 bytes across
7 chars, deliberately non-ASCII). Expected: `47 72 c3 bc 62 6e 69 6b
00 00 00 00` (8 content + 1 NUL + 3 padding = 12 total).

**ACME and 64tass**: real toolchain validated, both fully passing.
Permanent committed assets:
- `generated_6502_string_field.asm` / `_tass.asm` / `_ka.asm`
- `test_6502_string_field_harness.asm` (ACME) /
  `test_6502_string_field_harness_tass.asm` (64tass)
- `test_6502_string_field_run.py` (ACME) /
  `test_6502_string_field_tass_run.py` (64tass)

Both runners assemble the harness for real, execute via `py65`, and
verify the exact 12 bytes recovered through `Villager_Find` match the
expected UTF-8 encoding with correct NUL-terminator and zero padding.

**KickAssembler: fully validated, with one significant confirmed
difference from ACME and 64tass.** KickAssembler's `.text` directive
does NOT produce raw UTF-8 bytes for non-ASCII characters. Every
`.encoding` option (ascii, petscii_upper, petscii_mixed,
screencode_upper) treats non-ASCII source characters as single Latin-1
bytes -- e.g. 'ü' (U+00FC) always emits `$FC`, never the correct UTF-8
`$C3 $BC`. No escape sequences work either. This was confirmed directly
by assembling real UTF-8 source files under all encoding options and
checking output bytes.

The correct approach for KickAssembler: split at UTF-8 character
boundaries. ASCII runs emit as `.encoding "ascii"` + `.text "..."`;
non-ASCII bytes emit as explicit `.byte $c3, $bc` hex values. This
produces correct UTF-8 byte sequences and is the only approach that
does. The renderer (`export_6502_kickassembler.py`) implements this
split in `render_string_leaf_kickassembler()`, and the generated file
header includes `.encoding "ascii"` (required so `.text` emits ASCII
byte values rather than PETSCII-converted codes -- without it,
lowercase 'r' maps to `$12` instead of `$72`).

Also confirmed: KickAssembler does NOT have ACME's ZP-forward-reference
restriction -- labels defined after their use sites resolve correctly.

All checks passed: `47 72 c3 bc 62 6e 69 6b 00 00 00 00` from the real
KickAssembler binary, via `Villager_Find`, decoded correctly to "Grübnik".
Permanent committed assets: `generated_6502_string_field_ka.asm`,
`test_6502_string_field_harness_ka.asm`, `test_6502_string_field_ka_run.py`.

### RESOLVED: C++, 68000, and 6502 -- composition + genuine scalar `u16` field, all three targets

Triggered by a direct audit of what had actually been tested versus
merely implemented. Before this round: every remaining target's own
test suite covered composition OR `u16`, never both together, and
never `u16` as a genuine scalar field (only as an identifier-domain's
backing width):
  - **6502**: no `u16` anywhere in its own fixtures at all (though
    `!word`/`.word` mapping was already implemented and used correctly
    once exercised).
  - **68000**: its one `u16` usage (`Element`) is an identifier-domain
    width, not a scalar field; its fixtures have no composition at all
    (flat `Creature` only).
  - **C++**: has composition (`Item` nests `Object`), but every numeric
    field in its own fixtures is `u32`; its only `u16` usage is the
    same identifier-domain-width pattern as 68000.

Same fixture used across all four targets in this project now
(`composition_nested_u16_fields.gddl` -- first validated on Z80,
see the Z80 section above): `Character` composes `Stats` (hp, mp) and
`Equipment` (weapon_power), all `u16`, values deliberately above 255
(60000, 12000, 500) so an 8-bit-truncation or byte-order bug would be
observable, not coincidentally correct.

**C++** (`export_cpp_test/`): validated in BOTH real generation modes,
not just one -- `--force-single-header` and the new split-header
default (§14.3) are genuinely separate code paths (the split default's
instances are `extern const`, NOT `constexpr` the way single-header's
are, confirmed by a real compile failure when the first draft assumed
otherwise: "the value ... is not usable in a constant expression").
Single-header: `static_assert`-checked at compile time. Split: runtime
`assert`, both direct struct access and via `Character_Registry::Find`.
Both compiled and run with real `g++17`, both pass:
`hp=60000 mp=12000 weapon_power=500 level=42`. Assets:
`export_test_composition_nested_u16_fields.gddl`,
`generated_composition_nested_u16_fields.{h,cpp}` (split),
`generated_composition_nested_u16_fields_single.h` (single-header),
`test_generated_composition_nested_u16_fields{,_single}.cpp`.

**6502** (`export_6502_test/`): all three dialects, real assemble, real
`py65` execution, via the real `Character_Find` subroutine (not a
hand-computed offset). ACME's `!word 60000` and both other dialects'
equivalent all confirmed correct at the raw-byte level before building
the harnesses (`60 ea` / `e0 2e` / `f4 01` / `2a 00`, little-endian, as
expected) -- all four values round-trip correctly, all three dialects.
Assets: `composition_nested_u16_fields.gddl`,
`generated_6502_composition_u16{,_tass,_ka}.asm`,
`test_6502_composition_u16_harness{,_tass,_ka}.asm`,
`test_6502_composition_u16{,_tass,_ka}_run.py`.

**68000**: see the dedicated section below (this required rebuilding
`vbcc` from source, a real toolchain event worth its own record).

### 68000/vbcc real-toolchain validation setup

Same discipline as 6502: every 68000 exporter change should be
validated by actually compiling with the real `vbcc` toolchain and
executing the result in an emulator (`vamos` for Amiga, `hatari` for
Atari ST), not just visual review.

- **vbcc/vasm/vlink**: NOT apt-installable. The user uploaded a
  complete prebuilt multitarget Linux x64 distribution (includes m68k,
  6502, and many other targets/configs, ~103MB), which superseded an
  earlier hand-built Amiga-only version (built from
  `https://github.com/erique/vbcc_vasm_vlink` -- still a valid fallback
  if the prebuilt archive isn't available, just Amiga/Kickstart-only,
  no Atari target). The prebuilt one is preserved at
  `/mnt/user-data/outputs/tools/vbcc/` -- copy back to e.g.
  `/home/claude/work/gddl-compiler-core/compiler-python/tools/vbcc/ (same restructuring-era convention as above)` after a reset. Invoke via
  `VBCC=/path/to/vbcc PATH=$VBCC/bin:$PATH vc +TARGET file.c -o out`.
  Confirmed targets: `+aos68k` (AmigaOS), `+kick13` (Kickstart 1.3),
  `+tos` (Atari ST/TOS, **32-bit `int`** -- confirmed directly via
  `sizeof(int) == 4` under emulation, not assumed from the flag name;
  deliberately NOT `+tos16`, which would give 16-bit `int` and doesn't
  match anything GDDL's data model needs).
- **vamos** (the Amiga emulator, from `amitools`), for execution:
  `pip install amitools --break-system-packages` alone is NOT enough --
  a bare `pip install machine68k` grabs the latest release (0.4.1 as
  of this writing), but amitools' own `pyproject.toml` pins an EXACT
  `machine68k == 0.3.0` as its `vamos` optional-dependency requirement.
  Installing the mismatched latest produces a real, reproducible error
  (`AttributeError: 'machine68k.Traps' object has no attribute
  'set_exc_func'`) the moment `vamos` tries to start a machine. Fix:
  `pip install "machine68k==0.3.0" --break-system-packages
  --force-reinstall` (installing the exact pin explicitly, since a
  plain top-level `pip install machine68k` doesn't consult amitools'
  extras-based pin unless installed via `amitools[vamos]` specifically).
  Run via `vamos path/to/executable [args...]`. **Propagates the
  guest program's actual exit code as its own** -- confirmed directly.
- **hatari** (the Atari ST emulator), for execution: `apt-get install
  hatari` -- straightforward. Two real gotchas, both confirmed
  directly, not assumed:
  - Needs a virtual display even in headless/`--disable-video` mode
    (that flag means "don't render," not "no display connection
    needed at all") -- without one, hatari just hangs rather than
    erroring cleanly. Fix: `apt-get install xvfb`, run everything
    through `xvfb-run -a hatari ...`.
  - Needs a real TOS-compatible ROM image to boot at all -- not
    bundled with the apt package, and every official EmuTOS/TOS
    distribution host (`compilers.de`, `owl.de`/`phoenix.owl.de`,
    `sun.hasenbraten.de`, `todi.se`, `aminet.net`, `server.owl.de`,
    `ftp.exotica.org.uk`) is blocked by this sandbox's network egress
    proxy. EmuTOS's own GitHub repo (`emutos/emutos`) has no compiled
    Releases, and building it from source needs a *separate* GCC
    cross-toolchain (`m68k-atari-mint`), a large detour just for a
    ROM. Found a real fix instead: `github.com/bbbradsmith/hatariB`
    (a Libretro core for Hatari) commits real EmuTOS binaries directly
    into its repo for its own bundling purposes -- `emutos/etos1024k.img`
    there is a genuine, working 1MB EmuTOS ROM. Preserved at
    `/mnt/user-data/outputs/tools/emutos/etos1024k.img`.
  - **`hatari`'s own process exit code is ALWAYS 0**, regardless of
    the emulated program's actual return value -- confirmed directly
    (a test program returning 1 still yields hatari exit code 0),
    unlike `vamos`. Validation must parse captured console output
    (`--conout 2`), never rely on the host exit code.
  - Confirmed working invocation (see `run_atari_test.sh` in each
    `export_68000_test/` -- committed, not just documented here):
    `xvfb-run -a hatari --tos <emutos.img> --harddrive <dir> --auto
    'C:\PROGRAM.PRG' --conout 2 --run-vbls <n> --log-level warn`.
    `--auto` needs a full `C:\PATH` Atari-style path (drive letter +
    backslash) -- a bare filename silently doesn't autostart anything.
    `--run-vbls`, tuned high enough for boot+program to finish, is
    what makes this deterministic and script-friendly: a correctly-
    tuned run exits cleanly on its own in a few seconds, no external
    `timeout -k` kill needed (a mistuned/too-low value needs an
    external kill and leaves X-connection error noise in the output).

### RESOLVED: 68000 composition + genuine scalar `u16` field, real `vbcc` + `vamos`

Real gap closed: the one existing 68000 fixture is a flat `Creature`
with no composition, and its only `u16` usage is `Element`'s
identifier-domain width, not a scalar field. Never tested together on
this target before now. See the combined section above for the shared
fixture and why it was chosen.

**vbcc was NOT present in this session** -- the prebuilt multitarget
archive mentioned above (`+aos68k`/`+kick13`/`+tos`, uploaded
previously) was not preserved, consistent with this project's
established finding that the tools directory does not reliably
persist across sessions. Rather than block on a re-upload, **rebuilt
the documented fallback from source**
(`https://github.com/erique/vbcc_vasm_vlink`, reachable): unpacked
`vasm`/`vlink`/`vbcc`/the Unix config tarballs, extracted the two
`.lha` target packages via `p7zip-full` (not preinstalled -- installed
fresh), applied the documented `dtgen.c` interactive-prompt patch (had
to write it to a file and apply via `patch -p 0 < file` -- embedding
it in a shell heredoc inside a `bash -c '...'` mangled the escaping and
silently produced two failed hunks; caught by checking the patch
actually applied rather than trusting a "done" message), then built
`vasm`, `vlink`, and `vbcc` in sequence (`make CPU=m68k SYNTAX=mot`,
plain `make`, `make TARGET=m68k`, respectively -- all single-threaded,
`-j 1`, since this sandbox is single-core). Smoke-tested with the
documented `hello.c` before trusting it for anything: compiled with
`vc +aos68k`, ran under a freshly-`pip`-installed `vamos` (same
`machine68k==0.3.0` pin already documented above), got `hello, world`
back correctly.

**This fallback build is Amiga-only** (`+aos68k`, `+kick13`) -- no
`+tos` target, since that comes only from the prebuilt archive this
session didn't have. Sufficient for real validation here: the task
only required real compile + real execution on *some* 68000
environment, and `vamos`/AmigaOS satisfies that on its own without
needing the Atari/`hatari`/EmuTOS path too.

**Confirmed directly, not assumed from the type name**: `unsigned
short` is genuinely 2 bytes under `+aos68k`, via a real
compile-and-print `sizeof()` check under `vamos` -- same discipline
already established for `+tos`'s `sizeof(int) == 4` above.

Compiled `test_68000_composition_u16.c` (a separate translation unit,
seeing only the generated header, matching this target's existing
harness convention) plus the generated `.c`, ran under `vamos`: all
checks passed, both direct struct-field access and via the generated
`Character_Find()`, values `hp=60000 mp=12000 weapon_power=500
level=42` exactly. Assets: `generated_68000_composition_u16.{h,c}`,
`test_68000_composition_u16.c`, `run_composition_u16_test.sh` (the
committed, repeatable build+run script -- confirmed working from a
clean rebuild, not just the first ad hoc run).

**The rebuilt `vbcc` distribution itself was staged to
`/mnt/user-data/outputs/tools/vbcc/`** for the same reason KickAssembler's
jar was previously -- but note the copies made through that path lost
their executable bit (the same mount behavior already documented for
the Z80 tools), so restoring from there needs a `chmod +x` pass on
`bin/*` before use, confirmed by hitting exactly this ("Permission
denied" on `vc`) and switching back to the locally-built copy rather
than assuming the staged copy would just work.

### Z80/SjASMPlus real-toolchain validation setup

Same discipline as every other target: validated by actually
assembling with the real `sjasmplus` binary and executing the result
with a real Z80 emulation library, not just visual review.

- **SjASMPlus**: NOT apt-installable, but builds cleanly from source.
  `git clone https://github.com/z00m128/sjasmplus.git`, then
  `git submodule update --init --recursive` (pulls LuaBridge and
  unittest-cpp, both from GitHub), then `make`. Confirmed working:
  `LD A, 42` / `RET` assembles to `3e 2a c9`. The built binary
  (`sjasmplus`, ~700KB) is preserved at
  `/mnt/user-data/outputs/tools/sjasmplus/sjasmplus` -- copy back to
  e.g. `/home/claude/work/gddl-compiler-core/compiler-python/tools/sjasmplus/ (same restructuring-era convention as above)` after a reset (and
  `chmod +x` it there -- the persistent mount doesn't reliably keep
  the executable bit set, confirmed directly rather than assumed).
  Get a symbol table via `--sym=<file>` (format: `NAME: EQU
  0xHEXVALUE` per line) -- essential for locating labels when writing
  a test harness, since there's no other way to know where the
  assembler placed anything.
- **Execution**: NOT Fuse (the standard ZX Spectrum emulator) --
  investigated it first, but its CLI (`fuse`/`fuse-gtk`) has none of
  hatari's automation hooks (no `--conout`, `--run-vbls`, or scriptable
  autostart), and it's built around booting a full Spectrum system,
  more machinery than GDDL's generated code actually needs. Used the
  `z80` PyPI package instead (`pip install z80`, home:
  github.com/kosarev/z80) -- a bare Z80 CPU emulation library with
  direct register/memory access (`m.a`, `m.pc`, `m.memory`,
  `m.set_memory_block(addr, bytes)`), no OS/disk boot required at all,
  mirroring `py65`'s role for 6502 more closely than a full-system
  emulator would. Confirmed via the library's own bundled
  examples/tests (cloned the repo directly to check real usage, not
  guessed from the API surface alone): `m.ticks_to_stop = 1` before
  `m.run()` executes exactly one instruction -- this is the reliable
  single-stepping mechanism (see `examples/single_stepping.py`,
  `examples/exit_halted_state.py` in that repo).
  - **Not fully resolved, honestly recorded rather than silently
    worked around**: `m.set_breakpoint(addr)` + `m.run()` did not
    behave as expected in direct testing here -- it reported a
    breakpoint hit at the wrong address (the target of the immediately
    preceding `call`, not the address actually marked), even though
    the library's own test suite shows this exact pattern working in
    a simpler program. Root cause not tracked down. The single-step
    loop (`z80_test_helper.py::run_to_pc`, in each
    `export_z80_test/`) sidesteps this entirely and was cross-checked
    against a fully single-stepped trace that matched expectations
    exactly -- reliable, not a guess, just not the breakpoint shortcut
    originally expected to work.
- **`--auto`/console-output equivalent**: none needed at all -- since
  there's no OS/disk image involved, the test harness's own code
  (labels placed at points of interest, read via the assembler's
  `--sym` output) IS the automation hook; no separate autostart/conout
  mechanism exists or is needed.

### z88dk-z80asm real-toolchain validation setup

Second Z80 output path (§16.1); shares the shared IR (export_z80.py)
and the emulator (`z80` PyPI library) already set up for SjASMPlus --
only the assembler binary and its syntax needed fresh investigation.

- **z88dk-z80asm**: NOT apt-installable. `git clone --recursive
  https://github.com/z88dk/z88dk.git` -- recursive is required, a
  plain clone misses several submodules (UNIXem, Unity, optparse,
  regex, uthash). A full `./build.sh` (even with `-l` to skip
  libraries) hits an unrelated failure building `z88dk-appmake`
  (missing `gmp.h`, needed only for TI-83 calculator support) --
  irrelevant to needing just the assembler. Faster, targeted fix:
  build directly in `src/z80asm/` with a bare `make` -- confirmed
  working, produces `z88dk-z80asm` directly without touching appmake,
  the C compilers, or any per-machine runtime library at all. The
  built binary (~27MB) is preserved at
  `/mnt/user-data/outputs/tools/z88dk-z80asm/z88dk-z80asm` -- copy
  back and `chmod +x` after a reset (same executable-bit-on-the-mount
  caveat as every other persisted binary).
- **Output files, two genuinely different conventions, confirmed
  directly rather than assumed to match**:
  - `-s` produces `<inputstem>.sym` -- reports pre-`org` SECTION-
    RELATIVE offsets (e.g. `$002A`), NOT the final absolute addresses
    actually embedded in the assembled binary. Confirmed by comparing
    against the real machine code bytes directly.
  - `-m` produces `<outputstem>.map` -- reports the actual final
    absolute addresses (e.g. `$802A` for the same symbol, matching a
    real `org $8000`). **Use `-m`, not `-s`**, for locating real
    addresses -- despite `.sym` sounding like the more obvious choice
    for a symbol table.
  - `.bin` output (via `-b`) starts directly at the `org` address, no
    leading padding from address 0 -- same convention as ACME's
    `-f plain`, NOT 64tass's `--flat` (which pads a full image from
    address 0). Confirmed by checking the exact file size.
- **Syntax, confirmed directly against the real binary, not assumed to
  match SjASMPlus despite both targeting Z80** -- genuinely shares a
  surprising amount (`;` comments, `db`/`dw`, `equ`, `org`,
  `include "file"`), but with real, confirmed differences:
  - Label colon is **required** here (a bare label with no colon is a
    hard syntax error) -- the opposite of SjASMPlus, where it's
    optional.
  - Instructions do **not** need to be indented -- column 0 is fine,
    unlike SjASMPlus's hard column-0-means-label rule.
  - **Low/high byte extraction uses plain bitwise expressions**
    (`expr & $FF`, `(expr >> 8) & $FF`) -- SjASMPlus's `low()`/`high()`
    function-call syntax is a confirmed hard syntax error here (no
    such builtin exists). Both forms verified directly against a
    handler at a known address, checking the actual output bytes.
- **Execution**: no new investigation needed at all -- the `z80` PyPI
  library (already set up for SjASMPlus) executes raw Z80 machine code
  regardless of which assembler produced it. Reused the confirmed-
  reliable single-step mechanism (`z80_test_helper.py::run_to_pc`)
  directly; the breakpoint discrepancy noted in the SjASMPlus section
  wasn't revisited since single-stepping already works reliably.

### RESOLVED: Z80 composition + wide-domain (`u16`) testing (string fields remain untested -- see below)

Originally flagged as an open gap (see prior revision of this note in
git history / earlier session record): Z80 had no fixture exercising
nested `define` composition or a `u16` field, on any of the three
output paths, end-to-end on real toolchains. **Composition and `u16`
are now closed**, via `composition_nested_u16_fields.gddl` (source:
Test Corpus, GDDL Spec v4 §5.2-§5.3). String fields are intentionally
excluded from this fixture and remain a genuinely open, unstarted
design question -- see the dedicated note below.

Fixture: `define Character { stats = Stats, equipment = Equipment,
level = u16 }`, with `Stats { hp = u16, mp = u16 }` and `Equipment
{ weapon_power = u16 }`, nested two levels deep, flattened to one
dense 8-byte AoS record (`stats_hp`, `stats_mp`,
`equipment_weapon_power`, `level`). Values deliberately chosen above
255 (60000, 12000, 500) so that 8-bit truncation or wrong byte order
would produce an observably wrong result, not a coincidentally correct
one.

Real toolchain validation, all three paths, all passing:

- **SjASMPlus**: `export_z80_test/generated_z80_composition_u16.asm` +
  `test_z80_composition_u16_harness.asm` +
  `test_z80_composition_u16_run.py`. Resolves `Character_Hero` via the
  real `Character_Find` subroutine (not a hand-computed offset),
  reads all four fields through HL. `hp=60000 mp=12000
  weapon_power=500 level=42` -- all four exact matches.
- **z88dk-z80asm**: same logic,
  `generated_z80_composition_u16_z88dk.asm` +
  `test_z80_composition_u16_harness_z88dk.asm` +
  `test_z80_composition_u16_z88dk_run.py`, using `.map` (not `.sym`)
  per the already-confirmed absolute-vs-section-relative distinction.
  Same four exact matches.
- **z88dk C mode / real `zsdcc`**:
  `export_z80_c_test/composition_u16/{gddl_z80_export.h,
  gddl_z80_export.c, consumer.c}`. Compiled to `.rel` per file, linked
  as two translation units, executed on the `z80` emulator via
  `Character_Find(Character_Hero_Index)->stats_hp` etc. Same four
  exact matches.

All three paths flatten the two-level composition into the same
correct 4-field layout, in the same field order, and every `u16` value
round-trips exactly through `db`/`dw` (asm) and `unsigned int` (C).
This confirms what the prior note called "expectation, not
confirmation" -- reusing `export_cpp.py`'s flattening logic for Z80
does produce correct Z80 output for composed types, not just for the
flat single-field case already covered by `Creature`.

Golden-locked separately in Test Corpus's own corpus (language-level
resolution only, no export target): `composition_nested_u16_fields.gddl`
under `corpus/composition_no_inheritance/`. That capture and this
Z80-specific validation are deliberately two separate, non-merged
things -- the corpus schema has no concept of an export target and
correctly doesn't try to grow one; this record here is Compiler Core's
own.

### RESOLVED: Z80 string-field (`string N`) support

The last remaining item from the original composition/u16/string gap
note is now closed. Design decisions were already settled upstream
(§13.2), not made here: fixed-size storage, never a pointer or
length-prefixed scheme (mirroring `export_cpp.py`'s `char[N]`
precedent exactly); length/UTF-8 validation happens in phases 1-8, so
export never re-validates, just emits what arrives; emission on both
assembly dialects is a quoted, human-readable literal followed by
exactly enough explicit zero bytes to reach `N` total (`db "Grubnik",
0, 0`), never a byte-by-byte hex list.

Fixture: `export_z80_test/string_field_minimal.gddl` -- one type
(`Villager`), one field (`name = string 12`), one instance holding
`"Grübnik"`. Deliberately non-ASCII (a-umlaut is 2 UTF-8 bytes), so an
export that assumed 1-byte-per-character, or got padding/byte-order
wrong, would produce an observably wrong result rather than a
coincidentally correct one: 8 content bytes + 1 terminator + 3 padding
zeros = 12 total.

Real toolchain validation, all three paths, all passing, all
byte-identical to each other:

- **SjASMPlus**: `export_z80_test/generated_z80_string_field.asm` +
  `test_z80_string_field_harness.asm` +
  `test_z80_string_field_run.py`. Resolves `Villager_Grubnik` via the
  real `Villager_Find` subroutine, copies all 12 bytes of `name` out
  through HL byte-by-byte (`djnz` loop -- confirmed this instruction
  and `ds N, fill` both assemble as expected on this dialect, not
  assumed). Raw bytes `47 72 c3 bc 62 6e 69 6b 00 00 00 00`, decodes
  back to `"Grübnik"` exactly.
- **z88dk-z80asm**: same logic,
  `generated_z80_string_field_z88dk.asm` +
  `test_z80_string_field_harness_z88dk.asm` +
  `test_z80_string_field_z88dk_run.py`, `.map` (not `.sym`) as usual.
  Same raw bytes, same decode.
- **z88dk C mode / real `zsdcc`**:
  `export_z80_c_test/string_field/{gddl_z80_export.h,
  gddl_z80_export.c, consumer.c}`. `char name[12]` in the struct
  (special-cased at the declaration site exactly like
  `export_cpp.py` does -- a C array's size goes after the identifier,
  so `_c_type()`'s `"char[12]"` return can't just be interpolated
  before the field name the way every other type is). Initializer is
  a plain `{ "Grübnik" }` -- **no explicit padding emitted in C mode**,
  unlike the assembly paths, since C89 itself zero-pads a `char
  field[N] = "text";` initializer shorter than N for free. Confirmed
  directly by inspecting the compiled `Villager_Instances` bytes in
  the linked binary before ever executing anything: `47 72 c3 bc 62 6e
  69 6b 00 00 00 00`, identical to the two assembly paths.

**One real bug caught and fixed before any of the above was trusted**:
the first draft of `export_z80_z88dk_c.py`'s struct-declaration loop
reused the loop variable name `n` for the string field's byte size,
which shadowed the outer `n = len(t.instances)` used immediately after
for `#define {Type}_Registry_Count {n}` -- silently turning a correct
`Registry_Count 1` into a wrong `Registry_Count 12` for any type with
a string field. Caught by actually reading the generated header output
rather than trusting a clean exit code; fixed by renaming the
loop-local variable, then re-verified against the previously-validated
composition/`u16` output (byte-identical, confirming the fix didn't
disturb the non-string case) before proceeding to compile anything.

Golden-locked separately in Test Corpus's own corpus if they choose to
pick it up (independent initiative, not required): string-field
language semantics on their own terms, no export target -- same
deliberate non-merging of the two channels as the composition/`u16`
work.

**Z80 (all three renderers) is now closed to the same standard as
every other export target**: scalar/identifier fields, composition,
`u16`, and `string N` are all validated end-to-end on real toolchains.

### IMPORTANT: the tool-preservation premise above does NOT currently hold

Every "preserved at `/mnt/user-data/outputs/tools/...`, copy back after a
reset" instruction in the sections above is **currently unreliable, and
should not be planned around.** Verified independently from two sides in
this session: `/mnt/user-data/outputs/` is empty, and `tools/` does not
exist at all — not a one-session fluke but the observed state in every
session checked. Nothing is restorable because nothing is there.

Practical consequence: **assume no toolchain exists and budget for a
from-source rebuild.** The recipes above are still correct and still
work — they were re-executed end-to-end this session — they just describe
a rebuild, not a restore. Likewise, there is **no `.git/`** in the
distributed archive, so "check `git log` for checkpoint history" under
*Current state / how to resume* does not work either; the archive is a
flat snapshot with only `.gitignore` surviving.

The `KickAssembler` case is the one genuinely unrecoverable item, since
`theweb.dk` is egress-blocked and it cannot be rebuilt from source — it
must be re-uploaded by the user if 6502 work resumes.

#### Additional build findings (this session, Z80/C toolchains)

Re-executed the SjASMPlus and z88dk-z80asm recipes above verbatim; both
still correct, both confirmed against their documented smoke tests
(`3e 2a c9`; `.sym` section-relative `$0003` vs `.map` absolute `$8003`,
`.bin` starting at `org` with no leading pad). New findings, all
confirmed directly:

- **`zsdcc` source location.** Upstream SDCC lives on SourceForge, which
  is egress-blocked. The real zsdcc source is on GitHub at
  `https://github.com/z88dk/sdcc.git`, **branch `zsdcc`** (not `master`,
  which is an unmodified SDCC mirror). Confirmed genuine by the built
  binary self-identifying as `ZSDCC IS A MODIFICATION OF SDCC FOR Z88DK`,
  build `3.6.9 #10024`. This matters: it means the §16.2 crossover table
  no longer needs stock SDCC standing in for `zsdcc` — the real compiler
  is buildable here.
- **Build dependencies not present in the base image**, each of which
  fails `configure`/`make` with a distinct error: `bison` + `flex`
  (configure: "Cannot find required program bison"), `libboost-graph-dev`
  (configure: "boost library not found (boost/graph/adjacency_list.hpp)"),
  and `libgmp-dev` (the `appmake`/`gmp.h` blocker already recorded above;
  multiarch path `/usr/include/x86_64-linux-gnu/gmp.h`, which gcc finds by
  default — no `CPATH` override needed).
- **`makeinfo`/texinfo trap.** `sdcc/support/sdbinutils/bfd` tries to
  build `.info` docs and hard-fails without `makeinfo`. Installing
  `texinfo` alone is **not** sufficient: the already-generated Makefile
  has cached the `missing` wrapper from the first `configure` run, so it
  keeps reporting `makeinfo` as absent. Either re-run `configure` after
  installing, or — faster — build with **`make MAKEINFO=true`**, which
  skips docs entirely (command-line variables propagate to the recursive
  submakes). Docs are irrelevant to needing the compiler.
- **Scoping the build.** A full SDCC build is unnecessary. Configure with
  only the z80 port and no simulator/device libs — this is what makes it
  tractable on a single core:
  `./configure --disable-{mcs51,z180,r2k,r3ka,gbz80,tlcs90,ds390,ds400,pic14,pic16,hc08,s08,stm8}-port --disable-ucsim --disable-device-lib --disable-doc --prefix=<dir>`
  Produces `sdcc`, `sdcpp`, `sdasz80`, `sdldz80`, `makebin` in
  `sdcc/bin/`. Note `--disable-device-lib` means no crt0/stdlib, so test
  sources must be compiled `--no-std-crt0 --nostdlib` and use `const`
  data (which lands in ROM and needs no initializer copy).
- **Measuring T-states with the `z80` PyPI library.** `run()` stops only
  once the in-flight instruction completes, so a naive "raise
  `ticks_to_stop` until PC reaches the end" search **undercounts by
  (last instruction's T − 1)**, varying with whichever instruction
  happens to land last. Fix: place a trailing `NOP` after the sequence
  (or at the return address) and measure to just past it — the
  correction then becomes a constant `−1` regardless of the code under
  test. Both this session's measurement harnesses use that method and
  reproduce published Z80 timings exactly.

### Why this document exists


Mid-session, the sandbox environment reset and wiped `/home/claude`
entirely (everything not on the persistent `/mnt/user-data` mount was
lost). The rebuild was verified against the surviving `golden_output.json`
as a comparison baseline. Correction after the fact: that local copy
turned out to be **stale relative to Test Corpus's actual current
corpus**, not authoritative — two fixtures differed, were "fixed" to
match the local copy, and that fix happened to land on the value that
was already correct on Test Corpus's side too, dated from before the
reset. Right outcome, wrong reasoning at the time (a local snapshot was
mistaken for ground truth). See the process-conventions note above:
check with Test Corpus for current golden data before treating any local
copy as authoritative, especially after a continuity gap. This document,
the git repo, and keeping `golden_output.json` inside the project folder
(not just as a loose sibling file) are all here so a future reset — or a
future session picking this up — doesn't require reconstructing intent
from scratch, but none of that substitutes for confirming against the
real source of truth when one exists elsewhere.
