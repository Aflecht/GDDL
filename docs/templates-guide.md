# Templates, Chains, and Expressions

A game rarely has enemies, items, or abilities that are each entirely unique. Most share a common baseline, a whole tier of goblins might use roughly the same stats, with only a couple of numbers actually differing between the weak one and the tough one. Templates let you write that shared baseline once, then have each variant state only what's different from it, instead of retyping every field for every variant. Since GDDL's `define`s deliberately never inherit from each other (composition is the only structural-reuse mechanism for types), templates are what fill that same role at the instance level.

The README's [Templates you copy, not classes you extend](../README.md#templates-you-copy-not-classes-you-extend) section already covers the basics:

- Copying an instance with `Creature Human_Fighter = BaseCreature`
- `delete`-marked templates that compile but never export
- Simple arithmetic against the copy

This page goes further:

- Chains more than one generation deep
- The full set of operators, and how they actually evaluate
- Referencing other fields inside an expression
- What happens to a struct-typed field specifically when you copy into it

## Every field, or it doesn't compile

One rule underlies everything else on this page: every field an exported instance holds must actually be set by the time it's exported. No silent defaults, no zero-filling, and no exceptions.

```gddl
define Creature
	hitpoints = i32
	name = string 20

Creature Goblin
	hitpoints = 30
```

`name` never gets set. This doesn't compile:

```
Goblin: INCOMPLETE [phase 8] - export-blocking, uninitialized field(s): name
```

Real compiler, real failure, naming the exact instance and the exact missing field. Nothing gets written, exit code 1.

This is exactly why `delete` templates exist as their own, deliberate special case. A template is allowed to stay incomplete specifically because it's never exported directly, only ever copied from, matching the README's own example. Every other instance has no such exemption, complete or it doesn't compile.

## Chains, as many generations as you need

Nothing about copy-and-modify limits it to one hop. A template can copy another template, which can copy another, for as many generations as you actually need. This isn't a separate feature, it's the same copy-and-modify rule, just applied more than once:

```gddl
define Creature
	hitpoints = i32
	armor = i32
	name = string 20

Creature CreatureTemplate delete   // shared baseline, every creature starts here
	hitpoints = 50

Creature GoblinTemplate = CreatureTemplate delete   // goblins specifically: armor, tougher
	armor = 5
	hitpoints * 2

Creature GoblinBoss = GoblinTemplate   // one real, named enemy
	name = "Goblin Boss"
	hitpoints + 100
```

Both templates are `delete`, both can stay incomplete, only the final instance has to be whole. The real, compiled result:

```cpp
const Creature GoblinBoss = { 200, 5, "Goblin Boss" };
```

`50`, doubled to `100`, plus `100`, is `200`, computed once at compile time, across three separate instance bodies. Only `GoblinBoss` shows up in the output at all.

### What happens if a chain loops back on itself

```gddl
define Creature
	hitpoints = i32

Creature GoblinTemplate = GoblinBoss delete   // depends on GoblinBoss...
	hitpoints * 1

Creature GoblinBoss = GoblinTemplate   // ...which depends right back on GoblinTemplate
	hitpoints + 10
```

Neither one can ever actually resolve, there's no base case anywhere in the chain. This is a real, caught compile error, not an infinite loop or a stack overflow:

```
[phase 4, circular_dependency] line 4: circular instance-copy reference: GoblinTemplate -> GoblinBoss -> GoblinTemplate -- every instance in this cycle depends (directly or through a nested full-replace) on another instance in the same cycle, so none of them can ever be resolved
[phase 4, circular_dependency] line 7: circular instance-copy reference: GoblinTemplate -> GoblinBoss -> GoblinTemplate -- every instance in this cycle depends (directly or through a nested full-replace) on another instance in the same cycle, so none of them can ever be resolved
GoblinTemplate: ERROR [phase 4, circular_dependency] - line 4: circular instance-copy reference: GoblinTemplate -> GoblinBoss -> GoblinTemplate -- every instance in this cycle depends (directly or through a nested full-replace) on another instance in the same cycle, so none of them can ever be resolved
GoblinBoss: ERROR [phase 4, circular_dependency] - line 7: circular instance-copy reference: GoblinTemplate -> GoblinBoss -> GoblinTemplate -- every instance in this cycle depends (directly or through a nested full-replace) on another instance in the same cycle, so none of them can ever be resolved
```

