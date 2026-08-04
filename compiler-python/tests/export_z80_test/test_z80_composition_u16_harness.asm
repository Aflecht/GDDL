; Hand-written test harness for the composition + wide-domain (u16)
; gap flagged in HANDOFF.md: the only prior Z80 fixture (Creature) had
; a single flat u8 field, so neither nested `define` composition nor a
; u16 field had ever actually been compiled+assembled+executed on real
; toolchains, only accepted by the type tables in principle.
;
; Source fixture: composition_nested_u16_fields.gddl (Test Corpus).
; `Character` composes `Stats` (hp, mp) and `Equipment` (weapon_power),
; flattened to one dense AoS record: stats_hp, stats_mp,
; equipment_weapon_power, level -- all u16/dw, sizeof 8. Values chosen
; by Test Corpus specifically to exceed 255 (60000, 12000, 500), so an
; export that silently truncated to 8-bit storage or got byte order
; wrong would produce an observably wrong result, not one that happens
; to work by coincidence.
;
; Resolves Character_Hero via the real Character_Find subroutine (not
; a hand-computed offset into Character_Instances), then reads all four
; fields out through HL exactly as a real caller would.

	org $8000
	include "generated_z80_composition_u16.asm"

Main:
	ld a, Character_Hero_Index
	call Character_Find
	; HL -> Character_Hero. Field order matches the flattened struct:
	; +0 stats_hp, +2 stats_mp, +4 equipment_weapon_power, +6 level
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
