// Real MSVC compile/link/run validation for the arrays feature, SoA mode --
// the one code path stage 3 needed genuinely new logic for beyond folding
// into the existing type/value dispatch: an array-typed SoA column is the
// first case where the OUTER per-field std::array wrapping is itself an
// aggregate (its contained type is another std::array), needing the same
// double-brace treatment a plain std::array<AggregateType, N> always does.

#include "generated_arrays_soa.h"
#include <cstdio>
#include <cstring>

int main() {
    using namespace GDDL;
    using namespace GDDL::Enemy_SoA;

    // row 0 = BaseGoblin, row 1 = StrongerGoblin (per the Table entries in the header).
    static_assert(damage_min_max[0][0] == 10);
    static_assert(damage_min_max[0][1] == 30);
    static_assert(damage_min_max[1][0] == 10);
    static_assert(damage_min_max[1][1] == 80);

    static_assert(grid[0][1][2] == 6);
    static_assert(grid[1][0][0] == 1);

    if (std::strcmp(names[0][2].data(), "Carol, Jr.") != 0) {
        std::printf("FAIL SoA names[0][2]\n");
        return 1;
    }
    if (std::strcmp(names[1][3].data(), "Dave") != 0) {
        std::printf("FAIL SoA names[1][3]\n");
        return 1;
    }

    std::size_t row = Enemy_SoA_Registry::Find("StrongerGoblin");
    if (row == static_cast<std::size_t>(-1)) {
        std::printf("FAIL SoA Find\n");
        return 1;
    }
    if (damage_min_max[row][1] != 80) {
        std::printf("FAIL SoA Find result\n");
        return 1;
    }

    std::printf("All C++ SoA arrays (2D/3D nested std::array double-brace "
                "aggregate wrapping, real Find lookup) checks passed.\n");
    return 0;
}
