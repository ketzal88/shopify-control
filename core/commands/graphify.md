---
description: Build and query a knowledge graph of the codebase — orient via graph traversal before grepping, so exploration is precise instead of a file-by-file crawl
---

A codebase-graph layer built on [graphify](https://github.com/Graphify-Labs/graphify). It parses
your code with tree-sitter (local AST, **no LLM, no API key, no token cost**) into a queryable graph
of entities and their `imports`/`contains` relationships. Language-agnostic by design — tree-sitter
covers 36+ languages, so unlike the rest of this framework **it needs no `stack.json`**.

Use it to answer "who uses this?", "how does A reach B?", and "where do I start?" — the questions
that otherwise cost several exploratory file reads.

## Install (once per machine)

```bash
uv tool install graphifyy      # recommended (isolated); or: pipx install graphifyy
graphify install               # register the skill globally for your AI assistant
# project-scoped instead: graphify install --project   → writes .claude/skills/graphify/
```

> PyPI package is `graphifyy` (double-y); the CLI is `graphify`.

## Build & keep fresh

```bash
graphify update .              # build/refresh the graph (AST only, ~seconds–1min, free)
```

Output lands in `graphify-out/` at the scanned path. **Gitignore it** — it's a large, regenerable
local artifact (`echo 'graphify-out/' >> .gitignore`). `node_modules`, `.next`, build dirs are
skipped automatically. Re-run `graphify update .` after substantial code changes (the Stop hook
below automates this).

## Query (during work — prefer these over grepping unknown territory)

```bash
graphify explain "requireClientAccess"   # a node + its neighbors: who imports/contains it (blast radius)
graphify path "SomeCron" "SomeService"   # shortest path between two entities (trace a flow)
graphify query "how are alerts routed"   # BFS subgraph for an open question (orient, then read real code)
```

`explain`/`path` are surgical; `query` is broader but noisier. Read `graphify-out/GRAPH_REPORT.md`
for a whole-architecture overview (community hubs, subsystems).

## The fact worth internalizing

The graph is a map of **imports**, not of **runtime dependencies**. It does not see coupling that
happens through data or the network — a job that hits a route over HTTP, two modules that share a
database table, an event that triggers a handler. On decoupled architectures those are the *real*
dependencies, and disconnected islands in the graph reflect exactly that. Use the graph to **orient
fast, then read the real code** — never as a complete impact analysis for data/HTTP-coupled flows.

## Auto-consult (opt-in, aggressive mode)

Wire `graphify hook-guard search` (PreToolUse Bash) and `graphify hook-guard read`
(PreToolUse Read|Glob) so the assistant is nudged to consult the graph before grepping. This trades
a small per-operation token tax for graph-first exploration — worth it on large, exploration-heavy
repos; skip it on small ones where grep already suffices.

## Windows note

If the `graphify` console script can't be written (read-only global `Scripts/`, or not on `PATH`),
call `python -m graphify <cmd>` everywhere instead, and drop a shim named `graphify` (+ `graphify.cmd`)
that runs `python -m graphify %*` into any writable directory already on `PATH`. Wire the hooks with
`python -m graphify hook-guard ...` — bulletproof regardless of the shim.
