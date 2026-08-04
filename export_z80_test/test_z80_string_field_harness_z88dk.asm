; z88dk-z80asm counterpart of test_z80_string_field_harness.asm -- same
; logic, real second assembler. Confirmed directly (not assumed) that
; `db "text", 0, ...` with raw multi-byte UTF-8 content assembles
; identically here and on SjASMPlus, but `ds N, fill` / `djnz` syntax
; is checked independently too, per this project's repeated experience
; of these two dialects disagreeing on small points.

	org $8000
	include "generated_z80_string_field_z88dk.asm"

Main:
	ld a, Villager_Grubnik_Index
	call Villager_Find
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
