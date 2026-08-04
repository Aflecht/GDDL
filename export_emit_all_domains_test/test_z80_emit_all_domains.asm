	org $8000
	include "generated_z80_emit_ON.asm"

Rarity_common_Handler:
	ret
Rarity_rare_Handler:
	ret
Rarity_epic_Handler:
	ret

Main:
	; Load each Rarity constant (they're equ values, so load as immediates).
	ld a, Rarity_common
	ld (ResultCommon), a
	ld a, Rarity_rare
	ld (ResultRare), a
	ld a, Rarity_epic
	ld (ResultEpic), a
AfterChecks:
	halt

ResultCommon: db $FF
ResultRare:   db $FF
ResultEpic:   db $FF
