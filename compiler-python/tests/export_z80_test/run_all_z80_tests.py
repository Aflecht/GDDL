# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Driver for this directory's real-toolchain Z80 checks. Every
test_z80_*_run.py in this directory already validates against a real
assembled binary executed on the real `z80` PyPI emulator -- what was
missing was the assembly step itself, previously only documented as a
manual command in each script's own docstring ("Run from
export_z80_test/ after: sjasmplus --raw=... --sym=... <file>.asm").
This script runs that exact command for both Z80 dialects (SjASMPlus
and z88dk-z80asm) against every committed harness, then runs the
corresponding check script, so the whole real-assemble-then-execute
pipeline is one command instead of a manual multi-step recipe.

Tool locations default to this repo's own compiler-python/tools/
(see HANDOFF.md's "Windows portability pass" entry for how the
binaries got there and why they're not committed to git), overridable
via the SJASMPLUS / Z88DK_Z80ASM environment variables for anyone with
the tools installed elsewhere or on PATH.

Run directly: python run_all_z80_tests.py
"""

import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.normpath(os.path.join(_DIR, "..", "..", "tools"))

SJASMPLUS = os.environ.get(
    "SJASMPLUS", os.path.join(_TOOLS, "sjasmplus", "sjasmplus.exe"))
Z88DK_Z80ASM = os.environ.get(
    "Z88DK_Z80ASM", os.path.join(_TOOLS, "z88dk", "z88dk", "bin", "z88dk-z80asm.exe"))

# (harness stem, check script) -- SjASMPlus dialect, --raw=<stem>.bin
# --sym=<stem>.sym <stem>.asm, matching every script's own docstring.
SJASMPLUS_CASES = [
    ("test_z80_harness", "test_z80_run.py"),
    ("test_z80_soa_harness", "test_z80_soa_run.py"),
    ("test_z80_string_field_harness", "test_z80_string_field_run.py"),
    ("test_z80_composition_u16_harness", "test_z80_composition_u16_run.py"),
    ("test_z80_arrays_harness", "test_z80_arrays_run.py"),
]

# (harness stem, -o output stem, check script) -- z88dk-z80asm dialect,
# -b -m -o<out_stem> <stem>.asm. Output stem deliberately has no
# extension (matches -b's own convention, confirmed in each script's
# docstring); the .map sidecar is <out_stem>.map.
Z88DK_CASES = [
    ("test_z80_harness_z88dk", "test_z80_harness_z88dk_out", "test_z80_z88dk_run.py"),
    ("test_z80_soa_harness_z88dk", "test_z80_soa_harness_z88dk_out", "test_z80_soa_z88dk_run.py"),
    ("test_z80_string_field_harness_z88dk", "test_z80_string_field_harness_z88dk_out",
     "test_z80_string_field_z88dk_run.py"),
    ("test_z80_composition_u16_harness_z88dk", "test_z80_composition_u16_harness_z88dk_out",
     "test_z80_composition_u16_z88dk_run.py"),
    ("test_z80_arrays_harness_z88dk", "test_z80_arrays_harness_z88dk_out",
     "test_z80_arrays_z88dk_run.py"),
]


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_DIR)
    if result.returncode != 0:
        raise SystemExit(
            f"command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")
    return result


def assemble_sjasmplus(stem):
    _run([SJASMPLUS, f"--raw={stem}.bin", f"--sym={stem}.sym", f"{stem}.asm"])


def assemble_z88dk(stem, out_stem):
    _run([Z88DK_Z80ASM, "-b", "-m", f"-o{out_stem}", f"{stem}.asm"])


def run_check(script):
    result = _run([sys.executable, script])
    for line in result.stdout.strip().splitlines():
        print(f"  {line}")


def main():
    if not os.path.isfile(SJASMPLUS):
        raise SystemExit(
            f"SjASMPlus not found at {SJASMPLUS!r} -- set the SJASMPLUS "
            "environment variable to its real path")
    if not os.path.isfile(Z88DK_Z80ASM):
        raise SystemExit(
            f"z88dk-z80asm not found at {Z88DK_Z80ASM!r} -- set the "
            "Z88DK_Z80ASM environment variable to its real path")

    print("=== SjASMPlus dialect ===")
    for stem, script in SJASMPLUS_CASES:
        print(f"-- {script} --")
        assemble_sjasmplus(stem)
        run_check(script)

    print("\n=== z88dk-z80asm dialect ===")
    for stem, out_stem, script in Z88DK_CASES:
        print(f"-- {script} --")
        assemble_z88dk(stem, out_stem)
        run_check(script)

    print("\nALL Z80 REAL-TOOLCHAIN CHECKS PASSED (both dialects, 10/10).")


if __name__ == "__main__":
    main()
