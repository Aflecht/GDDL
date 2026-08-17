/* Real vbcc/vamos compile-and-run validation for the arrays feature, AoS
   mode. See export_test_68000_arrays.gddl for the fixture and
   corpus/arrays/ for the phase 1-8 golden-locked coverage. */

#include <stdio.h>
#include <string.h>
#include "generated_68000_arrays.h"

int main(void)
{
    const Enemy *base, *strong;

    base = Enemy_Find(Enemy_BaseGoblin_Index);
    strong = Enemy_Find(Enemy_StrongerGoblin_Index);

    if (base->damage_min_max[0] != 10 || base->damage_min_max[1] != 30) {
        printf("FAIL base damage_min_max\n");
        return 1;
    }
    if (strong->damage_min_max[0] != 10 || strong->damage_min_max[1] != 80) {
        printf("FAIL strong damage_min_max (bracket-indexed op-statement: 30 + 50)\n");
        return 1;
    }

    if (base->grid[0][0] != 1 || base->grid[0][2] != 3) {
        printf("FAIL grid row0\n");
        return 1;
    }
    if (base->grid[1][0] != 4 || base->grid[1][2] != 6) {
        printf("FAIL grid row1\n");
        return 1;
    }

    if (strcmp(base->names[0], "Alice") != 0) {
        printf("FAIL names[0]\n");
        return 1;
    }
    if (strcmp(base->names[2], "Carol, Jr.") != 0) {
        printf("FAIL names[2] (embedded comma inside a quoted array element)\n");
        return 1;
    }
    if (strcmp(base->names[3], "Dave") != 0) {
        printf("FAIL names[3]\n");
        return 1;
    }

    /* Row-major contiguity, matching the design's own "match how C++ does this" instruction. */
    if ((const char *)&base->grid[1] - (const char *)&base->grid[0] != 3 * (long)sizeof(signed long)) {
        printf("FAIL row stride\n");
        return 1;
    }

    printf("sizeof(Enemy) = %d\n", (int)sizeof(Enemy));
    printf("All 68000 arrays (1D/2D, string elements, bracket-indexed op-statement) checks passed.\n");
    return 0;
}
