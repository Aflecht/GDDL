# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
Scripting-VM bindings manifest export (opt-in, --emit-bindings-manifest,
C++ exporter only -- SPEC.md section 14.6).

GDDL itself never generates bindings for any specific embedded scripting
language: it has no way to know a given project's calling conventions,
type marshalling, or embedding API. Instead this writes
{output_stem}.gddlbindings.json -- a deterministic, machine-readable
description of every `define`'s declared fields, every instance's name
and stable ID, and every identifier/flags domain's members, generated
from the exact same compiled representation (`reg`/`resolver`) the C++
header itself is built from, so the two can never silently drift apart.
A separate, project-specific tool (understanding the real scripting
language's embedding conventions) reads this file and generates the
actual binding glue: registering types with the VM, generating
per-field getter thunks that dereference the real C++ memory (valid
for an in-process VM sharing the same address space -- what this was
designed against), and exposing each type's registry for script-side
lookup and iteration.

**C++ only, and AoS-family layouts only (`aos`/`aos-linear`), never
`soa`.** §14.6's whole premise is generating glue that dereferences a
real C++ struct's fields directly (`instance->field`) -- that struct
simply doesn't exist in SoA output (§13.1 fully flattens every field
into its own parallel array instead), so there is nothing for
"per-field getter thunk" to mean there. `aos` and `aos-linear` share
byte-identical struct/field layout (they only differ in how instances
are stored and looked up, never in a struct's own field list), so this
manifest's content is the same for either -- no layout parameter needed
here at all, only a rejection at the CLI when combined with `soa`.

**Domain content is reused, not reimplemented.** The exact same
`export_ids.build_ids_manifest(reg)` domain list this compile unit's
`--emit-ids-manifest` output would carry is embedded here verbatim
(both describe "every domain this compile unit declared," the same
scope the C++ header's own enum/namespace emission already uses
unconditionally, confirmed directly against generate_header/
generate_split -- see this module's own gather_bindings_manifest
docstring). Reusing the one function rather than a second,
independently-written domain walk is the same "one hash function, one
source of truth" discipline SPEC.md section 17.4 argues for.

Field type descriptions use a small structural vocabulary (`kind`:
`scalar`/`string`/`identifier`/`flags`/`struct`/`array`) rather than
GDDL's raw type-token text, mirroring registry.field_category()'s own
classification exactly (see _describe_type's docstring for the one
difference: this recurses into an array's element type, which
field_category() itself has no caller that needs). A `struct`-kind
field names another entry in this manifest's own `types` list rather
than inlining that type's fields again -- exactly how the generated
C++ struct itself refers to the nested type by name, and how §14.6's
per-field getter thunks would need to recurse too.
"""

import json

from .export_cpp import _string_n, export_instances_for_type, _topo_sort_defines
from .export_ids import build_ids_manifest
from .registry import Registry, _try_parse_array_type


def _describe_type(type_tokens: str, reg: Registry) -> dict:
    """Structural description of one field's (or array element's) type.
    Classification mirrors Registry.field_category()'s own category
    rules exactly (struct/identifier/flags/array/scalar, `@Domain`
    checked before a bare domain name), but returns a JSON-ready dict
    keyed by `kind` instead of a (category, type_name) tuple, and
    additionally recurses into an array's element type -- current
    arrays scope (SPEC.md section 21.1) only allows scalar/string N
    elements, so this recursion never actually reaches identifier/
    flags/struct today, but is written generally rather than assuming
    that stays true forever."""
    t = type_tokens.strip()
    n = _string_n(t)
    if n is not None:
        return {"kind": "string", "width": n}
    array_info = _try_parse_array_type(t)
    if array_info is not None:
        return {
            "kind": "array",
            "dims": list(array_info.dims),
            "element": _describe_type(array_info.element_type, reg),
        }
    indexed = t.startswith("@")
    bare = t[1:].strip() if indexed else t
    if bare in reg.defines:
        return {"kind": "struct", "type": bare}
    if bare in reg.identifiers:
        return {"kind": "identifier", "domain": bare, "indexed": indexed}
    if bare in reg.flags:
        return {"kind": "flags", "domain": bare}
    return {"kind": "scalar", "type": bare}


def build_bindings_manifest(reg: Registry, resolver) -> dict:
    """Returns the manifest as a plain dict, ready for json.dump.

    `types`: every `define` in `reg`, dependency order (the exact same
    `_topo_sort_defines(reg)` call, no `roots=`, that generate_header/
    generate_split themselves use for AoS struct emission -- C++ export
    has no per-request type subset at all, everything in the compile
    unit is always exported, §14.6's manifest matches that unconditional
    scope rather than inventing a narrower one). Each type's `fields`
    list is the DECLARED field list (`d.fields`), not flattened through
    composition (§13.1's flattening is a target-specific export
    concern for the assembly/binary targets; a real C++ struct keeps
    composition as real nested structs, and this manifest describes
    exactly that shape so generated getter thunks can write ordinary
    `instance->stats.hp`-style C++ access, not manual byte offsets).
    Each type's `instances` list is every fully-resolved, non-delete
    instance (export_instances_for_type -- the same filter the C++
    exporter itself applies), with its precomputed stable ID
    (reg.get_instance_id, §6.8's qualified-name hash).

    `domains`: reused verbatim from build_ids_manifest(reg) -- see
    module docstring."""
    manifest = build_ids_manifest(reg)

    types = []
    for type_name in _topo_sort_defines(reg):
        d = reg.defines[type_name]
        fields = [
            {"name": f.name, **_describe_type(f.type_tokens, reg)}
            for f in d.fields
        ]
        instances = [
            {"name": name, "stable_id": reg.get_instance_id(type_name, name)}
            for name, _value in export_instances_for_type(type_name, reg, resolver)
        ]
        types.append({"name": type_name, "fields": fields, "instances": instances})

    manifest["types"] = types
    return manifest


def write_bindings_manifest(reg: Registry, resolver, output_stem: str) -> str:
    """Writes {output_stem}.gddlbindings.json. Returns the path written,
    for the caller's own confirmation message (matching every other
    exporter CLI's own report-what-was-written convention)."""
    manifest = build_bindings_manifest(reg, resolver)
    path = f"{output_stem}.gddlbindings.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")
    return path
