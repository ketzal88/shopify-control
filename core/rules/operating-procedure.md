# Operating Procedure — Auto-Routing

Claude picks the sequence; the operator does NOT invoke commands manually.

## Step 0 — Triage by size (ALWAYS first)

- **Trivial** — question, read, explanation, 1-2 line change with no logic
  → answer directly. Zero sequence, zero ceremony. No TodoWrite, no planning, no gates. Do it and done.
- **Substantial** — feature, refactor, fix with logic, new UI, data change
  → apply the sequence for the relevant work type below.

Applying ceremony to trivial tasks is the same failure mode as skipping it on substantial ones. The default for a normal conversation is **lightweight**.

## Sequences by work type (only for "substantial" tasks)

| Work type | Claude runs, in order |
|---|---|
| **New non-trivial feature** | Plan inline (1-line assumptions + real A/B/C decisions) → implement → close |
| **UI / frontend change** | Implement → smoke-test the changed surface → announce before closing |
| **New engine or service** | Pure-function contract (no side effects in compute method) + test in the SAME change |
| **Scheduled job / worker** | Auth + idempotency + error handling → update the docs table |
| **Data model change** | Verify field naming, doc ID format, and that the UI reads what the service writes |
| **Threshold / financial value** | Check unit/currency awareness; never hardcode region-specific scales |
| **New storage collection / field** | Optional field + fallback reads + merge-writes; index BEFORE shipping |

## Close — before proposing any commit

Run the self-check from the ratchet-philosophy rule: typecheck clean, no new untyped annotations, no new dead exports. If you touched tested code, run those tests. Claude does this by default — the operator does not need to ask.

## Golden rule

Announce the chosen sequence in **one line** and follow it. The operator watches and can interrupt at any time. When in doubt between lightweight and heavyweight, go lightweight and say what was skipped.
