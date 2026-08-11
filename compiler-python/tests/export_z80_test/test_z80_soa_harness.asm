; Hand-written test harness for §13.7 Z80 SoA support (SjASMPlus).
;
; Closes the gap flagged in HANDOFF.md ("--layout=soa is not
; implemented for Z80 yet"). Fixture: soa_field_minimal.gddl -- a
; u16 field (power) and an identifier-typed field (rarity, domain
; Rarity, width u8), specifically chosen to exercise both the
; shift-based indexing a u16 SoA field array needs (no lo/hi split,
; unlike 6502) and a domain-typed field's array.
;
; SoA has no Find(), no registry (§13.4/§13.7 -- the same dense index
; that identifies an instance in AoS already indexes every SoA field
; array), so this harness computes addresses directly: index*2 (one
; `add hl,hl` shift, never a multiply) for the u16 array, plain
; index*1 for the u8/domain array.

	org $8000
	include "generated_z80_soa.asm"

; Rarity_JumpTable references these -- stubbed since this harness
; reads the raw stored domain index directly, never dispatches.
Rarity_common_Handler:
Rarity_rare_Handler:
	ret

Main:
	; Bow (index 1): power field, u16, shift-indexed
	ld a, Item_Bow_Index
	ld l, a
	ld h, 0
	add hl, hl		; index * 2 -- a shift, never a multiply
	ld de, Item_power
	add hl, de
	ld e, (hl)
	inc hl
	ld d, (hl)
	ld (Result_bow_power), de

	; Sword (index 0): rarity field, u8/domain, direct-indexed
	ld a, Item_Sword_Index
	ld l, a
	ld h, 0
	ld de, Item_rarity
	add hl, de
	ld a, (hl)
	ld (Result_sword_rarity), a

	; Shield (index 2): power field again, confirms every row, not
	; just row 0/1
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
