; Real assemble/execute validation harness for the pools feature
; (SjASMPlus dialect). A pool declares no compiled-in values at all
; (uninitialized storage, section 22.2) -- the check script writes
; synthetic bytes directly into the pool's own memory region via the
; real symbol addresses, then reads them back, confirming the layout
; the compiler claims (contiguous per-column arrays, u8 stride 1, u16
; stride 2, no Lo/Hi split -- Z80 richer registers, no overlap with
; code) against real assembled/executed output.

	org $8000

	include "generated_z80_pools.asm"

Main:
	nop
