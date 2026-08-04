// KickAssembler counterpart of test_6502_composition_u16_harness.asm.
// KickAssembler does NOT have ACME's ZP-forward-reference restriction
// (confirmed elsewhere in this project -- its multi-pass label
// resolution handles this correctly), but ZP constants are defined
// first anyway for parity/readability with the ACME version.
//
// Output is always PRG format (2-byte load-address header); the
// runner handles this via load_prg_kickassembler().

.label ResultHp    = $F0
.label ResultMp    = $F2
.label ResultWp    = $F4
.label ResultLevel = $F6

*=$C000

#import "generated_6502_composition_u16_ka.asm"

Main:
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
AfterReads:
	brk
