# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
z88dk-z80asm counterpart of test_z80_string_field_run.py. Uses the
.map file (via -m), NOT the .sym file (via -s) -- confirmed directly
that .sym reports pre-org section-relative offsets while .map reports
the actual final absolute addresses embedded in the assembled binary.

Run from export_z80_test/ after:
  z88dk-z80asm -b -m -otest_z80_string_field_harness_z88dk_out \
               test_z80_string_field_harness_z88dk.asm
"""

import z80
from z80_test_helper import load_symbols_z88dk_map, run_to_pc


def main():
    with open("test_z80_string_field_harness_z88dk_out", "rb") as f:
        code = f.read()
    symbols = load_symbols_z88dk_map(
        "test_z80_string_field_harness_z88dk_out.map")

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
        raise SystemExit("String field (z88dk-z80asm) check FAILED")

    decoded = result_bytes.split(b"\x00")[0].decode("utf-8")
    print(f"  decoded (up to first NUL): {decoded!r}  (want 'Grübnik')")
    if decoded != "Grübnik":
        raise SystemExit("String field (z88dk-z80asm) decode check FAILED")

    print("All Z80/z88dk-z80asm string-field checks passed.")


if __name__ == "__main__":
    main()
