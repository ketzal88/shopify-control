#!/usr/bin/env python3
"""Stop hook: refresh the graphify knowledge graph when code changed this session.

Opt-in and self-skipping: does nothing unless a graph already exists
(graphify-out/graph.json). Non-blocking by design - when the working tree has code
changes it spawns `graphify update .` in a DETACHED background process and returns
immediately, so the turn never waits on the (~seconds-1min) AST re-extraction. A
lockfile (graphify-out/.refresh.lock) prevents overlapping refreshes.

1.5.0:
  - Also refreshes when the graph was built at another commit than HEAD
    (graph.json `built_at_commit`): committed code used to leave the working
    tree clean and the graph stale until the next dirty turn.
  - The background job is this same file run with --worker, not an inline
    `python -c` string: a path with a quote or a trailing backslash broke the
    inline code on Windows, silently.
  - CREATE_NO_WINDOW on Windows: DETACHED_PROCESS alone flashes a console.

Always exits 0 (a stale graph must never block a turn). Bypass: SKIP_GRAPHIFY_REFRESH=1.
Language-agnostic; ASCII-only messages for cross-platform console safety.
"""
import os
import re
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


def graph_behind_head(root):
    """True if graph.json records a build commit that is not HEAD.

    Reads only the first and last 4 KB: the key sits at one end and graphs
    reach tens of MB. No key, or no git: False (fall back to the dirty check).
    """
    path = os.path.join(root, 'graphify-out', 'graph.json')
    try:
        size = os.path.getsize(path)
        with open(path, 'rb') as fh:
            head = fh.read(4096)
            if size > 8192:
                fh.seek(size - 4096)
            tail = fh.read(4096)
    except Exception:
        return False
    m = re.search(rb'"built_at_commit"\s*:\s*"([0-9a-f]{7,40})"', head + tail)
    if not m:
        return False
    try:
        r = subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=root,
                           capture_output=True, text=True, timeout=10)
    except Exception:
        return False
    built = m.group(1).decode()
    current = (r.stdout or '').strip()
    return r.returncode == 0 and bool(current) and not current.startswith(built)


def worker(root, lock):
    """Background half: run the update, then release the lock."""
    try:
        subprocess.run(graphify_argv() + ['update', '.'], cwd=root,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL)
    finally:
        try:
            os.remove(lock)
        except Exception:
            pass
    return 0


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--worker':
        return worker(sys.argv[2], sys.argv[3])
    if os.environ.get('SKIP_GRAPHIFY_REFRESH'):
        return 0
    root = os.environ.get('CLAUDE_PROJECT_DIR', '.')

    if not os.path.exists(os.path.join(root, 'graphify-out', 'graph.json')):
        return 0  # no graph -> nothing to keep fresh
    if not code_changed(root) and not graph_behind_head(root):
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

    kwargs = dict(cwd=root, stdin=subprocess.DEVNULL,
                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.name == 'nt':
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        CREATE_NO_WINDOW = 0x08000000
        kwargs['creationflags'] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
    else:
        kwargs['start_new_session'] = True

    try:
        subprocess.Popen([sys.executable, os.path.abspath(__file__), '--worker', root, lock],
                         **kwargs)
        print('[graphify] refreshing knowledge graph in background', file=sys.stderr)
    except Exception:
        try:
            os.remove(lock)
        except Exception:
            pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
