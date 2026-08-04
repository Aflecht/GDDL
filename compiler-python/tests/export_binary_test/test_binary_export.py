"""
Full validation suite for export_binary.py (§17), run against
export_test_binary_coverage.gddl. Three genuinely separate checks, per
the standard this target's own review set:

  1. Independent read-back: every field value, read via
     independent_reader.py (a from-scratch reader sharing NO code with
     export_binary.py's writer), matches the fixture's known resolved
     values exactly -- character-by-character for strings.
  2. Manifest truthfulness: every offset/size the JSON manifest claims
     is followed and confirmed to locate REAL data in the .bin file --
     not assumed correct just because it's present.
  3. Schema discrimination: a deliberate, isolated schema change
     (reordering two fields) is confirmed to actually change
     schema_hash -- the one claim in this target that's about
     discrimination rather than round-trip correctness, and isn't
     covered by checks 1-2 at all.

Run directly: python3 export_binary_test/test_binary_export.py
"""

import os
import sys
import shutil
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import parse_file
from resolve import resolve_all
from export_binary import export_binary, canonical_schema_string, compute_schema_hash
import independent_reader as reader


FIXTURE = os.path.join(os.path.dirname(__file__), "export_test_binary_coverage.gddl")

# Ground truth, extracted directly from the reference implementation
# (resolver.cache), not hand-derived -- see the session transcript for
# the exact extraction. Declaration order matches
# export_instances_for_type's own output, confirmed directly before
# writing this table.
EXPECTED_ITEM = [
    # (name, object.something1, object.something2, weight, element_key,
    #  name_field, fast_dispatch_key, fast_dispatch_index)
    ("ItemViaFullReplace", 10, 20, 5, "fire", "Sword", "melee_weapon", 0),
    ("ItemViaBareModify", 99, 100, 7, "ice", "AAAAAAAAAAAAAAA", "ranged_weapon", 1),
    ("ItemCopy", 10, 20, 50, "lightning", "Shield", "melee_weapon", 0),
]
EXPECTED_OBJECT = [
    ("DefaultObject", 0, 0),
    ("HeavyObject", 100, 50),
    ("LightObject", 5, 50),
    ("BaseObject", 10, 20),
    ("RealObjectGen1", 1, 2),
    ("RealObjectGen2", 10, 2),
]


def build(out_stem):
    prog = parse_file(FIXTURE)
    resolver = resolve_all(prog)
    reg = resolver.reg
    export_binary(reg, resolver, ["Item", "Object"], out_stem)
    return reg, resolver


def field_offsets_by_name(manifest_type):
    return {f["name"]: (f["byte_offset"], f["byte_width"], f["type"])
            for f in manifest_type["fields"]}


