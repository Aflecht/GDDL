# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validation suite for --emit-bindings-manifest (SPEC.md section 14.6).

Five genuinely separate checks:

  1. build_bindings_manifest() content, called directly against a real
     resolved Registry: every field `kind` the manifest vocabulary
     supports (struct, string, identifier -- both default and indexed
     form of the SAME domain, on two different fields, proving this is
     tracked per field not per domain -- flags, array), each instance's
     stable_id cross-checked against reg.get_instance_id() directly
     (the same precomputed table the C++ exporter itself reads), not
     just trusted because build_bindings_manifest() produced it.
  2. Delete-template exclusion matches export_instances_for_type()
     exactly: TemplateOnly (delete-marked) must NOT appear in the
     manifest's instance list, the same filter the real C++ header
     itself already applies -- the whole point of "generated from the
     same compiled representation... in lockstep."
  3. Domain content is reused verbatim from build_ids_manifest(), not a
     second, independently-written domain walk -- confirmed by a
     direct equality check against build_ids_manifest()'s own output
     for the same registry.
  4. The real CLI, real subprocess (matching this project's own
     standard for CLI-level regressions): --emit-bindings-manifest
     writes <output>.gddlbindings.json; omitting the flag writes no
     such file at all (confirms genuinely opt-in, not always-on).
  5. The --emit-bindings-manifest + --layout=soa guard, real CLI:
     rejected with a clear error and nonzero exit, since SoA output has
     no struct for "per-field getter thunk" to mean anything against.

