# GDDL: Game Data Definition Language

GDDL lets you define your game's structured data once: item stats, character definitions, ability tables, loot tables, anything with a fixed shape you'd otherwise hand-write as a struct or a spreadsheet. You compile it into whatever your game actually needs: real C++ structs, 6502 or Z80 assembly, C89 for 68000, or a portable binary file your game loads at runtime.

Every export target is generated from the same compiled, validated representation, so your C++ build and your loadable mod data can never silently drift apart from each other.

## Start here

[`docs/getting-started.md`](docs/getting-started.md) walks through running the compiler for real, from nothing installed except Python to a working C++ header, in a few minutes.

Once you're past that, [`SPEC.md`](SPEC.md) is the complete language reference: every type, every rule, how composition and identity and modding all work.

## A quick example

```gddl
define Item
	power = u16

Item Sword
	power = 42

Item Bow
	power = 15

Item Shield
	power = 8
```

Run that through the C++ exporter and you get a real header with all three items already populated:

```cpp
struct Item
{
    uint16_t power;
};

namespace Item_Instances
{
    extern const Item Sword;
    extern const Item Bow;
    extern const Item Shield;
}
```

In your own game code, you can look one up by name, or walk the whole list:

```cpp
// look up one item by name:
const GDDL::Item* sword = GDDL::Item_Registry::Find("Sword");
sword->power; // 42

// or walk the whole list (Table is a plain std::array: fixed-size,
// contiguous, no heap allocation, nothing to slow iteration down):
for (const auto& entry : GDDL::Item_Registry::Table)
    entry.data->power;
```

That's your item list, ready to use in your game.

## Multiple data layouts

You can choose which data layout to export into, switching is just a flag, same source either way:

- **AoS pointer list** (the default): one struct per item, plus a small list of pointers so you can look any of them up.
- **AoS, linear**: array-of-structures, one contiguous array holding every item's struct directly, no pointers at all.
- **SoA, linear**: structure-of-arrays, each field gets its own array instead, every item's value for that field sitting together.

Each layout is fastest in a different place. SoA is what 6502 needs (it has no hardware multiply) and what an ECS-style engine wants generally, since a system updates one component at a time across many entities. Linear AoS gives the most direct access wherever a multiply is cheap, like modern PC and console hardware.

[`docs/data-layouts.md`](docs/data-layouts.md) walks through all three side by side, with real code for each.

## Templates you copy, not classes you extend

Reuse in GDDL isn't inheritance, `define`s never inherit from each other, deliberately, so a struct's full field list is always visible in one place, not scattered across parent definitions. What you get instead is compile-time copying: build a base instance once, then copy and adjust it as many times as you need, with real arithmetic on the way.

```gddl
define Creature
	hitpoints = i32

Creature BaseCreature delete
	hitpoints = 100

Creature Human_Fighter = BaseCreature
	hitpoints * 2
	hitpoints + 5
```

`delete` marks `BaseCreature` as a template: it compiles, but it's never exported on its own, only usable as something to copy. `Human_Fighter` copies it, then runs its own statements against that copy, in order: `100 * 2 + 5 = 205`.

```cpp
const Creature Human_Fighter = { 205 };
```

The math happens once, at compile time. `Human_Fighter` doesn't carry `BaseCreature`'s formula around at runtime, it's already just `205`.

[`docs/templates-guide.md`](docs/templates-guide.md) covers multi-generation template chains, referencing other fields in the same expression, and the full set of operators available.

## Jump tables from data

A roguelike's attacks can live in an identifier domain, with each enemy just naming which one it uses:

```gddl
identifier AttackType u8
	slash = "A melee slashing attack"
	stab = "A melee piercing attack"

define Enemy
	attack = AttackType

Enemy Goblin
	attack = AttackType.slash
```

On PC, that domain compiles to a real enum, each value a genuine 64-bit hash of its own description:

```cpp
enum class AttackType : uint64_t
{
    slash = 0x53dfb22ff04e626dULL,
    stab = 0xbd6b7396f60a93e5ULL,
};
```

That's a real key you can dispatch on directly, an `unordered_map<AttackType, ...>` from value to handler function is all it takes:

