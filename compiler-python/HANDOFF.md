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

## Known gaps / pending work (not-forgotten list)

Consolidated here specifically so these don't get lost in this file's
own chronological narrative below -- each one is discussed in more
detail at its own point in the stage-by-stage history, and each has a
matching mention in `SPEC.md` where relevant. Real, open gaps only --
deliberate, permanent design non-goals (6502's missing AoS-linear
layout, mods being unable to declare new schema types at runtime,
GDDL never generating scripting-language bindings itself) are NOT
listed here; those are settled, not pending.

1. **Arrays under `--layout=soa` on 6502 and both Z80 assembly
   dialects** -- deliberately scoped out of arrays' stage 3, not
   ruled out permanently. See "Arrays work, stage 3" entry. (Note:
   `z88dk` C mode's `--layout=soa` does NOT share this gap -- see
   "Also resolved" below.)
2. **`string N` fields under `--layout=soa` on 6502/Z80 assembly**
   -- a pre-existing gap, same root cause arrays' own SoA gap (#1)
   mirrors: a non-power-of-two element width needs a real multiply
   neither dialect's multiply-avoidance discipline (SPEC.md section
   16) has a renderer for yet. Also does NOT apply to `z88dk` C mode.
3. **Struct/identifier/flags-typed array elements** -- explicitly
   deferred to "a later pass" in the arrays design itself; current
   scope is scalar and `string N` elements only. See SPEC.md section
   21.1.

**Found already resolved while drawing up this list, corrected rather
than left stale:** SPEC.md sections 8.5 and 14.7 both described a
"planned, not yet implemented" force-emit flag for an unreferenced,
width-declared domain (the `_Indexed` companion enum on C++; the
entire domain's compact constants on 6502/Z80/68000). Checked directly
against the real exporters rather than trusted at face value: all four
targets' existing `--emit-all-domains` flag already does exactly this,
confirmed with a real fixture and a real compile on each (a
width-declared, zero-reference `ActionAttack` domain produces nothing
without the flag, its full companion enum or constant table with it
on). SPEC.md sections 8.5, 14.7, and the cross-reference in section 4
were all corrected to describe this as implemented, not planned.

**Also resolved:** "Arrays on z88dk-C mode are implemented but never
toolchain-verified." `zsdcc` turned out to already be bundled with the
`z88dk` install under `compiler-python/tools/z88dk/z88dk/bin/` (as
`z88dk-zsdcc.exe`; the unprefixed `zsdcc.exe` next to it is a broken
0-byte stub, ignore it) -- no source build needed. Verified with a real
`zcc +embedded -compiler=sdcc -clib=sdcc_ix` compile+link of the
existing array fixture (`array_6502_test.gddl`, u8 elements): GDDL's
generated `gddl_z80_export.c` compiled and linked cleanly, and the
resulting binary's `CODE.bin` section contains the exact expected byte
sequence for the const instance data -- `0A 1E` (`damage_min_max =
{10,30}`), `01 02 03 04 05 06` (`grid = {{1,2,3},{4,5,6}}`), and the
two 8-byte null-padded string buffers for `names = {"Al","Bo"}` --
confirming both compile-time and data-layout correctness. Note for
future runs: the `embedded` target's *default* CLIB pulls in a console
driver and fails to link with `undefined symbol: fputc_cons_native`
even when the program never calls `printf`; `-clib=sdcc_ix` (the
SDCC-paired, `-nostdlib` variant) avoids that requirement entirely.

**Also resolved:** "Z80's `--z88dk-output=c` mode doesn't support
`--layout=soa`." Implemented in `export_z80_z88dk_c.py`: one
`extern`-declared, dense-index-order array per leaf field, no struct,
no `{Type}_Registry`, no `{Type}_Find` (§13.4 -- the same dense index
that finds an AoS instance already indexes every field array
directly), reusing the shared `gather_soa_columns` helper the two Z80
assembly dialects already use. Deliberately does NOT carry over the
assembly dialects' `string N`/array-typed-field rejection (gaps #1/#2
above): those dialects hand-write the index*stride multiply themselves
and only have a renderer for a power-of-two stride, but C mode leaves
all indexing to `zsdcc`, which strength-reduces `index * stride` for
any constant stride -- the same reasoning that already lets AoS mode's
`{Type}_Find` support every struct size (§16.1). Verified with two real
`zcc +embedded -compiler=sdcc -clib=sdcc_ix` compile+link runs, data
sections inspected byte-for-byte: a scalar/identifier-typed fixture
(`u16` + an identifier domain, 3 instances) and the same array/`string
N` fixture used for the AoS array verification just above. Both
matched exactly. Test assets committed under
`export_z80_c_test/soa/` and `export_z80_c_test/soa_arrays/`.

