; Hand-written test harness closing a real gap: existing 6502 fixtures
; cover composition (none directly, actually -- see HANDOFF) and u16
; only as an identifier-domain width, never a genuine scalar u16 field
; sitting inside a composed type. This fixture is exactly that
; combination, ported from the Z80 target where it was first validated.
;
; Source: composition_nested_u16_fields.gddl. Character composes Stats
; (hp, mp) and Equipment (weapon_power), flattened to one dense AoS
; record: stats_hp, stats_mp, equipment_weapon_power, level -- all u16,
; 8 bytes total. Values (60000, 12000, 500) deliberately exceed 255 so
; an export that assumed 8-bit storage, or got byte order wrong, would
; produce an observably wrong result.
;
; Resolves Character_Hero via the real Character_Find subroutine (not
; a hand-computed offset), then reads all four u16 fields back through
; the resolved zero-page pointer exactly as a real caller would.

; ZP allocations -- defined BEFORE any code that uses them (ACME's
; zero-page detection is single-pass and does not forward-reference;
; confirmed and documented already in test_6502_string_field_harness.asm).
ResultHp    = $F0
ResultMp    = $F2
ResultWp    = $F4
ResultLevel = $F6

* = $C000

!source "generated_6502_composition_u16.asm"

Main:
	LDX #Character_Hero_Index
	JSR Character_Find
	; Character_RegistryPtr -> Character_Hero (8 bytes: hp, mp,
	; weapon_power, level, each u16 little-endian).
	LDY #0
	LDA (Character_RegistryPtr),Y
	STA ResultHp
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultHp+1
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultMp
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultMp+1
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultWp
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultWp+1
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultLevel
	INY
	LDA (Character_RegistryPtr),Y
	STA ResultLevel+1
AfterReads:
	BRK
