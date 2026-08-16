# Part of GDDL, licensed under the GDDL License v1.0.
# See LICENSE at the project root for full terms.

"""
§18 Multi-File Compilation -- shared across every exporter, not
per-exporter logic. This is entirely a front-end input-handling
concern: nothing in parser.py, resolve.py, or validate.py is modified
to make this work (confirmed directly before writing any of this --
see the empirical forward-reference test referenced in HANDOFF.md).
The one exception is a small, purely-additive change to
parser.GDDLParseError (storing the raw message body alongside the
already-existing baked "line N: ..." string), needed because that
class freezes its string representation at construction time rather
than computing it fresh like CompileError/CompileWarning do -- verified
byte-identical for every existing caller before this module was built
on top of it.

Three responsibilities, in order:
  1. resolve_inputs() -- turn a list of CLI arguments (literal paths,
     glob patterns, ** for recursion) into a concrete, ordered list of
     real files on disk. No assumed .gddl extension anywhere (§18.3).
  2. combine_sources() -- concatenate those files into one in-memory
     source text, recording each file's name and starting line.
  3. compile_multi() -- run the EXISTING, unmodified pipeline against
     the combined text, then remap every line number in the result
     back to (source file, original line) using the recorded spans.
     This is the only new logic that touches the pipeline's OUTPUT;
     nothing upstream of it changes.

Combination order (§18.2), exactly as specified: files given directly
on the command line, in the order given, THEN files discovered via
glob patterns, in sorted path order. Two things not explicitly pinned
down by the spec text, decided here and documented rather than left
implicit:
  - Glob matches across multiple patterns are deduplicated (first
    sorted occurrence kept) -- compiling the same file twice would
    guarantee every top-level symbol in it collides with itself,
    clearly not the intent of overlapping patterns.
  - A glob match that coincides with a literal-argument file is
    dropped from the glob group (the literal's position wins) -- a
    file named both explicitly and via a pattern should appear once,
    where the user explicitly placed it.
"""

import glob
import os


class CombineError(Exception):
    """Input-resolution problems (§18.5): zero-match inputs. Raised
    BEFORE any parsing starts -- distinct from GDDLParseError
    (phase 2/3) and CompileError (phase 4+), which both presuppose a
    combined source already exists."""
    pass


class FileSpan:
    """One resolved input file's position within the combined text.
    start_line/end_line are both 1-based and inclusive, matching the
    line-numbering convention every existing error/warning already
    uses (confirmed directly: line 1 is the file's first line, not 0
    or 2 -- see HANDOFF.md for the empirical check)."""

    def __init__(self, filename: str, start_line: int, line_count: int):
        self.filename = filename
        self.start_line = start_line
        self.line_count = line_count

    @property
    def end_line(self) -> int:
        return self.start_line + self.line_count - 1


def _is_glob_pattern(s: str) -> bool:
    return any(c in s for c in "*?[")


def resolve_inputs(args):
    """§18.4/§18.5: resolves CLI arguments into an ordered list of real
    file paths (strings). Raises CombineError naming the specific
    input that failed, for either a nonexistent literal file or a
    glob pattern matching zero files -- both are the same case,
    exactly per §18.5's "no distinction" rule.

    Glob expansion is ALWAYS performed here, by Python's own glob
    module (recursive=True unconditionally) -- never left to the
    invoking shell. Confirmed directly, not assumed: glob.glob with
    recursive=True still requires '**' in the pattern text itself to
    actually recurse; passing the flag doesn't make an ordinary '*'
    pattern recurse on its own."""
    literal_files = []
    glob_matches = []

    for arg in args:
        if _is_glob_pattern(arg):
            matches = [m for m in glob.glob(arg, recursive=True) if os.path.isfile(m)]
            if not matches:
                raise CombineError(
                    f"input pattern {arg!r} matched zero files (§18.5) -- "
                    "every input, literal path or glob pattern, must "
                    "resolve to at least one real file")
            glob_matches.extend(matches)
        else:
            if not os.path.isfile(arg):
                raise CombineError(
                    f"input file {arg!r} does not exist (§18.5) -- "
                    "every input, literal path or glob pattern, must "
                    "resolve to at least one real file")
            literal_files.append(arg)

    already_used = {os.path.normpath(f) for f in literal_files}
    deduped_glob = []
    for m in sorted(glob_matches):
        norm = os.path.normpath(m)
        if norm not in already_used:
            already_used.add(norm)
            deduped_glob.append(m)

    return literal_files + deduped_glob


