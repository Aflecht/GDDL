# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Identifiers manifest export (opt-in, --emit-ids-manifest).

Writes {output_stem}.gddlids.json: every identifier and flags domain
declared in this compile unit, unconditionally -- independent of
--emit-all-domains (which only controls target-language code
generation for referenced domains, a separate concern from this
manifest's actual purpose: letting a separately-compiled consumer,
chiefly a future scripting-language compiler, resolve a `Domain.key`
text reference into the same logical ID or bit position this compile
unit itself resolved it to, for a domain it may not have the GDDL
source for at all -- see SPEC.md section 20).

Shared across all five exporters (§19's own precedent for check_and_report
in validate.py: one function, called the same way from every exporter's
_cli(), not five separate implementations of the same logic).

`logical_id` is written as the same 16-hex-digit string
registry.logical_id() already produces, not a raw JSON number: a full
64-bit value silently loses precision under any JSON parser that
treats numbers as IEEE-754 doubles (JavaScript being the common case),
and a string sidesteps that entirely regardless of what ever reads
this file. `bit` stays a plain JSON integer -- it only ranges 0..63
even at the widest flags width, nowhere near that danger zone.

Flags domain members carry no description text at all: flags syntax
(ast_nodes.FlagsEntry) never had a slot for one, unlike identifier
entries, which require `key = "description"`. Only `key` and `bit`
are written for flags members; inventing a fake description would
violate this project's own "nothing is implicit" principle (§2).

**`instances` (§20.3.1)**: same idea as `domains`, but for named
data-record instances instead of identifier/flags domain members --
lets a script resolve `Type::instance_name` (§6.8's `Type::Name`
qualified-name convention) to the same stable ID
(`reg.get_instance_id`) the C++/bindings-manifest exporters already
compute, for a define this compile unit may not even export to a
struct-bearing target at all. Reuses `_topo_sort_defines`/
`export_instances_for_type` from export_cpp.py verbatim -- the exact
same "one source of truth" reasoning the module docstring already
gives for not reinventing domain-listing a second time (and the same
functions export_bindings.py's own `types[].instances` already reuses
for .gddlbindings.json, so a name's stable ID is computed by the same
code path in both manifests, never two).

Building the `instances` section requires `resolver` (instance
resolution is a per-compile-unit runtime result, not something `reg`
holds by itself), so it's opt-in via the `resolver` parameter: omitted
(`None`, the default) skips it entirely, preserving the domains-only
shape wherever a caller has no resolver at hand -- specifically
export_bindings.py's own `build_ids_manifest(reg)` call, which already
carries its own per-type instances list nested under `types[]`, and
would otherwise end up with the exact same instance data serialized
twice, in two different shapes, in one `.gddlbindings.json` file.
Every CLI call site below does have a resolver in scope already
(instance resolution already happened before the manifest flag is
even checked), so every real `--emit-ids-manifest` invocation passes
it and gets the `instances` section.
"""

import json

from .export_cpp import _topo_sort_defines, export_instances_for_type
from .registry import Registry


def build_ids_manifest(reg: Registry, resolver=None) -> dict:
    """Returns the manifest as a plain dict, ready for json.dump. Every
    identifier and flags domain the compile unit declared, unconditionally
    -- see module docstring for why this doesn't follow --emit-all-domains.
    Duplicate/invalid entries (never registered, phase 4) are silently
    skipped -- the same "first wins, invalid entries just don't make it
    into the table" precedent Registry's own internal tables already
    follow.

    `resolver`: optional. When given, also builds the `instances`
    section (every `define`, unconditionally, each with every one of
    its non-delete resolved instances and that instance's stable ID --
    see module docstring). When omitted, the returned dict has no
    `instances` key at all, matching this function's original,
    domains-only shape."""
    domains = []

    for name, block in reg.identifiers.items():
        members = []
        for entry in block.entries:
            lid = reg.get_logical_id(name, entry.key)
            if lid is None:
                continue
            members.append({
                "key": entry.key,
                "logical_id": lid,
                "description": entry.description,
            })
        domains.append({"name": name, "kind": "identifier", "members": members})

    for name, block in reg.flags.items():
        members = []
        for entry in block.entries:
            value = reg.get_flags_value(name, entry.name)
            if value is None:
                continue
            bit = reg.get_flags_bit(name, entry.name)
            member = {"key": entry.name}
            if bit is not None:
                member["bit"] = bit
            members.append(member)
        domains.append({
            "name": name,
            "kind": "flags",
            "width": reg.get_flags_width(name),
            "members": members,
        })

    manifest = {"domains": domains}

    if resolver is not None:
        instances = []
        for type_name in _topo_sort_defines(reg):
            members = [
                {"name": name, "stable_id": reg.get_instance_id(type_name, name)}
                for name, _value in export_instances_for_type(type_name, reg, resolver)
            ]
            instances.append({"name": type_name, "members": members})
        manifest["instances"] = instances

    return manifest


def write_ids_manifest(reg: Registry, output_stem: str, resolver=None) -> str:
    """Writes {output_stem}.gddlids.json. Returns the path written, for
    the caller's own confirmation message (matching how every other
    exporter CLI reports what it wrote).

    `resolver`: optional, forwarded to build_ids_manifest -- see that
    function's docstring."""
    manifest = build_ids_manifest(reg, resolver)
    path = f"{output_stem}.gddlids.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path
