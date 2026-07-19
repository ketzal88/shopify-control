# Security Adapter Guide

This directory contains the agnostic secret-scan patterns and instructions for wiring language-specific SAST tools.

## secret-scan.sh

`core/hooks/scripts/secret-scan.sh` reads `secret-patterns.txt` from this directory. To add project-specific secret patterns (e.g. internal service tokens, custom key formats), append regex lines to `secret-patterns.txt`.

The scanner runs as a **PreToolUse** hook on `git commit`. This is correct — PostToolUse fires after the commit completes, at which point `git diff --cached` is empty.

## security.sast — One-shot SAST scanners

Set `security.sast` in `stack.json` to a shell command for your language's scanner:

| Language | Recommended tool | `security.sast` value |
|---|---|---|
| TypeScript / JavaScript | Semgrep | `semgrep --config auto src/` |
| Python | Bandit | `bandit -r .` |
| Go | Gosec | `gosec ./...` |
| Java | Semgrep | `semgrep --config auto src/` |
| Ruby | Brakeman | `brakeman -q` |
| Multi-language | Semgrep | `semgrep --config auto .` |

Run via `bash core/hooks/scripts/sast-scan.sh` on-demand or in CI.

## security.depAudit — Dependency vulnerability scanning

| Package manager | Tool | `security.depAudit` value |
|---|---|---|
| npm / yarn / pnpm | built-in | `npm audit --audit-level=high` |
| pip | pip-audit | `pip-audit` |
| Go modules | govulncheck | `govulncheck ./...` |
| Maven | OWASP checker | `mvn dependency-check:check` |
| Cargo | cargo-audit | `cargo audit` |

## ratchets.structural — sentrux (NOT SAST)

`ratchets.structural` is **not** a SAST slot. sentrux detects **structural regressions** against a committed baseline — same family as dead-code ratchets. Wire it in `gates.prePush.steps`, not `security.sast`.

Opt in: set `SENTRUX_BIN` env var to the binary path. Skips silently when binary or baseline (`.sentrux/baseline.json`) is absent.
