#!/usr/bin/env python3
"""Stop hook (close-protocol): reminds ONCE if the turn ends with uncommitted code.

Config-driven: enabled only when gates.closeProtocol = "blocking" in
stack.json. Absent key = silent no-op (framework convention).

Why: a friction audit of 100+ real sessions showed the most common
end-of-session pattern was the operator chasing the agent with "did you
commit?" — the close was never codified. The correct close for
substantial work is: run the commit-checkpoint flow, commit, and end the
final message with "committed: <short sha> - N commit(s) ready to push".

Blocks (exit 2) only ONCE per close (stop_hook_active breaks the loop).
If the dirty files are deliberate WIP or another session's debt, the
agent says so explicitly in its final message and closes on the retry.

Skip conditions (exit 0):
  - stop_hook_active=True (re-trigger of our own previous block).
  - SKIP_COMMITCHECK=1 (explicit bypass).
  - gates.closeProtocol not configured.
  - clean working tree, or only docs/config changes (.md, docs/, .claude/, .github/).
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")

DOC_SUFFIXES = (".md",)
DOC_DIR_PREFIXES = ("docs/", ".claude/", ".github/")


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
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except Exception:
        return 0

    if payload.get("stop_hook_active"):
        return 0
    if os.environ.get("SKIP_COMMITCHECK") == "1":
        return 0
    if cfg("gates.closeProtocol") != "blocking":
        return 0

    try:
        r = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        lines = [ln for ln in (r.stdout or "").splitlines() if len(ln) > 3]
    except Exception:
        return 0

    code_files = []
    for line in lines:
        path = line[3:].strip().strip('"').replace("\\", "/")
        if path.endswith(DOC_SUFFIXES):
            continue
        if any(path.startswith(p) for p in DOC_DIR_PREFIXES):
            continue
        code_files.append(path)

    if not code_files:
        return 0

    sys.stderr.write(
        "[close-protocol] " + str(len(code_files)) +
        " code file(s) left uncommitted:\n"
    )
    for p in code_files[:10]:
        sys.stderr.write("  " + p + "\n")
    if len(code_files) > 10:
        sys.stderr.write("  ... and " + str(len(code_files) - 10) + " more\n")
    sys.stderr.write(
        "\nBefore closing, pick ONE:\n"
        "  a) Finished work of yours -> run the commit-checkpoint flow, commit,\n"
        "     and end your message with 'committed: <sha> - N commit(s) ready to\n"
        "     push'. NEVER run git push yourself (the push belongs to the operator).\n"
        "  b) Deliberate WIP or another session's debt -> say so explicitly in your\n"
        "     final message (which files and why) and close.\n"
        "\nThis reminder fires once per close. Bypass: SKIP_COMMITCHECK=1.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
