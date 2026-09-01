// Real MSVC compile/link/run validation for the pools feature, SoA mode --
// stage 4's "real compiled/run output" requirement. See
// export_test_pools.gddl for the fixture and corpus/pools/ for the
// phase 1-8 golden-locked coverage.

#include "generated_pools_soa.h"
#include <cstdio>
#include <cstring>

int main() {
    using namespace GDDL;
    using namespace GDDL::ActiveEnemies_SoA;

    // Column arrays sized by pool count (8), the string column flattened
    // to a single contiguous count*width char array (128 = 8 * 16), not
    // an array of 8 separately-typed 16-char arrays -- matching how a
    // named instance's own SoA string column is laid out.
    static_assert(sizeof(hp) / sizeof(hp[0]) == 8);
    static_assert(sizeof(position_x) / sizeof(position_x[0]) == 8);
    static_assert(sizeof(name) == 128);

    // Write row 2's columns, the way the game would when spawning an
    // entity into slot 2 of this pool.
    hp[2] = 99;
    damage_min_max[2][0] = 7;
    damage_min_max[2][1] = 8;
    std::strcpy(name + 2 * 16, "Row2");
    position_x[2] = 1;
    position_y[2] = 2;

    if (hp[2] != 99) {
        std::printf("FAIL hp readback\n");
        return 1;
    }
    if (damage_min_max[2][0] != 7 || damage_min_max[2][1] != 8) {
        std::printf("FAIL damage_min_max readback\n");
        return 1;
    }
    if (std::strcmp(name + 2 * 16, "Row2") != 0) {
        std::printf("FAIL name readback\n");
        return 1;
    }
    if (position_x[2] != 1 || position_y[2] != 2) {
        std::printf("FAIL nested struct field (position_x/position_y column split) readback\n");
        return 1;
    }

    // A different row never written stays whatever it was -- just
    // confirmed it's a real, distinct column slot by writing a different
    // value there too and checking both hold independently.
    hp[0] = 5;
    if (hp[0] != 5 || hp[2] != 99) {
        std::printf("FAIL independent row storage\n");
        return 1;
    }

    // A pool contributes no named instance at all, in SoA mode either.
    if (Enemy_SoA_Registry::Table.size() != 0 || Vec2_SoA_Registry::Table.size() != 0) {
        std::printf("FAIL pool wrongly registered as a named instance\n");
        return 1;
    }

    std::printf("All C++ pools SoA (column write/read, nested struct field "
                "split, flattened string column, empty registries) checks "
                "passed.\n");
    return 0;
}
