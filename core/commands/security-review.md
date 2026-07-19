---
description: Guided security review of a change — run the config-driven triage, then read your stack's security references, and report findings by severity
---

A change-level security review. The deterministic triage is driven by `stack.json`; the judgement is yours. Complements the automated security **gates** (secret-scan, SAST, dep-audit) — this is the guided, AI/human review the gates can't do.

## Steps

1. **Scope.** `git diff main...HEAD --stat`, or the named files. Review a *change*, not the whole repo (unless asked).
2. **Triage (first pass).** Run:
   ```bash
   bash core/hooks/scripts/security-triage.sh
   ```
   It reads `security.review.*` from `stack.json` and runs the deterministic checks (cron-secret coverage, client-bundle secret exposure, tenant routes without an auth signal). Each hit is a **candidate, not a verdict** — read the code for each. Checks whose config key is absent skip silently.
3. **Read by category.** For each changed file, read your stack's security references before judging. If the repo ships a `security-review` skill with stack-specific patterns (e.g. `examples/nextjs-firebase/.claude/skills/security-review/` for Next.js + Firebase), use it.
4. **Report.** One finding per issue: severity + location `file:line` + what happens + fix. Sort by severity. If nothing is found, say so — don't invent findings.

## Severity → action SLA

| Severity | Means | Action |
|---|---|---|
| **Critical** | Exploitable now / cross-tenant data leak / exposed secret | **Fix before merge** |
| **High** | Real risk under specific conditions | Fix in same change or the next |
| **Medium** | Hardening, bounded impact | Fix soon, non-blocking |
| **Low** | Consistency / defense in depth | Fix when convenient |

## Finding format

```
### [Critical] IDOR: route accepts tenantId without an access check
- Location: app/api/foo/route.ts:24
- What happens: reads tenantId from the query and reads data without verifying access →
  any user swaps the id and reads another tenant's data
- Fix: authenticate the session, then verify tenant access before the read
```

## The fact worth internalizing

When your auth is verified by a runtime the edge/middleware layer can't reach — e.g. **Next.js
middleware cannot verify a Firebase session** (it needs the Admin SDK, which is Node-only and doesn't
run in Edge) — **the middleware cannot protect your API routes**. Each handler must authenticate AND
authorize itself. This is the #1 source of cross-tenant IDOR in these stacks.

## stack.json keys (all optional — absent = that check skipped)

```jsonc
"security": {
  "review": {
    "apiDir":        "src/app/api",                 // where route handlers live (default: src/app/api | app/api)
    "tenantParam":   "clientId|tenantId|orgId",      // regex of tenant-id param names your routes use
    "authSignals":   "getUser|requireAuth|session",  // regex of tokens that prove a route does auth
    "cronCheck":       "CRON_SECRET",                // regex proving a cron route checks its secret
    "publicEnvPrefix": "NEXT_PUBLIC_",               // client-bundle env prefix (VITE_ / PUBLIC_ for other stacks)
    "publicEnvAllow":  "FIREBASE"                    // known-public names to exclude (Firebase web config is public)
  }
}
```
