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
"""

import json

from .registry import Registry


def build_ids_manifest(reg: Registry) -> dict:
    """Returns the manifest as a plain dict, ready for json.dump. Every
    identifier and flags domain the compile unit declared, unconditionally
    -- see module docstring for why this doesn't follow --emit-all-domains.
    Duplicate/invalid entries (never registered, phase 4) are silently
    skipped -- the same "first wins, invalid entries just don't make it
    into the table" precedent Registry's own internal tables already
    follow."""
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

    return {"domains": domains}


def write_ids_manifest(reg: Registry, output_stem: str) -> str:
    """Writes {output_stem}.gddlids.json. Returns the path written, for
    the caller's own confirmation message (matching how every other
    exporter CLI reports what it wrote)."""
    manifest = build_ids_manifest(reg)
    path = f"{output_stem}.gddlids.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path
