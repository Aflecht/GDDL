#include "generated_bsearch_large.h"

// Confirm the binary search actually works in a genuine constexpr
// context at this scale (20 entries), not just at runtime -- first,
// middle, and last entries in SORTED order (i.e. actually exercising
// different numbers of loop iterations), plus a constexpr miss.
static_assert(GDDL::Stats_Registry::Find(0xaa04cd91d9a757e0ULL) == &GDDL::Stats_Instances::Entry04);
static_assert(GDDL::Stats_Registry::Find(0xaa085091d9aa6c50ULL) == &GDDL::Stats_Instances::Entry17);
static_assert(GDDL::Stats_Registry::Find(0xaa085f91d9aa85cdULL) == &GDDL::Stats_Instances::Entry18);
static_assert(GDDL::Stats_Registry::Find(0xdeadbeefULL) == nullptr);

int main() { return 0; }
