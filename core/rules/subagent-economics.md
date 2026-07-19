# Subagent Economics — the model tier is a decision, not a default

Subagents are usually the single largest line in an agent's bill. Measured on a
real account: **81% of a day's usage and 69% of a week's came from
subagent-heavy sessions.** The session's static overhead — system prompt,
CLAUDE.md, skills — did not appear at all: it is cached at ~10% and barely
registers.

That inverts the usual intuition. Trimming the brain file feels productive and
saves almost nothing. The spend is in **how many agents you spawn and which tier
they run on**.

## Why a subagent is expensive

Each subagent opens its own context window. It pays its own system prompt, its
own tool definitions, and **inherits none of the parent's cache** — it starts
cold and warms a fresh cache from zero (typically on a shorter TTL than the main
conversation). So the cost scales with:

1. **the number of agents**, and
2. **the model tier each one runs on**

Neither scales with how hard the question actually is. A trivial verification in
the top-tier model costs the same as a hard one.

## The rules

**1. Declare the model on every agent definition.** An agent with no `model:` in
its frontmatter inherits the parent's — which is usually the most expensive tier
available. Read-only diagnostics (grep, read, compare numbers, trace a value)
are a cheap-tier job. Reserve the top tier for agents that read source and
reason.

```yaml
---
name: sync-debugger
description: ...
tools: Read, Grep, Glob, Bash
model: sonnet          # <- not optional. Absent = inherits the expensive default.
---
```

**2. In orchestrated workflows, set the tier per stage.** Fan-out multiplies
whatever default you left in place. Mechanical stages — verify, dedup, classify,
extract, count — are cheap-tier work. Only the stages that read code or weigh
evidence need the expensive one. The same applies to reasoning effort: mechanical
stages do not need the default effort level.

**3. Scale the agent count to the question, not to the ambition.** "Is this tool
worth adopting?" does not need 24 adversarial verifiers; 3–5 do. The failure mode
is spawning a fleet because the harness makes it easy, then paying top-tier rates
for work a cheap tier would have done identically.

A real case: **29 agents / 3.7M tokens to evaluate one GitHub tool** — 25% of
that day's entire usage. The deep-reading stages earned their tier. The two dozen
verifiers checking blog-post claims did not: wrong tier, and three times more
agents than the question deserved.

**4. Verbose output belongs in a subagent — that part is real.** The one case
where spawning genuinely saves is isolating a high-volume operation (reading 20
files to return 5 findings): the noise stays in the subagent's window and only
the summary comes back. But it is a *trade*, not free — you pay a cold start and
a fresh system prompt to avoid the noise. Worth it when the discarded output is
large; a loss when the task is small.

## What to watch

The signal is not the size of your brain file. It is:

- **agents spawned per session** × **their tier**
- **session length** — >150k context accounted for 76–82% of usage in the same
  measurement. Clear between unrelated tasks; a stale window is re-read on every
  message.
- **MCP tool results** — they stay in context for the rest of the session. One
  server accounted for 13% of a day. Disconnect what this session does not need.

The README's **Context Layer** covers the other half of this problem: collapsing
a verbose command's output when it passes (`context.filterVerbose`).
