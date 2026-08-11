# Language Basics

The other docs jump straight into layouts, dispatch, and templates. This page is the syntax underneath all of them: comments, the actual data types a field can hold, and how identifier domains work.

## Comments

`//` starts a comment that runs to the end of the line.

`/* */` starts a comment that runs until its own closing `*/`, and can nest inside itself.

```gddl
define Item
	power = u16  // how much damage this item deals

/* A basic starter weapon,
   nothing special about it */
Item Sword
	power = 42   /* nested /* comment */ still closes correctly */
```

Both are quote-aware, `//` or `/*` sitting inside an actual string literal is just text, never treated as the start of a comment:

```gddl
define Item
	description = string 30

Item Sword
	description = "A blade // not a comment"
```

```cpp
const Item Sword = { "A blade // not a comment" };
```

## Data types

Every field has exactly one of these:

- **Eight integer types**, `u8`, `u16`, `u32`, `u64` (unsigned) and `i8`, `i16`, `i32`, `i64` (signed), each with the range its name implies (`u8` is `0..255`, `i16` is `-32768..32767`, and so on).
- **Two floating-point types**, `f32` and `f64`.
- **`string N`**, a fixed-length string, `N` bytes.
- **An identifier domain**, a field typed as one of your own `identifier` blocks (more below).
- **Another `define`**, composing one type inside another.

```gddl
identifier Rarity u8
	common = "Common item"
	rare = "Rare item"

define Stats
	strength = i32

define Item
	small_count = u8
	item_id = u64
	temperature = i16
	price = f32
	weight = f64
	name = string 16
	rarity = Rarity
	stats = Stats
```

Every one of those maps to a real, ordinary C++ type:

```cpp
struct Item
{
    uint8_t small_count;
    uint64_t item_id;
    int16_t temperature;
    float price;
    double weight;
    char name[16];
    Rarity rarity;
    Stats stats;
};
```

## Identifier domains and the `@` prefix

An `identifier` block is its own type, a fixed set of named values:

```gddl
identifier AttackType u8
	slash = "A melee slashing attack"
	stab = "A melee piercing attack"
```

Each value here, `slash`, `stab`, is normally stored as a 64-bit number, computed from the description text you write after the `=`. That number, unique and guaranteed not to clash with anything from anywhere else, is what actually ends up in your exported data by default.

If you'd rather have a simple index list instead, just `0`, `1`, `2`, in the order you wrote them, add `@` in front of the domain name on a field's type. Doing that also means the domain itself has to declare how big those numbers need to be, that's what the `u8` right after `identifier AttackType` above is for:

```gddl
identifier AttackType u8   // declares an 8-bit index form alongside the default
	slash = "A melee slashing attack"
	stab = "A melee piercing attack"

define Enemy
	primary_attack = AttackType    // uses the regular 64-bit generated number
	backup_attack = @AttackType    // uses the u8 index form instead

Enemy Goblin
	primary_attack = AttackType.slash
	backup_attack = AttackType.stab
```

The `@` only ever goes on the field's type, in the `define`. Assigning a value is always just `AttackType.stab`, whichever form the field chose. Both forms show up in the generated header, since something actually used each one:

```cpp
enum class AttackType : uint64_t
{
    slash = 0x53dfb22ff04e626dULL,
    stab = 0xbd6b7396f60a93e5ULL,
};

enum class AttackType_Indexed : uint8_t
{
    slash = 0,
    stab = 1,
};

struct Enemy
{
    AttackType primary_attack;
    AttackType_Indexed backup_attack;
};
```

```cpp
const Enemy Goblin = { AttackType::slash, AttackType_Indexed::stab };
```

The default, large-number form is what the README's [Jump tables from data](../README.md#jump-tables-from-data) section builds on, seeing it used for something real might help if any of this still feels abstract.

Two things about widths are checked at compile time. Using `@Domain` when `Domain` never declared a width at all:

```gddl
identifier AttackType
	slash = "A melee slashing attack"

define Enemy
	attack = @AttackType
```

```
[phase 4, indexed_no_width] line 5: field 'attack' in 'Enemy' uses '@AttackType', but domain 'AttackType' declared no indexed width -- '@' requires the domain to opt into an indexed form at its own declaration (e.g. 'identifier AttackType u8'), §8.3
```

And a domain simply having more members than its declared width can address, checked the moment the domain itself is registered, whether or not anything uses `@` on it yet:

```
[phase 4, indexed_width_overflow] line 1: identifier domain 'BigDomain' declares indexed width 'u8' (max 256 entries), but has 257 members -- exceeds what this width can address (§8.3)
```
