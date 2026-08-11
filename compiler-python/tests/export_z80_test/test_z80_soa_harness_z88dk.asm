; z88dk-z80asm counterpart of test_z80_soa_harness.asm. Same fixture,
; same logic, only the assembler differs -- confirms SoA support
; works identically on both Z80 assembly paths, not just one.

	org $8000
	include "generated_z80_soa_z88dk.asm"

Rarity_common_Handler:
Rarity_rare_Handler:
	ret

Main:
	ld a, Item_Bow_Index
	ld l, a
	ld h, 0
	add hl, hl
	ld de, Item_power
	add hl, de
	ld e, (hl)
	inc hl
	ld d, (hl)
	ld (Result_bow_power), de

	ld a, Item_Sword_Index
	ld l, a
	ld h, 0
	ld de, Item_rarity
	add hl, de
	ld a, (hl)
	ld (Result_sword_rarity), a

	ld a, Item_Shield_Index
	ld l, a
	ld h, 0
	add hl, hl
	ld de, Item_power
	add hl, de
	ld e, (hl)
	inc hl
	ld d, (hl)
	ld (Result_shield_power), de
AfterReads:
	halt

Result_bow_power:
	dw 0
Result_sword_rarity:
	db 0
Result_shield_power:
	dw 0
