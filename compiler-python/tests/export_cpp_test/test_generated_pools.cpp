// Real MSVC compile/link/run validation for the pools feature, AoS
// (single-header) mode -- stage 4's "real compiled/run output"
// requirement. See export_test_pools.gddl for the fixture and
// corpus/pools/ for the phase 1-8 golden-locked coverage.

#include "generated_pools.h"
#include <cstdio>
#include <cstring>

int main() {
    using namespace GDDL;

    // A pool is real, addressable storage: 8 uninitialized Enemy slots,
    // indexed by plain array subscript -- never by name (section 22.2,
    // not identity-bearing). Confirmed at compile time: the array bound
    // itself, not a runtime guess.
    static_assert(sizeof(ActiveEnemies) / sizeof(ActiveEnemies[0]) == 8);

    // Genuinely mutable (plain `inline`, not `inline constexpr` the way
    // named instances are) -- write into a slot at runtime, the way the
    // game itself would when spawning an entity into the pool.
    ActiveEnemies[3].hp = 42;
    ActiveEnemies[3].damage_min_max[0] = 1;
    ActiveEnemies[3].damage_min_max[1] = 2;
    std::strcpy(ActiveEnemies[3].name, "Test");
    ActiveEnemies[3].position.x = 5;
    ActiveEnemies[3].position.y = 6;

    if (ActiveEnemies[3].hp != 42) {
        std::printf("FAIL hp readback\n");
        return 1;
    }
    if (ActiveEnemies[3].damage_min_max[0] != 1 || ActiveEnemies[3].damage_min_max[1] != 2) {
        std::printf("FAIL damage_min_max readback\n");
        return 1;
    }
    if (std::strcmp(ActiveEnemies[3].name, "Test") != 0) {
        std::printf("FAIL name readback\n");
        return 1;
    }
    if (ActiveEnemies[3].position.x != 5 || ActiveEnemies[3].position.y != 6) {
        std::printf("FAIL nested struct position readback\n");
        return 1;
    }

    // A different slot never written stays whatever it was -- not
    // asserted to be any particular value (pools are genuinely
    // uninitialized, section 22.2), just confirmed it's a real, distinct
    // storage location from slot 3 by writing a different value there
    // too and checking both hold independently.
    ActiveEnemies[0].hp = 7;
    if (ActiveEnemies[0].hp != 7 || ActiveEnemies[3].hp != 42) {
        std::printf("FAIL independent slot storage\n");
        return 1;
    }

    // A pool contributes no named instance at all -- both registries
    // stay genuinely empty, confirming section 22.2 end to end against
    // real compiled output, not just the language-level golden fixture.
    if (Enemy_Registry::Table.size() != 0 || Vec2_Registry::Table.size() != 0) {
        std::printf("FAIL pool wrongly registered as a named instance\n");
        return 1;
    }

    // Zero padding either side of the struct: record_size (from the SAME
    // computation export_binary.py uses) must equal sizeof(Enemy)
    // exactly, matching the arrays test's own precedent.
    if (SchemaTable[1].record_size != sizeof(Enemy)) {
        std::printf("FAIL record_size (%u) != sizeof(Enemy) (%zu)\n",
                    SchemaTable[1].record_size, sizeof(Enemy));
        return 1;
    }

    std::printf("All C++ pools (AoS write/read, independent slots, nested "
                "struct field, empty registries) checks passed.\n");
    return 0;
}
