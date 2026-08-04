// Hand-written validation harness -- NOT part of the generated output.
// Exercises the generated Dispatch subroutines (now generated output,
// §10.2 update) and Find (zero-page-allocated named pointers)
// for TWO domains and TWO types.

*=$C000

.label GoblinSignal    = $E0
.label ArcherSignal    = $E1
.label FireSignal      = $E2
.label IceSignal       = $E3
.label LightningSignal = $E4
.label Signal          = $E5

.label CreatureGoblinPtrLo = $D0
.label CreatureGoblinPtrHi = $D1
.label CreatureArcherPtrLo = $D2
.label CreatureArcherPtrHi = $D3
.label ItemSwordPtrLo      = $D4
.label ItemSwordPtrHi      = $D5
.label ItemShieldPtrLo     = $D6
.label ItemShieldPtrHi     = $D7

#import "generated_6502_minimal_ka.asm"

Main:
	// --- dispatch: ActionAttack, both members ---
	ldx #ActionAttack_melee_weapon
	jsr ActionAttack_Dispatch
	lda Signal
	sta GoblinSignal

	ldx #ActionAttack_ranged_weapon
	jsr ActionAttack_Dispatch
	lda Signal
	sta ArcherSignal

	// --- dispatch: Element, all three members ---
	ldx #Element_fire
	jsr Element_Dispatch
	lda Signal
	sta FireSignal

	ldx #Element_ice
	jsr Element_Dispatch
	lda Signal
	sta IceSignal

	ldx #Element_lightning
	jsr Element_Dispatch
	lda Signal
	sta LightningSignal

	// --- registry: Creature, both instances ---
	ldx #Creature_Goblin_Index
	jsr Creature_Find
	lda Creature_RegistryPtr
	sta CreatureGoblinPtrLo
	lda Creature_RegistryPtr+1
	sta CreatureGoblinPtrHi

	ldx #Creature_Archer_Index
	jsr Creature_Find
	lda Creature_RegistryPtr
	sta CreatureArcherPtrLo
	lda Creature_RegistryPtr+1
	sta CreatureArcherPtrHi

	// --- registry: Item, both instances ---
	ldx #Item_Sword_Index
	jsr Item_Find
	lda Item_RegistryPtr
	sta ItemSwordPtrLo
	lda Item_RegistryPtr+1
	sta ItemSwordPtrHi

	ldx #Item_Shield_Index
	jsr Item_Find
	lda Item_RegistryPtr
	sta ItemShieldPtrLo
	lda Item_RegistryPtr+1
	sta ItemShieldPtrHi

	brk

ActionAttack_melee_weapon_Handler:
	lda #1
	sta Signal
	rts

ActionAttack_ranged_weapon_Handler:
	lda #2
	sta Signal
	rts

Element_fire_Handler:
	lda #3
	sta Signal
	rts

Element_ice_Handler:
	lda #4
	sta Signal
	rts

Element_lightning_Handler:
	lda #5
	sta Signal
	rts
