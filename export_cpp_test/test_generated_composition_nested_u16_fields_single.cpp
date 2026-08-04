// Real g++17 compile/link/run validation for composition_nested_u16_fields.gddl
// on the C++ export target -- closing a genuine gap, not a formality: this
// project's existing C++ fixtures cover composition (Item nests Object) and
// u16-as-identifier-domain-width, but NEVER a plain scalar u16 field sitting
// inside a composed type. This is exactly that combination.
//
// Values (60000, 12000, 500) are all well above 255 specifically so a
// truncation-to-8-bit bug, or any byte-order mishandling, would produce an
// observably wrong result rather than coincidentally passing.

#include "generated_composition_nested_u16_fields_single.h"
#include <cassert>
#include <cstdio>

int main() {
    // Compile-time checks: nested struct fields are directly accessible
    // and hold the exact 16-bit values, not truncated or reordered.
    static_assert(GDDL::Character_Instances::Hero.stats.hp == 60000);
    static_assert(GDDL::Character_Instances::Hero.stats.mp == 12000);
    static_assert(GDDL::Character_Instances::Hero.equipment.weapon_power == 500);
    static_assert(GDDL::Character_Instances::Hero.level == 42);

    // sizeof sanity: uint16_t fields should occupy exactly 2 bytes each,
    // not be silently widened or narrowed by the generated struct layout.
    static_assert(sizeof(GDDL::Character_Instances::Hero.stats.hp) == 2);
    static_assert(sizeof(GDDL::Character_Instances::Hero.level) == 2);

    // Runtime checks via the registry, not just compile-time constants --
    // confirms the same values round-trip through a real Find() call, not
    // just through the constexpr-friendly direct-access path.
    const GDDL::Character* found = GDDL::Character_Registry::Find(std::string_view("Hero"));
    assert(found != nullptr);
    assert(found->stats.hp == 60000);
    assert(found->stats.mp == 12000);
    assert(found->equipment.weapon_power == 500);
    assert(found->level == 42);

    std::printf("hp=%u mp=%u weapon_power=%u level=%u\n",
                found->stats.hp, found->stats.mp,
                found->equipment.weapon_power, found->level);
    std::printf("All C++ composition+u16 checks passed.\n");
    return 0;
}
