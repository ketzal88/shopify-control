#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks commands that ALWAYS fail in this environment.

Config-driven: reads environment.forbiddenCommands from stack.json —
an array of { "pattern": "<regex>", "fix": "<what to use instead>" }.
Absent key = silent no-op (framework convention).

Why: a friction audit of 100+ real sessions showed the agent re-picking
the broken "default" path (global linter without config, interactive CLI
logins that die headless, tools not installed on the machine) session
after session, burning 1-3 turns each time. Blocking with the exact
correction in the message turns the gotcha into a 0-turn self-fix.

Bypass: SKIP_CANONICAL=1 in the env, or the literal marker
`SKIP_CANONICAL=1` inside the command itself (env prefixes in the command
string do NOT reach the hook process).

Input contract (stdin JSON from Claude Code harness):
    { "tool_input": { "command": "..." }, ... }

NOTE: keep messages ASCII-safe — cp1252 consoles mangle non-ASCII.
"""
import json
import os
import re
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")


def cfg(key):
    try:
        r = subprocess.run(
            [sys.executable, READ_CONFIG, key],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def main():
    if os.environ.get("SKIP_CANONICAL") == "1":
        return 0

    try:
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except Exception:
        return 0

    cmd = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not cmd:
        return 0
    if "SKIP_CANONICAL=1" in cmd:
        return 0

    rules_raw = cfg("environment.forbiddenCommands")
    if not rules_raw:
        return 0
    try:
        rules = json.loads(rules_raw)
    except Exception:
        return 0
    if not isinstance(rules, list):
        return 0

    for rule in rules:
        pattern = (rule or {}).get("pattern", "")
        fix = (rule or {}).get("fix", "")
        if not pattern:
            continue
        try:
            if re.search(pattern, cmd):
                sys.stderr.write("[canonical-guard] command blocked in this environment:\n")
                sys.stderr.write("  " + cmd.strip()[:200] + "\n\n")
                sys.stderr.write("  " + (fix or "See environment rules for the canonical path.") + "\n\n")
                sys.stderr.write(
                    "  Config: environment.forbiddenCommands in stack.json"
                    "  |  Bypass: SKIP_CANONICAL=1\n"
                )
                return 2
        except re.error:
            continue  # malformed pattern in config — never block on config bugs

    return 0


if __name__ == "__main__":
    sys.exit(main())
