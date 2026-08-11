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

