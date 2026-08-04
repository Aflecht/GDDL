// Hand-written validation harness for 6502 SoA (KickAssembler) -- NOT
// part of the generated output. Reads specific instances' flattened
// field values directly BY INDEX, with no lookup/registry involved at
// all (§13.4: on 6502 there is no separate lookup step -- the dense
// declaration-order index reads every SoA field array directly).

*=$C000

// --- results, copied here for easy inspection after halting ---
.label CreatureHpGoblin      = $E0
.label CreatureHpArcher      = $E1
.label CreatureAttackGoblin  = $E2
.label CreatureAttackArcher  = $E3

.label ItemSomething1Sword  = $E4
.label ItemSomething1Shield = $E5
.label ItemSomething2Sword  = $E6
.label ItemSomething2Shield = $E7
.label ItemWeightSword      = $E8
.label ItemWeightShield     = $E9

#import "generated_6502_soa_ka.asm"

Main:
	// --- Creature: read hp and attack directly by dense index, no
	// lookup at all -- straight absolute-indexed loads. ---
	ldx #Creature_Goblin_Index
	lda Creature_hp,X
	sta CreatureHpGoblin
	lda Creature_attack,X
	sta CreatureAttackGoblin

	ldx #Creature_Archer_Index
	lda Creature_hp,X
	sta CreatureHpArcher
	lda Creature_attack,X
	sta CreatureAttackArcher

	// --- Item: composition flattening produced genuinely separate
	// arrays (object_something1, object_something2, weight) -- read
	// each independently by the same dense index. ---
	ldx #Item_Sword_Index
	lda Item_object_something1,X
	sta ItemSomething1Sword
	lda Item_object_something2,X
	sta ItemSomething2Sword
	lda Item_weight,X
	sta ItemWeightSword

	ldx #Item_Shield_Index
	lda Item_object_something1,X
	sta ItemSomething1Shield
	lda Item_object_something2,X
	sta ItemSomething2Shield
	lda Item_weight,X
	sta ItemWeightShield

	brk	// halt -- py65 driver stops here and inspects memory

// Minimal stubs so the jump table (emitted unconditionally regardless
// of AoS/SoA) assembles cleanly. This test doesn't exercise dispatch
// itself (already covered by the AoS harness); these just need to
// exist as valid targets.
ActionAttack_melee_weapon_Handler:
	rts

ActionAttack_ranged_weapon_Handler:
	rts

Element_fire_Handler:
	rts

Element_ice_Handler:
	rts

Element_lightning_Handler:
	rts
