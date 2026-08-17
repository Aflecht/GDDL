// Real MSVC compile/link/run validation for the arrays feature, AoS
// (single-header) mode -- stage 4's "real compiled/run output" requirement.
// See export_test_arrays.gddl for the fixture and corpus/arrays/ for the
// phase 1-8 golden-locked coverage.

#include "generated_arrays.h"
#include <cstdio>
#include <cstring>

int main() {
    using namespace GDDL;
    using namespace GDDL::Enemy_Instances;

    // Compile-time checkable: single-header mode is all inline constexpr.
    static_assert(BaseGoblin.damage_min_max[0] == 10);
    static_assert(BaseGoblin.damage_min_max[1] == 30);
    static_assert(StrongerGoblin.damage_min_max[0] == 10);
    static_assert(StrongerGoblin.damage_min_max[1] == 80);  // bracket-indexed op-statement: 30 + 50

    static_assert(BaseGoblin.grid[0][0] == 1);
    static_assert(BaseGoblin.grid[0][2] == 3);
    static_assert(BaseGoblin.grid[1][0] == 4);
    static_assert(BaseGoblin.grid[1][2] == 6);

    if (std::strcmp(BaseGoblin.names[0].data(), "Alice") != 0) {
        std::printf("FAIL names[0]\n");
        return 1;
    }
    if (std::strcmp(BaseGoblin.names[2].data(), "Carol, Jr.") != 0) {
        std::printf("FAIL names[2] (embedded comma inside a quoted array element)\n");
        return 1;
    }
    if (std::strcmp(BaseGoblin.names[3].data(), "Dave") != 0) {
        std::printf("FAIL names[3]\n");
        return 1;
    }

    // Real runtime lookup through the generated registry, not just direct access.
    const Enemy* found = Enemy_Registry::Find("StrongerGoblin");
    if (found == nullptr) {
        std::printf("FAIL Find by name\n");
        return 1;
    }
    if (found->damage_min_max[1] != 80) {
        std::printf("FAIL Find result value\n");
        return 1;
    }

    // Row-major contiguity, matching the design's own "match how C++ does this" instruction.
    const char* row0 = reinterpret_cast<const char*>(&BaseGoblin.grid[0]);
    const char* row1 = reinterpret_cast<const char*>(&BaseGoblin.grid[1]);
    if (row1 - row0 != 3 * sizeof(int32_t)) {
        std::printf("FAIL row stride\n");
        return 1;
    }

    // Zero padding either side of the struct: record_size (from the SAME
    // computation export_binary.py uses) must equal sizeof(Enemy) exactly.
    if (SchemaTable[0].record_size != sizeof(Enemy)) {
        std::printf("FAIL record_size (%u) != sizeof(Enemy) (%zu)\n",
                    SchemaTable[0].record_size, sizeof(Enemy));
        return 1;
    }

    std::printf("All C++ arrays (1D/2D, string elements, bracket-indexed "
                "op-statement, real Find lookup) checks passed.\n");
    return 0;
}
