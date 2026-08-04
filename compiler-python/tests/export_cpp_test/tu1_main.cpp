#include "generated_minimal.h"
#include <cassert>
#include <cstdio>

extern const GDDL::Object* get_heavy_object_from_tu2();

int main() {
    const GDDL::Object* from_tu1 = &GDDL::Object_Instances::HeavyObject;
    const GDDL::Object* from_tu2 = get_heavy_object_from_tu2();
    // The whole point of `inline constexpr` over bare `constexpr`: this
    // must be the SAME address across translation units, or the registry
    // (which stores a pointer captured in ITS OWN translation unit) could
    // silently point at a different copy than code elsewhere expects.
    assert(from_tu1 == from_tu2);
    std::printf("Pointer identity across translation units: %s\n",
                (from_tu1 == from_tu2) ? "OK (same address)" : "FAILED (different addresses!)");
    return 0;
}
