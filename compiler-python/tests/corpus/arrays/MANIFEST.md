# Arrays -- Fixture Manifest

Rule group: the arrays feature (`ElementType : dim1 : dim2 : ...` field types,
value literals, direct bracket-indexed element access/modification), designed
across `GDDL_Session_Handover.md` section 5 and implemented across stages 1-3
(see `compiler-python/HANDOFF.md`'s "Arrays work" entries for the full design
history and the real-toolchain export verification these fixtures build on).

Status: all ten fixtures captured against the real, current implementation --
`capture_status: "captured"` throughout, not predictions. Every value in each
fixture's "Expected" comment was computed by hand first, then confirmed
byte-for-byte against `export_golden.py`'s real output before the
`.golden.json` was written -- never the reverse, same discipline as
`corpus/flags/`.

| File | Isolates |
|---|---|
| `arrays_1d_literal_valid.gddl` | Positive baseline: a 1D array literal, with and without the always-optional single outermost brace layer -- confirms both forms produce the identical resolved value. |
| `arrays_multidim_literal_valid.gddl` | 2D and 3D nested literals, confirming the outermost-optional / inner-required brace rule generalizes past 1D, and that `dims` order matches both the type declaration's colon order and the value's own brace nesting order. |
| `arrays_string_elements_valid.gddl` | `string N` array elements, including one containing a literal comma inside its own quotes -- proves comma-splitting is quote-aware, not a naive split. |
| `arrays_bracket_index_copy_and_adjust_valid.gddl` | **Depth pass.** The arrays design's own motivating example end to end: a derived instance copies a base's array, then adjusts exactly one element via a bracket-indexed op-statement. Also exercises a cross-field reference plus arithmetic as an array element's own value, confirming array elements go through the same expression evaluator scalar fields already use, not a narrower literal-only parser. |
| `arrays_shape_mismatch_error.gddl` | Negative path, two instances: a value literal with the wrong element count, and a multi-dim literal missing its required inner braces -- both trigger `array_shape_mismatch`, isolated separately. |
| `arrays_element_type_unsupported_error.gddl` | Negative path, three fields in one define: struct-typed, identifier-typed, and flags-typed array elements, each explicitly deferred by the design and each getting its own specific `array_element_type_unsupported` rejection, not a generic message. Define-only fixture (phase 4, no instance needed). |
| `arrays_type_malformed_error.gddl` | Negative path, two fields: a non-integer dimension and a zero-valued dimension, both `array_type_malformed` -- distinct from element-type-unsupported above (a well-formed shape with a disallowed element vs. a shape that doesn't parse at all). Define-only fixture. |
| `arrays_bracket_index_errors_error.gddl` | Negative path, three instances: an out-of-bounds index (`array_index_out_of_range`), a bracket-indexed op-statement on a never-initialized array (`uninitialized_read` -- arrays are always either UNINIT as a whole or fully populated as a whole, never partially), and bracket indexing on a multi-dimensional array (`array_multidim_index_unsupported` -- scoped to 1D arrays only this pass). |
| `arrays_shape_validation_error.gddl` | Negative path, two instances, both phase 5 (`field_shape`, static, no resolution needed): a whole-array op-statement with no bracket index, and bracket indexing on a field that isn't array-typed at all. |
| `arrays_never_initialized_incomplete.gddl` | An array field that's never assigned is caught by phase 8's existing completeness check with zero array-specific code -- a fully populated array is just a plain list, never a `StructValue`, so the existing recursion already handles it. |

## Coverage check against the stage 4 task list

- [x] 1D and multi-dimensional literal parsing, including the
      outermost-optional/inner-required brace rule.
- [x] String array elements, including the quote-aware comma-splitting edge
      case.
- [x] The design's own motivating bracket-indexed copy-and-adjust example,
      plus expression/cross-field-reference array elements (an extension
      beyond the design's own shown examples, confirmed working).
- [x] Every registration-time (phase 4) rejection: malformed dimension
      syntax, and each of the three explicitly-deferred element types
      individually.
- [x] Every resolution-time (phase 6) bracket-indexing rejection: out of
      bounds, uninitialized, multi-dimensional.
- [x] Every static (phase 5) shape rejection: whole-array op-statement,
      bracket indexing on a non-array field.
- [x] Phase 8 completeness, unaffected by arrays needing any special
      handling.
- [x] Real, compiled/run output read back from real toolchains -- NOT in
      this folder (corpus fixtures only exercise phases 1-8, never export).
      See `export_cpp_test/`, `export_6502_test/`, `export_z80_test/`,
      `export_68000_test/`, `export_binary_test/` for the real-toolchain
      export fixtures wired into each driver suite's own `CASES` list.

## Notes

Numeric range/coercion enforcement on an array element is deliberately NOT
given its own fixture here: array elements are coerced/range-checked via
`_coerce_numeric`/`_check_string_length` called VERBATIM, the exact same
functions a plain scalar field already goes through (confirmed directly by
reading `resolve.py`'s `_parse_array_element`, not assumed) -- this is
already locked by every existing `numeric_range`/`numeric_coercion` fixture
in `corpus/numeric_range/` and `corpus/numeric_coercion/`, and a
dedicated array-specific duplicate would test the same code path a second
time, not a genuinely different one.

Every fixture's `check` name (`array_shape_mismatch`,
`array_element_type_unsupported`, `array_type_malformed`,
`array_index_out_of_range`, `array_multidim_index_unsupported`) was added
directly to `registry.py`/`resolve.py` as part of stage 2's own
implementation, confirmed present on the real `CompileError` objects before
these fixtures were locked -- the same "confirm the check name exists on
the real object, not just in message text" discipline `corpus/flags/`'s own
manifest already documents.
