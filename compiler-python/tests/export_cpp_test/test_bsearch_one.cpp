#include "generated_bsearch_one.h"
#include <cassert>
#include <cstdio>

int main() {
    // Single-entry table: lo=0, hi=1 initially -- the smallest non-empty
    // case, where the loop runs exactly once.
    assert(GDDL::Stats_Registry::Table.size() == 1);
    assert(GDDL::Stats_Registry::Find(0x5e71436bc9c63862ULL) == &GDDL::Stats_Instances::OnlyOne);
    assert(GDDL::Stats_Registry::Find(0x5e71436bc9c63861ULL) == nullptr); // below the only entry
    assert(GDDL::Stats_Registry::Find(0x5e71436bc9c63863ULL) == nullptr); // above the only entry
    std::printf("Single-entry boundary test passed.\n");
    return 0;
}
