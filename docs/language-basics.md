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
line 5: field 'attack' in 'Enemy' uses '@AttackType', but domain 'AttackType' declared no indexed width -- '@' requires the domain to opt into an indexed form at its own declaration (e.g. 'identifier AttackType u8'), §8.3
```

And a domain simply having more members than its declared width can address, checked the moment the domain itself is registered, whether or not anything uses `@` on it yet:

```
line 1: identifier domain 'BigDomain' declares indexed width 'u8' (max 256 entries), but has 257 members -- exceeds what this width can address (§8.3)
```

## Flags: combinable bits

An `identifier` domain picks exactly one value at a time. Sometimes you want several things true at once, an entity that's both damageable and movable, say, without writing out every possible combination as its own value. That's what `flags` is for: a fixed set of named bits in one integer, combined with the usual bitwise operators.

```gddl
flags ComponentFlags u64
	none            = 0
	is_damageable   = b0
	is_pickupable
	is_movable
	is_controllable

define Entity
	component_flags = ComponentFlags

Entity Player
	component_flags = ComponentFlags.is_movable | ComponentFlags.is_controllable
```

`flags Name WidthType` is required to declare a width, `u8`, `u16`, `u32`, or `u64`, there's no width-less form the way `identifier` has one. Each member takes one of three shapes:

- Leave the value off entirely, and it's handed the next bit nobody else has claimed yet, in declaration order. `is_pickupable`, `is_movable`, and `is_controllable` above get bits 1, 2, and 3 this way.
- `= bN` claims bit `N` explicitly. `bN` is a real integer literal, `1 << N`, so `is_damageable = b0` above means bit 0, the value `1`.
- `= 0` is the zero/none sentinel, and doesn't claim a bit at all.

`bN` isn't limited to `flags` declarations, it's a general integer literal, legal anywhere a number is:

```gddl
Entity DirectBits
	component_flags = b1 | b3
```

The field itself is just the raw width type, `uint64_t` here, not a named or wrapped type the way an `identifier` domain gets an `enum class`. Each member becomes a real, combinable constant:

```cpp
namespace ComponentFlags
{
    constexpr uint64_t none            = 0;
    constexpr uint64_t is_damageable   = 1ULL << 0;
    constexpr uint64_t is_pickupable   = 1ULL << 1;
    constexpr uint64_t is_movable      = 1ULL << 2;
    constexpr uint64_t is_controllable = 1ULL << 3;
}

struct Entity
{
    uint64_t component_flags;
};
```

```cpp
const Entity Player = { 12ULL };
```

`12` is `is_movable | is_controllable`, `4 | 8`. A plain `namespace` of `constexpr` values, not an `enum class`, so `Player.component_flags & ComponentFlags::is_movable` and every other bitwise operator work directly, with real scoping between domains just like `enum class` gives, but without inheriting its complete lack of built-in operators.

Op-statements work here too, the field's current value is the implicit left operand, same as anywhere else. Copy a base instance, then turn one bit off:

```gddl
Entity Base delete
	component_flags = ComponentFlags.none

Entity Stunned = Player
	component_flags & ~ComponentFlags.is_controllable
```

```cpp
const Entity Stunned = { 4ULL };
```

`12 & ~8` clears the controllable bit, leaving just `is_movable`.

Combining bits only ever uses the bitwise operators, `|`, `&`, `^`, `~`. Arithmetic is rejected outright on a flags-typed field, not just discouraged, since `flag + flag` isn't idempotent the way `flag | flag` is, a real, sharp footgun:

```gddl
Entity Bad = Base
	component_flags + 1
```

```
Bad: ERROR - line 24: arithmetic operator '+' used on a flags-typed field -- arithmetic is a compile-time error on flags-typed fields, no exceptions; combine flags with bitwise operators (| & ^ ~) only
```

The same rule runs in the other direction too: bitwise operators are a compile-time error on any field that isn't flags-typed. There's no other bitmask mechanism in the language, so `|`, `&`, `^`, `~` exist only for `flags`, full stop.

Each bit position can only be claimed once, whether it got there explicitly or automatically, checked the moment the domain is registered:

```gddl
flags Broken u8
	none            = 0
	is_damageable   = b2
	is_pickupable   = b2
```

```
line 4: flags member 'is_pickupable' claims bit 2 ('= b2'), but 'is_damageable' (line 3) already claims the same bit in domain 'Broken' -- each bit position must be claimed exactly once
```

Auto-assignment accounts for every explicit claim in the whole domain, not just ones declared earlier in the file, so reordering members around an explicit `bN` never causes a collision. And, matching `identifier`'s own width check, a domain whose real bit-flag members outnumber what its declared width can address is caught the same way, at registration.

## Arrays: fixed-size sequences

A field can be a fixed-size sequence of values instead of a single one, a min/max pair, a small grid, a handful of names, declared with `: dimN` after the element type:

```gddl
define Enemy
	damage_min_max = i32 : 2

Enemy Goblin
	damage_min_max = 10, 30
```

```cpp
struct Enemy
{
    std::array<int32_t, 2> damage_min_max;
};

