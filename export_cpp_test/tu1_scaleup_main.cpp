#include "generated_scaleup.h"
#include <cassert>
#include <cstdio>

extern const GDDL::Object* get_base_object_from_tu2();
extern const GDDL::Item* get_item_copy_from_tu2();

int main() {
    // Pointer identity across TUs, now checked for BOTH types in the
    // header (Object and the composed Item), not just a single type.
    assert(&GDDL::Object_Instances::BaseObject == get_base_object_from_tu2());
    assert(&GDDL::Item_Instances::ItemCopy == get_item_copy_from_tu2());
    std::printf("Cross-TU pointer identity holds for both Object and Item.\n");
    return 0;
}