```cpp
std::unordered_map<AttackType, void(*)(Enemy&)> handlers = {
    { AttackType::slash, DoSlash },
    { AttackType::stab, DoStab },
};

handlers[goblin.attack](goblin);
```

New to `identifier` blocks or this `@`/64-bit-ID syntax? [`docs/language-basics.md`](docs/language-basics.md) covers the fundamentals on their own, outside any specific example.

Because the ID comes from the text itself rather than a shared counter, a mod can add `AttackType.fireball` for some new enemy without ever touching the base game's own domain, more on exactly why below.

On 6502, where checking a 64-bit hash on every single attack would be far too slow, the identical domain compiles into something else entirely: a dense, declaration-order jump table, real assembly, no hashing anywhere:

```asm
; --- domain: AttackType (indexed form, width u8) ---
AttackType_slash = 0
AttackType_stab = 1

AttackType_JumpTable_Lo:
	!byte <AttackType_slash_Handler
	!byte <AttackType_stab_Handler
AttackType_JumpTable_Hi:
	!byte >AttackType_slash_Handler
	!byte >AttackType_stab_Handler

AttackType_DispatchPtr = $04

AttackType_Dispatch:
	LDA AttackType_JumpTable_Lo,X
	STA AttackType_DispatchPtr
	LDA AttackType_JumpTable_Hi,X
	STA AttackType_DispatchPtr+1
	JMP (AttackType_DispatchPtr)
```

Load the table entry for whichever attack was picked, jump straight to it. No comparisons, no hashing, no lookup loop.

[`docs/dispatch-guide.md`](docs/dispatch-guide.md) walks through this example end to end, including the real, assembled-and-executed version of the code above.

## Mods without a coordinator

Most moddable games need some way to hand out unique IDs by hand: the base game claims a range, each mod claims another, and everyone has to coordinate in advance to avoid collisions.

Say a mod wants to add its own attack. It writes its own, completely separate `.gddl` file:

```gddl
identifier AttackType u8
	fireball = "A fire-based ranged attack"
```

Compiled entirely on its own, with no access to the base game's source, that gets a real hash of its own:

```cpp
enum class AttackType : uint64_t
{
    fireball = 0x9a8624540909f0f7ULL,
};
```

Nowhere near `slash`'s `0x53dfb22ff04e626d` or `stab`'s `0xbd6b7396f60a93e5` from above, and realistically never will be: the ID comes from hashing the mod's own description text, not a shared counter, so two mods built by people who've never even heard of each other end up with different IDs without either one reserving anything in advance.

What that doesn't cover on its own is whether a mod's data still matches what the game actually expects. Your game can check, at load time, whether a mod's data matches the schema it was built against, so an out-of-date or incompatible mod fails to load cleanly instead of corrupting something.

## Built and validated for real

Every 6502, Z80, and 68000 export path is checked against real assemblers and real emulators, not just generated and assumed correct.

Bad data, an out-of-range number, an over-length string, two things claiming the same ID, is a compile error, never a silent bug you find later.

## Repository layout

| Path | What it is |
|---|---|
| [`SPEC.md`](SPEC.md) | The language specification. Read this for anything about what GDDL supports. |
| [`docs/`](docs/) | Practical guides for actually using GDDL. |
| [`examples/`](examples/) | Working example projects, once there are some worth pointing at. |
| [`compiler-python/`](compiler-python/) | The reference implementation. This is what actually runs when you compile a `.gddl` file, per `docs/getting-started.md`. |
| [`compiler-cpp/`](compiler-cpp/) | An embeddable C++ implementation of the compiler, for projects that want to compile `.gddl` files as part of their own build. Not started yet. |

## Status

Actively developed. C++, 6502 (ACME, KickAssembler, 64tass), Z80 (SjASMPlus, z88dk), and 68000 (C89 via vbcc, Amiga and Atari ST) export are complete and validated against real toolchains, each with its own command-line tool. The standalone binary export format is complete too, including the compile-time check a game uses to confirm loaded data actually matches its own schema. Compiling several `.gddl` files together, so definitions and instances can live in separate files, is also done.

**Python compiler (`compiler-python/`): v0.9.** Run any exporter with `--version` to confirm.

**C++ compiler (`compiler-cpp/`): v0.0, not started.**

## License

See [`LICENSE`](LICENSE).
