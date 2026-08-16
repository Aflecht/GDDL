// Real MSVC compile/link/run validation for export_test_flags.gddl on the C++
// export target -- GDDL's stage 5 "a real combined value actually read back
// correctly from real compiled/run output" requirement for the flags/bN
// feature. See corpus/flags/flags_explicit_bit_mixed_with_auto.gddl (the SAME
// source, golden-locked there under normal discipline) for the full rationale;
// this file only covers the export-side half that corpus fixture's schema
// can't capture on its own.
//
// Single-header mode: everything is `inline constexpr`, so both the namespace
// constants AND the resolved instance data are checkable via static_assert,
// not just at runtime -- confirms the natural `if (flags & X)` check works
// directly in a constexpr context too, the whole point of the namespace-over-
// enum-class design (HANDOFF.md's "C++ export shape" entry).

#include "generated_flags.h"
#include <cassert>
#include <cstdio>

int main() {
    using namespace GDDL;

    // Namespace constants: real bit values, matching the domain's own
    // mixed explicit/auto assignment (is_movable explicit '= b2', declared
    // AFTER is_pickupable/is_equippable in source -- confirms the auto
    // members correctly skipped bit 2 regardless of declaration order).
    static_assert(ComponentFlags::none == 0);
    static_assert(ComponentFlags::is_damageable == 1);      // bit 0, explicit
    static_assert(ComponentFlags::is_pickupable == 2);      // bit 1, auto
    static_assert(ComponentFlags::is_movable == 4);         // bit 2, explicit
    static_assert(ComponentFlags::is_equippable == 8);      // bit 3, auto (skipped bit 2)
    static_assert(ComponentFlags::is_controllable == 16);   // bit 4, auto
    static_assert(ComponentFlags::is_passive_effect == 32); // bit 5, auto
    static_assert(ComponentFlags::is_use == 64);            // bit 6, auto
    static_assert(ComponentFlags::is_attack == 128);        // bit 7, auto

    // Resolved instance data, computed by the compiler from real .gddl
    // source (assign-time '|' combining, then an op-statement '&'/'~'
    // clearing one inherited bit) -- checkable at compile time in
    // single-header mode.
    static_assert(Entity_Instances::Player.component_flags == 20);
    static_assert(Entity_Instances::PlayerDisarmed.component_flags == 4);

    // The natural `if (flags & X)` check, the whole reason this project
    // rejected `enum class` for flags (confirmed via real compiled testing,
    // not just argued in the abstract -- see HANDOFF.md).
    if (!(Entity_Instances::Player.component_flags & ComponentFlags::is_movable)) {
        std::printf("FAIL: Player should be movable\n");
        return 1;
    }
    if (Entity_Instances::PlayerDisarmed.component_flags & ComponentFlags::is_controllable) {
        std::printf("FAIL: PlayerDisarmed should NOT be controllable\n");
        return 1;
    }
    if (!(Entity_Instances::PlayerDisarmed.component_flags & ComponentFlags::is_movable)) {
        std::printf("FAIL: PlayerDisarmed should still be movable (only "
                     "is_controllable was cleared)\n");
        return 1;
    }

    std::printf("Player.component_flags=%llu PlayerDisarmed.component_flags=%llu\n",
                static_cast<unsigned long long>(Entity_Instances::Player.component_flags),
                static_cast<unsigned long long>(Entity_Instances::PlayerDisarmed.component_flags));
    std::printf("All C++ flags (explicit+auto bit assignment, real bitwise "
                "combining) checks passed.\n");
    return 0;
}
