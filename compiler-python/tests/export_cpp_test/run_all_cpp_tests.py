# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Driver for this directory's real-toolchain C++ checks, mirroring the
Z80/6502/68000 drivers' role for their targets. Unlike those, this
directory never had committed build recipes at all (every prior
session's HANDOFF.md entries mention "real g++17" but never a
preserved command line) -- the (sources, output name) groupings below
were reconstructed directly from each test file's own #include and
`int main()` presence, not guessed.

This machine has no g++ -- uses the MSVC toolset already installed via
Visual Studio (cl.exe), which this project's exporter output was never
specifically validated against before now. `/std:c++17 /EHsc` is the
closest equivalent to the g++17 standard every prior session used;
GDDL's generated headers are portable standard C++, not GCC-specific,
so this is a genuine equivalence check, not a lesser substitute.

Run directly: python run_all_cpp_tests.py
"""

import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))

# (source files, output binary name). Multi-file entries are the
# cross-translation-unit and split-mode tests, where a companion .cpp
# (no main()) must be compiled and linked alongside the real test
# entry point.
CASES = [
    (["test_generated_minimal.cpp"], "test_generated_minimal"),
    (["test_generated_empty.cpp"], "test_generated_empty"),
    (["tu1_main.cpp", "tu2.cpp"], "cross_tu_test"),
    (["test_generated_scaleup.cpp"], "test_generated_scaleup"),
    (["tu1_scaleup_main.cpp", "tu2_scaleup.cpp"], "cross_tu_scaleup_test"),
    (["test_generated_indexed.cpp"], "test_generated_indexed"),
    (["test_bsearch_large.cpp"], "test_bsearch_large"),
    (["test_bsearch_one.cpp"], "test_bsearch_one"),
    (["test_bsearch_two.cpp"], "test_bsearch_two"),
    (["test_bsearch_large_constexpr.cpp"], "test_bsearch_large_constexpr"),
    (["test_generated_indexed_soa.cpp"], "test_generated_indexed_soa"),
    (["test_split_aos_main.cpp", "generated_indexed_split.cpp"], "test_split_aos"),
    (["test_split_soa_main.cpp", "generated_indexed_split_soa.cpp"], "test_split_soa"),
    (["test_generated_composition_nested_u16_fields.cpp",
      "generated_composition_nested_u16_fields.cpp"],
     "test_generated_composition_nested_u16_fields"),
    (["test_generated_composition_nested_u16_fields_single.cpp"],
     "test_generated_composition_nested_u16_fields_single"),
    (["test_generated_scaleup2.cpp"], "test_generated_scaleup2"),
    (["test_generated_flags.cpp"], "test_generated_flags"),
    (["test_generated_arrays.cpp"], "test_generated_arrays"),
    (["test_generated_arrays_soa.cpp"], "test_generated_arrays_soa"),
]


def _find_vcvars64():
    env_override = os.environ.get("VCVARS64")
    if env_override:
        return env_override
    installer = (r"C:\Program Files (x86)\Microsoft Visual Studio\Installer\vswhere.exe")
    if os.path.isfile(installer):
        result = subprocess.run(
            [installer, "-latest", "-products", "*",
             "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
             "-property", "installationPath"],
            capture_output=True, text=True)
        install_path = result.stdout.strip()
        if install_path:
            candidate = os.path.join(
                install_path, "VC", "Auxiliary", "Build", "vcvars64.bat")
            if os.path.isfile(candidate):
                return candidate
    raise SystemExit(
        "could not locate vcvars64.bat -- set the VCVARS64 environment "
        "variable to its real path")


def _msvc_env(vcvars64):
    """Runs vcvars64.bat once and captures the resulting environment
    (INCLUDE/LIB/LIBPATH/PATH) as a real dict, so every subsequent cl.exe
    invocation gets it directly instead of re-running the batch script
    (and re-paying its ~1s startup cost) per compile."""
    marker = "___ENV_START___"
    result = subprocess.run(
        f'"{vcvars64}" >nul && echo {marker} && set',
        shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        raise SystemExit(f"vcvars64.bat failed:\n{result.stdout}\n{result.stderr}")
    out = result.stdout
    idx = out.index(marker)
    env = dict(os.environ)
    # Windows env vars are case-insensitive, but `set`'s output preserves
    # whatever casing vsdevcmd.bat used ("Path", not "PATH") -- a naive
    # dict merge leaves both keys present, and CreateProcess's handling
    # of two differently-cased duplicates is unreliable (confirmed
    # directly: the stale os.environ "PATH", without any VC directories,
    # silently won over the freshly captured "Path"). Drop the
    # existing key first, matched case-insensitively, before inserting.
    for line in out[idx + len(marker):].strip().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            for existing in list(env):
                if existing.lower() == k.lower():
                    del env[existing]
            env[k] = v
    return env


def _resolve_on_path(name, env):
    """subprocess.Popen's own PATH search (when a bare executable name
    with no directory separator is given) uses the CALLING process's
    os.environ, never the custom `env=` dict about to be handed to the
    child -- confirmed directly: passing plain "cl.exe" with a correct,
    fully-populated env["Path"] still raised FileNotFoundError, because
    Python resolved against this process's own (VC-less) PATH first.
    Resolving the real absolute path ourselves, from the same env dict
    the child will actually use, sidesteps this entirely."""
    path_var = next((v for k, v in env.items() if k.lower() == "path"), "")
    for directory in path_var.split(os.pathsep):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit(f"{name!r} not found on the captured MSVC Path")


def _run(cmd, env):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=_DIR, env=env)


def compile_and_run(sources, out_name, env, cl_path):
    out_exe = out_name + ".exe"
    cmd = [cl_path, "/nologo", "/std:c++17", "/EHsc"] + sources + [f"/Fe:{out_exe}"]
    compile_result = _run(cmd, env)
    if compile_result.returncode != 0:
        raise SystemExit(
            f"MSVC compile failed for {sources}: exit {compile_result.returncode}\n"
            f"--- stdout ---\n{compile_result.stdout}\n--- stderr ---\n{compile_result.stderr}")

    run_result = _run([os.path.join(_DIR, out_exe)], env)
    for line in run_result.stdout.strip().splitlines():
        print(f"  {line}")
    if run_result.returncode != 0:
        raise SystemExit(
            f"{out_exe} exited {run_result.returncode}\n"
            f"--- stdout ---\n{run_result.stdout}\n--- stderr ---\n{run_result.stderr}")


def main():
    vcvars64 = _find_vcvars64()
    env = _msvc_env(vcvars64)
    cl_path = _resolve_on_path("cl.exe", env)

    print(f"=== C++ (MSVC via {vcvars64}) ===")
    print(f"cl.exe: {cl_path}")
    for sources, out_name in CASES:
        print(f"-- {out_name} --")
        compile_and_run(sources, out_name, env, cl_path)

    print(f"\nALL C++ REAL-TOOLCHAIN CHECKS PASSED ({len(CASES)}/{len(CASES)}).")


if __name__ == "__main__":
    main()
