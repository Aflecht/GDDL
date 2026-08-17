/* Real vbcc/vamos compile-and-run validation for the arrays feature, SoA
   mode. See export_test_68000_arrays.gddl for the fixture. */

#include <stdio.h>
#include <string.h>
#include "generated_68000_arrays_soa.h"

int main(void)
{
    int base = Enemy_BaseGoblin_Index;
    int strong = Enemy_StrongerGoblin_Index;

    if (Enemy_damage_min_max[base][0] != 10 || Enemy_damage_min_max[base][1] != 30) {
        printf("FAIL base damage_min_max\n");
        return 1;
    }
    if (Enemy_damage_min_max[strong][0] != 10 || Enemy_damage_min_max[strong][1] != 80) {
        printf("FAIL strong damage_min_max\n");
        return 1;
    }

    if (Enemy_grid[base][1][2] != 6) {
        printf("FAIL grid\n");
        return 1;
    }
    if (strcmp(Enemy_names[base][2], "Carol, Jr.") != 0) {
        printf("FAIL names base\n");
        return 1;
    }
    if (strcmp(Enemy_names[strong][3], "Dave") != 0) {
        printf("FAIL names strong\n");
        return 1;
    }

    printf("All 68000 SoA arrays checks passed.\n");
    return 0;
}
