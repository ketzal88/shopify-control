#!/usr/bin/env python3
"""PreToolUse hook: wrap verbose commands so their output collapses when they pass.

Reads context.filterVerbose from stack.json -- a list of EXACT commands whose
output is noise when green. Absent key = no wrapping, silently (framework rule:
absent key = safe skip).

Why: a 370-line test run costs ~5.9k tokens to say "45/45 passed". That enters
context on every run and stays in the transcript, re-read on every later turn.
Measured on the reference project: 5,928 -> 34 tokens (99.4%) and 3,219 -> 58
(98.2%). The wrapper shows the full output whenever the command fails.

Defensive by design -- this hook sees EVERY Bash call:
  * EXACT, anchored match against the list. No substring matching: a rule that
    fires on substrings matches `test:unit` inside `test:unittest` and wraps the
    wrong command.
  * Never touches composed commands (pipe/redirect/&&/;/subshell) -- there the
    operator already decided what they want to see.
  * Fail-open: any doubt or exception returns {} and the command runs untouched.
    A token-saving hook must never break a command.

Do NOT list typecheck/lint here: they are already quiet when they pass, and when
they fail you want the whole error.

Input contract (stdin JSON from Claude Code harness):
    { "tool_input": { "command": "npm test" }, ... }

Bypass: SKIP_OUTPUT_FILTER=1
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")
WRAPPER = os.path.join(SCRIPT_DIR, "filter-verbose-output.sh")
# The rewritten command is run by bash, where a backslash is an escape character.
# On Windows os.path.join yields C:\...\filter-verbose-output.sh and bash would
# mangle it. Forward slashes work on every platform, including Git Bash.
WRAPPER_SH = WRAPPER.replace("\\", "/")

# Pipe, redirect, chain, subshell, expansion -> operator composed it on purpose.
COMPOSED = re.compile(r"[|><;&`$]")


def cfg(key):
    """Read a dotted key from stack.json via read-config.py (exit 1 = absent)."""
    try:
        r = subprocess.run(
            [sys.executable, READ_CONFIG, key],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def wrappable_commands():
    raw = cfg("context.filterVerbose")
    if not raw:
        return []
    try:
        val = json.loads(raw)
    except Exception:
        return [s.strip() for s in raw.split(",") if s.strip()]
    if isinstance(val, str):
        return [val]
    if isinstance(val, list):
        return [str(v).strip() for v in val if str(v).strip()]
    return []


def main():
    if os.environ.get("SKIP_OUTPUT_FILTER") == "1":
        print("{}")
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        print("{}")  # fail-open
        return 0

    try:
        cmd = ((payload.get("tool_input") or {}).get("command") or "").strip()
        if not cmd or COMPOSED.search(cmd):
            print("{}")
            return 0

        if cmd not in wrappable_commands():
            print("{}")
            return 0

        if not os.path.isfile(WRAPPER):
            print("{}")  # wrapper missing -> skip, don't break the command
            return 0

        print(json.dumps({
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": {"command": f'bash "{WRAPPER_SH}" {cmd}'},
            }
        }))
    except Exception:
        print("{}")  # fail-open

    return 0


if __name__ == "__main__":
    sys.exit(main())
