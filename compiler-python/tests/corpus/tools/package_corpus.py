#!/usr/bin/env python3
# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Mandatory pre-packaging step for this corpus: run the lock-completeness
check (received from Compiler Core) BEFORE any sync-to-outputs or zip
step runs. If it fails, packaging aborts loudly rather than silently
shipping a corpus with an orphaned .gddl file in it.

This exists specifically so the check doesn't depend on anyone
remembering to invoke it separately -- it rides on the one step that
already can't be skipped (you can't hand off a corpus without
packaging it), the same principle the check's own docstring argues for.

Usage:
    python3 tools/package_corpus.py /path/to/corpus_root
Exit code is non-zero (and packaging must not proceed) if the check
fails. Zero means safe to continue with sync/zip.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from check_lock_completeness import check_lock_completeness, _discover_gddl_files


def run_pre_packaging_check(root_dir: str) -> bool:
    """Returns True if safe to package, False if packaging should abort."""
    fixture_paths = _discover_gddl_files(root_dir)
    missing = check_lock_completeness(root_dir, fixture_paths)

    if missing:
        print(f"PRE-PACKAGING CHECK FAILED: {len(missing)} .gddl file(s) "
              f"have no .golden.json at all -- ABORTING PACKAGING, do not "
              f"sync or zip until this is fixed:", file=sys.stderr)
        for rel in missing:
            print(f"  MISSING: {rel}", file=sys.stderr)
        return False

    print(f"Pre-packaging check passed: all {len(fixture_paths)} .gddl "
          f"files have a .golden.json. Safe to sync/zip.")
    return True


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: python3 package_corpus.py /path/to/corpus_root",
              file=sys.stderr)
        sys.exit(2)

    ok = run_pre_packaging_check(sys.argv[1])
    sys.exit(0 if ok else 1)
