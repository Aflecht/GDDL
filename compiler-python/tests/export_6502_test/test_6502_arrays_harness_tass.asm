; 64tass counterpart of test_6502_arrays_harness.asm. Pure data check --
; no code execution needed.

* = $C000

.include "generated_6502_arrays_tass.asm"

Main
	brk
