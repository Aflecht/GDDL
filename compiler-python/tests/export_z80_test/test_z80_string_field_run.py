# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validates the generated Z80/SjASMPlus output for a `string N` field --
closes the last remaining item from HANDOFF.md's Z80 known-gap note
(composition and u16 were closed separately; this closes string
fields). Same standard as every other target: real assemble, real
execute, not just "should work".

Run from export_z80_test/ after:
  sjasmplus --raw=test_z80_string_field_harness.bin \
            --sym=test_z80_string_field_harness.sym \
            test_z80_string_field_harness.asm
"""

import z80
from z80_test_helper import load_symbols, run_to_pc


def main():
    with open("test_z80_string_field_harness.bin", "rb") as f:
        code = f.read()
    symbols = load_symbols("test_z80_string_field_harness.sym")

    m = z80.Z80Machine()
    m.set_memory_block(0x8000, code)
    m.pc = symbols["Main"]

    run_to_pc(m, symbols["AfterCopy"])

    result_addr = symbols["Result"]
    result_bytes = bytes(m.memory[result_addr + i] for i in range(12))
    expected = "Grübnik".encode("utf-8") + b"\x00" * 4

    print(f"  got:      {result_bytes.hex(' ')}")
    print(f"  expected: {expected.hex(' ')}")
    if result_bytes != expected:
        raise SystemExit("String field (SjASMPlus) check FAILED")

    decoded = result_bytes.split(b"\x00")[0].decode("utf-8")
    print(f"  decoded (up to first NUL): {decoded!r}  (want 'Grübnik')")
    if decoded != "Grübnik":
        raise SystemExit("String field (SjASMPlus) decode check FAILED")

    print("All Z80/SjASMPlus string-field checks passed.")


if __name__ == "__main__":
    main()
