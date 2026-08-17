#include "gddl_z80_export.h"
unsigned char result_damage_min;
unsigned char result_damage_max;
unsigned char result_grid00;
unsigned char result_grid12;
char result_name0_0;
char result_name1_1;
void run(void) {
    result_damage_min = Enemy_damage_min_max[Enemy_Goblin_Index][0];
    result_damage_max = Enemy_damage_min_max[Enemy_Goblin_Index][1];
    result_grid00 = Enemy_grid[Enemy_Goblin_Index][0][0];
    result_grid12 = Enemy_grid[Enemy_Goblin_Index][1][2];
    result_name0_0 = Enemy_names[Enemy_Goblin_Index][0][0];
    result_name1_1 = Enemy_names[Enemy_Goblin_Index][1][1];
}
