; Real assemble/execute validation harness for the pools feature (ACME
; dialect). A pool declares no compiled-in values at all (uninitialized
; storage, section 22.2) -- the check script writes synthetic bytes
; directly into the pool's own memory region via the real symbol
; addresses, then reads them back, confirming the layout the compiler
; claims (contiguous per-column arrays, correct stride, no overlap with
; code or zero page) against real assembled/executed output.

* = $C000

!source "generated_6502_pools.asm"

Main:
	BRK	; halt -- py65 driver stops here and inspects memory
