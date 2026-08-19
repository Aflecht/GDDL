# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Validation suite for --emit-ids-manifest (SPEC.md section 20).

Six genuinely separate checks:

  1. build_ids_manifest() content, called directly against a real
     resolved Registry: every field in both domain kinds (identifier:
     key/logical_id/description; flags: key/bit, no description),
     with logical_id cross-checked against an independent call to
     registry.logical_id() (the same function every other logical-ID
     consumer in this project calls -- not a hand-copied hex constant),
     not just trusted because build_ids_manifest() itself produced it.
  2. Domain-inclusion independence from --emit-all-domains: the fixture's
     ComponentFlags domain is never referenced by any field on Entity,
     yet must still appear in the manifest -- this is the manifest's
     whole point (every declared domain, unconditionally), a genuinely
     different rule from what --emit-all-domains controls for
     target-language code generation.
  3. The real CLI, real subprocess (matching this project's own
     standard for CLI-level regressions -- see test_68000_cli.py):
     --emit-ids-manifest writes <output>.gddlids.json; omitting the
     flag writes no such file at all (confirms genuinely opt-in, not
     always-on).
  4. The --emit-ids-manifest-requires--output guard, real CLI: 6502
     (stdout-default output) rejects the combination with a clear
     error and nonzero exit, rather than silently picking a stem name
     nobody asked for.
  5. The `instances` section (added for gscript's Type::instance_name
     resolution): omitting `resolver` from build_ids_manifest() leaves
     the returned dict exactly as before (no `instances` key at all) --
     the shape export_bindings.py's own build_ids_manifest(reg) call
     still relies on, since it embeds this dict verbatim into
     .gddlbindings.json and already carries its own per-type instances
     list under `types[]`.
  6. The `instances` section's actual content, resolver passed: every
     `define` (here just Entity, unconditionally -- same "every type,
     not just referenced ones" rule domains already follow), every
     resolved non-delete instance's name and stable_id, cross-checked
     against an independent reg.get_instance_id() call -- the same
     function export_bindings.py's own types[].instances already uses,
     confirming both manifests compute a name's stable ID via the one
     shared code path, never two.

Run directly: python3 test_ids_manifest.py
"""

import json
import os
import subprocess
import sys

_DIR = os.path.dirname(os.path.abspath(__file__))
_COMPILER_ROOT = os.path.normpath(os.path.join(_DIR, "..", ".."))
sys.path.insert(0, _COMPILER_ROOT)

from gddl.parser import parse_file
from gddl.resolve import resolve_all
from gddl.registry import logical_id
from gddl.export_ids import build_ids_manifest

FIXTURE = os.path.join(_DIR, "export_test_ids_manifest.gddl")


def _resolve_fixture():
    prog = parse_file(FIXTURE)
    resolver = resolve_all(prog)
    assert not resolver.reg.duplicate_errors, resolver.reg.duplicate_errors
    assert not resolver.errors, resolver.errors
    return resolver


def test_manifest_content():
    print("=== Check 1: manifest content, both domain kinds ===")
    resolver = _resolve_fixture()
    manifest = build_ids_manifest(resolver.reg)

    by_name = {d["name"]: d for d in manifest["domains"]}
    assert set(by_name) == {"ActionAttack", "ComponentFlags"}, by_name.keys()

    action = by_name["ActionAttack"]
    assert action["kind"] == "identifier"
    members = {m["key"]: m for m in action["members"]}
    assert set(members) == {"melee_weapon", "ranged_weapon"}
    for key, description in (
        ("melee_weapon", "Standard attack done with a melee weapon"),
        ("ranged_weapon", "Standard attack done with a ranged weapon"),
    ):
        m = members[key]
        assert m["description"] == description, m
        # Independently recomputed, not just trusting build_ids_manifest's
        # own use of the same underlying registry table.
        expected_lid = logical_id("ActionAttack", description)
        assert m["logical_id"] == expected_lid, (m["logical_id"], expected_lid)
        assert isinstance(m["logical_id"], str) and len(m["logical_id"]) == 16, m
    print("  ActionAttack (identifier): keys, descriptions, and "
          "independently-recomputed logical_id hex strings all match")

    flags = by_name["ComponentFlags"]
    assert flags["kind"] == "flags"
    assert flags["width"] == "u8"
    members = {m["key"]: m for m in flags["members"]}
    assert set(members) == {"none", "is_damageable", "is_pickupable", "is_movable"}
    assert "bit" not in members["none"], members["none"]  # zero sentinel, claims no bit
    assert "description" not in members["none"], "flags members carry no description at all"
    assert members["is_damageable"]["bit"] == 0
    assert members["is_pickupable"]["bit"] == 1  # auto-assigned, skips explicit bit 2
    assert members["is_movable"]["bit"] == 2
    print("  ComponentFlags (flags): keys, bit positions (explicit + auto), "
          "and the zero-sentinel's bit-less shape all match")
    print("Check 1 PASSED.\n")


def test_domain_inclusion_independent_of_emit_all_domains():
    print("=== Check 2: unreferenced domain still included ===")
    resolver = _resolve_fixture()
    manifest = build_ids_manifest(resolver.reg)
    names = {d["name"] for d in manifest["domains"]}
    # ComponentFlags is declared but never referenced by any field on
    # Entity in this fixture -- confirms the manifest doesn't follow
    # --emit-all-domains' referenced-only default.
    assert "ComponentFlags" in names, names
    print("  ComponentFlags (unreferenced by any field) is present -- "
          "manifest inclusion is unconditional, not emit-all-domains-gated")
    print("Check 2 PASSED.\n")


def test_real_cli_opt_in():
    print("=== Check 3: real CLI, --emit-ids-manifest is genuinely opt-in ===")
    import tempfile
    tmp = tempfile.gettempdir()
    stem_with = os.path.join(tmp, "gddl_ids_manifest_test_with")
    stem_without = os.path.join(tmp, "gddl_ids_manifest_test_without")
    manifest_with = stem_with + ".gddlids.json"
    manifest_without = stem_without + ".gddlids.json"
    for p in (manifest_with, manifest_without):
        if os.path.exists(p):
            os.remove(p)

    result = subprocess.run(
        [sys.executable, "-m", "gddl.export_cpp", FIXTURE,
         "--emit-ids-manifest", "-o", stem_with],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result.returncode == 0, result.stderr
    assert os.path.isfile(manifest_with), "flag passed but no manifest file was written"
    with open(manifest_with, encoding="utf-8") as f:
        data = json.load(f)
    names = {d["name"] for d in data["domains"]}
    assert names == {"ActionAttack", "ComponentFlags"}, names
    print("  --emit-ids-manifest: file written, real CLI, real content")

    instances_by_type = {t["name"]: t for t in data["instances"]}
    assert set(instances_by_type) == {"Entity"}, instances_by_type.keys()
    hero_members = {m["name"]: m["stable_id"] for m in instances_by_type["Entity"]["members"]}
    assert set(hero_members) == {"Hero"}, hero_members
    assert isinstance(hero_members["Hero"], str) and len(hero_members["Hero"]) == 16, hero_members
    print("  instances section: present via real CLI, Entity/Hero with a 16-hex-digit stable_id")

    result2 = subprocess.run(
        [sys.executable, "-m", "gddl.export_cpp", FIXTURE, "-o", stem_without],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result2.returncode == 0, result2.stderr
    assert not os.path.isfile(manifest_without), \
        "no --emit-ids-manifest flag, but a manifest file got written anyway"
    print("  no flag: no manifest file written -- genuinely opt-in, not always-on")

    for p in (manifest_with, manifest_without,
              stem_with + ".h", stem_with + ".cpp",
              stem_without + ".h", stem_without + ".cpp"):
        if os.path.exists(p):
            os.remove(p)
    print("Check 3 PASSED.\n")


def test_requires_output_guard():
    print("=== Check 4: --emit-ids-manifest requires -o (6502, stdout-default) ===")
    result = subprocess.run(
        [sys.executable, "-m", "gddl.export_6502", FIXTURE,
         "--type", "Entity", "--zp-base", "0x02", "--emit-ids-manifest"],
        capture_output=True, text=True, cwd=_COMPILER_ROOT)
    assert result.returncode != 0, \
        "expected a rejection (no -o given), but the CLI exited 0"
    assert "--emit-ids-manifest requires -o/--output" in result.stderr, result.stderr
    print("  correctly rejected: "
          f"{result.stderr.strip().splitlines()[-1]}")
    print("Check 4 PASSED.\n")


def test_instances_omitted_without_resolver():
    print("=== Check 5: instances section omitted when resolver isn't given ===")
    resolver = _resolve_fixture()
    manifest = build_ids_manifest(resolver.reg)  # no resolver= at all
    assert "instances" not in manifest, manifest.keys()
    print("  build_ids_manifest(reg) with no resolver: no 'instances' key at all -- "
          "the shape export_bindings.py's own embed still relies on")
    print("Check 5 PASSED.\n")


def test_instances_section_content():
    print("=== Check 6: instances section content, resolver passed ===")
    resolver = _resolve_fixture()
    manifest = build_ids_manifest(resolver.reg, resolver=resolver)

    by_type = {t["name"]: t for t in manifest["instances"]}
    assert set(by_type) == {"Entity"}, by_type.keys()  # every define, unconditionally

    members = {m["name"]: m["stable_id"] for m in by_type["Entity"]["members"]}
    assert set(members) == {"Hero"}, members

    # Independently recomputed, not just trusting build_ids_manifest's own
    # use of the same underlying registry table -- the same function
    # export_bindings.py's types[].instances already calls.
    expected = resolver.reg.get_instance_id("Entity", "Hero")
    assert members["Hero"] == expected, (members["Hero"], expected)
    assert isinstance(members["Hero"], str) and len(members["Hero"]) == 16, members
    print("  Entity/Hero: stable_id matches an independent reg.get_instance_id() call")
    print("Check 6 PASSED.\n")


def main():
    test_manifest_content()
    test_domain_inclusion_independent_of_emit_all_domains()
    test_real_cli_opt_in()
    test_requires_output_guard()
    test_instances_omitted_without_resolver()
    test_instances_section_content()
    print("ALL CHECKS PASSED.")


if __name__ == "__main__":
    main()
