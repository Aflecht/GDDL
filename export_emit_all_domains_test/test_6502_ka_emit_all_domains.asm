.label ResultCommon = $F0
.label ResultRare   = $F1
.label ResultEpic   = $F2

*=$C000

#import "generated_6502_ka_emit_ON.asm"

Rarity_common_Handler: rts
Rarity_rare_Handler:   rts
Rarity_epic_Handler:   rts

Main:
	lda #Rarity_common
	sta ResultCommon
	lda #Rarity_rare
	sta ResultRare
	lda #Rarity_epic
	sta ResultEpic
AfterChecks:
	brk