It names the exact cycle. The message appears twice in a slightly different shape, once as a general diagnostic, once attributed to each specific instance it blocks, but it's the same real error both times, caught before any resolution work even begins, not partway through.

## Every operator there is, and the rule that catches people off guard

Four operators exist: `+`, `-`, `*`, `/`. Nothing else, no modulo, no bitwise, no comparison.

What catches people off guard is how they combine. There's no precedence table, `*` and `/` don't bind tighter than `+` and `-` the way they would in ordinary math. Everything evaluates strictly left to right, exactly as written:

```gddl
define Item
	value = i32

Item NoParens
	value = 20 + 10 * 3   // left to right: (20 + 10) * 3, not 20 + (10 * 3)

Item WithParens
	value = 20 + (10 * 3)   // explicit grouping forces the other order
```

```cpp
const Item NoParens = { 90 };
const Item WithParens = { 50 };
```

Same numbers, same operators, two different real results, `90` versus `50`, depending only on whether parentheses are there to force the grouping ordinary math would assume for free. Nothing here is a special case for assign statements either, op-statements follow the exact same rule, with the field's own current value counting as the true leftmost operand:

```gddl
Item Test
	value = 10
	value * 2 + 1   // (10 * 2) + 1, not 10 * (2 + 1)
```

```cpp
const Item Test = { 21 };
```

## Referencing other fields

An expression isn't limited to literals and its own field's current value. It can read any other field already set on the same instance:

```gddl
define Item
	weight = u32
	count = u32
	total_weight = u32

Item Crate
	weight = 10
	count = 5
	total_weight = weight * count   // reads two other fields on this same instance
```

```cpp
const Item Crate = { 10, 5, 50 };
```

This only ever reaches fields on the current instance, nothing on any other instance is in scope, by design.

Read a field before it's set, and it's the same uninitialized-field error as before:

```gddl
define Item
	weight = u32
	count = u32
	total_weight = u32

Item Crate
	total_weight = weight * count   // weight and count are read here, but not set yet
	weight = 10
	count = 5
```

```
Crate: ERROR [phase 6, uninitialized_read] - line 7: 'weight' is read before being initialized -- reading an uninitialized field is always a compile-time error, delete-marked instances included
```

A field can even reference its own current value on a plain assign, and unlike op-statement shorthand, that self-reference doesn't have to lead the expression, it can sit anywhere:

```gddl
define Creature
	hitpoints_maximum = i32

Creature Ogre
	hitpoints_maximum = 100
	hitpoints_maximum = 20 + hitpoints_maximum * 0.5   // reads hitpoints_maximum before this line overwrites it
```

```cpp
const Creature Ogre = { 60 };
```

Left to right, same as always: `100`, then `20 + 100 * 0.5` reads as `(20 + 100) * 0.5`, which is `60`.

## Two ways to touch a nested field

This next fork only shows up on struct-typed fields. A scalar field like `hitpoints` has nothing to enter, `hitpoints = 100` is always a plain overwrite. A struct-typed field, one holding another `define`'s worth of data, has two genuinely different ways to be touched.

```gddl
define Stats
	hp = i32
	mp = i32

define Creature
	stats = Stats
	name = string 20

Stats OtherStats delete
	hp = 1
	mp = 2

Creature Base
	stats
		hp = 100
		mp = 50
	name = "Base"

Creature FullReplace = Base
	stats = OtherStats   // discards Base's stats entirely, adopts OtherStats's instead
	name = "FullReplace"

Creature ModifyOnly = Base
	stats
		mp = 999   // only mp changes; hp stays whatever Base already had
	name = "ModifyOnly"
```