def combine_sources(file_paths):
    """§18.2: reads and concatenates every resolved file into one
    in-memory source text, recording a FileSpan for each. Returns
    (combined_text, spans).

    Line counting is exact regardless of whether a file ends in its
    own trailing newline: splitting on '\\n' rather than using
    readlines() avoids counting one extra phantom line for a file that
    does end in '\\n' (readlines()/naive newline-counting can easily
    get this off by one -- checked directly against this exact case,
    not assumed correct)."""
    combined_lines = []
    spans = []
    current_line = 1  # 1-based, matching the parser's own convention

    for path in file_paths:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        lines = text.split("\n")
        if lines and lines[-1] == "":
            lines = lines[:-1]  # drop the phantom element from a trailing \n
        line_count = len(lines) if lines else 0

        spans.append(FileSpan(path, current_line, max(line_count, 1)))
        combined_lines.extend(lines)
        current_line += max(line_count, 1)

    combined_text = "\n".join(combined_lines) + "\n"
    return combined_text, spans


def remap_line(combined_line: int, spans):
    """Given a 1-based line number in the COMBINED text, returns
    (filename, original_line_in_that_file). Raises CombineError if the
    line falls outside every known span -- a defensive backstop that
    should be unreachable if spans were built correctly, not an
    expected runtime path."""
    for span in spans:
        if span.start_line <= combined_line <= span.end_line:
            return span.filename, combined_line - span.start_line + 1
    raise CombineError(
        f"internal error: combined-text line {combined_line} falls "
        f"outside every known file span -- this should be impossible")


def _remap_diag(diag, spans):
    """Remaps one CompileError/CompileWarning for reporting purposes.
    Deliberately does NOT mutate diag.line in place -- these objects
    are read-only as far as this module is concerned (see module
    docstring: nothing upstream of remapping should need to change,
    and mutating shared pipeline objects would be exactly the kind of
    hidden coupling that principle is meant to avoid). Returns a plain
    dict instead."""
    filename, orig_line = remap_line(diag.line, spans)
    return {
        "phase": diag.phase,
        "check": diag.check,
        "file": filename,
        "line": orig_line,
        "message": f"{filename}:{orig_line}: {diag.message}",
    }


def compile_multi(file_paths):
    """Runs the EXISTING single-file pipeline (parse_source ->
    resolve_all, entirely unmodified) against the combined text from
    file_paths, then remaps every line number in the result back to
    (source file, original line). This is the ONE piece of new logic
    touching the pipeline's output (§18.2).

    Returns a dict, one of two shapes:
      {"status": "parse_error", "error": {"phase": 3, "file": ...,
       "line": ..., "message": ...}}
    or
      {"status": "parsed", "resolver": Resolver, "spans": [...],
       "remapped_duplicate_errors": [...], "remapped_warnings": [...],
       "remapped_instance_errors": {name: {...}}}

    Callers (exporter CLIs, test harnesses) should use the remapped
    dicts for REPORTING, not read .line directly off resolver objects
    -- those still carry combined-text line numbers, unchanged, since
    they were never mutated."""
    from .parser import parse_source, GDDLParseError
    from .resolve import resolve_all

    combined_text, spans = combine_sources(file_paths)

    try:
        prog = parse_source(combined_text)
    except GDDLParseError as e:
        filename, orig_line = remap_line(e.line, spans)
        return {
            "status": "parse_error",
            "error": {
                "phase": 3,
                "file": filename,
                "line": orig_line,
                "message": f"{filename}:{orig_line}: {e.raw_message}",
            },
        }

    resolver = resolve_all(prog)

    return {
        "status": "parsed",
        "resolver": resolver,
        "spans": spans,
        "remapped_duplicate_errors": [_remap_diag(e, spans) for e in resolver.reg.duplicate_errors],
        "remapped_warnings": [_remap_diag(w, spans) for w in resolver.warnings],
        "remapped_instance_errors": {
            name: _remap_diag(e, spans) for name, e in resolver.errors.items()
        },
    }
