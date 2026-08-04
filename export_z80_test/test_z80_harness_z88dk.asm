; Hand-written validation harness -- NOT part of the generated output.
; Exercises the generated Dispatch subroutine and Find against
; the real z88dk-z80asm-assembled output, executed via the z80 PyPI
; library's bare-CPU emulation (single-step-based, the confirmed-
; reliable mechanism from the SjASMPlus round -- see z80_test_helper.py).

	org $8000

Main:
	; --- Test 1: dispatch for Goblin's attack (melee_weapon, index 0) ---
	ld a, ActionAttack_melee_weapon
	call ActionAttack_Dispatch
AfterDispatch1:
	nop

	; --- Test 2: dispatch for Archer's attack (ranged_weapon, index 1) ---
	ld a, ActionAttack_ranged_weapon
	call ActionAttack_Dispatch
AfterDispatch2:
	nop

	; --- Test 3: registry lookup, Goblin (dense index 0) ---
	ld a, Creature_Goblin_Index
	call Creature_Find
AfterLookup1:
	nop

	; --- Test 4: registry lookup, Archer (dense index 1) ---
	ld a, Creature_Archer_Index
	call Creature_Find
AfterLookup2:
	nop

Done:
	halt

Signal:
	db 0

ActionAttack_melee_weapon_Handler:
	ld a, 1
	ld (Signal), a
	ret

ActionAttack_ranged_weapon_Handler:
	ld a, 2
	ld (Signal), a
	ret

	include "generated_z80_minimal_z88dk.asm"
