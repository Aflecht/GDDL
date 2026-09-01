; z88dk-z80asm counterpart of test_z80_pools_harness.asm. A pool
; declares no compiled-in values at all (uninitialized storage, section
; 22.2) -- the check script writes synthetic bytes directly into the
; pool's own memory region via the real addresses (parsed from the
; generated .asm's own `equ` lines -- z88dk-z80asm's -m map output does
; not include equ-defined constants, only real address labels, a known
; gap from this project's own 6502/Z80 pool export stage), then reads
; them back.

	org $8000

	include "generated_z80_pools_z88dk.asm"

Main:
	nop
