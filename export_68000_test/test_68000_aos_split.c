#include <stdio.h>
#include <string.h>
#include "generated_68000_minimal.h"

/* Only sees the header -- separate translation unit from
   generated_68000_minimal.c. Covers the two gaps closed this round:
   domain width flexibility (u16/u32, not just u8) and string fields. */

int main(void)
{
    /* --- domain width flexibility --- */

    /* Element: declared u16 -- confirm the typedef is genuinely wide
       enough to hold all 3 members distinctly, not silently truncated
       to a narrower type. */
    if (sizeof(Element) < sizeof(unsigned short)) {
        printf("FAIL: Element typedef narrower than unsigned short\n");
        return 1;
    }
    if (Element_fire == Element_ice || Element_ice == Element_lightning
        || Element_fire == Element_lightning) {
        printf("FAIL: Element members not distinct\n");
        return 1;
    }
    if (Element_fire != 0 || Element_ice != 1 || Element_lightning != 2) {
        printf("FAIL: Element member values wrong\n");
        return 1;
    }

    /* Rarity: declared u32 -- confirm genuinely 32-bit-capable, not
       silently narrowed to 16 or 8 bits. */
    if (sizeof(Rarity) < sizeof(unsigned long)) {
        printf("FAIL: Rarity typedef narrower than unsigned long\n");
        return 1;
    }
    if (Rarity_common == Rarity_rare) {
        printf("FAIL: Rarity members not distinct\n");
        return 1;
    }
    if (Rarity_common != 0 || Rarity_rare != 1) {
        printf("FAIL: Rarity member values wrong\n");
        return 1;
    }

    /* Fields actually using the wider domains, via real instances. */
    if (Creature_Instances[Creature_Goblin_Index].rarity != Rarity_common) {
        printf("FAIL: Goblin.rarity\n");
        return 1;
    }
    if (Creature_Instances[Creature_Archer_Index].rarity != Rarity_rare) {
        printf("FAIL: Archer.rarity\n");
        return 1;
    }
    if (Item_Instances[Item_Sword_Index].element != Element_fire) {
        printf("FAIL: Sword.element\n");
        return 1;
    }
    if (Item_Instances[Item_Shield_Index].element != Element_ice) {
        printf("FAIL: Shield.element\n");
        return 1;
    }

    /* --- string fields --- */
    if (strcmp(Item_Instances[Item_Sword_Index].name, "Sword") != 0) {
        printf("FAIL: Sword.name\n");
        return 1;
    }
    if (strcmp(Item_Instances[Item_Shield_Index].name, "Shield") != 0) {
        printf("FAIL: Shield.name\n");
        return 1;
    }
    /* Confirm the array is genuinely 16 bytes (declared size), not
       just "big enough for these particular strings". */
    if (sizeof(Item_Instances[0].name) != 16) {
        printf("FAIL: name field not 16 bytes\n");
        return 1;
    }

    /* Preexisting checks (regression, unaffected by this round). */
    if (Creature_Instances[Creature_Goblin_Index].hp != 10) {
        printf("FAIL: Goblin.hp\n");
        return 1;
    }
    if (Item_Instances[Item_Sword_Index].object.something1 != 5) {
        printf("FAIL: Sword.object.something1\n");
        return 1;
    }

    printf("All 68000/vbcc AoS (width + string) checks passed.\n");
    return 0;
}
