# Ratchet Philosophy — The Baseline Is the Floor

A ratchet gate enforces that a quality metric never regresses: the count of issues can stay the same or go down, but **never up**.

## The contract

1. **Measure** — run a tool that counts issues (orphan exports, dead code, structural regressions, visual contract violations).
2. **Freeze the baseline** — commit `.<metric>-baseline.json` or equivalent at the current floor.
3. **Block regressions** — at the end of every turn (Stop hook) or before every push (pre-push step), measure again; if the count grew, the gate blocks.
4. **Reward cleanup** — if you deliberately reduce the count, re-run the baseline command to lower the floor.

The gate is **asymmetric**: adding issues is blocked; removing them is rewarded.

## When to add a ratchet

Add a ratchet for any quality metric where:
- You have seen it regress silently before
- The measurement is fast (<60s) and deterministic
- The violation is objective (grep / AST / count), not subjective

## Skip conditions (every ratchet MUST implement these)

- No relevant code changes in the working tree → skip (avoid tool overhead on doc-only turns)
- Baseline file doesn't exist yet → skip (tool not yet adopted)
- Tool binary isn't installed → skip
- Tool crashes or times out → log and skip (never block a turn because of a tooling bug)
- `stop_hook_active=True` in Stop payload → skip (prevent infinite re-trigger)

## Ratchets in this framework

| Ratchet | Trigger | manifest key | Skip condition |
|---|---|---|---|
| Dead code | Stop hook (end of turn) | `ratchets.deadCode` | baseline/tool absent |
| Structural regression | Pre-push step (opt-in) | `ratchets.structural` | binary or baseline absent |

Domain-specific ratchets (design contract, type-annotation count, etc.) are project-specific and live in `examples/<your-project>/` — not in the universal core.

## Manifest declaration

```json
{
  "ratchets": {
    "deadCode": "node scripts/check-dead-code-baseline.js",
    "structural": "sentrux gate",
    "baselineDir": ".sentrux/"
  }
}
```

`deadCode` is a full command that must exit 0 on pass, 1 on genuine regression, and 2 on tooling error. `ratchet-guard.py` only blocks on exit code 1.
