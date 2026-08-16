# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validation test for --zp-base's two required checks (§10.2):
(a) the value itself is a valid zero-page address (0-255 / $00-$FF).
(b) the highest byte actually allocated (base + total 2-byte blocks
    needed, across every registry and dispatch consumer combined)
    doesn't exceed $FF.

Both are hard export-time errors, never silently wrapped/clamped --
same principle as §5's numeric range enforcement. This script is a
persistent regression check, not just an ad hoc one-off: run directly
to confirm both failure modes still fail cleanly, with informative
messages (naming the actual bytes needed and the highest resulting
address, not just "out of range").
"""

import os
import sys

# Found during the repository restructuring sweep: this script had NO
# sys.path setup at all, relying entirely on the pre-restructuring flat
# layout where the pipeline modules sat in the same directory the test
# scripts were run from. Every sibling script in this project already
# handles this explicitly (see export_golden.py, verify_shift_add.py);
# this one was simply missed until a systematic grep for "imports the
# pipeline without any sys.path setup" surfaced it -- exactly the kind
# of gap a manual pass alone would likely have missed.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from gddl.parser import parse_file
from gddl.resolve import resolve_all
from gddl.export_6502 import gather_ir, allocate_zero_page, Export6502Error


def main():
    prog = parse_file("export_test_6502_minimal.gddl")
    resolver = resolve_all(prog)

    # ---- (a) out-of-range zp_base VALUE itself (not missing/None --
    # that's covered separately by --zp-base's required=True argparse
    # flag). A genuine bad number: negative, or >255. ----
    print("=== (a) out-of-range zp_base value ===")
    for bad in (-1, 256, 1000):
        try:
            domains, types = gather_ir(resolver.reg, resolver, ["Creature"], bad)
            print(f"  {bad}: NO ERROR (FAIL -- this should have been rejected)")
        except Export6502Error as e:
            print(f"  {bad}: correctly rejected -- {e}")

    # ---- (b) genuine overflow: enough real consumers (2 types with
    # registries + 2 domains with dispatch = 4 consumers x 2 bytes = 8
    # bytes needed) combined with a base near the top of the zero page
    # that the last block spills past $FF. ----
    print()
    print("=== (b) genuine zero-page overflow (4 real consumers, base=$FC) ===")
    domains, types = gather_ir(resolver.reg, resolver, ["Creature", "Item"], 0xFC)
    assert len(types) == 2 and len(domains) == 2, (
        "test setup assumption broken -- expected exactly 2 types and 2 "
        "domains so this is a genuine, non-trivial overflow, not a "
        "coincidental one-consumer case"
    )
    try:
        allocate_zero_page(0xFC, domains, types, layout="aos")
        print("  NO ERROR (FAIL -- this should have overflowed)")
    except Export6502Error as e:
        print(f"  correctly rejected -- {e}")
        assert "$103" in str(e), "message should name the actual highest resulting address"
        assert "8" in str(e), "message should name the actual total bytes needed"

    # ---- sanity: the SAME 4 consumers at a low base do NOT overflow,
    # confirming (b) isn't just rejecting everything. ----
    print()
    print("=== sanity: same 4 consumers, base=$F0 (no overflow expected) ===")
    zp = allocate_zero_page(0xF0, domains, types, layout="aos")
    print("  registry_blocks:", {k: hex(v) for k, v in zp.registry_blocks.items()})
    print("  dispatch_blocks:", {k: hex(v) for k, v in zp.dispatch_blocks.items()})
    print("  correctly succeeded, as expected")


if __name__ == "__main__":
    main()
