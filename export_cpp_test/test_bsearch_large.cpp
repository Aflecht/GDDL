#include "generated_bsearch_large.h"
#include <cassert>
#include <cstdio>

int main() {
    // Exhaustive: EVERY entry in the table must be findable by its
    // own real instance_id, and the returned pointer must be the
    // correct instance.
    assert(GDDL::Stats_Registry::Find(0xaa04cd91d9a757e0ULL) == &GDDL::Stats_Instances::Entry04);
    assert(GDDL::Stats_Registry::Find(0xaa04ce91d9a75993ULL) == &GDDL::Stats_Instances::Entry05);
    assert(GDDL::Stats_Registry::Find(0xaa04cf91d9a75b46ULL) == &GDDL::Stats_Instances::Entry06);
    assert(GDDL::Stats_Registry::Find(0xaa04d091d9a75cf9ULL) == &GDDL::Stats_Instances::Entry07);
    assert(GDDL::Stats_Registry::Find(0xaa04d191d9a75eacULL) == &GDDL::Stats_Instances::Entry00);
    assert(GDDL::Stats_Registry::Find(0xaa04d291d9a7605fULL) == &GDDL::Stats_Instances::Entry01);
    assert(GDDL::Stats_Registry::Find(0xaa04d391d9a76212ULL) == &GDDL::Stats_Instances::Entry02);
    assert(GDDL::Stats_Registry::Find(0xaa04d491d9a763c5ULL) == &GDDL::Stats_Instances::Entry03);
    assert(GDDL::Stats_Registry::Find(0xaa04d991d9a76c44ULL) == &GDDL::Stats_Instances::Entry08);
    assert(GDDL::Stats_Registry::Find(0xaa04da91d9a76df7ULL) == &GDDL::Stats_Instances::Entry09);
    assert(GDDL::Stats_Registry::Find(0xaa085091d9aa6c50ULL) == &GDDL::Stats_Instances::Entry17);
    assert(GDDL::Stats_Registry::Find(0xaa085191d9aa6e03ULL) == &GDDL::Stats_Instances::Entry16);
    assert(GDDL::Stats_Registry::Find(0xaa085291d9aa6fb6ULL) == &GDDL::Stats_Instances::Entry15);
    assert(GDDL::Stats_Registry::Find(0xaa085391d9aa7169ULL) == &GDDL::Stats_Instances::Entry14);
    assert(GDDL::Stats_Registry::Find(0xaa085491d9aa731cULL) == &GDDL::Stats_Instances::Entry13);
    assert(GDDL::Stats_Registry::Find(0xaa085591d9aa74cfULL) == &GDDL::Stats_Instances::Entry12);
    assert(GDDL::Stats_Registry::Find(0xaa085691d9aa7682ULL) == &GDDL::Stats_Instances::Entry11);
    assert(GDDL::Stats_Registry::Find(0xaa085791d9aa7835ULL) == &GDDL::Stats_Instances::Entry10);
    assert(GDDL::Stats_Registry::Find(0xaa085e91d9aa841aULL) == &GDDL::Stats_Instances::Entry19);
    assert(GDDL::Stats_Registry::Find(0xaa085f91d9aa85cdULL) == &GDDL::Stats_Instances::Entry18);

    // Misses at multiple relative positions/binary-search depths.
    assert(GDDL::Stats_Registry::Find(0xaa04cd91d9a757dfULL) == nullptr); // below all
    assert(GDDL::Stats_Registry::Find(0xaa085f91d9aa85ceULL) == nullptr); // above all
    assert(GDDL::Stats_Registry::Find(0xaa04cf11d9a75a6cULL) == nullptr); // between Entry05 and Entry06
    assert(GDDL::Stats_Registry::Find(0xaa085111d9aa6d29ULL) == nullptr); // between Entry17 and Entry16
    assert(GDDL::Stats_Registry::Find(0xaa085f11d9aa84f3ULL) == nullptr); // between Entry19 and Entry18

    // Also confirm every entry is findable by name (linear-scan side).
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry04")) == &GDDL::Stats_Instances::Entry04);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry05")) == &GDDL::Stats_Instances::Entry05);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry06")) == &GDDL::Stats_Instances::Entry06);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry07")) == &GDDL::Stats_Instances::Entry07);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry00")) == &GDDL::Stats_Instances::Entry00);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry01")) == &GDDL::Stats_Instances::Entry01);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry02")) == &GDDL::Stats_Instances::Entry02);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry03")) == &GDDL::Stats_Instances::Entry03);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry08")) == &GDDL::Stats_Instances::Entry08);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry09")) == &GDDL::Stats_Instances::Entry09);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry17")) == &GDDL::Stats_Instances::Entry17);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry16")) == &GDDL::Stats_Instances::Entry16);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry15")) == &GDDL::Stats_Instances::Entry15);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry14")) == &GDDL::Stats_Instances::Entry14);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry13")) == &GDDL::Stats_Instances::Entry13);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry12")) == &GDDL::Stats_Instances::Entry12);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry11")) == &GDDL::Stats_Instances::Entry11);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry10")) == &GDDL::Stats_Instances::Entry10);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry19")) == &GDDL::Stats_Instances::Entry19);
    assert(GDDL::Stats_Registry::Find(std::string_view("Entry18")) == &GDDL::Stats_Instances::Entry18);
    assert(GDDL::Stats_Registry::Find(std::string_view("NoSuchEntry")) == nullptr);

    assert(GDDL::Stats_Registry::Table.size() == 20);

    std::printf("Large-table exhaustive binary search test passed: %zu entries, every one individually verified.\n", GDDL::Stats_Registry::Table.size());
    return 0;
}