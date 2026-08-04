#!/bin/bash
# Real vbcc compile + vamos execution for composition_nested_u16_fields.gddl
# on the 68000 target. Run from export_68000_test/.
#
# Requires: VBCC env var pointing at a built vbcc distribution
# (bin/config/targets), amitools' vamos on PATH.
set -e
VBCC="${VBCC:?set VBCC to the vbcc distribution root}"
PATH="$VBCC/bin:$PATH" vc +aos68k -I. \
    test_68000_composition_u16.c generated_68000_composition_u16.c \
    -o test_68000_composition_u16
vamos test_68000_composition_u16
