# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Full validation suite for §18 Multi-File Compilation, run against the
5-file adversarial fixture in this directory (weapons/base_weapon.weapon,
domains/elements.gddl, defs/weapon_type.gddl, weapons/more_weapons.gddl,
weapons/duplicate.weapon).

Five genuinely separate checks, matching the task's own validation
requirements point for point:

  1. Forward/backward reference resolution, both define-level and
     identifier-level, all four directions, using the CLEAN 4-file
     subset (no collision).
  2. The deliberate collision: caught (not silently accepted), and
     BOTH locations -- the colliding declaration and the original --
     independently verified against exact, predicted line numbers,
     not just "somewhere in the combined text."
  3. Zero-match error path, both forms (nonexistent literal file, and
     a glob pattern matching nothing).
  4. Shell-independence: the glob expansion is done by the program
     itself, proven by invoking the CLI via subprocess with NO shell
     involved at all (list-argv, no shell=True) -- if this succeeds,
     it can only be because the program did its own expansion, since
     there was no shell in the call chain to have done it. A second
     form (real bash, pattern single-quoted so bash can't expand it
     even if invoked) confirms the same result under an actual shell
     that's prevented from touching the pattern -- the Windows
     cmd.exe/PowerShell case this whole requirement is about.
  5. Non-.gddl extension: base_weapon.weapon and duplicate.weapon both
     end in .weapon, never .gddl, and are resolved either as literal
     paths or via an extension-specific glob pattern throughout this
     suite -- never assumed to be GDDL source by name alone.

