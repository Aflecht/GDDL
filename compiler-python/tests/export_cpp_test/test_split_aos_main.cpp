#include "generated_indexed_split.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    // These are NOT constexpr-usable here anymore (§14.3's real cost) --
    // ordinary runtime reads of externally-linked globals defined in
    // the .cpp. No static_assert on instance data in split mode; that's
    // the whole point of the split.
    assert(GDDL::Object_Instances::HeavyObject.something1 == 100);
    assert(GDDL::Object_Instances::HeavyObject.something2 == 50);
    assert(GDDL::Item_Instances::ItemViaFullReplace.object.something1 == 10);
    assert(GDDL::Item_Instances::ItemViaFullReplace.weight == 5);
    assert(GDDL::Item_Instances::ItemViaFullReplace.element == GDDL::Element::fire);
    assert(GDDL::Item_Instances::ItemViaFullReplace.fast_dispatch == GDDL::ActionAttack_Indexed::melee_weapon);
    assert(std::strcmp(GDDL::Item_Instances::ItemViaFullReplace.name, "Sword") == 0);

    // Enum values ARE still compile-time-usable in split mode -- only
    // instance/registry data gives that up.
    static_assert(static_cast<uint64_t>(GDDL::ActionAttack::melee_weapon) == 0x5c96a731d7d47e03ULL);
    static_assert(GDDL::ActionAttack_Indexed::melee_weapon != GDDL::ActionAttack_Indexed::ranged_weapon);

    // Find() -- an ordinary runtime function call now, its body defined
    // in the .cpp this file never sees.
    const GDDL::Object* found = GDDL::Object_Registry::Find(std::string_view("HeavyObject"));
    assert(found == &GDDL::Object_Instances::HeavyObject);
    assert(found->something1 == 100);

    const GDDL::Object* found_by_id = GDDL::Object_Registry::Find(0x4e4417bdfce7a91aULL);
    assert(found_by_id == &GDDL::Object_Instances::HeavyObject);

    const GDDL::Item* found_item = GDDL::Item_Registry::Find(std::string_view("ItemCopy"));
    assert(found_item == &GDDL::Item_Instances::ItemCopy);
    assert(found_item->weight == 50);

    assert(GDDL::Object_Registry::Find(std::string_view("NoSuchObject")) == nullptr);
    assert(GDDL::Object_Registry::Find(0xdeadbeefULL) == nullptr);

    std::printf("Split-mode (AoS) link+run test passed: header-only compilation, "
                "linked against separately-compiled .cpp, all runtime lookups correct.\n");
    return 0;
}
