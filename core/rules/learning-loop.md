# Learning Loop — persistent memory that actually persists

Gates stop regressions; a learning loop stops *repetition*. Both are
needed. These are the three lessons from running a dual learning system
in production for months (one loop worked brilliantly, the other failed
silently for 80 days).

## 1. Project memory with an index (the loop that works)

One file per fact, in a per-project memory directory, with a single
index file loaded into context every session:

- `memory/MEMORY.md` — one line per memory (`- [title](file.md) — hook`).
  Never put content in the index; it is a table of contents.
- `memory/<slug>.md` — one fact each, typed: operator preferences,
  corrections with the *why*, project state, external references.
- Write a memory when the operator corrects the same thing twice, when a
  gotcha costs more than a turn, or when project state isn't derivable
  from the repo. Update in place; delete when wrong.

This works because retrieval is cheap (the index is small), writes are
immediate (same session, no batch job), and the operator can read/prune
it like any other file.

## 2. Verify every headless automation writes (the loop that failed)

An automated "reflection" job (cron/hook that analyzes past sessions and
writes rules) ran for **80 days without persisting a single rule** —
its file writes were silently blocked by permissions in headless mode,
and an empty `catch {}` swallowed every failure. Nobody noticed because
the system that learns had no monitoring of itself.

Non-negotiables for any headless automation that writes:

1. **Pre-create the target files/dirs** in the wrapper (permission
   prompts for *new* files behave differently than for existing ones).
2. **Grant explicit permission rules** for the target paths in
   settings (`Write(<path>/**)`) — headless runs have no human to approve.
3. **Verify post-run**: compare mtime/size before and after. If nothing
   changed, append one line to a visible run log with the captured
   stderr. An empty catch block on a learning system is how you lose
   80 days of signal.
4. **Smoke-test once manually** and check the run log the next day.

## 3. Prose rules don't enforce themselves — audit compliance

Written rules ("always run the browser check before delivering UI")
show near-zero compliance after a few weeks; blocking hooks show 100%.
Periodically audit your own session history: cluster the friction,
check which existing rules were violated repeatedly, and promote those
rules to deterministic gates (see close-protocol and
environment-canonical for two rules that made that jump). The memory
system captures the lesson; the gate enforces it.
