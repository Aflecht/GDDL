/* Test harness for --emit-all-domains on the 68000 target.
 * Confirms that the Rarity domain (declared u8, zero field references)
 * produces correct typedef + member constants when flag is on.
 * C89 (vbcc) -- separate TU from the generated .c, same convention as
 * existing 68000 tests. */
#include <stdio.h>
#include "generated_68000_emit_ON.h"

int main(void)
{
    /* Check that the Rarity typedef and named constants exist and
       hold the expected 0-based dense index values. A missing typedef
       or wrong value would be a compile error or assertion failure. */
    if ((int)Rarity_common != 0) {
        printf("FAIL: Rarity_common != 0\n"); return 1;
    }
    if ((int)Rarity_rare != 1) {
        printf("FAIL: Rarity_rare != 1\n"); return 1;
    }
    if ((int)Rarity_epic != 2) {
        printf("FAIL: Rarity_epic != 2\n"); return 1;
    }
    if (sizeof(Rarity) != 1) {
        printf("FAIL: sizeof(Rarity) != 1 (expected u8 = unsigned char)\n");
        return 1;
    }
    printf("Rarity_common=%d Rarity_rare=%d Rarity_epic=%d sizeof=%lu\n",
           (int)Rarity_common, (int)Rarity_rare, (int)Rarity_epic,
           (unsigned long)sizeof(Rarity));
    printf("68000 --emit-all-domains: Rarity constants correct (0, 1, 2)\n");
    return 0;
}
