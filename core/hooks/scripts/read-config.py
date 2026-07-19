#!/usr/bin/env python3
"""read-config: read a dotted key from stack.json -> stdout (exit 1 = key absent = safe skip).

Usage:  python read-config.py <dotted.key>
Output: value to stdout + exit 0, OR empty + exit 1 (callers treat as "skip this gate").

Searches for stack.json from cwd upward (up to 10 levels). Missing file = exit 1.
Array/object values are printed as JSON so callers can parse them.
"""
import json
import os
import sys


def find_manifest(start):
    d = start
    for _ in range(10):
        f = os.path.join(d, "stack.json")
        if os.path.isfile(f):
            return f
        p = os.path.dirname(d)
        if p == d:
            break
        d = p
    return None


def main():
    if len(sys.argv) < 2:
        sys.exit(1)
    manifest = find_manifest(os.getcwd())
    if not manifest:
        sys.exit(1)
    try:
        data = json.load(open(manifest, encoding="utf-8"))
    except Exception:
        sys.exit(1)
    node = data
    for k in sys.argv[1].split("."):
        if not isinstance(node, dict) or k not in node:
            sys.exit(1)
        node = node[k]
    if node is None or node == "" or node == [] or node is False:
        sys.exit(1)
    print(json.dumps(node) if isinstance(node, (list, dict)) else str(node))


if __name__ == "__main__":
    main()
