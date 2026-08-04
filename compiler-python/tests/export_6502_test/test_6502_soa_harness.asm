; Hand-written validation harness for 6502 SoA -- NOT part of the
; generated output. Reads specific instances' flattened field values
; directly BY INDEX, with no lookup/registry involved at all (§13.4:
; on 6502 there is no separate lookup step -- the dense declaration-
; order index reads every SoA field array directly).

* = $C000

; --- results, copied here for easy inspection after halting ---
CreatureHpGoblin      = $E0
CreatureHpArcher       = $E1
CreatureAttackGoblin   = $E2
CreatureAttackArcher   = $E3

ItemSomething1Sword    = $E4
ItemSomething1Shield    = $E5
ItemSomething2Sword    = $E6
ItemSomething2Shield    = $E7
ItemWeightSword        = $E8
ItemWeightShield        = $E9

!source "generated_6502_soa.asm"

Main:
	; --- Creature: read hp and attack directly by dense index, no
	; lookup at all -- straight absolute-indexed loads. ---
	LDX #Creature_Goblin_Index
	LDA Creature_hp,X
	STA CreatureHpGoblin
	LDA Creature_attack,X
	STA CreatureAttackGoblin

	LDX #Creature_Archer_Index
	LDA Creature_hp,X
	STA CreatureHpArcher
	LDA Creature_attack,X
	STA CreatureAttackArcher

	; --- Item: composition flattening produced genuinely separate
	; arrays (object_something1, object_something2, weight) -- read
	; each independently by the same dense index. ---
	LDX #Item_Sword_Index
	LDA Item_object_something1,X
	STA ItemSomething1Sword
	LDA Item_object_something2,X
	STA ItemSomething2Sword
	LDA Item_weight,X
	STA ItemWeightSword

	LDX #Item_Shield_Index
	LDA Item_object_something1,X
	STA ItemSomething1Shield
	LDA Item_object_something2,X
	STA ItemSomething2Shield
	LDA Item_weight,X
	STA ItemWeightShield

	BRK	; halt -- py65 driver stops here and inspects memory

; Minimal stubs so the jump table (emitted unconditionally regardless
; of AoS/SoA -- domains exist independent of instance-data layout)
; assembles cleanly. This test doesn't exercise dispatch itself
; (that's already covered by the AoS harness); these just need to
; exist as valid targets.
ActionAttack_melee_weapon_Handler:
	RTS

ActionAttack_ranged_weapon_Handler:
	RTS

Element_fire_Handler:
	rts

Element_ice_Handler:
	rts

Element_lightning_Handler:
	rts