**Also resolved:** "SPEC.md section 14.6's own 'metadata manifest' for
scripting-VM binding-glue generation" -- described in the spec, never
actually implemented as code. Implemented in the new
`export_bindings.py`, C++ exporter only (`--emit-bindings-manifest`,
writes `<output>.gddlbindings.json`), rejected outright when combined
with `--layout=soa` since SoA output has no struct for a "per-field
getter thunk that dereferences `instance->field`" to mean anything
against -- `aos`/`aos-linear` share byte-identical field layout, so no
layout parameter is needed beyond that one rejection. Domain content
(`"domains"`) is reused verbatim from `export_ids.build_ids_manifest`
rather than a second, independently-written domain walk, confirmed by
a direct equality check in the test suite -- one source of truth for
"every domain this compile unit declared," matching the same scope the
C++ header's own enum/namespace emission already uses unconditionally.
Type/field/instance content (`"types"`) is new: every `define`'s
DECLARED field list (never flattened through composition, unlike the
assembly/binary targets -- a real C++ struct keeps composition as real
nested structs, and `struct`-kind fields name another entry in the
same `types` list rather than inlining it again) plus every
fully-resolved, non-delete instance's name and stable ID
(`reg.get_instance_id`, cross-checked directly against the real
generated `.cpp`'s own registry entries, not just trusted). Test suite
at `export_bindings_test/test_bindings_manifest.py`, 5 checks
(content/every field kind, delete-template exclusion, domain-content
reuse, real-CLI opt-in, the SoA rejection).

**Also resolved:** `.gddlids.json` (`--emit-ids-manifest`, SPEC.md
§20) never exposed named data-record instance stable IDs, only
identifier/flags domain members -- so a script compiler with only this
manifest (never a C++ build, never `.gddlbindings.json`) had no way to
resolve `Type::instance_name` (§6.8) at all. Requested by the
downstream scripting-language ("gscript") session, which had already
traced the exact reuse path before asking: `reg.get_instance_id` and
`export_bindings.py`'s own `types[].instances` shape. Added a new
`instances` section to `build_ids_manifest`/`write_ids_manifest`, one
block per `define` (unconditionally, same "every declared thing" rule
`domains` already follows), each with every non-delete resolved
instance's `name`/`stable_id` -- reusing `_topo_sort_defines` and
`export_instances_for_type` from `export_cpp.py` verbatim, the same
two functions `export_bindings.py` already reuses, so a name's stable
ID is computed by the one shared code path in both manifests, never
two. Gated behind a new optional `resolver` parameter (all five CLI
call sites pass it; `export_bindings.py`'s own internal
`build_ids_manifest(reg)` call deliberately omits it, since it already
carries its own per-type instances list under `types[]` and would
otherwise serialize the same data twice, in two different shapes, in
one `.gddlbindings.json`) -- confirmed the omit-path leaves the
returned dict byte-identical to its pre-change shape. Verified via a
real CLI regeneration against the bindings-manifest fixture: the new
section's stable IDs matched the previously-captured
`.gddlbindings.json` values exactly (`246fb5e1bf51ef67` for
`Human_Fighter`, etc.), and the delete-marked `TemplateOnly` instance
stayed correctly excluded. Two new checks added to
`export_ids_test/test_ids_manifest.py` (instances omitted without a
resolver; instances content cross-checked against an independent
`reg.get_instance_id` call), plus the existing real-CLI check extended
to assert the new section's presence and shape. SPEC.md §20 updated:
new §20.3.1, §20.1's scope description widened to cover instance
references, §14.6.2's own `instances` bullet cross-referenced.

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

## Z80 SoA support (§13.7), closing the "not implemented yet" gap

Implemented `--layout=soa` for both Z80 assembly paths (SjASMPlus,
z88dk-z80asm). Previously raised `NotImplementedError` deliberately;
that's now real, working output on both dialects, real toolchain
verified. C mode (`--z88dk-output=c`) explicitly stays out of scope for
this pass -- rejected cleanly with a clear error if combined with
`--layout=soa`, not silently mishandled.

**Design, grounded in §13.4/§13.7 before writing anything**: any
dense-index target (6502, 68000, Z80) needs no lookup mechanism at all
in SoA mode -- the same index that finds an AoS instance already
indexes every SoA field array. No Find(), no registry, just parallel
arrays. `gather_type_info` already fully flattens through composition
regardless of layout, so the only new IR-side logic needed was
`gather_soa_columns`, a transpose from row-major (per-instance) to
column-major (per-field), directly mirroring `export_68000.py`'s own
identically-named, identically-shaped helper -- not a new idea,
applying an already-proven pattern to a third target.

**Z80-specific reasoning, not a port of 6502's SoA renderer**: 6502
splits every field wider than a byte into separate lo/hi arrays,
because 6502 can only do 8-bit indexed loads. Z80 has real 16-bit
registers and 16-bit indexed addressing, so a `u16` SoA field array is
one straightforward array of 16-bit words, indexed with a single cheap
shift (`add hl,hl` for x2), never lo/hi splitting. Confirmed for real,
not just reasoned about: the harness computes `Item_power + index*2`
via exactly that shift and reads back the correct value on real
hardware emulation.

**`string N` fields are explicitly rejected in SoA mode**, matching
6502's own precedent exactly: a string field's width isn't guaranteed
a power of two, so indexing it would need a genuine multiply, not a
shift, and that renderer hasn't been designed. Raises a clear
`ExportZ80Error` at the emission site if attempted, not a silent gap.

**`--z80-pointer-table`'s existing warn-and-ignore-under-SoA logic was
left completely untouched** -- it was already correctly specified and
tested before this work started; confirmed it still fires correctly
(including when the flag is explicitly `on`, not just when omitted)
now that SoA actually produces real output instead of erroring
immediately after the warning.

**Validation, both dialects, real toolchains throughout:**
- Rebuilt `sjasmplus` from source per this file's own documented
  recipe (confirmed working via the same `LD A,42`/`RET` -> `3e 2a c9`
  smoke test already on record). Rebuilt `z88dk-z80asm` the same way,
  targeted `make` in `src/z80asm/` per this file's own documented
  shortcut, avoiding the unrelated `z88dk-appmake` build failure.
- Permanent fixture: `export_z80_test/soa_field_minimal.gddl` -- a
  `u16` field and an identifier-typed (`u8` domain) field, specifically
  chosen to exercise both the shift-indexed case and the plain-indexed
  case in one fixture.
- Real assemble + real execute on both dialects:
  `test_z80_soa_harness.asm`/`test_z80_soa_run.py` (SjASMPlus),
  `test_z80_soa_harness_z88dk.asm`/`test_z80_soa_z88dk_run.py`
  (z88dk-z80asm) -- both confirmed passing from a clean run, not just
  the first ad hoc pass.
- Confirmed existing AoS output and tests are completely unaffected:
  full 72-fixture regression clean, plus explicit re-run of the
  existing `test_z80_composition_u16_run.py` (real SjASMPlus assemble
  + real execute) to confirm nothing about touching shared code
  (`render()`, `gather_ir`, the two dialect renderers) disturbed the
  AoS path it already validated.
- Confirmed the pointer-table warning and the new C-mode+SoA rejection
  both fire correctly via direct CLI invocation, not just by reading
  the code.

**Known limitation, honestly recorded, not silently left implicit**:
`--z88dk-output=c` + `--layout=soa` remains unimplemented, rejected
cleanly rather than attempted. `string N` fields remain unsupported in
Z80 SoA on both assembly paths, same scope limit 6502 already has.

## C++ SoA Find() not-found sentinel: Table.size() -> static_cast<std::size_t>(-1)

Changed both `Find(uint64_t)` and `Find(std::string_view)` overloads,
in both single-header and split rendering (4 call sites total), from
returning `Table.size()` to returning `static_cast<std::size_t>(-1)`
on a miss.

**Reasoning, not just a style change**: `Table.size()` and
`static_cast<std::size_t>(-1)` fail very differently if a caller
forgets to check the return value before indexing with it. `size()`
used unchecked is exactly one past the end -- undefined behavior that
may not crash at all, silently reading whatever memory happens to sit
next, producing a plausible-looking but wrong value rather than an
obvious failure. `static_cast<std::size_t>(-1)` used unchecked is
`SIZE_MAX`, catastrophically out of bounds -- an immediate crash or an
instant ASan catch, not a quiet bug that ships. The new value is also
numerically identical to `std::string::npos` (confirmed directly:
`static_cast<std::size_t>(-1) == std::numeric_limits<std::size_t>::max()`),
matching an established standard-library idiom rather than inventing
a new one.

**Confirmed no other exporter is affected.** Checked directly, not
assumed: 6502/Z80/68000's own `{Type}_Find` functions take an
already-known compile-time index and convert it straight to an
address (direct array arithmetic or a pointer-table read) -- there is
no runtime search and therefore no "not found" case to have a
sentinel for at all. `export_binary.py` has no `Find()`-style
functions of its own. C++'s own AoS pointer-list and AoS-linear
`Find()` overloads are also unaffected, since they return `const
Item*`, and `nullptr` was already the natural, unambiguous sentinel
for a pointer -- this question only ever applied to SoA specifically,
since SoA is the one layout where `Find()` can't return a pointer at
all.

**Validated**: real `g++17` compile and execution, checked under
`-Wall -Wextra -Wconversion` specifically (the strictest relevant
flag for an implicit-sign-conversion concern) -- zero warnings.
Confirmed both the found and not-found cases directly, single-header
and split. Updated the two existing committed test files that
asserted against the old sentinel value (`test_generated_indexed_soa.cpp`,
`test_split_soa_main.cpp`) and regenerated their committed generated
output. Full 72-fixture regression clean throughout. `SPEC.md` checked
directly -- no SoA `Find()` worked example exists there, so nothing
needed updating on that side.

**One incidental, clearly-separated finding, not part of the requested
change**: regenerating `generated_indexed_soa.h` and
`generated_indexed_split_soa.h` revealed both were already stale
before this fix, missing the entire §17.5 `SchemaTable` section --
these two committed fixtures predate that work and were never
regenerated after it landed. Kept the fix, since reverting it would
have knowingly reintroduced a known-stale committed artifact, but
calling it out as its own thing rather than folding it silently into
the sentinel change's diff.

## Real bug fix: compile errors were being silently swallowed by every exporter

Found while verifying documentation content for docs/templates-guide.md
(specifically, checking that "uninitialized field is a compile-time
error" was actually true before writing it down). It wasn't, reliably.

**The actual defect**: `validate.py`'s phase-8 completeness check
(`final_validate`/`compile_report`/`print_report`) is well-designed and
was already described accurately in SPEC.md, but nothing in the entire
codebase ever imported or called it. Separately, `resolver.errors`,
`resolver.blocked`, and `resolver.reg.duplicate_errors` -- all real,
correctly-populated by phases 4-6 -- were also never checked by any
exporter CLI. Confirmed directly: `resolver.errors['Sword']` already
contained a precise, correct `CompileError` naming the exact line and
problem for a reference to a nonexistent domain member, but the CLI
proceeded straight to rendering anyway. Since a broken instance never
makes it into `resolver.cache`, the renderer's own (deliberate, correct)
"only emit fully-resolved instances" logic just silently excluded it.
End result: `exit 0`, a "successful" compile, with an instance quietly
missing from the output and no indication anything was wrong. The
uninitialized-field case hit the same root cause from a different
angle -- crashed with a raw, unhandled Python traceback instead of
vanishing silently, but the missing piece was identical.

**The fix**: added `check_and_report(resolver) -> bool` to `validate.py`,
sitting alongside the already-correct `print_report` but printing only
genuine problems (error/blocked/incomplete/duplicate_errors) to stderr,
in the exact same message formats `print_report` already established,
warnings included but non-blocking. Wired into all five exporter CLIs
(`export_cpp.py`, `export_6502.py`, `export_z80.py`, `export_68000.py`,
`export_binary.py`), immediately after obtaining `resolver`, before any
rendering begins. Every CLI now exits 1 with a precise diagnostic and
writes no output at all if anything is wrong, exactly matching what
SPEC.md already promised was true.

**Validated across all five exporters, each one individually, not
just the shared function in isolation**:
- A genuine resolution error (reference to a nonexistent domain
  member) now fails cleanly with `Sword: ERROR [phase 5,
  domain_typing] - line 8: 'Rarity.nonexistent' is not a known member
  of domain 'Rarity'`, exit 1, no output files written -- confirmed
  directly on every exporter.
- An uninitialized field now fails cleanly with `Goblin: INCOMPLETE
  [phase 8] - export-blocking, uninitialized field(s): name`, exit 1,
  instead of a Python traceback.
- A circular copy reference (`A = B`, `B = A`) was already correctly
  detected at phase 4 and now correctly blocks the build too, naming
  the exact cycle.
- A childless bare field correctly prints its existing warning and
  does NOT block the build -- confirmed the file still gets written,
  exit 0.
- Every clean, valid fixture still compiles silently and successfully,
  confirmed both individually and via the full 72-fixture regression,
  clean throughout.

This closes a real, previously-unnoticed gap in a core guarantee this
project has stated repeatedly: bad data is always a compile error,
never something that ships silently. It wasn't, until now.

## -h help text trimmed across all five exporters

Every exporter's --help output had grown quite verbose over the
course of this project -- §-references pointing at SPEC.md, argparse
design rationale ("a repeatable option rather than a second
positional list, since argparse cannot disambiguate..."), and asides
explaining *why* a flag works a certain way rather than just *what*
it does. That's genuinely useful context, but it belongs in this file
or SPEC.md, not in something meant to be read at a glance on the
command line.

Trimmed every flag's help= string (and export_binary.py's description
line, which had its own stray §17) down to what a user actually needs:
what the flag does, valid choices, and whether it's required. Net
reduction of 77 lines across the five files, roughly a third to a half
the length per exporter depending on how verbose it started.

**Scope, deliberately narrow**: only help= and description= string
literals were touched, nothing else. Runtime error messages (the
actual ap.error() calls, the --z88dk-output=c + --layout=soa
rejection, the --z80-pointer-table required-flag error, etc.) were
left completely untouched -- those are diagnostics a user sees only
when something's actually wrong, and full context there is still the
right call, unlike the --help text everyone sees on every invocation
regardless of whether anything's wrong.

**Validated**: all five files confirmed parsing, all five -h outputs
read and confirmed genuinely shorter with zero remaining § references,
and a real functional invocation of each exporter confirmed unaffected
(same generated output, same flags, same behavior). The Z80 C-mode +
SoA rejection specifically re-checked to confirm its full runtime
error text is untouched. Full 72-fixture regression clean throughout.

## Two real fixes from actual GDDL usage: #include path bug, description comments

Both found and requested directly from a real user actually using the
compiler, not from internal testing -- exactly the kind of feedback
this project doesn't get from its own regression suite.

**Bug: #include line embedded the full, unmodified -o path.** Reported
directly: running `export_cpp.py --layout aos-linear GDDL/* -o
Generated\Items` on Windows produced `#include "Generated\Items.h"`
in the .cpp, and Visual Studio failed to resolve it even though both
files sat in the same folder -- the raw backslash inside a C++ string
literal is an escape-sequence introducer, not a path separator, and
corrupts the include.

Root cause: `header_name = f"{args.output}.h"` was embedded verbatim
into the #include line, when the header and .cpp are always written
to the same directory by construction (both derived from the same -o
stem) and the #include never needed a directory component at all.

Fix: added `_include_basename()`, deliberately NOT via os.path.basename
-- confirmed directly that os.path.basename leaves a Windows-style
backslash path completely untouched when the exporter itself is
running on Linux/Mac, since os.path only understands whatever
separator convention its own host platform uses. The new helper
splits on both / and \ explicitly, regardless of host OS.

Validated: reproduced the exact reported scenario byte-for-byte
(confirmed the bug first, then confirmed the fix), tested six path
shapes including the literal reported one and a Windows drive-letter
path, confirmed the ordinary no-directory case is completely
unaffected, and confirmed the fixed output genuinely compiles with
real g++17 from a real matching directory layout, not just that the
string looks right. Full 72-fixture regression clean.

**Feature: description text as a comment on each enum entry.**
Requested directly: the quoted description text is already
self-documenting in the .gddl source, and having it repeated as a
`//` comment on the corresponding C++ enum line means a developer
never has to jump back to the .gddl file to know what an enum value
means.

`entry.description` was already retained on the parsed entry object,
fully unescaped through the same `_unescape_string_content` path
regular string field values use (confirmed directly with a quote-
containing description; an apparent backslash in one early check
turned out to be a display artifact of how the tool result got
rendered, not a real byte in the file -- confirmed via Python's own
repr() against the actual file content). Added to all four places an
enum gets emitted: the plain hash enum and the _Indexed companion
enum, in both single-header and split-mode header generation.

Validated: real generated output confirmed correct in all four
locations, confirmed genuinely valid, compilable C++ with real g++17
(zero warnings), confirmed correct with a quote-containing description
specifically. Full 72-fixture regression clean.

**Feasibility investigated but not implemented: column-aligned enum
and struct output.** Asked as an open question, not a direct request.
Real technical finding worth recording: hash values in the plain enum
are already zero-padded to a fixed 16 hex digits (`f"{h:016x}"`, `0x`
+ 16 hex + `ULL` = always exactly 21 characters), so that column
doesn't actually need padding, only the member-name column does. The
_Indexed companion enum's plain integer values and struct field types
genuinely do vary in width and would need real padding logic. Would
require restructuring the relevant emission loops from single-pass
(emit each line immediately) to two-pass (collect the block's
name/value/comment triples, compute max widths, then emit padded
lines) -- a real but contained change, scoped per-block as requested,
not global. Left for a follow-up decision given its larger surface
(which structures, which exporters, C++ only vs. also 68000's C89
output as suggested) rather than built unprompted.

## Column-aligned enum/struct output (C++ and 68000), and a real policy decision surfaced along the way

Requested directly from real usage: align member/field names, values,
and comments into consistent columns within each individual enum or
struct block (never globally across the file), for easier reading.
Scope confirmed explicitly: both C++ and 68000's C89 output.

**Implementation**: added `_align_columns()` to export_cpp.py (a
general two-pass helper: collect a block's rows, pad every column
except the last to that column's own widest entry within the block,
join). 68000 imports it from export_cpp.py, matching the project's
existing pattern of sharing utilities between the two rather than
duplicating them.

Applied to four locations in export_cpp.py (struct definitions and
identifier enums, both plain and the _Indexed companion, in both
single-header and split modes) and two in export_68000.py (struct
fields, and the domain #define block, 68000's own functional
equivalent of an enum). Deliberately did NOT touch the one place with
an explicit byte-for-byte compatibility guarantee (generate_header's
default-AoS instance/registry rendering block, which --force-single-
header depends on reproducing exactly) -- confirmed directly that the
protection is specifically on that block, not on struct or enum
definitions, before changing anything.

Validated: real, meaningfully-varying test data (a member name like
`devastating_overhead_strike` forcing genuine column padding, not a
trivial no-op case) confirmed actual alignment in every location.
Confirmed valid, compiling output with real g++17 (C++) and real
gcc -std=c89 -pedantic (68000) -- vbcc itself isn't available in this
sandbox instance, so the 68000 side is verified as valid C89 syntax
directly, not independently re-verified against vbcc specifically,
named precisely rather than rounded up. Full 72-fixture regression
clean.

**Found and fixed real staleness this surfaced**, same category as
before: the alignment change altered actual bytes in several committed
test fixtures with multi-entry domains or multi-field structs.
Regenerated 10 files across export_cpp_test/ and
export_emit_all_domains_test/, each one verified structurally
(whitespace-collapsed diff against the previous committed version) to
confirm only the expected additive changes appeared -- new alignment,
and in a couple of cases the newly-added description comments and a
previously-undiscovered missing §17.5 SchemaTable section, nothing
unrelated. Every real hand-written test depending on these fixtures
re-run and passing. Two other locations (export_binary_test's schema
table tests, export_68000_test's CLI suite) turned out to regenerate
their own fixtures fresh via subprocess on every run, so needed no
manual regeneration, just running them.

**A separate, real bug found in the process, unrelated to alignment**:
`test_68000_cli.py`'s own --help content check was asserting exact
substrings from the *pre-trim* help text (`"repeat for multiple
types"`, `"§8.5"`, etc.) -- stale since the help-text-trim work
several sessions back, never caught because that work's own regression
never ran this particular hand-written CLI suite. Fixed by checking
functional keywords tied to each flag's current, correct meaning
instead of exact old phrasing, so it won't go stale again the next
time wording is lightly adjusted.

**A genuine design question surfaced and resolved, touching earlier,
already-delivered work**: running the real CLI test suites (rather
than just the corpus regression) surfaced that the earlier
check_and_report() fix had conflated two different situations.
resolver.errors (an instance referencing something that flatly doesn't
resolve, no fallback) is genuinely unrecoverable -- that's the actual
bug that fix closed. resolver.reg.duplicate_errors is different: the
registry already has a real, deliberate first-wins policy for a name
collision, confirmed by a pre-existing test (test_multi_file.py's
Check 2, calling compile_multi() directly) that predates this fix and
was never updated for it. The earlier fix silently made a
collision fatal without that distinction being made explicitly.

Decision, discussed and confirmed directly: duplicate names ARE
treated as a hard, build-blocking error, in every case, no exception
for multi-file compilation. Reasoning: §18 multi-file compilation
combines files at the *source* level, a tighter coupling than the
runtime mod-loading story (which uses independently-compiled units
combined only afterward, via hash-based IDs, and is never exposed to
this at all) -- within one compile, a name collision is realistically
almost always a genuine mistake, not a legitimate multi-party
scenario. check_and_report()'s existing behavior (already live) was
confirmed correct as-is, no code change needed there.

What did need updating: two tests still written against the old,
silent-collision-tolerant CLI behavior. test_multi_file.py's
test_shell_independence() and test_68000_cli.py's own version were
both using an overly-broad glob (*.weapon) that happened to also sweep
in weapons/duplicate.weapon, a deliberate, permanent collision fixture
that belongs to a *different* test (test_multi_file.py's own Check 2).
Neither shell-independence test was actually testing duplicate-name
handling at all, their real purpose is proving the program itself
expands glob patterns, not a shell -- narrowed both to base_*.weapon,
a real wildcard that still proves expansion happens, without sweeping
in an unrelated fixture. Confirmed Check 2 itself (the test that
actually owns and exercises the collision) is completely unaffected,
since it calls compile_multi() directly, bypassing check_and_report()
entirely -- the library-level first-wins detection and CLI-level
build-blocking are two different layers, and this whole investigation
only ever touched the second one.

Full regression, every affected test suite, re-run clean after all of
the above: export_golden.py (72/72), test_multi_file.py (5/5),
test_68000_cli.py (6/6), test_binary_export.py, test_schema_table_cpp.py,
and every real hand-written C++ compile+run test in export_cpp_test/
and export_emit_all_domains_test/.

## Error message formatting: [phase N, check] dropped from default output

Requested directly from real usage: the internal phase/check tagging
("[phase 4, duplicate_name]") is genuinely useful for whoever's
working on the compiler itself, but pure noise for someone just using
the language, they want to know what's wrong and where, not which
internal check caught it.

Confirmed first, rather than assumed, that this was a small, contained
fix: phase and check are already separate, structured attributes on
CompileError/CompileWarning (errors.py), never baked into the message
text itself (str(err) already renders as just "line N: message", no
tag at all). The tagging was entirely a formatting-layer addition in
validate.py's print_report()/check_and_report(), nothing structural
needed to change anywhere else.

Added a `verbose` parameter (default False) to both functions. Off:
"{name}: ERROR - {message}", clean. On: the exact original
"{name}: ERROR [phase N, check] - {message}" format, unchanged.
Applied consistently across all four message categories (duplicate
names, warnings, per-instance errors, incomplete/uninitialized), each
one's clean default kept anything genuinely useful (e.g. "incomplete"
still says "export-blocking", that's real information, not internals
jargon) while dropping only the phase/check tag specifically.

Exposed as --verbose-errors on all five exporter CLIs, default off,
wired straight through to check_and_report(). Validated: all four
message categories confirmed correct in both modes via direct function
calls before touching any CLI, then all five exporters individually
re-confirmed through their real CLI in both modes. Clean/successful
compiles confirmed completely silent and unaffected on all five, same
as before. Full regression clean across every affected suite
(72-fixture corpus, multi_file_test, export_68000_test,
export_binary_test).

## flags/bN work, stage 1: bit literals and bitwise operators wired into the expression evaluator

First real work of a new session, picked up cold from
`GDDL_Session_Handover.md` (repo root). State described in that
document reconfirmed against the live repo before touching anything:
all five docs present, `--verbose-errors` present on all five
exporters and `validate.py`, `resolve.py`'s `_TOKEN_RE` still the
pre-flags pattern (nothing had actually been applied yet, matching the
handover's own claim). Working directory was already a clean `dev`
checkout up to date with `origin/dev`, used directly rather than
re-cloning.

**New environment note, not present in the handover doc**: this
session ran natively on the person's Windows machine (PowerShell),
not the Linux/Mac cloud sandbox every prior session in this project
used. `git` was not on PATH by default (found and used the copy
bundled with GitHub Desktop). No g++, gcc, or vbcc toolchain is
present here, and no bash. This does not block today's work (pure
Python, no export code touched) but will matter once the flags
feature reaches Stage 4 (export, all five targets) -- real-toolchain
validation the way this project has always done it will need either
those tools installed here or a return to a sandboxed environment.

**Implementation, the four/five touch points from the handover's
section 4.2, all applied exactly as designed and pre-verified there**:
1. `resolve.py`'s `_TOKEN_RE`: applied the pre-tested regex verbatim,
   adding the `b\d+(?!\w)` bit-literal alternative (before the
   identifier alternative, load-bearing order) and `~|&^` to the
   operator character class.
2. `parser.py`'s `OPERATORS` tuple: extended with `|`, `&`, `^` only,
   not `~`. Checked the one real call site
   (`_classify_statement`, testing `rest[0]` against the tuple to
   recognize an op-statement's leading binary operator) before
   assuming anything -- confirmed this position only ever sees a
   binary operator (`field <op> expr`), `~` never appears there since
   it's unary-only and always appears inside an expression, not as an
   op-statement's own operator token. Doing this blindly as a
   copy-paste would have silently made `field ~ expr` parse as an
   op-statement with operator `~`, which was never a real shape.
3. `resolve.py`'s `_fold_left`: operator tuple extended with `|`, `&`,
   `^`.
4. `resolve.py`'s `_apply_binop`: added the three binary bitwise
   computations, gated behind a real integer-only type check (rejects
   float operands with a precise message naming both operands and the
   operator, matching this project's established error-message bar).
5. `resolve.py`'s `_parse_operand`: added the unary `~` case
   (integer-only, same rejection style) and a `_BIT_LITERAL_RE`
   (`^b(\d+)$`) branch computing `1 << N`, checked before the general
   `_NUMBER_RE` branch since the two patterns never overlap but bN
   needs to resolve to a real value here rather than fall through to
   `_resolve_reference` and fail as an unknown field.

**Validated**, matching the handover's own bar for what "wired
correctly" means, not just "syntactically present":
- Real tokenization run through the actual `resolve.py` file (not a
  standalone re-implementation): 12 cases incl. `b0`, `b0value` (must
  NOT split), `bacon` (must NOT split at all), multi-digit bit
  positions, all four new operators alone and combined, all passed.
- A real end-to-end compile of a tiny fixture combining `b0`, `~`,
  `|`, `&`, `^`, and parens on a plain `u64` field through the full
  parse/resolve/report pipeline (not the exporters, which stage 1
  never touches): computed values confirmed correct by hand
  (`b0|b1|b3` -> `0b1011`, `mask & ~b1` -> `0b1001` turning off bit 1,
  `mask ^ b2` -> `0b1111`, `(b0|b1) & ~b4` -> `0b11`).
- Real error path: a bitwise op against a float-typed field rejected
  with `bitwise operator '|' applied to a non-integer operand: 1.5 | 1
  -- bitwise operators require integer operands`, phase 6.
- Full `export_golden.py` regression: 72/72, zero content diffs
  (see below for a path-separator false-positive this surfaced and
  ruled out).
- `multi_file_test/test_multi_file.py` Checks 1-3 (forward/backward
  references, the deliberate collision, zero-match error paths): all
  PASSED. Check 4 (shell-independence) could not run in this
  environment at all -- see the real, unrelated bug below.

**A real, pre-existing bug found and fixed along the way, unrelated to
flags/bN**: `parser.py`'s `parse_file()` opened source files with
`open(path, "r")`, no explicit encoding, so on this Windows machine's
non-UTF-8 default codepage a source file containing genuine UTF-8
multi-byte characters gets mis-decoded (`cafe with an accent` came out
as `cafÃ©`-style mojibake, silently corrupting content rather than
raising anything). Confirmed this was pre-existing by stashing this
session's changes and re-running the same fixture against unmodified
`dev` -- identical mojibake, so nothing in this session's own edits
introduced it. Also confirmed `combine.py`'s multi-file reader already
opens with `encoding="utf-8"` explicitly -- the correct fix already
existed as an established pattern elsewhere in the codebase, just
never applied to the single-file path. Fixed by adding the same
`encoding="utf-8"` to `parse_file()`. This is exactly the kind of gap
that only ever surfaces on a non-UTF-8-default platform, which is
presumably why 70+ fixtures' worth of prior sessions in a UTF-8-default
Linux/Mac sandbox never hit it. Re-ran the full golden regression after
the fix: the one real content diff dropped to zero, confirming the fix
and ruling out any other cause.

**A false-positive surfaced during regression, investigated and ruled
out, not a real diff**: `export_golden.py` uses `glob`, which on
Windows returns fixture keys with `\` path separators instead of the
committed corpus's `/`. This makes every fixture key differ from the
committed `golden_output.json` in a raw diff even though nothing about
compiled output actually changed. Verified by normalizing separators
in both the freshly regenerated and the git-committed HEAD version and
diffing structurally (same keyset, same per-fixture content) -- zero
real diffs once the platform-specific key format is normalized out.
Did not "fix" `export_golden.py` for this (out of scope for the
current task, and the existing corpus format/committed keys are a
Linux/Mac-sandbox convention this project has always used) -- noting
it here so a future Windows-native session doesn't mistake this for a
real regression again.

**A second, real pre-existing environment gap found, not fixed**:
several hand-written CLI test suites (`multi_file_test/test_multi_file.py`'s
`test_shell_independence`, `export_68000_test/test_68000_cli.py`'s
single-file-invocation check, likely others in the same family)
hardcode Unix-style `/tmp/...` output paths and, in the multi-file
case, also shell out to `bash` directly to simulate quote-handling.
Neither `/tmp` nor `bash` exist on this Windows machine. Confirmed this
is a pre-existing sandbox assumption, not something this session's
changes touched (the failures are `FileNotFoundError` on the literal
`/tmp/...` path, from CLI code this session never edited). Not fixed --
genuinely out of scope for the flags/bN task, and repointing every
`/tmp` reference plus finding a Windows substitute for the bash check
is a real, separate piece of work someone should decide to take on
deliberately. Flagging clearly rather than silently working around it:
**this Windows environment cannot fully run this project's own test
suites as committed**, on top of already lacking every real toolchain
(g++, gcc, vbcc, ACME/64tass/KickAssembler, py65, z80 emulator) the
project's own validation standard requires. Today's work was still
verified to the project's real standard within what stage 1 actually
touches (pure Python expression evaluation, no export code), but this
gap will need resolving, either by installing the missing tools here
or by returning to a sandboxed environment, before Stage 4 (export)
of the flags feature can be done to the same bar as every prior
export-touching change in this project.

**Not yet done, next**: Stage 2 (parsing the `flags` construct itself)
per the handover's own remaining plan. Stage 1 as scoped there is
complete.

## Windows portability pass on the test suite, requested directly

Immediately after the entry above, the person clarified something the
handover doc didn't know: this project moved from Claude.ai cloud
sessions to **Claude Code running locally in VS Code on their own
Windows 10 machine** -- every edit already lands directly in their
real working copy (a real clone of this repo), nothing needs
delivering as a tarball, and the flagged "this Windows environment
cannot fully run this project's own test suites as committed" gap from
the entry above was a real, fixable problem, not just an
environment-mismatch note to live with. Requested directly: port the
Linux-only assumptions to Windows rather than working around them.

**`multi_file_test/test_multi_file.py`**: `test_shell_independence()`'s
hardcoded `/tmp/gddl_multi_file_shell_indep_test.asm` replaced with
`tempfile.gettempdir()`-based path (this project's already-established
`combine.py`/`export_binary.py` convention of using real stdlib
primitives rather than a hand-rolled path join). The bash half of the
same check (real shell present, pattern quoted so that shell can't
expand it, simulating "what actually happens on Windows cmd.exe" per
the check's own original comment) doesn't need simulating on an actual
Windows machine -- it IS that case. Made conditional: `bash -c` with
the exact original single-quoted command if `shutil.which("bash")`
finds one (preserves the exact prior behavior unmodified on any
machine that does have bash), otherwise `subprocess.run(cmd,
shell=True)`, which on Windows invokes `cmd.exe` via `COMSPEC` --
proven correct by realizing cmd.exe/PowerShell never expand `*` for an
external command's arguments regardless of quoting, so this is a
direct test of the real target case, not a workaround standing in for
one. Verified: all 5 checks now PASS end to end on this machine,
including Check 4 specifically, which failed outright before this fix
(`FileNotFoundError` on `/tmp/...`).

**`export_68000_test/test_68000_cli.py`**: seven separate hardcoded
`/tmp/...` literals (every check that writes CLI output somewhere)
replaced the same way, `tempfile.gettempdir()` computed once at module
level. No shell/bash dependency existed in this file already (its own
shell-independence check only ever used list-argv subprocess, no
`shell=True` variant), so only the path fix was needed here. Verified:
all 6 checks now PASS end to end on this machine, all previously
blocked by the same `FileNotFoundError` class of failure.

Both fixes verified by actually running the suites, not just read for
plausibility -- exactly this project's own established bar. Full
`export_golden.py` regression re-run after both fixes: 72/72, zero
content diffs (path-separator false-positive again present and again
ruled out the same way as the entry above; `golden_output.json` left
uncommitted/reverted rather than checked in with corrupted key
separators, same reasoning as before).

**Found, not fixed, flagged rather than silently left**:
`export_z80_c_test/crossover_sweep.py` (a standalone §16.2 spec-table
measurement script, not part of the standard regression set this
project's own conventions call out) hardcodes both a Linux sandbox
path to a specific zsdcc build (`BIN =
"/home/claude/tools/zsdcc-src/sdcc/bin"`) and Unix-style `:`-separated
`PATH` joining, on top of its own `/tmp/crossover` work directory.
Deliberately not touched: fixing the path alone wouldn't make this
script runnable, since the actual zsdcc toolchain it depends on isn't
installed anywhere accessible right now, Windows or otherwise, and
this project's own "verify every claim against real output" standard
means a portability fix that can't actually be run and confirmed isn't
one that should be claimed as done. Whoever picks up real Z80
toolchain installation on this machine should revisit this file
specifically.

Confirmed via a full search of `compiler-python/` for `/tmp/` and
`bash` references that these three files were the complete set --
nothing else in the tree has this class of gap as of this pass.

## Real Z80 toolchain installed and verified on this Windows machine, both dialects

Requested directly, following on from the environment gap flagged two
entries above: get real SjASMPlus and z88dk-z80asm assemble-and-execute
validation actually working here, not just documented as a future
requirement.

**Investigated first rather than assumed**: the prior sandbox sessions
built both assemblers from source (see the "Z80/SjASMPlus real-toolchain
validation setup" and "z88dk-z80asm real-toolchain validation setup"
entries earlier in this file), which needs a C/C++ compiler this
machine doesn't have. Checked both projects' GitHub releases directly
before assuming a source build was the only option: both publish
ready-made Windows binaries --
`sjasmplus-1.23.1.win.zip` (github.com/z00m128/sjasmplus) and
`z88dk-win32-2.4.zip` (github.com/z88dk/z88dk), the latter also
bundling `zsdcc`/`sccz80` (the C compiler `crossover_sweep.py` needs,
flagged as unfixable two entries above -- worth revisiting now that
it's actually available, though not done as part of this entry, out of
scope for what was asked here).

**Installed, not committed**: downloaded both, extracted to
`compiler-python/tools/sjasmplus/sjasmplus.exe` and
`compiler-python/tools/z88dk/z88dk/bin/z88dk-z80asm.exe`. Added
`compiler-python/tools/` to `.gitignore` -- third-party binaries, same
reasoning this project already applied to KickAssembler ("third-party
proprietary freeware, not project source"), except here it's real open
source so redownloading on any machine is trivial rather than needing
a preserved copy. `pip install z80` (the kosarev/z80 CPU emulation
library used for execution) installs cleanly here with no compiler
needed -- confirmed by actually building its wheel, not assumed from
it being "pure Python" on faith.

**A real, pre-existing bug found in `.gitignore` while checking whether
the freshly assembled `.bin`/`.sym`/`.map`/`.o` files would need
cleaning up manually**: every per-test-directory pattern in this file
(`export_cpp_test/*.o`, `export_z80_test/*.bin`, etc., going back to
whenever this file was first written) contains an internal slash,
which git's own ignore rules anchor to the directory the `.gitignore`
file itself lives in -- repo root. The actual directories these
patterns were clearly meant to cover
(`compiler-python/tests/export_z80_test/`, etc.) sit three levels
below that, so none of these patterns have ever actually matched
anything, on any platform, since this file was written. Confirmed
directly with `git check-ignore -v` before and after: exit 1 (not
ignored) on a real generated file beforehand, a real matching pattern
line reported afterward. Fixed by prefixing every nested pattern with
`**/` so each matches at any depth rather than only at repo root; the
three genuinely root-relative lines (`__pycache__/`, `*.pyc`,
`*.code-workspace`, none of which contain an internal slash, plus the
new `compiler-python/tools/` line, which is deliberately anchored)
were left as they already were. This was never specific to Z80 or to
this session's own new files -- it's a real, standing gap that applied
to every test directory's generated build artifacts (C++, 6502, 68000)
the whole time; simply never surfaced before because nobody had
actually inspected `git status` output against a freshly-built tree
closely enough to notice extraneous untracked build artifacts weren't
being filtered.

**Verified real, both dialects, all 8 fixture variants**:
- SjASMPlus: `sjasmplus --raw=<stem>.bin --sym=<stem>.sym <stem>.asm`
  against `test_z80_harness.asm`, `test_z80_soa_harness.asm`,
  `test_z80_string_field_harness.asm`,
  `test_z80_composition_u16_harness.asm` -- all four assembled clean
  (0 errors), all four corresponding `test_z80_*_run.py` checks passed
  against the real `z80` emulator.
- z88dk-z80asm: `z88dk-z80asm -b -m -o<out_stem> <stem>.asm` against
  the `_z88dk` variant of the same four harnesses -- same result, all
  four passed.
- The `Grübnik` string-field check's console output displays as
  mojibake in this PowerShell session (`GrÃ¼bnik`) -- investigated
  directly before assuming it was a real bug like the earlier
  `parser.py` one: `test_z80_string_field_run.py`'s actual check is a
  byte-exact comparison (`result_bytes != expected`, both real UTF-8
  encoded bytes) followed by a real Python string equality
  (`decoded != "Grübnik"`), neither of which touches the console at
  all -- the check genuinely passed (no `SystemExit` raised) before
  the value was ever printed. This is purely this terminal's own
  display codepage misrendering already-correct UTF-8 bytes on the way
  out, not a computation bug -- confirmed by what actually gated
  pass/fail, not by how the output looked.
- Full `export_golden.py` regression re-run after all of the above:
  72/72, zero content diffs (same path-separator false positive as
  every other entry in this pass, ruled out the same way, left
  uncommitted).

**New driver script**, closing the gap the earlier entry flagged (the
existing `test_z80_*_run.py` scripts each assume their `.bin`/`.sym`/
`.map` already exist, with the actual assembler invocation only ever
documented as prose in each script's own docstring):
`export_z80_test/run_all_z80_tests.py`. Runs both dialects against all
four harnesses each, assembling with the real toolchain then invoking
the real check script, one command instead of eight manual ones.
Tool paths default to `compiler-python/tools/` (where this entry's own
downloads landed) with `SJASMPLUS`/`Z88DK_Z80ASM` environment variable
overrides for anyone with the tools elsewhere or on PATH. Confirmed
working end to end, output shown per check exactly as each individual
script already prints it, ending in a single pass/fail summary line
covering all 8.

**Not done, deliberately out of scope for what was asked here**:
revisiting `crossover_sweep.py` now that a real zsdcc is actually
available (flagged two entries above as blocked on exactly this), and
building any equivalent driver/toolchain setup for the 6502
(ACME/64tass/KickAssembler + py65) or 68000 (vbcc + vamos) targets,
which remain unset-up on this machine as of this entry.

## Real 6502 toolchain installed and verified on this Windows machine, all three dialects

Requested directly, same shape as the Z80 entry above: get real
ACME/64tass/KickAssembler assemble-and-execute validation actually
working here. All three dialects' existing `test_6502_*_run.py` scripts
(ACME, `_tass`, `_ka` suffixes) were already real (real assemble, real
`py65` execution) -- same gap as Z80 had, the assembler invocation only
ever documented as prose in each script's own docstring.

**ACME**: official distribution is on SourceForge
(sourceforge.net/projects/acme-crossass), not GitHub -- checked before
assuming a from-source build was needed (this project's prior Linux
sandbox sessions built it from source, but that's a C codebase and this
machine has no C compiler). The `win32/acme0.97win.zip` release asset
is a real, ready `acme.exe`, no compiler needed. Installed at
`compiler-python/tools/acme/acme.exe`.

**64tass**: same SourceForge-hosted shape in principle
(sourceforge.net/projects/tass64), but this specific project's file
host is behind real Cloudflare bot-management (`cf_bm` cookie + 403,
confirmed genuine -- not a simple redirect gate like ACME's project has)
that neither `curl` nor PowerShell's `Invoke-WebRequest` could get
through with any header/mirror combination tried (several were: direct
`-L`, forcing the same mirror ACME's download had succeeded through,
carrying cookies across a two-request session). Worked around by
sourcing the same official binary through OlderGeeks.com, a long-
established clean freeware archive (no bundling, confirmed by
inspecting the extracted contents before trusting it: real GPL/LGPL
license files matching 64tass's actual licensing, the genuine
`README.md`/`manual.pdf`, and real 64tass example `.asm` files) --
version 1.59.3120 rather than the SourceForge page's latest
1.60.3243, one version behind, not pinned to for any technical reason,
just what that mirror happened to host. Installed at
`compiler-python/tools/64tass/64tass.exe`. Confirmed genuinely
equivalent for this project's purposes by real use, not just trusted:
all three real-execution checks that use it passed with correct
computed values.

**KickAssembler**: HANDOFF.md's own prior entries recorded
`theweb.dk` as blocked by the OLD sandbox's network egress proxy,
requiring the person to manually upload a working jar. Checked directly
whether that's still true here rather than assuming it carries over --
it is NOT: `theweb.dk` is fully reachable from this machine (real `curl`
200 responses throughout), so the real `KickAssembler.zip` was
downloaded directly from the primary/official source, no manual upload
needed this time. Got `KickAss.jar` v5.25 -- confirmed the exact same
version number the old sandbox's manually-uploaded copy was, by
coincidence of timing (this project hasn't needed a KickAssembler
update since), not by design. Installed at
`compiler-python/tools/kickassembler/KickAss.jar`.

**A new dependency this project didn't have before**: KickAssembler is
a Java jar, and this machine has no JRE at all (confirmed:
`java` not found). Rather than a full JDK/installer (bigger footprint,
needs an installer with its own permissions/registration), used
Eclipse Temurin's portable JRE 17 Windows x64 zip (via the official
Adoptium GitHub releases, `api.adoptium.net`'s own latest-release API
used to get the exact current download URL rather than guessing a
version string) -- a real, no-install-needed runtime, extracted to
`compiler-python/tools/jre/`. Confirmed working before trusting it:
`java -version` reports a genuine Temurin 17.0.20 build, and the real
`KickAss.jar` runs under it (reports its own real "v5.25 by Mads
Nielsen" banner).

**`py65`** (pure-Python 6502/65C02 emulator, this target's counterpart
to Z80's `z80` PyPI package): `pip install py65` installed cleanly,
same as `z80` did -- confirmed via real `MPU()` instantiation, not just
a successful pip exit code.

**All third-party binaries gitignored, not committed** -- same
reasoning and same `compiler-python/tools/` location as the Z80 entry
above; ACME/64tass/KickAssembler/the JRE are all real, independently
redownloadable open-source or freely-licensed tools, so there's nothing
here that needs preserving the way the old sandbox needed to preserve
its one manually-uploaded KickAssembler copy.

**Verified real, all three dialects, all 9 fixture-variant
combinations** (minimal, string_field, composition_u16, times ACME /
64tass / KickAssembler): every harness assembled clean and every
corresponding `test_6502_*_run.py` check passed against the real `py65`
emulator, including the dispatch/registry-lookup values in the minimal
harness and the exact hp/mp/weapon_power/level values in the
composition+u16 harness. The string-field check's `Grübnik` console
output shows the same PowerShell-codepage mojibake noted in the Z80
entry above -- confirmed the same way: the actual pass/fail gate is a
byte-exact comparison and a real Python string equality, neither of
which touches the console, so this is display-only, not a computation
bug.

**A real, pre-existing `.gitignore` gap found and fixed while checking
generated artifacts**: `**/export_6502_test/*.lst` (64tass's `-l`
label-list output) had no pattern at all -- the existing entries
covered `.bin`/`.sym`/`.prg`/`.labels`/`*labels*.txt` (ACME and
KickAssembler's output shapes) but 64tass's own `.lst` extension was
simply never added, unrelated to the anchoring bug fixed in the entry
above (this one was a real missing pattern, not a broken one). Added.

**New driver script**, same role and shape as
`export_z80_test/run_all_z80_tests.py`:
`export_6502_test/run_all_6502_tests.py`. Runs all three dialects
against all three fixture variants each (9 total), assembling with the
real toolchain then invoking the real check script. Tool paths default
to `compiler-python/tools/` with `ACME`/`TASS64`/`KICKASS_JAR`/`JAVA`
environment variable overrides. Confirmed working end to end, single
pass/fail summary line covering all 9.

**Found, not fixed, flagged rather than silently left**: this
directory also has `test_6502_soa_harness.asm` (plus `_tass`/`_ka`
variants) and their `generated_6502_soa*.asm` counterparts committed,
but no corresponding `test_6502_soa*_run.py` check script exists at
all, unlike every other fixture group here and unlike Z80 (which does
have a working `test_z80_soa_run.py`). Not clear from anything in this
file whether that's an intentionally incomplete/abandoned fixture or a
genuine gap -- searched `HANDOFF.md` for any prior mention of 6502 SoA
and found none. Not built here, deliberately: writing a new test
script is a different kind of task than getting the existing ones
running, and this was never asked for. Worth a real decision from
whoever owns this next, not a silent assumption either way.

Full `export_golden.py` regression re-run after all of the above:
72/72, zero content diffs (same path-separator false positive as every
other entry in this pass, ruled out the same way, left uncommitted).

## Real 68000 toolchain installed and verified on this Windows machine (vbcc + vamos, AmigaOS)

Requested directly, same shape as the Z80 and 6502 entries above.
Unlike those two, `vbcc`'s own official distribution host
(`sun.hasenbraten.de`, file host `phoenix.owl.de`) is one of the exact
hostnames the earlier "68000/vbcc real-toolchain validation setup"
section already named as blocked by the OLD sandbox's egress proxy
(same host list the EmuTOS/TOS search covered) -- checked directly
rather than assumed to still apply here: both are fully reachable from
this machine (real `curl` 200 responses throughout), so the real
official binaries were used directly, no from-source rebuild needed
this time (the prior sessions' two build paths -- a user-uploaded
prebuilt Linux archive, or building `erique/vbcc_vasm_vlink` from
source -- are both Linux-specific and moot here regardless).

**vbcc host binary**: `vbcc_bin_win64.zip` from the official archive
(`phoenix.owl.de/vbcc/2022-03-23/`, the most recent dated release that
still included a win64 asset -- the newer `2022-05-22` release only
published target archives, no host binary, confirmed by checking
before downloading rather than assuming the latest dated folder has
everything). A real Windows-native zip -- `vc.exe`, `vbccm68k.exe`,
`vasmm68k_mot.exe`, `vlink.exe`, and the target config profiles
(`config/aos68k` etc.) all bundled together, no compiler needed to
build anything. Installed at `compiler-python/tools/vbcc/`.

**vbcc target files** (system headers/libs/startup code for
`+aos68k`): a separate download, `vbcc_target_m68k-amigaos.lha` --
**only ever distributed as `.lha`** (Amiga's native archive format,
confirmed by checking the actual file listing rather than assuming a
`.zip` alternative exists the way the Atari target happens to have
one). No LHA extraction tool exists on this machine by default, and
`7z.exe`/`winget` were not viable in the time available (`winget`
requires an interactive MS Store terms prompt this non-interactive
session can't answer even with `--accept-source-agreements`, and a
backgrounded `winget install 7zip.7zip` attempt was abandoned once a
faster path was found, not left dangling -- stopped explicitly with
`TaskStop` rather than silently orphaned). Used GnuWin32's standalone
`lha.exe` port instead (`gnuwin32.sourceforge.net/packages/lha.htm`,
real download via `prdownloads.sourceforge.net` -> a real mirror,
worked cleanly with no Cloudflare friction unlike the 64tass case in
the entry above). Extracted with `lha.exe x`, then moved the real
payload up one level to match vbcc's expected
`<VBCC>/targets/m68k-amigaos/{include,lib}` layout -- the archive's
own internal structure nests it one level deeper
(`vbcc_target_m68k-amigaos/targets/m68k-amigaos/...`), confirmed by
inspecting the actual extracted tree rather than assuming the vendor
archive's layout matches the destination layout. `lha.exe` itself
installed at `compiler-python/tools/lha/` -- useful as a general LHA
extractor for any future need, not just this one archive.

**A real, non-obvious invocation requirement, found by hitting it, not
by reading docs first**: `vc.exe` needs `VBCC` set as a real Windows
*environment variable*, not just a value baked into the command
Python constructs -- the aos68k config file's paths are written as
`%%VBCC%%/targets/...`, which the config-file templating layer turns
into a literal `%VBCC%` string in the commands `vc.exe` shells out to
`vbccm68k`/`vlink` with, relying on the OS's own environment-variable
substitution to resolve it at that point. The very first driver-script
attempt only set `PATH`, not `VBCC`, in the subprocess environment --
compiling failed outright with `No config file!` before it even got to
the missing-substitution problem. Fixed by explicitly setting
`env["VBCC"]` (not just relying on it being inherited from the parent
shell, which won't be true for whoever runs this driver without having
manually exported it first).

**A second real bug, found the same way**: passing `-I.` (matching
what the two existing `run_*_test.sh` scripts already used, written
for bash) made `vc.exe` silently drop the flag and leak a bare `.` into
the `vlink` command as if it were an input object file to link --
confirmed directly (the failing `vlink` invocation showed `"."` sitting
where an object filename belongs, and `vamos` then failed to load the
resulting non-binary "executable"). Not investigated further as a
`vc.exe`-internals bug since it didn't need to be: every one of this
directory's test `.c` files uses a *quoted* `#include "generated_...h"`
already, which the C standard already resolves relative to the
including file's own directory before ever consulting `-I` -- so `-I.`
was always redundant here, on any platform. Fixed by dropping it
entirely rather than chasing why Windows `vc.exe` mishandles a flag
the Linux build apparently accepted; confirmed compiling and linking
cleanly without it.

**`vamos`** (from `amitools`, unchanged from the documented setup):
`pip install amitools` alone pulls the newest `machine68k` (0.4.1 as
of this check, same drift the original setup notes already warned
about), which breaks `vamos` the same documented way. Re-confirmed the
documented fix still applies here: `pip install "machine68k==0.3.0"
--force-reinstall` (no `--break-system-packages` needed on this
machine's Python, unlike the original Linux/apt-managed Python that
flag existed for). Both packages installed cleanly with real compiled
wheels, confirmed via real `MPU`/`Z80Machine`-style instantiation
before trusting either -- same discipline as `z80`/`py65` in the
entries above.

**Smoke-tested exactly like the original setup notes did, before
trusting any of this for real fixtures**: a real `hello, world` C
program (`printf`, not the trivial `return 42` first attempt -- which
actually surfaced its own unrelated PowerShell mistake, `Write-Host`
piped into `Out-File` producing a genuinely empty source file, caught
by checking the file's actual byte length rather than assuming the
write succeeded), compiled with `vc +aos68k`, run under `vamos`,
printed `hello, world` correctly.

**Verified real, all four existing fixture pairs**: `vc +aos68k
<test>.c <generated>.c -o <stem>` then `vamos <stem>`, matching the two
already-committed `run_composition_u16_test.sh` /
`run_subset_request_bug_test.sh` recipes exactly (minus the redundant
`-I.`), plus the two that never had a committed script at all
(`test_68000_soa.c` + `generated_68000_soa.c`, `test_68000_aos_split.c`
+ `generated_68000_minimal.c`) -- all four compiled clean and all four
printed their own real pass line (`hp=60000 mp=12000 weapon_power=500
level=42`, `rarity=0 object.weight=5`, the SoA and AoS width/string
pass lines), `vamos` propagating exit code 0 in every case, confirmed
via the driver script's own exit-code check, not just eyeballing
stdout.

**New driver script**, same role and shape as the Z80/6502 ones:
`export_68000_test/run_all_68000_tests.py`. Runs all four fixture
pairs, compiling with real `vc +aos68k` then executing with real
`vamos`. Tool paths default to `compiler-python/tools/` with
`VBCC`/`VAMOS` environment variable overrides. Confirmed working end
to end, single pass/fail summary line covering all 4.

**Deliberately out of scope, matching the original setup notes' own
conclusion**: the Atari/`hatari`/EmuTOS path. The original 68000/vbcc
setup section explicitly concluded AmigaOS/`vamos` alone is sufficient
real validation ("the task only required real compile + real execution
on *some* 68000 environment... without needing the Atari/`hatari`/
EmuTOS path too") -- nothing here revisits that conclusion, and
`run_atari_test.sh` remains exactly as documented, untouched, for
whoever picks up Atari/TOS coverage specifically as a deliberate
choice later.

**A real, pre-existing `.gitignore` gap found and fixed, same class as
the 6502 `.lst` one above**: `test_68000_composition_u16` and
`test_68000_subset_request_bug` (the two fixture pairs that already
had a committed `.sh` recipe) had no matching ignore entry at all --
only `test_68000_minimal`/`test_68000_aos_split`/`test_68000_soa` were
listed, by exact binary name (this target's compiled output has no
extension at all under AmigaOS, so the existing `*.o` pattern doesn't
cover it either). Added both missing exact-name entries.

Full `export_golden.py` regression re-run after all of the above:
72/72, zero content diffs (same path-separator false positive as every
other entry in this pass, ruled out the same way, left uncommitted).

## Real C++ toolchain installed and verified on this Windows machine (MSVC, not g++)

Requested directly, same shape as every entry above, but a genuinely
different toolchain: this machine has no g++ (every prior session in
this project's whole history validated C++ output with real g++17
specifically), but does have Visual Studio 2022 and Visual Studio 18
already installed, both with the C++ workload -- confirmed via
`vswhere.exe` before doing anything else rather than assumed from the
person's own statement, per this project's standing "verify before
recommending" discipline: real `MSVC.Component.VC.Tools.x86.x64`,
`cl.exe` 19.50 under VS 18. Used MSVC (`/std:c++17 /EHsc`) rather than
attempting to install a second, redundant compiler -- GDDL's generated
headers are portable standard C++, not GCC-specific, so this is a
genuine independent-compiler validation, not a lesser substitute for
g++.

**No committed build recipe existed for this directory at all**,
unlike every other export target (Z80/6502/68000 each had at least a
docstring-documented command, some had real `.sh` scripts). Every
prior HANDOFF.md mention of C++ validation says "real g++17" but never
preserves an actual invocation. The (sources, output name) groupings
for all 16 real test binaries were reconstructed directly from each
`.cpp` file's own `#include`/`int main()` presence, not guessed --
confirmed each grouping compiles and links cleanly before trusting it,
same as the exact-command reconstructions in the Z80/6502/68000
entries above. Three of the sixteen
(`test_generated_composition_nested_u16_fields[.cpp/_single.cpp]`,
`test_generated_scaleup2.cpp`) had no `.gitignore` entry at all,
same "validated once, ad hoc, binary manually deleted before anyone
ran `git status`" pattern already seen in the 6502/68000 entries above
-- not a sign anything is wrong with them, confirmed by building and
running all three cleanly.

**Two real Windows-Python subprocess bugs found and fixed, neither
specific to this project's code, both worth remembering generally**:
- `vcvars64.bat` (via its nested `vsdevcmd.bat`) sets the PATH variable
  as `Path` (mixed case), not `PATH` -- Windows env vars are
  case-insensitive at the OS level, so this is invisible when working
  interactively, but a naive Python `dict(os.environ)` merge that
  blindly does `env[k] = v` for a captured `Path` line leaves BOTH
  `PATH` (stale, no VC directories, inherited from Python's own launch
  environment) and `Path` (correct) as separate dict keys.
  `_winapi.CreateProcess`'s handling of an environment block with two
  differently-cased duplicates of the same logical variable is
  unreliable -- confirmed directly: the stale one silently won,
  `cl.exe` was never found despite the captured environment genuinely
  containing its directory. Fixed by deleting any existing key that
  matches case-insensitively before inserting the freshly captured
  one, in `run_all_cpp_tests.py`'s `_msvc_env()`.
- **Separately**, even after that fix, `subprocess.run(["cl.exe", ...],
  env=custom_env)` still raised `FileNotFoundError`. Root cause,
  confirmed by direct, isolated testing rather than assumed: when a
  bare executable name (no path separator) is given, Python's
  `subprocess`/`_winapi.CreateProcess` resolves it against the
  *calling* process's own `os.environ["PATH"]` for the initial lookup,
  never the custom `env=` dict that's about to be handed to the child
  -- confirmed by testing the exact same call with a plain, correct
  `env` dict in isolation, still failing the same way. Not a bug
  specific to this project; a general, easy-to-hit Python-on-Windows
  gotcha whenever a subprocess needs a PATH different from the
  parent's own. Fixed by resolving `cl.exe`'s real absolute path
  ourselves (`_resolve_on_path()`, walking the captured `Path` value
  directly) and passing that instead of the bare name.
- **A third, unrelated MSVC-specific flag issue**: `/Fo:<name>.` (meant
  to namespace each test's `.obj` file by test name, avoiding
  collisions across sequential compiles) is only valid for a
  single-source compile -- MSVC rejects it outright
  (`D8036: not allowed with multiple source files`) for the
  cross-translation-unit and split-mode cases, which pass two `.cpp`
  files to one `cl.exe` invocation. Dropped `/Fo` entirely rather than
  branching the flag per case; confirmed no real basename collision
  exists across this directory's actual 16 cases before relying on
  the default per-source `.obj` naming being safe.

**A real, unrelated mistake caught and cleaned up, not left behind**:
the very first smoke-test compile (a trivial `hello.cpp`, done before
any of the driver script existed, to confirm `cl.exe` itself works at
all) was run with the working directory still at the repo root,
leaking a stray `hello.obj` there -- caught by running `git status`
before considering this work done (this project's own standing
convention: review what's about to be committed), not because
anything flagged it automatically. Deleted; confirmed gone via a
second `git status`.

**Verified real, all 16 binaries**: every one compiled clean under
`/std:c++17 /EHsc` and ran with exit code 0, each printing its own
real pass line (or, for `test_bsearch_large_constexpr`, correctly
printing nothing at all -- that file's checks are 100% `static_assert`,
compile-time only, `main()` just returns 0, confirmed by reading the
source rather than assuming silence meant something was swallowed).

**New driver script**, same role and shape as the Z80/6502/68000 ones:
`export_cpp_test/run_all_cpp_tests.py`. Locates the VS installation via
`vswhere.exe` (overridable via `VCVARS64`), captures the MSVC
environment once (not once per compile, avoiding vcvars64.bat's own
real startup cost 16 times over), then compiles and runs all 16 cases.
Confirmed working end to end, single pass/fail summary line covering
all 16.

**A real, pre-existing `.gitignore` gap found and fixed, same class as
the 6502/68000 ones above, but with a twist specific to this
toolchain switch**: the existing entries were exact bare binary names
(`test_generated_minimal`, etc.) plus a `*.o` pattern -- both written
for g++'s Linux/no-extension-executable, `.o`-object convention. MSVC
uses `.exe` and `.obj` instead, so every single existing pattern in
this section silently failed to match anything this session's compiles
produced, on top of the three missing-entirely names already noted
above. Added blanket `**/export_cpp_test/*.obj` and
`**/export_cpp_test/*.exe` patterns (covering all 16 outputs, present
and future, rather than sixteen more exact-name lines) alongside the
existing bare-name entries, which are left in place unmodified --
still correct and still useful for a future Linux-hosted g++ session
on this same repo.

Full `export_golden.py` regression re-run after all of the above:
72/72, zero content diffs (same path-separator false positive as every
other entry in this pass, ruled out the same way, left uncommitted).

**This closes out real-toolchain validation for all five GDDL export
targets on this Windows machine** (C++, 6502, Z80, 68000/AmigaOS, plus
the portable binary format which never needed a toolchain at all) --
every target this project's own standard requires "real compile/
assemble + real execute, not just should work" for now has a working,
driver-scripted path here.

## flags/bN work, stage 2: parsing the `flags` construct itself

Picked back up on the actual `flags`/`bN` feature (deferred while the
Windows toolchain work above happened) at exactly the point
`GDDL_Session_Handover.md` left it: stage 1 (bit literals, bitwise
operators in the expression evaluator) confirmed still complete and
untouched by grepping for any existing `flags`-construct parsing first
(found none -- the only hits were unrelated CLI-flag terminology in
`export_z80.py`/`export_cpp.py`), then moved on to stage 2 exactly as
scoped there: real new grammar, not a copy of `identifier`'s.

**New AST nodes** (`ast_nodes.py`): `FlagsBlock` (name, required
`width` -- unlike `IdentifierBlock.width`, which is optional since
identifier has a non-indexed default form; `flags` has no such
fallback, the whole point of the construct is a real addressable bit
width, so width is mandatory) and `FlagsEntry` (name, `kind` one of
`'auto'`/`'bit'`/`'number'`, plus whichever of `explicit_bit`/
`explicit_number` applies). Deliberately does NOT decide which bit an
`'auto'` member actually claims, or check for claim collisions, or
check width-vs-member-count overflow -- all three need to see every
entry in the domain together, which is stage 3's job (registration),
not a single-entry parse's.

**Parsing** (`parser.py`): `_parse_flags_block` (header:
`flags Name WidthType`, exactly 3 tokens, width checked against the
same u8/u16/u32/u64 closed set `identifier`'s width already uses) and
`_parse_flags_entries` (body: three shapes per line, mirroring
`_parse_identifier_entries`'s indentation-handling structure but with
genuinely different per-line grammar). Reused `_require_field_name`
(already used for op-statement/assign-statement leading identifiers)
for member names -- confirmed this is stricter than `identifier`'s own
key parsing, which doesn't validate key shape at all today; not fixed
here (out of scope, a pre-existing identifier-parsing gap, not
something stage 2 of flags should touch), but deliberately not
repeated for `flags`, since member names become real export-target
identifiers (C++ member names, assembly constants) where a
malformed one would only surface as a confusing downstream export
failure instead of a precise, immediate parse error.

**A real scope-boundary decision, not left implicit**: whether
`= NUMBER` should accept any non-negative integer (deferring "must
actually be 0" to stage 3) or only the literal `0` (rejecting anything
else right here, at parse time). Went with the latter -- re-reading the
handover doc's own spec text closely ("every member's value is a
single bit or zero, no exceptions in this first pass") shows the
third shape isn't "= any NUMBER", it's specifically "= 0"; accepting
other numbers here would silently produce wrong behavior (no stage 3
exists yet to catch `foo = 5`) rather than a clear, immediate parse
error, for a value that was never going to be legal regardless of
which phase catches it.

**Validated**: real parse of the reference `Entity.gddl` file's own
`flags ComponentFlags u64` block (handover doc section 6, byte-for-byte
verbatim) -- `none = 0` (kind='number'), `is_damageable = b0`
(kind='bit', bit=0), and the five bare auto-assigned members all
parsed into exactly the expected shape, checked field-by-field, not
just "didn't crash". Six real error-path cases, all correctly
rejected with precise messages: missing width, invalid width token,
non-zero/non-bN number, malformed bit literal (`bfoo`), a stray second
`=` on one line, and an invalid member name. Full `export_golden.py`
regression: 72/72, zero content diffs (structural comparison,
path-separator false positive ruled out the same way as every entry
in the Windows-portability pass above).

**A real, pre-existing gap found while testing the full pipeline with
a `flags` block present, confirmed NOT caused by this stage's work**:
since `registry.py`'s `Registry.__init__` only recognizes
`IdentifierBlock`/`DefineBlock`/`InstanceDecl` nodes, a `FlagsBlock`
is currently just silently skipped -- expected at this point (stage 3
is what registers it), so a field typed `= ComponentFlags` doesn't
raise "unknown type" the way you might expect, it just resolves
whatever value was assigned with no complaint at all. Checked directly
whether this is specific to `flags` or a wider gap: a field typed with
a totally unrelated, never-declared bogus type name (`TotallyBogusUndefinedType`)
behaves identically -- resolves fine, no error. **This is a
pre-existing characteristic of the current implementation, not
something stage 2 introduced or regressed**: field types are
apparently not validated against a closed registry of known
identifier/define names at general assignment time today, at least
not for scalar-looking values. Not fixed here (genuinely out of scope
for "parse the flags construct"), but worth stage 3 knowing about
directly: the "reject bitwise on non-flags-typed fields" / "reject
arithmetic on flags-typed fields" checks stage 3 needs to build will
require real field-type awareness that doesn't obviously already exist
for arbitrary field types today, not just wiring up `flags` specifically.

**Not yet done, next**: stage 3 (registry and resolution logic --
bit-claim tracking with auto-assignment and duplicate-claim detection,
width-overflow check, reject-arithmetic-on-flags /
reject-bitwise-on-non-flags, op-statement support confirmation for
flags fields), per the handover doc's own remaining plan. Stage 2 as
scoped there is complete.

## flags/bN work, stage 3: registry and resolution logic

Picked up immediately after stage 2, same session. Scope exactly as
the handover doc listed: bit-claim tracking (auto-assignment +
duplicate-claim detection), width-overflow, reject-arithmetic-on-flags
/ reject-bitwise-on-non-flags, and confirming op-statement support on
flags fields actually works.

**`registry.py`**: `FlagsBlock` nodes are now actually registered
(previously silently skipped -- the real, pre-existing gap flagged
explicitly at the end of the stage 2 entry above). New state:
`self.flags` (name -> node, own namespace, no cross-check against
`identifiers`/`defines`, matching this file's own documented policy
that namespace collision detection is deliberately per-construct only)
and `self.flags_values` ((domain, member) -> resolved int, 0 for the
none/zero sentinel or 1 << claimed-bit otherwise). Duplicate domain
names and duplicate member names both follow the exact first-wins,
collect-and-continue pattern `identifier` already established.

**Bit-claim algorithm** (`_assign_flags_bits`), the real heart of this
stage: two passes, not one, and this is load-bearing, not a style
choice. Pass 1 collects EVERY explicit `= bN` claim across the whole
domain first (catching an out-of-width position, or two members
claiming the same bit, as real phase-4 errors). Only after that full
picture exists does pass 2 walk the auto-assigned members in
declaration order, each one skipping every bit pass 1 already claimed
-- domain-wide, not just claims seen earlier in the file. This is what
the spec's own wording actually requires ("auto-assigns the next
UNCLAIMED bit") and it has a real consequence worth stating precisely:
explicit-vs-auto and auto-vs-auto collisions are structurally
impossible by this construction, not just individually guarded against
-- the auto cursor can never land on a bit that's either explicitly
claimed anywhere in the domain or already handed to an earlier auto
member. The only collision that can actually occur is
explicit-vs-explicit (two members both writing the same `bN`), which
pass 1 catches directly. Proved this isn't just true in the easy
ordering: a real fixture with an explicit claim placed AFTER two auto
members that a naive single-pass left-to-right algorithm would have
let grab that bit first -- confirmed directly (not assumed from reading
the algorithm) that the auto members correctly land on the NEXT bits
instead, computed values checked individually, not just "no crash".

**Width-overflow**, explicitly noted in the handover doc as reusing
`identifier`'s `indexed_width_overflow` "shape" but NOT its formula --
confirmed this distinction mattered before writing anything: identifier's
check is `entry_count > 2**bits` (a dense index can address up to
2^bits distinct values), but flags is a bitmask, so the real capacity
is `bits` addressable positions, not `2**bits`. Two separate checks
followed from this, not one: `flags_bit_exceeds_width` (an individual
explicit `bN` where N >= the domain's own bit count) and
`flags_width_overflow` (an auto member with no unclaimed bit left
within the domain's bit count) -- different failure shapes, both real,
neither reducible to the other.

**Field-category integration**: `field_category()` gained a fourth
category, `'flags'`, returned when the field's type token names a
known flags domain -- inserted after the existing `identifier` check,
before the final scalar fallback. This directly closes the real,
pre-existing gap the stage 2 entry above flagged explicitly (a
flags-typed field silently falling into 'scalar' with no type
awareness at all, identical to what already happened for any
undefined type name) -- confirmed closed by re-running the exact same
repro from that entry (`component_flags = 0` on a `ComponentFlags`
field) and confirming it now round-trips through real flags-specific
coercion instead of silently succeeding as an untyped scalar.

**Numeric coercion/range enforcement for flags fields**: reused
`_coerce_numeric`/`_check_range` completely unmodified -- a flags
field's real "type" for range-check purposes is its declared WIDTH
(u8/u16/u32/u64), which those functions already understand perfectly;
the two call sites in `_apply_assign`/`_apply_op` just substitute
`registry.get_flags_width(domain)` for the domain name before calling
them, rather than teaching those functions a new vocabulary. Confirmed
this is the right layer for it: a flags value is a plain unsigned
integer of a known width, nothing about range enforcement is
flags-specific.

**Arithmetic/bitwise gating by field kind**, threaded through the
whole expression evaluator (`_eval_expr`, `_eval_op_expr`,
`_parse_expr_tokens`, `_fold_left`, `_parse_operand`, `_apply_binop`)
via a new `is_flags` parameter, constant across one expression's whole
evaluation (parens included) since it describes the field being
assigned, not any individual sub-term. `_apply_binop` centralizes the
binary-operator check (arithmetic rejected when `is_flags`, bitwise
rejected when not) so both the op-statement's own leading operator and
every operator `_fold_left` walks afterward go through exactly one
check, not two separately-maintained copies. Unary `-`/`+`/`~` gated
directly in `_parse_operand`, same reasoning: unary arithmetic is just
as much "arithmetic" as binary for this rule, and unary `~` is
bitwise-only in both directions like every other bitwise operator.

**`OpStmt` category gate widened, two places, both real, both would
have silently broken flags op-statement support otherwise**:
`resolve.py`'s `_apply_op` (`category != "scalar"` -> `category not in
("scalar", "flags")`) and `phase5.py`'s static `field_shape` check
(the exact same widening, phase 5 runs before phase 6 and would have
rejected a flags op-statement before resolution ever got the chance
to). Found the phase5.py one by deliberately checking every existing
`== "scalar"` / `!= "scalar"` site project-wide (`grep`) before
declaring this done, not by waiting for a test to fail -- confirmed
these two were the complete set.

**`Domain.member` dot-access for flags**, `_resolve_reference`'s third
branch (after struct-field-on-current-scope, then `identifier`
domains): looks up `self.reg.flags_values`, resolving directly to the
member's real int value (not an `IdentifierRef` wrapper -- flags
values ARE the raw combinable integer, there's no hash/index duality
to carry the way identifier has). The `0`/none-sentinel case is
real and deliberately distinguished from "no such member" with an
explicit `is None` check on the lookup, not a truthiness check that
would have wrongly rejected a legitimate zero value.

**Validated, real pipeline runs, not just read for plausibility**:
- The reference `Entity.gddl` file's exact `ComponentFlags u64` domain
  (handover doc section 6, byte-for-byte): all 9 members' computed
  values checked individually against hand-derived expected values
  (`none=0`, `is_damageable=1` ... `is_attack=128`) -- exact match.
- A `copy-a-base-then-turn-on/off-one-more-flag` scenario end to end
  (the exact motivating case stage 3 was asked to confirm): an
  instance combining two flags via `|` at assign time, a descendant
  instance clearing one via an op-statement (`& ~ComponentFlags.is_controllable`)
  -- both computed values checked, both correct.
- A parenthesized combining expression mixing `Domain.member` dot
  references with `|`/`&`/`~` in one line -- correct.
- The late-explicit-claim reordering fixture described above --
  correct, checked per-member, not just "compiled without error".
- Eight real error-path fixtures: explicit-vs-explicit bit collision,
  bit position exceeding declared width, width overflow from too many
  auto members, arithmetic op-statement on a flags field, arithmetic
  embedded inside a flags assign-expression, bitwise op-statement on a
  non-flags field, bitwise embedded inside a non-flags assign
  expression, and unary `~` on a non-flags field -- all eight correctly
  rejected with precise, distinct messages naming the actual operator
  and field-kind involved, not a generic failure.
- Full `export_golden.py` regression: 72/72, zero content diffs
  (structural comparison, path-separator false positive ruled out the
  same way as every Windows-portability entry above). Also re-ran
  `multi_file_test/test_multi_file.py` and
  `export_68000_test/test_68000_cli.py` in full, both still 100%
  passing -- touched shared pipeline code (`registry.py`, `resolve.py`,
  `phase5.py`), so this wasn't assumed safe from the golden corpus
  alone.

**Not yet done, next**: stage 4 (export, all five targets -- C++
shape already fully designed and compile-tested in the handover doc's
section 4.3; 6502/Z80/68000/binary as plain integer constants, same
shape `identifier` domains already use on those targets). Real
toolchain validation for stage 4 is now actually possible on this
machine for every target (see the Windows real-toolchain entries
above) -- unlike when this feature was first designed. Stage 3 as
scoped in the handover doc is complete.

## flags/bN work, stage 4: export, all five targets

Picked up immediately after stage 3, same session. Every one of the
five real toolchains set up earlier this session (MSVC, ACME/64tass/
KickAssembler, SjASMPlus/z88dk-z80asm, vbcc+vamos) got used for real
here, not just the pure-Python pipeline stages -- this is the first
`flags` stage where that setup work actually paid off directly.

**C++ (`export_cpp.py`)**: the settled `namespace Domain { constexpr
WIDTH member = ...; }` shape (handover doc §4.3, already compile-tested
there against three alternatives before this session ever started) --
new shared `_render_flags_namespace()` helper, called from both
`generate_header` and `generate_split` (the namespace's own content
never differs between single-header and split modes; C++ has no way to
split a namespace's constexpr definitions from their values anyway, so
both modes emit it into the header). `_cpp_field_type` gained a real,
deliberate distinction from how it already handles `identifier`: a
flags-typed field becomes the domain's raw WIDTH type directly
(`uint64_t` etc.), never the domain name itself -- there is no flags
"type" in the emitted C++ at all, unlike identifier's `enum class`.
The shared §17.4 schema computation (`_leaf_binary_kind`, used by BOTH
this module's own §17.5 compile-time table AND `export_binary.py`)
needed one addition -- a flags field packs exactly like an ordinary
scalar of its own width, no logical-ID/indexed duality to preserve
(flags never had one). Fixing this one shared function unlocked both
consumers at once, exactly the reason it lives in one place instead of
two.

**A real correctness bug found and fixed in `_cpp_value_literal`,
not just a style gap**: the existing `ULL`/`LL` suffix logic checked
`t in ("u64",)` literally -- but a flags-typed field's declared type
(`t`) is the domain name, not `"u64"`, so a u64-width flags value at
or above 2**63 (a legitimate value -- e.g. a claimed high bit) would
have rendered as a bare, unsuffixed decimal literal. Real C++ decimal
integer literals without a suffix only ever get a SIGNED type
candidate (int/long/long long); a value that doesn't fit any of those
is rejected or mishandled by real compilers, not silently accepted.
Fixed by resolving a flags field's real width before deciding on a
suffix, same reasoning `u64`/`i64` already use.

**A separate, real, pre-existing bug found while verifying C++ output
on this machine, affecting ALL FIVE exporters, not just this feature**:
every exporter's actual file-writing code (`open(path, "w")`, the CLI
paths that produce real `.h`/`.cpp`/`.asm`/`.c`/`.json` output) had no
explicit `encoding="utf-8"`, the exact write-side counterpart of the
`parser.py` read-side bug fixed earlier this session. Confirmed real,
not assumed: a generated header containing a real `§` character (the
§17.5 schema-table comment) came out corrupted on this Windows
machine's non-UTF-8 default codepage -- confirmed at the byte level
(decoding the written file's raw bytes as UTF-8 produced mojibake,
not just a display artifact) before and after the fix. Sweep was
project-wide, not scoped to what this session happened to touch:
grepped every `open(` call across `gddl/` and added `encoding="utf-8"`
to every text-mode write across `export_cpp.py` (3 sites),
`export_68000.py` (2), `export_6502.py` (1), `export_z80.py` (2), and
`export_binary.py`'s `.gddlmeta.json` writer (1) -- the one `"wb"`
binary-mode write in `export_binary.py` correctly left untouched, no
text encoding concept applies to it. This would have silently
corrupted non-ASCII content (§ references, any description text with
accented characters) in every real exported file on this machine
before today, for any prior export, flags-related or not.

**6502/Z80/68000, one shared design decision across all three**:
reused each target's existing `DomainInfo` dataclass for flags domains
too (`members` holds each entry's real bit-claim value instead of a
dense index), rather than threading a new, separate return value
through `gather_ir`. Added one field, `kind: str = "identifier"`
(default preserves every existing call site's behavior unmodified,
including the real, committed test files calling `gather_ir` directly
-- `test_6502_zp_validation.py`, `test_68000_cli.py` -- checked before
assuming a signature change was safe, confirmed a 3-tuple return would
have broken them). Flags `DomainInfo`s are appended into the SAME
`domains` list every renderer already loops over; `kind` tells each
renderer to skip the identifier-only jump-table/Dispatch machinery
(flags fields are combinable data, never dispatched to a handler) and
just emit the plain constant lines the exact same `for key, value in
d.members` loop already produces. This is why the diff per renderer is
small (one `if d.kind != "identifier":` branch each) despite covering
six renderer files.

- **6502**: `gather_flags_domain_info` (mirrors `gather_domain_info`),
  wired into `gather_ir`. `allocate_zero_page` updated to skip
  dispatch-block allocation for flags domains specifically -- zero
  page is small and contested (§10.2's own stated reason for requiring
  `--zp-base` at all); allocating a pointer never used would have
  wasted it. All three dialect renderers (ACME, 64tass, KickAssembler)
  updated identically. `domain_widths` (used by `_leaf_directive` for
  storage-directive width lookups) already gets flags widths for free,
  since it's built generically from whatever's in `domains` -- no
  changes needed there at all.
- **Z80**: same `DomainInfo.kind`/`gather_flags_domain_info` pattern,
  wired into `gather_ir`. Both real dialect renderers (SjASMPlus,
  z88dk-z80asm) updated identically. The third renderer,
  `export_z80_z88dk_c.py` (C-mode), needed ZERO changes -- confirmed
  by reading it, not assumed: its own domain-constant loop already
  emits plain `#define`s with no jump-table/dispatch concept at all,
  so it was already flags-correct the moment the shared IR started
  feeding it flags domains.
- **68000**: the one target where flags needed a REAL divergence from
  the shared pattern, not just a skip-the-dispatch branch -- identifier
  domains get their own C89 `typedef` (a real named type, e.g. `typedef
  unsigned char ActionAttack;`), but flags must NOT (same "raw width
  type, not a named/wrapped type" rule as C++, §4.3's own stated
  reasoning applies identically to a C89 typedef). `_c_field_type`
  checks `t in reg.flags` FIRST, before the identifier-typedef lookup,
  returning the domain's raw C width type directly; `render_c89_split`'s
  domain-emission loop branches on `kind` to skip the `typedef` line
  and the cast-to-domain-type wrapper on the `#define` constants
  (`#define Domain_member value`, not identifier's `#define
  Domain_member ((Domain)index)`).

**Binary format (`export_binary.py`)**: needed ZERO changes of its own
-- confirmed by reading `pack_leaf_value`, not assumed -- it already
dispatches purely on `_leaf_binary_kind`'s returned `kind`, and that
function's new flags case (`"scalar"`, same as any u8/u16/u32/u64
field) already routes through the existing generic `struct.pack`
scalar path with no special-casing needed. Fixing the one shared
function in `export_cpp.py` was the whole fix for this target.

**Validated, real toolchain, every target, not just "should work"**:
- **C++**: real MSVC (`cl.exe /std:c++17 /EHsc`) compile and execution,
  both single-header and split modes -- `static_assert`s on the
  namespace constants themselves, a real bitwise-combined value
  checked at compile time, real instance data checked at runtime, and
  the natural `if (flags & X)` check working directly (the whole
  point of the namespace-over-`enum class` design, confirmed for real
  this time, not just in the abstract).
- **6502**: all three dialects (ACME, 64tass, KickAssembler) -- real
  assemble, real execution under `py65`, matching hand-computed
  combined values (`is_movable | is_pickupable` = 10, checked byte-
  exact in emulated memory).
- **Z80**: both dialects (SjASMPlus, z88dk-z80asm) -- real assemble,
  real execution under the `z80` emulator, AoS confirmed via both
  dialects' real toolchains, SoA layout output inspected directly
  (correct dense-index array shape, same values).
- **68000**: real `vbcc +aos68k` compile, real `vamos` execution --
  confirmed the generated header has no typedef for the flags domain
  and the field really is `unsigned char` directly, then confirmed the
  combined value reads back correctly at runtime.
- **Binary format**: real `.gddldata.bin` generation, independent
  readback (a from-scratch byte parser sharing no code with the
  writer, matching this target's own established validation
  standard) -- record_size, record_count, and the packed flags byte
  itself all confirmed correct directly from the raw file bytes.
- **Full regression**: `export_golden.py` 72/72 zero content diffs;
  re-ran all four real-toolchain driver scripts built earlier this
  session (`run_all_cpp_tests.py` 16/16, `run_all_6502_tests.py` 9/9,
  `run_all_z80_tests.py` 8/8, `run_all_68000_tests.py` 4/4) to confirm
  every EXISTING identifier-domain export path still works correctly
  after the shared `DomainInfo`/`gather_ir` changes -- not assumed
  safe from the golden corpus alone, since none of those four driver
  scripts' fixtures happen to use `flags` yet. Also re-ran
  `test_binary_export.py` (binary format's own hand-written suite),
  `multi_file_test.py`, and `test_68000_cli.py`, all clean.
- **One pre-existing test left unrun, not newly broken**:
  `export_binary_test/test_schema_table_cpp.py` hardcodes `g++`
  directly, which has never been available on this Windows machine at
  any point this session (confirmed: this is the exact reason
  `run_all_cpp_tests.py` exists as a separate, MSVC-based driver in
  the first place). The claim this test exists to check -- that the
  §17.5 schema table compiles for a flags-containing type -- was
  already independently confirmed via real MSVC in this session's own
  direct verification, just not through this specific pre-existing
  g++-based script.

**Not yet done, next**: stage 5 (validation -- new permanent corpus
fixtures: valid auto-assignment, explicit `bN` mixed with
auto-assignment, duplicate-bit error, width-overflow error,
arithmetic-rejected, bitwise-rejected-elsewhere, a real combined value
read back from real compiled/run output) and stage 6 (docs, folded
into `language-basics.md` or a new guide -- deliberately undecided
until real material exists). Stage 4 as scoped in the handover doc is
complete for all five targets.

## flags/bN work, stage 5: permanent corpus fixtures

Picked up immediately after stage 4, same session, prompted by a
direct question ("are the tests written for this new feature?") that
correctly caught this gap -- every stage 1-4 validation so far lived
in throwaway scratch scripts, real and thorough but not committed or
repeatable by anyone else. This stage closes that specifically.

**A real, precision gap closed first, before writing anything that
would depend on it**: the arithmetic-rejected-on-flags and
bitwise-rejected-on-non-flags errors (`_apply_binop`/`_parse_operand`
in `resolve.py`, added during stage 3) had no `check=` name at all --
`None`, unlike every other error in this codebase. Found while
preparing to write fixtures whose `.golden.json` would need to name a
specific check, not just a message string. Added
`check="flags_arithmetic_rejected"` / `check="flags_bitwise_rejected"`
to all four call sites (both the binary form in `_apply_binop` and the
unary `-`/`+`/`~` forms in `_parse_operand`). Confirmed via direct
attribute access on the real `CompileError` object (not just eyeballing
message text) before trusting it. Full regression re-run clean after
this alone, before any fixture existed yet.

**New `corpus/flags/` fixture group**, seven files, all real
`capture_status: "captured"` (not predictions -- this is a
single-session design-and-implementation thread, unlike the corpus's
original two-role Test Corpus/Compiler Core process, so there was
never a "predict before an implementation exists" phase to go through;
every fixture's expected values were hand-computed FIRST, then
confirmed byte-for-byte against `export_golden.py`'s real output
before locking, never the reverse):
- `flags_auto_assignment_valid.gddl` -- positive baseline, every real
  member auto-assigned, confirming sequential bit assignment and that
  a `= 0` sentinel claims no bit.
- `flags_explicit_bit_mixed_with_auto.gddl` -- the depth pass, and the
  most important fixture in this batch: an explicit `= b2` declared
  AFTER two auto members that a naive single-pass algorithm would let
  grab bit 2 first. Locks the exact property that makes explicit-vs-
  auto collisions structurally impossible (stage 3's own central
  design insight), not just today's implementation happening to get it
  right. Also the fixture reused for the export-side check below.
- `flags_duplicate_bit_claim_error.gddl` -- the one collision that CAN
  actually occur (explicit-vs-explicit), domain-only, no instances,
  same convention `domain_logical_id_collision_error.gddl` already
  established.
- `flags_bit_exceeds_width_error.gddl` / `flags_width_overflow_error.gddl`
  -- two DISTINCT failure shapes, both real, neither reducible to the
  other (an individual out-of-range explicit claim vs. a domain-wide
  capacity shortfall during auto-assignment) -- the handover doc's
  stage 5 checklist only names "the width-overflow error" singular,
  but both were built during stage 3 and both deserve permanent
  coverage, matching this corpus's own established precedent of adding
  a bonus negative path when a real, distinct case exists beyond the
  strict checklist (`domain_field_wrong_domain_error.gddl`'s own
  MANIFEST.md entry names this exact precedent).
- `flags_arithmetic_rejected_error.gddl` / `flags_bitwise_rejected_on_non_flags_error.gddl`
  -- both directions of the operator-legality gate, op-statement form.

New `corpus/flags/MANIFEST.md`, matching every other fixture group's
documentation convention (file table, coverage checklist against the
stage 5 task list, notes on what was verified and how).

**Export-side requirement** ("a real combined value actually read back
correctly from real compiled/run output" -- something `corpus/`'s own
schema structurally cannot capture, since it never runs an export
target): `flags_explicit_bit_mixed_with_auto.gddl` -- the SAME source,
not a variant -- also lives at `export_cpp_test/export_test_flags.gddl`,
matching the exact "dual purpose, two separate channels" convention
`composition_nested_u16_fields.gddl` already established (documented
identically in both copies' header comments). Checked-in
`generated_flags.h` (single-header mode, default guard name, matching
this directory's own existing convention of NOT customizing it per
file even though multiple `generated_*.h` files coexist there -- each
test only ever includes one at a time, so no real collision). New
`test_generated_flags.cpp`: `static_assert`s against both the
namespace constants themselves AND the resolved instance data
(single-header mode makes both `inline constexpr`, so the "copy a
base, toggle one flag" scenario is checkable at COMPILE time, not just
runtime), plus the natural `if (flags & X)` check -- the exact thing
the namespace-over-`enum class` design exists for, confirmed working
in a real compiled program, not just argued for on paper. Added to
`run_all_cpp_tests.py`'s `CASES` list. Real MSVC compile and
execution, all 17 cases (16 pre-existing + this one) passing.

**A real, easy-to-hit `.golden.json`/`golden_output.json` consistency
trap, worth recording precisely so a future session doesn't lose time
rediscovering it**: `export_golden.py`'s own `main()` ALWAYS
regenerates `golden_output.json` fresh from real compiler output as a
side effect of running it (needed for the lock-completeness check) --
on this Windows machine, that means every run reintroduces the
`glob`-produced backslash path-separator keys already documented as a
false-positive earlier in this file. Merging new fixtures into the
real, committed (forward-slash-keyed) `golden_output.json` safely
means: (1) run `export_golden.py` once to confirm lock-completeness
and get fresh real output, (2) normalize path separators and merge
ONLY the genuinely new fixture keys into a copy of the last real
`git show HEAD:...` version -- never a blanket rewrite of the whole
file, which would also silently flip every pre-existing fixture's
`\uXXXX`-escaped non-ASCII characters to raw UTF-8 (confirmed hitting
this exact mistake once while preparing this batch: `json.dump(...,
ensure_ascii=False)` doesn't match `export_golden.py`'s own plain
`json.dump(out, fh, indent=2)` call, and produced 150+ lines of pure
serialization-style diff noise across fixtures this batch never
touched, before being caught and fixed by matching the tool's own
default exactly), and (3) if `export_golden.py` gets run again for any
reason afterward, redo the merge -- it always overwrites the file
fresh, every time, with no memory of a prior merge. Confirmed the
final merge is purely additive (142 insertions, 1 deletion -- the
`_meta.fixture_count` line -- nothing else touched) via a real `git
diff` before trusting it, not assumed from the merge script's own
logic being "obviously correct".

**Validated**: all seven new fixtures' real output confirmed
byte-for-byte against hand-computed expected values before locking.
Full `export_golden.py` regression: 79/79 (72 pre-existing + 7 new),
lock-completeness clean, zero content diffs among the 72 pre-existing
fixtures (structural comparison). `run_all_cpp_tests.py`: 17/17, real
MSVC. `multi_file_test.py` and `test_68000_cli.py` re-run clean
(touched shared `resolve.py`, same discipline as every stage before
this one).

**Not yet done, next**: stage 6 (docs -- fold into
`language-basics.md` or a new guide, deliberately undecided until real
material exists to look at). Stage 5 as scoped in the handover doc is
complete.

## flags/bN work, stage 6: docs -- the final stage, feature complete

Picked up immediately after stage 5, same session. The handover doc
deliberately left "fold into `language-basics.md`, or its own guide"
undecided until real material existed to look at (section 4.4's own
wording) -- with stages 1-5 all shipped, that material now exists.

**Decision, made now rather than left open**: folded into
`docs/language-basics.md`, as a new `## Flags: combinable bits`
section immediately after the existing `## Identifier domains and the
'@' prefix` section, not a new standalone guide. Reasoning: that page's
own stated scope is "the actual data types a field can hold" -- flags
is exactly that, a new field-typeable construct, structurally the same
weight as the identifier-domains section already there, not a
cross-cutting topic like `templates-guide.md`'s delete-template
pattern (which touches every construct) or `dispatch-guide.md`'s
export-target-specific material. A single section, matched in depth to
its neighbor (one worked example, the three member-value shapes, real
generated C++ output, two real error examples -- the identifier
section itself shows exactly two).

**Every example verified against real output before being written
down, same standing rule as every other doc page in this project, not
relaxed here**: the `.gddl` source shown, the C++ namespace/struct
output, and both error messages were each run through the real
pipeline (`generate_header` for the C++, `print_report` for the
errors) and copied verbatim, never typed from memory of the design.

**A real mistake caught by this verification, not by luck**: the
arithmetic-rejected-on-flags error example is presented as continuing
the doc's own running example (referencing `Base`, already shown
earlier in the section), so its real line number depends on every
snippet before it in the page, not just its own few lines. The first
draft copied the error text from an isolated standalone test file
(`component_flags + 1` at line 13 there) and dropped it straight into
the doc claiming that same line number -- wrong, since the real
cumulative file (every snippet from `flags ComponentFlags u64` through
`Entity Bad = Base` typed in sequence, exactly as a reader following
the page would end up with) puts that statement at line 24. Caught by
literally reconstructing the full cumulative file and re-running it
for real before trusting the number, not by re-reading the isolated
snippet more carefully -- the isolated snippet's OWN output was
already completely correct, the mismatch was purely from citing it
against the wrong context. Fixed to `line 24`, confirmed against the
real cumulative run. The domain-only bit-collision error example, by
contrast, is deliberately introduced as a fresh, disconnected block
(`flags Broken u8`, matching the identical convention the identifier
section's own two error examples already use) -- verified standalone
correctly, no cumulative-context risk there since it never references
anything from the running example.

**A second, smaller inconsistency caught on a full re-read**: a
sentence referenced `flags & ComponentFlags::is_movable` as an
illustration of the natural bitwise-check pattern, but no variable
named bare `flags` was ever introduced anywhere in the shown example
(the real field is `component_flags`, on the `Player` instance
specifically) -- confusing for a reader trying to map the prose onto
the actual code just shown. Fixed to `Player.component_flags &
ComponentFlags::is_movable`, a real, traceable reference to symbols
the reader has actually seen.

**Content covered**: what `flags` is for and how it differs from
`identifier` (combinable vs. mutually exclusive); the required-width
syntax; all three member-value shapes (auto, explicit `bN`, the `= 0`
sentinel) with a note that `bN` is a general integer literal, not
scoped to `flags` blocks; the settled C++ export shape and why
(namespace of `constexpr`, not `enum class`, real bitwise operators
with real scoping); op-statement combining (the copy-a-base-then-
toggle-one-bit pattern); the arithmetic-rejected-on-flags rule with
its real error message; the bitwise-rejected-elsewhere rule (described
in prose, not a third error example -- keeping this section's depth
matched to its neighbor rather than exhaustively re-demonstrating a
rule that's just the mirror image of the one already shown); and the
bit-collision + width-overflow checks, the latter described in prose
(matching identifier's own width-overflow error, which the neighboring
section already demonstrates in exactly this same "described, not
re-shown" way for its own second error case).

**Validated**: every `.gddl` snippet shown compiles (or fails)
exactly as the surrounding prose claims, confirmed via direct pipeline
runs, not visual inspection. Zero em-dashes (checked directly, this
project's own hard rule, in code comments, commit messages, AND
documentation alike). Purely additive diff to `language-basics.md`
(100 lines, nothing else in the file touched) -- no code changed this
stage, so no regression suite re-run was needed or performed.

**This completes the `flags`/`bN` feature, all six stages, per the
handover doc's own plan.** Next up per that same plan (section 5):
arrays, fully designed already but explicitly deferred until `flags`
shipped in full -- which, as of this entry, it now has.

## Packaging restructuring: `gddl/` is now a real installable Python package

Motivation was external to this repo's own pipeline work: a separate,
future scripting-language compiler (its own project, its own GitHub
repo) needs to reuse this repo's own logical-ID hashing code directly
(fnv1a_64 in registry.py) rather than re-implementing it, to avoid two
independently-maintained copies of the same hash ever drifting apart
(a risk this project's own SPEC.md section 4.1.1 already flags
explicitly). The proper way to make that possible is a real installable
Python package (`pip install git+https://...`), not manual sys.path
surgery from the consuming project.

**What changed, mechanically:**
- Added `compiler-python/gddl/__init__.py` (empty except the license
  header) -- the one file that turns `gddl/` from a loose folder of
  scripts into an actual Python package.
- Added `compiler-python/pyproject.toml` (setuptools, package name
  `gddl-compiler`, `packages.find` includes `gddl*`).
- Converted every internal import inside `gddl/` from flat sibling-style
  (`from resolve import X`, which only worked because every script sat
  in the same directory and something upstream had put that directory
  on sys.path) to package-relative (`from .resolve import X`). This
  touched all 17 files under `gddl/` -- both top-level imports and every
  deferred, function-local import (the dialect-dispatch imports inside
  `export_6502.render()`/`export_z80.render()`, and the `_cli()` imports
  of `combine`, in every exporter). Two of these deferred dispatch
  imports (`export_6502.py`'s and `export_z80.py`'s own dialect-selection
  branches) were missed by the first grep pass, which only searched
  column-0 `from X import` lines; a second grep for indented `from`
  lines caught them. Confirmed nothing left over with a final grep
  across the whole `gddl/` tree for any remaining flat-style import: zero
  matches.
- Updated the 6 test-side scripts that import `gddl` modules
  in-process (`export_golden.py`, `multi_file_test/test_multi_file.py`,
  `export_6502_test/test_6502_zp_validation.py`,
  `export_binary_test/test_binary_export.py`,
  `export_binary_test/test_schema_table_cpp.py`,
  `export_z80_c_test/verify_shift_add.py`) to point their `sys.path`
  entry at `compiler-python/` itself (the package's parent directory,
  not `gddl/` directly) and import via `from gddl.parser import X`
  style. `test_binary_export.py` had three of its own deferred,
  function-local imports (`registry.logical_id`, `export_cpp._flatten_leaves`,
  `export_binary.compute_record_size`) that the first pass missed for
  the same column-0-only-grep reason as above; caught and fixed the same
  way.

**One real behavioral consequence, not just a mechanical rename:** any
exporter invoked as a subprocess by running its `.py` file directly
(`python .../gddl/export_z80.py ...`) now fails with `ImportError:
attempted relative import with no known parent package` -- a relative
import needs the module to be loaded as part of its package, which
running a file directly as `__main__` never provides, package or not.
Two test suites did exactly this: `multi_file_test/test_multi_file.py`
(Check 4, shell-independence, invokes `export_z80.py` as a real
subprocess three different ways) and `export_68000_test/test_68000_cli.py`
(its entire suite invokes `export_68000.py` as a subprocess). Both
switched from `[sys.executable, path/to/export_X.py, ...]` to
`[sys.executable, "-m", "gddl.export_X", ...]` with `cwd` set to
`compiler-python/` (the package's parent) -- `-m` loads the module as
part of its package, which is what the relative imports now require.
This is also the shape any real end-user CLI invocation of these
exporters needs going forward, not just tests: `python -m gddl.export_z80
...` from `compiler-python/`, not `python gddl/export_z80.py ...`
directly. (A `[project.scripts]` console-script entry point in
`pyproject.toml` would remove this requirement entirely once one is
added; not done yet since it wasn't needed for this pass.)

**Verified, not just assumed:** a standalone import sweep (every module
in `gddl/`, including every dialect exporter, imported fresh with only
`compiler-python/` on `sys.path`) succeeded with zero errors. Then the
full regression suite: `export_golden.py` regenerated all 79 fixtures
cleanly; a structural diff against the previously-committed
`golden_output.json` (normalizing Windows backslash path-separator keys
back to forward slashes, the same known cosmetic artifact every prior
Windows-side regeneration this session has produced) found zero content
differences across all 79 fixtures -- confirming the restructuring
changed no compiler behavior. All four real-toolchain driver suites
re-run clean: `run_all_cpp_tests.py` (17/17, MSVC), `run_all_6502_tests.py`
(9/9, ACME + 64tass + KickAssembler), `run_all_z80_tests.py` (8/8,
SjASMPlus + z88dk), `run_all_68000_tests.py` (4/4, vbcc + vamos).
`multi_file_test.py`, `test_binary_export.py`, and `test_68000_cli.py`
all pass clean after their subprocess-invocation and deferred-import
fixes above. `test_schema_table_cpp.py` hits its one already-documented
pre-existing gap (hardcoded `g++`, never available on this Windows
machine at any point this session -- see the entry above); everything
in that script short of the actual g++ compile step ran and passed.

Zero em-dashes (checked directly, this project's own hard rule).

**Follow-up, same session, addressing a real usability regression the
user caught:** `python -m gddl.export_z80 ...` still needed the caller
to be inside `compiler-python/` (or have it on PYTHONPATH), meaning
every compile required cd-ing into the GDDL checkout first, then back
out again afterward. Fixed with `[project.scripts]` entries in
`pyproject.toml` for all five exporters (`gddl-export-cpp`,
`gddl-export-6502`, `gddl-export-z80`, `gddl-export-68000`,
`gddl-export-binary`), each pointing at the existing `_cli()` function
already used by `if __name__ == "__main__"` in each module (no new
code needed, `_cli()` already calls `sys.exit(1)` on failure and
returns cleanly on success, exactly what an entry point needs).

Verified for real, not assumed: `pip install -e compiler-python/`,
then `gddl-export-z80 --help` and a real compile of
`export_test_z80_minimal.gddl`, both run from `%TEMP%` (nowhere near
the repo), both succeeded (exit 0, and the compile produced real,
correct SjASMPlus output, checked by reading it). One PowerShell
wrinkle hit and resolved during this check: redirecting a native
command's stderr with `2>&1` makes the tool report a nonzero exit even
when the real exit code is 0 (a known PowerShell 5.1 behavior, not a
real failure) -- confirmed the real exit code separately via
`$LASTEXITCODE` without the redirection.

Added `compiler-python/*.egg-info/` and `compiler-python/build/` to
`.gitignore` -- the editable install used for this verification
generates `gddl_compiler.egg-info/`, a local build artifact, not
something to commit.

## Identifiers manifest export (`--emit-ids-manifest`), SPEC.md section 20

The original motivating task behind this whole session's packaging
work (making `gddl/` a real installable package): a future, separately
maintained scripting-language compiler needs a build-time way to
resolve a `Domain.key` text reference, written in that language's own
script source, into the same logical ID or bit position a completely
different, independently-compiled mod (or the base game itself)
already resolved it to -- without needing that mod's GDDL source at
all. Design was worked through with the user across several turns
(usage patterns before format choice, live-console debugging as the
concrete runtime-tooling use case, the exact JSON schema, the flag
shape) before any code was written; see this session's own
conversation for the full reasoning trail. SPEC.md section 20 is the
permanent record of the settled design; this entry covers what was
actually built and how it was verified.

**New module, `gddl/export_ids.py`**: `build_ids_manifest(reg)` (pure
function, registry in, dict out) and `write_ids_manifest(reg,
output_stem)` (writes `{output_stem}.gddlids.json`). Walks
`reg.identifiers` and `reg.flags` directly, unconditionally --
deliberately independent of `--emit-all-domains`, which only controls
target-language code generation for referenced domains, a separate
concern from what this manifest is for. `logical_id` is written as the
same 16-hex-digit string `registry.logical_id()` already produces, not
a raw JSON number -- a full 64-bit value silently loses precision
under any JSON parser treating numbers as IEEE-754 doubles (the
settled reason, see the conversation this session). `bit` stays a
plain integer, no precision concern at that range.

**One real gap found while implementing, not while designing:** the
settled schema called for a `description` field on flags domain
members too, matching identifier domain members. But `ast_nodes.
FlagsEntry` has no description slot at all -- flags syntax only ever
carries `name` plus one of `kind`/`explicit_bit`/`explicit_number`,
unlike `IdentifierEntry`, which requires `key = "description"`. Rather
than fabricate a fake description or silently drop the field without
saying so, this is called out directly: flags domain members carry
only `key` and `bit` in the manifest, by necessity, not by choice, and
both `export_ids.py`'s own docstring and SPEC.md section 20.3 state
this plainly rather than leaving a reader to wonder why the two domain
kinds' member shapes aren't parallel.

**CLI wiring, all five exporters identically**: `--emit-ids-manifest`
(boolean, off by default), added to `export_cpp.py`, `export_6502.py`,
`export_z80.py`, `export_68000.py`, `export_binary.py`. No separate
path argument -- always `<output>.gddlids.json`, derived from each
exporter's existing `-o`/`--output` stem, matching the precedent
`export_binary.py`'s own `.gddlmeta.json` already set. For the two
exporters where `-o` is optional and defaults to stdout (6502, Z80),
combining `--emit-ids-manifest` with no `-o` is now a hard `ap.error()`
rather than silently inventing a stem nobody asked for -- confirmed
this doesn't regress either exporter's existing stdout-default
behavior when the flag isn't used at all.

**Verified for real, not assumed:**
- A combined smoke fixture (one identifier domain, one flags domain,
  one instance) run through all five exporters' real CLIs
  (`python -m gddl.export_X ... --emit-ids-manifest`), confirming
  byte-identical manifest content regardless of target -- proving the
  manifest generation is genuinely target-independent, not five
  separate implementations that happen to agree.
- The two pre-existing, unrelated gaps this smoke test surfaced along
  the way (not caused by this feature, confirmed by reading the actual
  failing code path in each case): 6502/Z80/68000 all require a
  declared width on any referenced identifier domain (§10.1/§16/§15.4,
  a real, older restriction unrelated to `--emit-ids-manifest`), and
  Z80 specifically doesn't yet support `flags`-typed instance fields at
  all (a real, separate capability gap in `export_z80.py`, distinct
  from flags domain *constant* emission, which does work on Z80).
  Fixture adjusted to route around both rather than treating either as
  something this feature broke.
- A new permanent test suite, `tests/export_ids_test/` (fixture +
  `test_ids_manifest.py`, following `test_binary_export.py`'s own
  style): manifest content checked directly against
  `build_ids_manifest()`, with every `logical_id` independently
  recomputed via a fresh call to `registry.logical_id()` rather than
  trusted just because the function under test produced it; confirmed
  the manifest includes a domain never referenced by any field
  (proving independence from `--emit-all-domains`); confirmed via a
  real subprocess CLI invocation that the flag is genuinely opt-in (no
  flag means no manifest file, not just an empty one); confirmed the
  no-`-o` guard actually rejects, real subprocess, real exit code and
  message. All four checks pass.
- Full regression suite re-run clean after: `export_golden.py` (79
  fixtures, structurally diffed against the previously committed
  `golden_output.json` with zero content differences, the same
  Windows path-separator cosmetic noise as every prior regeneration
  this session), all four real-toolchain driver suites (17+9+8+4,
  MSVC/6502-three-dialects/Z80-two-dialects/vbcc), `test_68000_cli.py`,
  `test_binary_export.py`, `multi_file_test.py`.

**A genuine pre-existing spec concept this new section had to be
positioned against, not silently duplicate:** SPEC.md section 14.6
already described a "metadata manifest" concept, for a different
purpose: generating binding glue for an in-process scripting VM
(getter thunks dereferencing real C++ memory in the same address
space), covering full struct/instance layout, tied to the C++ export
specifically. This session's new manifest is narrower (identifier and
flags domains only, no instance or struct data) and serves a different
consumer (a standalone, separately-compiled script compiler resolving
text to numbers at its own build time, never touching a running game's
memory). Surfaced to the user directly before writing SPEC.md section
20 rather than assumed; user chose keeping the two concepts explicitly
separate over folding the new work into section 14.6 as if it were
that section's concrete implementation, which it isn't (it doesn't
cover what section 14.6 promises). Section 20 states this
non-overlap explicitly, the same pattern section 17 already used to
distinguish itself from section 14.6.

Zero em-dashes (checked directly, this project's own hard rule).

## Arrays work, stage 1: bracket-indexed statement parsing

`GDDL_Session_Handover.md` (repo root) has arrays fully designed
already, section 5, explicitly deferred until `flags` shipped in full
("flags first because it's smaller and proves the 'new construct, five
export targets' pipeline before the bigger, riskier array feature gets
built on top of it"). Flags shipped in full this session (all six
stages, see above); the identifiers-manifest detour (also above) came
between flags finishing and this starting, per the user's own explicit
sequencing this session. Staged the same way flags was: parser first,
then registry/resolution, then export across all five targets, then
permanent corpus fixtures, then docs. This entry is stage 1 only.

**Scope, confirmed by actually reading parser.py before writing
anything, not assumed:** two of the three syntax pieces the design
calls for turned out to need zero parser changes at all.
`FieldDef.type_tokens` and `AssignStmt.rhs`/`OpStmt.rhs` were already
raw, uninterpreted text at the parse level (`split_top_level_equals`
just splits on the first top-level `=`, nothing about `:` or `,` or
`{`/`}` is special to the parser) -- so `damage_min_max = i32 : 2` as
a field type, and `damage_min_max = { 10, 30, 5 }, { 20, 50, 8 }` as a
value literal, already parse today, unchanged, with the array syntax
sitting untouched inside a string the parser was never going to look
inside of at this phase anyway. Interpreting what's inside those raw
strings is registry.py's job (stage 2), not parser.py's. Confirmed
this directly with a scratch check (`field.type_tokens ==
"i32 : 2"`), not just reasoned about.

The one piece that genuinely needed parser changes: **direct bracket
indexing**, `damage_min_max[1] = 200` / `damage_min_max[1] + 50`
(assign and op-statement forms; the design explicitly rejected a
nested-block alternative in favor of this). The existing
`_classify_statement`/`_require_field_name` machinery validates a
statement's leading field-name token against `^[A-Za-z_]\w*$`, which a
bracketed reference doesn't match at all -- every array-element
statement would have hit the ordinary "not a valid field identifier"
parse error with zero code changes.

**Implementation:**
- `ast_nodes.py`: added `index: Optional[int] = None` to `AssignStmt`
  and `OpStmt` (appended last, after the existing default-valued
  `children` field on `AssignStmt`, to keep every dataclass's
  no-default-before-default field ordering valid). `None` for every
  statement that doesn't use bracket indexing, which is every
  statement written before this stage existed -- not a new required
  argument, a new optional one.
- `parser.py`: added `_INDEXED_FIELD_RE` (`^([A-Za-z_]\w*)\[(\d+)\]$`,
  digits only, never an expression, matching how `bN` flags literals
  are similarly a closed non-expression grammar at this phase) and
  `_parse_field_ref()`, returning `(base_name, index)`. Kept
  `_require_field_name` as-is rather than replacing it: it's also used
  by `_parse_flags_entries` for flags member names, which must never
  accept bracket indexing, so that call site needed to stay
  untouched, not get pulled toward a shared, unintentionally-permissive
  path.
- `_classify_statement` restructured so the leading-token validation
  happens permissively (plain name or indexed) for the assign/op paths,
  but the bare-field path explicitly re-checks `index is not None`
  and rejects with a dedicated message naming exactly why (arrays
  don't use the bare/modify-only form at all) rather than a generic
  regex-mismatch message. Getting the order right here mattered: the
  original function validated the leading token once, unconditionally,
  before knowing whether the line would end up being 'op', 'bare', or
  fall through to 'raw' -- collapsing that into a single permissive
  check up front, then re-validating specifically inside the 'bare'
  branch, was the only way to keep both "brackets valid for assign/op"
  and "brackets rejected for bare" true without either silently
  admitting bracket-indexed bare fields or accidentally rejecting
  valid non-bracketed statements that used to reach the 'raw' fallback.

**One real, expected corpus-lock change, not a bug:** the
"not a valid field identifier" error message itself changed (now
mentions the two new array-element shapes alongside the pre-existing
ones), which two existing error-fixture corpus locks
(`op_statements/op_statement_leading_operator_error.golden.json`,
`op_statements/op_statement_missing_leading_field_error.golden.json`)
capture verbatim. Confirmed via a structural diff against the
previously committed `golden_output.json` that these were the ONLY
two fixtures with any content difference across all 79 (everything
else byte-identical once path separators are normalized) -- updated
both `.golden.json` files and surgically merged just these two entries
into `golden_output.json`, leaving every other committed fixture
untouched (same discipline as every other golden-lock update this
session).

**Verified, not assumed:**
- A scratch script (six checks, not yet a permanent fixture -- see
  below for why): array-element assign captures the right
  `(field_name, index, rhs)`; array-element op-statement captures the
  right `(field_name, op, rhs, index)`; an ordinary non-array assign's
  `index` is `None`; a bracket-indexed bare field is rejected with the
  dedicated message; a malformed non-numeric index (`damage_min_max[x]`)
  falls through to the ordinary "not a valid field identifier" error
  rather than being silently accepted or crashing; an array field type
  declaration round-trips through `type_tokens` completely unchanged.
  All six passed.
- No permanent corpus fixtures added at this stage, deliberately,
  matching the precedent flags' own stage 1 set (see above entry): a
  `.gddl` fixture actually exercising array syntax would fail
  meaninglessly right now, since `array` isn't a registry-known field
  category yet (stage 2's job) -- phase 4/5 would reject it as "not a
  field of X" or similar, which isn't what a stage-1 corpus fixture
  should be locking in. Real corpus fixtures land once resolution
  (stage 2) makes array fields and array-element statements actually
  resolve to something.
- Full regression suite re-run clean, everything, not just the parser:
  `export_golden.py` (79 fixtures, structurally diffed, exactly the
  two expected changes above and nothing else), all four
  real-toolchain driver suites (17/9/8/4), `test_68000_cli.py`,
  `test_binary_export.py`, `multi_file_test.py`, `test_ids_manifest.py`
  -- confirming this stage changed zero behavior anywhere outside the
  new bracket-indexing grammar itself.

**Not yet done, next**: stage 2 (registry/resolution -- interpreting
`ElementType : dim1 : ... : dimN` in `type_tokens` into a real field
category, resolving array value literals including the
outer-braces-optional/inner-braces-required nesting rules, wiring
bracket-indexed assign/op-statements into phase 6 evaluation, op
statements' "current value at that index" rule).

Zero em-dashes (checked directly, this project's own hard rule).

## Arrays work, stage 2: registry/resolution

Second of five staged passes (see stage 1 above for the full plan and
its own reasoning). This stage covers everything stage 1 explicitly
deferred: interpreting `type_tokens` array syntax into a real field
category, resolving array value literals, and wiring bracket-indexed
assign/op-statements (parsed in stage 1, unused until now) into actual
phase 6 evaluation.

**Registry-level (`registry.py`)**: added `ArrayTypeInfo` (dataclass,
`element_type: str`, `dims: List[int]`, outermost-to-innermost) and
`_try_parse_array_type()`, a pure, never-raising syntactic parser of
`'ElementType : dim1 : dim2 : ...'`. `field_category()` now returns
`("array", ArrayTypeInfo)` for a field whose type_tokens parses this
way -- the one genuinely new thing every existing caller of
`field_category()` needed checking against: for every category before
this, the second return value was always a bare string; for `"array"`
it's now an object. Grepped and re-read every call site (phase5.py x6,
resolve.py x5, registry.py's own dependency-walk x2) before writing
anything -- most needed zero changes at all, since they already
fall through generically to "not struct, reject children" /
"not struct, reject bare-field" style checks that correctly handle
`"array"` for free, without ever touching the payload. Only phase5's
OpStmt check and resolve.py's `_apply_assign`/`_apply_op` needed real
new logic (see below).

**A real, deliberate scope decision, not pre-specified by the
design**: `_check_array_field_types()` (registration-time validation,
same pattern as `_check_indexed_field_types` for `@Domain`) rejects a
struct, identifier-domain, or flags-domain element type by name
(explicitly deferred per the design), but does NOT validate that a
non-rejected element type is a genuinely KNOWN scalar type (`u8`,
`string N`, etc.) against a fixed vocabulary. Checked first: plain,
non-array scalar fields don't get this validation either today (a
typo'd type name on an ordinary field silently never gets coerced or
range-checked by anything, anywhere in the pipeline -- a real,
pre-existing, unrelated gap, confirmed by reading `_coerce_numeric`,
not fixed here since it's well outside arrays' own scope and would be
a materially bigger, separate change). Matching that existing
leniency for array element types keeps arrays consistent with how the
rest of the language already behaves, rather than introducing new,
array-specific strictness nothing else has.

**Resolution-level (`resolve.py`)**: a full array VALUE is always a
plain, possibly-nested Python list (`[10, 30]`, `[[10,30,5],[20,50,8]]`)
-- no new wrapper value type. This works because of one load-bearing
design decision, confirmed against the spec's own principles rather
than assumed: **an array field is always either UNINIT as a whole, or
fully populated as a whole, never partially initialized element by
element.** The design explicitly rejected the bare/modify-only
nested-block form for arrays in favor of direct bracket indexing --
which means arrays never get that form's "build up incrementally,
leaving the rest UNINIT" capability at all. A bracket-indexed assign
or op-statement requires the array to ALREADY hold a full value (a
prior full-literal assign earlier in the same instance body, or copied
in via `= Source`) before touching one element -- exactly the same
"read an uninitialized field, hard error, no exceptions" rule scalar
op-statements already enforce, just generalized to per-element. This
one decision is why phase 8's completeness check
(`validate.py::_find_uninitialized`) needed ZERO changes: a fully
populated array is just a plain list, never a `StructValue`, so the
existing `isinstance(field_val, StructValue)` recursion check already
correctly treats it as "not missing" with no array-specific code path
added at all.

**Array value literal parsing**: `_parse_array_literal` /
`_parse_array_group` / `_parse_array_element`, plus two small
quote-and-brace-aware text primitives (`_is_single_brace_group`,
`_split_top_level_commas`) in the same spirit as `parser.py`'s own
`split_top_level_equals` (imported `_is_quote_escaped` from `parser.py`
rather than reimplementing it -- `resolve.py` already imports other
parser-private helpers this same way). Implements the design's rule
exactly: the single outermost brace layer is always optional (peeled
at most once, before any dimension-based recursion begins);
every level from there inward requires explicit braces to disambiguate
nested groups, enforced by the recursive `_parse_array_group` never
having an optional-brace branch of its own. Comma-splitting is
quote-aware specifically because a `string N` array element can itself
contain a literal comma (`"Carol, Jr."`), which a naive
`text.split(",")` would have mis-split -- caught by writing check 7 in
the verification script below before assuming it would just work.

**A real, deliberate extension beyond what the shown examples
demonstrate**: each array element is parsed through the exact same
`_eval_expr` evaluator a plain scalar field's RHS already goes
through, not a narrower literal-only parser -- so an array element can
be a cross-field reference, a `bN` literal, or an arithmetic
expression, not just a bare number. The design's own examples only
ever show plain numeric literals, but nothing about the design rejects
this, and reusing the existing evaluator verbatim (rather than
building a second, narrower one) is both less code and more
consistent with how every other value-producing position in the
language already works. Confirmed working, not just assumed, via
check 8 below.

**A real gap in the design notes, resolved here, documented rather
than silently decided:** the design's own examples of bracket indexing
(`damage_min_max[1] = 200`) are all 1D; nothing specifies what
`field[N]` should mean for a 2D+ array (index into the outermost
dimension only, returning a sub-array? require chained brackets,
`field[1][2]`, which stage 1's parser doesn't support at all -- it
only ever parses one bracket pair?). Rather than guess at unspecified
multi-dimensional bracket syntax, bracket indexing is scoped to
one-dimensional arrays only for this pass: a bracket-indexed
assign/op-statement on a 2D+ array is a clear, dedicated
`array_multidim_index_unsupported` error naming the field's actual
dimension count and pointing at the full-literal-assign alternative,
never a silent misinterpretation. Full-literal assignment of 2D+
arrays (any dimensionality) works completely unaffected -- only
per-element bracket access is scoped down.

**Phase 5 gets new checks too, not just phase 6:** bracket-indexing
shape validation (is the field actually array-typed; does an
op-statement without brackets on an array field make sense -- it
doesn't, a whole array has no single current numeric value to
read-modify-write) is a purely STATIC check needing only the AST and
registry, matching phase 5's own existing charter exactly
("field_shape: every field referenced in a statement exists on its
declared enclosing struct type... only valid on struct-typed fields").
Added to both `AssignStmt` and `OpStmt` handling in
`_walk_statements`. `resolve.py`'s own matching checks in
`_apply_assign`/`_apply_op` are kept anyway, explicitly commented as
defensive backstops now unreachable in normal operation (any instance
phase 5 already rejects never reaches phase 6 resolution at all, per
`resolve_all()`'s own skip-already-errored-instances logic) -- the
exact same "keep the redundant check anyway" precedent this file's own
`resolve_instance()` circular-dependency backstop already documents
for the identical reason.

**Verified, not assumed:** a 22-check scratch script (not yet
permanent fixtures -- see stage 1's own entry for why corpus fixtures
land later, once export exists too, matching flags' own precedent):
1D array literals both with and without the optional outer braces
(confirmed equivalent); 2D and 3D nested literals; bracket-indexed
element assign; bracket-indexed op-statement reproducing the design's
own motivating "copy a base instance, then adjust one element" case
end to end (`BaseGoblin.damage_min_max = [10,30]`,
`StrongerGoblin = BaseGoblin` then `damage_min_max[1] + 50` ->
`[10, 80]`); string array elements including one containing a literal
comma inside its own quotes; a cross-field-reference-plus-arithmetic
expression as an array element; an uninitialized array read via
bracket op-statement (rejected); an out-of-bounds index (rejected);
multi-dimensional bracket indexing (rejected, dedicated check name);
a wrong total element count (rejected); a multi-dim literal missing
its required inner braces (rejected); struct/identifier/flags element
types, each rejected individually at registration with its own
specific message; malformed and zero-valued dimensions (rejected at
registration); a whole-array op-statement with no brackets (rejected,
phase 5); bracket indexing on a plain scalar field (rejected, phase
5); a never-initialized array field correctly reported `incomplete` by
phase 8 with no array-specific code needed; numeric range enforcement
applying to an individual array element exactly as it already does for
a plain scalar field. All 22 passed.

Full regression suite re-run clean: `export_golden.py` (79 fixtures,
structurally diffed against the previously committed
`golden_output.json`, zero content differences at all this time --
unlike stage 1, none of this stage's new/changed error messages
happened to be exercised by any existing corpus fixture's error path),
all four real-toolchain driver suites (17/9/8/4), `test_68000_cli.py`,
`test_binary_export.py`, `multi_file_test.py`, `test_ids_manifest.py`.

**Not yet done, next**: stage 3 (export across all five targets --
`std::array`/nested `std::array` in C++, matching row-major contiguous
layout uniformly across 6502/Z80/68000/binary per the design's own
"match how C++ does this" instruction). Stage 2's one-dimensional-only
bracket-indexing scope decision may be worth revisiting once export
design surfaces whether multi-dimensional element access turns out to
be needed sooner than expected; noted here so stage 3 doesn't have to
rediscover it from scratch.

## Arrays work, stage 3: export across all five targets

Third of five staged passes. The biggest single stage of this feature
by a wide margin -- every export target's field-type mapping and
value-rendering machinery needed real, target-specific changes, and
two of those changes (C++'s and C89's exact aggregate-initializer
brace rules) are the kind of thing this project's own history says not
to guess at, so both were pinned down against a real compiler BEFORE
any generator code was written, not after.

**C++ (`export_cpp.py`), verified first, real MSVC:** wrote a small
standalone probe (`std::array<int32_t,2>`, a 2D and 3D nested numeric
`std::array`, a 1D `std::array<std::array<char,16>,4>` of fixed
strings) and compiled it before touching the generator. Confirmed:
- A `std::array<T,N>` needs the well-known double-brace treatment
  (`{{ ... }}`, not `{ ... }`) whenever `T` is itself an aggregate
  class type -- which is every non-innermost array dimension, and the
  innermost dimension too when the element is `string N`
  (`std::array<char,N>` is an aggregate). Single bracing suffices only
  when the innermost level holds a genuinely primitive type (a plain
  number).
- Contiguity (row-major, matching the design's "match how C++ does
  this" instruction) falls out of `std::array`'s own memory layout for
  free -- confirmed with a real pointer-arithmetic stride check
  (`&A2[1] - &A2[0] == 3 * sizeof(int32_t)`), not assumed.

Implementation: `_cpp_array_field_type` (builds the nested
`std::array<...>` type string, innermost dimension outward -- a
`string N` element becomes `std::array<char, N>`, never the raw
`char[N]` a plain non-array string field gets, since a raw array can't
itself be another `std::array`'s element type), `_cpp_type_is_aggregate`,
and `_cpp_array_value_literal` (the recursive brace-decision function,
implementing the rule confirmed above). `_cpp_field_type` and
`_cpp_value_literal` both got one new branch each, folding array
support directly into the existing dispatch rather than adding a
parallel code path -- every existing caller of either function
(AoS struct fields, AoS-linear, split mode, the C++17.5 schema table)
gets array support for free, since none of them needed touching
themselves. The ONE place that genuinely needed its own new logic:
`emit_soa_type`'s per-field SoA array declaration, since an
array-typed leaf's SoA column is the first case where the OUTER
`std::array<cpp_type, instance_count>` wrapping ALSO needs the
double-brace treatment (its own contained type, another
`std::array<...>`, is itself an aggregate) -- every leaf type this
exporter produced before arrays (int/float, an enum class, a flags
width's plain int) was never an aggregate, so this exact case simply
never came up before.

**Binary export / schema table (shared in `export_cpp.py`,
`export_binary.py`):** `_leaf_binary_kind` gained an `"array"` kind
(total width = element width * total element count, row-major,
contiguous, no padding -- matching the C++ layout confirmed above);
`export_binary.py`'s `pack_leaf_value` gained a matching branch plus
`_pack_array_value`, recursively packing each element via
`pack_leaf_value` itself (an array element is always scalar or string,
never itself array-shaped, so this recursion can't re-enter the
"array" branch). `canonical_schema_string`/`compute_schema_hash`
needed zero changes -- they already just use `type_tokens.strip()`
verbatim as part of the hash input, array syntax included.

**68000 (`export_68000.py`), verified with real vbcc:** C89 (unlike
C++) puts an array's dimension in the DECLARATOR, after the field
name (`int32_t name[2];`), not in the type itself -- and, confirmed
directly with a real vbcc probe before writing any generator code,
needs NO double-brace treatment at all: plain single-brace nesting at
every level (`int grid[2][3] = { {1,2,3}, {4,5,6} };`) compiles and
runs correctly, real C arrays having no `std::array`-style hidden
wrapper member to trip over. `_c_array_declaration_parts` (returns
`(base_c_type, bracket_suffix)`, folding a `string N` element's own
width in as the final bracket dimension -- `char name[2][16];` for a
2-element array of 16-byte strings, the natural C extension of a
plain string field's own `char name[16];`) and
`_c_array_value_literal` (simple single-brace recursion, no aggregate
distinction needed). Wired into both the AoS struct-field declaration
site and the SoA field-array declaration site (68000's SoA, unlike
6502/Z80's, has no precedent gap to match -- C's raw arrays don't have
6502/Z80 assembly's "no nesting concept" problem, so SoA arrays needed
no special-casing or rejection here at all, just the same declarator
logic as AoS).

**6502 (`export_6502.py` + all three dialects) and Z80 (`export_z80.py`
+ SjASMPlus/z88dk-z80asm), verified with real assemblers + real
emulator memory read-back:** assembly data directives have no nesting
concept at all -- an array is just a flat, contiguous sequence of
element values in row-major order. `flatten_array_ir_value` (identical
helper added to both `export_6502.py` and `export_z80.py`) flattens a
possibly-nested array IR value into that flat sequence once; each
dialect renderer's own AoS emission loop then emits one directive (or
multi-line string block) per flattened element, reusing that dialect's
own existing scalar/string emission functions for the element type --
no new per-dialect emission logic beyond the flatten-and-loop, since
the element-level rendering was already correct. `export_z80.py`'s
shared `_leaf_size_bytes` (used for `type_sizeof`, the AoS stride
needed by the `--z80-pointer-table=off` direct-indexing path) also
gained array support, computed the same way as the binary exporter's
width (element width * total count) -- 6502 needed no equivalent
change since its own zero-page allocation is about type/domain COUNTS
only, never per-field byte width.

**A real, deliberate scope decision, matching an EXISTING precedent in
this exact codebase, not a new inconsistency:** both 6502 and Z80
already had an unimplemented SoA gap for `string N` fields (documented
directly in each renderer's own module docstring: "SoA string support
is not yet implemented," on the reasoning that a non-power-of-two
width would need a real multiply to index, which neither CPU's
multiply-avoidance discipline has a renderer for yet). Arrays hit the
exact same underlying problem -- an array-typed SoA column's per-
instance stride is `element_width * total_count`, generally not a
power of two either -- so array support in SoA mode is scoped out
here too, for both targets, with an explicit, clear, immediate
Python-level rejection (`ValueError`/`ExportZ80Error` naming the field
and pointing at `--layout aos`) rather than either reimplementing the
whole SoA-indexing multiply problem as a arrays-specific side quest,
or (worse) silently falling through to broken output the way the
PRE-EXISTING string gap technically still does on 6502 today (its own
SoA loop doesn't actually raise cleanly for strings, confirmed by
reading it -- a real, pre-existing weakness, not something this stage
introduced or was in scope to fix). AoS mode is fully supported for
arrays on both targets, all three 6502 dialects and both Z80 assembly
dialects, real-toolchain verified.

**z88dk C mode (`export_z80_z88dk_c.py`) -- implemented but NOT
toolchain-verified, a real, honestly-recorded gap, not a silent
skip:** applied the exact same C89 declaration/value logic as
`export_68000.py` (`_c_array_declaration_parts`,
`_c_array_value_literal`, both confirmed structurally identical to the
68000 versions), since this target is also plain C89. `zsdcc` itself
is NOT installed on this Windows machine -- checked directly
(`compiler-python/tools/` has no `sdcc*.exe`), and HANDOFF.md's own
prior entry for it references a `/home/claude/tools/...` path from a
now-defunct Linux cloud-sandbox session, confirming it was never built
here. This is the exact same category of gap as `g++`'s absence
blocking `test_schema_table_cpp.py` earlier this session -- a
pre-existing environment limitation, not something arrays broke, and
not something in scope to fix by building a Z80 C compiler toolchain
from source now. Confidence is still reasonably high (the identical
C89 single-brace aggregate-init rule was verified against real vbcc
for the structurally identical 68000 case, and SDCC has no known
reason to diverge from standard C89 aggregate-initialization
semantics specifically, unlike its calling-convention/register-
allocation internals, which genuinely are custom) -- but "reasonably
high confidence" is explicitly flagged as weaker than this project's
own real-toolchain-verified bar, not conflated with it.

**Verified, not assumed, for everything real-toolchain-checkable:** a
combined fixture (Enemy: a 1D `i32:2` array, a 2D `i32:2:3` array, a
1D `string 16:4` array of names) exported and independently verified
per target:
- C++: real MSVC compile (`/W4`, zero warnings) + real execution, both
  AoS (single-header) and SoA modes -- direct field access, real
  `Registry::Find(name)` runtime lookup, row-major stride check,
  `sizeof(Enemy) == SchemaTable[0].record_size` (96 bytes, zero
  padding either side).
- Binary export: independent Python read-back (shares no code with the
  writer, same discipline as `test_binary_export.py`'s own
  `independent_reader.py`) of the real `.gddldata.bin` bytes, byte-for-
  byte, confirming the manifest's own claimed `schema_hash` matches
  C++'s compile-time table exactly (`0x86fcd4cb436de7da`, both paths).
- 68000: real vbcc compile + real vamos execution, AoS and SoA both,
  including the same row-major stride check.
- 6502: real assemble + real py65 memory read-back, all three dialects
  (ACME, 64tass, KickAssembler), each independently confirming the
  exact same 24-byte flat layout at the instance's label address.
- Z80: real assemble + real z80-emulator memory read-back, both
  assembly dialects (SjASMPlus, z88dk-z80asm), same 24-byte layout
  confirmed both ways.
- Both 6502 and Z80's SoA-array rejection confirmed to actually fire
  (real `--layout soa` invocation, real raised error, real message).

Full existing regression suite re-run clean throughout: `export_golden.py`
(79 fixtures, zero content differences -- this stage touched only
export modules, never the core phase 1-8 pipeline), all four
real-toolchain driver suites (17/9/8/4, none of the PRE-EXISTING,
non-array fixtures affected), `test_68000_cli.py`,
`test_binary_export.py`, `multi_file_test.py`, `test_ids_manifest.py`.

**Not yet done, next**: stage 4 (permanent corpus/regression
fixtures -- matching flags' own stage 5 precedent, this is where the
ad hoc real-toolchain verification fixtures built for this stage get
turned into permanent, committed test cases wired into each driver
suite's own CASES list, the same way `export_test_flags.gddl` landed
in `run_all_cpp_tests.py`), then stage 5 (docs, SPEC.md and
`language-basics.md`). The z88dk-C zsdcc verification gap above should
be revisited if/when that toolchain ever gets built on this machine --
not urgent, but worth remembering rather than quietly forgetting.

Zero em-dashes (checked directly, this project's own hard rule).

## Arrays work, stage 4: permanent corpus/regression fixtures

Fourth of five staged passes -- matching `flags`' own stage 5
precedent exactly (see that entry above): this is where the phase 1-8
golden-locking discipline and the ad hoc real-toolchain fixtures built
during stage 3 both become permanent, committed regression coverage,
not one-off scratchpad verification that evaporates at the end of a
session.

**`tests/corpus/arrays/` -- ten new fixtures, phases 1-8 only, no
export.** Same discipline as `corpus/flags/`'s own manifest states
plainly: every value in each fixture's "Expected" comment was computed
by hand first, then confirmed byte-for-byte against
`export_golden.py`'s real captured output before the `.golden.json`
was written, via a small script reading the freshly regenerated
`golden_output.json` and wrapping each new fixture's real `output`
block in the standard `fixture`/`capture_status`/`captured_at`/`output`
envelope -- never hand-transcribed, avoiding exactly the kind of
transcription error that discipline exists to prevent. All ten matched
their hand-computed expectations exactly on the first real run.
Positive baselines (1D and multi-dimensional literals, string
elements including a literal comma inside a quoted element, and the
design's own bracket-indexed copy-and-adjust motivating example, end
to end); negative paths for every rejection this feature has: shape
mismatch (wrong count, missing inner braces), each of the three
explicitly-deferred element types individually, malformed/zero
dimensions, out-of-bounds/uninitialized/multi-dimensional bracket
indexing, both phase-5 static shape checks, and phase 8 completeness
needing zero array-specific code. See `corpus/arrays/MANIFEST.md` for
the full table and the stage-4 coverage checklist. Surgically merged
into the committed `golden_output.json` (structurally diffed first --
exactly the 10 new fixtures added, zero content differences to the
existing 79 -- same discipline as every other corpus update this
session).

**Real-toolchain export fixtures, wired into every driver suite's own
`CASES` list, matching the exact `.gddl` + committed generated output +
hand-written test + CASES-entry pattern `export_test_flags.gddl`
already established:**

- **C++** (`export_cpp_test/`): `export_test_arrays.gddl`, committed
  `generated_arrays.h` (AoS) and `generated_arrays_soa.h` (SoA), and
  `test_generated_arrays.cpp` / `test_generated_arrays_soa.cpp` --
  static-assert-checkable in single-header mode (as flags' own test
  already established), plus a real runtime `Registry::Find(name)`
  lookup and a row-major stride check. Added to `run_all_cpp_tests.py`'s
  `CASES` (17 -> 19; that count is computed from `len(CASES)`, needed
  no manual fix).
- **6502** (`export_6502_test/`): one `.gddl` (u8-only elements,
  matching this target's real scope) exported to all three dialects'
  own committed `.asm`, one hand-written harness per dialect (pure
  data check -- no code execution needed, matching the reasoning
  already used for the stage-3 ad hoc verification), one check script
  per dialect. Added to `ACME_CASES`/`TASS64_CASES`/`KICKASS_CASES`
  (9 -> 12).
- **Z80** (`export_z80_test/`): same pattern, both assembly dialects
  (SjASMPlus, z88dk-z80asm). Added to `SJASMPLUS_CASES`/`Z88DK_CASES`
  (8 -> 10).
- **68000** (`export_68000_test/`): AoS and SoA both, following
  `test_68000_soa.c`/`test_68000_aos_split.c`'s own established shape.
  Added to `CASES` (4 -> 6).
- **Binary export** (`export_binary_test/`): a dedicated, SEPARATE
  fixture and build (`export_test_binary_arrays.gddl`, `check_array_readback`
  as a new numbered check, Check 4) rather than touching the existing
  Item/Object coverage fixture -- purely additive, no risk to
  already-locked schema/offset expectations elsewhere in that suite.
  `independent_reader.py` itself needed real new logic here, not just
  a new fixture: `_independent_parse_array_type` (a SECOND, genuinely
  independent parser of `'ElementType : dim1 : dim2 : ...'`,
  deliberately NOT importing `registry._try_parse_array_type` -- the
  same independence reasoning the whole file's module docstring
  already states is the actual point of it existing) and
  `_unpack_array_level` (row-major recursive unpack, confirmed against
  the writer's layout rather than assumed to match it).

**A real, small gap found and fixed along the way, not silently
carried forward:** three of the four assembly-target driver scripts
(`run_all_6502_tests.py`, `run_all_z80_tests.py`,
`run_all_68000_tests.py`) print a hardcoded `"N/N"` pass count at the
end rather than computing it from the CASES list length the way
`run_all_cpp_tests.py` already does (`len(CASES)`). Updating each
`CASES` list without updating this string would have silently printed
a stale, wrong count once the new array cases started passing --
caught by actually reading the real output after the first re-run
(6502 printed "9/9" with 12 real passing cases), not assumed correct.
Fixed all three to the real new counts (12/12, 10/10, 6/6) rather than
also converting them to `len(...)`-computed strings, matching this
project's own "the smallest change that fixes the actual problem"
discipline -- these three files' own existing style already hardcodes
the dialect-count English text (`"all three dialects"`, `"both
dialects"`) right next to the number, so a full refactor to computed
counts would be a larger, unrelated change than this stage needed to
make.

**Cleanup, not part of the feature itself:** three stray MSVC `.obj`
files had leaked into the repo root during stage 3's own ad hoc
compile probes (already fixed then); this stage found two more stray
build artifacts of the same general kind -- the compiled vbcc test
binaries `test_68000_arrays`/`test_68000_arrays_soa`, landing in
`export_68000_test/` alongside their own `.c` source before being
caught. Added both to `.gitignore` (matching that file's existing
per-binary-name convention for this directory, not a wildcard) and
removed them from the working tree.

Full regression suite re-run clean, one final time, everything
together: `export_golden.py` (89 fixtures now, structurally diffed --
exactly the 10 new array fixtures, zero content differences to the
other 79), all four real-toolchain driver suites at their new real
counts (19/12/10/6), `test_68000_cli.py`, `test_binary_export.py`
(now with its own new Check 4), `multi_file_test.py`,
`test_ids_manifest.py`.

**Not yet done, next**: stage 5, the last stage -- documentation.
SPEC.md needs a new top-level section for arrays (following the exact
pattern section 20 already set for the identifiers manifest earlier
this session: append at the end rather than inserting in the middle,
since several existing sections are cited by number throughout code
comments and other docs). `language-basics.md` needs its own worked,
verified-against-real-output section, matching how the flags feature's
own documentation pass worked (every example re-run through the real
compiler before being written down, not hand-derived). The z88dk-C
zsdcc verification gap (stage 3) remains open, not urgent.

Zero em-dashes (checked directly, this project's own hard rule).

## Arrays work, stage 5: documentation (feature complete)

Fifth and last of the staged passes. Every `.gddl` snippet in both new
doc sections was actually run through the real compiler before being
written down -- captured output copy-pasted verbatim, never hand-typed
approximations -- then re-verified a second time, independently, right
before this entry was written (a small standalone script re-resolving
the two most load-bearing example instances and asserting their exact
field values), confirming the committed doc text still matches real
output, not just at the moment it was first captured. No code changed
this stage, so no regression suite re-run was needed or performed --
same precedent flags' own stage 6 (docs) already established.

**`SPEC.md` section 21 (Arrays), appended at the end** (same reasoning
as section 20's own placement: several existing sections are cited by
number throughout code comments and other docs, so appending avoids
renumbering anything already referenced elsewhere). Four subsections:
21.1 declaration and element-type scope (with the real
`array_element_type_unsupported` error shown verbatim); 21.2 value
literals, the outermost-optional/inner-required brace rule stated with
every example from the original design notes plus the 3-dimensional
case; 21.3 bracket indexing, including the "always either UNINIT as a
whole or fully populated as a whole" invariant and its direct
consequence (why the bare/modify-only form's absence for arrays is
what makes that invariant hold), and the one-dimensional-only scope
limit stated as a real, explicit constraint with its own real error
text, not glossed over; 21.4 export shape, per-target notes covering
the C++ double-brace rule, C89's simpler single-brace rule (68000 and
z88dk C mode both), the 6502/Z80 AoS-only restriction explicitly
tied back to those two targets' own pre-existing `string N` SoA gap
(the same underlying non-power-of-two-stride problem, not a new,
unrelated limitation), and binary export's width computation. Also
added an "Arrays" row to section 19's design-summary table, following
section 20's own precedent for extending that table rather than
leaving it to go stale.

**`docs/language-basics.md`'s new "Arrays: fixed-size sequences"
section**, appended after the existing Flags section (matching how
Flags itself was appended after Identifier domains). Purely additive:
nothing else in the file touched. Covers, in the same
worked-example-then-generated-output style Flags already established:
1D declaration and literal; the outer-brace-optional/inner-required
rule via a real 2D example; `string N` composing with array syntax;
the explicit struct/identifier/flags element-type rejection, shown
with real error text; an array element as a full expression
(cross-field reference plus arithmetic, not just a bare literal); the
bracket-indexed copy-and-adjust motivating example end to end, with
its real generated C++; and the one-dimensional-only bracket-indexing
limit, again with real error text rather than a paraphrase.
Deliberately does NOT cover cross-target export shape (that's SPEC.md
section 21.4's job) -- matching Flags' own choice to show C++ output
only, language-basics.md stays about language semantics, not a
target-by-target export reference.

**This completes the arrays feature, all five stages**, per
`GDDL_Session_Handover.md` section 5's own original plan: parser
(stage 1), registry/resolution (stage 2), export across all five
targets (stage 3), permanent corpus/regression fixtures (stage 4),
documentation (stage 5, this entry). One honestly-recorded, open gap
remains from stage 3, not blocking: SoA layout doesn't support
array-typed fields on 6502 or Z80 yet (matching those targets' own
pre-existing `string N` SoA gap, not a new one arrays introduced),
noted in SPEC.md section 21.4 and this file's own stage-3 entry, not
silently dropped. z88dk C mode's array support was later
toolchain-verified with a real `zsdcc` compile+link (see this file's
"Known gaps" section above) -- `zsdcc` turned out to already be
bundled with the `z88dk` install, no source build needed.

Zero em-dashes (checked directly, this project's own hard rule).

## Pools work, stage 1: parsing `pool TypeName PoolName : N`

New feature, requested directly by the user while working on the C64
game: a way to reserve a fixed-size block of UNINITIALIZED instances of
an existing `define`, laid out per whichever AoS/SoA export flag is
active, for the game itself to populate/manage at runtime (an entity
pool, in the ordinary game-dev sense) -- genuinely new territory for
GDDL, since everything before this assumed every exported field has a
fully-resolved, compile-time-known value (SS7's completeness check).
Designed collaboratively before any code was written, same discipline
as flags/arrays: syntax, zero-init-vs-uninitialized semantics, and
target scope were all explicit decisions, not assumptions. Staged the
same five-part way flags and arrays both were (parser, registry/
resolution, export across all five targets, corpus fixtures, docs).
This entry is stage 1 only.

**Settled design, recorded here since SPEC.md's own new section isn't
written yet (lands with stage 2, once registry-level semantics exist to
document alongside the grammar):**
- Syntax: `pool TypeName PoolName : N` -- a new top-level construct, no
  body (there are no field values to initialize, so an indented block
  under this line is a parse error, not silently accepted).
- No restriction on `TypeName`'s own field composition -- struct/
  identifier/flags/array/string/scalar fields are all fine, since a pool
  never computes or checks any value, only reserves shape-sized space.
- Deliberately NOT identity-bearing: no logical/stable ID, no
  `{Name}_Registry`/`Find()` -- pool slots are addressed by plain index
  (0..N-1) by the game itself, never looked up by name or hash the way
  named instances are. Only needs an ordinary "name not already taken"
  check at registration, not the hash-collision table identifiers/
  instances share (SS4.1.1's Collision Detection).
- Never enters phase 6 (resolve) or phase 8 (completeness check) at all
  -- there is nothing to resolve or check, by construction, not a
  carve-out bolted onto those phases after the fact.
- AoS/SoA layout applies to a pool exactly like it applies to named
  instances today -- SS13.6's "layout is never source-level syntax"
  principle stays intact; a pool declaration carries no layout opinion
  of its own, deliberately, so it doesn't punch a hole in that
  principle.
- Genuinely uninitialized, not zero-filled -- confirmed directly with
  the user this is deliberate and target-asymmetric: 6502/Z80/68000
  assembly and the standalone binary format can reserve real, unwritten
  space (BSS-style `.res`/`ds` directives on the assembly targets, pure
  directory/metadata with no instance bytes at all for the binary
  format -- both genuinely free of cost, which is the actual point for
  a C64 build where disk/tape space matters). C++ is the one exception,
  not by choice: a namespace-scope POD array with no initializer is
  zero-initialized by the C++ standard itself, unconditionally -- there
  is no way to keep a plain, directly-indexable `Entity Pool[40]` while
  also avoiding that. Confirmed acceptable to the user as-is; SPEC.md's
  new section (stage 2 or later, once export shape is real) will state
  this asymmetry plainly rather than let it read as an inconsistency
  nobody noticed.
- Mutability: pool storage must be non-const (`inline Entity
  EntityPool[40];`, no `constexpr`), unlike named instances' `inline
  constexpr` -- the entire point is the game writing into it at
  runtime. SoA export names its per-field arrays after the POOL's own
  name, not the type's (`EntityPool_SoA`-shaped, not `Entity_SoA`-
  shaped), since two differently-named pools of the same type must not
  collide.
- All five export targets are in scope for the first pass (the user's
  own choice, not the smaller "6502 first" precedent flags/arrays each
  used) -- stage 3 will need real verification against each target's
  own toolchain the same way every prior feature has, not "should work"
  reasoning.

**Implementation, this stage:**
- `ast_nodes.py`: new `PoolDecl` (`type_name`, `pool_name`, `count`),
  positioned next to `InstanceDecl` -- structurally similar (a
  top-level construct naming an existing type) but semantically
  distinct enough (no body at all, ever) that it's its own node, not a
  variant of `InstanceDecl` with an empty body allowed. This mirrors the
  precedent already set for `flags` vs. `identifier`: a real semantic
  difference gets a distinct node, not a shared one with a mode flag.
- `parser.py`: `_parse_one` gained a `tokens[0] == "pool"` dispatch
  branch (alongside `identifier`/`flags`/`define`, before the
  instance-decl fallback), routing to new `_parse_pool_decl`. Parses the
  whole `pool TypeName PoolName : N` shape as one fixed grammar in this
  one place -- deliberately NOT deferred to registry.py the way array
  dimensions are (`ElementType : dim1 : dim2` inside a field's raw
  `type_tokens`, interpreted only at registry time, SS21.1): that
  precedent applies to text sitting inside another construct's payload,
  but this IS the top-level statement's own grammar, the same reasoning
  `flags`' width token already gets checked immediately in
  `_parse_flags_block` rather than deferred. New `_POOL_COUNT_RE`
  (`^\d+$`) validates the count is a plain non-negative integer literal
  at parse time; `TypeName`/`PoolName` themselves are captured raw and
  left for registry to validate (matching `_parse_instance_decl`'s own
  precedent -- it doesn't regex-validate `type_name`/`instance_name`
  either, that's a registration-time concern once a symbol table
  exists to check against).
- Body rejection reuses the existing `_parse_statement_block` call
  (so indentation is still consumed correctly, not left dangling) and
  raises a clear, dedicated error naming exactly why a body can never
  appear here, rather than reusing OpStmt's generic "unexpected
  indented block" wording -- the reason is different (nothing to
  initialize, not "this statement shape doesn't nest") and worth saying
  plainly.

**Verified, not assumed:** a scratch script (happy path plus three error
shapes -- non-integer count, missing colon, missing count -- plus body
rejection) confirmed directly against the real parser, not reasoned
about. Full regression suite (`export_golden.py`, 89 fixtures) re-run
clean, zero content differences against the previously committed
`golden_output.json` -- confirming this stage changed no existing
behavior anywhere, purely additive grammar recognition.

**Not yet done, next**: stage 2 (registry -- validating `TypeName`
actually names a known `define`, the pool name isn't already taken by
anything else in the compile unit, the count is nonzero; SPEC.md's own
new section gets written here, once there's real registry-level
semantics to document alongside the grammar, not just a parser shape).

Zero em-dashes (checked directly, this project's own hard rule).

## Pools work, stage 2: registry validation

Second of five staged passes (see stage 1 above for the full settled
design and its own reasoning). This stage: `Registry.pools` (name ->
`PoolDecl`), duplicate-pool-name detection, and the two real validation
checks a pool needs that nothing else in the pipeline would ever catch
for it (see below for why).

**`registry.py`**: `self.pools = {}` added alongside `self.instances`.
A new `PoolDecl` branch in the main per-node registration loop --
duplicate-name detection follows the exact same "first wins, append a
CompileError, continue" pattern every other namespace here already
uses, and registers the pool regardless of whether `TypeName` turns out
to be valid (checked separately, below), mirroring the precedent
identifier width-overflow already established (register first, report
validation errors as a separate pass). Deliberately NOT run through
`_check_id_collision`/`self._id_table` -- pools carry no logical/stable
ID at all (SS22.2), so there is no hash to collide in the first place.

**Why pool type-checking needed its own dedicated pass, unlike an
ordinary instance's `type_name`**: an instance with an unknown type and
an empty body can currently slip through phase 5 undetected (phase 5's
`_check_field_shape` only walks a body's statements -- an empty body has
none to walk, so a mistyped `type_name` with no field statements
referencing it produces zero errors anywhere in the existing pipeline;
a genuine pre-existing gap, confirmed by reading `phase5.py` directly,
not fixed here since it's outside this feature's own scope). A pool has
NO body at all, ever, by construction -- so if pools inherited that
same "nothing to walk" gap, an unknown `TypeName` would silently
compile clean. New `Registry._check_pool_types()` (mirroring
`_check_indexed_field_types`/`_check_array_field_types`'s own "run once
after the main loop, so `self.defines` is guaranteed fully populated
regardless of declaration order" pattern) closes this directly: `pool_
unknown_type` if `TypeName` isn't a real `define`, `pool_zero_count` if
the count is exactly 0 (the parser's own `_POOL_COUNT_RE` already
rejects negative/non-integer counts at parse time, so zero is the one
remaining malformed case left for registration).

**Verified, not assumed:** a scratch script confirmed five real cases
against the actual registry -- happy path; a pool declared BEFORE its
own type's `define` block in source order (confirmed this resolves
correctly, proving the post-main-loop placement actually matters, not
just defensive positioning); an unknown-type reference; a zero count;
a duplicate pool name. All five produced exactly the expected errors
(or none, for the two success cases). Full regression re-run clean:
`export_golden.py` (89 fixtures, zero content differences against the
committed `golden_output.json`) and the full `pytest tests` suite (22
tests, all passing) -- the real-toolchain driver suites
(`export_6502_test`, `export_z80_test`, `export_68000_test`'s CLI
suite, `multi_file_test`'s Z80 run) aren't collected by a plain `pytest
tests` invocation and weren't separately run this stage, since nothing
this stage touches export at all; they'll get real verification once
stage 3 actually reaches those code paths, matching how flags/arrays'
own early stages were verified.

**SPEC.md SS22 written this stage** (declaration syntax SS22.1, the
not-identity-bearing rule SS22.2, resolution/validation scope SS22.3) --
marked at the very top of the new section as partial: registry
semantics are real and verified, but SS22.4 (export) is explicitly
labeled "not yet implemented," not glossed over, since nothing about
export exists yet to document as fact. One citation error caught and
fixed before this entry was written: an early draft cited "SS12" for
the namespace-scoped duplicate-name-checking precedent, which is
actually the Compiler Pipeline section, not a namespace-scoping rule at
all -- SPEC.md has no single numbered section stating that rule
explicitly (it lives only in `registry.py`'s own module docstring), so
the citation was removed rather than left wrong or invented.

**Not yet done, next**: stage 3 (export, all five targets at once per
the user's own scope choice -- unlike flags/arrays' smaller "one target
first" precedent). Real per-target verification against actual
toolchains required before any of it is called done, matching this
project's standing discipline.

Zero em-dashes (checked directly, this project's own hard rule).

## Pools work, stage 3a: C++ export (both single-header and split mode)

First target of stage 3 (see stage 1's entry for the full settled
design). User asked for this to proceed "in steps" rather than all five
targets in one pass, so stage 3 is being split into its own per-target
sub-entries -- this one covers C++ only, both output modes.

**`export_cpp.py`**: new `emit_pools(lines, reg, layout)` (single-header
mode, `generate_header`) and `emit_pools_split(header_lines, cpp_lines,
reg, layout)` (split mode, `generate_split`), both called right after
the SS17.5 schema table and before the closing `} // namespace GDDL`,
gated on `if reg.pools:` so a compile with no pools produces byte-
identical output to before this work (no unconditional blank line or
empty block ever appears).

Reuses `_flatten_leaves` (the exact same leaf-enumeration helper named
instances' own SoA export already uses) for SoA pool columns, and
`_cpp_field_type` for the per-leaf/per-field C++ type -- no new type-
mapping logic anywhere, pools ride entirely on infrastructure this
exporter already had. AoS/aos-linear: `inline {Type} {PoolName}[N];`,
a plain top-level array. SoA: `namespace {PoolName}_SoA { inline
{FieldType} {leaf_path}[N]; ... }`, named after the POOL not the type
(SS22.2 -- two differently-named pools of the same type must not
collide). Split mode mirrors this with `extern` declarations in the
header and the one real (still non-const) definition in the .cpp,
matching the exact "avoid per-TU duplication" reasoning every other
split-mode definition in this file already follows -- `inline` was
correct for single-header mode specifically because it's genuinely
merged across every including TU, but split mode's whole point is
exactly one real definition, so `extern`/definition is the right split-
mode shape here too, not `inline` copied over unchanged.

**Never `constexpr`, in either mode** -- confirmed this compiles and
behaves correctly under real, deliberate write-then-read-back usage
(see verification below), not just "the compiler accepted it."

**Verified, not assumed, against a real MSVC compile+run (this
project's own established toolchain, `cl.exe` via `vcvars64.bat`) for
every combination**: single-header AoS, single-header aos-linear,
single-header SoA, split-mode AoS (two real, separately-compiled
translation units, linked), split-mode SoA (same). Every test writes
real values into every pool slot after confirming the zero-initial
state (C++'s own static-zero-init guarantee, SS22.4's documented
asymmetry, not something this exporter had to do anything for), reads
them back, and asserts -- for SoA specifically, including a `string N`
leaf's flat `N*count` byte layout, written and read back at its exact
per-slot byte offset. All five compiled clean under `/W4 /WX` (warnings
as errors) and ran correctly. Full regression re-run clean after:
`export_golden.py` (89 fixtures, zero diff), `pytest tests` (22
passing), and the full real-toolchain `export_cpp_test` suite (19/19,
including the pre-existing split-mode tests, confirming this change
didn't disturb anything already there).

**Not yet done, next**: stage 3b, 6502 export.

Zero em-dashes (checked directly, this project's own hard rule).
