# Game Data Definition Language (GDDL)
## Specification v4.0

---

## 1. Purpose

GDDL is a **compile-time, text-based data definition language** for game development.

It lets developers and designers:

- Define strongly typed data structures.
- Create data instances from those structures.
- Build complex data by copying and modifying existing instances.
- Perform compile-time calculations and transformations.
- Export fully resolved data into formats suitable for game engines and runtime systems — including platforms as constrained as the 6502.

GDDL is **not** a runtime scripting language. All copying, modification, calculation, and validation happen during compilation. The exported data contains only finished values. A game's runtime never needs to understand or execute any GDDL language feature.

Supported export targets include (non-exhaustive):
- C++ source (structs, enums)
- 6502 assembly (data tables, jump tables)
- Pure binary data files
- Other user-defined export formats

---

## 2. Core Principles

These principles are the language's constant reference points — every design decision below is a consequence of one or more of these:

1. **Nothing is implicit.** No default values, no silent type conversions, no hidden state. If a value exists, something explicitly set it.
2. **Errors are caught at compile time, not discovered at runtime.** The compiler is responsible for proving the exported data is complete and correct before it ever reaches a game build.
3. **Runtime engines never interpret GDDL.** They consume finished data only.
4. **Logical identity and runtime representation are separate concerns.** What a piece of data *means* is independent of how a specific build chooses to store or index it.
5. **Determinism.** Identical source files and compiler settings must always produce identical output.
6. **Composition over inheritance**, wherever a choice exists between the two.

---

## 3. Source File Structure

A GDDL source file contains three kinds of declarations:

1. **Identifiers** — named, stable, semantic values.
2. **Definitions** (`define`) — type layouts, no data.
3. **Instances** — actual data, built from definitions.

### Indentation

- Scope is defined by indentation, not braces.
- Both spaces and tabs are valid indentation characters.
- **Only one type of indentation character may be used within a single scope.** Mixing tabs and spaces inside one data structure's scope is a compile error.
  - **A "scope" here means one entire top-level `define` or instance block, including everything nested inside it** — not each individual nested field block independently. A nested bare-field block (§6.4) cannot switch to a different indentation character than its enclosing structure, even if the nested block is internally self-consistent. The whole structure, from its header line to its final dedent, must use one indentation character throughout.

### Comments

```
// Single-line comment
/* Block comment, can be nested */
```
Both work as in C++. Block comments may be nested.

---

## 4. Identifiers and Domains

### 4.1 Declaration

```
identifier ActionAttack
    melee_weapon  = "Standard attack done with a melee weapon"
    ranged_weapon = "Standard attack done with a ranged weapon"
```

Each entry has:
- A human-readable name.
- A unique descriptive text, used to generate a permanent **logical ID** via a stable hash of that text.

The logical ID depends only on the descriptive text — never on declaration order, and never on what else exists in the domain. This means:

- Adding new identifiers later never changes existing identifiers' logical IDs.
- Identifiers can be added independently by different parties (see §9, Modding) without central coordination or collision risk.
- The descriptive text is part of an identifier's permanent identity. **Changing the text creates a new identifier.**

#### 4.1.1 Logical ID Algorithm

The logical ID is not "however a given implementation happens to hash it" — it's a precisely specified, cross-implementation contract, since two independently-built compilers (or a compiler and a standalone tool reading its exported data) must compute the exact same logical ID for the exact same identifier text, with zero room for divergence.

- **Algorithm: FNV-1a.** Chosen for being simple and unambiguous to reimplement bit-for-bit identically in any language — a few lines involving one XOR and one multiply per byte, with no cryptographic complexity and no room for two correct implementations to disagree on the result.
- **Width: 64-bit.** Wide enough that collision risk stays effectively zero even across an ecosystem of independently-authored mod/DLC content (§9) with no central coordination — 32-bit was the original width shown in earlier spec examples, but that risk becomes non-negligible once real, uncoordinated third-party content is expected to exist.
- **Input: the domain-qualified text, hashed as UTF-8 bytes, exactly as written.** The hash input is `"DomainName::description text"` — the identifier block's own name, the literal separator `::`, then the description text — **not the description text alone.** This prevents two different domains from coincidentally producing the same logical ID if their description texts ever happen to match (e.g. a reused placeholder string like `"None"` across unrelated domains). A domain name is always a valid identifier token (letters, digits, underscore only) and can therefore never itself contain `::`, so the split between domain name and description text is always unambiguous regardless of what the free-form description text contains. No normalization, no case-folding, no trimming beyond this — any byte-level change to either the domain name or the description text produces a different logical ID.

This same qualified-name-hashing convention (`Qualifier::Name`, FNV-1a-64, UTF-8 bytes) is reused for instance stable IDs (§6.8) — one shared mechanism applied in two places, not two independently-specified schemes that could drift apart from each other.

#### Collision Detection

64-bit FNV-1a makes an accidental collision astronomically unlikely — but "unlikely" is not "guaranteed," and a silent collision here would be worse than almost any other failure mode in the language: two genuinely different identifiers, or a different identifier and an instance, becoming indistinguishable to anything that stores or looks up a reference by ID. This is checked, not assumed.

The compiler maintains **one shared table across the entire compiled project**, covering every identifier logical ID (§4.1.1) and every instance stable ID (§6.8) together — not two separate pools. Both mechanisms produce values in the same 64-bit space for the same fundamental purpose (a permanent, unambiguous reference), so a collision between an identifier and an unrelated instance is exactly as much a failure as a collision between two identifiers, and needs to be caught the same way.

