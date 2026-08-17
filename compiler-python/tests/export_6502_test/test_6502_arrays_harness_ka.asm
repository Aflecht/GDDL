// KickAssembler counterpart of test_6502_arrays_harness.asm. Pure data
// check -- no code execution needed. Output is always PRG format (2-byte
// load-address header); the runner handles this via load_prg_kickassembler().

*=$C000

#import "generated_6502_arrays_ka.asm"

Main:
	brk
