// C++17 real compile+run test for --emit-all-domains.
// Uses --force-single-header mode (inline constexpr, static_assert-able)
// specifically because it gives the clearest possible signal: if
// Rarity_Indexed is missing, the reference below is a hard compile error
// rather than a runtime failure.
//
// The flag-OFF case cannot be tested in the same compile unit (the type
// wouldn't exist to reference), so flag-OFF is verified via a separate
// compile of the OFF header as a syntax check with no reference to
// Rarity_Indexed (see test_cpp_emit_all_domains_off.cpp).
//
// Two-target assertion:
//   1. Rarity_Indexed exists and has the right enum values when flag is ON.
//   2. sizeof(Rarity_Indexed) == 1 (u8 width declared in the fixture).

#include "generated_cpp_single_ON.h"
#include <cassert>
#include <cstdio>
#include <type_traits>

int main() {
    // §14.7 / §8.5: the _Indexed companion should exist when
    // --emit-all-domains is on, with 0-based declaration-order values.
    static_assert(static_cast<int>(GDDL::Rarity_Indexed::common) == 0);
    static_assert(static_cast<int>(GDDL::Rarity_Indexed::rare)   == 1);
    static_assert(static_cast<int>(GDDL::Rarity_Indexed::epic)   == 2);
    static_assert(sizeof(GDDL::Rarity_Indexed) == 1,
                  "Rarity declared u8, so _Indexed should be uint8_t (1 byte)");

    std::printf("Rarity_Indexed::common=%d rare=%d epic=%d sizeof=%zu\n",
                static_cast<int>(GDDL::Rarity_Indexed::common),
                static_cast<int>(GDDL::Rarity_Indexed::rare),
                static_cast<int>(GDDL::Rarity_Indexed::epic),
                sizeof(GDDL::Rarity_Indexed));
    std::printf("C++ --emit-all-domains: Rarity_Indexed companion correct (0, 1, 2)\n");
    return 0;
}
