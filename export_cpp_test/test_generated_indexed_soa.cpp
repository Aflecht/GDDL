#include "generated_indexed_soa.h"
#include <cassert>
#include <cstdio>
#include <cstring>
#include <type_traits>

int main() {
    // ---- §13.1: composition flattening produces genuinely SEPARATE
    // arrays, not a nested array-of-structs ----
    static_assert(std::is_same_v<
        std::remove_const_t<decltype(GDDL::Item_SoA::object_something1)>,
        std::array<uint32_t, 3>>);
    static_assert(std::is_same_v<
        std::remove_const_t<decltype(GDDL::Item_SoA::object_something2)>,
        std::array<uint32_t, 3>>);
    // (There is deliberately no GDDL::Item_SoA::object array of Object
    // structs at all -- if the flattening had failed and left a nested
    // struct array instead, this file simply wouldn't reference
    // anything of that shape, so there's nothing to negatively assert
    // against; the affirmative checks above ARE the proof it flattened
    // correctly, since a nested-struct-array design couldn't produce
    // these two independently-typed, independently-sized arrays.)

    // ---- values correct at matching indices across every field's
    // array (index i = same instance across ALL arrays) ----
    // Declaration order: ItemViaFullReplace=0, ItemViaBareModify=1, ItemCopy=2
    static_assert(GDDL::Item_SoA::object_something1[0] == 10); // FullReplace: object=BaseObject{10,20}
    static_assert(GDDL::Item_SoA::object_something2[0] == 20);
    static_assert(GDDL::Item_SoA::weight[0] == 5);
    static_assert(GDDL::Item_SoA::element[0] == GDDL::Element::fire);
    static_assert(GDDL::Item_SoA::fast_dispatch[0] == GDDL::ActionAttack_Indexed::melee_weapon);

    static_assert(GDDL::Item_SoA::object_something1[1] == 99); // BareModify: object.something1=99 set directly
    static_assert(GDDL::Item_SoA::object_something2[1] == 100);
    static_assert(GDDL::Item_SoA::weight[1] == 7);
    static_assert(GDDL::Item_SoA::element[1] == GDDL::Element::ice);
    static_assert(GDDL::Item_SoA::fast_dispatch[1] == GDDL::ActionAttack_Indexed::ranged_weapon);

    static_assert(GDDL::Item_SoA::object_something1[2] == 10); // Copy = FullReplace: object inherited unchanged
    static_assert(GDDL::Item_SoA::object_something2[2] == 20);
    static_assert(GDDL::Item_SoA::weight[2] == 50); // weight overridden on the copy
    static_assert(GDDL::Item_SoA::element[2] == GDDL::Element::lightning); // element overridden too
    static_assert(GDDL::Item_SoA::fast_dispatch[2] == GDDL::ActionAttack_Indexed::melee_weapon);

    // ---- §13.2: string field as one flat N*count byte array, correct
    // per-instance N-byte slice ----
    static_assert(GDDL::Item_SoA::name.size() == 48); // 16 * 3
    assert(std::strncmp(&GDDL::Item_SoA::name[0 * 16], "Sword", 5) == 0);
    assert(GDDL::Item_SoA::name[0 * 16 + 5] == '\0');
    assert(std::strncmp(&GDDL::Item_SoA::name[1 * 16], "AAAAAAAAAAAAAAA", 15) == 0);
    assert(GDDL::Item_SoA::name[1 * 16 + 15] == '\0'); // exact N-1 boundary case, still correct in SoA
    assert(std::strncmp(&GDDL::Item_SoA::name[2 * 16], "Shield", 6) == 0);
    assert(GDDL::Item_SoA::name[2 * 16 + 6] == '\0');

    // ---- §13.4: parallel lookup table resolves ID/name to the
    // correct row, and that row correctly indexes every field array ----
    std::size_t row = GDDL::Item_SoA_Registry::Find(std::string_view("ItemViaBareModify"));
    assert(row != GDDL::Item_SoA_Registry::Table.size()); // found (not the not-found sentinel)
    assert(GDDL::Item_SoA::object_something1[row] == 99);
    assert(GDDL::Item_SoA::weight[row] == 7);
    assert(GDDL::Item_SoA::element[row] == GDDL::Element::ice);
    assert(GDDL::Item_SoA::fast_dispatch[row] == GDDL::ActionAttack_Indexed::ranged_weapon);
    assert(std::strncmp(&GDDL::Item_SoA::name[row * 16], "AAAAAAAAAAAAAAA", 15) == 0);

    // Same lookup by instance_id instead of name -- must resolve to the
    // SAME row.
    std::size_t row_by_id = GDDL::Item_SoA_Registry::Find(0x8ad19844df88b655ULL);
    assert(row_by_id == row);

    // Miss: not-found sentinel is Table.size(), not some other value.
    assert(GDDL::Item_SoA_Registry::Find(std::string_view("NoSuchItem")) == GDDL::Item_SoA_Registry::Table.size());
    assert(GDDL::Item_SoA_Registry::Find(0xdeadbeefULL) == GDDL::Item_SoA_Registry::Table.size());

    // ---- Object's SoA (a type with no composition, simpler case,
    // larger instance count) -- every entry via the parallel lookup ----
    for (const auto& entry : GDDL::Object_SoA_Registry::Table) {
        std::size_t r = GDDL::Object_SoA_Registry::Find(entry.instance_id);
        assert(r == entry.row);
        // sanity: the row actually indexes real data (no crash / OOB)
        assert(r < GDDL::Object_SoA::something1.size());
    }
    assert(GDDL::Object_SoA::something1[GDDL::Object_SoA_Registry::Find(std::string_view("HeavyObject"))] == 100);
    assert(GDDL::Object_SoA::something2[GDDL::Object_SoA_Registry::Find(std::string_view("HeavyObject"))] == 50);

    std::printf("All SoA checks passed: composition flattening, string slicing, "
                "identifier forms, and parallel lookup all verified.\n");
    return 0;
}
