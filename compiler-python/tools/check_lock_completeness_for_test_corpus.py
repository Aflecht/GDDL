"""
Lock-completeness check for a GDDL corpus tree: every `.gddl` file has
a matching `.golden.json` sitting next to it.

Sent by Compiler Core to Test Corpus for parity -- the exact same gap
this closes (a `.gddl` with no corresponding lock, silently invisible
because nothing checked for it) was just found and fixed in Compiler
Core's own copy of `corpus/`, and it can just as easily open in this
direction instead. Same check, same reasoning, same scope limits.

Deliberately self-contained: no dependency on any compiler internals
(parser/resolve/validate-equivalent modules), so this drops into any
corpus tree and runs standalone, regardless of what your own pipeline
looks like internally.

SCOPE, precisely, so it doesn't grow into something bigger than the
actual problem:
  - Checks EXISTENCE of a `.golden.json` next to each `.gddl`. Nothing
    about its content.
  - Missing entirely = hard failure (non-zero exit, exact filenames
    printed).
  - Present with any capture_status, including "pending" (legitimate,
    tracked, in-progress work -- e.g. a deliberately-stubbed fixture
    awaiting capture) = NOT an error. Flagging that would just train
    people to ignore this check's output the first time it cries wolf
    over something that's actually fine.
  - Does NOT gate or replace whatever your own golden-output regression
    does -- if you have an equivalent of "regenerate golden output from
    the reference implementation," that step should still run and write
    its own output regardless of what this check finds; this only adds
    a second, independent assertion afterward.

WHAT THIS DELIBERATELY DOES NOT SOLVE: this only verifies ONE copy of
a corpus against itself. It cannot detect two separate copies of the
"same" corpus diverging in some OTHER way -- e.g. both having a lock
for the same fixture, but with different captured content. No
single-sandbox script can catch that, since no single sandbox holds
both copies at once. That's a cross-copy consistency problem, not a
completeness problem, and is out of scope for this check specifically.

WHY THIS SHOULD LIVE INSIDE WHATEVER STEP YOU ALREADY ALWAYS RUN, not
as a second optional script: a standalone script that nobody is forced
to run doesn't fix anything -- it just relocates the exact same failure
mode one level down. If you have a "regenerate golden output" script
analogous to Compiler Core's `export_golden.py`, fold this into it
(see `check_lock_completeness()` below, designed to be called as a
function, not just run as `__main__`) so it rides on a step that's
already mandatory, rather than becoming a second one nobody remembers.

Usage as a standalone script:
    python3 check_lock_completeness.py /path/to/corpus

Usage as a library call from your own tooling:
    from check_lock_completeness import check_lock_completeness
    missing = check_lock_completeness(corpus_root, gddl_paths)
"""

import glob
import os
import sys


def check_lock_completeness(root_dir: str, fixture_paths):
    """Every .gddl file must have a matching .golden.json sitting next
    to it -- EXISTENCE only, nothing about its content. Returns the
    list of .gddl paths (relative to root_dir) that have no
    .golden.json at all. Empty list means full coverage."""
    missing = []
    for gddl_path in fixture_paths:
        lock_path = gddl_path[:-len(".gddl")] + ".golden.json"
        if not os.path.exists(lock_path):
            rel = os.path.relpath(gddl_path, root_dir)
            missing.append(rel)
    return sorted(missing)


def _discover_gddl_files(root_dir: str):
    return sorted(
        glob.glob(f"{root_dir}/*.gddl") + glob.glob(f"{root_dir}/*/*.gddl"))


def main():
    if len(sys.argv) != 2:
        print("usage: python3 check_lock_completeness.py /path/to/corpus",
              file=sys.stderr)
        sys.exit(2)

    root_dir = sys.argv[1]
    fixture_paths = _discover_gddl_files(root_dir)
    missing = check_lock_completeness(root_dir, fixture_paths)

    if missing:
        print(f"LOCK COMPLETENESS CHECK FAILED: {len(missing)} .gddl "
              f"file(s) have no .golden.json at all:")
        for rel in missing:
            print(f"  MISSING: {rel}")
        sys.exit(1)
    else:
        print(f"Lock completeness check passed: all {len(fixture_paths)} "
              f".gddl files have a .golden.json (pending/blocked entries "
              f"count as present -- this checks existence only).")


if __name__ == "__main__":
    main()
