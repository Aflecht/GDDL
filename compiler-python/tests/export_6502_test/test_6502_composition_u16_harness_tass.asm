; 64tass counterpart of test_6502_composition_u16_harness.asm -- same
; logic, real second assembler. 64tass does NOT have ACME's ZP-forward-
; reference restriction (confirmed elsewhere in this project), but the
; ZP constants are defined first anyway for parity/readability with the
; ACME version.

ResultHp    = $F0
ResultMp    = $F2
ResultWp    = $F4
ResultLevel = $F6

*=$C000

.include "generated_6502_composition_u16_tass.asm"

Main
	ldx #Character_Hero_Index
	jsr Character_Find
	ldy #0
	lda (Character_RegistryPtr),y
	sta ResultHp
	iny
	lda (Character_RegistryPtr),y
	sta ResultHp+1
	iny
	lda (Character_RegistryPtr),y
	sta ResultMp
	iny
	lda (Character_RegistryPtr),y
	sta ResultMp+1
	iny
	lda (Character_RegistryPtr),y
	sta ResultWp
	iny
	lda (Character_RegistryPtr),y
	sta ResultWp+1
	iny
	lda (Character_RegistryPtr),y
	sta ResultLevel
	iny
	lda (Character_RegistryPtr),y
	sta ResultLevel+1
AfterReads
	brk
