// KickAssembler counterpart of test_6502_pools_harness.asm. A pool
// declares no compiled-in values at all (uninitialized storage, section
// 22.2) -- the check script writes synthetic bytes directly into the
// pool's own memory region via the real symbol addresses, then reads
// them back. Output is always PRG format (2-byte load-address header);
// the runner handles this via load_prg_kickassembler().

*=$C000

#import "generated_6502_pools_ka.asm"

Main:
	brk
