# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

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

from .resolve import StructValue, UNINIT, Resolver
import sys


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


def print_report(resolver: Resolver, verbose: bool = False):
    if resolver.reg.duplicate_errors:
        for err in resolver.reg.duplicate_errors:
            if verbose:
                print(f"[phase {err.phase}, {err.check}] {err}")
            else:
                print(f"{err}")
    if resolver.warnings:
        for w in resolver.warnings:
            if verbose:
                print(f"WARNING [phase {w.phase}, {w.check}] - {w}")
            else:
                print(f"WARNING - {w}")
    report = compile_report(resolver)
    for name, (status, detail) in report.items():
        if status == "ok":
            print(f"{name}: OK (export-ready)")
        elif status == "delete":
            print(f"{name}: delete template (not exported, completeness exempt)")
        elif status == "error":
            if verbose:
                print(f"{name}: ERROR [phase {detail.phase}, {detail.check}] - {detail}")
            else:
                print(f"{name}: ERROR - {detail}")
        elif status == "blocked":
            print(f"{name}: BLOCKED - depends on '{detail}'")
        elif status == "incomplete":
            fields = ", ".join(detail)
            if verbose:
                print(f"{name}: INCOMPLETE [phase 8] - export-blocking, uninitialized field(s): {fields}")
            else:
                print(f"{name}: INCOMPLETE - export-blocking, uninitialized field(s): {fields}")


def check_and_report(resolver: Resolver, verbose: bool = False) -> bool:
    """The actual build-blocking gate every exporter CLI must call
    after compile_multi() returns a resolver and before any rendering
    begins. Unlike print_report (which unconditionally prints a line
    per instance, 'OK' included -- meant for an explicit report/debug
    view), this prints ONLY genuine problems to stderr, using the same
    message formats print_report already established, and returns
    False if the build should be blocked.

    `verbose` controls whether each message is tagged with its
    internal [phase N, check_name] -- useful for whoever's working on
    the compiler itself (or an AI coding assistant doing so), genuine
    noise for someone just using the language. Off by default; every
    exporter CLI exposes it as --verbose-errors.

    Exists because phases 4-8 were already computing real, precise
    errors (resolver.errors, resolver.blocked, resolver.reg.duplicate_errors,
    and this module's own phase-8 incompleteness check) that nothing
    was ever calling -- an instance with a genuine, correctly-detected
    error simply never made it into resolver.cache, so it silently
    vanished from rendered output instead of failing the build. This
    closes that gap; every exporter CLI calls this once, right after
    obtaining a resolver, and exits nonzero without writing any output
    if it returns False."""
    ok = True
    if resolver.reg.duplicate_errors:
        for err in resolver.reg.duplicate_errors:
            if verbose:
                print(f"[phase {err.phase}, {err.check}] {err}", file=sys.stderr)
            else:
                print(f"{err}", file=sys.stderr)
            ok = False
    if resolver.warnings:
        for w in resolver.warnings:
            if verbose:
                print(f"WARNING [phase {w.phase}, {w.check}] - {w}", file=sys.stderr)
            else:
                print(f"WARNING - {w}", file=sys.stderr)
    report = compile_report(resolver)
    for name, (status, detail) in report.items():
        if status == "error":
            if verbose:
                print(f"{name}: ERROR [phase {detail.phase}, {detail.check}] - {detail}", file=sys.stderr)
            else:
                print(f"{name}: ERROR - {detail}", file=sys.stderr)
            ok = False
        elif status == "blocked":
            print(f"{name}: BLOCKED - depends on '{detail}'", file=sys.stderr)
            ok = False
        elif status == "incomplete":
            fields = ", ".join(detail)
            if verbose:
                print(f"{name}: INCOMPLETE [phase 8] - export-blocking, uninitialized field(s): {fields}", file=sys.stderr)
            else:
                print(f"{name}: INCOMPLETE - export-blocking, uninitialized field(s): {fields}", file=sys.stderr)
            ok = False
    return ok
