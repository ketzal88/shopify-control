#!/bin/bash
# filter-verbose-output: run a command, collapse its output ONLY when it passes.
#
# Verbose runners spend thousands of tokens to say "all green". A 370-line test
# run costs ~5.9k tokens to deliver one line of signal ("45/45 passed"). That
# lands in context on every run AND stays in the transcript, re-read on every
# later turn. This wrapper keeps the signal and drops the noise.
#
# Rule: if the command FAILS, nothing is filtered. A failure is exactly when you
# need the full output. A blind grep does the opposite: it strips the context you
# need at the worst possible moment.
#
# Preserves the command's REAL exit code. `cmd | grep` returns grep's status, not
# cmd's -- so a broken run reports green, and (worse) a passing run reports broken
# because grep exits 1 when it matches nothing. Gates that read exit codes silently
# invert. This captures rc before any pipe.
#
# Usage: bash filter-verbose-output.sh <command> [args...]
# Wired by: filter-verbose-guard.py (PreToolUse/Bash), driven by
#           context.filterVerbose in stack.json.

set -uo pipefail

if [ $# -eq 0 ]; then
  echo "usage: $0 <command> [args...]" >&2
  exit 2
fi

out=$("$@" 2>&1)
rc=$?

lines=$(printf '%s\n' "$out" | wc -l | tr -d ' ')

# The exit code is the AUTHORITATIVE failure signal. Text markers are only a
# safety net for runners that print FAIL but still exit 0.
#
# Deliberately NOT matching a bare 'Error:' here: test suites legitimately print
# expected errors (e.g. a test asserting an invalid-timezone fallback prints
# "RangeError: Invalid time zone" and passes). An unanchored 'Error:' matches
# inside 'RangeError:' and flags a green run as broken -- the same
# substring-without-boundaries bug that breaks keyword-matching rule injectors.
if [ "$rc" -ne 0 ] || printf '%s\n' "$out" | grep -qE '(^|[^A-Za-z])(FAIL|FAILED|✗|✘)([^A-Za-z]|$)'; then
  printf '%s\n' "$out"
  exit "$rc"
fi

# Passed -> verdict only.
verdict=$(printf '%s\n' "$out" | grep -E \
  '[0-9]+/[0-9]+ (tests? )?passed|[0-9]+ (tests?|specs?|examples?) passed|ALL [0-9]+ .*PASSED|OK \([0-9]+ tests?\)|no issues found|✔ No .*(warnings|errors)|PASSED' \
  | tail -4)

if [ -n "$verdict" ]; then
  printf '%s\n' "$verdict"
else
  # No recognizable verdict line: show the tail rather than guess.
  printf '%s\n' "$out" | tail -5
fi

echo "[ok] $* — $lines lines collapsed (passed; full output shown only on failure)"
exit "$rc"
