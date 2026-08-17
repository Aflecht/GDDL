# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
A genuinely independent reader for `.gddldata.bin` files (§17.3),
built directly from the binary format's own docstring in
export_binary.py, using raw struct.unpack -- deliberately NOT
importing or reusing any of export_binary.py's writer-side functions
(TypeBinaryInfo, write_binary, pack_leaf_value, etc.).

The whole point of this file: a reader built from the same code that
wrote the file would only confirm the writer agrees with itself. This
reader is a second, from-scratch implementation of the same format
description, so a real writer bug (wrong offset math, wrong byte
order, wrong field width) has a genuine chance of being caught rather
than silently reproduced by both sides making the identical mistake.

This mirrors, deliberately, the same role the manifest's own
"independent code path" requirement plays for record_size vs
schema_hash (§17.4) -- independence is the actual mechanism that makes
a check meaningful, not a formality.
"""

import struct


class BinaryReadError(Exception):
    pass


class TypeTableEntry:
    def __init__(self, name, schema_hash, record_size, record_count,
                 record_array_offset, lookup_table_offset, lookup_table_count):
        self.name = name
        self.schema_hash = schema_hash
        self.record_size = record_size
        self.record_count = record_count
        self.record_array_offset = record_array_offset
        self.lookup_table_offset = lookup_table_offset
        self.lookup_table_count = lookup_table_count


def read_header_and_type_table(data: bytes):
    """Parses the global header and per-type table. Returns (format_version,
    [TypeTableEntry, ...])."""
    if data[0:4] != b"GDBD":
        raise BinaryReadError(f"bad magic: {data[0:4]!r}, expected b'GDBD'")
    format_version, type_count = struct.unpack_from("<BI", data, 4)
    if format_version != 1:
        raise BinaryReadError(f"unsupported format_version {format_version}")

    entries = []
    cursor = 9  # 4 (magic) + 1 (version) + 4 (type_count)
    for _ in range(type_count):
        (name_len,) = struct.unpack_from("<H", data, cursor)
        cursor += 2
        name = data[cursor:cursor + name_len].decode("utf-8")
        cursor += name_len
        (schema_hash, record_size, record_count,
         record_array_offset, lookup_table_offset,
         lookup_table_count) = struct.unpack_from("<QIIQQI", data, cursor)
        cursor += 8 + 4 + 4 + 8 + 8 + 4
        entries.append(TypeTableEntry(
            name, schema_hash, record_size, record_count,
            record_array_offset, lookup_table_offset, lookup_table_count))
    return format_version, entries


def read_records_raw(data: bytes, entry: TypeTableEntry):
    """Returns a list of `entry.record_count` raw byte-strings, each
    exactly `entry.record_size` bytes, read directly from
    `entry.record_array_offset` -- no field-level interpretation here,
    that's the caller's job (using the manifest's field list, or fixed
    domain knowledge, same as a real third-party consumer would)."""
    records = []
    off = entry.record_array_offset
    for i in range(entry.record_count):
        start = off + i * entry.record_size
        records.append(data[start:start + entry.record_size])
    return records


def read_lookup_table(data: bytes, entry: TypeTableEntry):
    """Returns a list of (stable_id, dense_index) pairs, read directly
    from entry.lookup_table_offset. Also verifies the sorted-by-id
    invariant the format guarantees (§17.3) -- a genuine independence
    check, not assumed true just because the writer claims it."""
    pairs = []
    off = entry.lookup_table_offset
    for i in range(entry.lookup_table_count):
        stable_id, dense_index = struct.unpack_from("<QI", data, off + i * 12)
        pairs.append((stable_id, dense_index))
    ids = [p[0] for p in pairs]
    if ids != sorted(ids):
        raise BinaryReadError(
            f"lookup table for {entry.name!r} is not sorted by stable_id "
            "-- format invariant violated")
    return pairs


def _independent_parse_array_type(field_type: str):
    """A SECOND, from-scratch parser of 'ElementType : dim1 : dim2 : ...'
    -- deliberately NOT importing registry._try_parse_array_type, for
    the exact same independence reason this whole file exists (see
    module docstring). Returns (element_type, dims) or None if
    field_type isn't array-shaped."""
    if ":" not in field_type:
        return None
    parts = [p.strip() for p in field_type.split(":")]
    element_type = parts[0]
    dims = [int(p) for p in parts[1:]]
    return element_type, dims


def _unpack_array_level(raw: bytes, dims, element_type: str, elem_width: int):
    """Row-major/contiguous unpack, one dimension at a time -- the exact
    same layout the writer's own _pack_array_value uses, confirmed
    independently here rather than assumed to match."""
    if len(dims) == 1:
        return [unpack_field(raw[i * elem_width:(i + 1) * elem_width], 0, elem_width, element_type)
                for i in range(dims[0])]
    stride = elem_width
    for d in dims[1:]:
        stride *= d
    return [_unpack_array_level(raw[i * stride:(i + 1) * stride], dims[1:], element_type, elem_width)
            for i in range(dims[0])]


def unpack_field(record: bytes, byte_offset: int, byte_width: int, field_type: str):
    """Unpacks a single field from a raw record's bytes, given the
    manifest's own field description (name/type/offset/width) -- this
    is exactly what a real third-party reader would do: consult the
    manifest for field layout, then read raw bytes at that offset."""
    raw = record[byte_offset:byte_offset + byte_width]

    ft = field_type.strip()

    array_shape = _independent_parse_array_type(ft)
    if array_shape is not None:
        element_type, dims = array_shape
        elem_width = byte_width
        for d in dims:
            elem_width //= d
        return _unpack_array_level(raw, dims, element_type, elem_width)

    if ft.startswith("@"):
        # indexed identifier: plain unsigned int of byte_width size
        fmt = {1: "<B", 2: "<H", 4: "<I", 8: "<Q"}[byte_width]
        return struct.unpack(fmt, raw)[0]
    if ft.startswith("string "):
        return raw.split(b"\x00", 1)[0].decode("utf-8")
    if ft in ("u8",):
        return struct.unpack("<B", raw)[0]
    if ft in ("i8",):
        return struct.unpack("<b", raw)[0]
    if ft in ("u16",):
        return struct.unpack("<H", raw)[0]
    if ft in ("i16",):
        return struct.unpack("<h", raw)[0]
    if ft in ("u32",):
        return struct.unpack("<I", raw)[0]
    if ft in ("i32",):
        return struct.unpack("<i", raw)[0]
    if ft in ("u64",):
        return struct.unpack("<Q", raw)[0]
    if ft in ("i64",):
        return struct.unpack("<q", raw)[0]
    if ft in ("f32",):
        return struct.unpack("<f", raw)[0]
    if ft in ("f64",):
        return struct.unpack("<d", raw)[0]
    # Plain identifier domain (no '@', no 'string', not a scalar token):
    # 8-byte logical ID, per §8.3's default-is-always-logical-ID rule.
    return struct.unpack("<Q", raw)[0]
