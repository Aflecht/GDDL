; Hand-written validation harness for 6502 SoA (64tass) -- NOT part of
; the generated output. Reads specific instances' flattened field
; values directly BY INDEX, with no lookup/registry involved at all
; (§13.4: on 6502 there is no separate lookup step -- the dense
; declaration-order index reads every SoA field array directly).

*=$C000

; --- results, copied here for easy inspection after halting ---
CreatureHpGoblin      = $E0
CreatureHpArcher      = $E1
CreatureAttackGoblin  = $E2
CreatureAttackArcher  = $E3

ItemSomething1Sword  = $E4
ItemSomething1Shield = $E5
ItemSomething2Sword  = $E6
ItemSomething2Shield = $E7
ItemWeightSword      = $E8
ItemWeightShield     = $E9

.include "generated_6502_soa_tass.asm"

Main:
	; --- Creature: read hp and attack directly by dense index, no
	; lookup at all -- straight absolute-indexed loads. ---
	ldx #Creature_Goblin_Index
	lda Creature_hp,x
	sta CreatureHpGoblin
	lda Creature_attack,x
	sta CreatureAttackGoblin

	ldx #Creature_Archer_Index
	lda Creature_hp,x
	sta CreatureHpArcher
	lda Creature_attack,x
	sta CreatureAttackArcher

	; --- Item: composition flattening produced genuinely separate
	; arrays (object_something1, object_something2, weight) -- read
	; each independently by the same dense index. ---
	ldx #Item_Sword_Index
	lda Item_object_something1,x
	sta ItemSomething1Sword
	lda Item_object_something2,x
	sta ItemSomething2Sword
	lda Item_weight,x
	sta ItemWeightSword

	ldx #Item_Shield_Index
	lda Item_object_something1,x
	sta ItemSomething1Shield
	lda Item_object_something2,x
	sta ItemSomething2Shield
	lda Item_weight,x
	sta ItemWeightShield

	brk	; halt -- py65 driver stops here and inspects memory

; Minimal stubs so the jump table (emitted unconditionally regardless
; of AoS/SoA) assembles cleanly. This test doesn't exercise dispatch
; itself (already covered by the AoS harness); these just need to
; exist as valid targets.
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
