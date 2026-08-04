# GDDL — Game Data Definition Language

GDDL is a compile-time data definition language for game development. You describe your game's data — items, characters, dialogue, anything with structure — once, in `.gddl` source files, and GDDL compiles it into your target language: real C++ structs, real 6502/Z80/68000 assembly or C, or a standalone binary file your game loads at runtime.

Every export target is generated from the same compiled, validated representation, so your C++ build and your loadable mod data can never silently drift apart from each other.

## What you probably want, depending on who you are

**Building a modern PC/console game in C++?**
→ [`docs/export-targets/cpp.md`](docs/export-targets/cpp.md) for compiling GDDL data directly into your game.
→ [`docs/export-targets/binary-format.md`](docs/export-targets/binary-format.md) if you also want to load data at runtime — DLC, mods, or just avoiding a full rebuild for every data tweak.
→ [`examples/cpp-load-binary-data/`](examples/cpp-load-binary-data/) for a minimal, working example of the above.

**Building or modding for a retro platform (6502, Z80, 68000)?**
→ [`docs/export-targets/retro/`](docs/export-targets/retro/) covers each target, including the specific assembler/toolchain each one is validated against.

**Want to know what GDDL as a language actually supports** — syntax, types, composition, how identity and modding work?
→ [`SPEC.md`](SPEC.md) is the complete, authoritative reference.

## Quick example

```gddl
identifier ActionAttack u8
    melee_weapon  = "Standard attack done with a melee weapon"
    ranged_weapon = "Standard attack done with a ranged weapon"

define Creature
    hp     = u8
    attack = ActionAttack

Creature Goblin
    hp     = 10
    attack = ActionAttack.melee_weapon
```

Compile that once, and get a real C++ header with your `Creature` struct and `Goblin` instance already populated — or 6502 assembly with the same data laid out as a dense, zero-overhead table — or a standalone binary file your game can load, hot-reload, or mod, all from the exact same source.

## Repository layout

```
SPEC.md                 The language specification. Read this for anything about what GDDL supports.
docs/                    Practical, target-specific guides — how to actually use each export target.
examples/                Minimal, working example projects. Start here if you learn by reading code.
compiler-python/         The reference implementation (Python). This is where GDDL is actually built,
                         if you're contributing to the compiler itself rather than just using it.
compiler-cpp/            An embeddable C++ implementation of the compiler, for projects that want to
                         compile .gddl files as part of their own build — in development.
```

If you're using GDDL to make a game, you almost certainly don't need to open `compiler-python/` at all — it's the compiler's own source, not something your project depends on directly unless you're building GDDL itself from source.

## Status

Actively developed. C++, 6502 (ACME/KickAssembler/64tass), Z80 (SjASMPlus/z88dk), and 68000 export targets are complete and validated against real toolchains. The standalone binary data format (`compiler-python/`'s newest export target) is in progress. `compiler-cpp/`, the embeddable second implementation, hasn't been started yet.

## License

See [`LICENSE`](LICENSE).
