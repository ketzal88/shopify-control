# Security Gates — Universal Security Layer

Four named security gates, all driven by `stack.json`. The gate logic is universal; only the tool command is per-project.

## Gate 1: Secret Scan (blocking, pre-commit)

Runs `security.secretScan` from the manifest before every `git commit`.

**Must be `PreToolUse`, NOT `PostToolUse`.** PostToolUse fires after the commit completes — at that point `git diff --cached` is empty and staged secrets can no longer be caught. The hook must intercept the commit BEFORE it happens.

Default: `core/hooks/scripts/secret-scan.sh` + `core/security/secret-patterns.txt`. Checks:
1. Filenames — blocks `.env*`, `*credentials*`, `*secret*` files (except `.md`)
2. Staged diff content — PEM keys, cloud access key IDs, service tokens, API key assignments

Add project-specific patterns to `secret-patterns.txt`.

Since 1.5.0:
- **The commit is found anywhere in the command**: `a && git commit`, `cd repo && git commit`, `git -C repo commit` (parsed by `git_target.py`). Before, only commands that started with `git commit` were scanned, and `git add -A && git commit` let a token through.
- **Pending mode**: in `git add ... && git commit` or `git commit -a`, nothing is staged yet when the hook runs, so the scan also covers unstaged and untracked files.
- **Only added lines are scanned**: a commit that deletes a secret never blocks. Templates such as `.env.example` are allowed.
- **False positives**: add `secret-scan:allow` on the line and say why in the commit message. A gate without a documented exception gets bypassed by habit.
- Use fake tokens in tests and smokes, never real ones.

## Gate 2: Pre-Push Guard (blocking)

Runs before every `git push`. **Blocking — exits 2 on failure, preventing the push.**

Reads `gates.prePush.steps` and resolves each step to a command from `commands.*` or `ratchets.*`. The guard script itself contains **zero language-specific tool names** — only the manifest does.

All steps run regardless of individual failures (mirrors CI's `if: always()` behavior), so the full list of problems is visible in one pass.

`SKIP_PREPUSH=1` bypass: accepted ONLY when ALL changed files match docs/config patterns (`.md`, `.claude/`, `docs/`, `.gitignore`). Rejected for any code changes.

Since 1.5.0 the push is found inside compound commands (`cd repo && git push`, `git -C repo push`), and `gates.pushWrappers` lists regexes for project scripts that push for you (a release script, an npm script that pushes several repos): the push policy applies to them like to a literal `git push`. Output compressors and command wrappers must never wrap `git push`: they hide the gate's output and exit code. See `headless-automation.md`.

## Gate 3: Structural Ratchet (pre-push step, opt-in)

`ratchets.structural` is a **pre-push step** — it runs inside the pre-push guard as one of the entries in `gates.prePush.steps`. The reference implementation is `sentrux gate`, which diffs the current structure against a baseline.

**This is NOT a one-shot SAST scanner.** It is a structural-regression ratchet: same family as dead-code ratchets. Wire it in `gates.prePush.steps`; leave `security.sast` empty unless you also want a one-shot scanner.

Opt-in via `SENTRUX_BIN` env var. **Skips silently when the binary or baseline is absent** — zero friction for teams that haven't adopted it.

## Gate 4: SAST + Dep-Audit (configurable)

`security.sast` and `security.depAudit` run the specified command. Empty value = gate skipped. Wire them into CI or as on-demand slash commands.

See `core/security/README.md` for recommended tools by language.

## Summary table

| Gate | Trigger | Hook type | Blocking? | manifest key |
|---|---|---|---|---|
| Secret scan | `git commit` | **PreToolUse** | **✅ Blocking** | `security.secretScan` |
| Pre-push guard | `git push` | **PreToolUse** | **✅ Blocking** | `gates.prePush` |
| Structural ratchet | pre-push step | (inside guard) | **✅ Blocks push** | `ratchets.structural` |
| SAST | on-demand / CI | — | configurable | `security.sast` |
| Dep-audit | on-demand / CI | — | configurable | `security.depAudit` |
