# Data Layouts

GDDL's C++ exporter can produce the same source in one of three concrete layouts, chosen with a single `--layout` flag. This page walks through all three side by side, using the same example throughout, so you can see exactly what changes and what stays the same.

C++ is currently the only target with all three. 6502, Z80, and 68000 each support a subset, for reasons specific to each chip; [`SPEC.md`](../SPEC.md) §13.7 has the full cross-platform picture. This page is just about what you get on PC.

## The example used on this page

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

## AoS pointer list (`--layout=aos`, the default)

```
python3 export_cpp.py items.gddl -o items_output
```

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

namespace Item_Registry
{
    struct Entry
    {
        uint64_t instance_id;
        std::string_view name;
        const Item* data;
    };

    extern const std::array<Entry, 3> Table;

    const Item* Find(uint64_t instance_id);

    const Item* Find(std::string_view name);
} // namespace Item_Registry
```

Every instance is its own separately-declared global. There's no guarantee the compiler places `Sword`, `Bow`, and `Shield` next to each other in memory, and nothing here depends on it. `Item_Registry::Table` is a real, contiguous array, but what it holds is small lookup records, each one a hash, a name, and a pointer to where the actual data lives.

You get three ways to reach an item:

```cpp
// by name, straight from the source:
GDDL::Item_Instances::Sword.power;

// by name, at runtime:
const GDDL::Item* sword = GDDL::Item_Registry::Find("Sword");
sword->power;

// walking everything:
for (const auto& entry : GDDL::Item_Registry::Table)
    entry.data->power;
```

This is the layout to reach for by default. Writing `Item_Instances::Sword` directly in your own code is the most convenient thing here, and nothing about it changes if you add a hundred more items later.

## AoS, linear (`--layout=aos-linear`)

```
python3 export_cpp.py items.gddl --layout aos-linear -o items_output
```

```cpp
struct Item
{
    uint16_t power;
};

namespace Item_Instances
{
    extern const std::array<Item, 3> All;

    inline constexpr std::size_t Sword_Index = 0;
    inline constexpr std::size_t Bow_Index = 1;
    inline constexpr std::size_t Shield_Index = 2;
}

namespace Item_Registry
{
    struct Entry
    {
        uint64_t instance_id;
        std::string_view name;
        std::size_t index;
    };

    extern const std::array<Entry, 3> Table;

    const Item* Find(uint64_t instance_id);

    const Item* Find(std::string_view name);
} // namespace Item_Registry
```

The difference is right there in `Item_Instances`: instead of three separate globals, there's one real `std::array<Item, 3>` holding the actual structs directly. This is genuine, physical contiguity, not something that happens to be true on one compiler, you can check it yourself:

```cpp
(const char*)&Item_Instances::All[1] - (const char*)&Item_Instances::All[0]
// == sizeof(Item), always, guaranteed by std::array itself
```

`Find()` still returns `const Item*`, exactly like the default layout, it's just computed as `&All[i]` instead of following a stored pointer. That means code written against the default layout's `Find()` calls doesn't need to change at all if you switch to this one:

```cpp
const GDDL::Item* sword = GDDL::Item_Registry::Find("Sword");  // same call, either layout
sword->power;

// or index directly, no lookup at all:
GDDL::Item_Instances::All[GDDL::Item_Instances::Sword_Index].power;

for (const auto& item : GDDL::Item_Instances::All)
    item.power;
```

Reach for this one when you specifically need contiguous memory: handing a pointer and count off to another system, crossing an API boundary, serializing the whole block at once.

The tradeoff is losing named access. `Item_Instances::Sword` doesn't exist in this layout; you go through `Find()` or the index constants instead.

## SoA, linear (`--layout=soa`)

```
python3 export_cpp.py items.gddl --layout soa -o items_output
```

```cpp
namespace Item_SoA
{
    extern const std::array<uint16_t, 3> power;
}

namespace Item_SoA_Registry
{
    struct Entry
    {
        uint64_t instance_id;
        std::string_view name;
        std::size_t row;
    };

    extern const std::array<Entry, 3> Table;

    std::size_t Find(uint64_t instance_id);

    std::size_t Find(std::string_view name);
} // namespace Item_SoA_Registry
```

This one looks the least like the other two, because it's solving a different problem. There's no `Item` struct at all here, every field gets its own flat array (`power`, and one more per field if `Item` had more), with each item's values living at the same index across every one of those arrays. `Find()` can't return a pointer anymore, there's no single struct to point at, so it returns a row index instead, or `static_cast<std::size_t>(-1)` if nothing matched, the same sentinel `std::string::npos` uses, and just as loud if you forget to check it before indexing with it:

```cpp
std::size_t row = GDDL::Item_SoA_Registry::Find("Sword");
GDDL::Item_SoA::power[row];  // 42

// iterate one field across every item:
for (std::size_t i = 0; i < GDDL::Item_SoA::power.size(); ++i)
    GDDL::Item_SoA::power[i];
```

This is the layout an ECS-style engine wants: a system that updates one component across many entities is reading exactly one of these arrays, start to finish, with nothing else in between. It's also what 6502 needs for a completely different reason, no hardware multiply, so indexing has to stay cheap, but that's a retro concern; on PC the reason to reach for this is the access pattern, not the arithmetic.

## Choosing between them

| | Contiguous? | Named access | `Find()` returns |
|---|---|---|---|
| **AoS pointer list** (default) | No | `Item_Instances::Sword` | pointer |
| **AoS, linear** | Yes | index constants only | pointer |
| **SoA, linear** | Yes, per field | index constants only | row index |

If you're not sure, start with the default. Reach for linear AoS when contiguity itself is the requirement. Reach for SoA when you're iterating one field across many instances far more often than you're reading a whole instance at once.
