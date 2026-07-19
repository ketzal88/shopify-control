# Incident Triage — protocol + living error dictionary

A friction audit of 100+ real sessions found the most frequent operator
workflow was: an error lands in Slack/Sentry/prod logs → the operator
pastes it raw into the chat → the agent re-derives context from zero —
including errors already diagnosed weeks earlier. The signal usually
already lives structured somewhere (an events collection, the host's
log API, the error tracker); what's missing is the reflex and the memory.

## The protocol (when an error is pasted, or "something broke")

1. **Check the dictionary first.** If the error matches a known row, go
   straight to cause + fix — never re-derive a solved diagnosis.
2. **Read the structured signal before speculating**: the project rule
   defines the one command that dumps recent errors + job executions
   (service-account script, log CLI, whatever the stack has). Run it
   BEFORE hypothesizing from the pasted fragment.
3. **Close the loop in the same turn**: every NEW error diagnosed adds
   its row to the project's dictionary — pattern, root cause, fix,
   where to look. The rule is alive or it is useless.

## The dictionary (project-side)

Each project keeps its own table in `.claude/rules/incident-triage.md`:

| Error pattern | Cause | Fix / where to look |
|---|---|---|
| `<provider> 402/403 quota` | metered free tier exhausted | usage dashboard + failover pool config |
| `401 on <integration>` | token revoked/rotated | re-OAuth for the affected account; ping-check cron should have caught it |
| `query requires an index` | missing composite index | index file + deploy command — never the console link |
| interactive-auth error from a CLI | wrong path for this machine | see environment-canonical rule |
| job ran "green" but produced 0 output | idempotency lock already taken, or a filter excluded everything | check the day's lock doc + pipeline filters |

Reference implementation with 11 production rows:
`examples/nextjs-firebase/rules/incident-triage.md`.

## The upstream fix

Triage-by-paste is a symptom. The audit's structural lesson: **every
system with an idempotency lock also needs the inverse check ("it ran
but produced nothing") and every metered external resource needs a
preventive quota/validity watchdog** — otherwise the operator IS the
monitoring system. Build the watchdog once the same paste arrives twice.
