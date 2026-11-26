#!/usr/bin/env python3
"""Stop hook (close-protocol): reminds ONCE if the turn ends with uncommitted code.

Config-driven: enabled only when gates.closeProtocol = "blocking" in
stack.json. Absent key = silent no-op (framework convention).

Why: a friction audit of 100+ real sessions showed the most common
end-of-session pattern was the operator chasing the agent with "did you
commit?" - the close was never codified. The correct close for
substantial work is: run the commit-checkpoint flow, commit, and end the
final message with "committed: <short sha> - N commit(s) ready to push".

1.5.0 - SESSION-SCOPED: with two sessions open on the same repo, `git status`
mixes both sessions' work, and the old hook blamed this session for the other
one's files. Agents then either committed work that was not theirs (with a
`git add -A`) or learned to ignore the hook. Now the dirty files are split with
the transcript (session_files.attribute): only files THIS session touched can
block; the rest are listed as a count and left alone. If the transcript cannot
be read, it falls back to the whole dirty tree (the 1.4 behaviour).

Also checks repos nested one level down (a monorepo of independent repos:
work committed in the parent can leave a child dirty), and mentions commits
that are ready to push so the final message can report them.

1.5.3 - gates.closeUnpushed = "report": commits that never got pushed (root
and nested repos) also trigger the reminder, even with a clean tree. The agent
cannot fix them when push is operator-only, so it only REPORTS them; the close
line is the one place where "committed" and "pushed" stop meaning the same
thing. Found in the wild: a nested repo sat 3 commits ahead of origin for
weeks because nothing ever said so out loud.

Blocks (exit 2) only ONCE per close (stop_hook_active breaks the loop).
If the dirty files are deliberate WIP, the agent says so explicitly in its
final message and closes on the retry.

Skip conditions (exit 0):
  - stop_hook_active=True (re-trigger of our own previous block).
  - SKIP_COMMITCHECK=1 (explicit bypass).
  - gates.closeProtocol not configured.
  - no code file of this session left dirty (docs/config never count:
    .md, docs/, .claude/, .github/) and no unpushed commit to report.
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")
sys.path.insert(0, SCRIPT_DIR)
import session_files  # noqa: E402

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


def git(args, cwd):
    try:
        r = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception:
        return None


def dirty_code(repo):
    """Dirty code paths of one repo, relative to it (docs/config excluded)."""
    out = git(["status", "--porcelain"], repo)
    if out is None:
        return []
    paths = []
    for line in out.splitlines():
        if len(line) <= 3:
            continue
        path = line[3:].strip()
        if " -> " in path:  # rename: keep the new name
            path = path.split(" -> ", 1)[1]
        path = path.strip('"').replace("\\", "/")
        if path.endswith("/"):
            continue  # an untracked directory: a nested repo or a new folder
        if path.endswith(DOC_SUFFIXES) or any(path.startswith(p) for p in DOC_DIR_PREFIXES):
            continue
        paths.append(path)
    return paths


def nested_repos(root):
    try:
        names = sorted(os.listdir(root))
    except Exception:
        return []
    return [n for n in names
            if not n.startswith(".") and os.path.isdir(os.path.join(root, n, ".git"))]


def unpushed(repo):
    out = git(["rev-list", "--count", "@{upstream}..HEAD"], repo)
    try:
        return int((out or "0").strip())
    except ValueError:
        return 0


def main():
    try:
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    if payload.get("stop_hook_active"):
        return 0
    if os.environ.get("SKIP_COMMITCHECK") == "1":
        return 0
    if cfg("gates.closeProtocol") != "blocking":
        return 0

    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    subs = nested_repos(root)
    dirty = dirty_code(root)
    for sub in subs:
        dirty += [sub + "/" + p for p in dirty_code(os.path.join(root, sub))]

    mine, foreign = [], []
    if dirty:
        split = session_files.attribute(dirty, payload.get("transcript_path"), root)
        mine, foreign = (dirty, []) if split is None else split  # unreadable: 1.4 behaviour

    ahead = [(".", unpushed(root))] + [(sub, unpushed(os.path.join(root, sub))) for sub in subs]
    ahead = [(name, n) for name, n in ahead if n]
    report_ahead = cfg("gates.closeUnpushed") == "report"

    if not mine and not (report_ahead and ahead):
        return 0  # nothing of this session's to commit, nothing to report

    w = sys.stderr.write
    if mine:
        w("[close-protocol] " + str(len(mine)) + " code file(s) of this session left uncommitted:\n")
        for p in mine[:10]:
            w("  " + p + "\n")
        if len(mine) > 10:
            w("  ... and " + str(len(mine) - 10) + " more\n")
        if foreign:
            w("(" + str(len(foreign)) + " other dirty file(s) were not touched by this session:"
              " ignored. Do not commit them and do not use `git add -A`.)\n")
        w(
            "\nBefore closing, pick ONE:\n"
            "  a) Finished work -> run the commit-checkpoint flow, `git add` THESE paths\n"
            "     by name, commit, and end your message with 'committed: <sha> - N\n"
            "     commit(s) ready to push'. NEVER run git push yourself unless the\n"
            "     push policy says so.\n"
            "  b) Deliberate WIP -> say so explicitly in your final message (which\n"
            "     files and why) and close.\n"
        )
    if ahead:
        w("\n[close-protocol] commit(s) not pushed yet:\n")
        for name, n in ahead:
            w("  " + name + ": " + str(n) + " commit(s) ahead of upstream\n")
        if report_ahead:
            w("Do not push them unless the push policy says so. Name each repo and its\n"
              "count in your final message, and say whose work it is if not yours.\n")
    w("\nThis reminder fires once per close. Bypass: SKIP_COMMITCHECK=1.\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
