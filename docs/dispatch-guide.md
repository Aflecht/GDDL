# Dispatch: Choosing Code From Data

An identifier domain doesn't just hold data, it can be used to decide which code runs. This page walks through one real scenario end to end: a roguelike where each enemy's attack is picked from an identifier domain, compiled to real, executed code on two very different platforms from the exact same source.

## The scenario

```gddl
identifier AttackType u8
	slash = "A melee slashing attack"
	stab = "A melee piercing attack"

define Enemy
	attack = AttackType

Enemy Goblin
	attack = AttackType.slash

Enemy Skeleton
	attack = AttackType.stab
```

## On PC: a real, working dispatch table

The domain compiles to a real enum, each value a genuine 64-bit hash of its own description.

Right below it in the same header sits `Enemy` itself. Everything needed to work with real enemies is right there too: look one up by name, or walk every enemy that exists.

```cpp
enum class AttackType : uint64_t
{
    slash = 0x53dfb22ff04e626dULL,
    stab = 0xbd6b7396f60a93e5ULL,
};

struct Enemy
{
    AttackType attack;
};

namespace Enemy_Instances
{
    extern const Enemy Goblin;
    extern const Enemy Skeleton;
}

namespace Enemy_Registry
{
    struct Entry
    {
        uint64_t instance_id;
        std::string_view name;
        const Enemy* data;
    };

    extern const std::array<Entry, 2> Table;

    const Enemy* Find(uint64_t instance_id);

    const Enemy* Find(std::string_view name);
} // namespace Enemy_Registry
```

That's everything the header gives you.

Here's what you do with it in your own game code. A complete, working dispatch table, one handler function per attack, called for every enemy in the registry:

```cpp
void DoSlash(std::string_view name) { printf("%.*s slashes!\n", (int)name.size(), name.data()); }
void DoStab(std::string_view name)  { printf("%.*s stabs!\n", (int)name.size(), name.data()); }

std::unordered_map<GDDL::AttackType, void(*)(std::string_view)> handlers =
{
    { GDDL::AttackType::slash, DoSlash },
    { GDDL::AttackType::stab, DoStab },
};

for (const auto& entry : GDDL::Enemy_Registry::Table)
    handlers[entry.data->attack](entry.name);
```

Real compile, real run:

```
Skeleton stabs!
Goblin slashes!
```

(The registry is sorted by ID for binary search, not declaration order, which is why `Skeleton` prints first, nothing to worry about, just not the order you wrote them in.)

### Adding an attack from a mod

The dispatch table above doesn't actually care where an entry comes from. It's just a map from a 64-bit ID to a function pointer. Nothing about it requires either one to be known ahead of time, or to come from the base game at all.

That's what makes loading mods at runtime possible. A mod, whether it's built as a `.dll`, a `.so`, or even a scripting language binding, only needs to hand your own modding system two things when it loads: a GDDL-generated 64-bit ID, and a function pointer for what should run when that ID comes up. Your own loading code adds that pair to the exact same map shown above, at any time, the same way `slash` and `stab` got added when the program started.

The ID itself comes from compiling the mod's own, completely separate `.gddl` file:

```gddl
identifier AttackType u8
	fireball = "A fire-based ranged attack"
```

```cpp
enum class AttackType : uint64_t
{
    fireball = 0x9a8624540909f0f7ULL,
};
```

One detail worth knowing: the mod's compiled output and the base game's compiled output each declare their own `enum class AttackType`, with different members, so a mod can never literally share that C++ type with the game, only the raw number. That's exactly why the map below is keyed on `uint64_t`, not on the enum itself:

```cpp
std::unordered_map<uint64_t, void(*)()> handlers =
{
    { 0x53dfb22ff04e626dULL, DoSlash },    // AttackType::slash
    { 0xbd6b7396f60a93e5ULL, DoStab },     // AttackType::stab
};

// the mod hands over its own ID and its own function, added to the
// map exactly like the two built-in attacks above:
handlers[0x9a8624540909f0f7ULL] = DoFireball; // AttackType::fireball

handlers[0x53dfb22ff04e626dULL]();
handlers[0xbd6b7396f60a93e5ULL]();
handlers[0x9a8624540909f0f7ULL]();
```

Real run, the base game's own two attacks and the mod's new one, all reachable through the same map:

```
slash!
stab!
fireball!
```

## On 6502: no hash in sight

The identical domain, same source, compiles into something with nothing in common with the C++ version:

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

No hash, because 6502 can't afford to compare one at runtime. Instead, `slash` and `stab` are just `0` and `1`, plain indices into a lo/hi pointer table. Put a value in X, call `AttackType_Dispatch`, it jumps straight to the matching handler, nothing to search, nothing to compare.

This was assembled with real ACME and run on a real 6502 emulator, not just generated and assumed correct. Each handler writes a distinct marker byte so the result is actually checkable afterward, not just "it didn't crash":

```asm
AttackType_slash_Handler:
	LDA #$AA
	STA LastAttackMarker
	RTS

AttackType_stab_Handler:
	LDA #$BB
	STA LastAttackMarker
	RTS
```

Running Goblin's attack through `AttackType_Dispatch` and reading the marker back:

```
GoblinResult:   $aa (expect $aa, slash handler)
SkeletonResult: $bb (expect $bb, stab handler)
Confirmed: each enemy's attack dispatched to the correct handler.
```

Goblin's `slash` reached the slash handler. Skeleton's `stab` reached the stab handler. Same source as the C++ example above, a completely different mechanism, the correct result either way.

## What about Z80 and 68000?

Z80 has the identical jump-table mechanism as 6502, its own `AttackType_Dispatch`/`AttackType_JumpTable`, same shape, same reasoning, already validated with real SjASMPlus assembly and real execution earlier in this project's development, not independently re-run for this specific page.

68000 doesn't generate a dispatch mechanism at all. Identifier domains compile to plain `#define` constants there, since 68000's C target doesn't need GDDL to build a jump table for it, a hand-written `switch` or function-pointer array using those constants does the same job in ordinary C.