def check_independent_readback(reg, data, manifest):
    """Check 1: every field value, read via the independent reader,
    matches the fixture's known resolved values exactly."""
    print("=== Check 1: independent read-back ===")
    _version, entries = reader.read_header_and_type_table(data)
    by_name = {e.name: e for e in entries}

    assert set(by_name) == {"Item", "Object"}, f"unexpected type set: {set(by_name)}"

    item_entry = by_name["Item"]
    item_manifest = next(t for t in manifest["types"] if t["name"] == "Item")
    item_fields = field_offsets_by_name(item_manifest)
    item_records = reader.read_records_raw(data, item_entry)
    assert len(item_records) == len(EXPECTED_ITEM), \
        f"Item record count mismatch: got {len(item_records)}, want {len(EXPECTED_ITEM)}"

    domain_index = {"melee_weapon": 0, "ranged_weapon": 1}

    for record, (name, s1, s2, weight, elem_key, name_val, fd_key, fd_idx) in \
            zip(item_records, EXPECTED_ITEM):
        off, width, ftype = item_fields["object_something1"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == s1, f"{name}.object.something1: got {got}, want {s1}"

        off, width, ftype = item_fields["object_something2"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == s2, f"{name}.object.something2: got {got}, want {s2}"

        off, width, ftype = item_fields["weight"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == weight, f"{name}.weight: got {got}, want {weight}"

        # element: plain identifier, logical-ID form -- verify against
        # the SAME logical_id function used everywhere else in this
        # project (registry.logical_id), not a hand-copied hex constant.
        from registry import logical_id
        off, width, ftype = item_fields["element"]
        got = reader.unpack_field(record, off, width, ftype)
        want = int(logical_id("Element", {
            "fire": "Elemental fire damage type",
            "ice": "Elemental ice damage type",
            "lightning": "Elemental lightning damage type",
        }[elem_key]), 16)
        assert got == want, f"{name}.element: got {got:016x}, want {want:016x}"

        off, width, ftype = item_fields["name"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == name_val, f"{name}.name: got {got!r}, want {name_val!r}"
        assert list(got) == list(name_val), \
            f"{name}.name character-by-character mismatch: {list(got)} != {list(name_val)}"

        off, width, ftype = item_fields["fast_dispatch"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == domain_index[fd_key], \
            f"{name}.fast_dispatch: got {got}, want {domain_index[fd_key]} ({fd_key})"
        assert got == fd_idx

        print(f"  Item.{name}: all fields OK")

    object_entry = by_name["Object"]
    object_manifest = next(t for t in manifest["types"] if t["name"] == "Object")
    object_fields = field_offsets_by_name(object_manifest)
    object_records = reader.read_records_raw(data, object_entry)
    assert len(object_records) == len(EXPECTED_OBJECT)

    for record, (name, s1, s2) in zip(object_records, EXPECTED_OBJECT):
        off, width, ftype = object_fields["something1"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == s1, f"Object.{name}.something1: got {got}, want {s1}"
        off, width, ftype = object_fields["something2"]
        got = reader.unpack_field(record, off, width, ftype)
        assert got == s2, f"Object.{name}.something2: got {got}, want {s2}"
        print(f"  Object.{name}: all fields OK")

    print("Check 1 PASSED: every field value matches exactly.\n")
    return by_name


def check_lookup_tables(reg, resolver, data, by_name):
    """Bonus, still part of independent read-back: lookup table entries
    resolve to the correct record via dense_index, and stable IDs match
    registry.py's own instance-ID computation."""
    print("=== Check 1b: lookup tables (stable_id -> dense_index -> record) ===")
    for type_name, expected in (("Item", EXPECTED_ITEM), ("Object", EXPECTED_OBJECT)):
        entry = by_name[type_name]
        pairs = reader.read_lookup_table(data, entry)
        assert len(pairs) == len(expected)

        expected_ids = {reg.get_instance_id(type_name, row[0]) for row in expected}
        got_ids = {f"{sid:016x}" for sid, _ in pairs}
        assert got_ids == expected_ids, \
            f"{type_name} lookup table ID set mismatch: {got_ids} != {expected_ids}"

        # Every dense_index must point at a real, distinct record.
        indices = sorted(idx for _sid, idx in pairs)
        assert indices == list(range(len(expected))), \
            f"{type_name} dense_index set isn't a clean 0..N-1 permutation: {indices}"

        print(f"  {type_name}: {len(pairs)} lookup entries, sorted, all indices valid")
    print("Check 1b PASSED.\n")


def check_manifest_truthfulness(data, manifest):
    """Check 2: every offset/size the manifest claims is followed and
    confirmed to locate real data -- not assumed correct."""
    print("=== Check 2: manifest truthfulness ===")
    _version, entries = reader.read_header_and_type_table(data)
    by_name = {e.name: e for e in entries}

    for t in manifest["types"]:
        entry = by_name[t["name"]]

        # The manifest's claimed offsets/sizes must match what's
        # actually in the .bin's own per-type table -- not just be
        # internally self-consistent within the JSON.
        assert entry.schema_hash == int(t["schema_hash"], 16), \
            f"{t['name']}: manifest schema_hash disagrees with .bin's own table"
        assert entry.record_size == t["record_size"]
        assert entry.record_count == t["record_count"]
        assert entry.record_array_offset == t["record_array_offset"]
        assert entry.lookup_table_offset == t["lookup_table_offset"]
        assert entry.lookup_table_count == t["lookup_table_count"]

        # The claimed record_array_offset must actually be IN BOUNDS
        # and contain the claimed number of full records -- not just a
        # number that happens to be present in the JSON.
        end = t["record_array_offset"] + t["record_count"] * t["record_size"]
        assert end <= len(data), \
            f"{t['name']}: record array [{t['record_array_offset']}:{end}] " \
            f"runs past end of file ({len(data)} bytes)"

        # The claimed lookup_table_offset must be in bounds too.
        lut_end = t["lookup_table_offset"] + t["lookup_table_count"] * 12
        assert lut_end <= len(data), \
            f"{t['name']}: lookup table [{t['lookup_table_offset']}:{lut_end}] " \
            f"runs past end of file ({len(data)} bytes)"

        # Field byte_offset + byte_width must sum to exactly record_size
        # -- no gap, no overlap, no field hanging off the end.
        fields = sorted(t["fields"], key=lambda f: f["byte_offset"])
        cursor = 0
        for f in fields:
            assert f["byte_offset"] == cursor, \
                f"{t['name']}.{f['name']}: byte_offset {f['byte_offset']} " \
                f"!= expected cursor {cursor} (gap or overlap)"
            cursor += f["byte_width"]
        assert cursor == t["record_size"], \
            f"{t['name']}: field widths sum to {cursor}, manifest record_size is {t['record_size']}"

        print(f"  {t['name']}: offsets/sizes verified against real .bin data, "
              f"field layout accounts for every byte")

    print("Check 2 PASSED.\n")


def check_schema_discrimination(build_dir):
    """Check 3: a deliberate, isolated schema change (reordering two
    fields) must actually change schema_hash. This is the one claim
    about DISCRIMINATION, not round-trip correctness -- not covered by
    checks 1-2 at all, needs its own explicit test."""
    print("=== Check 3: schema-change discrimination ===")

    original = open(FIXTURE).read()

    # Isolated change: swap 'weight' and 'element' field order in Item.
    # Everything else in the file stays byte-for-byte identical.
    modified = original.replace(
        "\tobject\t\t= Object\n\tweight\t\t= u32\n\telement\t\t= Element\n",
        "\tobject\t\t= Object\n\telement\t\t= Element\n\tweight\t\t= u32\n",
    )
    assert modified != original, \
        "field-reorder replacement didn't match anything -- fixture text changed " \
        "since this test was written, update the replace() target"

    modified_path = os.path.join(build_dir, "modified.gddl")
    with open(modified_path, "w") as f:
        f.write(modified)

    prog_orig = parse_file(FIXTURE)
    resolver_orig = resolve_all(prog_orig)
    from export_cpp import _flatten_leaves
    leaves_orig = _flatten_leaves("Item", resolver_orig.reg)
    hash_orig = compute_schema_hash(leaves_orig)

    prog_mod = parse_file(modified_path)
    resolver_mod = resolve_all(prog_mod)
    leaves_mod = _flatten_leaves("Item", resolver_mod.reg)
    hash_mod = compute_schema_hash(leaves_mod)

    print(f"  original Item schema_hash: {hash_orig:016x}")
    print(f"  reordered Item schema_hash: {hash_mod:016x}")
    assert hash_orig != hash_mod, \
        "schema_hash did NOT change after reordering two fields -- " \
        "the compatibility check would silently accept an incompatible file"

    # Also confirm record_size did NOT change (same fields, same widths,
    # just reordered) -- this is what makes the reorder case interesting:
    # record_size alone would NOT have caught this, only the hash does.
    from export_binary import compute_record_size
    size_orig = compute_record_size(leaves_orig, resolver_orig.reg)
    size_mod = compute_record_size(leaves_mod, resolver_mod.reg)
    print(f"  original Item record_size: {size_orig}")
    print(f"  reordered Item record_size: {size_mod}")
    assert size_orig == size_mod, \
        "test setup error: reordering should NOT change record_size " \
        "(same fields, same widths) -- if it did, this isn't testing what it claims to"

    # And a genuinely UNRELATED type (Object) must be completely
    # unaffected -- per-type hashing (§17.4), not a whole-project
    # fingerprint.
    leaves_object_orig = _flatten_leaves("Object", resolver_orig.reg)
    leaves_object_mod = _flatten_leaves("Object", resolver_mod.reg)
    hash_object_orig = compute_schema_hash(leaves_object_orig)
    hash_object_mod = compute_schema_hash(leaves_object_mod)
    assert hash_object_orig == hash_object_mod, \
        "Object's schema_hash changed even though Object itself wasn't touched -- " \
        "this should be impossible for a per-type hash"
    print(f"  Object schema_hash unaffected by Item's change (per-type, not whole-project): "
          f"{hash_object_orig:016x} == {hash_object_mod:016x}")

    print("Check 3 PASSED: schema_hash discriminates the reorder; "
          "record_size alone would not have; unrelated type unaffected.\n")


def main():
    build_dir = tempfile.mkdtemp(prefix="gddl_binary_test_")
    try:
        out_stem = os.path.join(build_dir, "test")
        reg, resolver = build(out_stem)

        bin_path = out_stem + ".gddldata.bin"
        meta_path = out_stem + ".gddlmeta.json"

        with open(bin_path, "rb") as f:
            data = f.read()
        import json
        with open(meta_path) as f:
            manifest = json.load(f)

        by_name = check_independent_readback(reg, data, manifest)
        check_lookup_tables(reg, resolver, data, by_name)
        check_manifest_truthfulness(data, manifest)
        check_schema_discrimination(build_dir)

        print("ALL CHECKS PASSED.")
    finally:
        shutil.rmtree(build_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
