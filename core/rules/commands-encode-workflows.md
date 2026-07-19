# Commands Encode Workflows

Multi-step processes become one-line slash commands. This is the principle behind every `.claude/commands/*.md` file.

## Why commands exist

The operating procedure routes Claude to run certain steps for certain work types. Commands are the *implementation* of those steps — not buttons a human has to remember to press. The auto-router decides which command to invoke; the human watches the methodology happen and interrupts when they want.

## Command anatomy

```markdown
---
description: One-line description shown in /help
argument-hint: [optional] [--flags] <required>
---

Context for Claude about what this command does.

Steps:
1. Specific step with exact shell command
2. Parse and report
3. Safety checks

Never <thing that would be dangerous>.
```

## Design principles

- **Diagnostic by default.** Commands report; they don't fix unless explicitly asked.
- **Safety rails built in.** `/commit-checkpoint` blocks on test failures; domain commands block on irreversible operations.
- **Each command references the rules it enforces.** The command is the entry point; the rule is the contract.
- **Plain markdown.** No build step, no template engine — a command file is just text Claude reads.

## Core commands

| Command | Purpose |
|---|---|
| `/typecheck` | Run `commands.typecheck` and report errors |
| `/ci-simulate` | Run all `gates.prePush.steps` locally with full output |
| `/commit-checkpoint` | Lint → tests → ratchets → propose message → commit |
| `/env-check` | Validate env vars vs CLAUDE.md documentation |

## Adding domain commands

Domain-specific commands (e.g., `/test-alerts`, `/deploy-indexes`, `/audit-parity`) belong in `examples/<your-project>/commands/`. They follow the same anatomy and reference project-specific rules and tools.

Rule of thumb: when you run the same 3 commands in sequence more than twice, make it a slash command.
