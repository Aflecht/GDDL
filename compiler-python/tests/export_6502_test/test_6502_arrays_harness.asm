; Real assemble/execute validation harness for the arrays feature (ACME
; dialect). Pure data check -- no code execution needed, array fields are
; just bytes, read directly from memory via the symbol table after
; assembly (matching every other data-only check in this project).

* = $C000

!source "generated_6502_arrays.asm"

Main:
	BRK	; halt -- py65 driver stops here and inspects memory
