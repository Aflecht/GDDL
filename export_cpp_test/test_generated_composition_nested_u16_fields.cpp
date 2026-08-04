// Real g++17 compile/link/run validation for composition_nested_u16_fields.gddl
// on the C++ export target -- closing a genuine gap, not a formality: this
// project's existing C++ fixtures cover composition (Item nests Object) and
// u16-as-identifier-domain-width, but NEVER a plain scalar u16 field sitting
// inside a composed type. This is exactly that combination.
//
// Values (60000, 12000, 500) are all well above 255 specifically so a
// truncation-to-8-bit bug, or any byte-order mishandling, would produce an
// observably wrong result rather than coincidentally passing.
//
// This is the SPLIT-mode variant (§14.3's new default, header/.cpp): the
// instance definition (`Character_Instances::Hero`) lives in the .cpp file
// as a plain `extern const`, NOT `inline constexpr` the way single-header
// mode's does -- so static_assert against it directly isn't available here
// (confirmed directly: attempting it gives "not usable in a constant
// expression", not a stylistic choice). Runtime checks below cover the
// same ground; see test_generated_composition_nested_u16_fields_single.cpp
// for the constexpr-checkable single-header counterpart.

#include "generated_composition_nested_u16_fields.h"
#include <cassert>
#include <cstdio>

int main() {
    // sizeof sanity: uint16_t fields should occupy exactly 2 bytes each,
    // not be silently widened or narrowed by the generated struct layout.
    // This much IS available at compile time regardless of split mode,
    // since it only depends on the type, not on a specific instance.
    static_assert(sizeof(GDDL::Character::stats) == sizeof(GDDL::Stats));
    static_assert(sizeof(decltype(GDDL::Stats::hp)) == 2);
    static_assert(sizeof(decltype(GDDL::Character::level)) == 2);

    // Runtime checks: direct access to the extern instance, and via the
    // registry's Find() -- confirms the same values round-trip both ways,
    // not just through the constexpr-friendly path this mode doesn't have.
    assert(GDDL::Character_Instances::Hero.stats.hp == 60000);
    assert(GDDL::Character_Instances::Hero.stats.mp == 12000);
    assert(GDDL::Character_Instances::Hero.equipment.weapon_power == 500);
    assert(GDDL::Character_Instances::Hero.level == 42);

    const GDDL::Character* found = GDDL::Character_Registry::Find(std::string_view("Hero"));
    assert(found != nullptr);
    assert(found->stats.hp == 60000);
    assert(found->stats.mp == 12000);
    assert(found->equipment.weapon_power == 500);
    assert(found->level == 42);

    std::printf("hp=%u mp=%u weapon_power=%u level=%u\n",
                found->stats.hp, found->stats.mp,
                found->equipment.weapon_power, found->level);
    std::printf("All C++ (split mode) composition+u16 checks passed.\n");
    return 0;
}
