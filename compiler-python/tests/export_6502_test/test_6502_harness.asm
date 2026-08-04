; Hand-written validation harness -- NOT part of the generated output.
; Exercises the generated Dispatch subroutines (now generated output,
; §10.2 update) and Find (now using zero-page-allocated named
; pointers instead of a hardcoded address) for TWO domains and TWO
; types, confirming the deterministic block-assignment ordering
; actually matters (not trivially "only one thing exists").

* = $C000

GoblinSignal    = $E0
ArcherSignal    = $E1
FireSignal      = $E2
IceSignal       = $E3
LightningSignal = $E4
Signal          = $E5   ; last dispatch handler's marker value

CreatureGoblinPtrLo = $D0
CreatureGoblinPtrHi = $D1
CreatureArcherPtrLo = $D2
CreatureArcherPtrHi = $D3
ItemSwordPtrLo      = $D4
ItemSwordPtrHi      = $D5
ItemShieldPtrLo     = $D6
ItemShieldPtrHi     = $D7

!source "generated_6502_minimal.asm"

Main:
	; --- dispatch: ActionAttack, both members ---
	LDX #ActionAttack_melee_weapon
	JSR ActionAttack_Dispatch
	LDA Signal
	STA GoblinSignal   ; reused name, just means "melee ran"

	LDX #ActionAttack_ranged_weapon
	JSR ActionAttack_Dispatch
	LDA Signal
	STA ArcherSignal   ; "ranged ran"

	; --- dispatch: Element, all three members ---
	LDX #Element_fire
	JSR Element_Dispatch
	LDA Signal
	STA FireSignal

	LDX #Element_ice
	JSR Element_Dispatch
	LDA Signal
	STA IceSignal

	LDX #Element_lightning
	JSR Element_Dispatch
	LDA Signal
	STA LightningSignal

	; --- registry: Creature, both instances, via the generated
	; Creature_RegistryPtr named constant (not a hardcoded address) ---
	LDX #Creature_Goblin_Index
	JSR Creature_Find
	LDA Creature_RegistryPtr
	STA CreatureGoblinPtrLo
	LDA Creature_RegistryPtr+1
	STA CreatureGoblinPtrHi

	LDX #Creature_Archer_Index
	JSR Creature_Find
	LDA Creature_RegistryPtr
	STA CreatureArcherPtrLo
	LDA Creature_RegistryPtr+1
	STA CreatureArcherPtrHi

	; --- registry: Item, both instances, via Item_RegistryPtr --
	; a DIFFERENT zero-page block than Creature's, confirming
	; non-overlapping allocation actually matters here (both
	; registries get used in the same run without clobbering
	; each other's pointer). ---
	LDX #Item_Sword_Index
	JSR Item_Find
	LDA Item_RegistryPtr
	STA ItemSwordPtrLo
	LDA Item_RegistryPtr+1
	STA ItemSwordPtrHi

	LDX #Item_Shield_Index
	JSR Item_Find
	LDA Item_RegistryPtr
	STA ItemShieldPtrLo
	LDA Item_RegistryPtr+1
	STA ItemShieldPtrHi

	BRK	; halt -- py65 driver stops here and inspects memory

ActionAttack_melee_weapon_Handler:
	LDA #1
	STA Signal
	RTS

ActionAttack_ranged_weapon_Handler:
	LDA #2
	STA Signal
	RTS

Element_fire_Handler:
	LDA #3
	STA Signal
	RTS

Element_ice_Handler:
	LDA #4
	STA Signal
	RTS

Element_lightning_Handler:
	LDA #5
	STA Signal
	RTS
