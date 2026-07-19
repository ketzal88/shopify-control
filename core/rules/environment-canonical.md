# Canonical Environment — one true path per operation, enforced

Every dev machine has commands that ALWAYS fail on it (a global linter
that expects a config format the repo doesn't use, an interactive CLI
login that dies headless, a tool that simply isn't installed) — and a
canonical path that always works. A friction audit of 100+ real sessions
found the agent re-picking the broken path in ~20% of sessions, burning
1-3 turns each time, sometimes cutting a debug in half.

## The pattern

1. **Maintain a two-column table in a project rule**: "ALWAYS USE" vs
   "NEVER USE (why)". One row per operation: lint, DB access, deploy,
   JSON-in-shell, multiline commits, shell dialect quirks.
2. **Enforce the top offenders with the canonical-guard hook** —
   `core/hooks/scripts/canonical-guard.py` reads
   `environment.forbiddenCommands` from `stack.json`:

```json
"environment": {
  "forbiddenCommands": [
    { "pattern": "(^|[;&|]\\s*)(npx\\s+)?eslint\\b",
      "fix": "Use `npm run lint` — global ESLint 9 fails without eslint.config" },
    { "pattern": "\\bsome-cli\\s+login\\b",
      "fix": "Interactive login dies headless. Use the service-account script instead." }
  ]
}
```

   Blocked command → exit 2 with the exact correction in the message →
   the agent self-fixes in 0 turns instead of retrying variants.
3. **The rule is alive**: every NEW environment gotcha diagnosed in a
   session gets its table row (and, if frequent, its config pattern) in
   the same turn.

## Rules of thumb for what goes in the table

- Anything that fails with interactive-auth, missing-config or
  command-not-found errors → don't retry variants, add the row.
- Shell dialect mismatches (PowerShell cmdlets in a POSIX shell and
  vice versa) are the highest-frequency offender on Windows machines.
- Precision over recall in `forbiddenCommands` patterns: the guard
  BLOCKS, so a false positive costs more than a miss. Anchor patterns to
  command position where possible. The long tail stays in the table as
  prose.

Reference implementation: `examples/nextjs-firebase/rules/windows-environment.md`.