Run directly: python3 test_bindings_manifest.py
"""

import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPILER_ROOT = os.path.normpath(os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _COMPILER_ROOT)

from gddl.parser import parse_file
from gddl.resolve import resolve_all
from gddl.export_ids import build_ids_manifest
from gddl.export_bindings import build_bindings_manifest

FIXTURE = os.path.join(_DIR, "export_test_bindings.gddl")


def _resolve_fixture():
    prog = parse_file(FIXTURE)
    resolver = resolve_all(prog)
    assert not resolver.reg.duplicate_errors, resolver.reg.duplicate_errors
    assert not resolver.errors, resolver.errors
    return resolver


def test_manifest_content():
    print("=== Check 1: manifest content, every field kind + stable IDs ===")
    resolver = _resolve_fixture()
    reg = resolver.reg
    manifest = build_bindings_manifest(reg, resolver)

    types_by_name = {t["name"]: t for t in manifest["types"]}
    assert set(types_by_name) == {"Stats", "Creature"}, types_by_name.keys()

    creature_fields = {f["name"]: f for f in types_by_name["Creature"]["fields"]}
    assert creature_fields["stats"] == {"name": "stats", "kind": "struct", "type": "Stats"}
    assert creature_fields["label"] == {"name": "label", "kind": "string", "width": 16}
    assert creature_fields["attack"] == {
        "name": "attack", "kind": "identifier", "domain": "ActionAttack", "indexed": False}
    assert creature_fields["fast_dispatch"] == {
        "name": "fast_dispatch", "kind": "identifier", "domain": "ActionAttack", "indexed": True}
    assert creature_fields["components"] == {
        "name": "components", "kind": "flags", "domain": "ComponentFlags"}
    assert creature_fields["scores"] == {
        "name": "scores", "kind": "array", "dims": [3],
        "element": {"kind": "scalar", "type": "u8"}}
    print("  Creature: struct/string/identifier(default)/identifier(indexed)/"
          "flags/array field kinds all match, attack vs fast_dispatch "
          "correctly distinguished despite sharing one domain")

    creature_instances = {i["name"]: i for i in types_by_name["Creature"]["instances"]}
    for name in ("Human_Fighter", "RealFromTemplate"):
        expected_id = reg.get_instance_id("Creature", name)
        assert expected_id is not None, name
        assert creature_instances[name]["stable_id"] == expected_id, name
    print("  Creature instances: stable_id matches reg.get_instance_id() "
          "for every exported instance")
    print("Check 1 PASSED.\n")


def test_delete_template_excluded():
    print("=== Check 2: delete-marked instance excluded from manifest ===")
    resolver = _resolve_fixture()
    manifest = build_bindings_manifest(resolver.reg, resolver)
    types_by_name = {t["name"]: t for t in manifest["types"]}
    names = {i["name"] for i in types_by_name["Creature"]["instances"]}
    assert names == {"Human_Fighter", "RealFromTemplate"}, names
    assert "TemplateOnly" not in names, \
        "delete-marked instance must never appear, same as the real C++ export"
    print("  TemplateOnly (delete) correctly absent; "
          "RealFromTemplate (built FROM the template) correctly present")
    print("Check 2 PASSED.\n")


def test_domains_match_ids_manifest():
    print("=== Check 3: domain content reused verbatim from build_ids_manifest ===")
    resolver = _resolve_fixture()
    bindings = build_bindings_manifest(resolver.reg, resolver)
    ids = build_ids_manifest(resolver.reg)
    assert bindings["domains"] == ids["domains"], (bindings["domains"], ids["domains"])
    print("  bindings manifest's 'domains' key is byte-for-byte identical "
          "to build_ids_manifest()'s own output -- one source of truth, "
          "not two independently-written domain walks")
    print("Check 3 PASSED.\n")


def test_real_cli_opt_in():
    print("=== Check 4: real CLI, --emit-bindings-manifest is genuinely opt-in ===")
    import json
    import tempfile
    tmp = tempfile.gettempdir()
    stem_with = os.path.join(tmp, "gddl_bindings_manifest_test_with")
    stem_without = os.path.join(tmp, "gddl_bindings_manifest_test_without")
    manifest_with = stem_with + ".gddlbindings.json"
    manifest_without = stem_without + ".gddlbindings.json"
    for p in (manifest_with, manifest_without):
        if os.path.exists(p):
            os.remove(p)

    result = subprocess.run(
        [sys.executable, "-m", "gddl.export_cpp", FIXTURE,
         "--emit-bindings-manifest", "-o", stem_with],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(manifest_with), "flag passed but no manifest file was written"
    with open(manifest_with, encoding="utf-8") as f:
        data = json.load(f)
    assert {t["name"] for t in data["types"]} == {"Stats", "Creature"}
    print("  --emit-bindings-manifest: file written, real CLI, real content")

    result2 = subprocess.run(
        [sys.executable, "-m", "gddl.export_cpp", FIXTURE, "-o", stem_without],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result2.returncode == 0, result2.stderr
    assert not os.path.isfile(manifest_without), \
        "no --emit-bindings-manifest flag, but a manifest file got written anyway"
    print("  no flag: no manifest file written -- genuinely opt-in, not always-on")

    for p in (manifest_with, manifest_without,
              stem_with + ".h", stem_with + ".cpp",
              stem_without + ".h", stem_without + ".cpp"):
        if os.path.exists(p):
            os.remove(p)
    print("Check 4 PASSED.\n")


def test_soa_guard():
    print("=== Check 5: --emit-bindings-manifest + --layout=soa is rejected ===")
    import tempfile
    stem = os.path.join(tempfile.gettempdir(), "gddl_bindings_soa_guard_test")
    result = subprocess.run(
        [sys.executable, "-m", "gddl.export_cpp", FIXTURE,
         "--emit-bindings-manifest", "--layout", "soa", "-o", stem],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result.returncode != 0, \
        "expected a rejection (--layout=soa), but the CLI exited 0"
    assert "--emit-bindings-manifest is not available with --layout=soa" in result.stderr, \
        result.stderr
    print("  correctly rejected: "
          f"{result.stderr.strip().splitlines()[-1]}")
    print("Check 5 PASSED.\n")


def main():
    test_manifest_content()
    test_delete_template_excluded()
    test_domains_match_ids_manifest()
    test_real_cli_opt_in()
    test_soa_guard()
    print("ALL CHECKS PASSED.")


if __name__ == "__main__":
    main()
