#!/usr/bin/env python3
"""Stop hook: runs the dead-code ratchet before Claude ends a turn.

Reads ratchets.deadCode from stack.json. If absent or empty — skip silently.
Blocks (exit 2) only on genuine regression (ratchet command exits 1).
Any other exit code (tooling crash, timeout) is logged but never blocks.

Skip conditions:
  - stop_hook_active=True in payload (prevent infinite re-trigger loop)
  - SKIP_DEADCODE=1 env var
  - No code-file changes in working tree
  - ratchets.deadCode not configured in stack.json
  - Ratchet command crashes or times out

Input contract (stdin JSON from Claude Code harness):
    { "stop_hook_active": bool, "session_id": "...", ... }
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")
TIMEOUT_SEC = 60

# File extensions that count as code changes (triggers ratchet check)
CODE_EXTS = (".ts", ".tsx", ".js", ".cjs", ".mjs",
             ".py", ".go", ".java", ".rs", ".rb", ".json")


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
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    if payload.get("stop_hook_active"):
        return 0
    if os.environ.get("SKIP_DEADCODE") == "1":
        return 0

    # Skip if only docs/config changed
    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        lines = (r.stdout or "").splitlines()
    except Exception:
        return 0

    changed_paths = [
        line[3:].strip().strip('"').replace("\\", "/")
        for line in lines
        if len(line) > 3
    ]
    has_code = any(p.endswith(CODE_EXTS) for p in changed_paths)
    if not has_code:
        return 0

    ratchet_cmd = cfg("ratchets.deadCode")
    if not ratchet_cmd:
        return 0

    # Scope-by-diff contract: CHANGED_FILES (newline-separated, /-normalized)
    # carries the files THIS session touched. A ratchet command MAY use it to
    # block only on regressions in those files and downgrade inherited debt
    # (another session's WIP) to a warning. CI runs the same command WITHOUT
    # CHANGED_FILES and keeps strict global enforcement, so the floor holds.
    try:
        result = subprocess.run(
            ["bash", "-c", ratchet_cmd],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace",
            timeout=TIMEOUT_SEC,
            env={**os.environ, "CHANGED_FILES": "\n".join(changed_paths)},
        )
    except subprocess.TimeoutExpired:
        sys.stderr.write(
            f"[ratchet-guard] dead-code ratchet timed out (>{TIMEOUT_SEC}s) — skipping.\n"
        )
        return 0
    except Exception as e:
        sys.stderr.write(f"[ratchet-guard] ratchet skipped: {e}\n")
        return 0

    if result.returncode == 0:
        return 0
    if result.returncode != 1:
        # Tooling error (not installed, missing baseline, etc.) — don't block
        sys.stderr.write(
            f"[ratchet-guard] ratchet exit {result.returncode} (tooling issue) — not blocking.\n"
        )
        return 0

    sys.stderr.write("[ratchet-guard] blocking stop — dead-code ratchet regressed:\n\n")
    sys.stderr.write(result.stderr or result.stdout or "")
    sys.stderr.write("\n")
    sys.stderr.write("Options:\n")
    sys.stderr.write("  - Delete orphaned exports/files\n")
    sys.stderr.write("  - Wire them to a real consumer\n")
    sys.stderr.write("  - Re-baseline if floor genuinely dropped (see ratchets.deadCode in stack.json)\n")
    sys.stderr.write("Bypass: SKIP_DEADCODE=1\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
