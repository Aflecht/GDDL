#include <stdio.h>
#include <string.h>
#include "generated_68000_soa.h"

/* Only sees the header -- separate translation unit from
   generated_68000_soa.c. Covers width flexibility and string fields
   in SoA form. */

int main(void)
{
    /* Creature SoA: read by dense index, no lookup at all. */
    if (Creature_hp[Creature_Goblin_Index] != 10) {
        printf("FAIL: Goblin.hp\n");
        return 1;
    }
    if (Creature_attack[Creature_Goblin_Index] != ActionAttack_melee_weapon) {
        printf("FAIL: Goblin.attack\n");
        return 1;
    }
    if (Creature_rarity[Creature_Goblin_Index] != Rarity_common) {
        printf("FAIL: Goblin.rarity (u32 domain)\n");
        return 1;
    }
    if (Creature_rarity[Creature_Archer_Index] != Rarity_rare) {
        printf("FAIL: Archer.rarity (u32 domain)\n");
        return 1;
    }

    /* Item SoA: composition flattening + u16 domain + string field,
       all in SoA form, at matching indices. */
    if (Item_object_something1[Item_Sword_Index] != 5) {
        printf("FAIL: Sword.object.something1\n");
        return 1;
    }
    if (Item_object_something2[Item_Sword_Index] != 3) {
        printf("FAIL: Sword.object.something2\n");
        return 1;
    }
    if (Item_weight[Item_Sword_Index] != 7) {
        printf("FAIL: Sword.weight\n");
        return 1;
    }
    if (Item_element[Item_Sword_Index] != Element_fire) {
        printf("FAIL: Sword.element (u16 domain)\n");
        return 1;
    }
    if (Item_element[Item_Shield_Index] != Element_ice) {
        printf("FAIL: Shield.element (u16 domain)\n");
        return 1;
    }

    /* String field in SoA form: char Item_name[count][N] -- each row
       is one instance's whole N-byte string, confirming the 2D-array
       representation actually behaves like N independent per-instance
       strings, not one shared buffer. */
    if (strcmp(Item_name[Item_Sword_Index], "Sword") != 0) {
        printf("FAIL: Sword.name (SoA)\n");
        return 1;
    }
    if (strcmp(Item_name[Item_Shield_Index], "Shield") != 0) {
        printf("FAIL: Shield.name (SoA)\n");
        return 1;
    }
    if (sizeof(Item_name[0]) != 16) {
        printf("FAIL: Item_name row not 16 bytes\n");
        return 1;
    }
    /* Cross-check: two different instances' strings genuinely differ,
       not coincidentally reading the same row twice. */
    if (strcmp(Item_name[Item_Sword_Index], Item_name[Item_Shield_Index]) == 0) {
        printf("FAIL: Sword/Shield names unexpectedly equal\n");
        return 1;
    }

    printf("All 68000/vbcc SoA (width + string) checks passed.\n");
    return 0;
}
