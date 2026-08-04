"""
Phase 5: Validate.

Two independently-attributable static checks, run in sequence, purely
against the AST + registry -- no instance resolution needed:

  1. field_shape: every field referenced in a statement exists on its
     declared enclosing struct type; bare-field (modify-only) and
     assign-with-children are only valid on struct-typed fields.
  2. domain_typing: for scalar fields typed as an identifier domain,
     statically check the RHS shape where it's unambiguous (a bare
     literal can never satisfy an identifier-typed field; a dotted
     Domain.member reference must name the right domain and a real
     member). Dynamic RHS shapes (field references, expressions) are
     deliberately NOT rejected here -- they're deferred to phase 6's
     runtime check, since a cross-field reference's ultimate type isn't
     statically obvious without evaluation.

Numeric coercion/range enforcement (spec §5) deliberately does NOT live
here -- it needs an evaluated value (you can't know if an expression has
a fractional remainder without computing it), so it's implemented at the
point of storage in phase 6/7 instead. See resolve.py.

Errors from both checks share one CompileError with check names
"field_shape" / "domain_typing", both phase 5. Only the FIRST error per
instance is recorded here (collect-and-report happens at the resolver
level across instances, not multiple errors within one instance).
"""

import re

from ast_nodes import AssignStmt, OpStmt, BareFieldStmt, RawStmt
from errors import CompileError

_DOMAIN_REF_RE = re.compile(r"^([A-Za-z_]\w*)\.([A-Za-z_]\w*)$")
_BARE_NAME_RE = re.compile(r"^[A-Za-z_]\w*$")


def run_phase5(reg):
    """Returns dict: instance_name -> CompileError (its phase-5 failure),
    for every instance where a phase-5 check found a problem. Instances
    not present in the returned dict passed phase 5 cleanly."""
    errors = {}
    for name, decl in reg.instances.items():
        err = _check_field_shape(decl.body, decl.type_name, reg)
        if err is None:
            err = _check_domain_typing(decl.body, decl.type_name, reg)
        if err is not None:
            errors[name] = err
    return errors


# ---- check 1: field_shape ----

def _check_field_shape(stmts, scope_type, reg):
    return _walk_statements(stmts, scope_type, reg)


def _walk_statements(stmts, scope_type, reg):
    for stmt in stmts:
        if isinstance(stmt, RawStmt):
            return CompileError(
                phase=5, check="field_shape", line=stmt.line,
                message=f"unrecognized statement shape: {stmt.text!r}")

        if isinstance(stmt, BareFieldStmt):
            err = _check_bare(stmt, scope_type, reg)
            if err is not None:
                return err
            continue

        if isinstance(stmt, AssignStmt):
            category, field_type = reg.field_category(scope_type, stmt.field_name)
            if category is None:
                return CompileError(
                    phase=5, check="field_shape", line=stmt.line,
                    message=f"'{stmt.field_name}' is not a field of '{scope_type}'")
            if category == "struct":
                if stmt.children:
                    nested_scope_type = field_type
                    return _walk_statements(stmt.children, nested_scope_type, reg)
                continue
            if stmt.children:
                return CompileError(
                    phase=5, check="field_shape", line=stmt.line,
                    message=f"scalar field '{stmt.field_name}' has an indented "
                            "block under a plain assign -- only struct-typed "
                            "fields can have children here")
            continue

        if isinstance(stmt, OpStmt):
            category, _ = reg.field_category(scope_type, stmt.field_name)
            if category is None:
                return CompileError(
                    phase=5, check="field_shape", line=stmt.line,
                    message=f"'{stmt.field_name}' is not a field of '{scope_type}'")
            if category != "scalar":
                return CompileError(
                    phase=5, check="field_shape", line=stmt.line,
                    message=f"operator statement on '{stmt.field_name}' (a "
                            f"{category}-typed field) -- arithmetic operators "
                            "only apply to plain scalar fields")
            continue

    return None


def _check_bare(stmt: BareFieldStmt, scope_type, reg):
    category, type_name = reg.field_category(scope_type, stmt.field_name)
    if category is None:
        return CompileError(
            phase=5, check="field_shape", line=stmt.line,
            message=f"'{stmt.field_name}' is not a field of '{scope_type}'")
    if category != "struct":
        return CompileError(
            phase=5, check="field_shape", line=stmt.line,
            message=f"bare field '{stmt.field_name}' (modify-only form) used "
                    f"on a scalar field -- only struct-typed fields have a "
                    "scope to enter")
    return _walk_statements(stmt.children, type_name, reg)


# ---- check 2: domain_typing ----

def _check_domain_typing(stmts, scope_type, reg):
    return _walk_domain_typing(stmts, scope_type, reg)


def _walk_domain_typing(stmts, scope_type, reg):
    for stmt in stmts:
        if isinstance(stmt, AssignStmt):
            category, domain_name = reg.field_category(scope_type, stmt.field_name)
            if category == "identifier":
                err = _check_domain_assignment(
                    stmt.field_name, domain_name, stmt.rhs, stmt.line, scope_type, reg)
                if err is not None:
                    return err
            elif category == "struct" and stmt.children:
                err = _walk_domain_typing(stmt.children, domain_name, reg)
                if err is not None:
                    return err

        elif isinstance(stmt, BareFieldStmt):
            category, type_name = reg.field_category(scope_type, stmt.field_name)
            if category == "struct":
                err = _walk_domain_typing(stmt.children, type_name, reg)
                if err is not None:
                    return err

    return None


def _check_domain_assignment(field_name, domain_name, rhs, line, scope_type, reg):
    rhs = rhs.strip()

    m = _DOMAIN_REF_RE.match(rhs)
    if m:
        d, k = m.group(1), m.group(2)
        if d != domain_name:
            return _domain_typing_error(
                f"'{field_name}' is typed as identifier domain "
                f"'{domain_name}', but was assigned '{d}.{k}' -- a reference "
                f"to domain '{d}', not '{domain_name}' -- a bare literal or "
                "wrong-domain reference can never satisfy an "
                "identifier-typed field", line)
        if reg.get_logical_id(d, k) is None:
            return _domain_typing_error(
                f"'{d}.{k}' is not a known member of domain '{d}'", line)
        return None

    if _BARE_NAME_RE.match(rhs):
        ref_category, ref_type = reg.field_category(scope_type, rhs)
        if ref_category == "identifier" and ref_type == domain_name:
            return None  # same-domain field-name reference -- structurally valid
        # Otherwise it's either a scalar/struct field reference (invalid,
        # but let phase 6 report it in evaluation context) or an unknown
        # name -- ambiguous enough to defer rather than guess.
        return None

    return _domain_typing_error(
        f"'{field_name}' is typed as identifier domain '{domain_name}', but "
        f"was assigned {rhs!r} -- a bare literal or wrong-domain reference "
        "can never satisfy an identifier-typed field", line)


def _domain_typing_error(message, line):
    return CompileError(phase=5, check="domain_typing", line=line, message=message)
