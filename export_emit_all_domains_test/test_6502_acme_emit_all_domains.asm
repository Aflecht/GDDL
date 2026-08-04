; Hand-written test harness for --emit-all-domains on the 6502/ACME
; dialect. The investigation fixture (Rarity domain, declared u8, zero
; field references in any exported type) is the permanent test case
; following the "real fixture rather than infer from comments" standard.
;
; This harness is intentionally simple: it doesn't need to assemble,
; link, and *run* a dispatch subroutine through the Rarity domain (the
; fixture has no instances of any Rarity-typed field), because the
; claim under test is purely structural -- "are the constants present
; with the right values." Confirmed by assembling the generated output
; with the flag ON and checking that the symbolic constants resolve to
; the expected 0-based dense index values. The py65 execution loop
; reads these back from memory rather than trusting the assembler's
; printed diagnostics, same standard as every other test in this thread.

* = $C000

!source "generated_6502_acme_emit_ON.asm"

; Stub handlers required because the generated Rarity_JumpTable references
; them. In real usage these would contain dispatch logic; here they just
; need to exist so the assembler resolves the jump-table addresses.
Rarity_common_Handler: RTS
Rarity_rare_Handler:   RTS
Rarity_epic_Handler:   RTS

Main:
	; Load each Rarity constant and store at known memory addresses.
	; Values: common=0, rare=1, epic=2 (0-based declaration order, §8.4)
	LDA #Rarity_common
	STA ResultCommon
	LDA #Rarity_rare
	STA ResultRare
	LDA #Rarity_epic
	STA ResultEpic
AfterChecks:
	BRK

ResultCommon: !byte $FF
ResultRare:   !byte $FF
ResultEpic:   !byte $FF
