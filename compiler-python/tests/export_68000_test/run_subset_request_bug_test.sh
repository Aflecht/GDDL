#!/bin/bash
# Real vbcc compile + vamos execution for the subset-request bug fix
# (export_68000.py's render_c89_split AoS struct emission). Run from
# this directory.
#
# Requires: VBCC env var pointing at a built vbcc distribution
# (bin/config/targets), amitools' vamos on PATH.
set -e
VBCC="${VBCC:?set VBCC to the vbcc distribution root}"
PATH="$VBCC/bin:$PATH" vc +aos68k -I. \
    test_68000_subset_request_bug.c generated_68000_subset_request_bug.c \
    -o test_68000_subset_request_bug
vamos test_68000_subset_request_bug
