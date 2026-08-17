; Real assemble/execute validation harness for the arrays feature (SjASMPlus
; dialect). Pure data check -- no code execution needed, array fields are
; just bytes, read directly from memory via the symbol table after
; assembly.

	org $8000

	include "generated_z80_arrays.asm"

Main:
	nop
