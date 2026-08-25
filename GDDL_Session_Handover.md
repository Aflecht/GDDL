# GDDL Project: Session Handover

This document exists because development is moving from a hosted conversational session into a local Claude Code session. It is meant to let a brand-new Claude instance pick up this project with zero prior memory and continue exactly where things left off, without re-deriving anything already settled. Read this whole document before doing anything else.

**Environment note**: this document was originally written for a hosted chat session with no direct git push access (all work delivered as tarballs for the person to apply and push themselves). Running locally in Claude Code may change that, you may have direct filesystem and git access to the person's actual local clone. Don't assume either way; confirm with the person how they want commits and pushes handled in this new setup before doing anything that touches git history.

## 1. What GDDL is, and what your role is

GDDL (Game Data Definition Language) is a compile-time game data definition language: item stats, character definitions, ability tables, loot tables, anything with a fixed shape a game would otherwise hand-write as a struct or spreadsheet. It compiles to real C++ structs, 6502/Z80 assembly, C89 (68000, via `vbcc`), or a portable binary format, from one source of truth.

**Live repository**: `https://github.com/Aflecht/GDDL.git`, public, `main` and `dev` branches. **No AI session has push access, ever.** The person you're talking to is the sole git operator. Your workflow: clone `dev` fresh at the start of any task, do your work, deliver a tarball (or individual files for doc-only changes) for them to apply and push themselves, then do a fresh-clone verification once they confirm the push. Never claim something is "live" or "done" without having independently re-cloned and checked it yourself.

You are functioning as the project's design authority and, in practice throughout this whole conversation, its direct implementer too. Earlier project history had a separate "Compiler Core" session doing implementation while "Lead" (you) did design/arbitration, but for a long stretch of this actual conversation Lead has been writing and verifying all the code directly. Continue doing that unless the person redirects you.

## 2. Non-negotiable working conventions, established over a very long conversation

- **No em-dashes anywhere**, in code comments, commit messages, or documentation. The em-dash is Unicode U+2014; before shipping anything, search the file for that codepoint (e.g. `grep -c $'\u2014' <file>` in bash) and confirm zero.
- **Verify every claim against real output before writing it down.** Every code example in every doc page was checked against actual compiled/run output, not written from memory of the spec. Every error message shown anywhere was copied from a real compiler run, not typed by hand. This has caught real bugs and real doc-drift multiple times; do not skip it.
- **Full regression after every change**: `compiler-python/tests/export_golden.py` (72-fixture corpus) at minimum, plus whichever hand-written test suites touch the area you changed (`multi_file_test/`, `export_68000_test/`, `export_binary_test/`, `export_cpp_test/`, `export_emit_all_domains_test/`).
- **Watch for stale committed fixtures.** Several past changes (comment additions, column alignment) altered the actual bytes of committed test `.h`/`.cpp` files that predate the change. Always check whether a change affects existing committed generated files, and regenerate + structurally re-verify them if so, don't just trust the corpus regression alone; some fixtures are hand-maintained outside it.
- **`HANDOFF.md`** (at `compiler-python/HANDOFF.md`) is the project's own dev journal. Every real piece of work gets an entry: what was found, what was fixed, how it was validated. Read its tail when you start, write a new entry before you finish.
- **This convention was written for the old hosted-chat environment and may not apply as-is locally**: deliver work as a tarball via `present_files`, or as individual files for doc-only changes, and keep a running personal tracking repo (any scratch git repo under `/mnt/user-data/outputs/`) for your own bookkeeping across turns, optional, not something the person consumes directly. In Claude Code you likely have direct filesystem and git access instead, confirm with the person which model they actually want before assuming either one. Either way, the real record of "what's actually shipped" is always the live GitHub repo, not any local scratch copy.
- If you find something wrong while doing something else (stale docs, a real bug, a broken test assertion), say so plainly and fix it, don't just note it and move on silently.

## 3. Current state of the live repository: confirmed shipped

Everything below is live on both `main` and `dev` (they were merged and confirmed in sync as of the last checkpoint), independently re-verified via fresh clone, not just trusted from delivery:

