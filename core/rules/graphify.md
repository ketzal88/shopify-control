# Codebase Graph — orient before you crawl

When a [graphify](https://github.com/Graphify-Labs/graphify) knowledge graph exists
(`graphify-out/graph.json`), it is the cheapest way to answer structural questions. This rule is
**opt-in** — it applies only once a graph is built, and skips silently otherwise.

## When to consult the graph first

- **Before exploring unfamiliar code** — `graphify query "<question>"` to orient, then read only the
  files that matter. Beats reading many files to reconstruct structure by hand.
- **Before touching a shared module** — `graphify explain "<name>"` to see the blast radius (who
  imports/contains it) before you refactor. This is the single highest-value use.
- **To trace a flow** — `graphify path "<A>" "<B>"` instead of reading the intermediate hops.

`explain`/`path` are surgical (small, precise output). `query` is broader but noisier — for open
questions, not precise lookups.

## What it does not know

The graph is `imports` + `contains` (AST). It does **not** capture runtime coupling — HTTP calls
between services, a shared database table, event/queue flows. Disconnected islands in the graph are
usually this, not a bug. Never treat the graph as complete impact analysis for data/HTTP-coupled
paths: orient with it, then confirm in the real code.

## Freshness

The graph reflects the commit it was built from and goes stale as code changes.
`graphify update .` refreshes it (AST only, no token cost). Automate with the Stop hook
`stop-graphify-refresh.py` (backgrounds the refresh after code-touching turns) — never block a turn
on a rebuild.

## Cost honesty

Building the graph costs **zero LLM tokens** (local AST). In-session it *saves* tokens on
exploration turns (one `explain` vs several file reads) but the aggressive auto-consult hooks *add* a
small per-operation tax. Net-positive on large exploration-heavy repos; on small repos where grep
suffices, keep it on-demand rather than always-on.
