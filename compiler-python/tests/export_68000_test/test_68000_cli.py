# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validation suite for export_68000.py's new CLI (§18 multi-file input,
matching the shape of the other four exporters' CLIs), and a
regression check that the subset-request bug (see
subset_request_bug.gddl and this repo's HANDOFF.md) stays fixed when
exercised through the REAL CLI -- argparse, real sys.argv-equivalent
invocation via subprocess -- not just the direct function calls
gather_ir()/render_c89_split() already get tested with elsewhere.

Every check here invokes export_68000.py as a real subprocess, the
same standard §18's own test suite already holds itself to for exactly
this reason: a test that only calls the underlying Python functions
directly would never have caught an argparse-level break (a missing
import, a bad flag definition, an argument-parsing ambiguity) the way
running the actual CLI does.

Run directly: python3 test_68000_cli.py
"""

import os
import subprocess
import sys
import tempfile

_DIR = os.path.dirname(os.path.abspath(__file__))
_GDDL_DIR = os.path.normpath(os.path.join(_DIR, "..", "..", "gddl"))
_EXPORTER = os.path.join(_GDDL_DIR, "export_68000.py")

_MULTI_FILE_DIR = os.path.normpath(os.path.join(_DIR, "..", "multi_file_test"))

# Platform temp dir, not a hardcoded /tmp -- this suite runs on Windows too,
# where /tmp doesn't exist.
_TMP = tempfile.gettempdir()


def _run(args, **kwargs):
    return subprocess.run(
        [sys.executable, _EXPORTER] + args, capture_output=True, text=True, **kwargs)


def test_help():
    print("=== Check: --help works, matches the other exporters' quality ===")
    result = _run(["--help"])
    assert result.returncode == 0, result.stderr
    # argparse wraps help text across lines at its own discretion --
    # e.g. "repeat for multiple\n    types" -- so substring checks must
    # be against WHITESPACE-NORMALIZED text, not the raw wrapped
    # output. Confirmed this was a real issue, not a hypothetical one:
    # the first version of this check failed against real --help output
    # for exactly this reason, caught by running it rather than trusting
    # the check on inspection.
    normalized = " ".join(result.stdout.split())
    assert "--type" in normalized
    assert "--layout" in normalized
    assert "--emit-all-domains" in normalized
    assert "-o OUTPUT" in normalized or "--output" in normalized
    # Every argument gets real, substantive help text, not a placeholder.
    # Checked against functional keywords tied to each flag's actual
    # meaning, not exact phrasing -- help text was deliberately trimmed
    # for readability since this check was first written (removing
    # §-references and design-rationale asides), and checking for
    # specific old wording here would just make this test go stale
    # again the next time phrasing gets lightly adjusted.
    for flag_help_fragment in (
        "glob patterns", "repeatable", "aos", "domain", ".h and"
    ):
        assert flag_help_fragment in normalized, \
            f"expected substantive help text containing {flag_help_fragment!r}, not found"
    print("  --help exits 0, documents every flag substantively")
    print("Check PASSED.\n")


def test_single_file_real_cli():
    print("=== Check: single-file invocation through the REAL CLI ===")
    out_stem = os.path.join(_TMP, "gddl_test_68000_cli_single")
    source = os.path.join(_DIR, "composition_nested_u16_fields.gddl")
    result = _run([source, "--type", "Character", "-o", out_stem])
    assert result.returncode == 0, result.stderr
    with open(out_stem + ".c") as f:
        c = f.read()
    assert "60000" in c and "12000" in c and "500" in c and "42" in c, c
    print("  single-file CLI invocation: correct values (Hero: 60000/12000/500/42)")
    os.remove(out_stem + ".h")
    os.remove(out_stem + ".c")
    print("Check PASSED.\n")


def test_multi_file_real_cli():
    print("=== Check: multi-file invocation through the REAL CLI ===")
    out_stem = os.path.join(_TMP, "gddl_test_68000_cli_multi")
    result = _run([
        os.path.join(_MULTI_FILE_DIR, "weapons", "base_weapon.weapon"),
        os.path.join(_MULTI_FILE_DIR, "domains", "elements.gddl"),
        os.path.join(_MULTI_FILE_DIR, "defs", "weapon_type.gddl"),
        os.path.join(_MULTI_FILE_DIR, "weapons", "more_weapons.gddl"),
        "--type", "Weapon", "-o", out_stem,
    ])
    assert result.returncode == 0, result.stderr
    with open(out_stem + ".c") as f:
        c = f.read()
    assert "{ 10, Element_fire }" in c, \
        f"Sword (forward define+identifier ref) missing/wrong: {c}"
    assert "{ 5, Element_lightning }" in c, \
        f"Bow (backward define+identifier ref) missing/wrong: {c}"
    print("  multi-file CLI invocation: Sword (forward refs) and Bow "
          "(backward refs) both correct")
    os.remove(out_stem + ".h")
    os.remove(out_stem + ".c")
    print("Check PASSED.\n")


def test_subset_request_bug_fix_via_real_cli():
    print("=== Check: subset-request bug fix, through the REAL CLI ===")
    out_stem = os.path.join(_TMP, "gddl_test_68000_cli_subset")
    source = os.path.join(_DIR, "subset_request_bug.gddl")
    result = _run([source, "--type", "Item", "-o", out_stem])
    assert result.returncode == 0, \
        f"requesting a genuine subset should succeed (this is exactly what " \
        f"the bug broke): {result.stderr}"
    with open(out_stem + ".h") as f:
        h = f.read()
    with open(out_stem + ".c") as f:
        c = f.read()
    assert "Creature" not in h and "Creature" not in c, \
        "unrelated Creature/CreatureKind leaked into a request for Item alone"
    assert "struct Object" in h, \
        "Object (transitively composed into Item) missing -- over-correction " \
        "would be just as wrong as the original under-scoping bug"
    assert "struct Item" in h
    print("  requesting only 'Item' via the real CLI: succeeds, Object correctly "
          "included (transitive composition), Creature correctly absent")
    os.remove(out_stem + ".h")
    os.remove(out_stem + ".c")
    print("Check PASSED.\n")


def test_error_paths():
    print("=== Check: CLI error paths, real subprocess ===")
    source = os.path.join(_DIR, "subset_request_bug.gddl")

    result = _run([source, "-o", os.path.join(_TMP, "x")])
    assert result.returncode != 0
    assert "--type" in result.stderr
    print("  missing --type: correctly rejected")

    result = _run([os.path.join(_DIR, "no_such_file.gddl"), "--type", "Item", "-o", os.path.join(_TMP, "x")])
    assert result.returncode != 0
    assert "does not exist" in result.stderr
    print("  nonexistent literal file: correctly rejected")

    result = _run([os.path.join(_DIR, "nonexistent_dir", "*.gddl"), "--type", "Item", "-o", os.path.join(_TMP, "x")])
    assert result.returncode != 0
    assert "matched zero files" in result.stderr
    print("  zero-match glob pattern: correctly rejected")
    print("Check PASSED.\n")


def test_shell_independence():
    print("=== Check: shell-independence, zero shell involvement ===")
    out_stem = os.path.join(_TMP, "gddl_test_68000_shell_indep")
    # List-argv, no shell=True anywhere in this call: the OS execs
    # python3 directly. The glob pattern string arrives in argv
    # completely unexpanded -- if this succeeds, only the program
    # itself could have expanded it.
    # base_*.weapon, not *.weapon: weapons/ also holds duplicate.weapon,
    # a deliberate cross-file name collision fixture for
    # test_multi_file.py's own duplicate-detection test, not something
    # this function is testing. A real wildcard is still needed here
    # (not just the literal filename) to prove glob expansion actually
    # happens in the program itself, so narrow the pattern rather than
    # drop the wildcard entirely.
    pattern = os.path.join(_MULTI_FILE_DIR, "weapons", "base_*.weapon")
    result = _run([
        pattern,
        os.path.join(_MULTI_FILE_DIR, "domains", "elements.gddl"),
        os.path.join(_MULTI_FILE_DIR, "defs", "weapon_type.gddl"),
        "--type", "Weapon", "-o", out_stem,
    ])
    assert result.returncode == 0, result.stderr
    with open(out_stem + ".c") as f:
        c = f.read()
    assert "Sword" in c
    print("  glob pattern correctly expanded by the program itself "
          "(no shell was ever involved in this subprocess call)")
    os.remove(out_stem + ".h")
    os.remove(out_stem + ".c")
    print("Check PASSED.\n")


def main():
    test_help()
    test_single_file_real_cli()
    test_multi_file_real_cli()
    test_subset_request_bug_fix_via_real_cli()
    test_error_paths()
    test_shell_independence()
    print("ALL CHECKS PASSED.")


if __name__ == "__main__":
    main()
