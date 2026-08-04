#include "gddl_z80_export.h"
unsigned char result_hp;
unsigned char result_attack;
void run_a(void) {
    const Creature *c = Creature_Find(Creature_Archer_Index);
    result_hp = c->hp;
    result_attack = c->attack;
}
