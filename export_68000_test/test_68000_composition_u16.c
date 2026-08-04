#include <stdio.h>
#include "generated_68000_composition_u16.h"

/* Real vbcc compile/link/run validation for composition_nested_u16_fields.gddl
 * on the 68000 export target -- closing a genuine gap, not a formality: prior
 * 68000 fixtures use u16 only as an identifier-domain width (Element's backing
 * type), never a plain scalar u16 field, and the one existing fixture (flat
 * Creature) has no composition at all. This is exactly that untested
 * combination, ported from the Z80/C++/6502 targets where it was validated
 * separately.
 *
 * Values (60000, 12000, 500) are all well above 255 specifically so a
 * truncation-to-8-bit bug, or any byte-order mishandling under C89's
 * aggregate initializer, would produce an observably wrong result rather
 * than one that happens to work by coincidence.
 */

int main(void)
{
    /* sizeof sanity: u16 fields should occupy exactly 2 bytes on this
       target, confirmed directly under emulation (sizeof(unsigned short)
       == 2 was checked separately before trusting this), not silently
       widened by the generated struct layout. */
    if (sizeof(Character_Instances[0].stats.hp) != 2) {
        printf("FAIL: stats.hp is not 2 bytes\n");
        return 1;
    }
    if (sizeof(Character_Instances[0].level) != 2) {
        printf("FAIL: level is not 2 bytes\n");
        return 1;
    }

    /* Direct access: nested struct fields hold the exact values, not
       truncated or reordered by composition. */
    if (Character_Instances[0].stats.hp != 60000) {
        printf("FAIL: stats.hp wrong: %u\n", Character_Instances[0].stats.hp);
        return 1;
    }
    if (Character_Instances[0].stats.mp != 12000) {
        printf("FAIL: stats.mp wrong: %u\n", Character_Instances[0].stats.mp);
        return 1;
    }
    if (Character_Instances[0].equipment.weapon_power != 500) {
        printf("FAIL: equipment.weapon_power wrong: %u\n",
               Character_Instances[0].equipment.weapon_power);
        return 1;
    }
    if (Character_Instances[0].level != 42) {
        printf("FAIL: level wrong: %u\n", Character_Instances[0].level);
        return 1;
    }

    /* Runtime access via Character_Find(), not just the raw array --
       confirms the same values round-trip through the generated lookup
       function, not just through direct array indexing. */
    {
        const Character* found = Character_Find(Character_Hero_Index);
        if (found == 0) {
            printf("FAIL: Character_Find returned NULL\n");
            return 1;
        }
        if (found->stats.hp != 60000 || found->stats.mp != 12000
            || found->equipment.weapon_power != 500 || found->level != 42) {
            printf("FAIL: Character_Find result mismatch\n");
            return 1;
        }
        printf("hp=%u mp=%u weapon_power=%u level=%u\n",
               found->stats.hp, found->stats.mp,
               found->equipment.weapon_power, found->level);
    }

    printf("All 68000 composition+u16 checks passed.\n");
    return 0;
}
