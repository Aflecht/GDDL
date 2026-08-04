"""
Phase 8: final validation.

Every exported (non-delete) instance must have every field initialized
by the time it's exported. `delete`-marked instances are exempt.

This phase walks the ACTUAL fully-resolved StructValue tree phase 6
produced and checks the real, current state of every field, recursively
into every nested struct, at any depth -- the only way to be correct
given full-replace-then-modify and modify-only can each leave a
different subset of a struct's fields initialized depending on
execution order.

Relationship to phase 6's collect-and-report policy: an instance that
never made it into resolver.cache (errored directly, or blocked on a
dependency that errored) has no resolved tree to walk, so phase 8 has
nothing to check for it -- already reported once by phase 6.
"""

from resolve import StructValue, UNINIT, Resolver


def _find_uninitialized(value: StructValue, path_prefix: str = ""):
    missing = []
    for field_name, field_val in value.fields.items():
        path = f"{path_prefix}{field_name}"
        if field_val is UNINIT:
            missing.append(path)
        elif isinstance(field_val, StructValue):
            missing.extend(_find_uninitialized(field_val, path_prefix=f"{path}."))
    return missing


def final_validate(resolver: Resolver):
    results = {}
    for name, value in resolver.cache.items():
        decl = resolver.reg.instances[name]
        if decl.is_delete:
            continue
        missing = _find_uninitialized(value)
        results[name] = missing
    return results


def compile_report(resolver: Resolver):
    """Ties phase 4/5/6 + phase 8 together into one per-instance status,
    in declaration order. Status is one of:
      'ok' / 'delete' / 'error' (CompileError as detail) /
      'blocked' (root name as detail) / 'incomplete' (missing-fields list)
    """
    completeness = final_validate(resolver)
    report = {}
    for name, decl in resolver.reg.instances.items():
        if name in resolver.errors:
            report[name] = ("error", resolver.errors[name])
        elif name in resolver.blocked:
            report[name] = ("blocked", resolver.blocked[name])
        elif decl.is_delete:
            report[name] = ("delete", None)
        else:
            missing = completeness.get(name, [])
            if missing:
                report[name] = ("incomplete", missing)
            else:
                report[name] = ("ok", None)
    return report


def print_report(resolver: Resolver):
    if resolver.reg.duplicate_errors:
        for err in resolver.reg.duplicate_errors:
            print(f"[phase {err.phase}, {err.check}] {err}")
    if resolver.warnings:
        for w in resolver.warnings:
            print(f"WARNING [phase {w.phase}, {w.check}] - {w}")
    report = compile_report(resolver)
    for name, (status, detail) in report.items():
        if status == "ok":
            print(f"{name}: OK (export-ready)")
        elif status == "delete":
            print(f"{name}: delete template (not exported, completeness exempt)")
        elif status == "error":
            print(f"{name}: ERROR [phase {detail.phase}, {detail.check}] - {detail}")
        elif status == "blocked":
            print(f"{name}: BLOCKED - depends on '{detail}'")
        elif status == "incomplete":
            fields = ", ".join(detail)
            print(f"{name}: INCOMPLETE [phase 8] - export-blocking, uninitialized field(s): {fields}")
