/* Real vbcc/vamos compile-and-run validation for the pools feature, AoS
   mode. See export_test_68000_pools.gddl for the fixture and
   corpus/pools/ for the phase 1-8 golden-locked coverage. */

#include <stdio.h>
#include <string.h>
#include "generated_68000_pools.h"

int main(void)
{
    const Enemy *placeholder;

    /* The one named instance in this fixture (worked around a real,
       unrelated, pre-existing vbcc empty-initializer gap -- see the
       .gddl fixture's own comment) still resolves normally, unaffected
       by the pool declared alongside it. */
    placeholder = Enemy_Find(Enemy_Placeholder_Index);
    if (placeholder->hp != 1) {
        printf("FAIL named instance untouched by pool\n");
        return 1;
    }

    /* A pool is real, addressable storage: 8 uninitialized Enemy slots,
       indexed by plain array subscript -- never by name (section 22.2,
       not identity-bearing). Genuinely mutable (`Enemy ActiveEnemies[8]`,
       not `const`) -- write into a slot at runtime, the way the game
       itself would when spawning an entity into the pool. Unlike
       6502/Z80, no field-type restriction -- exercises string and
       nested-struct fields a pool on those targets could never hold. */
    ActiveEnemies[3].hp = 42;
    ActiveEnemies[3].damage_min_max[0] = 1;
    ActiveEnemies[3].damage_min_max[1] = 2;
    strcpy(ActiveEnemies[3].name, "Test");
    ActiveEnemies[3].position.x = 5;
    ActiveEnemies[3].position.y = 6;

    if (ActiveEnemies[3].hp != 42) {
        printf("FAIL hp readback\n");
        return 1;
    }
    if (ActiveEnemies[3].damage_min_max[0] != 1 || ActiveEnemies[3].damage_min_max[1] != 2) {
        printf("FAIL damage_min_max readback\n");
        return 1;
    }
    if (strcmp(ActiveEnemies[3].name, "Test") != 0) {
        printf("FAIL name readback\n");
        return 1;
    }
    if (ActiveEnemies[3].position.x != 5 || ActiveEnemies[3].position.y != 6) {
        printf("FAIL nested struct position readback\n");
        return 1;
    }

    /* A different slot never written stays whatever it was -- just
       confirmed it's a real, distinct storage location from slot 3. */
    ActiveEnemies[0].hp = 7;
    if (ActiveEnemies[0].hp != 7 || ActiveEnemies[3].hp != 42) {
        printf("FAIL independent slot storage\n");
        return 1;
    }

    printf("sizeof(Enemy) = %d\n", (int)sizeof(Enemy));
    printf("All 68000 pools (AoS write/read, independent slots, nested "
           "struct field, named instance unaffected) checks passed.\n");
    return 0;
}
