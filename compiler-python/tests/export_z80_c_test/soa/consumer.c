#include "gddl_z80_export.h"
unsigned int result_power_sword;
unsigned int result_power_bow;
unsigned int result_power_shield;
unsigned char result_rarity_sword;
unsigned char result_rarity_bow;
unsigned char result_rarity_shield;
void run(void) {
    result_power_sword = Item_power[Item_Sword_Index];
    result_power_bow = Item_power[Item_Bow_Index];
    result_power_shield = Item_power[Item_Shield_Index];
    result_rarity_sword = Item_rarity[Item_Sword_Index];
    result_rarity_bow = Item_rarity[Item_Bow_Index];
    result_rarity_shield = Item_rarity[Item_Shield_Index];
}
