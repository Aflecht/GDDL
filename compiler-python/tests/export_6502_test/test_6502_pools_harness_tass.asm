; 64tass counterpart of test_6502_pools_harness.asm. A pool declares no
; compiled-in values at all (uninitialized storage, section 22.2) -- the
; check script writes synthetic bytes directly into the pool's own
; memory region via the real symbol addresses, then reads them back.

* = $C000

.include "generated_6502_pools_tass.asm"

Main
	brk
