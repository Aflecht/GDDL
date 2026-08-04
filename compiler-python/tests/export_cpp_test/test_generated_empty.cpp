#include "generated_empty.h"
#include <cassert>
#include <cstdio>

int main() {
    static_assert(GDDL::Object_Registry::Table.size() == 0);
    assert(GDDL::Object_Registry::Find(12345ULL) == nullptr);
    assert(GDDL::Object_Registry::Find(std::string_view("Anything")) == nullptr);
    // Delete template never appears anywhere in the output at all.
    std::printf("Empty registry (zero exported instances) works correctly.\n");
    return 0;
}
