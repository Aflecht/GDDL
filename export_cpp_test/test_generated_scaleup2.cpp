#include "generated_scaleup2.h"
#include <cassert>
#include <cstdio>
#include <cstring>

int main() {
    // ---- string N field export (§13.1 + §5 boundary) ----

    // char[16] array, correct size, per §13.1.
    static_assert(sizeof(GDDL::Item_Instances::ItemViaFullReplace.name) == 16);

    // Well-under-capacity string: correct content, null-terminated.
    static_assert(GDDL::Item_Instances::ItemViaFullReplace.name[0] == 'S');
    assert(std::strcmp(GDDL::Item_Instances::ItemViaFullReplace.name, "Sword") == 0);
    assert(GDDL::Item_Instances::ItemViaFullReplace.name[5] == '\0');

    // Exact boundary case: 15 bytes of content (N-1 for string 16) --
    // the maximum valid case the new String Length Enforcement rule
    // allows. Must fit with the 16th byte as the null terminator, and
    // nothing beyond that is guaranteed non-garbage by the standard,
    // but aggregate-init from a string literal zero-fills the rest, so
    // byte 15 (0-indexed) must be exactly '\0'.
    const char* boundary_name = GDDL::Item_Instances::ItemViaBareModify.name;
    assert(std::strlen(boundary_name) == 15);
    assert(boundary_name[15] == '\0');
    for (int i = 0; i < 15; ++i) {
        assert(boundary_name[i] == 'A');
    }
    assert(std::strcmp(boundary_name, "AAAAAAAAAAAAAAA") == 0);

    // ItemCopy's own string field, independent of the fields it
    // inherited unchanged from ItemViaFullReplace.
    assert(std::strcmp(GDDL::Item_Instances::ItemCopy.name, "Shield") == 0);

    // ---- delete-template-sourced export chain ----

    // BaseTemplate itself must not exist as a symbol at all -- if the
    // exporter had failed to exclude it, this file simply wouldn't
    // compile as a negative-space check, so there's no direct
    // static_assert for "it's absent"; the grep-based absence check
    // (done separately) plus this file compiling at all with no
    // reference to GDDL::Object_Instances::BaseTemplate is the proof.

    // Generation 1: completes the delete template (something1=1
    // inherited, something2=2 newly set).
    static_assert(GDDL::Object_Instances::RealObjectGen1.something1 == 1);
    static_assert(GDDL::Object_Instances::RealObjectGen1.something2 == 2);

    // Generation 2: built on top of generation 1 via an op-statement
    // (something1 * 10 => 10; something2 == 2, inherited unchanged).
    static_assert(GDDL::Object_Instances::RealObjectGen2.something1 == 10);
    static_assert(GDDL::Object_Instances::RealObjectGen2.something2 == 2);

    // Registry: exactly 6 Object instances (Default, Heavy, Light,
    // Base, Gen1, Gen2) -- BaseTemplate does NOT count towards this,
    // confirming it's excluded from the registry too, not just from
    // direct instance access.
    static_assert(GDDL::Object_Registry::Table.size() == 6);

    const GDDL::Object* gen1 = GDDL::Object_Registry::Find(std::string_view("RealObjectGen1"));
    assert(gen1 != nullptr);
    assert(gen1->something1 == 1 && gen1->something2 == 2);

    const GDDL::Object* gen2 = GDDL::Object_Registry::Find(std::string_view("RealObjectGen2"));
    assert(gen2 != nullptr);
    assert(gen2->something1 == 10 && gen2->something2 == 2);

    // The delete template's name must not resolve in the registry --
    // it was never an entry to begin with (not "found and rejected",
    // genuinely never registered).
    assert(GDDL::Object_Registry::Find(std::string_view("BaseTemplate")) == nullptr);

    std::printf("All string-N and delete-chain checks passed.\n");
    return 0;
}
