#!/bin/bash
# Headless Atari ST test runner (hatari + EmuTOS), analogous to vamos
# for Amiga. Confirmed working invocation, documented here so it's
# reproducible rather than ad hoc:
#
#   xvfb-run -a hatari --tos <emutos.img> --harddrive <dir> \
#       --auto 'C:\PROGRAM.PRG' --conout 2 --run-vbls <n> --log-level warn
#
# Findings, confirmed directly rather than assumed:
#   - hatari needs xvfb-run (or an equivalent virtual display) even
#     with --disable-video -- that flag means "don't render," not
#     "don't need a display connection at all." Without a display,
#     hatari hangs rather than erroring out cleanly.
#   - hatari needs a real TOS-compatible ROM image to boot at all
#     (not bundled with the apt package, and not fetchable from any
#     of the official EmuTOS/TOS hosts, which are all blocked by this
#     sandbox's network egress proxy). Got a real, free EmuTOS
#     etos1024k.img from github.com/bbbradsmith/hatariB, which commits
#     real EmuTOS binaries directly into its repo (GitHub is
#     reachable; the official EmuTOS/TOS distribution hosts are not).
#   - --auto needs a full "C:\PATH" style Atari path (drive letter +
#     backslash), not a bare filename -- a bare filename silently
#     doesn't autostart anything.
#   - hatari's own process exit code is ALWAYS 0 regardless of the
#     emulated program's actual return value (confirmed directly: a
#     test program that returns 1 still yields hatari exit code 0).
#     Unlike vamos, which does propagate the guest's exit code.
#     Validation MUST parse captured console output (--conout), never
#     rely on the host exit code.
#   - --run-vbls is what makes this deterministic and script-friendly:
#     hatari exits cleanly on its own after N video blanks, once tuned
#     high enough for the boot+program to finish. No external `timeout
#     -k` kill is needed for a correctly-tuned run (confirmed: a
#     tuned run completes in ~7s with clean exit, versus a mistuned
#     one needing an external kill and leaving X-connection noise in
#     the output).
#
# Usage: run_atari_test.sh <PRG file> <harddrive dir> [run-vbls]

set -e

PRG="$1"
HD_DIR="$2"
VBLS="${3:-400}"
EMUTOS="${EMUTOS_IMG:-/home/claude/gddl/tools/emutos/etos1024k.img}"

xvfb-run -a hatari --tos "$EMUTOS" \
    --harddrive "$HD_DIR" \
    --auto "C:\\$(basename "$PRG")" \
    --conout 2 \
    --run-vbls "$VBLS" \
    --log-level warn
