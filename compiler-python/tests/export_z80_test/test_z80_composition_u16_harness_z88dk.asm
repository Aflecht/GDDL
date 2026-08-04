; z88dk-z80asm counterpart of test_z80_composition_u16_harness.asm --
; same logic, real second assembler, since the two dialects have
; confirmed genuine differences elsewhere (label-colon requirement,
; low()/high() availability) and are never assumed to behave alike
; without direct verification.

	org $8000
	include "generated_z80_composition_u16_z88dk.asm"

Main:
	ld a, Character_Hero_Index
	call Character_Find
	ld e, (hl)
	inc hl
	ld d, (hl)
	inc hl
	ld (Result_hp), de
	ld e, (hl)
	inc hl
	ld d, (hl)
	inc hl
	ld (Result_mp), de
	ld e, (hl)
	inc hl
	ld d, (hl)
	inc hl
	ld (Result_weapon_power), de
	ld e, (hl)
	inc hl
	ld d, (hl)
	ld (Result_level), de
AfterReads:
	halt

Result_hp:
	dw 0
Result_mp:
	dw 0
Result_weapon_power:
	dw 0
Result_level:
	dw 0