```cpp
const Creature FullReplace = { Stats{ 1, 2 }, "FullReplace" };
const Creature ModifyOnly = { Stats{ 100, 999 }, "ModifyOnly" };
```

`stats = OtherStats` is full replace: `Base`'s `hp = 100, mp = 50` is thrown away completely, and `FullReplace` ends up with `OtherStats`'s values instead. A bare `stats` with no `=` is the opposite, modify-only: it enters `Base`'s already-inherited stats and changes only what's actually listed, `mp` becomes `999`, `hp` stays exactly what it already was.

A bare field with nothing indented under it at all is legal, a genuine no-op, but it's usually a mistake, so a warning is generated:

```gddl
define Stats
	hp = i32
	mp = i32

define Creature
	stats = Stats
	name = string 20

Creature Base
	stats
		hp = 100
		mp = 50
	name = "Base"

Creature Placeholder = Base
	stats
	name = "Placeholder"
```

```
WARNING [phase 3, empty_bare_field] - line 16: bare field 'stats' (modify-only form) has no indented sub-statements -- this enters the field's scope but changes nothing in it, which is valid but usually unintentional (e.g. every statement under it got commented out)
```

It still compiles, `Placeholder` just ends up with `Base`'s stats completely untouched. There's no third option in between full replace and modify-only, no mode that keeps old values except where something new happens to be provided. That's deliberate: a field silently keeping a stale value because nobody remembered to list it would look identical to a field someone genuinely meant to leave alone.

## What happens to the result

Every expression on this page eventually gets stored into a field, and that storage step enforces two more rules, on every value, regardless of whether it came from a literal, an op-statement, a copy, or a cross-field reference.

Storing a whole number into a floating-point field always just works, promoted automatically:

```gddl
define Item
	scale = f32

Item Test
	scale = 100 + 50   // an integer result, but the field is f32
```

```cpp
const Item Test = { 150.0f };
```

Going the other way is where it matters. A fractional value stored into an integer field is a real error if any precision would actually be lost:

```gddl
define Item
	count = i32

Item Test
	count = 10 / 3   // 3.333..., a fraction, into an integer field
```

```
Test: ERROR [phase 6, numeric_coercion] - line 5: 'count' is typed 'i32' (integer), but its computed value 3.3333333333333335 has a fractional part -- narrowing with fractional loss is a compile-time error (spec §5, Numeric Type Coercion)
```

Change the numbers so nothing is actually lost, and the exact same shape compiles fine:

```gddl
define Item
	count = i32

Item Test
	count = 12 / 3   // exactly 4.0, no fraction to lose
```

```cpp
const Item Test = { 4 };
```

Range works the same way, checked at the same moment, on the same final value. Every numeric type has a real, fixed range, and storing something outside it is always a compile-time error:

```gddl
define Item
	durability = u8

Item Test
	durability = 300   // u8 only goes up to 255
```

```
Test: ERROR [phase 6, numeric_range] - line 5: 'durability' is typed 'u8', but its computed value 300 is outside u8's range (0..255) -- storing an out-of-range value is a compile-time error, never silently wrapped or clamped (spec §5, Numeric Range Enforcement)
```

Never silently wrapped or clamped is the point. `300` into a `u8` becoming `44` with no error anywhere is exactly the failure mode this rule exists to prevent.

Only the value that actually gets stored is checked, though, not every step along the way there:

```gddl
define Item
	durability = u8

Item Test
	durability = 200 + 100 - 250   // 300 mid-expression, briefly over u8's max of 255
```

```cpp
const Item Test = { 50 };
```

`200 + 100` is `300`, already past `u8`'s ceiling, but that's never stored anywhere, it's just a number partway through evaluating a longer expression. Only `50`, the actual final result, ever gets checked and stored.