const Enemy Goblin = { { 10, 30 } };
```

The outermost `{ }` around a value is always optional, `damage_min_max = { 10, 30 }` means exactly the same thing as the line above. For more than one dimension, that same outermost layer stays optional, but every level from there inward needs its own braces to say where one group ends and the next begins:

```gddl
define Grid
	cells = i32 : 2 : 3

Grid Level1
	cells = { 1, 2, 3 }, { 4, 5, 6 }
```

```cpp
struct Grid
{
    std::array<std::array<int32_t, 3>, 2> cells;
};

const Grid Level1 = { {{ { 1, 2, 3 }, { 4, 5, 6 } }} };
```

Two outer groups of three, dimensions read left to right the same way the value's own braces nest, outermost to innermost. A third dimension would just nest one layer deeper on both sides.

`string N`'s own width composes with the array syntax the same way any other element type does:

```gddl
define Party
	names = string 16 : 3

Party Heroes
	names = "Alice", "Bob", "Carol"
```

```cpp
struct Party
{
    std::array<std::array<char, 16>, 3> names;
};

const Party Heroes = { {{ { "Alice" }, { "Bob" }, { "Carol" } }} };
```

Array elements are scalars or strings only, for now, struct-typed and identifier-typed elements are explicitly deferred to a later pass:

```gddl
identifier ActionAttack
	melee_weapon = "Standard melee attack"

define Enemy
	actions = ActionAttack : 2
```

```
line 5: field 'actions' in 'Enemy' declares an array of identifier domain 'ActionAttack' -- identifier-typed array elements are not yet supported (first-pass scope is scalar and string elements only)
```

An element inside the value itself can be an expression, not just a bare literal, cross-field references and arithmetic both work exactly as they do anywhere else:

```gddl
define Enemy
	base_power = i32
	powers = i32 : 2

Enemy Goblin
	base_power = 100
	powers = base_power, base_power + 5
```

`powers` resolves to `[100, 105]`.

### Reading and changing one element

Square brackets reach into a specific element, for both a plain assign and an op-statement, the same "current value is the implicit left operand" rule every op-statement already has, applied per element instead of per field. The motivating case is copy-then-adjust: a derived instance copies a base's array, then tweaks just one entry:

```gddl
define Enemy
	damage_min_max = i32 : 2

Enemy BaseGoblin
	damage_min_max = 10, 30

Enemy StrongerGoblin = BaseGoblin
	damage_min_max[1] + 50
```

```cpp
const Enemy BaseGoblin = { { 10, 30 } };
const Enemy StrongerGoblin = { { 10, 80 } };
```

Only index 1 changed, `30 + 50`, index 0 carried over untouched. Bracket indexing needs the array to already hold a full value first, from a literal earlier in the same instance, or copied in from a source instance, the same way an op-statement on any other field needs a current value to read before it can modify it.

Bracket indexing is one-dimensional only for now. A 2D or deeper array still assigns fine as a whole with a literal, just not element by element:

```gddl
define Grid
	cells = i32 : 2 : 3

Grid Level1
	cells = { 1, 2, 3 }, { 4, 5, 6 }
	cells[0] = 99
```

```
Level1: ERROR - line 6: 'cells[0]': bracket indexing is only supported for one-dimensional arrays in this pass -- 'cells' has 2 dimensions; assign the full array with a literal instead
```

## Pools: reserved, uninitialized storage

Everything up to this point describes fully-resolved, compile-time data, every field has a real value before it ever reaches your game. A `pool` is the opposite: a fixed-size block of instances with no values at all, reserved at compile time and filled in by your game at runtime. Think an entity pool, a fixed-size table of active projectiles, anything your own game code manages the contents of rather than GDDL.

```gddl
define Enemy
	hp = i32
	damage_min_max = i32 : 2

pool Enemy ActiveEnemies : 8
```

```cpp
struct Enemy
{
    int32_t                hp;
    std::array<int32_t, 2> damage_min_max;
};

inline Enemy ActiveEnemies[8];
```

`pool TypeName PoolName : N` is a top-level declaration on its own, with no indented body underneath it, there's nothing to initialize:

```gddl
define Enemy
	hp = i32

pool Enemy ActiveEnemies : 8
	hp = 5
```

```
line 4: 'pool Enemy ActiveEnemies : 8' cannot have an indented body -- pool slots are always uninitialized, filled in by the game at runtime, never by the compiler
```

`TypeName` has to be a real `define`, and `N` has to be a positive count, both checked the moment the pool is registered:

```
line 4: pool 'ActiveGhosts' references type 'Ghost', but no such define exists
```

```
line 4: pool 'ActiveEnemies' declares a count of 0 -- a pool must reserve at least one slot
```

A pool has no name-based or ID-based lookup of any kind, no `Registry`, no `Find()`, unlike a `define`'s own named instances. There's no identity to look up, your game addresses a slot by plain index, `0` through `N - 1`, and owns whatever bookkeeping (which slots are actually in use, say) it needs on top of that. Any field type is fine inside the pooled `define`, struct-typed, identifier-typed, `string N`, arrays, the same as an ordinary instance, since a pool never computes or checks a value, only reserves shape-sized space.

Unlike a named instance's storage, which is `const`, a pool's storage is always mutable, `inline Enemy ActiveEnemies[8];` here, never `inline constexpr`. The entire point is your own code writing into it while the game runs.
