// Hand-written test harness for §13.2 string-field export,
// KickAssembler dialect.
//
// Source: string_field_6502_minimal.gddl. Villager.name = string 12,
// value "Grübnik" (8 UTF-8 bytes across 7 chars, non-ASCII deliberately).
//
// KickAssembler-specific notes:
//   - .encoding "ascii" is required in the generated file (it's emitted
//     by the renderer's header) so .text emits raw ASCII byte values
//     rather than PETSCII-converted codes. Without it, lowercase 'r'
//     maps to $12 (PETSCII) instead of $72 (ASCII). Confirmed directly.
//   - For non-ASCII content (.text can't produce UTF-8 byte sequences),
//     the renderer uses split .text/.byte: ASCII runs as .text literals,
//     non-ASCII bytes as explicit .byte $xx hex values. Confirmed working
//     by assembling real output and checking the output bytes.
//   - Output is always PRG format (2-byte load-address header). The
//     test runner handles this via load_prg_kickassembler().
//   - ZP forward-reference restriction (found in ACME) does NOT apply
//     to KickAssembler: .label definitions are resolved in a full multi-
//     pass, not single-pass. Confirmed: placing IndirLo after its use
//     site works correctly here (unlike ACME).

.label IndirLo    = $F8
.label IndirHi    = $F9
.label ResultAddr = $C100

*=$C000

#import "generated_6502_string_field_ka.asm"

Main:
    ldx #Villager_Grubnik_Index
    jsr Villager_Find
    lda Villager_RegistryPtr
    sta IndirLo
    lda Villager_RegistryPtr+1
    sta IndirHi
    ldy #0
CopyLoop:
    lda (IndirLo),y
    sta ResultAddr,y
    iny
    cpy #$0c
    bne CopyLoop
AfterCopy:
    brk