- **All five export targets** (C++, 6502, Z80, 68000, standalone binary) complete, each validated against real toolchains (g++17, ACME/KickAssembler/64tass, SjASMPlus/z88dk, vbcc where available, real emulators where applicable).
- **Full documentation set**: `README.md` plus five pages in `docs/`: `getting-started.md`, `data-layouts.md`, `dispatch-guide.md`, `templates-guide.md`, `language-basics.md`. Every code example in every one of these is byte-verified against real compiler output.
- **Real bugs found and fixed during this conversation**, all shipped:
  - A validation gap where genuine compile-time errors (`resolver.errors`, `resolver.blocked`, `resolver.reg.duplicate_errors`, uninitialized fields) were computed correctly but never actually checked by any exporter CLI, so broken instances silently vanished from output with `exit 0` instead of failing the build. Fixed via `validate.py`'s `check_and_report()`, now called by all five exporters before rendering.
  - A real `#include` path bug: the C++ exporter embedded the raw `-o` path verbatim into the generated `#include` line, which corrupted the include on Windows (`Generated\Items.h`, where the backslash is a C++ string escape character, not a working path separator once embedded in a string literal). Fixed with a `_include_basename()` helper that's deliberately not `os.path.basename` (confirmed that silently fails on a Linux-hosted run given a Windows-style path).
  - Description-as-comment: identifier domain description text now appears as a `//` comment on the corresponding C++ enum entry, both the plain hash enum and the `_Indexed` companion, both single-header and split modes.
  - Column alignment: struct fields and enum entries (both C++ and 68000's C89 struct fields / `#define` domain constants) are column-aligned per-block (never globally across the file), via a shared `_align_columns()` helper in `export_cpp.py` that `export_68000.py` imports.
  - **Duplicate names are a confirmed, deliberate, hard build-blocking error, always**, including across multi-file (`§18`) compilation. This was explicitly discussed and decided: mods and base games are realistically separate compilation units (combined only at runtime via hash IDs), never combined at the source level the way `§18` does, so a source-level name collision within one compile is almost always a genuine mistake worth failing loudly on. Do not revisit this without the person raising it again.
  - **Error message formatting**: the internal `[phase N, check_name]` tag is now dropped from default CLI output (it's compiler-internals noise for an end user), restorable via `--verbose-errors` on all five exporters. This was item 1 of a 3-item task list; it is fully done and shipped, do not redo it.

## 4. In progress right now: `flags`, bit literals, and bitwise operators

This is the **live, active task**. It was designed through a long, careful back-and-forth with the person, working from an uploaded reference file (`Entity.gddl`, full content reproduced in section 7 below). Every decision below is settled and should not be re-litigated; if you find yourself wanting to ask the person something covered here, check this document again first.

### 4.1 The `flags` construct, fully specified

- Syntax: `flags DomainName WidthType` (e.g. `flags ComponentFlags u64`), block body lists members, one per line.
- **`flags` is a distinct language construct from `identifier`, not a variant of it.** `identifier` gives mod-safe, hash-based *identity* to a closed set of mutually-exclusive choices, exactly one value ever. `flags` gives real, predictable, *combinable* bit positions, several can be true at once. This distinction drives the export design too (see 4.3).
- Every member's value is a single bit or zero, no exceptions in this first pass. (A later idea, pre-combined "alias" members like `both = b2 | b5` for a named shortcut, was explicitly discussed and explicitly deferred: "make each flags element always be a pow2 value, no exceptions... if a real need raises for combining bits already at definition stage, we look at this again." Do not build alias members unless the person explicitly asks again.)
- `= bN` is an explicit bit position, meaning `1 << N`. Omitting the value entirely auto-assigns the next unclaimed bit, in declaration order. In the reference file, `is_damageable = b0` is followed by five members with no explicit value at all (`is_pickupable`, `is_equippable`, ...), which should auto-assign bits 1 through 5 in order. `none = 0` is a valid sentinel and does not consume a bit position.
- **`bN` is a general integer literal**, valid anywhere an integer literal is valid in the language, not scoped only to `flags` blocks. (Confirmed with the person directly.)
- Each bit position claimed exactly once, explicit or automatic; a second claim on an already-claimed bit is a compile-time error.
- A `flags` domain whose real bit-flag members exceed what its declared width can address is a compile-time error, the same shape as the existing `identifier`/`@`-indexed width-overflow check (`indexed_width_overflow` in `registry.py`), reuse that pattern.
- **Combining bits on a field uses bitwise operators only.** The person explicitly rejected using `+` for this (idempotency: `flag | flag == flag`, but `flag + flag != flag`, a real, sharp footgun) and confirmed wanting **all four standard bitwise operators**: `|`, `&`, `^`, `~` ("users most likely want to turn bits on and off as usual").
- **Arithmetic operators (`+ - * /`) are a compile-time error on a flags-typed field.** Not just discouraged, rejected outright, this was explicit.
- **Bitwise operators are a compile-time error on any field that is NOT flags-typed.** There is no other bitmask mechanism in the language (no user-defined C-style integer enums exist), so bitwise ops exist only for `flags`, full stop, in both directions.
- Op-statements on flags-typed fields should work the same way they already do elsewhere: `component_flags | ComponentFlags.is_movable` as its own statement line, combining into whatever the field's current value already is (the existing "field's own current value is the implicit leading operand" rule generalizes naturally here).

### 4.2 Parser-level finding: this is genuinely small to add, already verified

Checked directly in `resolve.py` before any design commitment was made, this is real, confirmed fact, not a guess:

- Unary `-`/`+` are **not** a tokenizer hack. `_parse_operand`'s own docstring already documents the grammar as `operand := NUMBER | reference | '(' expr ')' | '-' operand | '+' operand`, a real, explicit recursive case. Adding unary `~` is a third instance of the exact same pattern: check for the token, recurse into `_parse_operand` for whatever follows, apply the operation, with an integer-only type check (bitwise NOT on a float is meaningless).
- Binary `|`, `&`, `^` are the same story one level up: `_fold_left` walks a fixed tuple `("+", "-", "*", "/")` and dispatches to `_apply_binop`. Extending that tuple and adding three more cases to `_apply_binop` is the same pattern, not new architecture.
- **Four touch points total** for the operator/literal side, all additive, all following patterns already proven twice in the existing code:
  1. `resolve.py`'s `_TOKEN_RE` tokenizer regex, the operator character class `[+\-*/()]` needs `~|&^` added, and a new alternative for the `bN` literal needs adding **before** the general identifier pattern in the alternation (regex tries alternatives in order; if the identifier pattern came first, `b0` would just match as an ordinary identifier and the bit-literal branch would never fire).
  2. `resolve.py`'s `_fold_left` operator tuple, extend to include the three binary bitwise operators.
  3. `resolve.py`'s `_apply_binop`, add the three binary computations.
  4. `resolve.py`'s `_parse_operand`, add the unary `~` case.
  5. `parser.py`'s separate `OPERATORS = ("+", "-", "*", "/")` tuple, used at an earlier parse stage to recognize an op-statement line in the first place (distinct from the expression evaluator above), needs the same extension.

The real work for `flags` is everywhere else: bit-claim tracking, the width-overflow check, rejecting arithmetic/bitwise ops on the wrong field kinds, and all five export targets. The operators themselves are the easy part.

### 4.3 C++ export shape: settled after real, compiled testing, do not relitigate

Three real options were built and compiled, not just discussed abstractly. Full results:

| Approach | Bitwise ops work directly | Natural `if (flags & X)` check works | Cross-domain name collision |
|---|---|---|---|
| `enum class Domain : width` | **No**, confirmed via real compile: `no match for 'operator&'` with zero overloads written | No, needs `!= Domain::none` even with overloads added | No (scoped) |
| Plain `enum Domain : width` (unscoped) | Yes | Yes | **Yes, confirmed via real compile**: `'none' conflicts with a previous declaration` the moment a second flags domain also wants a `none` member (which the reference file already does across several `identifier` domains) |
| **`namespace Domain { constexpr width member = ...; }`** | **Yes** | **Yes** | **No** |

**Decided, confirmed shape**:

```cpp
namespace ComponentFlags
{
    constexpr uint64_t none              = 0;
    constexpr uint64_t is_damageable     = 1ULL << 0;
    constexpr uint64_t is_pickupable     = 1ULL << 1;
    // ... one per member, in declaration order, using each member's
    // actual claimed bit position (explicit bN or auto-assigned)
}

struct Entity
{
    uint64_t component_flags;   // the field itself is the raw width type, NOT a named/wrapped type
};
```

- Width maps the same way `identifier`'s `@`-indexed companion enum already does (`u8`→`uint8_t`, `u16`→`uint16_t`, `u32`→`uint32_t`, `u64`→`uint64_t`, see `_CPP_INT_TYPES` or equivalent lookup already in `export_cpp.py`).
- The `namespace` gives the same real scoping `enum class` would (so `ComponentFlags::none` and some other domain's `Something::none` never collide), without inheriting `enum class`'s complete lack of built-in operators. This was the deciding insight, confirmed by real compiled proof, not argued in the abstract.
- **6502/Z80/68000**: plain integer constants, the same shape `identifier` domains already use on those targets (no enum concept exists there at all), just real bit values instead of a dense index. No hash-vs-index duality to carry over, `flags` never had one.

### 4.4 Exact current implementation state: pick up here

**Nothing has been applied to any real file yet.** The previous session got as far as designing and standalone-testing the new tokenizer regex, then ran out of context before applying it.

The tested, confirmed-correct regex (tested against 13 real cases including the tricky ones: `b0value` must NOT split into `b0`+`value`, `bacon` must NOT split at all, multi-digit bit positions, all four new operators alone and combined with real GDDL-shaped expressions):

```python
_TOKEN_RE = re.compile(
    r"\d+\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?|"
    r"b\d+(?!\w)|"
    r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*|[+\-*/()~|&^]"
)
```

The `(?!\w)` negative lookahead after `b\d+` is load-bearing: without it, an identifier like `b0value` would incorrectly split into a bit-literal token `b0` followed by a stray identifier token `value`. All 13 standalone test cases passed with this exact pattern; do not simplify it away.

**Next concrete steps, in order:**

1. Clone `dev` fresh. Apply the tested regex above to `resolve.py`'s `_TOKEN_RE`. Re-verify with real tokenization (not just the standalone test already done, run it through the actual file this time) and a real end-to-end compile of a tiny fixture using `b0`, `~`, `|`, `&`, `^` in an expression, to confirm the change is wired correctly, not just syntactically present.
2. Extend `parser.py`'s `OPERATORS` tuple the same way. Before assuming this is a trivial copy-paste, check the exact call site(s) where `OPERATORS` is used, confirm whether it needs the unary case represented at all at that stage, or only the binary set, don't assume, verify.
3. Extend `resolve.py`'s `_fold_left` tuple and `_apply_binop` for the three binary bitwise operators, and `_parse_operand` for unary `~`. Add real type-checking (integer operands only; reject float operands to bitwise ops with a clear error, matching this project's established "precise, real error, never a vague failure" standard).
4. Full regression (`export_golden.py` at minimum) after this stage, before moving to stage 2. Nothing here should change any *existing* behavior, only add new token/operator recognition, so the existing 72-fixture corpus should be completely unaffected; if it isn't, something is wrong.
5. Write a `HANDOFF.md` entry for this stage specifically before moving on, matching the established pattern of one entry per real, validated piece of work.

**Then continue with the remaining stages of the `flags` feature**, in this order (from the originally agreed plan, still accurate):

- **Stage 2, parsing `flags` itself.** This is genuinely new grammar, not a thin copy of `identifier`'s parsing: an `identifier` member's value is always a description string; a `flags` member's value is one of three different shapes (bare name / `= NUMBER` / `= bN`), with none of that resembling `identifier`'s existing grammar at all.
- **Stage 3, registry and resolution logic.** Bit-claim tracking with auto-assignment and duplicate-claim detection (explicit-vs-explicit, explicit-vs-auto, and auto-vs-auto collisions all need catching). Width-overflow check. Reject arithmetic on flags-typed fields; reject bitwise on everything else. Confirm op-statement support for flags fields works correctly (copy-a-base-then-turn-on-one-more-flag).
- **Stage 4, export, all five targets.** C++ shape is fully settled (4.3 above). 6502/Z80/68000/binary: plain integer constants, same shape `identifier` domains already use, real bit values instead of a dense index.
- **Stage 5, validation.** New permanent corpus fixtures: valid auto-assignment, explicit `bN` mixed with auto-assignment, a duplicate-bit-claim error, the width-overflow error, arithmetic-rejected-on-flags, bitwise-rejected-elsewhere, and a real combined value actually read back correctly from real compiled/run output. Same standard as every other feature in this project: real toolchain execution where applicable, not just "should work."
- **Stage 6, docs.** Hold off deciding where this content lives (folded into `language-basics.md`, or its own guide the way `templates-guide.md` got one) until there's a real draft to look at; don't decide that on paper before the material exists.

## 5. New, unstarted: incoming feature request from gscript (external, another AI's project)

This arrived after the `flags` design work above and has **not been investigated, evaluated, or prioritized against `flags`/arrays yet**. It's a real, technically precise request from another AI developing gscript, a scripting layer built on top of GDDL (lives in `Game/Script`, a separate project/codebase from GDDL itself, consuming GDDL's generated C++ output). Relayed here close to verbatim since it cites specific line numbers and function signatures worth preserving exactly, not paraphrasing.

**The request, as received:**

> Feature request: runtime membership registry for identifier domains (like data-record types already have)
>
> Context: gscript (the scripting layer built on top of GDDL, in `Game/Script`) is adding load-time validation for mods that extend or override values in a GDDL identifier domain (e.g., a mod adding a new member to an enum-like domain such as `EnemyAIType`, and another mod's script binding a handler to it). To validate this safely at runtime, across mods that may or may not know about each other at compile time, gscript's `Mod_Loader` needs to be able to ask, at runtime, "is this raw `uint64_t` actually a valid, currently-known member of domain X?"
>
> The problem: `export_cpp.py` currently generates two different kinds of output (per its own header comment, lines 23-25):
>
> - Identifier domains → a bare `enum class DomainName : uint64_t { ... }` only (see the `# ---- 1. identifier domains -> enum class ----` block, around line 832).
> - Data-record types (structs) → the enum/struct plus a companion `TypeName_Registry` namespace with `Table`, `Find(uint64_t)`, and `Find(string_view)` (visible in the generated output today, e.g. `Entity_Registry::Find(uint64_t)` in a shipped `Entities.h`).
>
> So a struct-typed record can be looked up by ID at runtime, but an identifier domain's own members cannot, a C++ `enum class` has no runtime reflection, and nothing else is generated to compensate. This means there's currently no way for any C++ code (not just gscript) to check "does this ID actually belong to this domain" without it having been known and named at compile time.
>
> What we'd need: identifier domains should get the same kind of companion registry data-record types already get, a `DomainName_Registry` namespace (or however you'd want to name/shape it) with at least `Find(uint64_t) -> bool` (or returning the member's name/description) and ideally `Find(string_view) -> bool` too, generated alongside the existing `enum class`, populated from the domain's own known members at GDDL-compile time. Doesn't need anything more elaborate than what data-record types already get, just the same pattern applied to the identifier-domain code path in `export_cpp.py` that currently skips it.
>
> Is this feasible, and is there a reason identifier domains were deliberately left out of the registry-generation path when data-record types got it?

**What's already been confirmed, and what hasn't:** the header comment and code-location references in the request (`export_cpp.py` lines 23-25, the identifier-domain block around line 832, the existing `TypeName_Registry` pattern for data-record types) were spot-checked as real and accurately cited, this is someone who has genuinely read the actual source, not a speculative request. **The actual technical question, whether there's a deliberate reason identifier domains were left out of the registry pattern, has not yet been investigated.** That's real, honest, unresolved work, don't assume either answer. Check `SPEC.md` and `HANDOFF.md` for any prior discussion of this before concluding it either way, and check whether skipping it was ever discussed at all versus simply not having come up until now.

**Not yet prioritized against the `flags`/arrays work in sections 4 and 6.** All three are now real, pending items. Bring this to the person's attention and let them decide sequencing rather than assuming this jumps the queue just because it arrived more recently, or assuming it waits just because it arrived later.

## 6. Arrays: fully designed, but explicitly deferred until `flags` is done

Do not start this until `flags` (all six stages above) is complete and shipped. The person explicitly set this build order: `flags` first because it's smaller and proves the "new construct, five export targets" pipeline before the bigger, riskier array feature gets built on top of it.

Full settled spec, so it's ready when the time comes:

- Declaration syntax: `field = ElementType : dim1 : dim2 : ... : dimN`, e.g. `damage_min_max = i32 : 2` for a 2-element `i32` array, compiling to `std::array<int32_t, 2> damage_min_max;` in C++.
- The outermost brace layer on a *value* is always optional; inner grouping braces are required wherever they're needed to disambiguate shape. Confirmed examples from the person directly:
  ```
  damage_min_max = 10, 30                              // i32 : 2
  damage_min_max = { 10, 30 }                          // i32 : 2 (same thing)
  damage_min_max = { 10, 30, 5 }, { 20, 50, 8 }        // i32 : 2 : 3
  damage_min_max = {{ 10, 30, 5 }, { 20, 50, 8 }}, {{ 10, 30, 5 }, { 20, 50, 8 }}   // i32 : 2 : 2 : 3
  ```
- `names = string 16 : 4`, an array of four fixed 16-byte strings, confirmed directly as the intended syntax for string-array declarations (the element's own `string N` width syntax composes with the array-dimension syntax exactly as you'd expect).
- Struct-typed or identifier-typed array elements: **explicitly deferred to a later pass**, confirmed by the person ("these can be deferred to a second pass later"). First-pass scope is scalars and strings only.
- Op-statements and cross-field references **do** apply to arrays, confirmed needed directly: the motivating example is a `Goblin`/`Enemy`-style copy-and-adjust, where a derived instance copies a base's `hitpoints_min_max` array and then needs to modify just the max value.
- **Element access and modification use direct bracket indexing**, confirmed as the chosen syntax over a nested-block modify-only form: `damage_min_max[1] = 200`. This extends naturally to op-statements too, `damage_min_max[1] + 50` following the same "current value at that index is the implicit leading operand" rule every other op-statement already has. (A struct-style nested-block alternative was presented and explicitly rejected in favor of this direct form.)
- Export shape: match how C++ itself lays out nested `std::array` (row-major, contiguous), applied **uniformly across every export target**, not just C++, since that's also simply how real C arrays already lay out on every one of these targets. Confirmed directly ("match this how C++ does this").

## 7. The reference file (`Entity.gddl`), verbatim

This was uploaded by the person as the concrete reference for the `flags`/`bN` design (arrays were designed separately, in conversation, with no file reference; the syntax in section 6 above is the complete and only spec for arrays). Reproduced here in full since a new session won't have file-upload access to the original.

```gddl
// Invoked when you pickup this item
identifier ItemPickupType
	none			= "You cannot pickup this object"
	normal			= "You can pickup this object"
	cursed			= "The object attached itself to your hand permanently"
	trap_explode	= "Explodes when picked up, destroys the object"
	trap_teleport	= "Teleports the person picking up the object, then changes the object into a normal object"


// Invoked when you drop this item
identifier ItemDropType
	none			= "You cannot drop this object"
	normal			= "You can drop this object"
	trap_explode	= "Explodes when dropped, destroys the object"		// Can also be used for throwing items at enemies which trigger the explosion


// Invoked when you put this item on
identifier ItemPutOnType
	none			= "You cannot wield nor wear this item"
	wield			= "You can wield this item"
	wear			= "You can wear this item"


// Invoked when item is taken off
identifier ItemTakeOffType
	none			= "You cannot remove this item"
	normal			= "You can take off this item"


identifier ItemControlHandlerType
	none						= "None"
	ai							= "AI controls this entity"
	script						= "Script controls this entity"
	player_controls				= "Player controls this entity"


identifier ItemMoveHandlerType
	none						= "None"
	normal						= "Add velocity to speed and calculate new position"
	physics						= "Same as normal but also add gravity and collisions"


// Invoked when the item is in hand or worn
identifier ItemPassiveEffectType
	none						= "None"
	hitpoints_more				= "More hitpoints"
	hitpoints_regenerate		= "Regenerate hitpoints slowly"
	armor_points				= "More armor points"
	protect_from_fire			= "Protection from fire"
	protect_from_cold			= "Protection from cold"
	protect_from_poison			= "Protection from poison"
	dark_vision					= "See in dark"
	better_hearing				= "Hear better"
	monster_magnet				= "Makes enemies easily notice the owner of this object"


// Invoked when the item is used in regular way
identifier ItemUseEffectType
	none						= "None"
	heal						= "Add health"
	damage_poison				= "Add poison damage"
	damage_explosion			= "Add damage"
	illuminate					= "Shines light to surrounding area"


// Invoked when the item is used for attacking
identifier ItemAttackType
	none						= "None"
	melee						= "Melee attack"
	ranged						= "Ranged attack"



//
// Components
//
// With "flags" keyword, values must always be powers of 2 or zero.
// All other values are a compile time error.
//
// If no value is given for a field, the first unused bit is assigned to that field.
// Each bit can be used only once.
//
flags ComponentFlags u64
	none			= 0		// Start enumertating from 0 onward, one bit at a time
	is_damageable	= b0	// Set bit 0, then progressively assign the next bits for rest of the field. NOTE: This " = b0" should actually be redundant, as this field would automatically be assigned the first unused bit, which is bit 0
	is_pickupable
	is_equippable
	is_movable
	is_controllable
	is_passive_effect
	is_use
	is_attack

define Damageable
	hitpoints		= i32
	hitpoints_min	= i32
	hitpoints_max	= i32

define Pickupable
	effect_pickup	= ItemPickupType
	effect_drop		= ItemDropType
	weight			= u32

define Equippable
	effect_put_on	= ItemPutOnType
	effect_take_off	= ItemTakeOffType


//
// Entity: all items, object, creatures and the player are Entities
//
define Entity
	component_flags = ComponentFlags		// Bit flags defining which components are present for this entity

	damageable		= Damageable
	pickupable		= Pickupable
	equippable		= Equippable

	move_handler	= ItemMoveHandlerType
	control_handler = ItemControlHandlerType
	passive_effect  = ItemPassiveEffectType
	use_effect		= ItemUseEffectType
	attack_type		= ItemAttackType


//
// Component prototypes
//
Pickupable ComponentPickupBase delete
	effect_pickup	= ItemPickupType.none
	effect_drop		= ItemDropType.none
	weight			= 0

Equippable ComponentEquippableBase delete
	effect_put_on	= ItemPutOnType.none
	effect_take_off	= ItemTakeOffType.none

Damageable ComponentDamageableBase delete
	hitpoints		= 0
	hitpoints_min	= 0
	hitpoints_max	= 0


Entity EntityBase delete
	component_flags = ComponentFlags.none

	damageable		= ComponentDamageableBase
	pickupable		= ComponentPickupBase
	equippable		= ComponentEquippableBase
	
	move_handler    = ItemMoveHandlerType.none		// Velocity, location and orientation are stored into the in-game component storage instead of into EntityBase itself
	control_handler = ItemControlHandlerType.none
	passive_effect  = ItemPassiveEffectType.none
	use_effect		= ItemUseEffectType.none
	attack_type		= ItemAttackType.none
```

## 8. First actions for the new session

1. Read this entire document.
2. Clone `dev` fresh, confirm the state described in section 3 actually matches reality (spot-check a few things: the `--verbose-errors` flag exists on all five exporters, the five docs exist, the column-alignment output looks right). Don't just trust this document, verify it, exactly as this project's own conventions require.
3. Read the tail of `compiler-python/HANDOFF.md` for the most recent real entries, to build additional confidence about exactly where things stand.
4. There are now three pending items: `flags` (section 4, in progress, pick up at 4.4's "next concrete steps"), arrays (section 6, fully designed, not started, waits for `flags` to finish), and the gscript registry request (section 5, not investigated at all yet). Don't assume priority order between the `flags`/arrays sequence and the gscript request, ask the person which they want worked on first.
5. Whichever comes first, keep working in the same style this whole conversation established: real verification before real claims, full regression after every change, no em-dashes, clear and direct communication about what was found and fixed along the way. Confirm with the person early how git operations should actually work in this new local environment before assuming either the old tarball-delivery model or direct local commits.
