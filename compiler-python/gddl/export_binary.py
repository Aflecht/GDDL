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

GLOBAL HEADER (fixed size, 13 bytes as of format_version 2; 9 bytes for
format_version 1, before pools existed):
    magic           4 bytes,  ASCII b"GDBD" ("GDDL Binary Data")
    format_version  u8,       value 2 for this format revision (was 1
                              before pools existed; a reader seeing a
                              stale format_version=1 file has no
                              pool_count field to read at all -- it
                              must fail cleanly rather than misparse
                              the byte immediately following type_count
                              as something else)
    type_count      u32
    pool_count      u32       (§22.4, new in format_version 2)

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

POOL TABLE (pool_count entries, new in format_version 2, immediately
following the per-type table, back to back, VARIABLE-LENGTH entries
due to the two name fields):
    name_len              u16     byte length of the UTF-8 pool name
    name                  name_len bytes, UTF-8, NOT null-terminated
    type_name_len         u16     byte length of the UTF-8 type name
                                   this pool reserves records of
    type_name             type_name_len bytes, UTF-8
    schema_hash           u64     same computation as a real type
                                   entry's own schema_hash -- lets a
                                   reader cross-check shape compatibility
                                   against a same-named type entry, if
                                   one also appears in this same file
    record_size           u32     bytes per record, same computation
                                   as a real type entry's own
    record_count          u32     the pool's declared count (§22.1's N)

A pool table entry carries NO offset field, unlike a type entry, and
deliberately writes NO bytes anywhere else in the file for its own
records -- a pool is reserved, UNINITIALIZED storage by design (§22.4:
"the only export target this format's own document ever intended to be
read directly by a shipping game at runtime" is the exact reason this
target can honor "genuinely uninitialized, free of file cost" more
literally than any compiled target: there is no compiled artifact to
reserve space IN, the game's own runtime loader is responsible for
allocating record_size * record_count bytes of its OWN memory for this
pool, keyed by name, the moment it reads this entry. Writing real bytes
for it would also fight this format's own determinism guarantee (Core
Principle 5 -- same source always produces byte-identical output):
"uninitialized" has no single deterministic byte pattern to write.

RECORD ARRAYS (one per type, in per-type-table order, back to back,
starting immediately after the last per-type table entry, or the last
pool table entry if any pools exist -- pools contribute no entries of
their own here, only the type table's real records do):
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

from .registry import fnv1a_64
from .export_cpp import (
    _flatten_leaves, _flatten_value, _string_n, export_instances_for_type,
    _leaf_binary_kind, leaf_binary_width, canonical_schema_string,
    compute_schema_hash, compute_record_size, SchemaComputationError,
)
from .resolve import StructValue, IdentifierRef
from .validate import check_and_report

MAGIC = b"GDBD"
FORMAT_VERSION = 2  # §22.4: bumped from 1 -- global header gained pool_count,
                    # and a new pool table section was added. A stale
                    # format_version=1 reader has no pool_count field to read
                    # and must fail cleanly rather than misparse the file.


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

    if kind == "array":
        # Arrays design: `fmt` carries the ArrayTypeInfo itself for this
        # kind (see _leaf_binary_kind's own docstring on this module's
        # loosely-typed (kind, fmt, width) shape -- fmt's meaning is
        # already kind-dependent for every other kind too). Packs each
        # leaf element via THIS SAME function, recursively -- an array
        # element is always scalar or string N (enforced at
        # registration), never itself array-shaped, so there's no risk
        # of this recursion re-entering the "array" branch.
        array_info = fmt
        return _pack_array_value(value, array_info.dims, array_info.element_type, reg)

    # scalar
    return struct.pack(f"<{fmt}", value)


def _pack_array_value(value, dims, element_type: str, reg) -> bytes:
    """Row-major, contiguous, no padding -- packs each element in turn,
    recursing one dimension at a time, concatenating the results.
    Confirmed to match the same layout a real compiled nested
    std::array<...> produces (pointer-arithmetic stride check against
    real MSVC output, not assumed) -- see HANDOFF.md."""
    if len(value) != dims[0]:
        raise ExportBinaryError(
            f"array value has {len(value)} element(s) at this nesting "
            f"level, expected {dims[0]} -- should already have been "
            "caught as a phase 6 array_shape_mismatch error before "
            "export ever ran")
    if len(dims) == 1:
        return b"".join(pack_leaf_value(v, element_type, reg) for v in value)
    return b"".join(_pack_array_value(v, dims[1:], element_type, reg) for v in value)


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


class PoolBinaryInfo:
    """§22.4: everything gathered for one pool, ready to serialize.
    No .records/.lookup_entries -- a pool carries no values at all, only
    shape and count; nothing is ever packed for it."""

    def __init__(self, name, type_name, leaves, schema_hash, record_size, count):
        self.name = name
        self.type_name = type_name
        self.leaves = leaves                # [(path, type_tokens), ...]
        self.schema_hash = schema_hash
        self.record_size = record_size
        self.count = count


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


def gather_pool_binary_ir(reg, type_names) -> list:
    """§22.4: every declared pool whose own TypeName is among the types
    actually being exported this run (--type selection) -- same
    reasoning as every other target's identical function. schema_hash/
    record_size are computed the exact same way a real type entry's own
    are (compute_schema_hash/compute_record_size, the same functions,
    never a second independent computation) -- so a pool and a same-
    shaped type entry, if both appear in one file, are directly
    comparable without a reader re-deriving anything."""
    result = []
    for name, node in reg.pools.items():
        if node.type_name not in type_names:
            continue
        leaves = _flatten_leaves(node.type_name, reg)
        schema_hash = compute_schema_hash(leaves)
        record_size = compute_record_size(leaves, reg)
        result.append(PoolBinaryInfo(
            name=name, type_name=node.type_name, leaves=leaves,
            schema_hash=schema_hash, record_size=record_size, count=node.count))
    return result


def write_binary(types_ir, out_path: str, pools_ir: list = None):
    """Writes the .gddldata.bin file per this module's docstring's
    binary format definition. Returns the per-type offset info
    computed along the way (used by write_manifest so the manifest's
    own offsets are guaranteed to match what was actually written, not
    recomputed a second, potentially-drifting way)."""
    pools_ir = pools_ir or []
    header = MAGIC + struct.pack("<BII", FORMAT_VERSION, len(types_ir), len(pools_ir))

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

    # §22.4, format_version 2: pool table entries -- two variable-
    # length name fields (pool name, type name), then a fixed 16-byte
    # tail (schema_hash u64 + record_size u32 + record_count u32).
    pool_table_entries = []
    for p in pools_ir:
        pool_name_bytes = p.name.encode("utf-8")
        type_name_bytes = p.type_name.encode("utf-8")
        pool_table_entries.append({
            "pool_name_bytes": pool_name_bytes,
            "type_name_bytes": type_name_bytes,
            "schema_hash": p.schema_hash,
            "record_size": p.record_size,
            "record_count": p.count,
        })
    _POOL_FIXED_ENTRY_SIZE = 16
    pool_table_size = sum(
        2 + len(e["pool_name_bytes"]) + 2 + len(e["type_name_bytes"]) + _POOL_FIXED_ENTRY_SIZE
        for e in pool_table_entries)

    record_array_offsets = []
    cursor = len(header) + type_table_size + pool_table_size
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
        for e in pool_table_entries:
            f.write(struct.pack("<H", len(e["pool_name_bytes"])))
            f.write(e["pool_name_bytes"])
            f.write(struct.pack("<H", len(e["type_name_bytes"])))
            f.write(e["type_name_bytes"])
            f.write(struct.pack("<QII", e["schema_hash"], e["record_size"], e["record_count"]))
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
        "pool_table_entries": pool_table_entries,
    }


