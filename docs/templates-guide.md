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
