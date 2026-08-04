#include "generated_indexed.h"
#include <cassert>
#include <cstdio>
#include <type_traits>

int main() {
    // ---- companion enum: correct values, 0-based, declaration order ----
    static_assert(static_cast<uint8_t>(GDDL::ActionAttack_Indexed::melee_weapon) == 0);
    static_assert(static_cast<uint8_t>(GDDL::ActionAttack_Indexed::ranged_weapon) == 1);
    static_assert(GDDL::ActionAttack_Indexed::melee_weapon != GDDL::ActionAttack_Indexed::ranged_weapon);

    // Underlying type is genuinely uint8_t, not left as the default int.
    static_assert(std::is_same_v<std::underlying_type_t<GDDL::ActionAttack_Indexed>, uint8_t>);

    // ---- struct member type is Domain_Indexed, not Domain ----
    static_assert(std::is_same_v<
        decltype(GDDL::Item_Instances::ItemViaFullReplace.fast_dispatch),
        GDDL::ActionAttack_Indexed>);
    // (Also confirm it's genuinely NOT plain ActionAttack -- the whole point.)
    static_assert(!std::is_same_v<
        decltype(GDDL::Item_Instances::ItemViaFullReplace.fast_dispatch),
        GDDL::ActionAttack>);

    // ---- correct values per-instance, matching source semantics ----
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.fast_dispatch
                  == GDDL::ActionAttack_Indexed::melee_weapon);
    static_assert(GDDL::Item_Instances::ItemViaBareModify.fast_dispatch
                  == GDDL::ActionAttack_Indexed::ranged_weapon);
    // ItemCopy = ItemViaFullReplace, then explicitly re-set fast_dispatch
    // to melee_weapon again (same value) -- still correctly melee_weapon.
    static_assert(GDDL::Item_Instances::ItemCopy.fast_dispatch
                  == GDDL::ActionAttack_Indexed::melee_weapon);

    // Meanwhile the PLAIN (non-indexed) ActionAttack enum is completely
    // unaffected and still logical-ID-valued as always -- indexed mode
    // is purely additive, doesn't change the default.
    static_assert(static_cast<uint64_t>(GDDL::ActionAttack::melee_weapon)
                  == 0x5c96a731d7d47e03ULL);

    // element field stays plain Element (never opted into @), confirming
    // Element having a declared width doesn't force every field of that
    // domain into indexed form -- it's per-field, always explicit.
    static_assert(std::is_same_v<
        decltype(GDDL::Item_Instances::ItemViaFullReplace.element),
        GDDL::Element>);
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.element == GDDL::Element::fire);

    std::printf("All indexed-mode checks passed.\n");
    return 0;
}
