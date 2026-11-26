#!/usr/bin/env python3
"""session_files: which files did THIS Claude session touch? Shared by the Stop hooks.

Not a hook by itself. Used by close-guard.py and ratchet-guard.py.

Why: `git status` answers a different question. With two sessions open on the
same repo (a normal way of working), the dirty tree mixes both sessions' work,
and a Stop hook that reads `git status` blames one session for the other's
debt. Agents then either "fix" files that are not theirs or learn to ignore
the hook.

Sources, joined by session_touched():
  1. Edit/Write/MultiEdit/NotebookEdit tool calls in the transcript.
  2. Files of the commits THIS session created.

Source 2 is not optional:
  - Edits made through Bash (sed, codemods, scripts) leave no Edit tool call.
  - Committed files no longer show in `git status`, so a ratchet that only reads
    the working tree stops seeing what the session committed: committing was
    enough to escape it. A guard that switches off when you do the right thing
    is worse than one that nags.

Source 2 can NOT be "every commit since the session started": a parallel
session's commits fall in the same window. So a commit only counts if its
subject also appears in a Bash command of this transcript, i.e. this session
typed it. A commit made by hand in another terminal does not match.

Everything returns None when the transcript cannot be read: callers fall back
to their old behaviour (git status) instead of assuming "touched nothing".

ASCII-only (cp1252 consoles).
"""
import json
import os
import subprocess

EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
SHELL_TOOLS = {"Bash", "PowerShell"}
# Cap on collected shell text: commands are small next to the transcript, the cap
# only keeps a very long session from eating the hook's memory.
BASH_TEXT_CAP = 2_000_000


def _root_key(project_root):
    return project_root.replace("\\", "/").rstrip("/").lower()


def _rel(raw, root_key):
    """Absolute or relative path -> posix path relative to the repo, CASE PRESERVED.

    Case is preserved on purpose: tools report paths as they are on disk
    (PascalCase components), and lowercasing would make every one of them miss.
    Only the repo prefix is compared case-insensitively (Windows reports the
    drive letter with inconsistent case).
    """
    p = raw.replace("\\", "/")
    if p.lower().startswith(root_key + "/"):
        p = p[len(root_key) + 1:]
    while p.startswith("./"):
        p = p[2:]
    return p


def _outside_repo(rel):
    """True if the path is still absolute (could not be made repo-relative)."""
    return ":" in rel or rel.startswith("/")


def scan(transcript_path, project_root):
    """One pass over the transcript -> (edited paths, shell command text).

    Returns (None, "") if the transcript is missing or unreadable.
    """
    if not transcript_path or not os.path.isfile(transcript_path):
        return None, ""
    root = _root_key(project_root)
    touched, chunks, size = set(), [], 0
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"tool_use"' not in line:
                    continue
                try:
                    entry = json.loads(line)
                except Exception:
                    continue
                content = (entry.get("message") or {}).get("content")
                if not isinstance(content, list):
                    continue
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_use":
                        continue
                    name = block.get("name")
                    inp = block.get("input") or {}
                    if name in EDIT_TOOLS:
                        raw = inp.get("file_path") or inp.get("notebook_path")
                        if isinstance(raw, str) and raw:
                            rel = _rel(raw, root)
                            if not _outside_repo(rel):  # scratchpad, temp files
                                touched.add(rel)
                    elif name in SHELL_TOOLS and size < BASH_TEXT_CAP:
                        cmd = inp.get("command")
                        if isinstance(cmd, str) and cmd:
                            chunks.append(cmd)
                            size += len(cmd)
    except Exception:
        return None, ""
    return touched, "\n".join(chunks)


def session_start(transcript_path):
    """ISO timestamp of the first transcript event, or None."""
    if not transcript_path or not os.path.isfile(transcript_path):
        return None
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                if '"timestamp"' not in line:
                    continue
                try:
                    ts = json.loads(line).get("timestamp")
                except Exception:
                    continue
                if isinstance(ts, str) and ts:
                    return ts
    except Exception:
        return None
    return None


def own_commit_files(iso_ts, shell_text, project_root):
    """Files of the commits THIS session created since iso_ts (empty set on error)."""
    if not iso_ts or not shell_text:
        return set()
    # \x02 and not NUL: Python rejects an embedded NUL in argv with ValueError,
    # and inside a try/except that failure would be silent forever.
    sep = "\x02"
    try:
        r = subprocess.run(
            ["git", "log", "--since=" + iso_ts, "--name-only", "--pretty=format:%x01%s" + sep],
            cwd=project_root, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=15,
        )
    except Exception:
        return set()
    if r.returncode != 0:
        return set()
    root = _root_key(project_root)
    files = set()
    for chunk in (r.stdout or "").split("\x01"):
        if not chunk.strip():
            continue
        subject, _, body = chunk.partition(sep)
        subject = subject.strip()
        if not subject or subject not in shell_text:
            continue
        for ln in body.splitlines():
            ln = ln.strip()
            if ln:
                rel = _rel(ln, root)
                if not _outside_repo(rel):
                    files.add(rel)
    return files


def session_touched(transcript_path, project_root):
    """Edited by tool call  UNION  committed by this session. None if unreadable."""
    edits, shell_text = scan(transcript_path, project_root)
    if edits is None:
        return None
    return edits | own_commit_files(session_start(transcript_path), shell_text, project_root)


def attribute(dirty_paths, transcript_path, project_root):
    """Split dirty paths into (mine, foreign). None if the transcript is unreadable.

    A dirty path is "mine" if this session edited it by tool call, committed it,
    or named it in a shell command (catches sed/codemod edits that are still
    uncommitted). Everything else is another session's or the operator's.
    """
    edits, shell_text = scan(transcript_path, project_root)
    if edits is None:
        return None
    touched = edits | own_commit_files(session_start(transcript_path), shell_text, project_root)
    mine, foreign = [], []
    for p in dirty_paths:
        if p in touched or (p and p in shell_text):
            mine.append(p)
        else:
            foreign.append(p)
    return mine, foreign
