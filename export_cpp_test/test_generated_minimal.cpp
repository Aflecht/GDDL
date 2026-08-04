#include "generated_minimal.h"
#include <cassert>
#include <cstdio>

int main() {
    // Direct access -- compile-time known instance, zero indirection.
    static_assert(GDDL::Object_Instances::HeavyObject.something1 == 100);
    static_assert(GDDL::Object_Instances::HeavyObject.something2 == 50);
    static_assert(GDDL::Object_Instances::LightObject.something1 == 5);
    static_assert(GDDL::Object_Instances::LightObject.something2 == 50);
    static_assert(GDDL::Object_Instances::DefaultObject.something1 == 0);

    // Enum values are real, distinct, and match the domain-qualified
    // FNV-1a-64 hashes computed by the reference implementation.
    static_assert(static_cast<uint64_t>(GDDL::ActionAttack::melee_weapon) == 0x5c96a731d7d47e03ULL);
    static_assert(static_cast<uint64_t>(GDDL::ActionAttack::ranged_weapon) == 0xaa92e2b5323e5154ULL);
    static_assert(GDDL::ActionAttack::melee_weapon != GDDL::ActionAttack::ranged_weapon);

    // Registry: pointer identity with the same object Object_Instances:: exposes.
    static_assert(GDDL::Object_Registry::Table.size() == 3);
    static_assert(GDDL::Object_Registry::Find(0x4e4417bdfce7a91aULL) == &GDDL::Object_Instances::HeavyObject);

    // Dynamic lookup by stable ID, at runtime (not just constexpr context).
    const GDDL::Object* found = GDDL::Object_Registry::Find(0x4e4417bdfce7a91aULL);
    assert(found == &GDDL::Object_Instances::HeavyObject);
    assert(found->something1 == 100);

    // Dynamic lookup by name.
    const GDDL::Object* found_by_name = GDDL::Object_Registry::Find(std::string_view("LightObject"));
    assert(found_by_name == &GDDL::Object_Instances::LightObject);
    assert(found_by_name->something1 == 5);
    assert(found_by_name->something2 == 50);

    // Miss cases.
    assert(GDDL::Object_Registry::Find(0xdeadbeefULL) == nullptr);
    assert(GDDL::Object_Registry::Find(std::string_view("Nonexistent")) == nullptr);

    // Find() usable in a constexpr context too (per §13.2's whole point).
    static_assert(GDDL::Object_Registry::Find(0x4e4417bdfce7a91aULL) != nullptr);

    std::printf("All checks passed.\n");
    return 0;
}