Run directly: python3 test_multi_file.py
"""

import os
import subprocess
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "gddl"))

from combine import resolve_inputs, compile_multi, remap_line, CombineError

_DIR = os.path.dirname(os.path.abspath(__file__))

FILE1_BASE_WEAPON = os.path.join(_DIR, "weapons", "base_weapon.weapon")
FILE2_ELEMENTS = os.path.join(_DIR, "domains", "elements.gddl")
FILE3_WEAPON_TYPE = os.path.join(_DIR, "defs", "weapon_type.gddl")
FILE4_MORE_WEAPONS = os.path.join(_DIR, "weapons", "more_weapons.gddl")
FILE5_DUPLICATE = os.path.join(_DIR, "weapons", "duplicate.weapon")

CLEAN_FILES = [FILE1_BASE_WEAPON, FILE2_ELEMENTS, FILE3_WEAPON_TYPE, FILE4_MORE_WEAPONS]
ALL_FILES_WITH_COLLISION = CLEAN_FILES + [FILE5_DUPLICATE]


def test_forward_and_backward_references():
    print("=== Check 1: forward/backward references, all four directions ===")
    paths = resolve_inputs(CLEAN_FILES)
    assert paths == CLEAN_FILES, \
        f"literal-argument order not preserved: {paths}"

    result = compile_multi(paths)
    assert result["status"] == "parsed", result

    resolver = result["resolver"]
    sword = resolver.cache.get("Sword")
    bow = resolver.cache.get("Bow")
    assert sword is not None, "Sword failed to resolve at all"
    assert bow is not None, "Bow failed to resolve at all"

    # Sword (file 1) forward-references Weapon (file 3) and
    # Element.fire (file 2) -- both declared LATER in combination order.
    assert sword.fields["damage"] == 10, sword.fields
    assert sword.fields["element"].key == "fire", sword.fields["element"]
    print("  Sword (forward define ref -> file 3, forward identifier ref -> file 2): OK")

    # Bow (file 4) backward-references Weapon (file 3) and
    # Element.lightning (file 2) -- both declared EARLIER.
    assert bow.fields["damage"] == 5, bow.fields
    assert bow.fields["element"].key == "lightning", bow.fields["element"]
    print("  Bow (backward define ref -> file 3, backward identifier ref -> file 2): OK")

    assert not result["remapped_duplicate_errors"], \
        f"clean 4-file set should have NO duplicate errors, got: {result['remapped_duplicate_errors']}"
    print("Check 1 PASSED.\n")


def test_collision_dual_location_attribution():
    print("=== Check 2: deliberate collision, dual-location attribution ===")
    paths = resolve_inputs(ALL_FILES_WITH_COLLISION)
    result = compile_multi(paths)
    assert result["status"] == "parsed", result

    dup_errors = result["remapped_duplicate_errors"]
    assert len(dup_errors) == 1, \
        f"expected exactly 1 duplicate_name error, got {len(dup_errors)}: {dup_errors}"

    err = dup_errors[0]
    assert err["check"] == "duplicate_name", err
    print(f"  collision caught: {err['message']}")

    # The COLLIDING declaration (file 5, duplicate.weapon) -- the real
    # statement, unindented, at the start of its line -- NOT any line
    # merely mentioning "Weapon Sword" in a comment (this file's own
    # header comment references the phrase too; a naive substring
    # search over every line matches the COMMENT first, a real bug
    # caught by running this test rather than trusting the search
    # logic on inspection alone).
    with open(FILE5_DUPLICATE) as f:
        dup_lines = f.read().split("\n")
    predicted_dup_line = next(
        i for i, line in enumerate(dup_lines, start=1)
        if line.startswith("Weapon Sword"))
    assert err["file"] == FILE5_DUPLICATE, err["file"]
    assert err["line"] == predicted_dup_line, \
        f"colliding declaration: got line {err['line']}, predicted {predicted_dup_line}"
    print(f"  colliding declaration correctly attributed: {FILE5_DUPLICATE}:{err['line']}")

    # The ORIGINAL (winning) declaration -- independently verified via
    # resolver.reg.instances['Sword'].line, remapped the same way,
    # confirmed against file 1's own actual content.
    resolver = result["resolver"]
    decl = resolver.reg.instances["Sword"]
    orig_file, orig_line = remap_line(decl.line, result["spans"])
    with open(FILE1_BASE_WEAPON) as f:
        base_lines = f.read().split("\n")
    predicted_orig_line = next(
        i for i, line in enumerate(base_lines, start=1)
        if line.startswith("Weapon Sword"))
    assert orig_file == FILE1_BASE_WEAPON, orig_file
    assert orig_line == predicted_orig_line, \
        f"original declaration: got line {orig_line}, predicted {predicted_orig_line}"
    print(f"  original declaration correctly attributed: {FILE1_BASE_WEAPON}:{orig_line}")

    # First declaration wins -- Sword resolves using file 1's values,
    # not file 5's (damage=999, element=ice -- the colliding values).
    sword = resolver.cache["Sword"]
    assert sword.fields["damage"] == 10, \
        f"first-wins policy violated: Sword.damage = {sword.fields['damage']}, expected 10 (file 1's value)"
    print("  first declaration wins (Sword.damage == 10, not the colliding 999): OK")
    print("Check 2 PASSED.\n")


def test_zero_match_error_path():
    print("=== Check 3: zero-match error path, both forms ===")
    try:
        resolve_inputs([os.path.join(_DIR, "no_such_file.gddl")])
        raise AssertionError("nonexistent literal file did NOT raise CombineError")
    except CombineError as e:
        print(f"  nonexistent literal file correctly rejected: {e}")

    try:
        resolve_inputs([os.path.join(_DIR, "weapons", "nonexistent_subdir", "*.gddl")])
        raise AssertionError("zero-match glob pattern did NOT raise CombineError")
    except CombineError as e:
        print(f"  zero-match glob pattern correctly rejected: {e}")

    print("Check 3 PASSED.\n")


def test_shell_independence():
    print("=== Check 4: shell-independence, real subprocess, no shell involved ===")
    gddl_dir = os.path.join(os.path.dirname(_DIR), "..", "gddl")
    gddl_dir = os.path.normpath(gddl_dir)
    out_stem = "/tmp/gddl_multi_file_shell_indep_test.asm"

    # base_*.weapon, not *.weapon: weapons/ also holds duplicate.weapon,
    # a deliberate cross-file name collision fixture for Check 2's own
    # test, not something this function is testing. Duplicate names are
    # now a hard build-blocking error (confirmed policy, §18 combines
    # files at the source level, a genuine collision there is almost
    # always a real mistake), so a glob that swept it in here would
    # fail this function for a reason unrelated to what it's actually
    # checking. A real wildcard is still needed (not the literal
    # filename) to prove glob expansion actually happens in the
    # program itself, so narrow the pattern rather than drop the
    # wildcard entirely.

    # List-argv, no shell=True: the OS execs python3 directly. The
    # pattern string arrives in argv completely unexpanded -- there is
    # no shell anywhere in this call to have expanded it.
    pattern = os.path.join(_DIR, "weapons", "more_weapons.gddl")
    result = subprocess.run(
        [sys.executable, os.path.join(gddl_dir, "export_z80.py"),
         os.path.join(_DIR, "weapons", "base_*.weapon"),
         FILE2_ELEMENTS, FILE3_WEAPON_TYPE,
         "--type", "Weapon", "--z80-pointer-table=on", "-o", out_stem],
        capture_output=True, text=True)
    assert result.returncode == 0, f"subprocess (no shell) failed: {result.stderr}"
    with open(out_stem) as f:
        out = f.read()
    assert "Weapon_Sword:" in out, "glob expansion did not occur -- no shell was involved to do it"
    print("  list-argv subprocess (zero shell involvement): glob correctly expanded by the program")

    # Real bash, but the pattern is single-quoted so bash CANNOT expand
    # it even though a real shell is genuinely present -- simulates
    # what actually happens on Windows cmd.exe/PowerShell.
    cmd = (f"{sys.executable} {os.path.join(gddl_dir, 'export_z80.py')} "
           f"'{os.path.join(_DIR, 'weapons', 'base_*.weapon')}' "
           f"{FILE2_ELEMENTS} {FILE3_WEAPON_TYPE} "
           f"--type Weapon --z80-pointer-table=on -o {out_stem}")
    result2 = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True)
    assert result2.returncode == 0, f"quoted-glob bash invocation failed: {result2.stderr}"
    with open(out_stem) as f:
        out2 = f.read()
    assert "Weapon_Sword:" in out2, "quoted glob was not expanded by the program"
    print("  quoted-glob bash invocation (shell present, prevented from expanding): "
          "glob correctly expanded by the program")

    os.remove(out_stem)
    print("Check 4 PASSED.\n")


def test_non_gddl_extension():
    print("=== Check 5: non-.gddl extension, never assumed ===")
    assert FILE1_BASE_WEAPON.endswith(".weapon"), FILE1_BASE_WEAPON
    assert FILE5_DUPLICATE.endswith(".weapon"), FILE5_DUPLICATE

    # Resolved correctly as a literal path (already exercised by every
    # check above -- FILE1_BASE_WEAPON is a .weapon file throughout).
    # Also confirm an extension-SPECIFIC glob pattern (not unqualified)
    # correctly matches only .weapon files, never assuming .gddl.
    matches = resolve_inputs([os.path.join(_DIR, "weapons", "*.weapon")])
    assert all(m.endswith(".weapon") for m in matches), matches
    assert len(matches) == 2, f"expected exactly 2 .weapon files, got {matches}"
    print(f"  '*.weapon' pattern correctly matched exactly the 2 .weapon files, "
          f"nothing .gddl-named swept in: {[os.path.basename(m) for m in matches]}")
    print("Check 5 PASSED.\n")


def main():
    test_forward_and_backward_references()
    test_collision_dual_location_attribution()
    test_zero_match_error_path()
    test_shell_independence()
    test_non_gddl_extension()
    print("ALL CHECKS PASSED.")


if __name__ == "__main__":
    main()
