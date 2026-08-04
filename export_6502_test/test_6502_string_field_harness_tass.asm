; 64tass counterpart of test_6502_string_field_harness.asm. Same logic,
; confirmed directly (not assumed from ACME) that:
;   (a) `.text "Grübnik"` passes raw UTF-8 bytes through byte-for-byte.
;   (b) `.byte "Grübnik"` is a hard syntax error (identical restriction
;       to ACME's !byte -- neither accepts a multi-char string literal).
;   (c) ZP symbol forward references work correctly in 64tass (unlike
;       ACME) -- no need to define IndirLo/IndirHi before their use.
;
; The -Wportable warning about absolute include paths is benign and
; expected when assembling standalone outside the project root.

IndirLo    = $F8
IndirHi    = $F9
ResultAddr = $C100

*=$C000

.include "generated_6502_string_field_tass.asm"

Main
    ldx #Villager_Grubnik_Index
    jsr Villager_Find
    lda Villager_RegistryPtr
    sta IndirLo
    lda Villager_RegistryPtr+1
    sta IndirHi
    ldy #0
CopyLoop
    lda (IndirLo),y
    sta ResultAddr,y
    iny
    cpy #$0C
    bne CopyLoop
AfterCopy
    brk
