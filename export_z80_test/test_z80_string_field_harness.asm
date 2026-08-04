; Hand-written test harness closing the last remaining gap flagged in
; HANDOFF.md: no prior Z80 fixture (Creature: flat u8; Character:
; composed u16) ever exercised a `string N` field, on any of the three
; output paths, end-to-end on real toolchains.
;
; Source fixture: string_field_minimal.gddl. `Villager.name` is
; `string 12`, holding "Grübnik" -- deliberately non-ASCII (a-umlaut
; is 2 UTF-8 bytes), 8 content bytes + 1 terminator + 3 padding zeros
; = 12 total, so an export that assumed 1-byte-per-character, or got
; padding/byte-order wrong, would produce an observably wrong result.
;
; Resolves Villager_Grubnik via the real Villager_Find subroutine (not
; a hand-computed offset), then copies all 12 bytes of the `name`
; field out through HL exactly as a real caller would, byte by byte
; (no `ld (nn), hl`-style word copy available for a 12-byte field).

	org $8000
	include "generated_z80_string_field.asm"

Main:
	ld a, Villager_Grubnik_Index
	call Villager_Find
	; HL -> Villager_Grubnik. Copy all 12 bytes of `name` to Result.
	ld de, Result
	ld b, 12
CopyLoop:
	ld a, (hl)
	ld (de), a
	inc hl
	inc de
	djnz CopyLoop
AfterCopy:
	halt

Result:
	ds 12, 0
