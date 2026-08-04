; Hand-written test harness for §13.2 string-field export on the
; 6502/ACME dialect. Closes the last 6502 implementation gap: no prior
; 6502 fixture exercised a `string N` field end-to-end on any of the
; three dialects.
;
; Source: string_field_6502_minimal.gddl. `Villager.name` is
; `string 12`, holding "Grübnik" -- deliberately non-ASCII (a-umlaut
; is 2 UTF-8 bytes), 8 content bytes + 1 NUL + 3 padding zeros = 12
; total, so an export that assumed 1-byte-per-character, got
; !text/!byte ordering wrong, or miscounted padding would produce an
; observably wrong result.
;
; ACME implementation note: ACME's zero-page detection is single-pass
; and does NOT forward-reference ZP symbols correctly -- using
; `LDA (IndirLo),Y` before `IndirLo` is defined later in the file
; produces "Number does not fit in 8 bits" at assemble time. Fix: all
; ZP symbols must be defined BEFORE the code that uses them. Confirmed
; by attempting the forward-reference form and reading the actual error.

* = $C000

; ZP allocations -- defined first, before any code that uses them.
IndirLo    = $F8
IndirHi    = $F9
ResultAddr = $C100

!source "generated_6502_string_field.asm"

Main:
    ; Resolve Villager_Grubnik via the real Villager_Find subroutine
    ; (not a hand-computed offset into Villager_Grubnik directly).
    LDX #Villager_Grubnik_Index
    JSR Villager_Find
    ; Villager_RegistryPtr now holds the instance address. Copy it
    ; into our own ZP pair for indirect-indexed access.
    LDA Villager_RegistryPtr
    STA IndirLo
    LDA Villager_RegistryPtr+1
    STA IndirHi
    ; Copy all 12 bytes of `name` to ResultAddr page.
    LDY #0
CopyLoop:
    LDA (IndirLo),Y
    STA ResultAddr,Y
    INY
    CPY #$0C
    BNE CopyLoop
AfterCopy:
    BRK     ; py65 driver stops here and reads ResultAddr