def write_manifest(types_ir, reg, offsets_info, bin_filename: str, out_path: str,
                    pools_ir: list = None):
    """Writes the .gddlmeta.json manifest (§17.2): every offset/size the
    .bin's own header states, PLUS full field-level detail the .bin
    never carries. Takes offsets_info directly from write_binary's
    return value rather than recomputing offsets a second way -- the
    two must describe the same file by construction, not by agreement.

    §22.4: `pools` is a new top-level list, same shape convention as
    `types` (a `fields` list, byte_offset/byte_width per field) but with
    `count` instead of `record_count`/offsets -- a pool has no records
    and nothing written anywhere in the .bin for its own data, so there
    is no record_array_offset/lookup_table_offset/lookup_table_count to
    report; a reader allocates its own storage per §22.4's own binary-
    format documentation above."""
    pools_ir = pools_ir or []
    manifest = {
        "format_version": FORMAT_VERSION,
        "data_file": bin_filename,
        "types": [],
        "pools": [],
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

    for p in pools_ir:
        fields = []
        byte_offset = 0
        for path, type_tokens in p.leaves:
            width = leaf_binary_width(type_tokens, reg)
            fields.append({
                "name": path,
                "type": type_tokens.strip(),
                "byte_offset": byte_offset,
                "byte_width": width,
            })
            byte_offset += width

        manifest["pools"].append({
            "name": p.name,
            "type": p.type_name,
            "schema_hash": f"{p.schema_hash:016x}",
            "record_size": p.record_size,
            "count": p.count,
            "fields": fields,
        })

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")


def export_binary(reg, resolver, type_names, out_stem: str):
    """Top-level entry point: writes both {out_stem}.gddldata.bin and
    {out_stem}.gddlmeta.json. Returns the TypeBinaryInfo list (useful
    for tests that want to inspect the IR without re-parsing the
    written files)."""
    types_ir = gather_binary_ir(reg, resolver, type_names)
    pools_ir = gather_pool_binary_ir(reg, type_names)
    bin_path = out_stem + ".gddldata.bin"
    meta_path = out_stem + ".gddlmeta.json"
    offsets_info = write_binary(types_ir, bin_path, pools_ir=pools_ir)
    write_manifest(types_ir, reg, offsets_info,
                    os.path.basename(bin_path), meta_path, pools_ir=pools_ir)
    return types_ir


def _cli():
    import argparse
    import sys
    from .combine import resolve_inputs, compile_multi, CombineError
    from .export_ids import write_ids_manifest

    ap = argparse.ArgumentParser(description="GDDL -> standalone binary exporter")
    ap.add_argument("source", nargs="+",
                     help="one or more .gddl files or glob patterns")
    ap.add_argument("--type", dest="types", action="append", required=True,
                     help="type to export (repeatable)")
    ap.add_argument("--emit-ids-manifest", action="store_true",
                     help="also write <output>.gddlids.json, every identifier/flags "
                          "domain declared, for cross-mod script references (default: off)")
    ap.add_argument("-o", "--output", required=True,
                     help="output stem (writes <stem>.gddldata.bin and <stem>.gddlmeta.json)")
    ap.add_argument("--verbose-errors", action="store_true",
                     help="tag each error with its internal [phase N, check] (default: off)")
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
    if not check_and_report(resolver, verbose=args.verbose_errors):
        sys.exit(1)
    export_binary(resolver.reg, resolver, args.types, args.output)
    print(f"wrote {args.output}.gddldata.bin and {args.output}.gddlmeta.json")

    if args.emit_ids_manifest:
        manifest_path = write_ids_manifest(resolver.reg, args.output, resolver=resolver)
        print(f"wrote {manifest_path}")


if __name__ == "__main__":
    _cli()
