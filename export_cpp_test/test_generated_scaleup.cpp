#include "generated_scaleup.h"
#include <cassert>
#include <cstdio>

int main() {
    // Composition: nested struct fields, correctly resolved per instance.
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.object.something1 == 10);
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.object.something2 == 20);
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.weight == 5);
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.element == GDDL::Element::fire);

    static_assert(GDDL::Item_Instances::ItemViaBareModify.object.something1 == 99);
    static_assert(GDDL::Item_Instances::ItemViaBareModify.object.something2 == 100);
    static_assert(GDDL::Item_Instances::ItemViaBareModify.weight == 7);
    static_assert(GDDL::Item_Instances::ItemViaBareModify.element == GDDL::Element::ice);

    // ItemCopy = ItemViaFullReplace, weight/element overridden, object
    // (nested struct) inherited unchanged -- exercises composition
    // surviving an instance-level copy, not just a direct field assign.
    static_assert(GDDL::Item_Instances::ItemCopy.object.something1 == 10);
    static_assert(GDDL::Item_Instances::ItemCopy.object.something2 == 20);
    static_assert(GDDL::Item_Instances::ItemCopy.weight == 50);
    static_assert(GDDL::Item_Instances::ItemCopy.element == GDDL::Element::lightning);

    // Larger identifier domain: all 4 members distinct, correct values.
    static_assert(static_cast<uint64_t>(GDDL::Element::fire) == 0x9bcf40f6874d9103ULL);
    static_assert(static_cast<uint64_t>(GDDL::Element::ice) == 0x8304148e0f4f19acULL);
    static_assert(static_cast<uint64_t>(GDDL::Element::lightning) == 0x2ac1c587b5474f2dULL);
    static_assert(static_cast<uint64_t>(GDDL::Element::poison) == 0xfa09e3b805721ebfULL);
    static_assert(GDDL::Element::fire != GDDL::Element::ice);
    static_assert(GDDL::Element::ice != GDDL::Element::lightning);
    static_assert(GDDL::Element::lightning != GDDL::Element::poison);
    static_assert(GDDL::Element::fire != GDDL::Element::poison);

    // Both registries, independently, including the composed type.
    static_assert(GDDL::Object_Registry::Table.size() == 4);
    static_assert(GDDL::Item_Registry::Table.size() == 3);

    const GDDL::Item* found = GDDL::Item_Registry::Find(std::string_view("ItemCopy"));
    assert(found == &GDDL::Item_Instances::ItemCopy);
    assert(found->object.something1 == 10);
    assert(found->weight == 50);
    assert(found->element == GDDL::Element::lightning);

    const GDDL::Object* found_obj = GDDL::Object_Registry::Find(std::string_view("BaseObject"));
    assert(found_obj != nullptr);
    assert(found_obj->something1 == 10);

    // Cross-registry miss: an Item name shouldn't resolve in Object's
    // registry, and vice versa (they're genuinely separate tables).
    assert(GDDL::Object_Registry::Find(std::string_view("ItemCopy")) == nullptr);
    assert(GDDL::Item_Registry::Find(std::string_view("BaseObject")) == nullptr);

    std::printf("All scale-up checks passed.\n");
    return 0;
}
