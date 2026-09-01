# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Driver for this directory's real-toolchain 68000 checks, mirroring
export_z80_test/run_all_z80_tests.py and export_6502_test/run_all_6502_tests.py's
role for their targets. Two of these fixture pairs already had a
committed manual recipe (run_composition_u16_test.sh,
run_subset_request_bug_test.sh); the other two (SoA, AoS/width+string)
were validated ad hoc in the past with no committed script at all. This
driver runs all four uniformly: real `vc +aos68k` compile against the
generated exporter output, real `vamos` execution, checked by exit code
and stdout (vamos propagates the guest program's real exit code,
confirmed in HANDOFF.md's own 68000/vbcc setup notes -- each test .c
file already prints its own pass/fail line and returns 0/1 accordingly).

Tool locations default to this repo's own compiler-python/tools/
(see HANDOFF.md's "Real 68000 toolchain installed and verified on this
Windows machine" entry for how the binaries got there and why they're
not committed to git), overridable via the VBCC / VAMOS environment
variables for anyone with the tools installed elsewhere or on PATH.

Run directly: python run_all_68000_tests.py
"""

import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLS = os.path.normpath(os.path.join(_DIR, "..", "..", "tools"))

VBCC = os.environ.get("VBCC", os.path.join(_TOOLS, "vbcc"))
VC = os.path.join(VBCC, "bin", "vc.exe")
VAMOS = os.environ.get(
    "VAMOS",
    os.path.join(os.path.dirname(sys.executable), "Scripts", "vamos.exe"))

# (test .c, generated .c, output stem) -- each test .c #includes its
# matching generated .h by quoted path, so no -I flag is needed (and
# actively breaks vc.exe's Windows arg parsing when passed as "-I.",
# confirmed directly: it silently drops the flag and leaks a bare "."
# into the vlink line instead of an include path).
CASES = [
    ("test_68000_composition_u16.c", "generated_68000_composition_u16.c",
     "test_68000_composition_u16"),
    ("test_68000_subset_request_bug.c", "generated_68000_subset_request_bug.c",
     "test_68000_subset_request_bug"),
    ("test_68000_soa.c", "generated_68000_soa.c", "test_68000_soa"),
    ("test_68000_aos_split.c", "generated_68000_minimal.c", "test_68000_aos_split"),
    ("test_68000_arrays.c", "generated_68000_arrays.c", "test_68000_arrays"),
    ("test_68000_arrays_soa.c", "generated_68000_arrays_soa.c", "test_68000_arrays_soa"),
    ("test_68000_pools.c", "generated_68000_pools.c", "test_68000_pools"),
    ("test_68000_pools_soa.c", "generated_68000_pools_soa.c", "test_68000_pools_soa"),
]


def _run(cmd, env=None):
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=_DIR, env=env)
    return result


def compile_and_run(test_c, generated_c, out_stem):
    env = dict(os.environ)
    env["VBCC"] = VBCC
    env["PATH"] = os.path.join(VBCC, "bin") + os.pathsep + env.get("PATH", "")

    compile_result = _run([VC, "+aos68k", test_c, generated_c, "-o", out_stem], env=env)
    if compile_result.returncode != 0:
        raise SystemExit(
            f"vbcc compile failed for {test_c}: exit {compile_result.returncode}\n"
            f"--- stdout ---\n{compile_result.stdout}\n--- stderr ---\n{compile_result.stderr}")

    run_result = _run([VAMOS, out_stem])
    for line in run_result.stdout.strip().splitlines():
        print(f"  {line}")
    if run_result.returncode != 0:
        raise SystemExit(
            f"vamos run failed for {out_stem}: exit {run_result.returncode}\n"
            f"--- stdout ---\n{run_result.stdout}\n--- stderr ---\n{run_result.stderr}")


def main():
    if not os.path.isfile(VC):
        raise SystemExit(f"vbcc not found at {VC!r} -- set the VBCC environment variable")
    if not os.path.isfile(VAMOS):
        raise SystemExit(f"vamos not found at {VAMOS!r} -- set the VAMOS environment variable")

    print("=== 68000/vbcc + vamos (AmigaOS) ===")
    for test_c, generated_c, out_stem in CASES:
        print(f"-- {out_stem} --")
        compile_and_run(test_c, generated_c, out_stem)

    print("\nALL 68000 REAL-TOOLCHAIN CHECKS PASSED (8/8).")


if __name__ == "__main__":
    main()
