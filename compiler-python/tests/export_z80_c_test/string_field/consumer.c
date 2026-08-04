#include "gddl_z80_export.h"
char result_name[12];
void run(void) {
    const Villager *v = Villager_Find(Villager_Grubnik_Index);
    unsigned char i;
    for (i = 0; i < 12; i++) {
        result_name[i] = v->name[i];
    }
}
