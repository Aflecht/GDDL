# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Phase 4: Register.

Builds the lookup tables every later phase depends on, and is the
single place duplicate names get detected. Scope, deliberately narrow:
duplicate detection is WITHIN each namespace only:

  - identifier block names, among themselves
  - entry keys, within one identifier block
  - flags block names, among themselves
  - entry names, within one flags block
  - define block names, among themselves
  - field names, within one define block
  - instance names, among themselves

Cross-namespace collisions are NOT checked here.

Policy: first declaration wins, every subsequent duplicate is recorded
as a CompileError (phase 4, check="duplicate_name") and otherwise
ignored. Errors are collected, not raised immediately.

Also precomputes the logical ID (hash of description text) for every
identifier entry at registration time, once.

Also detects circular instance-copy references here (spec §6.1
addition) -- builds a dependency graph from every `= Source` reference,
including nested `field = Source` full-replace references at any depth
(the same underlying copy-from relationship, just at nested scope), and
runs ordinary cycle detection on it before phase 6 resolution ever
starts. This replaces what used to be a runtime recursion guard in the
resolver (which could only report "a cycle exists somewhere," via
generic recursion-depth-style detection) with an actual designed check
that names the exact cycle, e.g. `Human_Fighter -> Boss -> Human_Fighter`.
"""

from .ast_nodes import (
    Program, IdentifierBlock, FlagsBlock, DefineBlock, InstanceDecl,
    AssignStmt, BareFieldStmt,
)
from .errors import CompileError

# FNV-1a, 64-bit output, over the UTF-8 bytes of the description text
# exactly as written -- no normalization.
_FNV64_OFFSET_BASIS = 0xcbf29ce484222325
_FNV64_PRIME = 0x100000001b3
_FNV64_MASK = 0xFFFFFFFFFFFFFFFF

# §8.3: indexed-mode width -> bit count, for the member-count capacity check
_INDEXED_WIDTH_BITS = {"u8": 8, "u16": 16, "u32": 32, "u64": 64}


def fnv1a_64(data: bytes) -> int:
    """The one FNV-1a-64 implementation in this codebase. Every other
    hash need in this project (identifier logical IDs §4.1.1, instance
    stable IDs §6.8, and binary-export schema_hash §17.4) MUST call this
    function rather than re-implementing the loop -- if two hash
    implementations exist by the end of any piece of work, that's a bug
    regardless of whether they currently happen to agree, per this
    project's own established discipline. Returns the raw 64-bit
    integer; callers format it however their own context needs (hex
    string for logical_id below, a u64 for binary serialization)."""
    h = _FNV64_OFFSET_BASIS
    for byte in data:
        h ^= byte
        h = (h * _FNV64_PRIME) & _FNV64_MASK
    return h


def logical_id(domain_name: str, description: str) -> str:
    """Permanent, order-independent ID for an identifier entry: FNV-1a-64
    over the UTF-8 bytes of `"{domain_name}::{description}"` exactly as
    written -- no normalization. Domain-qualified (spec §4.1.1, revised):
    without qualification, two different domains could coincidentally
    produce colliding IDs if their description texts ever happened to
    match (e.g. a reused placeholder string across unrelated domains) --
    the same collision risk instance stable IDs (§6.8) are designed to
    avoid from the start. Returned as a 16-hex-digit (64-bit) string."""
    h = fnv1a_64(f"{domain_name}::{description}".encode("utf-8"))
    return f"{h:016x}"


class Registry:
    def __init__(self, program: Program):
        self.identifiers = {}      # name -> IdentifierBlock
        self.flags = {}            # name -> FlagsBlock
        self.defines = {}          # name -> DefineBlock
        self.instances = {}        # name -> InstanceDecl
        self.logical_ids = {}      # (domain, key) -> precomputed logical ID
        self.identifier_widths = {}  # domain_name -> width string ('u8'/'u16'/'u32'/'u64'), §8.3
        self.flags_widths = {}     # domain_name -> width string, mandatory for flags (unlike identifier's)
        self.flags_values = {}     # (domain, member_name) -> resolved int value (0, or 1 << claimed bit)
        self.flags_bits = {}       # (domain, member_name) -> claimed bit index (int), absent for the zero sentinel
        self.instance_ids = {}     # (type_name, instance_name) -> precomputed stable ID
        self.duplicate_errors = []  # list of CompileError

        # Shared collision table: id (hex str) -> qualified name that
        # produced it. Covers every identifier logical ID AND every
        # instance stable ID (§6.8, not yet implemented -- phase 9/export
        # work) together, deliberately, since both share the same 64-bit
        # space and purpose. Whichever produces an ID second when two
        # qualified names collide is recorded as a phase-4 error; the
        # first registrant is unaffected (consistent with "first wins"
        # policy used for duplicate names).
        self._id_table = {}

        for node in program.children:
            if isinstance(node, IdentifierBlock):
                if node.name in self.identifiers:
                    self.duplicate_errors.append(CompileError(
                        phase=4,
                        check="duplicate_name",
                        line=node.line,
                        message=f"duplicate identifier domain name '{node.name}' "
                                "(first declaration wins, this one is ignored)",
                    ))
                    continue
                self.identifiers[node.name] = node
                seen_keys = {}
                for entry in node.entries:
                    if entry.key in seen_keys:
                        self.duplicate_errors.append(CompileError(
                            phase=4,
                            check="duplicate_name",
                            line=entry.line,
                            message=f"duplicate key '{entry.key}' in identifier "
                                    f"domain '{node.name}' (first wins)",
                        ))
                        continue
                    seen_keys[entry.key] = entry
                    lid = logical_id(node.name, entry.description)
                    qualified_name = f"{node.name}::{entry.description}"
                    self._check_id_collision(lid, (node.name, entry.key), qualified_name, entry.line)
                    self.logical_ids[(node.name, entry.key)] = lid

                # §8.3: width is committed once, at the domain's own
                # declaration. Capacity check is unconditional -- runs
                # the moment the domain is registered, regardless of
                # whether anything ever uses '@' on it.
                if node.width is not None:
                    self.identifier_widths[node.name] = node.width
                    bits = _INDEXED_WIDTH_BITS[node.width]
                    max_count = 2 ** bits
                    actual_count = len(seen_keys)
                    if actual_count > max_count:
                        self.duplicate_errors.append(CompileError(
                            phase=4,
                            check="indexed_width_overflow",
                            line=node.line,
                            message=f"identifier domain '{node.name}' declares indexed "
                                    f"width '{node.width}' (max {max_count} entries), but "
                                    f"has {actual_count} members -- exceeds what this "
                                    "width can address (§8.3)",
                        ))

            elif isinstance(node, FlagsBlock):
                if node.name in self.flags:
                    self.duplicate_errors.append(CompileError(
                        phase=4,
                        check="duplicate_name",
                        line=node.line,
                        message=f"duplicate flags domain name '{node.name}' "
                                "(first declaration wins, this one is ignored)",
                    ))
                    continue
                self.flags[node.name] = node
                self.flags_widths[node.name] = node.width

                seen_names = {}
                unique_entries = []
                for entry in node.entries:
                    if entry.name in seen_names:
                        self.duplicate_errors.append(CompileError(
                            phase=4,
                            check="duplicate_name",
                            line=entry.line,
                            message=f"duplicate member '{entry.name}' in flags "
                                    f"domain '{node.name}' (first wins)",
                        ))
                        continue
                    seen_names[entry.name] = entry
                    unique_entries.append(entry)

                self.duplicate_errors.extend(
                    self._assign_flags_bits(node, unique_entries))

            elif isinstance(node, DefineBlock):
                if node.name in self.defines:
                    self.duplicate_errors.append(CompileError(
                        phase=4,
                        check="duplicate_name",
                        line=node.line,
                        message=f"duplicate define name '{node.name}' "
                                "(first declaration wins, this one is ignored)",
                    ))
                    continue
                self.defines[node.name] = node
                seen_fields = {}
                for f in node.fields:
                    if f.name in seen_fields:
                        self.duplicate_errors.append(CompileError(
                            phase=4,
                            check="duplicate_name",
                            line=f.line,
                            message=f"duplicate field '{f.name}' in define "
                                    f"'{node.name}' (first wins)",
                        ))
                        continue
                    seen_fields[f.name] = f

            elif isinstance(node, InstanceDecl):
                if node.instance_name in self.instances:
                    self.duplicate_errors.append(CompileError(
                        phase=4,
                        check="duplicate_name",
                        line=node.line,
                        message=f"duplicate instance name '{node.instance_name}' "
                                "(first declaration wins, this one is ignored)",
                    ))
                    continue
                self.instances[node.instance_name] = node

                # Instance stable ID (§6.8): computed for EVERY declared
                # instance at registration, regardless of delete-marked
                # status or eventual resolve/export success -- this is
                # what closes the gap where a genuine instance-name
                # collision was previously invisible until someone
                # happened to run the exporter. Same shared collision
                # table identifiers already use (§4.1's Collision
                # Detection subsection), not a separate pool.
                iid = logical_id(node.type_name, node.instance_name)
                qualified_name = f"{node.type_name}::{node.instance_name}"
                self._check_id_collision(
                    iid, (node.type_name, node.instance_name), qualified_name, node.line)
                self.instance_ids[(node.type_name, node.instance_name)] = iid

        # Must run after self.instances/self.defines are fully populated,
        # since building dependency edges needs field_category() to know
        # which fields are struct-typed.
        self.circular_dependency_errors = self._detect_circular_dependencies()
        self.duplicate_errors.extend(self.circular_dependency_errors.values())

        # §8.3: '@Domain' field-type validation. Static, needs only
        # self.defines/self.identifiers/self.identifier_widths, all
        # already populated -- not tied to any specific instance, so
        # these go in the same global list duplicate_name/id_collision/
        # circular_dependency already use, not per-instance errors.
        self.duplicate_errors.extend(self._check_indexed_field_types())

    def _assign_flags_bits(self, node, entries):
        """Computes each entry's real bit-claim value and populates
        self.flags_values. Follows the spec's auto-assignment rule
        exactly: "omitting the value entirely auto-assigns the next
        unclaimed bit, in declaration order" -- unclaimed DOMAIN-WIDE,
        not just by entries seen so far, so every explicit claim
        (wherever it appears in the file) is collected FIRST, before any
        auto-assignment happens.

        This two-pass structure is what makes explicit-vs-auto and
        auto-vs-auto collisions structurally impossible, not just
        individually guarded against: auto-assignment always skips every
        explicit claim domain-wide, and its own cursor only ever moves
        forward, so it can never repeat a bit either explicitly claimed
        or already handed to an earlier auto entry. The one collision
        that CAN actually occur is explicit-vs-explicit: two members
        both writing '= bN' for the same N, a real conflict where
        neither yields.

        On any single entry's own claim failing (out-of-width position,
        or losing an explicit-vs-explicit collision), that entry is
        skipped entirely -- no value registered for it at all, same
        "first wins, duplicate/invalid entries just don't make it into
        the table" precedent this file's own identifier-entry handling
        already established. A later reference to a skipped member
        surfaces its own secondary "no such member" error at resolution
        time, layered on top of the phase-4 error already reported here
        -- not a new failure mode, the exact shape identifier's
        duplicate-key handling already has."""
        errors = []
        bits = _INDEXED_WIDTH_BITS[node.width]

        # Pass 1: every explicit claim, domain-wide, before any auto
        # assignment happens.
        claimed = {}  # bit position (int) -> the entry that holds it
        for entry in entries:
            if entry.kind != "bit":
                continue
            if entry.explicit_bit >= bits:
                errors.append(CompileError(
                    phase=4,
                    check="flags_bit_exceeds_width",
                    line=entry.line,
                    message=f"flags member '{entry.name}' claims bit "
                            f"{entry.explicit_bit} ('= b{entry.explicit_bit}'), "
                            f"but domain '{node.name}' is declared "
                            f"'{node.width}' ({bits} bits, positions "
                            f"0..{bits - 1}) -- this bit position doesn't "
                            "exist at this width",
                ))
                continue
            if entry.explicit_bit in claimed:
                other = claimed[entry.explicit_bit]
                errors.append(CompileError(
                    phase=4,
                    check="flags_bit_collision",
                    line=entry.line,
                    message=f"flags member '{entry.name}' claims bit "
                            f"{entry.explicit_bit} ('= b{entry.explicit_bit}'), "
                            f"but '{other.name}' (line {other.line}) already "
                            f"claims the same bit in domain '{node.name}' -- "
                            "each bit position must be claimed exactly once",
                ))
                continue
            claimed[entry.explicit_bit] = entry
            self.flags_values[(node.name, entry.name)] = 1 << entry.explicit_bit
            self.flags_bits[(node.name, entry.name)] = entry.explicit_bit

        # Pass 2: auto-assign everything else, in declaration order,
        # around every explicit claim from pass 1 -- regardless of
        # whether that claim's own line came before or after this entry.
        cursor = 0
        for entry in entries:
            if entry.kind == "number":
                self.flags_values[(node.name, entry.name)] = 0  # sentinel, claims no bit
                continue
            if entry.kind == "bit":
                continue  # already handled in pass 1 (or skipped as invalid)

            while cursor in claimed:
                cursor += 1
            if cursor >= bits:
                errors.append(CompileError(
                    phase=4,
                    check="flags_width_overflow",
                    line=entry.line,
                    message=f"flags domain '{node.name}' declares width "
                            f"'{node.width}' ({bits} bits), but member "
                            f"'{entry.name}' has no unclaimed bit left to "
                            "auto-assign -- the domain's real bit-flag "
                            "members exceed what this width can address",
                ))
                cursor += 1
                continue
            claimed[cursor] = entry
            self.flags_values[(node.name, entry.name)] = 1 << cursor
            self.flags_bits[(node.name, entry.name)] = cursor
            cursor += 1

        return errors

    def _check_indexed_field_types(self):
        """Two static checks (§8.3), over every field of every define:
        - '@Domain' used, but Domain declared no indexed width (or isn't
          a known identifier domain at all).
        - '@' used on anything other than an identifier-domain type."""
        errors = []
        for type_name, d in self.defines.items():
            for f in d.fields:
                t = f.type_tokens.strip()
                if not t.startswith("@"):
                    continue
                target = t[1:].strip()
                if target not in self.identifiers:
                    if target in self.defines:
                        reason = f"'{target}' is a struct type (define), not an identifier domain"
                    else:
                        reason = f"'{target}' is not a known identifier domain"
                    errors.append(CompileError(
                        phase=4,
                        check="indexed_wrong_type",
                        line=f.line,
                        message=f"field '{f.name}' in '{type_name}' uses '@{target}', but "
                                f"'@' is only legal prefixing an identifier-domain type -- "
                                f"{reason}",
                    ))
                    continue
                if target not in self.identifier_widths:
                    errors.append(CompileError(
                        phase=4,
                        check="indexed_no_width",
                        line=f.line,
                        message=f"field '{f.name}' in '{type_name}' uses '@{target}', but "
                                f"domain '{target}' declared no indexed width -- '@' "
                                f"requires the domain to opt into an indexed form at its "
                                f"own declaration (e.g. 'identifier {target} u8'), §8.3",
                    ))
        return errors

    def _instance_dependencies(self, decl: InstanceDecl):
        """Every instance name this InstanceDecl directly depends on:
        the top-level `= Source` copy, plus every nested `field =
        SourceInstance` full-replace reference at any depth (walking
        recursively through struct-typed fields, mirroring the same
        recursive structure Nested Field Semantics itself uses)."""
        deps = set()
        if decl.source_name is not None:
            deps.add(decl.source_name)

        def walk(stmts, scope_type):
            for stmt in stmts:
                if isinstance(stmt, AssignStmt):
                    category, field_type = self.field_category(scope_type, stmt.field_name)
                    if category == "struct":
                        rhs = stmt.rhs.strip()
                        if rhs in self.instances:
                            deps.add(rhs)
                        if stmt.children:
                            walk(stmt.children, field_type)
                elif isinstance(stmt, BareFieldStmt):
                    category, field_type = self.field_category(scope_type, stmt.field_name)
                    if category == "struct":
                        walk(stmt.children, field_type)

        walk(decl.body, decl.type_name)
        return deps

    def _detect_circular_dependencies(self):
        """Ordinary cycle detection (DFS, white/gray/black) over the
        instance dependency graph. Returns dict: instance_name ->
        CompileError, for every instance that's part of at least one
        detected cycle -- every participant gets the same message naming
        the full cycle, since a cycle has no single well-defined "root
        cause" instance the way a simple linear dependency failure does."""
        graph = {name: self._instance_dependencies(decl)
                 for name, decl in self.instances.items()}

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {name: WHITE for name in graph}
        path = []
        errors = {}

        def record_cycle(cycle):
            arrow = " -> ".join(cycle)
            message = (
                f"circular instance-copy reference: {arrow} -- every "
                "instance in this cycle depends (directly or through a "
                "nested full-replace) on another instance in the same "
                "cycle, so none of them can ever be resolved"
            )
            for name in cycle[:-1]:  # last entry repeats the first, don't double up
                if name not in errors:  # first cycle found involving this instance wins
                    errors[name] = CompileError(
                        phase=4, check="circular_dependency",
                        line=self.instances[name].line, message=message,
                    )

        def dfs(node):
            color[node] = GRAY
            path.append(node)
            for neighbor in graph.get(node, ()):
                if neighbor not in graph:
                    continue  # unknown-instance reference is a separate error, not a cycle
                if color[neighbor] == GRAY:
                    idx = path.index(neighbor)
                    record_cycle(path[idx:] + [neighbor])
                elif color[neighbor] == WHITE:
                    dfs(neighbor)
            path.pop()
            color[node] = BLACK

        for name in graph:
            if color[name] == WHITE:
                dfs(name)

        return errors

    def _check_id_collision(self, id_hex: str, identity_key, qualified_name: str, line: int):
        """Shared collision check across every logical/stable ID (see
        self._id_table). `identity_key` (e.g. (domain, key)) identifies
        WHICH entry this is, kept separate from `qualified_name` (the
        display string, matching the actual hashed input) -- these two
        used to be conflated by using qualified_name as the identity
        check too, which broke the moment qualified_name switched from a
        domain+key display format to the domain+description format the
        spec requires: two entries that genuinely collide (same domain,
        same description text, different keys) now produce IDENTICAL
        qualified-name strings, which is exactly the case that must
        trigger the error, not be mistaken for "the same entry seen
        twice." A hard compile error naming both colliding qualified
        names and the shared hash value -- astronomically unlikely with
        real, distinct project content given FNV-1a-64's space, so this
        is defensive infrastructure, not something real content is
        expected to trigger."""
        existing = self._id_table.get(id_hex)
        if existing is not None and existing[0] != identity_key:
            self.duplicate_errors.append(CompileError(
                phase=4,
                check="id_collision",
                line=line,
                message=f"'{qualified_name}' and '{existing[1]}' both hash to "
                        f"the same ID ({id_hex}) -- this is a hard compile "
                        "error regardless of how astronomically unlikely a "
                        "real collision is; every logical/stable ID must be "
                        "unique across the shared 64-bit space",
            ))
            return
        self._id_table[id_hex] = (identity_key, qualified_name)

    def field_type(self, struct_type_name: str, field_name: str):
        """Returns the declared type_tokens string for a field, or None
        if the struct type or field isn't known."""
        d = self.defines.get(struct_type_name)
        if d is None:
            return None
        for f in d.fields:
            if f.name == field_name:
                return f.type_tokens
        return None

    def field_category(self, struct_type_name: str, field_name: str):
        """Returns (category, type_name) where category is 'struct',
        'identifier', 'flags', or 'scalar' -- or (None, None) if unknown.

        §8.3: a valid '@Domain' (domain exists and is a real identifier
        domain) is treated EXACTLY like plain 'Domain' here -- resolution
        (phases 6-8) needs no semantic change at all; '@' only matters
        once export happens (see export_cpp.py). An invalid '@X' (X isn't
        a real identifier domain, flags domain included -- flags never
        had a hash-vs-index duality to opt into, so '@FlagsDomain' is
        just as invalid as '@AnyStructType') deliberately does NOT get
        special-cased here -- it falls through to 'scalar' with the full
        '@X' text as type_name, an inert no-op, since that misuse is
        already reported as a hard compile-time error by
        Registry._check_indexed_field_types regardless of what happens
        here."""
        t = self.field_type(struct_type_name, field_name)
        if t is None:
            return None, None
        t = t.strip()
        if t.startswith("@"):
            domain = t[1:].strip()
            if domain in self.identifiers:
                return "identifier", domain
            return "scalar", t
        if t in self.defines:
            return "struct", t
        if t in self.identifiers:
            return "identifier", t
        if t in self.flags:
            return "flags", t
        return "scalar", t

    def is_struct_type(self, type_name: str) -> bool:
        return type_name in self.defines

    def get_logical_id(self, domain: str, key: str):
        return self.logical_ids.get((domain, key))

    def get_instance_id(self, type_name: str, instance_name: str):
        return self.instance_ids.get((type_name, instance_name))

    def get_identifier_width(self, domain: str):
        return self.identifier_widths.get(domain)

    def get_flags_width(self, domain: str):
        return self.flags_widths.get(domain)

    def get_flags_value(self, domain: str, member: str):
        return self.flags_values.get((domain, member))

    def get_flags_bit(self, domain: str, member: str):
        """The claimed bit index (int), or None for the zero/none
        sentinel (which claims no bit at all) or an unregistered member."""
        return self.flags_bits.get((domain, member))
