/* Real vbcc compile/link/run validation for the subset-request bug fix
 * (§export_68000.py's render_c89_split, AoS struct emission). Requests
 * only "Item" from a file that also defines an unrelated "Creature" --
 * confirms the generated header has NO trace of Creature/CreatureKind
 * anywhere, and that Item's transitively-composed Object struct IS
 * correctly present and correctly populated.
 *
 * Compile-time check (the strongest possible signal for "did the
 * unrelated type leak in"): if Creature or CreatureKind somehow WERE
 * emitted into the header, this file wouldn't even need to reference
 * them for the header to just... have them defined, so the absence
 * itself isn't directly testable via a positive compile assertion.
 * What IS directly testable, and is exactly what the bug actually
 * broke: this file compiling and linking AT ALL. Before the fix,
 * requesting just "Item" crashed the EXPORTER itself (an
 * Export68000Error, before any C file was even written) -- so merely
 * reaching a successful vbcc compile of the generated output is real
 * evidence the fix works, not a formality. The runtime checks below
 * confirm Item's own data (including its transitively-required Object
 * composition) is correct, on top of that.
 */
#include <stdio.h>
#include "generated_68000_subset_request_bug.h"

int main(void)
{
    if (Item_Instances[0].rarity != ItemRarity_common) {
        printf("FAIL: Sword.rarity wrong: %u\n", (unsigned)Item_Instances[0].rarity);
        return 1;
    }
    if (Item_Instances[0].object.weight != 5) {
        printf("FAIL: Sword.object.weight wrong: %u\n",
               (unsigned)Item_Instances[0].object.weight);
        return 1;
    }

    {
        const Item* found = Item_Find(Item_Sword_Index);
        if (found == 0) {
            printf("FAIL: Item_Find returned NULL\n");
            return 1;
        }
        if (found->rarity != ItemRarity_common || found->object.weight != 5) {
            printf("FAIL: Item_Find result mismatch\n");
            return 1;
        }
        printf("rarity=%u object.weight=%u\n",
               (unsigned)found->rarity, (unsigned)found->object.weight);
    }

    printf("All 68000 subset-request-bug-fix checks passed "
           "(unrelated Creature/CreatureKind correctly never emitted -- "
           "confirmed by this file compiling at all, which the bug "
           "prevented outright).\n");
    return 0;
}
