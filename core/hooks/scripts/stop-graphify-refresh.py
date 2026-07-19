#!/usr/bin/env python3
"""Stop hook: refresh the graphify knowledge graph when code changed this session.

Opt-in and self-skipping: does nothing unless a graph already exists
(graphify-out/graph.json). Non-blocking by design — when the working tree has code
changes it spawns `graphify update .` in a DETACHED background process and returns
immediately, so the turn never waits on the (~seconds–1min) AST re-extraction. A
lockfile (graphify-out/.refresh.lock) prevents overlapping refreshes.

Always exits 0 (a stale graph must never block a turn). Bypass: SKIP_GRAPHIFY_REFRESH=1.
Language-agnostic; ASCII-only messages for cross-platform console safety.
"""
import os
import shutil
import subprocess
import sys
import time

# Extend for your stack if the graph should track more than these.
CODE_EXTS = ('.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs', '.py', '.go', '.rs',
             '.java', '.rb', '.php', '.c', '.h', '.cpp', '.cs', '.kt', '.swift')
LOCK_TTL = 600  # seconds; a lock older than this is treated as stale


def graphify_argv():
    """Prefer the `graphify` console script; fall back to `python -m graphify`."""
    if shutil.which('graphify'):
        return ['graphify']
    return [sys.executable, '-m', 'graphify']


def code_changed(root):
    try:
        out = subprocess.run(
            ['git', 'status', '--porcelain'],
            cwd=root, capture_output=True, text=True, timeout=15,
        ).stdout
    except Exception:
        return False
    for line in out.splitlines():
        path = line[3:].strip()
        if ' -> ' in path:  # rename: "old -> new"
            path = path.split(' -> ')[-1].strip()
        if path.startswith('graphify-out'):
            continue
        if path.endswith(CODE_EXTS):
            return True
    return False


def main():
    if os.environ.get('SKIP_GRAPHIFY_REFRESH'):
        return 0
    root = os.environ.get('CLAUDE_PROJECT_DIR', '.')

    if not os.path.exists(os.path.join(root, 'graphify-out', 'graph.json')):
        return 0  # no graph -> nothing to keep fresh
    if not code_changed(root):
        return 0

    lock = os.path.join(root, 'graphify-out', '.refresh.lock')
    try:
        if os.path.exists(lock) and (time.time() - os.path.getmtime(lock) < LOCK_TTL):
            return 0  # a refresh is already in flight
    except Exception:
        pass
    try:
        os.makedirs(os.path.dirname(lock), exist_ok=True)
        with open(lock, 'w') as fh:
            fh.write(str(int(time.time())))
    except Exception:
        return 0

    argv = graphify_argv()
    inner = (
        "import subprocess, os;"
        "subprocess.run({argv} + ['update', '.'], cwd=r'{root}');"
        "os.remove(r'{lock}') if os.path.exists(r'{lock}') else None"
    ).format(argv=repr(argv), root=root, lock=lock)

    kwargs = dict(cwd=root, stdin=subprocess.DEVNULL,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == 'nt':
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        kwargs['creationflags'] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        kwargs['start_new_session'] = True

    try:
        subprocess.Popen([sys.executable, '-c', inner], **kwargs)
        print('[graphify] refreshing knowledge graph in background', file=sys.stderr)
    except Exception:
        try:
            os.remove(lock)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
