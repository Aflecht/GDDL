# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Driver for this directory's real-toolchain 6502 checks, mirroring
export_z80_test/run_all_z80_tests.py's role for Z80. Every
test_6502_*_run.py in this directory already validates against a real
assembled binary executed on the real `py65` emulator -- what was
missing was the assembly step itself, previously only documented as a
manual command in each script's own docstring. This script runs that
exact command for all three 6502 dialects (ACME, 64tass,
KickAssembler) against every committed harness, then runs the
corresponding check script.

Tool locations default to this repo's own compiler-python/tools/
(see HANDOFF.md's "Real 6502 toolchain installed and verified on this
Windows machine" entry for how the binaries got there and why they're
not committed to git), overridable via the ACME / TASS64 / KICKASS_JAR
/ JAVA environment variables for anyone with the tools installed
elsewhere or on PATH.

Run directly: python run_all_6502_tests.py
"""

import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.normpath(os.path.join(_DIR, "..", "..", "tools"))

ACME = os.environ.get("ACME", os.path.join(_TOOLS, "acme", "acme.exe"))
TASS64 = os.environ.get("TASS64", os.path.join(_TOOLS, "64tass", "64tass.exe"))
KICKASS_JAR = os.environ.get(
    "KICKASS_JAR", os.path.join(_TOOLS, "kickassembler", "KickAss.jar"))
JAVA = os.environ.get(
    "JAVA", os.path.join(_TOOLS, "jre", "jdk-17.0.20+8-jre", "bin", "java.exe"))

# (harness stem, check script) -- ACME dialect: -o <stem>.bin
# --format plain --symbollist <stem>.sym <stem>.asm, matching every
# script's own docstring.
ACME_CASES = [
    ("test_6502_harness", "test_6502_run.py"),
    ("test_6502_string_field_harness", "test_6502_string_field_run.py"),
    ("test_6502_composition_u16_harness", "test_6502_composition_u16_run.py"),
    ("test_6502_arrays_harness", "test_6502_arrays_run.py"),
    ("test_6502_pools_harness", "test_6502_pools_run.py"),
]

# (harness stem, check script) -- 64tass dialect: --nostart -o <stem>.bin
# -l <stem>.lst <stem>.asm.
TASS64_CASES = [
    ("test_6502_harness_tass", "test_6502_tass_run.py"),
    ("test_6502_string_field_harness_tass", "test_6502_string_field_tass_run.py"),
    ("test_6502_composition_u16_harness_tass", "test_6502_composition_u16_tass_run.py"),
    ("test_6502_arrays_harness_tass", "test_6502_arrays_tass_run.py"),
    ("test_6502_pools_harness_tass", "test_6502_pools_tass_run.py"),
]

# (harness stem, check script) -- KickAssembler dialect: java -jar
# KickAss.jar <stem>.asm -o <stem>.prg (the .sym file is written
# automatically alongside the .prg, same basename).
KICKASS_CASES = [
    ("test_6502_harness_ka", "test_6502_ka_run.py"),
    ("test_6502_string_field_harness_ka", "test_6502_string_field_ka_run.py"),
    ("test_6502_composition_u16_harness_ka", "test_6502_composition_u16_ka_run.py"),
    ("test_6502_arrays_harness_ka", "test_6502_arrays_ka_run.py"),
    ("test_6502_pools_harness_ka", "test_6502_pools_ka_run.py"),
]


def _run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_DIR)
    if result.returncode != 0:
        raise SystemExit(
            f"command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}\n"
            f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}")
    return result


def assemble_acme(stem):
    _run([ACME, "-o", f"{stem}.bin", "--format", "plain",
          "--symbollist", f"{stem}.sym", f"{stem}.asm"])


def assemble_tass64(stem):
    _run([TASS64, "--nostart", "-o", f"{stem}.bin", "-l", f"{stem}.lst", f"{stem}.asm"])


def assemble_kickass(stem):
    # -symbolfile is required -- confirmed directly against the real jar
    # (v5.25): without it, no .sym file is written at all, which every
    # check script in this directory depends on to read back label
    # addresses. Not previously caught because the KickAssembler jar was
    # never actually present in this environment until now.
    _run([JAVA, "-jar", KICKASS_JAR, f"{stem}.asm", "-o", f"{stem}.prg", "-symbolfile"])


def run_check(script):
    result = _run([sys.executable, script])
    for line in result.stdout.strip().splitlines():
        print(f"  {line}")


def main():
    for name, path in (("ACME", ACME), ("64tass", TASS64),
                        ("KickAssembler jar", KICKASS_JAR), ("Java", JAVA)):
        if not os.path.isfile(path):
            raise SystemExit(f"{name} not found at {path!r}")

    print("=== ACME dialect ===")
    for stem, script in ACME_CASES:
        print(f"-- {script} --")
        assemble_acme(stem)
        run_check(script)

    print("\n=== 64tass dialect ===")
    for stem, script in TASS64_CASES:
        print(f"-- {script} --")
        assemble_tass64(stem)
        run_check(script)

    print("\n=== KickAssembler dialect ===")
    for stem, script in KICKASS_CASES:
        print(f"-- {script} --")
        assemble_kickass(stem)
        run_check(script)

    print("\nALL 6502 REAL-TOOLCHAIN CHECKS PASSED (all three dialects, 15/15).")


if __name__ == "__main__":
    main()
