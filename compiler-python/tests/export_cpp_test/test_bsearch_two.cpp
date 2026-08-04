#include "generated_bsearch_two.h"
#include <cassert>
#include <cstdio>

int main() {
    // Two-entry table: exercises both branches of the comparison
    // (Table[mid] < target vs >=) in a single loop iteration.
    assert(GDDL::Stats_Registry::Table.size() == 2);
    assert(GDDL::Stats_Registry::Find(0xcf21be814f115716ULL) == &GDDL::Stats_Instances::First);
    assert(GDDL::Stats_Registry::Find(0xd010fa000af29e04ULL) == &GDDL::Stats_Instances::Second);
    assert(GDDL::Stats_Registry::Find(0xcf21be814f115715ULL) == nullptr); // below both
    assert(GDDL::Stats_Registry::Find(0xd010fa000af29e05ULL) == nullptr); // above both
    assert(GDDL::Stats_Registry::Find(0xcf995c40ad01fa8dULL) == nullptr); // strictly between the two
    std::printf("Two-entry boundary test passed.\n");
    return 0;
}