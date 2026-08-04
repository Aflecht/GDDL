#include "generated_indexed_split_soa.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    // Runtime reads (no static_assert -- data isn't constexpr-usable in
    // split mode). Composition flattening still holds: separate arrays,
    // matching indices across fields.
    assert(GDDL::Item_SoA::object_something1[0] == 10);
    assert(GDDL::Item_SoA::object_something2[0] == 20);
    assert(GDDL::Item_SoA::weight[0] == 5);
    assert(GDDL::Item_SoA::element[0] == GDDL::Element::fire);
    assert(GDDL::Item_SoA::fast_dispatch[0] == GDDL::ActionAttack_Indexed::melee_weapon);

    assert(GDDL::Item_SoA::object_something1[1] == 99);
    assert(GDDL::Item_SoA::weight[1] == 7);

    // string slicing still correct via runtime access
    assert(std::strncmp(&GDDL::Item_SoA::name[0 * 16], "Sword", 5) == 0);
    assert(std::strncmp(&GDDL::Item_SoA::name[1 * 16], "AAAAAAAAAAAAAAA", 15) == 0);

    // parallel lookup -- ordinary runtime function now
    std::size_t row = GDDL::Item_SoA_Registry::Find(std::string_view("ItemViaBareModify"));
    assert(row != GDDL::Item_SoA_Registry::Table.size());
    assert(GDDL::Item_SoA::weight[row] == 7);
    assert(GDDL::Item_SoA::element[row] == GDDL::Element::ice);

    std::size_t row_by_id = GDDL::Item_SoA_Registry::Find(0x8ad19844df88b655ULL);
    assert(row_by_id == row);

    assert(GDDL::Item_SoA_Registry::Find(std::string_view("NoSuchItem")) == GDDL::Item_SoA_Registry::Table.size());

    // Object's SoA -- larger table, every entry via the lookup
    for (const auto& entry : GDDL::Object_SoA_Registry::Table) {
        std::size_t r = GDDL::Object_SoA_Registry::Find(entry.instance_id);
        assert(r == entry.row);
    }
    assert(GDDL::Object_SoA::something1[GDDL::Object_SoA_Registry::Find(std::string_view("HeavyObject"))] == 100);

    // Enums still compile-time-usable even in SoA split mode.
    static_assert(static_cast<uint64_t>(GDDL::ActionAttack::melee_weapon) == 0x5c96a731d7d47e03ULL);

    std::printf("Split-mode (SoA) link+run test passed: header-only compilation, "
                "linked against separately-compiled .cpp, all runtime lookups correct.\n");
    return 0;
}
