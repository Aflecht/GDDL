/* Real vbcc/vamos compile-and-run validation for the pools feature, SoA
   mode. See export_test_68000_pools.gddl for the fixture and
   corpus/pools/ for the phase 1-8 golden-locked coverage. */

#include <stdio.h>
#include <string.h>
#include "generated_68000_pools_soa.h"

int main(void)
{
    /* The one named instance's own SoA columns are untouched by the
       pool's own separate columns declared alongside them. */
    if (Enemy_hp[0] != 1) {
        printf("FAIL named instance column untouched by pool\n");
        return 1;
    }

    /* Column arrays sized by pool count (8). No field-type restriction
       on this target -- exercises string and nested-struct (column-
       split into _x/_y) fields a pool on 6502/Z80 could never hold. */
    ActiveEnemies_hp[2] = 99;
    ActiveEnemies_damage_min_max[2][0] = 7;
    ActiveEnemies_damage_min_max[2][1] = 8;
    strcpy(ActiveEnemies_name[2], "Row2");
    ActiveEnemies_position_x[2] = 1;
    ActiveEnemies_position_y[2] = 2;

    if (ActiveEnemies_hp[2] != 99) {
        printf("FAIL hp readback\n");
        return 1;
    }
    if (ActiveEnemies_damage_min_max[2][0] != 7 || ActiveEnemies_damage_min_max[2][1] != 8) {
        printf("FAIL damage_min_max readback\n");
        return 1;
    }
    if (strcmp(ActiveEnemies_name[2], "Row2") != 0) {
        printf("FAIL name readback\n");
        return 1;
    }
    if (ActiveEnemies_position_x[2] != 1 || ActiveEnemies_position_y[2] != 2) {
        printf("FAIL nested struct field (position_x/position_y column split) readback\n");
        return 1;
    }

    /* A different row never written stays whatever it was -- just
       confirmed it's a real, distinct column slot. */
    ActiveEnemies_hp[0] = 5;
    if (ActiveEnemies_hp[0] != 5 || ActiveEnemies_hp[2] != 99) {
        printf("FAIL independent row storage\n");
        return 1;
    }

    printf("All 68000 pools SoA (column write/read, nested struct field "
           "split, string field, named instance column unaffected) "
           "checks passed.\n");
    return 0;
}