This check requires no new computation — every ID is already computed once during registration (phase 4, §12). As each ID is produced, it's checked against the shared table; if it already exists, that's a **hard compile-time error** naming both colliding qualified names (`Domain::description text` or `Type::InstanceName`) and the shared hash value, so the user can adjust either offending text to disambiguate. This is never a warning — unlike a suspicious-but-legal construct (§6.4's childless bare field), a collision is an actual, empirically broken guarantee, not something a designer might have intended.

This is a foundational, effectively irreversible decision: changing the algorithm, width, or encoding later invalidates every previously-computed logical ID across every existing save file and exported data file — exactly the class of break the logical ID system exists to prevent. It must be treated as fixed, not as an implementation detail any particular compiler is free to vary.

There are no built-in `null`/`none`/`unset` values. If a domain needs an "empty" state, the user defines one explicitly:

```
identifier ActionAttack
    none = "No attack action"
```

### 4.2 Identifier Blocks Are Types (Domains)

**An identifier block declaration simultaneously defines a new type**, usable anywhere a field type is expected in a `define`. The identifier block *is* the domain — there is no separate "domain" concept beyond the block itself.

```
define Creature
    attack = ActionAttack     // strictly typed: only ActionAttack.* values are valid here
```

Identifier-typed fields are **strictly domain-bound** — exactly like `u32` or `string 30` are strict types. There is no generic "any identifier" type. A field typed `ActionAttack` will never accept a value from any other domain. This keeps identifier fields fully compile-time checkable, with no exceptions carved out of the type system.

---

## 5. Data Structure Definitions (`define`)

Definitions describe layout and types only. They never contain data.

```
define Creature
    hitpoints = i32
    attack    = ActionAttack
```

Equivalent to:
```cpp
struct Creature {
    int32_t hitpoints;
    ActionAttack attack;
};
```

### 5.1 Definitions Never Inherit

**A `define` can never inherit from another `define`.** This is a deliberate design choice, not merely a technical limitation, for two reasons:

1. **Readability.** A struct's full field list should always be visible in one place. Inheritance chains force a reader to trace through parent definitions to know what fields exist; a flat, composed struct doesn't.
2. **Composition already covers the need.** A struct-typed field (see §5.2) provides the same practical capability as "is-a" inheritance would, without introducing a second, parallel inheritance mechanism alongside instance copying.

### 5.2 Composition

Definitions may nest other definitions as field types:

```
define Object
    weight = u32
    value  = u32

define Item
    object = Object
```

There is no depth limit; composition can nest arbitrarily.

### Built-in Primitive Types

```
u8, u16, u32, u64      unsigned integers
i8, i16, i32, i64      signed integers
f32, f64               floating point
string N               ASCIIZ string, N bytes total including terminator
```

The exact storage representation of each type is decided by the exporter for its target format.

#### String Literal Escaping

A string literal supports exactly two escape sequences: **`\"`** (a literal double-quote character) and **`\\`** (a literal backslash character). No other escape sequence exists — `\n`, `\t`, and similar are deliberately out of scope, since `string N` is a fixed ASCIIZ buffer, not a place where control characters are expected to make sense, and a data-definition language for game content has no established need for them. This is a minimal, deliberately narrow set, not a placeholder for a larger one.

Both sequences are necessary together, not independently optional: introducing `\` as an escape-sequence prefix at all requires a way to write a literal backslash, or a string that happens to end in one (e.g. a Windows-style path fragment) becomes ambiguous with the sequence that precedes the closing quote. Escape sequences are processed left-to-right as atomic two-character units, so `\\` is always consumed as a single literal backslash before any subsequent character is considered for its own escape meaning.

**Locating a string literal's closing quote requires backslash-run parity, not a single-character lookback.** Given a `"` candidate for the closing quote, count the consecutive `\` characters immediately preceding it. An **even** count (including zero) means every backslash is part of a complete `\\` pair with nothing left dangling, so this `"` is a genuine, unescaped terminator. An **odd** count means the final backslash is unpaired and is actively escaping this `"` — a literal quote character, not a boundary, so scanning continues for a later, real terminator. A naive "is the immediately preceding character a backslash" check gets this backwards for exactly the case `\\` exists to support: a string ending in a literal backslash (`"C:\\Users\\"`, resolving to `C:\Users\`) has two backslashes immediately before its closing quote — an even count, correctly a real terminator — but a single-character lookback sees only the last of those two and misreads it as an escaped quote, incorrectly reporting the string as unterminated. This is not a hypothetical edge case; it is the direct, motivating scenario `\\` was introduced to handle, and any implementation must get the parity right or the feature doesn't actually work for its own stated purpose.

**A lone, unpaired trailing backslash immediately before an apparent closing quote is genuinely ambiguous with a real terminator, and is therefore never reachable as an "invalid escape sequence" error.** By the parity rule above, an odd backslash count before a `"` always means that `"` is escaped — there is no way to distinguish "author meant to end the string here with a stray trailing backslash" from "author is mid-escape-sequence" at that position, so the tokenizer correctly keeps scanning. If no later terminator exists, the result is a **whole-file, phase-3 "unterminated string literal" error**, not a phase-6 escape-validation error — a structurally different failure than an invalid escape sequence appearing mid-string (e.g. `\n`), which the tokenizer parses as a complete literal and phase 6 then rejects for containing an unrecognized escape. Both are rejections of malformed input; they simply occur through different mechanisms depending on where in the literal the bad backslash sits.

**Any other backslash usage is a compile-time error**, not a passthrough — `\` followed by any character other than `"` or `\` (checked once a literal's true boundaries are known, per the above) is rejected outright, for the same reason an out-of-range number or an over-length string is rejected rather than silently accepted in some best-effort interpretation: a plausible-looking value that quietly wasn't what the author meant is exactly the failure mode this language's error-handling philosophy exists to prevent everywhere else.

This is a language-level rule with no dependency on UTF-8 content: a literal non-ASCII character (`é`, for instance) is simply written directly in the UTF-8-encoded source text, with no escape sequence involved — escaping exists solely for the two characters (`"` and `\`) that would otherwise be structurally ambiguous inside a quoted literal.

**Ordering with length enforcement, stated explicitly since it's a real dependency between the two rules below:** string length is measured on the value *after* escape processing, not on the raw source text between the quotes. The source literal `"a\"b"` spans 4 characters between the quotes (`a`, `\`, `"`, `b`) but unescapes to 3 bytes of actual content (`a`, `"`, `b`) — length enforcement measures the latter. Get this ordering backwards and length enforcement would reject or accept based on the wrong count the moment any string actually uses an escape sequence.

#### String Length Enforcement

Storing a string value whose length exceeds what a `string N` field can hold is a **compile-time error** — never silent truncation, for exactly the same reason numeric range enforcement (below) rejects an out-of-bounds number rather than silently wrapping it: a truncated string is a plausible-looking but silently wrong value, not caught anywhere, surfacing only as a confusing bug at runtime.

Length is measured as the **byte length of the UTF-8-encoded text, after escape processing (above)**, not a character count — consistent with the language treating source text as UTF-8 bytes everywhere else (§4.1.1). A `string N` field can hold at most `N - 1` bytes of actual content, since one byte is always reserved for the ASCIIZ terminator (`string N` is defined as "N bytes total including terminator"). Storing a value whose UTF-8 byte length exceeds `N - 1` is rejected at the same point as any other type-safety check on that field (point of storage), not deferred to export time.

#### Numeric Type Coercion

A field's declared type is enforced, not cosmetic. Whenever a value is stored into a field — via assign, op-statement result, or copy — it is coerced to that field's declared type as the final step of storage, regardless of how the value was produced or what numeric form it happened to take along the way.

- **Widening is always automatic.** Storing an integer-valued result into a `f32`/`f64`-typed field always promotes it to a float (`393` → `393.0`), with no error and no dependency on whether any literal or intermediate value in the expression happened to contain a decimal point.
- **Narrowing with loss is a compile-time error.** Storing a value with a nonzero fractional part into an integer-typed field (`i8`...`u64`) is rejected outright — never silently truncated. A float value that is exactly whole (e.g. `4.0` into an `i32` field) may be coerced safely, since no information is lost.

This mirrors the identifier-domain strict-typing rule (§4.2): a declared type is a real, enforced constraint at the point of storage, never a label the compiler happens to agree with by coincidence.

#### Numeric Range Enforcement

Every numeric type has a fixed, defined representable range. Storing a value outside that range into a field of that type is a **compile-time error** — never silently wrapped, clamped, or truncated to fit. Silent wrapping (e.g. `300` into a `u8` becoming `44`) is precisely the failure mode this rule exists to prevent: a plausible-looking wrong number with no error anywhere, surfacing only as a hard-to-diagnose bug in the running game rather than a caught compile error.

```
u8: 0 to 255                    i8:  -128 to 127
u16: 0 to 65535                 i16: -32768 to 32767
u32: 0 to 4294967295            i32: -2147483648 to 2147483647
u64: 0 to 18446744073709551615  i64: -9223372036854775808 to 9223372036854775807
f32, f64: each has a finite representable magnitude; a value whose magnitude
          exceeds it (overflow to infinity) is likewise a compile-time error,
          not a silently-produced inf/NaN.
```

This check happens at the same point as numeric coercion above — at the point of storage, using the fully-evaluated result, after any widening/narrowing decision — and applies uniformly regardless of source: literal, op-statement result, or cross-field expression. **Intermediate computation within an expression is not range-checked at each sub-step** — only the final result is checked when it's actually stored into a field, matching the same "evaluate fully with full precision, then check and store" architecture as coercion, rather than introducing a second, different evaluation model.

---

## 6. Instances

Instances hold actual values, built from a `define`.

```
Creature Human
    hitpoints = 100
    attack    = ActionAttack.melee_weapon
```

### 6.1 Instance Copying

```
Creature Human_Fighter = Human
```

This means:
1. Copy all data from `Human`.
2. Execute the statements inside `Human_Fighter`, in order, against that copy.
3. Produce a new, independent, fully resolved instance.

The original (`Human`) is never modified. This is a compile-time copy-and-modify operation, not runtime inheritance.

**Circular copy references are a compile-time error**, detected at registration (phase 4, §12) — before any instance resolution begins, not as a runtime recursion guard. Since every `= Source` reference (including nested `field = Source`, §6.4 — the same underlying copy-from relationship, just at nested scope) is already known once registration completes, the compiler builds a dependency graph of these references and runs ordinary cycle detection on it. This lets the error name the exact cycle (e.g. `Human_Fighter -> Boss -> Human_Fighter`), rather than a generic "recursion too deep" message that can't identify which references actually form the loop.

### 6.2 Sequential Statement Execution

All statements inside an instance execute strictly top to bottom. Repeated operations on the same field are allowed and simply chain:

```
Creature Human_Fighter = Human
    hitpoints * 2
    hitpoints + 5
    hitpoints / 2 + 60
```

executes as:
```
hitpoints = Human.hitpoints
hitpoints = hitpoints * 2
hitpoints = hitpoints + 5
hitpoints = hitpoints / 2 + 60
```

### 6.3 Field Operations

Every statement inside an instance body must begin with a field name — there is no statement form where a field's target is inferred or implicit. The three legal shapes are: `field = expr` (assign), `field op expr...` (op-statement, see below), and bare `field` (nested modify-only scope entry, §6.4). A line that does not begin with a field name — e.g. `20 + hitpoints_maximum * 0.5` written on its own, with no leading field and no `=` — is a **syntax error at phase 3 (Parse)**, since the parser has no way to determine which field the statement targets. The intended meaning must instead be written as an assign statement with the field explicit: `hitpoints_maximum = 20 + hitpoints_maximum * 0.5`.

There is a single underlying mechanism: **evaluate an expression, then store the result.** Assign and op-statement syntax are two surface forms of that one mechanism, not separate mechanisms:

- **Assign** — `hitpoints = 100` — the expression is evaluated and stored as-is. Any self-reference (e.g. `hitpoints = hitpoints * 2`) must be written out explicitly.
- **Op-statement** — `hitpoints * 2` or `hitpoints / 2 + 60` — syntactic shorthand that implicitly prepends "the field's own current value" to the expression before evaluating. `hitpoints * 2` is exactly equivalent to `hitpoints = hitpoints * 2`.

Expressions may reference **any other field in the current instance's own scope** (see §6.7, Cross-Field Expression References) in addition to literals and the field's own current value. All evaluation is compile-time only — the runtime never evaluates formulas; only the final resolved value is exported.

#### 6.3.1 Operator Precedence

Expressions evaluate **strictly left to right** — there is no operator precedence table (`*`/`/` do *not* implicitly bind tighter than `+`/`-`). This matches the language's broader philosophy of explicit, sequential evaluation with no hidden ordering rules to memorize (§6.2 applies the same principle to statements; this applies it to expressions). Parentheses are supported for explicit grouping, for the cases where a different grouping — including standard mathematical grouping — is actually wanted.

```
hitpoints_maximum * 0.5 + 20        // = (hitpoints_maximum * 0.5) + 20   — left operand first, then left to right
20 + hitpoints_maximum * 0.5        // = (20 + hitpoints_maximum) * 0.5  — NOT standard math grouping; use parens if that's not what's wanted
20 + (hitpoints_maximum * 0.5)      // = 20 + (hitpoints_maximum * 0.5)  — explicit grouping via parentheses
```

For an op-statement, the implicitly-prepended "current value of this field" is treated as the literal leftmost operand of the whole expression, evaluated in the same left-to-right sequence as everything after it — never as its own separately-parenthesized sub-expression grouped against the remainder of the line.

### 6.4 Nested Field Semantics — Replace vs. Modify-Only

This is the core rule governing struct-typed fields, and it is **fully recursive**: the same rule applies at the top level (an instance copying another instance) and at any nested field, at any depth.

**`field = SourceInstance`** — full replace-then-modify:
1. Discard whatever `field` currently holds (if anything).
2. Copy all data from `SourceInstance` into `field`.
3. Execute any following indented statements against that copy, in order.

```
object = Test_Object
    something1 = 1000     // copy Test_Object into object, then override something1
```

**Bare `field` (no `=`)** — modify-only scope:
- Enters `field`'s existing scope (its inherited value, if this instance was itself copied from a parent — otherwise a blank instance of that field's type).
- **Only the sub-fields explicitly listed inside are touched.** Anything not listed keeps whatever value it already had (or stays uninitialized, if it never had one).

```
object
    something2 = 1234      // only something2 is touched; something1 is untouched
```

**A bare `field` with no child statements at all is legal syntax — a no-op.** It enters the field's scope and touches nothing, which is functionally identical to not writing the statement at all. This isn't a violation of "nothing is implicit" (Core Principle 1) — that principle governs implicit *values* (silent defaults, silent conversions), not whether harmless, inert syntax is permitted. A childless bare field is a legitimate way to leave a placeholder while incrementally filling in data, and rejecting it at parse time would be strictly less useful than letting any resulting incompleteness be caught at phase 8 (§12), which reports the precise missing field with full context rather than a generic syntax complaint.

Compiling it does, however, emit a **warning** (§12.1) — not an error — since a childless bare field is unusual enough to plausibly be a forgotten line rather than a deliberate placeholder, and the designer benefits from being told either way. This warning applies specifically to a bare struct-field entry written with zero children; it does **not** apply to an entire instance body being empty (e.g. `Type Name = Source` with no body at all is an ordinary, unsuspicious pure-copy — the bare-field form specifically signals "sub-fields follow," which an empty top-level body never claimed in the first place).

**This fork only becomes observable on struct-typed fields.** For scalar fields there is nothing to "enter" — `hitpoints = 100` is always a plain overwrite, full stop. The replace-vs-modify distinction is a structural property of nesting, not a general-purpose language mechanic.

### 6.5 No Merge Semantics — Deliberate

GDDL has exactly two nested-field modes (replace-then-modify, and modify-only) and **no third "merge" mode** (keep old values, overwrite only what's explicitly named, leave everything else in a mixed old/new state).

This is deliberate. Merge semantics look convenient in small examples but are a common source of hard-to-trace bugs at scale: a field can silently retain a stale inherited value simply because no one remembered to include it, with no error to catch the omission — "kept intentionally" and "forgotten" look identical. Two explicit, unambiguous modes are easier for designers to reason about and easier for the compiler to validate, matching Core Principle 1 (nothing is implicit).

### 6.6 Deleted Instances / Templates

```
Creature BaseCreature delete
    hitpoints = 100
```

A `delete`-marked instance:
- Exists during compilation and can be copied by other instances.
- **May be incomplete** — not every field needs to be initialized.
- Is never exported.

This allows reusable templates without polluting final game data. Only fully-resolved, non-`delete` instances are subject to full initialization validation at export time.

### 6.7 Cross-Field Expression References

Expressions (§6.3) may reference the current value of **any other field within the current instance's own scope**, not only the field being assigned:

```
define Item
    weight = u32
    count  = u32
    total_weight = u32

Item Sword
    weight       = 10
    count        = 5
    total_weight = weight * count      // resolves to 50
```

A field-name reference means "the current value of that field, at this exact point in the instance's sequential execution timeline" — the same rule that already governs self-reference in op-statements, generalized to any field name. Nested fields use the same dot syntax as identifier domain access (`object.weight`); which meaning applies is resolved by type context (current-scope field checked first, then identifier domain).

- **Scope: current instance only**, including nested struct fields via dotted path. Referencing a field on a separate, unrelated instance is out of scope by design — not supported.
- **No separate initialization-order or cycle-detection machinery is needed.** Because execution is strictly sequential and reading an uninitialized field is already always an error (§7), referencing a not-yet-set field simply falls through to that existing error. A reference cycle cannot be constructed under these rules.
- Fields brought in via `= SourceInstance` (§6.4) are already initialized before the instance's own statements run, so referencing them is valid immediately.
- **Self-reference on assign is a special case of this same rule, not a separate mechanism.** `hitpoints_maximum = 20 + hitpoints_maximum * 0.5` reads `hitpoints_maximum`'s value immediately prior to this statement (the assignment hasn't completed yet), and the reference may appear anywhere in the expression — leading, trailing, or in the middle — evaluated left-to-right (§6.3.1) like any other expression. This differs from op-statement shorthand (§6.3), where the field's current value is always the literal leading token by construction, since that's what identifies the statement as targeting that field in the first place.

### 6.8 Instance Stable IDs

Every exported (non-`delete`) instance has a permanent **stable ID**, generated the same way identifier logical IDs are (§4.1.1): FNV-1a-64 over the UTF-8 bytes of a qualified name, using the same `Qualifier::Name` convention.

```
instance_id = FNV1a64("CreatureType::Human_Fighter")
```

The qualifier is the instance's `define` type, not merely its own name — this prevents two different types from coincidentally colliding if they happen to reuse the same instance name (e.g. two unrelated types both having an instance called `Default`). As with identifiers, changing either the type name or the instance name produces a different stable ID; renaming either is equivalent to creating a new logical entity as far as anything that stored a reference to it is concerned.

This exists for the same reason identifier logical IDs exist: any exported artifact that needs to reference *this specific instance* independently of a compile-time C++ symbol — a save file, a level file, a script holding a runtime handle, mod/DLC content — needs a reference that survives across builds, additions, and reorderings, the same way identifier references already do. An instance's stable ID is the mechanism that makes dynamic lookup (§ export specification, instance registries) possible at all: it is what a registry table is keyed by, and it is the value a runtime lookup call (`Find(instance_id)`) takes as input.

---

## 7. Initialization Rules

- Every field that is read or exported must have a value. There are no implicit defaults.
- A field becomes initialized only through: assignment, copying from an initialized source, or compile-time evaluation producing a value.
- Reading an uninitialized field is always a compile-time error — the compiler must never assume zero, empty string, null, or any other default.
- `delete` templates are the sole exception: they may remain incomplete, since they're never exported directly (§6.6).

---

## 8. Save Data and Exported Binary Data

### 8.1 Same Stability Requirement

**Exported binary game data and save-file data have the same lifetime requirement**, and therefore the same rule: both must remain correct if new identifiers are added to a domain between versions — including insertion between existing entries, not just appended at the end. (Example: a developer adds a new `ActionAttack` identifier between two existing ones in a patch; existing save files and any previously-exported binary data referencing that domain must still resolve correctly.)

### 8.2 Default: Logical IDs

By default, **identifier-typed fields are exported as logical IDs** (the stable hash described in §4.1), both in save files and in exported binary data.

This is safe under insertion because logical IDs never depend on position or on what else exists in the domain — inserting a new identifier anywhere never changes any existing identifier's logical ID.

```
attack = 0xA82F91C4    // logical ID, stable across builds
```

### 8.3 Explicit Opt-In: Direct Indexing

For data that is always compiled and shipped as a single unit together with its own registry — e.g., data baked directly into a ROM or game binary, where the data and the registry it depends on can never go out of sync — or for hot-path dispatch code that benefits from a small, dense value instead of a sparse 64-bit hash — a domain may opt into having an **indexed form** available, and individual fields may choose to use it.

**Width is committed once, at the domain's own declaration — never per field, and never repeated.**

```
identifier ActionAttack u8
    melee_weapon  = "Standard attack done with a melee weapon"
    ranged_weapon = "Standard attack done with a ranged weapon"
```

A trailing width token (`u8`/`u16`/`u32`/`u64`) right after the domain name declares that domain's indexed form and commits to a width for the whole project. Omitting it (the default, and every domain's behavior prior to this rule) means the domain has no indexed form available at all.

This width is domain-wide by necessity, not by convenience: any identifier-typed field can be assigned *any* member of its domain, so the minimum valid width is a direct function of the domain's own member count — not anything about which field or `define` happens to reference it. There is no legitimate scenario where two different fields want different widths for the same domain; one would simply be wrong (too narrow for the domain's actual size) or wasteful (wider than necessary for no benefit). Putting the commitment at the domain's declaration, once, is what actually matches the constraint.

**A field opts into the indexed form with an `@` prefix on the domain type:**

```
define Creature
    attack        = ActionAttack     // default: logical ID, save-safe
    fast_dispatch = @ActionAttack    // opts into ActionAttack's already-declared indexed width
```

Assignment syntax is unaffected either way (`fast_dispatch = ActionAttack.melee_weapon` works identically regardless of the field's declared type) — representation is purely an export-time concern; a resolved field is always just "member X of domain Y" through phases 1–8, with mode only mattering once export happens.

**Two errors, both checked statically at registration (phase 4/5), not deferred to resolution or export:**

1. **`@Domain` used somewhere, but `Domain` declared no width.** Error names the domain and the field that tried to use it.
2. **A domain declares a width, and its member count exceeds what that width can address** (e.g. more than 256 entries for `u8`) — checked the moment the domain is registered, **regardless of whether anything actually uses `@` on it yet.** Declaring a width is a deliberate commitment (§8.3's original "the user is responsible for picking the width" principle); letting that commitment silently go stale until something eventually references it would be exactly the kind of latent, late-discovered bug this project is designed to avoid.

**`@` is only legal prefixing an identifier-domain type.** Using it on a numeric or `string N` field is a compile error — those types have no alternate representation to opt into.

**The default is always logical ID.** A field's type with no `@` prefix always means logical ID, regardless of whether its domain happens to have declared a width — using the indexed form is always an explicit per-field choice, never inferred.

**Export-side: the companion enum is only emitted if actually used** — if nothing in the compiled data uses `@Domain` for a given domain, no companion enum appears in the output, even if that domain declared a width. See §8.5 and §14.7 for the planned exception to this (force-emitting an indexed enum with nothing referencing it in the data itself, for hand-written dispatch code).

### 8.4 Ordering Differs by Mode

The two modes use different, deliberately distinct orderings, because position means something different in each:

- **Logical ID mode**: the compiler's generated table is ordered **canonically by hash**. Position carries no meaning — the value itself *is* the identity — so insertion anywhere in the domain is always safe and never disturbs other entries.
- **Indexed mode**: the compiler orders entries by **declaration order** in the source file. Here, position *is* the identity — index 0 always means the first-declared entry — so a human can read the source top-to-bottom and know exactly which index each identifier will get, without needing to run the compiler first. This is required for 6502 (or any platform) code that hand-codes a jump table matching the GDDL source.
  - **Appending** a new identifier at the end of an indexed domain is always safe.
  - **Inserting** a new identifier in the middle shifts the index of every entry declared after it. This is expected: an indexed domain's GDDL source and any hand-written code depending on its indices (e.g. 6502 jump tables) must always be rebuilt and kept in lockstep together.

### 8.5 Force-Emitting an Unreferenced Domain (Cross-Target)

**Every export target currently suppresses a domain's output entirely if nothing in the compiled data references it**, even if that domain declared a width. Confirmed directly, not assumed, across all three non-C++ targets: `gather_domains_used()` collects only domains actually referenced by some field after composition flattening, and each of `export_6502.py`, `export_z80.py`, and `export_68000.py` has a `continue`-on-not-in-`used` line in its own `gather_domain_info()` that's structurally identical across all three (confirmed by direct fixture test: a width-declared, zero-reference domain produces `domains gathered: []` and nothing about it appears in any of the three targets' output).

This is a real gap, worth closing with the same underlying justification as C++'s planned §14.7 mechanism: hand-written low-level code (an assembly dispatch table, a 68000 C jump table) may want a domain's compact constants available without GDDL ever storing a value from that domain in any compiled struct. **But it is not the same mechanism as §14.7**, and describing it that way would be wrong:

- **On C++**, a referenced domain already always gets its default logical-ID enum; only the `@`-gated `_Indexed` companion is missing when unused. The gap is about a *second form* of an *already-emitted* domain.
- **On 6502, Z80, and 68000**, `Domain` and `@Domain` are indistinguishable — there is only ever one representation, always the compact/indexed form. The gap here is about the *entire domain* being absent, not a missing companion of something already present.

**The fix, applied identically in shape across all four targets, one shared boolean, no per-domain selection list** (matching §14.7's existing precedent that this is a blanket convenience switch, not a fine-grained one): when on, every domain that declared a width gets its target-appropriate compact representation emitted — the `_Indexed` companion enum on C++, the existing constant-table form each of 6502/Z80/68000 already produces for referenced domains — regardless of whether anything in the compiled data references it. When off (the default), current per-target "only emit if used" behavior is unchanged. A domain with no declared width is unaffected either way, on every target, since there's nothing for it to force-emit.

---

## 9. Modding and DLC Support

Support for adding content without recompiling the base game is a **PC-only capability**. It relies on runtime-dynamic dispatch, which 6502-class platforms do not have.

### 9.1 PC (dynamic dispatch)

Because logical IDs are self-contained hashes of description text, a mod or DLC package can declare entirely new identifiers independently of the base game, with negligible collision risk, and without needing any central registry or recompilation of the base game.

At load time, the mod's declared identifiers register into the runtime's dispatch structure:

```
unordered_map<logical_id, function_ptr*> AttackMap;
```

Old base-game data and save files never need to know a mod exists. A modded identifier is simply another logical ID the dispatch map didn't contain until the mod registered it.

### 9.2 6502 (static only)

6502 has no equivalent capability, and none is designed for it. Its dispatch structures (jump tables) are generated entirely at compile time and are fixed once built. **All 6502 content — base game and any DLC — must be compiled together into a single build.** Adding content on 6502 always means a full rebuild, which is simply the ordinary version-update path (§8), not a modding path.

---

## 10. 6502 Export

### 10.1 No 64-Bit IDs on 6502 — Neither Identifiers Nor Instances

The entire reason logical IDs (§4.1.1) and instance stable IDs (§6.8) exist is surviving insertion of new content across separately-compiled builds — a patched build must still resolve old save files or externally-persisted binary data correctly. But 6502 (§9) is fully static: no mod/DLC, every rebuild is a full rebuild of all content together, and physical 6502 media (cartridge, tape, disk) is never live-patched after release the way networked software is. **The problem both mechanisms solve simply never arises on this target — for identifiers and instances alike, not identifiers alone.**

**Every identifier-typed field is always exported to 6502 using its domain's indexed form (§8.3).** `@Domain` and plain `Domain` become indistinguishable once targeting 6502 — logical-ID (64-bit hash) representation is never offered on this target, regardless of what the field's declared type says in source.

**Every instance reference on 6502 is likewise a dense, declaration-ordered index — never a 64-bit stable ID.** A registry's lookup key on this target is a small index, not a hash, for the identical reason identifiers use one. This keeps the "source carries zero target-specific hints" principle intact, the same as AoS/SoA (§13.6): the identical source exports 64-bit stable IDs for C++'s registry and compact indices for 6502's, without the source needing to know or care which.

**This cascades into a further simplification, not just a smaller key.** Once instance references are dense, sequential indices, "registry lookup" no longer means searching at all — it means direct O(1) indexed access. A 6502 registry is two parallel arrays (instance address low bytes, high bytes), each indexed directly by the stored index, the same split-array-to-avoid-a-multiply pattern already established for jump tables (§10.2). There is no binary search on this target's registries; binary search was only ever needed to search by an arbitrary 64-bit value, and a small dense index doesn't need searching, only indexing.

**Every identifier domain referenced by anything being exported to 6502 must have a declared width.** A domain with no declared width is completely valid for other targets (C++'s logical-ID mode needs none) — but exporting that domain to 6502 specifically is a 6502-export-time error, naming the domain and requiring a width be added before export can proceed.

### 10.2 Runtime Dispatch

Since the stored index is always correct for the exact build that compiled it — there is no cross-build compatibility concern on this target, per §10.1 — dispatch never needs any resolution step at load time. The stored index is used directly, every time, with zero processing cost.

**The dispatch code must be plain NMOS 6502-compatible — no 65C02-only addressing modes.** An earlier version of this section used `JMP (Table,X)` (indexed-indirect jump), which is a **65C02-only** addressing mode; the base 6502/6510 (the actual CPU in a real Commodore 64) never had it. This was caught by actually assembling and executing the generated code against a real 6502 emulator, not by reviewing the assembly text alone — worth remembering as a reason to always validate 6502 output against a real toolchain, the same standard already applied to the C++ exporter.

The correct, NMOS-compatible form splits the jump table into two parallel byte arrays (low bytes, high bytes of each handler address) — the same "split into parallel single-purpose arrays to avoid needing to multiply an index" principle already established for SoA (§13), just applied to a jump table instead of instance data. Each array is indexed directly by the stored index (no doubling needed, unlike the indexed-indirect form), combined into a zero-page pointer, then dispatched with a plain, non-indexed `JMP` — every instruction here (`LDA abs,X`, `STA zp`, `JMP (zp)`) is original, base-6502-legal:

```asm
LDA Creature.attack_index
TAX
LDA ActionAttack_JumpTableLo,X
STA JumpPtr+0
LDA ActionAttack_JumpTableHi,X
STA JumpPtr+1
JMP (JumpPtr)
```

**`Dispatch` is generated output, one per identifier domain that has a jump table** — not hand-written boilerplate a developer reproduces per project. Since every identifier field on 6502 is always indexed (§10.1), a jump table is already emitted unconditionally for every referenced domain; `Dispatch` is emitted alongside it, unconditionally, for the same domain. This mirrors the precedent already set by `{Type}_Registry_Find` (§10.1) being generated code rather than something left to the developer to hand-write — and it matters beyond mere convenience: hand-copying this exact pattern risks silently reintroducing the 65C02-only bug found and fixed above, once per project, with nothing to catch it. The realistic use case for indexed dispatch is a generic per-frame loop processing many instances uniformly, where the actual domain member isn't known until runtime — exactly the kind of code that also plausibly does other zero-page-using work nearby (including, plausibly, a nested registry lookup or another dispatch), which is why zero-page allocation (below) never shares scratch space between consumers by default.

**Zero-page addressing: a single required export-time parameter, `--zp-base`, with no default.** Zero-page is small and heavily contested on real C64 projects (KERNAL/BASIC routines banked in or out, existing hand-managed reservations) — the exporter must never silently assume an address is safe, so this parameter has no fallback; 6502 export refuses to proceed without it being explicitly supplied. From that base, the exporter deterministically assigns non-overlapping 2-byte blocks, one per consumer, in two clearly separated groups: first one block per exported type with a registry (AoS only — SoA needs none at all, §13.4), in declaration order; then one block per identifier domain with a jump table, in declaration order. This ordering is simple to predict and document, and non-overlapping allocation by default is what makes nested/reentrant usage (a dispatched handler that itself triggers a registry lookup or another dispatch) safe rather than merely assumed safe.

### 10.3 Multiple Assembler Dialects

GDDL's 6502 export is not tied to one assembler; there is no single dominant "6502 assembly" the way there's a de facto C++ standard. The design splits into two layers:

- **A shared, assembler-agnostic resolution step** — computing exactly what needs to be emitted (flattened SoA arrays if requested, per-domain index/jump tables, registry/lookup tables) — identical regardless of which assembler will render it. This mirrors how the C++ exporter already separates flattening logic from its output-rendering functions (§14).
- **A per-dialect renderer**, translating that shared representation into the actual assembly text for one specific assembler's syntax.

Dialects are added one at a time, each as an independent renderer against the same shared data — never a rewrite of prior work. The three target dialects, based on which are actively used in the current Commodore 64 development community: **ACME** (first), **KickAssembler** (second), and **64tass** — each gets its own renderer, all consuming the same shared, assembler-agnostic representation.

**Selection is a single export-time flag, `--dialect=acme|kickassembler|64tass`**, defaulting to `acme` — mirroring exactly how `--layout` (§13.6) and `--force-single-header` (§14.3) already work: an explicit, per-run choice, never inferred, never mixed within one run. This flag composes freely with the others (e.g. `--dialect=kickassembler --layout=soa` is a valid, meaningful combination) — dialect choice and layout choice are fully independent axes.

### 10.4 AoS/SoA Applies Identically, No Target-Based Default

The AoS/SoA layout choice (§13) works exactly the same way on 6502 as on any other target: a single explicit compile-time flag, never a target-based default. **No export target — 6502 included — ever silently prefers one layout over the other.** A developer targeting 6502 must specify AoS or SoA explicitly, exactly as a developer targeting C++ must — the target itself carries no implicit bias, even though SoA's motivating rationale (§13) happens to matter most on 6502 specifically, since that's the platform lacking a hardware multiply instruction in the first place.

---

## 11. PC Runtime Model

```cpp
unordered_map<uint32_t, void(*)()> AttackMap;   // logical ID -> function pointer
```

Supports dynamic dispatch directly from logical IDs, which is what makes runtime mod registration (§9.1) possible without any index-resolution step at all.

---

## 12. Compiler Pipeline

1. **Read** source files.
2. **Preprocess** — remove comments (block comments may be nested), remove empty lines.
3. **Parse** — build an AST, preserving declaration order, statement order, and indentation structure. Enforce single-indentation-character-per-scope.
4. **Register** — identifiers (and their domains/types), definitions, instance declarations.
5. **Validate** — types exist, fields exist, identifier references resolve to a valid domain member, structure nesting is valid.
6. **Resolve instances** — for every instance: copy source instance if one exists, execute all statements in order (§6.2–6.4), resolve nested structures recursively.
   - **Error policy: collect-and-report, not halt-on-first.** A direct failure inside an instance's own body is recorded once, against that instance. Any instance that transitively copies from a failed instance is marked as blocked, pointing back to the original failing instance — it does not re-derive or duplicate field-level errors of its own. One compile pass surfaces every independent root-cause problem, rather than stopping at the first or burying the root cause under a cascade of derived errors.
7. **Evaluate expressions** — all calculations performed at compile time; only resolved values remain.
8. **Final validation** — every field required for export must be initialized (§7); no invalid references; no unresolved expressions remain. `delete` instances are exempt from being exported but their descendants must still fully resolve.
   - **Each non-`delete` instance is checked independently here — failures do not cascade or block the way phase 6 failures do.** By phase 8, every instance under consideration already has a fully, successfully resolved tree (phase 6 succeeded for it) — phase 8 checks a property of that finished tree (is it complete enough to export), not the resolution process itself. If two instances in a copy chain both end up missing the same field because neither ever set it, each gets its own distinct error; neither is marked "blocked by" the other, since both fully resolved and each stands as its own independently complete-or-incomplete artifact.
9. **Export** — emit the fully resolved data in the requested target format(s), per the identifier-encoding mode (logical ID or direct index, §8) specified for each `define`.

The compiler must produce identical output for identical source files and settings (Core Principle 5).

### 12.1 Warnings

Distinct from errors, **warnings are non-blocking diagnostics**: reported to the designer, but never halt any phase, never block resolution or validation, and never prevent export. A warning means "this compiled successfully and is legal, but is worth a second look" — as opposed to an error, which means the source is invalid and cannot proceed as written.

Each warning carries the same phase/location attribution as an error (which phase detected it, line number, a clear message) so tooling can surface it the same way, but it is reported under a separate category and does not affect compile success.

Currently defined warnings:
- **Childless bare field** (§6.4) — a bare struct-field entry (`field`, no `=`) with zero child statements. Detected at phase 3 (Parse), since it's a purely syntactic property requiring no type or resolution information. Legal, compiles clean, but flagged since it's more often a forgotten line than a deliberate placeholder.

---

## 13. Data Layout: Array-of-Structs vs. Struct-of-Arrays (Cross-Target)

GDDL's language model (defines composed of fields, instances filling them) naturally produces one canonical resolved representation per instance — semantically, "one instance = one complete record." **Array-of-Structs (AoS)** is the direct, natural export of that representation: one contiguous block per instance, instances laid out consecutively. This is what every export target does by default, and what every exporter built so far (C++) has produced.

**Struct-of-Arrays (SoA)** is a pure re-shaping of the exact same resolved data, generated automatically at export time — never a separate authoring format, never anything the GDDL source itself needs to express twice. Instead of one array of instance-blocks, every leaf field gets its own independent, tightly-packed array, with the same index across every field's array referring to the same instance.

This is a **cross-target concept, opt-in per exported type** — not a 6502-specific mechanism, even though 6502 and modern targets benefit from it for different underlying reasons:

- **6502**: avoids the 6502's lack of a hardware multiply instruction. AoS indexing requires `base + i * struct_size`, an arbitrary (usually non-power-of-two) multiply — genuinely expensive on this hardware. SoA indexing into a single field's array is `base + i` for byte-width fields (free, direct indexed addressing) or a cheap power-of-two shift for wider fields (`i << 1` for `u16`, etc.) — never an arbitrary multiply. This is not a claim that SoA is free for every field width, only that it turns an arbitrary multiply into nothing (for `u8`, the most common 6502 field width) or something far cheaper (a shift, for wider power-of-two-width fields).
- **C++/modern targets**: SoA is valuable for cache locality and SIMD-friendliness in hot loops that only touch one or two fields across many instances (a common data-oriented-design pattern) — a different motivation from 6502's, but the same underlying transformation.

### 13.1 Full Flattening Through Composition

SoA flattens **every leaf field, all the way down through nested composition** — not just top-level fields. A nested struct-typed field left grouped in SoA would reintroduce exactly the problem SoA exists to solve for that portion, since a nested sub-struct still has its own arbitrary, usually non-power-of-two size. Concretely, `Item.object.something1` and `Item.object.something2` (§5.2 composition) each become their own independent top-level array in SoA mode, not a single array of `Object` structs.

### 13.2 String Fields

A `string N` field becomes one flat byte array of size `N * instance_count`, with each instance's string occupying a fixed `N`-byte slice (`base + i * N`). This is only genuinely multiply-free if `N` is itself a power of two — worth choosing string sizes like 16 or 32 for this reason where SoA access matters, though not a requirement.

**On any assembler-based export target** (6502, Z80 — as opposed to a C-family target, where a plain `char name[N] = "text";` is already both compact and human-readable, with implicit zero-padding to the array width free from C89 itself), **string content is emitted as a quoted, human-readable string literal followed by exactly enough explicit zero bytes to reach `N` total** — one of those bytes covering the mandatory ASCIIZ terminator, the rest padding — e.g. `db "Grubnik", 0, 0` for a `string 9` field holding a 7-byte value. **Never** a byte-by-byte numeric list (`db $47, $72, $75, $62, $6E, $69, $6B, 0, 0`) for the readable content itself — that defeats the entire point of a human ever reading generated output to sanity-check it. Confirmed this assembles to the exact expected bytes on a real assembler (`z88dk-z80asm`); each additional dialect (ACME, KickAssembler, 64tass, SjASMPlus, `z88dk`-asm) should confirm the same `db "text", 0, ...` construction is accepted identically before assuming it, given this project's repeated experience of these dialects disagreeing on small syntax points that look universal at a glance.

As of this writing, **no assembler-based export target has string field support implemented yet** — this is a forward-looking rule for whoever implements it on 6502 or Z80, not a correction to anything already shipped. `export_6502.py` and, before this rule, the Z80 renderers both explicitly scope string fields out with a comment to that effect; there is no existing wrong format to retrofit.

### 13.3 Identifier-Typed Fields

An identifier-typed field using the `@Domain` indexed form (§8.3) is a natural, synergistic fit for SoA — its width is small (commonly `u8`) and user-chosen specifically for compact storage, exactly the case where SoA indexing is genuinely free. A logical-ID-mode field (the default, 64-bit) can still be flattened into its own array in SoA mode, but loses the "free indexing" benefit that motivates SoA in the first place, the same way any other 8-byte field would.

### 13.4 Dynamic Lookup

SoA mode still needs an equivalent to the AoS registry (§14.2 for the C++ case) — a parallel lookup table (stable ID or name → row index) for dynamic access, generated alongside the field arrays. **On any target using the dense-index identity system (6502, §10.1; 68000, §15.4), there is no separate lookup step at all.** Instance identity on these targets is already a dense, declaration-order index — the same index used to access an AoS instance's registry entry directly indexes into every SoA field array too, with zero resolution needed. SoA's field arrays and AoS's registry share the exact same index space; nothing needs to be looked up, only read.

### 13.5 AoS and SoA Are Not Mutually Exclusive

A developer may request AoS, SoA, or both for the same underlying source data — opt-in, with no cost forced onto anyone who doesn't choose it. Both projections are generated from the exact same resolved instance data; there is no duplicate authoring and no risk of the two views disagreeing with each other. This mirrors the reasoning already established for direct vs. dynamic access in C++ (§14.5): forcing a single mode to serve every use case makes the common case worse in service of the rare one, when both are legitimate, real needs. The only real cost of requesting both is doubled storage in the compiled output for whatever data is exported both ways — a cost only paid when a developer deliberately opts into it, never a default.

### 13.6 How the Choice Is Made

The layout choice is a **single compile-time flag applying to the whole compile/export run** — not per-type granularity built into the compiler, and **not source-level syntax in the `.gddl` file at all.** A `.gddl` source file contains zero indication of layout, anywhere, ever — no annotation, no keyword, nothing a `define` or instance could opt into or out of. The exact same, completely unmodified source compiles to AoS or to SoA depending solely on which flag is passed to the compiler that run; the source itself has no opinion and no awareness that the distinction exists. Within any single invocation, every exported type gets the same layout, whichever the flag specifies — there is no mixing AoS and SoA types within one run. This follows the same precedent already established in §8.3 ("a compile-time flag may also set the mode for an entire export run").

This is a deliberate choice, not an oversight: AoS vs. SoA has no bearing on whether a `.gddl` source is valid — it doesn't affect any value, any error-checking, or any part of resolution (phases 1–8). It only matters at the final export step, once fully-resolved data is being turned into a file. Keeping it out of the source entirely also means the same `.gddl` source can be exported differently for different targets (e.g. a PC build wanting plain AoS, a 6502 build of the identical creature data wanting SoA) without editing anything or inventing per-platform conditional syntax.

**"Both simultaneously" (§13.5) is achieved by running the compiler twice — once per flag value — not by one invocation producing two outputs at once.** The natural, sensible workflow this leads to (though not compiler-enforced): a developer organizes `.gddl` source files so that types intended for one layout live together, and types intended for the other live together, then feeds each group to its own run with the matching flag.

Composition is unaffected by files being split this way: SoA's full-flattening rule (§13.1) already breaks a nested composed field down into its own leaf arrays as part of flattening its containing type — regardless of whether the nested type is *also*, separately, exported standalone as AoS in a different run. The two projections don't need to agree or coordinate; they're independent. And since instance/identifier stable IDs are always deterministic (§4.1.1, §6.8 — the same qualified name always hashes the same value), an AoS run and an SoA run of the same source will always agree on identity for the same instance, even though they're two separate compiler executions (Core Principle 5).

---

## 14. C++ Export Specification

This section captures the design decisions made for the C++ export target — target: **C++17**, chosen for `inline constexpr`'s cross-translation-unit safety while remaining a widely-supported baseline. Fully built and validated: type mapping, per-type registry, instance stable IDs, indexed mode, AoS/SoA, header/`.cpp` split with `--force-single-header` fallback, all validated via real `g++17` compile+link+run.

### 14.0 Generated Code Style

**Brace placement.** Every block-opening brace goes on its own line, with one exception: **only the very first `if` in a chain gets its opening brace on its own new line. Every subsequent `else if (...)` or `else` cuddles everything onto one line** — the preceding block's closing brace, the `else`/`else if` keyword, the condition if there is one, and the new opening brace, all together:

```cpp
if (something)
{
    // ...
} else if (something_else) {
    // ...
} else {
    // ...
}
```

A plain `if` with no `else` at all still gets its opening brace on its own line, same as any other block. Every other block construct — `while`, `for`, functions, `struct`, `namespace`, `enum class` — also keeps its opening brace on its own line, unaffected by this rule.

**Aggregate initializers are not block constructs.** A single-line initializer (`{ 100, 50 }`, a one-row `Entry{ ... }`) stays compact, brace cuddled onto the declaration. A multi-line initializer (e.g. a table with one entry per line) follows the same own-line-brace rule as any other block, since visually and structurally it behaves like one.

**Blank line after every closing brace that ends its own line** — with one exception: **if the very next line is also a closing brace, no blank line is inserted between them.** Braces that are cuddled onto a continuing line (`} else {`) have nothing to add a blank line after, since nothing follows them on their own line.

**Blank line after a group of variable declarations**, separating them from the logic that follows — but not after a loop variable declared inline as part of a `for (...)` statement itself, since that's one construct with its body, not a separate declaration to set apart from what follows.

This governs only the C++ output the exporter writes; it has no bearing on the Python reference compiler's own source style.

**Full worked reference** (every rule above applied together):

```cpp
#ifndef GDDL_GENERATED_H
#define GDDL_GENERATED_H

// Auto-generated by the GDDL compiler. Do not edit by hand.

#include <cstdint>
#include <array>
#include <string_view>

namespace GDDL
{

enum class ActionAttack : uint64_t
{
    melee_weapon = 0x5c96a731d7d47e03ULL,
    ranged_weapon = 0xaa92e2b5323e5154ULL,
};

struct Object
{
    uint32_t something1;
    uint32_t something2;
};

namespace Object_Instances
{
    inline constexpr Object DefaultObject = { 0, 0 };
    inline constexpr Object HeavyObject = { 100, 50 };
    inline constexpr Object LightObject = { 5, 50 };
}

namespace Object_Registry
{
    struct Entry
    {
        uint64_t instance_id;
        std::string_view name;
        const Object* data;
    };

    inline constexpr std::array<Entry, 3> Table =
    {
        Entry{ 0x4e4417bdfce7a91aULL, "HeavyObject", &Object_Instances::HeavyObject },
        Entry{ 0xad84053e592e7248ULL, "DefaultObject", &Object_Instances::DefaultObject },
        Entry{ 0xea3fb911673e5dc9ULL, "LightObject", &Object_Instances::LightObject },
    };

    constexpr const Object* Find(uint64_t instance_id)
    {
        std::size_t lo = 0, hi = Table.size();

        while (lo < hi)
        {
            std::size_t mid = lo + (hi - lo) / 2;

            if (Table[mid].instance_id < instance_id)
            {
                lo = mid + 1;
            } else {
                hi = mid;
            }
        }

        if (lo < Table.size() && Table[lo].instance_id == instance_id)
        {
            return Table[lo].data;
        }

        return nullptr;
    }

    constexpr const Object* Find(std::string_view name)
    {
        for (const auto& entry : Table)
        {
            if (entry.name == name)
            {
                return entry.data;
            }
        }

        return nullptr;
    }
} // namespace Object_Registry
} // namespace GDDL

#endif // GDDL_GENERATED_H
```

### 14.1 Type Mapping

- `u8`...`i64` → `<cstdint>` fixed-width types (`uint8_t`...`int64_t`).
- `f32`/`f64` → `float`/`double`.
- `string N` → fixed-size `char[N]`, never `std::string` — keeps generated structs POD/trivially-copyable, which matters for bulk operations, memory-mapping, and cache-friendly layout on data that's meant to be compile-time constant.
- Identifier domains → `enum class Domain : uint64_t { member = 0x...logical_id... }` — `uint64_t` specifically, matching the logical ID width (§4.1.1).
- `define` composition → nested C++ structs, one-to-one, same field order as declared.
- Instances → `inline constexpr` struct values, aggregate-initialized. `inline` (not bare `constexpr`) is required, not stylistic: a bare `constexpr` at namespace scope has internal linkage, meaning each translation unit that includes the header would get its own independent copy at its own address — breaking pointer identity between the registry (§14.2) and any direct reference the moment the header is included from more than one `.cpp` file, which is the ordinary case for any real project.

### 14.2 Per-Type Registry

Every exported type gets an auto-generated registry — this is **structurally required, not optional infrastructure**, for a reason specific to C++'s optimizer: a `constexpr` value that nothing ever takes the address of, and that the compiler can fully resolve at every use site, doesn't need to occupy any real memory location at all. An instance only ever meant to be found dynamically (e.g. by a game script, by name/ID, never referenced directly in C++ source) could be optimized away entirely — silently absent from the compiled binary — unless something forces it to exist. Taking the address of an object is what forces the compiler to give it one; the registry, by storing a pointer to every exported instance of a type, is what guarantees every instance is retained regardless of whether direct C++ code ever references it by name.

```cpp
namespace CreatureType_Registry {
    struct Entry {
        uint64_t instance_id;       // see §14.4
        std::string_view name;      // for tooling/debugging, not hot-path lookup
        const CreatureType* data;   // MUST point at the same object CreatureType_Instances:: exposes -- never a copy
    };
    inline constexpr std::array<Entry, N> Table = { /* sorted by instance_id at export time */ };

    constexpr const CreatureType* Find(uint64_t instance_id);   // hand-written binary search --
        // std::lower_bound etc. aren't guaranteed constexpr until C++20, so under a C++17 target
        // this can't lean on <algorithm>
    constexpr const CreatureType* Find(std::string_view name);  // linear scan, tooling/debug use
}
```

- **One registry per type, strongly typed** (`const CreatureType*`), not one type-erased global table across all types. A cross-type registry would need `void*` plus a runtime type tag, discarding the compile-time type safety this whole design protects. "Iterate literally everything regardless of type" is a distinct, deliberately out-of-scope feature for now.
- **`std::array`, specifically** — free range-based iteration on the C++ side, and `.data()`/`.size()` give a plain contiguous pointer+count pair that's trivial to expose across a boundary into something that doesn't understand C++ templates at all (e.g. an embedded scripting VM, §14.5).
- **Table sorted by `instance_id` at export time** — free, since the compiler already knows every instance and its ID at export time; enables `constexpr` binary search with zero runtime cost.

### 14.3 Header/`.cpp` Split

**Default: split into `.h` + `.cpp`.** A single monolithic header holding every instance's data, plus every registry table, is the least readable option once a project has any real amount of content — most of a generated header's length is data, not structure. The default instead separates by what C++ actually requires to stay visible everywhere versus what's only ever needed in one place:

**Always in the header, in both modes — not a choice, a structural requirement of C++ itself:**
- **Enum definitions** (a domain's logical-ID and, if used, `_Indexed` companion enum, §14.7). An `enum class`'s enumerators *are* its definition — there is no C++ mechanism to declare an enum in one place and define its values elsewhere, unlike a variable or function. This also happens to cost nothing: a domain is a handful of named integers, never the bulk of a real project's data, and keeping it universally compile-time-usable (in a `switch`, a template parameter, a `static_assert`) is exactly what a developer would want from it anyway.
- **`struct`/type definitions** (per §14.1, and correctly *not* emitted at all when using the SoA layout, §13) — any code touching the type needs to see its layout.
- **`extern` declarations** for every instance and every registry's `Table`, plus **function declarations** (signatures only) for `Find()`.

**In the generated `.cpp`, by default:**
- The actual `const` definitions of every instance (whichever GDDL source produced them — individual AoS instances, or SoA's flat per-field arrays).
- The actual contents of every registry's `Table`.
- `Find()`'s bodies — an ordinary runtime function now, not `constexpr`, since its body no longer needs to be visible at every call site.

An externally-linked `const` global with a compile-time-constant initializer is placed in the binary's read-only data exactly the same way regardless of which file defines it — the retention and binary-embedding guarantees are unaffected by this split. Retention is in fact simpler under split mode: an ordinary global with external linkage always has a real, concrete storage location (the compiler must assume some other translation unit may reference it), so there's no need for the "must take its address to force retention" reasoning that motivates `inline constexpr` in single-header mode — it's just how externally-linked globals have always worked.

**The real cost, precisely stated: split mode gives up compile-time (`constexpr`) evaluability of instance data outside the one `.cpp` file that defines it.** Nothing outside that file can use a specific monster's `hitpoints`, for example, in a `static_assert` or a non-type template parameter — only through an ordinary runtime read. Enum values are unaffected by this and remain compile-time-usable everywhere, in both modes, unconditionally.

**`--force-single-header` reverts to the original single-header behavior**: everything — types, data, registries, `Find()` bodies — inline in one `.h`, `inline constexpr` throughout, exactly as built and validated prior to this rule. This is the mode every exporter test built so far has used; it remains fully correct and available, just no longer the default.

### 14.4 Instance Stable IDs

See §6.8 — every exported instance gets a permanent stable ID via the same qualified-name FNV-1a-64 mechanism as identifiers (`"TypeName::InstanceName"`), which is what the registry is keyed by and what a dynamic lookup call takes as input.

### 14.5 Access Patterns

Two genuinely different access patterns are both real needs, not a redundant either/or:

- **Direct access** — C++ code references a specific, compile-time-known instance by its actual name (`GDDL::CreatureType_Instances::Human_Fighter.hitpoints`). Zero indirection, full compile-time type checking, zero runtime cost. The right choice whenever the specific content is known at the time the code is written.
- **Dynamic access** — the specific instance is only known at runtime, from an external source (a save file, a level file, a script). Resolved via the registry's `Find()`, by stable ID or by name.

Both operate over the exact same underlying data — never two parallel representations. This is a deliberate hybrid, not an unresolved tension: forcing either pattern to serve both needs would make the common case worse in service of the rare one (or vice versa).

**Filtering/querying is plain iteration + ordinary predicate code, not a generic runtime reflection/query engine.** "Find all creatures that are benevolent, then tiny, then pick one at random" is fully expressible as ordinary chained operations over `CreatureType_Registry::Table` (or an equivalent iteration primitive), using regular typed field access — no query language, no field-introspection-by-string-name system. This matches GDDL's broader ethos (explicit, strongly typed, no implicit behavior) better than a generic reflection layer would, and avoids building and maintaining a meaningfully larger, more fragile piece of infrastructure than the actual need requires.

### 14.6 Scripting Language Bindings — Out of Scope for GDDL Itself

GDDL does not generate bindings for any specific embedded scripting language or VM, and should not — it has no way to know a given project's scripting language's calling conventions, type marshalling, or embedding API, and baking in support for one specific language would tie a general-purpose data definition language to a moving, project-specific target.

Instead, GDDL exports a **metadata manifest** — a new export target (in the spirit of "other user-defined export formats," named as a category since v1) alongside the C++ header: a deterministic, machine-readable description (e.g. JSON) of every `define`'s fields and types, every instance's name and stable ID, and every identifier domain's members and logical IDs — generated from the same compiled representation as the C++ export, in lockstep with it, so the two can never silently drift apart.

A separate, project-specific tool (understanding the actual scripting language's embedding conventions) reads this manifest and generates the real binding glue — registering types with the VM, generating per-field getter thunks that dereference the real C++ memory (valid for an in-process VM sharing the same address space, which is the case this was designed against), and exposing each type's registry for script-side lookup and iteration identical in spirit to the C++ side. This keeps GDDL itself permanently scripting-language-agnostic while still making automated, always-in-sync binding generation possible — the metadata manifest is what makes it automatable at all, replacing what would otherwise be hand-maintained bindings that silently drift out of sync every time a `.gddl` file's schema changes.

### 14.7 Indexed Mode (§8.3) in C++

On 6502, indexed mode exists to eliminate load-time resolution cost — but `inline constexpr` already gives C++ that property unconditionally, indexed or not. The problem indexed mode actually solves in C++ is different: **dispatch efficiency.** A domain's default logical-ID values are sparse 64-bit hashes; a `switch` or array lookup over them can't become an O(1) jump, forcing a binary search or comparison chain. Indexed mode gives hot-path dispatch code (e.g. a per-frame attack-handler lookup across thousands of instances) a small, dense, declaration-ordered value instead.

**A domain that declares a width gets a companion enum, generated only if something actually uses `@Domain` somewhere in the compiled data:**

```cpp
enum class ActionAttack : uint64_t        // unchanged, default logical-ID mode, always generated
{
    melee_weapon = 0x5c96a731d7d47e03ULL,
    ranged_weapon = 0xaa92e2b5323e5154ULL,
};

enum class ActionAttack_Indexed : uint8_t // generated only if @ActionAttack is used somewhere
{
    melee_weapon = 0,
    ranged_weapon = 1,
};
```

Values are 0-based, declaration order, per §8.4 — nothing new there, just applied to this concrete C++ shape. A field declared `@ActionAttack` gets `ActionAttack_Indexed` as its C++ struct member type, not `ActionAttack` — this preserves type safety and self-documentation; an indexed field is never exported as a raw, meaning-less integer.

**Planned, not yet implemented: force-emitting indexed enums with nothing in the data referencing them.** A game developer may want an `_Indexed` companion enum available for hand-written C++ dispatch code (e.g. a function-pointer table indexed directly by the compact value) without ever storing an `@Domain`-typed field in any GDDL-defined struct at all. This needs a single export-time boolean switch — no per-domain selection list. When on, the exporter emits the companion enum for **every** domain that has declared a width (§8.3), regardless of whether `@Domain` is actually used anywhere in the compiled data; when off (the default), a companion enum is only ever emitted for a domain actually referenced via `@`, as already specified above. This follows the same precedent as §8.3's existing compile-time mode-override flag: an export-time convenience knob layered on top of otherwise-unchanged per-field/per-domain semantics. A domain with no declared width is simply unaffected by this switch either way — there's nothing for it to force-emit.

**See §8.5 for the cross-target version of this same underlying need.** 6502, Z80, and 68000 all have an equivalent, but structurally different, gap: since those targets have no default-vs-indexed duality at all (`Domain`/`@Domain` are indistinguishable there), an entirely unreferenced, width-declared domain is missing in full, not missing one companion form of an already-emitted domain. Same shared boolean flag shape, same underlying justification, genuinely different mechanism per target — confirmed directly against each exporter's actual code and a real fixture, not assumed to generalize from this section alone.

---

## 15. 68000 Export Specification

Motorola 68000 export — targeting both the Atari ST and the Amiga, motivated by reaching a substantially larger audience of retro/homebrew developers than 6502 alone reaches. This is a genuine hybrid of the two prior export targets, not a clone of either: its **implementation style follows the C++ exporter** (real structs, a real C compiler doing codegen, no hand-tuned assembly), while its **identity/indexing philosophy follows the 6502 exporter** (fully static, no logical IDs, dense declaration-order indices, no search).

### 15.1 Target: C Source via `vbcc`

Unlike 6502 (where no practical C compiler was ever in scope, forcing raw hand-written assembly), real Atari ST/Amiga development is commonly done mostly in C, with assembly reserved only for small, critical hot spots. `vbcc` (Volker Barthelmann's C compiler) is a genuine, actively-maintained, portable ANSI C compiler used across both platforms, paired with the `vasm` assembler and `vlink` linker as one shared toolchain family — this is a real, current, non-speculative choice, not a historical curiosity: both platforms have converged on the same modern toolchain despite each having its own separate historically-famous tools (Devpac, Pure C, and Lattice C for Atari ST; ASM-One, Devpac, and SAS/C for Amiga).

**Target C89, not "parts of C99."** `vbcc`'s own documentation is explicit about full C89 support with only partial C99 support — "partial" is too vague a target to build against confidently, the same reasoning that motivated picking C++17 outright for the C++ exporter rather than something fuzzier.

**One shared design serves both platforms.** The generated C89 data (structs, arrays, constants) is platform-agnostic — Atari ST and Amiga only actually differ at the point of compiling and linking against each OS's own libraries (`vbcc`'s own separate target configuration), not in what GDDL generates. This is notably simpler than 6502's three genuinely incompatible assembler dialects: one generated output, two `vbcc` target configs.

### 15.2 No `inline`-Equivalent Trickery Needed — But a Header/`.c` Split Is Still Required

C++'s registry design (§14.2) exists partly to solve a C++-specific problem: a `constexpr` value nothing takes the address of can be silently optimized out of existence entirely. **This problem does not exist in C.** An ordinary global variable with external linkage is always emitted into the compiled output — the compiler can never assume another translation unit won't reference it.

**This does not mean a header/`.c` split is optional, though — it's required for any real multi-file project, for an entirely ordinary reason.** A definition (`const Creature Creature_Instances[2] = {...};`) can only appear in exactly one `.c` file; anything else that needs this data must see only a **declaration** (`extern const Creature Creature_Instances[2];`) in a header, the same basic C convention every real multi-file C project already follows. A single generated `.c` file that's directly `#include`d — which is how this first pass validated correctness, out of test-harness convenience — only works because the test happens to be exactly one translation unit. The moment a second `.c` file in a real project needs the same data, this breaks with duplicate-definition linker errors. **The exporter must always produce a genuine header (declarations, `extern`) plus a `.c` file (the actual definitions)**, never a single file meant to be directly included by more than one place.

### 15.3 No Hand-Written Byte-Splitting Tricks Needed

The 6502 exporter's lo/hi byte-array splitting (§10.2) was a raw-assembly-specific workaround for a CPU with no multiply instruction at all. On 68000, ordinary C array indexing (`table[index]`) is idiomatic and correct; `vbcc`'s own code generator decides how to implement it efficiently. **This is the compiler's job now, not something GDDL's text generator hand-optimizes** — a meaningful simplification versus the 6502 renderer's approach.

The instinct to avoid multiplication where possible still applies, for a different reason than 6502's: the 68000's `MULU`/`MULS` instructions are available but genuinely slow (roughly 38–70+ cycles depending on operand, versus a handful of cycles for a shift or plain indexed load) — available, not forbidden, but still worth avoiding in a hot path where it's not truly necessary. This mainly affects how `vbcc` itself compiles ordinary array indexing, not something GDDL's generated C source needs to work around directly.

### 15.4 Identity System: Same as 6502, Not C++

**The "fully static, no logical IDs, dense declaration-order index, no mod/DLC" reasoning (§9, §10.1) carries over to Atari ST and Amiga as-is.** Both platforms shipped on physical media (floppy disk, cartridge) in the same fundamental distribution model as 6502's cartridge/tape/disk — no live-patching mechanic exists for a released game the way networked software has, so the problem logical IDs and stable IDs solve simply doesn't arise here either. Every identifier-typed field and every instance reference is a dense, declaration-order index, exactly as on 6502 — never a 64-bit hash, regardless of how the field's declared type is written in source.

Since C has no `enum class` with an explicit underlying type, identifier domains are represented as a `typedef` for nominal type-hinting plus typed constants, rather than untyped `#define`s — preserving some self-documentation value even though C won't enforce the type the way C++ does:

```c
typedef unsigned char ActionAttack;
#define ActionAttack_melee_weapon  ((ActionAttack)0)
#define ActionAttack_ranged_weapon ((ActionAttack)1)
```

Naming reuses the exact `TypeName_InstanceName` / `Domain_member` prefix convention already established for the 6502 exporter (§10) — C has no namespaces either, and that convention already solved this exact problem once; no need for a second scheme.

### 15.5 AoS/SoA — Same Mechanism, Reframed Motivation

AoS/SoA (§13) remains available and works exactly the same way here as on any other target — a single explicit, per-run flag, never a default that varies by target (§13.6). The *motivation* reframes, though: no longer "avoid multiply because the CPU cannot do it at all" (6502's reason), but the C++ rationale (§13) — cache locality and hot-loop efficiency for code that only touches one or two fields across many instances — since `vbcc` and the 68000 handle indexing arithmetic correctly either way, with or without SoA.

---

## 16. Z80 Export Specification (Preliminary)

Z80 export — targeting ZX Spectrum, and by extension other Z80-family retro platforms reachable through `z88dk`'s broader target support (MSX, Amstrad CPC, Sega Master System, Game Boy, and more). **The Z80 has no hardware multiply instruction at all** — the same fundamental limitation as 6502, not 68000's "available but slow." As a direct consequence, the identity system and multiply-avoidance discipline both follow the **6502 model** here, regardless of which toolchain or output form is chosen — this is not a new decision, since §9's "fully static, no live patching" reasoning (the actual justification for dense declaration-order indices over logical IDs) is about physical-media distribution, not CPU capability, and applies identically to Z80/ZX Spectrum's tape/disk-based distribution model.

### 16.1 Two Toolchains, Three Output Paths

Unlike 68000 (where C was clearly dominant enough to justify a single implementation style) or 6502 (assembly-only, no viable C compiler in scope), **Z80 development practice is genuinely mixed between assembly and C, with no clear consensus favoring one.** This motivates supporting both toolchains as parallel, equally-legitimate options — the same reasoning already applied to AoS/SoA (§13) and header-mode (§14.3/15.2): when two approaches both serve real needs, offer both rather than force a single choice.

- **SjASMPlus** — assembly only. One renderer, following the 6502 exporter's *identity system* directly (§10): dense declaration-order indices, no logical IDs, hand-written dispatch/registry subroutines. **The dispatch/registry table layout itself is Z80-specific, not a copy of 6502's split-array pattern**: a single combined table of 2-byte little-endian entries (ordinary `dw HandlerName`/`dw InstanceLabel` per entry), indexed by `index × 2` — cheap on Z80 via `add hl,hl`, a plain left-shift, not a real multiply — then read via the classic `ld a,(hl) / inc hl / ld h,(hl) / ld l,a` sequence, ending in either `jp (hl)` (dispatch) or `ret` (registry, address left in `HL`). This is cheaper on Z80 than 6502's two-separate-arrays approach specifically because Z80's register-based addressing avoids recomputing the table-base-plus-index address twice — an advantage 6502 doesn't have, so 6502 keeps its own split-array design unchanged (§10.2); the two targets deliberately diverge here rather than sharing one pattern.
- **`z88dk`** — a broader development kit supporting *both* assembly and C internally, selectable independently of the toolchain choice itself:
  - **`z88dk` assembly mode** — raw assembly output, targeting `z88dk`'s own internal assembler syntax, which is distinct from SjASMPlus's and needs its own real investigation — the same "verify the actual syntax, don't assume it resembles the last dialect" discipline applied to every prior assembler (ACME, KickAssembler, 64tass all turned out to genuinely differ from each other).
  - **`z88dk` C mode** — C source, compiled via `z88dk`'s own C toolchain (`zcc`), **targeting `zsdcc` (z88dk's packaging of SDCC) exclusively.** This follows the C++/68000-style *implementation* pattern (real structs, a real compiler) — but **the identity system and multiply-avoidance discipline stay 6502-style even here.** The Z80 lacking hardware multiply is a CPU-level fact independent of language choice, so generated C code must still avoid ordinary AoS-style struct-array indexing on likely hot paths where it would be costly, the same way 6502's generated assembly needed to — unlike 68000, where plain C array indexing was fine to leave entirely to the compiler's own codegen.

    **`sccz80` (z88dk's own in-house compiler, unrelated to SDCC) is deliberately not a supported target.** Measured directly (SDCC 4.2.0 standing in for `zsdcc`; both compilers accept the same C89 source unmodified): `sccz80` inlines constant-multiplication only for a hardcoded, enumerated set of multipliers (1–10, 12, 14, 15, 16, 20, 32, 40, 64, 256, 512, 1024, 2048 — confirmed directly from `sccz80`'s `quikmult()`, not inferred from timing alone); any struct size or `string N` width outside that list falls through to a runtime multiply-helper call, at a measured cost of roughly 500+ Z80 T-states per access versus a small, constant handful for the values the list does cover. `zsdcc` has no such cliff — it strength-reduces every constant multiply, at any value, with no runtime call. Since GDDL cannot constrain what struct sizes or string widths a project's data happens to produce, and the goal is runtime speed rather than build speed, only `zsdcc` is supported. (`sccz80` also compiles roughly 8× faster and, for GDDL's specific access shapes, generates code that is both slower and not smaller than `zsdcc`'s — it has no compensating advantage for this use case.)

    A `zsdcc` build depends on SDCC being present in the `z88dk` toolchain; official `z88dk` binary distributions bundle it, but a from-source `z88dk` build requires building SDCC as an additional step. This should be stated plainly wherever the C-mode toolchain is documented for a developer, since `sccz80` remains `zcc`'s default compiler and is silently selected if `-compiler=sdcc` isn't passed.

### 16.1.1 Naming

Three names, shared across every Z80 output path (SjASMPlus, `z88dk` assembly mode, `z88dk` C mode) for the same underlying concepts, so a developer moving between them finds the same vocabulary:

- **`{Type}_Instances`** — the dense, declaration-order array of instance data itself. Matches the name already used by the C++ (§14) and 68000 (§15) exporters for the same concept. Always emitted, regardless of any flag below — this is where the data actually lives.
- **`{Type}_Registry`** — the parallel table of pointers into `{Type}_Instances`, one entry per instance, indexed the same way as the data it points to. Only emitted when the pointer-table flag (§16.3) is on for the given run. Name inherited unchanged from the existing SjASMPlus/`z88dk`-asm renderers.
- **`{Type}_Find`** — the function (assembly: callable subroutine; C: either an ordinary function or, when the compiler inlines it, effectively free) that resolves a dense index to an instance pointer. Takes the index, returns the pointer; in assembly, per existing convention, the index arrives in `A` and the pointer is returned in `HL`.

**`{Type}_Find` is a rename, for Z80 only, of what the existing SjASMPlus and `z88dk`-asm renderers previously called `{Type}_Registry_Find`.** The shorter name matches the name already used by the 68000 exporter (§15) for the same conceptual operation — resolve a dense index to an instance pointer — despite the two targets implementing it by different mechanisms (68000: direct struct-array indexing, left entirely to the compiler; Z80: an explicit pointer table when §16.3's flag is on, or an exporter-emitted shift-add index computation when it's off). Same job, same name, regardless of mechanism or whether a separate table exists to back it.

**Known open inconsistency, not yet resolved:** the 6502 exporter (§10) still calls its equivalent function `{Type}_Registry_Find`, across all three of its assembler dialects (ACME, KickAssembler, 64tass). This predates the present naming decision and was deliberately left untouched for now — 6502 is already built and validated, and folding it into this rename was judged a separate, larger piece of work (re-validation across three dialects with real assemblers plus `py65` emulation) rather than something to bundle into the Z80 change. **This is a tracked follow-up, not a resolved decision to leave 6502 as `Registry_Find` permanently** — it should eventually be renamed to `{Type}_Find` to match every other target, at which point this paragraph should be deleted.

### 16.2 Direct Indexing vs. Pointer Table (AoS Only)

**`{Type}_Instances` is always present — the struct data has to live somewhere regardless of any flag.** The only question this flag answers is whether a second array, `{Type}_Registry`, is *also* emitted alongside it, holding one pointer per instance so that indexed lookups can go through a flat `index × 2` (a Z80 pointer is 2 bytes) rather than `index × sizeof(Type)`.

This is a genuine, non-obvious tradeoff rather than an obvious win either way, measured directly against real `zsdcc` (T-states, single indexed field access, `z88dk`'s own cycle-accurate emulator, both forms measured inline with no call-site overhead in either column):

| `sizeof(Type)` | direct indexing (`Instances[i].field`) | pointer table (`Registry[i]->field`) |
|---|---|---|
| 2 | 65 (cheaper) | 89 |
| 8 | 87 (cheaper, marginal) | 89 |
| 16 | 98 | 89 (cheaper) |
| 21 | 128 | 89 (cheaper) |
| 32 | 109 | 89 (cheaper) |
| 64 | 120 | 89 (cheaper) |

Direct indexing costs one `add hl,hl` per power-of-two step in `sizeof(Type)` and starts cheaper; the pointer table costs a constant 89 T-states regardless of type size, at a cost of 2 bytes of table per instance. **The crossover sits between 8 and 16 bytes** — materially more types should use the pointer table than a first pass at this measurement suggested. Neither form is universally correct, and — critically — **the exporter cannot decide this per-type automatically**: doing so would mean a type's generated API silently changes shape (whether `{Type}_Registry` exists at all) purely because its field list happens to sum past an undocumented byte threshold, which is exactly the kind of silent, field-list-dependent instability this design otherwise avoids.

**Measurement history, recorded for anyone re-deriving these numbers later:** an earlier pass at this table was built from stock SDCC 4.2.0 standing in for `zsdcc` (`zsdcc` wasn't yet buildable in that environment — upstream SDCC lives on SourceForge, which is blocked; the actual patched source is `github.com/z88dk/sdcc`, branch `zsdcc`, not `master`). That earlier table put the crossover between 16 and 32 bytes, and turned out to have a real defect beyond just using a stand-in compiler: the two columns had been measured under inconsistent framing, with 17 T-states of asymmetry between them — exactly the cost of one `CALL nn` — baked into the pointer-table column but not the direct-indexing column. Root-caused by comparing an instruction-level cycle model against measurement (the model matched exactly at every size once the asymmetry was accounted for), then confirmed the access-shape comparison holds under `-O2`/`--opt-code-speed` (optimization changes only the common calling-convention prologue, not the relative cost of the two indexing forms). The table above supersedes that one.

**This is therefore a single, mandatory, export-time flag with no default** — `--z80-pointer-table=on|off` — following the precedent already set by `--zp-base` (§10.2): a resource/performance tradeoff only the developer, knowing their own target's memory budget and which lookups sit in a hot path, can correctly decide. The flag applies identically across **both** Z80 output paths (assembly and `z88dk` C mode) and to **both** `z88dk`-asm and SjASMPlus within the assembly path — one flag, one meaning, everywhere on this target, so a developer never has to remember that it defaults differently depending which Z80 exporter they happen to be using.

**This flag is AoS-only.** Under `--layout=soa` (§13.6) there are no instance structs to hold addresses of in the first place — SoA data is already flattened into per-field arrays, indexed directly. Setting `--z80-pointer-table` under `layout=soa` produces a warning (§9's diagnostic category) and is otherwise ignored, rather than a hard error, since the two flags are independent axes that simply don't compose meaningfully in this one direction.

**Migration note for already-validated fixtures:** because the assembly renderers previously emitted the pointer table unconditionally (no flag existed), every existing Z80 assembly fixture needs `--z80-pointer-table=on` added explicitly when this flag is introduced, to preserve today's actual output. This is a one-time, mechanical fixture update, not a behavior change — but it does mean re-running golden capture for the affected fixtures rather than treating the flag as backward-compatible by default.

### 16.2.1 Header/`.c` Split (`z88dk` C Mode)

`z88dk` C mode targets C89 via `zsdcc`, the same language tier as 68000's `vbcc` target (§15.1) — so it inherits **68000's reasoning for requiring a header/`.c` split (§15.2), not C++'s.** There is no `constexpr`-retention problem to solve here (C has none), but the ordinary C rule still applies unchanged: a definition (`const Item Item_Instances[2] = {...};`) can only appear in exactly one `.c` file, and any second file needing the same data breaks with duplicate-definition linker errors the moment a real project has more than one translation unit. A single directly-`#include`d file is test-harness convenience only, exactly as noted for 68000, and not what the exporter produces for real use.

Always in the header: struct/type definitions, and `extern` declarations for `{Type}_Instances`, `{Type}_Registry` (only if §16.2's flag is on for the run), and `{Type}_Find`'s signature.

In the `.c`: the actual `{Type}_Instances` definitions, the actual `{Type}_Registry` contents (if emitted), and `{Type}_Find`'s body.

**Identifier domain constants are emitted as `#define`, never `enum`** — a C89 `enum`'s underlying type is implementation-defined and typically `int` (16-bit here), which would silently widen what should be a `u8`-sized index the moment it's stored or compared against one. This is not a Z80-specific rule: the 68000 exporter (§15) already follows it for the same reason, since it targets the same C89 tier via `vbcc`. Both C89 targets should stay consistent on this point going forward.

### 16.3 Selection Mechanism

Four independent, composable export-time flags, following the precedent set by `--dialect` (§10.3) and `--layout` (§13.6):

- `--z80-toolchain=sjasmplus|z88dk`
- `--z88dk-output=asm|c` (meaningful only when `--z80-toolchain=z88dk`; rejected as a configuration error otherwise, the same "an export-time flag combination must make sense together" discipline as `--dialect`/`--layout` composing freely for 6502)
- `--z80-pointer-table=on|off` (§16.2; mandatory, no default, applies regardless of the other two flags' values — the only exception is a warning, not an error, when combined with `--layout=soa`)
- `--z80-find-macro=on|off` (assembly output only — SjASMPlus and `z88dk` asm mode — meaningless for `z88dk` C mode, where the compiler's own inlining decision serves the same purpose; rejected as a configuration error if set alongside `--z88dk-output=c`). Default `off`. When `on`, `{Type}_Find` is additionally emitted as a `MACRO`/`ENDM` block expanding to the identical instruction sequence as the callable subroutine — verified byte-identical against both assembler dialects — trading code size at each expansion site for the ~27 T-states (one `CALL`+`RET`) a call-site would otherwise pay. **The macro must be defined before first use** — the existing convention of `include`-ing generated output at the end of a hand-written file works for label references but not for macro invocations, which need the definition to have already been seen by the assembler. Generated output states this caveat inline as a comment.

---

## 17. Standalone Binary Data Export

### 17.1 Purpose and Scope

Every export target specified so far — C++, 6502, Z80, 68000 — produces *source code* compiled together with hand-written game code into one binary, with all data baked in at build time. Nothing in this project, until now, has provided a way for a game to load GDDL-defined data from a file at runtime, independent of any compile step.

This section specifies exactly that: a standalone binary data format, decoupled from any single compile target, readable by third-party software written in any language, with no dependency on GDDL's own source code or any particular compiler ABI.

**This is not an extension of §14.6.** §14.6's metadata manifest exists to let a scripting VM, running in-process, generate binding glue that reads memory already baked into a compiled C++ binary — it describes data that already exists, it doesn't carry any. This section's format is the opposite: the data itself, portable, meant to be loaded independently, by a program that may never have linked against any GDDL-generated C++ at all.

**This section is what makes §9 (Modding and DLC Support) concretely buildable.** §9 specifies how a mod's new logical IDs register into a runtime dispatch map, but never specifies where a mod's actual instance data comes from — every prior export target assumed all data was compiled in advance, which a mod's data, by definition, isn't. This format is that missing piece.

**Explicit non-goal, stated plainly rather than left to be assumed:** a mod may declare new *instances* of a type the base game already knows about. A mod may **not** declare an entirely new `define` the base game's compiled code has never seen — consuming an arbitrary, previously-unknown schema at runtime would require the game to interpret data generically rather than read it into known compiled structs, which is a fundamentally different kind of system than anything else in this specification, and is out of scope.

### 17.2 File Pair

Two files, matching the existing convention that a manifest accompanies an export rather than replacing it (§14.6):

- **`.gddldata.bin`** — the data itself. Deliberately minimal, no structural knowledge required to parse it beyond what's in its own small header (§17.3) — everything else needed to interpret it fully lives in the manifest.
- **`.gddlmeta.json`** — full structural description: every type's field list (name, type, byte offset, byte width), every domain's members and width, generated from the same compiled representation as the binary file, in lockstep with it, the same guarantee §14.6 already makes for its own manifest.

**The shipped game never needs to parse the JSON manifest to do its one load-time safety check (§17.4) — that check is a pure binary-to-binary comparison.** The manifest exists for tools, editors, documentation generation, and any third-party reader wanting full introspection — never on a shipped game's critical load path.

### 17.3 Binary File Structure

- **Global header:** magic bytes, a format-version byte (so the container format itself can evolve independent of any project's schema).
- **Per-type table:** for every type present in this file — type name, record byte size, record count, this type's schema hash (§17.4), byte offset of its record array, byte offset and count of its optional ID-lookup table (zero/absent if this type isn't using logical-ID lookup).
- **Per-type record arrays:** one packed, contiguous array per type. Fields flattened through composition (§5.2) into a flat leaf list, declaration order, **no padding**, **little-endian** throughout (§17.3.1). `string N` fields remain exactly the fixed-width ASCIIZ representation already specified (§4.1.1) — nothing new invented for this target. An identifier-typed field uses its domain's dense index at the declared width when using the indexed form (`@Domain`, §8.3), or the full 8-byte logical ID hash otherwise — matching the default-is-always-logical-ID rule already stated in §8.3, never inferred.
- **Per-type ID-lookup tables (optional):** `(stable_id: u64, dense_index)` pairs, sorted by ID for binary search — the same shape as C++'s own registry (§14.4), just serialized instead of `constexpr`.

#### 17.3.1 Endianness

**Little-endian, unconditionally, with no configurable alternative.** Every realistic modern target this format is meant to serve — x86-64, ARM64 (Apple Silicon, iOS, Android, Switch, PS5, Xbox Series) — is little-endian; the last real big-endian consumer hardware (pre-2006 PowerPC Macs) has been dead for nearly two decades, and the retro 8/16-bit targets this project already supports (6502, Z80) aren't realistic consumers of this format's full manifest-driven path in the first place (§17.7). A future genuinely big-endian target, if one ever mattered, would need a byte-swap-on-load step — a small, isolated addition, not a redesign of this format.

### 17.4 Compatibility Checking

**Per-type, not a single whole-project fingerprint.** Each type gets its own `(schema_hash: u64, record_size: u32)` pair. This means a base-game patch touching one type's field list only invalidates mods that actually reference that type — every mod untouched by the change keeps working without a rebuild.

- **`schema_hash`**: FNV-1a-64 (the same hash function used everywhere else in this language, §4.1.1/§6.8 — no second hash algorithm introduced for this purpose) over a canonical serialization of the type's complete field list: every field's name, type, and order.
- **`record_size`**: computed directly from field widths — **not derived from or verified against the hash**, computed by a completely independent code path.

**Why both, when `record_size` is already implied by the same information the hash covers:** the point of comparing two independently-computed values isn't defending against ordinary schema drift — a hash mismatch already catches that on its own. It's defending against **a bug in the hash computation itself**. If two pieces of code that are each supposed to compute "this type's schema hash" diverge even slightly — different canonicalization, an inconsistently-handled edge case — a hash-only check can pass when it shouldn't, because both sides confidently agree on the same wrong answer. Comparing against a size computed a completely different way is real protection against exactly that failure mode. This isn't hypothetical: this project already found multiple real instances this session of two things that were supposed to compute the same result quietly failing to (the Z80 `Registry_Count` variable-shadowing bug, the C++ `header_filename` mismatch, the tokenizer's escape-parity bug) — and a second, independent, from-scratch C++ implementation of this compiler is a standing, deferred item in this project's own history. If that implementation's schema-hash logic ever drifts from the Python reference's, even slightly, this is the check that catches it before a hash-only design silently would have let a genuinely incompatible file load.

### 17.5 The Compile-Time Header Table (C++)

The C++ exporter (§14) additionally emits a small compile-time table alongside its existing header output: for every type in the schema, `(type_name, schema_hash, record_size)` — generated by the exact same code path that computes these values for the `.gddldata.bin` export, so the two can never drift apart by construction, the same guarantee already made for §14.6's manifest.

**This is what lets a compiled game know, at its own compile time, exactly what it was built with** — independent of whatever `.gddldata.bin`/`.gddlmeta.json` pair it happens to load at runtime. The comparison in §17.6's algorithm is always: the game's own compiled-in expectation, against whatever a loaded file actually declares.

This table is C++-specific, consistent with §9 already scoping modding and runtime data loading as a PC-only capability — 6502-class platforms have no equivalent capability, and none is designed for one (§9.2).

### 17.6 Division of Responsibility

Stated explicitly, since anyone building on this format needs to know exactly where GDDL's guarantees end and their own game's responsibilities begin.

**The GDDL compiler/exporter is responsible for:**
- Producing a correct `.gddldata.bin`/`.gddlmeta.json` pair from a compiled schema.
- Producing the C++ compile-time table (§17.5) in lockstep with that pair, from the same underlying computation.
- Correct, consistent `schema_hash`/`record_size` computation — and, especially once a second compiler implementation exists, keeping that computation identical across implementations is a real, ongoing correctness obligation, not a one-time task.

**The GDDL compiler/exporter is explicitly *not* responsible for:**
- Actually loading any file at runtime — there is no GDDL runtime library specified or implied.
- Cross-mod ID collision detection. No compiler, GDDL's or otherwise, ever sees two independently-compiled mod files together — there is no point in any pipeline where this could be checked at compile time. This is a solved problem, not an unsolved one: the runtime's own dispatch-registration insert (§9.1's `unordered_map`) already reveals a collision for free the moment a second insert with the same key fails — no new mechanism needs to be built, and none is GDDL's to build.
- Merging loaded data into whatever live in-memory structures a game maintains — GDDL delivers validated, ready-to-read bytes; what a game does with them afterward is entirely its own concern.

**The game/runtime is responsible for, in order, at every file load:**
1. For each type present in the loaded file: look up the type name against its own compiled-in table (§17.5). A name with no match means the game wasn't compiled with this type at all — skip that type's data from this file entirely. (This is also how the §17.1 non-goal — no new types from mods — is naturally enforced: the game simply has nothing to interpret an unknown type's bytes as, so it doesn't try.)
2. For each type name that *does* match: compare `(schema_hash, record_size)` between the loaded file's per-type table entry and the game's own compiled-in expectation. Equal on both means it's safe to read that type's record array directly as the compiled struct. Unequal on either means reject that type's data from this file — logged, not crashed on.
3. For types that passed: read the record array (bulk iteration by index) and/or the ID-lookup table (binary search by stable ID) as needed, and insert the resulting instances into the game's own live runtime structures — a live dispatch map (§9.1), a live instance registry, whatever the game itself maintains. GDDL specifies none of this; it only guarantees the bytes being inserted are safe to interpret.
4. Any collision encountered while inserting a newly-loaded instance's stable ID into the game's own live structures is the game's own concern to detect and handle (trivially, per the point above) — not something to check for separately beforehand.

### 17.7 Modding, DLC, and Cross-File Loading

Any number of `.gddldata.bin` files — the base game's own, plus any number of mods' — can be loaded side by side, each independently checked per §17.6, and merged into one set of live runtime structures. No special handling is needed for this beyond running §17.6's algorithm once per file: a mod's file just declares new instances of already-known types, which is indistinguishable, from the compatibility check's perspective, from any other load.

For 6502 and Z80: nothing in this section applies to those targets' own existing export paths (§10, §16), which remain compile-time-only, per §9.2. A retro-platform programmer *can* still choose to hand-write an assembly routine that reads a `.gddldata.bin` file's raw bytes directly at a documented, fixed offset — the format itself is platform-agnostic, nothing in it assumes C++ or any particular ABI — but they would do so entirely without the manifest, the compatibility check, or any of this section's tooling, working from the documented byte layout alone and skipping whatever fields don't fit their platform's practical width. This isn't a capability GDDL needs to build for that case; it falls out for free from the format not assuming anything C++-specific in the first place.

---

## 18. Multi-File Compilation

### 18.1 Purpose and Scope

A single `.gddl` file has always been fully self-contained — its own identifiers, its own `define`s, its own instances — and nothing about that changes here. This section adds the ability to compile **several such files together as one combined unit**, letting a `define` (or an `identifier` domain) live in one file while any number of other files declare instances of it. This is the mechanism that makes a shared `Definitions.weapon`-style file, referenced implicitly by many other files declaring actual weapon instances, expressible for the first time — previously, every file needing a given type had to redeclare it.

**This is entirely a front-end input-handling concern, resolved before any exporter is ever invoked.** No exporter (§10, §14, §15, §16, §17) needs to know, or is able to tell, whether its input came from one file or many — by the time compilation reaches parsing, there is exactly one combined source, exactly as today.

### 18.2 How Combination Works

Every resolved input file is concatenated into a single in-memory source text, then handed to the existing single-file pipeline unchanged. This works cleanly, and was verified directly rather than assumed, because the resolver already performs something equivalent to a declaration-collection pass before resolving instances or references — confirmed by direct testing: an instance may already reference its own type's `define`, an identifier domain, or a composed type's `define`, regardless of whether that declaration appears earlier or later in the *same* file. Combining multiple files exposes that existing behavior across file boundaries; it required no change to the parser, resolver, or validator.

**Combined files share one identifier/instance namespace, with full cross-file collision detection.** This is not a side effect to tolerate — it is the actual feature, and it follows directly from the identity system already being global rather than file-scoped (logical IDs are `Domain::text` hashes, stable IDs are `Type::InstanceName` hashes, per §4.1.1/§6.8). Two files declaring the same name collide exactly as two statements in one file would today; nothing about this rule is relaxed by being spread across files.

**Error messages are remapped back to their real source file and line number.** The combination step itself records each input file's name and its starting line offset in the combined text; after compilation, every error and warning is rewritten from a combined-text line number back to `(source file, original line)` before being reported. This remapping is the only new logic in the pipeline — everything upstream and downstream of it is unaware combination ever happened.

**Combination order affects only error-attribution determinism, never compilation success.** Order-independence for compilation itself is confirmed by the testing above — a genuine collision is a genuine collision regardless of which file is processed "first." But when a collision *does* occur, which file's declaration gets reported as "the duplicate" depends on processing order, and that should be reproducible across identical runs, not dependent on filesystem enumeration order (which is not guaranteed stable across platforms). Combination order is therefore fixed as: files given directly on the command line, in the order given, followed by files discovered via glob patterns, in sorted path order.

### 18.3 No Assumed File Extension

**The compiler never assumes `.gddl` as a file extension**, and never infers "this is a GDDL source file" from a name alone. A project may name its files however suits its own organization — `weapons.weapon`, `enemies.enemy`, or anything else — and every input must be given explicitly, either as a literal filename or as a glob pattern that names the extension it's looking for (or deliberately omits one, matching everything in a location).

### 18.4 Input Forms

Three forms, freely combinable in one invocation:

1. **Individual file paths**, with or without leading directory structure (`goblin.weapon`, `items/goblin.weapon`) — always unambiguous, never affected by anything below.
2. **Glob patterns naming an extension**, matching files directly inside a directory (`items/*.weapon`) or, using `**`, recursively through subdirectories (`items/**/*.weapon`).
3. **Unqualified glob patterns**, matching every file in a location regardless of extension (`items/*`, or recursively, `items/**/*`) — a deliberate choice when a project doesn't distinguish by extension at all; anything non-GDDL swept in this way surfaces as an ordinary parse error on that specific file, which is informative, not a failure mode the tool needs to specially guard against.

**There is no bare-folder input form, and no separate recursion flag.** A directory can only be referenced through a glob pattern (form 2 or 3 above) — a tool that doesn't assume any extension has no principled way to answer "which files in this folder count" without one. Recursion is controlled entirely per-pattern by the presence of `**`; a single invocation may freely mix recursive and non-recursive patterns, since there is no global flag to conflict between them.

**Glob expansion is always performed by the GDDL compiler itself, never left to the invoking shell.** This matters concretely across platforms: Unix shells typically expand a wildcard before the program ever sees it, but Windows' `cmd.exe` and PowerShell generally do not, passing the literal pattern text straight through. Relying on shell expansion would make wildcards work by accident on some platforms and silently do nothing on others.

### 18.5 Error Behavior

**Any file argument or glob pattern that resolves to zero actual files is a hard, unconditional error** — never a silent no-op. This is a single uniform rule covering what might otherwise look like two separate cases (a literal file that doesn't exist, and a pattern that matches nothing): both are exactly the same situation, since directory references only ever exist as patterns in the first place, so "this folder has no `.weapon` files" and "this pattern matched zero files" are the same event, not two policies to reconcile.

### 18.6 Output

**Unchanged.** Every exporter's existing `-o`/`--output` flag continues to work exactly as it does for a single file today — multiple inputs are simply a new way of building up the one combined source that gets compiled and exported once. No exporter requires any change to support this.

### 18.7 Deliberately Out of Scope for This Pass

An `--exclude` pattern, for skipping specific paths inside a recursive glob (a `.git` directory, a generated-output directory that happens to sit inside a source tree, etc.). Real and likely useful eventually; not needed for the feature to function, and adding it speculatively now would be building flexibility nobody has asked for yet rather than scoping this cleanly.

---

## 19. Design Summary

| Concept | Rule |
|---|---|
| Identifiers | Logical ID = hash of description text. Permanent, insertion-safe, collision-resistant across independent authors. |
| Identifier blocks | Are themselves types ("domains"). Fields are strictly bound to one domain — no generic identifier type. |
| `define` | Layout only, no data, **never inherits**. Composition (nested struct fields) is the only structural-reuse mechanism. |
| Instances | Built from a `define`; may copy another instance (`= Instance`), then execute statements sequentially. |
| Nested fields | `field = Instance` → full replace, then modify. Bare `field` → modify-only, touches only what's listed. No merge mode, ever. |
| `delete` | Marks a template: may be incomplete, compiled but never exported, may be copied. |
| Initialization | No implicit defaults, anywhere. Reading or exporting an uninitialized field is a compile error. |
| Save / binary export | Default: logical ID, stable under identifier insertion at any version. |
| Direct indexing | Opt-in per `define` (or globally via compile flag). Always user-specified width. Only safe for data always compiled together with its own registry (e.g. baked ROM data). |
| Ordering | Logical-ID mode: canonical hash order (position-independent). Indexed mode: declaration order (position-is-identity). |
| Modding/DLC | PC only — dynamic `logical ID -> function pointer` dispatch. 6502 is fully static; new content requires a full rebuild. |
| Instance stable IDs | Same FNV-1a-64/qualified-name mechanism as identifiers (`TypeName::InstanceName`). What registries are keyed by. |
| ID collision detection | One shared table across all identifier + instance IDs project-wide. Any collision is a hard compile error, never a warning. |
| C++ export | `inline constexpr` instances (never bare `constexpr`), per-type registry forces retention + enables lookup, direct + dynamic access over the same data, no generic query engine — plain iteration instead. |
| Scripting bindings | Out of GDDL's scope. GDDL exports a metadata manifest; a separate project-specific tool generates the actual binding glue for whatever language/VM is in use. |
| Determinism | Identical source + settings -> identical output, always. |

---

*This document consolidates the original GDDL specification (v1), the v3 revision, the export/save-format design notes, and design decisions resolved through direct review, superseding prior versions where they conflict — most notably: removal of the speculative version-seed / u8-hybrid save mechanism, formalization of replace-vs-modify-only nested field semantics, the no-merge-semantics rule, the definitions-never-inherit rule, identifier domains as strict field types, the logical-ID/direct-index duality with mode-dependent ordering, and the PC-only scope of modding support.*
