---
description: Review staged changes, run all quality gates, then commit safely
---

Perform a safe commit checkpoint. Goal: only commit code that would pass CI.

Steps:
1. Run `git status` and `git diff --stat` to see what's changed.

2. If a lint auto-fix is available (check `commands.lint`), run it with the tool's auto-fix flag. Note which files changed.

3. Run typecheck (`commands.typecheck` from `stack.json`) — **STOP** if it fails.

4. Run tests (`commands.test` from `stack.json`) — **STOP** if they fail.

5. Run lint (`commands.lint`) — **STOP** if there are unfixed errors.

6. If a dead-code ratchet is configured (`ratchets.deadCode`), run it — **STOP** if the orphan count grew.

7. Show the diff summary and propose a commit message. Scan `git log --oneline -10` to match the project's existing style.

8. Wait for user confirmation.

9. On confirmation:
   - Stage specific files (NEVER `git add -A`).
   - Commit with HEREDOC message.
   - Run `git status` to verify.

Safety:
- Never `--amend` without explicit instruction.
- Never `--no-verify`.
- Never include `.env*`, `*credentials*`, `*secret*` files.
- `SKIP_PREPUSH=1` only when ALL changed files are docs/config (no code changes).
- If the pre-commit hook fails, fix and create a **NEW** commit (not amend).
