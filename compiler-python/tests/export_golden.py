# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Exports actual reference-implementation output for every .gddl fixture
under corpus/ as structured JSON -- meant to become golden data.
"""

import sys
import re
import json
import glob
import os

# Script-relative, not hardcoded: this file must be runnable from any
# working directory and from wherever the project root happens to live
# (the previous absolute /home/claude/gddl paths broke the regression
# workflow whenever the tree was checked out or copied elsewhere).
#
# Post-restructuring split: this file lives in compiler-python/tests/,
# but the pipeline modules it imports (parser, resolve, validate) now
# live in a SIBLING directory, compiler-python/gddl/ -- corpus/ and
# golden_output.json stay relative to THIS file's own directory
# (_TESTS_ROOT), but the import path must point one level up and into
# gddl/ instead (_GDDL_ROOT). Before the restructuring these were the
# same directory; conflating them again here would silently break the
# moment either side of the tree moves independently in the future.
_TESTS_ROOT = os.path.dirname(os.path.abspath(__file__))
_COMPILER_ROOT = os.path.dirname(_TESTS_ROOT)

sys.path.insert(0, _COMPILER_ROOT)

from gddl.parser import parse_file, GDDLParseError
from gddl.resolve import resolve_all, StructValue, UNINIT, IdentifierRef
from gddl.validate import compile_report

_LINE_RE = re.compile(r"^line (\d+):")


def serialize_value(v):
    if v is UNINIT:
        return {"__uninitialized__": True}
    if isinstance(v, StructValue):
        return {k: serialize_value(val) for k, val in v.fields.items()}
    if isinstance(v, IdentifierRef):
        return {
            "__identifier_ref__": True,
            "domain": v.domain,
            "key": v.key,
            "logical_id": v.logical_id,
        }
    return v


def extract_line(message: str):
    m = _LINE_RE.match(message)
    return int(m.group(1)) if m else None


def run_fixture(path: str):
    try:
        prog = parse_file(path)
    except GDDLParseError as e:
        return {
            "status": "parse_error",
            "error": {"phase": 3, "line": e.line, "message": str(e)},
        }

    resolver = resolve_all(prog)
    report = compile_report(resolver)

    instances = {}
    for name, (status, detail) in report.items():
        entry = {"status": status}
        if status in ("ok", "delete"):
            entry["resolved"] = serialize_value(resolver.cache[name])
            entry["phase"] = None
            entry["check"] = None
        elif status == "error":
            entry["phase"] = detail.phase
            entry["check"] = detail.check
            entry["line"] = detail.line
            entry["message"] = str(detail)
        elif status == "blocked":
            entry["phase"] = 6
            entry["check"] = None
            entry["blocked_on"] = detail
            entry["message"] = f"unresolvable: depends on '{detail}', which failed to compile"
        elif status == "incomplete":
            entry["phase"] = 8
            entry["check"] = "final_completeness"
            entry["missing_fields"] = detail
            entry["resolved"] = serialize_value(resolver.cache[name])
        instances[name] = entry

    return {
        "status": "parsed",
        "duplicate_errors": [e.to_dict() for e in resolver.reg.duplicate_errors],
        "warnings": [w.to_dict() for w in resolver.warnings],
        "instances": instances,
    }


def run_batch(root_dir: str, out_fixtures: dict, path_prefix: str = ""):
    files = sorted(glob.glob(f"{root_dir}/*.gddl") + glob.glob(f"{root_dir}/*/*.gddl"))
    for f in files:
        rel = path_prefix + f[len(root_dir) + 1:]
        out_fixtures[rel] = run_fixture(f)
    return files


def check_lock_completeness(root_dir: str, fixture_paths):
    """Every .gddl file under corpus/ must have a matching .golden.json
    sitting next to it -- EXISTENCE only, nothing about its content.
    Missing entirely is a hard failure. A .golden.json that exists but
    has capture_status "pending" (e.g. the numeric_range/ stubs) is
    NOT an error -- that's legitimate, tracked, in-progress work, and
    flagging it would just train people to ignore this check's output
    the first time it cries wolf over something that's actually fine.

    Returns the list of .gddl paths (relative to root_dir, matching
    golden_output.json's own fixture-key convention) that have no
    .golden.json at all. Empty list means full coverage.

    Deliberately narrow in scope: this only verifies ONE copy of
    corpus/ against itself. It cannot detect this copy and another
    party's copy of the same corpus diverging in some OTHER way (e.g.
    both having a lock for the same fixture, but with different
    captured content) -- no single-sandbox script can catch that, since
    no single sandbox holds both copies at once. That's a cross-copy
    consistency problem, not a completeness problem, and is explicitly
    out of scope here (see HANDOFF.md)."""
    missing = []
    for gddl_path in fixture_paths:
        lock_path = gddl_path[:-len(".gddl")] + ".golden.json"
        if not os.path.exists(lock_path):
            rel = os.path.relpath(gddl_path, root_dir)
            missing.append(rel)
    return sorted(missing)


def main():
    out = {
        "_meta": {"fixture_count": 0, "batches": []},
        "fixtures": {},
    }
    corpus_root = os.path.join(_TESTS_ROOT, "corpus")
    main_files = run_batch(corpus_root, out["fixtures"])
    out["_meta"]["batches"].append({"name": "main_corpus", "count": len(main_files)})
    out["_meta"]["fixture_count"] = len(out["fixtures"])

    with open(os.path.join(_TESTS_ROOT, "golden_output.json"), "w") as fh:
        json.dump(out, fh, indent=2)

    print(f"Wrote golden_output.json: {len(out['fixtures'])} fixtures")

    # Lock-completeness check runs AFTER golden_output.json is written --
    # it never gates that output, since golden_output.json is useful on
    # its own even when lock coverage is incomplete.
    missing = check_lock_completeness(corpus_root, main_files)
    if missing:
        print(f"\nLOCK COMPLETENESS CHECK FAILED: {len(missing)} .gddl "
              f"file(s) have no .golden.json at all:")
        for rel in missing:
            print(f"  MISSING: {rel}")
        sys.exit(1)
    else:
        print(f"Lock completeness check passed: all {len(main_files)} "
              f".gddl files have a .golden.json (pending/blocked entries "
              f"count as present -- this checks existence only).")


if __name__ == "__main__":
    main()
