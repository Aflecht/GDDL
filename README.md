# GDDL: Game Data Definition Language

GDDL lets you define your game's structured data once: item stats, character definitions, ability tables, loot tables, anything with a fixed shape you'd otherwise hand-write as a struct or a spreadsheet. You compile it into whatever your game actually needs: real C++ structs, retro 6502/Z80/68000 assembly or C, or a portable binary file your game loads at runtime.

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

That's your item list, ready to use in your game. The same source, unchanged, can also produce 6502 or Z80 assembly with the same three items laid out as a dense, zero-overhead table, or a standalone binary file your game can load, hot-reload, or mod at runtime.

Every export also comes in two layouts: one struct per item (what's shown above), or one flat array per field, all items' `power` values sitting together in memory. The second layout, called SoA, is what you want on 6502 specifically, since it avoids a multiply the chip doesn't have in hardware, and it's also the layout an ECS-style engine wants, since a system updating one component type across many entities is exactly the access pattern SoA is built for. Same source, same command, just a flag.

Every 6502, Z80, and 68000 export path was built and tested against real assemblers and real emulators, not just generated and assumed correct. Bad data (an out-of-range number, an over-length string, two things claiming the same ID) is a compile error, never a silent bug you find later.

### Mods without a coordinator

Most games that support mods need some way to hand out unique IDs: the base game claims a range, mod A claims another, and everyone has to agree in advance who owns what. Get that wrong and two mods pick the same ID, and one of them silently breaks.

GDDL sidesteps this. Every item's ID is computed by hashing its own name, not assigned from a shared counter. Two mods built by people who have never talked to each other, each adding their own new items, will end up with different IDs almost certainly, without either author reserving anything or registering with anyone first. Your game can also check, at load time, whether a mod's data actually matches the schema it was built against, so a mismatched or out-of-date mod fails to load cleanly instead of corrupting something. This is what makes GDDL's standalone binary export genuinely usable for real mod support, not just data storage.

## Repository layout

| Path | What it is |
|---|---|
| [`SPEC.md`](SPEC.md) | The language specification. Read this for anything about what GDDL supports. |
| [`docs/`](docs/) | Practical guides for actually using GDDL. |
| [`examples/`](examples/) | Working example projects, once there are some worth pointing at. |
| [`compiler-python/`](compiler-python/) | The reference implementation. This is what actually runs when you compile a `.gddl` file, per `docs/getting-started.md`. |
| [`compiler-cpp/`](compiler-cpp/) | An embeddable C++ implementation of the compiler, for projects that want to compile `.gddl` files as part of their own build. Not started yet. |

## Status

Actively developed. C++, 6502 (ACME, KickAssembler, 64tass), Z80 (SjASMPlus, z88dk), and 68000 (Amiga, Atari ST) export are complete and validated against real toolchains, each with its own command-line tool. The standalone binary export format is complete too, including the compile-time check a game uses to confirm loaded data actually matches its own schema. Compiling several `.gddl` files together, so definitions and instances can live in separate files, is also done.

**Python compiler (`compiler-python/`): v0.9.** Run any exporter with `--version` to confirm.

**C++ compiler (`compiler-cpp/`): v0.0, not started.**

## License

See [`LICENSE`](LICENSE).
