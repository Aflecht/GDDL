#include "gddl_z80_export.h"
unsigned int result_hp;
unsigned int result_mp;
unsigned int result_weapon;
unsigned int result_level;
void run(void) {
    const Character *c = Character_Find(Character_Hero_Index);
    result_hp = c->stats_hp;
    result_mp = c->stats_mp;
    result_weapon = c->equipment_weapon_power;
    result_level = c->level;
}
