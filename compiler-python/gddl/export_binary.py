# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Binary export target, §17 of the spec: a standalone `.gddldata.bin` /
`.gddlmeta.json` pair, decoupled from any compile target, readable by
third-party software in any language.

First implementation pass, per the request that introduced this module:
the core mechanism solid and genuinely verified, not full coverage of
every field-width combination. §17.5 (the C++ compile-time header
table) is EXPLICITLY OUT OF SCOPE for this pass -- it lives in
export_cpp.py, not here, and isn't touched by this module. See
HANDOFF.md for that gap recorded plainly rather than silently skipped.

Reuses existing infrastructure rather than reimplementing it:
  - registry.fnv1a_64: the ONE FNV-1a-64 implementation in this
    codebase (refactored out of registry.logical_id specifically for
    this module to share -- verified byte-identical to the pre-refactor
    behavior before anything here was built on top of it).
  - export_cpp._flatten_leaves / _flatten_value: the same composition-
    flattening logic already shared across C++, Z80, and 6502.
  - export_cpp.export_instances_for_type: the same "every resolved,
    non-delete instance of this type" gather already used elsewhere.
  - export_cpp._string_n: the same `string N` token parser.

=====================================================================
BINARY FILE FORMAT -- authoritative definition. A future independent
implementation (§17.6's "keeping that computation identical across
implementations is a real, ongoing correctness obligation") must be
able to reproduce this exactly from this docstring alone.
=====================================================================

All multi-byte integers are little-endian (§17.3.1), no exceptions.
All struct.pack/unpack format strings in this module use the "<" prefix
throughout for exactly this reason -- never left to platform default.

GLOBAL HEADER (fixed size, 9 bytes):
    magic           4 bytes,  ASCII b"GDBD" ("GDDL Binary Data")
    format_version  u8,       value 1 for this format revision
    type_count      u32

PER-TYPE TABLE (type_count entries, immediately following the global
header, back to back, VARIABLE-LENGTH entries due to the name field):
    name_len              u16     byte length of the UTF-8 type name
    name                  name_len bytes, UTF-8, NOT null-terminated
    schema_hash           u64     FNV-1a-64, see "SCHEMA HASH" below
    record_size           u32     bytes per record, this type
    record_count          u32     number of records, this type
    record_array_offset   u64     absolute byte offset from file start
    lookup_table_offset   u64     absolute byte offset from file start
                                  (0 if lookup_table_count == 0)
    lookup_table_count    u32     always > 0 in this implementation --
                                  every instance has a stable ID (§6.8)
                                  unconditionally, so the "optional/
                                  absent" case the spec allows for
                                  never actually arises here. Flagged
                                  in HANDOFF.md as a known simplification,
                                  not silently assumed away.

This per-type table is fully self-describing WITHOUT the JSON manifest
-- §17.4's load-time compatibility check is a pure binary-to-binary
comparison per spec, so a reader must be able to get type name,
schema_hash, record_size, and both sets of offsets from the .bin file
alone. The manifest adds full field-level detail (name/type/byte
offset/width per field) the .bin intentionally never carries.

RECORD ARRAYS (one per type, in per-type-table order, back to back,
starting immediately after the last per-type table entry):
    record_count records, each exactly record_size bytes, packed
    contiguously, NO PADDING, in declaration order (matching
    _flatten_leaves' order exactly). One record = one instance's full
    flattened leaf list, concatenated.

LOOKUP TABLES (one per type, in per-type-table order, back to back,
starting immediately after the last record array):
    lookup_table_count entries, each 12 bytes:
        stable_id     u64   this instance's stable ID (§6.8)
        dense_index   u32   0-based position of this instance within
                             its type's own record array
    Sorted by stable_id ascending (binary-searchable) -- same shape as
    the C++ exporter's own registry table (§14.4), just serialized
    instead of `constexpr`.

LEAF VALUE ENCODING, per flattened leaf's declared type:
    u8/i8/u16/i16/u32/i32/u64/i64   the obvious fixed-width int, LE
    f32/f64                        IEEE-754, LE
    string N                      exactly N bytes, ASCIIZ (§4.1.1) --
                                   nothing new invented for this target
    Domain (plain, no @)          u64 -- the full logical ID hash
                                   (default-is-always-logical-ID, §8.3,
                                   never inferred from context)
    @Domain (indexed)             the domain's OWN declared width
                                   (u8/u16/u32/u64), the dense index
    Composition (nested define)   flattened away entirely by
                                   _flatten_leaves/_flatten_value --
                                   never appears as its own leaf

SCHEMA HASH (§17.4): FNV-1a-64 over a canonical serialization of the
type's complete FLATTENED leaf list (name, type, order) -- deliberately
the flattened path, not just top-level field names, since that's what
actually determines the byte layout. Canonical form, precisely:

    For each leaf, in _flatten_leaves' order:
        "{flattened_path}\x1f{type_tokens.strip()}"
    joined with "\x1e" between leaves (no trailing separator).
    Encoded as UTF-8, then registry.fnv1a_64() over those bytes.

\x1f (Unit Separator) and \x1e (Record Separator) are used specifically
because no GDDL identifier or type token can ever contain them (GDDL
identifiers are alphanumeric/underscore only) -- this makes the join
unambiguous: two different (name, type) sequences can never canonicalize
to the same string. See export_cpp.canonical_schema_string() (moved
there so §17.5's C++ compile-time table can call it directly, no
circular import -- see that function's own docstring); this docstring
and that function must never drift from each other.

RECORD_SIZE is computed by an INDEPENDENTLY-derived code path from
SCHEMA_HASH -- summing leaf byte widths directly, never derived from or
checked against the hash (§17.4's own stated reason: this catches a bug
IN the hash computation itself, which a hash-only check structurally
cannot).
"""

import json
import os
import struct

from registry import fnv1a_64
from export_cpp import (
    _flatten_leaves, _flatten_value, _string_n, export_instances_for_type,
    _leaf_binary_kind, leaf_binary_width, canonical_schema_string,
    compute_schema_hash, compute_record_size, SchemaComputationError,
)
from resolve import StructValue, IdentifierRef
from validate import check_and_report

MAGIC = b"GDBD"
FORMAT_VERSION = 1


class ExportBinaryError(SchemaComputationError):
    """Kept as its own name for backward compatibility with anything
    catching ExportBinaryError specifically, but IS-A
    SchemaComputationError now that the leaf-classification logic that
    used to raise it directly lives in export_cpp.py and raises
    SchemaComputationError instead -- callers catching either name see
    every error this module (or export_cpp's schema-computation code)
    can raise for an unsupported field type."""
    pass


def pack_leaf_value(value, type_tokens: str, reg) -> bytes:
    """Packs one flattened leaf's resolved value into its binary
    encoding, per this module's docstring's "LEAF VALUE ENCODING"
    table."""
    kind, fmt, width = _leaf_binary_kind(type_tokens, reg)

    if kind == "string":
        if not isinstance(value, str):
            raise ExportBinaryError(
                f"expected a string value for 'string {width}' field, "
                f"got {value!r}")
        content = value.encode("utf-8")
        if len(content) > width:
            raise ExportBinaryError(
                f"string value {value!r} is {len(content)} UTF-8 bytes, "
                f"doesn't fit in string {width} -- should already have "
                "been caught as a phase 6 string_length error before "
                "export ever ran")
        return content + b"\x00" * (width - len(content))

    if kind == "logical_id":
        if not isinstance(value, IdentifierRef):
            raise ExportBinaryError(
                f"expected an identifier value, got {value!r}")
        return struct.pack("<Q", int(value.logical_id, 16))

    if kind == "indexed":
        if not isinstance(value, IdentifierRef):
            raise ExportBinaryError(
                f"expected an identifier value, got {value!r}")
        block = reg.identifiers[value.domain]
        index = next(i for i, e in enumerate(block.entries) if e.key == value.key)
        return struct.pack(f"<{fmt}", index)

    # scalar
    return struct.pack(f"<{fmt}", value)


def pack_record(value: StructValue, type_name: str, reg, leaves) -> bytes:
    """Packs one full instance's flattened leaf values into its record
    bytes -- concatenation of pack_leaf_value over _flatten_value's
    output, in the exact order _flatten_leaves produced `leaves` in."""
    flat_values = _flatten_value(value, type_name, reg)
    return b"".join(
        pack_leaf_value(v, tokens, reg)
        for v, (_path, tokens) in zip(flat_values, leaves))


class TypeBinaryInfo:
    """Everything gathered for one type, ready to serialize."""

    def __init__(self, name, leaves, schema_hash, record_size,
                 records, lookup_entries):
        self.name = name
        self.leaves = leaves                # [(path, type_tokens), ...]
        self.schema_hash = schema_hash
        self.record_size = record_size
        self.records = records              # [bytes, ...], declaration order
        self.lookup_entries = lookup_entries  # [(stable_id:int, dense_index:int), ...] sorted


def gather_binary_ir(reg, resolver, type_names):
    """Full IR for a binary export of the given types. Returns a list
    of TypeBinaryInfo, in the order type_names was given."""
    result = []
    for type_name in type_names:
        if type_name not in reg.defines:
            raise ExportBinaryError(f"unknown type {type_name!r}")

        leaves = _flatten_leaves(type_name, reg)
        schema_hash = compute_schema_hash(leaves)
        record_size = compute_record_size(leaves, reg)

        instances = export_instances_for_type(type_name, reg, resolver)
        records = [pack_record(value, type_name, reg, leaves)
                   for _name, value in instances]

        lookup_entries = []
        for i, (name, _value) in enumerate(instances):
            stable_id_hex = reg.get_instance_id(type_name, name)
            lookup_entries.append((int(stable_id_hex, 16), i))
        lookup_entries.sort(key=lambda e: e[0])

        result.append(TypeBinaryInfo(
            name=type_name, leaves=leaves, schema_hash=schema_hash,
            record_size=record_size, records=records,
            lookup_entries=lookup_entries))
    return result


def write_binary(types_ir, out_path: str):
    """Writes the .gddldata.bin file per this module's docstring's
    binary format definition. Returns the per-type offset info
    computed along the way (used by write_manifest so the manifest's
    own offsets are guaranteed to match what was actually written, not
    recomputed a second, potentially-drifting way)."""
    header = MAGIC + struct.pack("<BI", FORMAT_VERSION, len(types_ir))

    type_table_entries = []
    for t in types_ir:
        name_bytes = t.name.encode("utf-8")
        lookup_count = len(t.lookup_entries)
        # offsets filled in below once every size is known
        type_table_entries.append({
            "name_bytes": name_bytes,
            "schema_hash": t.schema_hash,
            "record_size": t.record_size,
            "record_count": len(t.records),
            "lookup_count": lookup_count,
        })

    # Fixed-size portion of each type-table entry (everything after the
    # variable-length name): 8+4+4+8+8+4 = 36 bytes.
    _FIXED_ENTRY_SIZE = 36

    type_table_size = sum(
        2 + len(e["name_bytes"]) + _FIXED_ENTRY_SIZE
        for e in type_table_entries)

    record_array_offsets = []
    cursor = len(header) + type_table_size
    for t, e in zip(types_ir, type_table_entries):
        record_array_offsets.append(cursor)
        cursor += e["record_count"] * e["record_size"]

    lookup_table_offsets = []
    for t, e in zip(types_ir, type_table_entries):
        lookup_table_offsets.append(cursor if e["lookup_count"] else 0)
        cursor += e["lookup_count"] * 12

    with open(out_path, "wb") as f:
        f.write(header)
        for e, rec_off, lut_off in zip(
                type_table_entries, record_array_offsets, lookup_table_offsets):
            f.write(struct.pack("<H", len(e["name_bytes"])))
            f.write(e["name_bytes"])
            f.write(struct.pack("<QIIQQI",
                                 e["schema_hash"], e["record_size"],
                                 e["record_count"], rec_off, lut_off,
                                 e["lookup_count"]))
        for t in types_ir:
            for rec in t.records:
                f.write(rec)
        for t in types_ir:
            for stable_id, dense_index in t.lookup_entries:
                f.write(struct.pack("<QI", stable_id, dense_index))

    return {
        "type_table_entries": type_table_entries,
        "record_array_offsets": record_array_offsets,
        "lookup_table_offsets": lookup_table_offsets,
    }


def write_manifest(types_ir, reg, offsets_info, bin_filename: str, out_path: str):
    """Writes the .gddlmeta.json manifest (§17.2): every offset/size the
    .bin's own header states, PLUS full field-level detail the .bin
    never carries. Takes offsets_info directly from write_binary's
    return value rather than recomputing offsets a second way -- the
    two must describe the same file by construction, not by agreement."""
    manifest = {
        "format_version": FORMAT_VERSION,
        "data_file": bin_filename,
        "types": [],
    }

    for t, entry, rec_off, lut_off in zip(
            types_ir, offsets_info["type_table_entries"],
            offsets_info["record_array_offsets"],
            offsets_info["lookup_table_offsets"]):
        fields = []
        byte_offset = 0
        for path, type_tokens in t.leaves:
            width = leaf_binary_width(type_tokens, reg)
            fields.append({
                "name": path,
                "type": type_tokens.strip(),
                "byte_offset": byte_offset,
                "byte_width": width,
            })
            byte_offset += width

        manifest["types"].append({
            "name": t.name,
            "schema_hash": f"{t.schema_hash:016x}",
            "record_size": t.record_size,
            "record_count": entry["record_count"],
            "record_array_offset": rec_off,
            "lookup_table_offset": lut_off,
            "lookup_table_count": entry["lookup_count"],
            "fields": fields,
        })

    with open(out_path, "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")


def export_binary(reg, resolver, type_names, out_stem: str):
    """Top-level entry point: writes both {out_stem}.gddldata.bin and
    {out_stem}.gddlmeta.json. Returns the TypeBinaryInfo list (useful
    for tests that want to inspect the IR without re-parsing the
    written files)."""
    types_ir = gather_binary_ir(reg, resolver, type_names)
    bin_path = out_stem + ".gddldata.bin"
    meta_path = out_stem + ".gddlmeta.json"
    offsets_info = write_binary(types_ir, bin_path)
    write_manifest(types_ir, reg, offsets_info,
                    os.path.basename(bin_path), meta_path)
    return types_ir


def _cli():
    import argparse
    import sys
    from combine import resolve_inputs, compile_multi, CombineError

    ap = argparse.ArgumentParser(description="GDDL -> standalone binary exporter")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--type", dest="types", action="append", required=True,
                     help="type to export (repeatable)")
    ap.add_argument("-o", "--output", required=True,
                     help="output stem (writes <stem>.gddldata.bin and <stem>.gddlmeta.json)")
    args = ap.parse_args()

    try:
        paths = resolve_inputs(args.source)
    except CombineError as e:
        ap.error(str(e))

    result = compile_multi(paths)
    if result["status"] == "parse_error":
        err = result["error"]
        print(f"{err['file']}:{err['line']}: {err['message']}", file=sys.stderr)
        sys.exit(1)
    resolver = result["resolver"]
    if not check_and_report(resolver):
        sys.exit(1)
    export_binary(resolver.reg, resolver, args.types, args.output)
    print(f"wrote {args.output}.gddldata.bin and {args.output}.gddlmeta.json")


if __name__ == "__main__":
    _cli()
