<!-- fill me: replace all {{placeholders}} in this file once, then delete this comment -->
<!-- fill me: stack name, primary language, source root -->
<!-- fill me: 3-5 architectural patterns that Claude must always know -->

# {{Project Name}} — Claude Brain

## Stack

- **Language**: {{language, e.g. TypeScript 5, Python 3.12, Java 21}}
- **Package manager**: {{packageManager, e.g. npm, pip, maven}}
- **Source root**: {{source root, e.g. src/}}
- **Primary framework**: {{framework, e.g. Next.js 14, FastAPI, Spring Boot}}
- **Infra**: {{infra, e.g. Vercel + Firebase, AWS Lambda + RDS, GCP Cloud Run}}

## Modular Rules

@.claude/core/rules/operating-procedure.md
<!-- Add domain-specific rules here using @-syntax: -->
<!-- @.claude/rules/<your-rule>.md -->
<!-- Keep this list short. Every @-import is loaded on EVERY session, so it is paid
     for whether or not the turn needs it. Import a rule only if an agent would get
     it wrong by default — environment facts, domain semantics, conventions it cannot
     infer. Anything a blocking hook already catches does not belong here: the hook
     delivers the correction at the exact moment of the mistake, with the fix inline.
     Target: under 600 words of always-loaded context. -->
<!-- The other core rules live in .claude/core/rules/ and are read on demand. -->

## Environment Variables

<!-- Document required env vars so /env-check can audit them. -->
<!-- Never put actual values here — names and purpose only. -->

| Var | Purpose | Required |
|---|---|---|
| `{{VAR_NAME}}` | {{description}} | Yes |

## Architecture Patterns

<!-- Document the 3-5 patterns everything follows. Examples: -->

### {{Pattern 1 Name}}

{{One paragraph explaining the invariant and why it exists.}}

### {{Pattern 2 Name}}

{{One paragraph.}}

## Testing

```bash
# Typecheck
{{commands.typecheck from stack.json}}

# Unit tests
{{commands.test from stack.json}}

# Lint
{{commands.lint from stack.json}}
```

## Reference Tables

<!-- Optional: alert types, scheduled jobs, API routes, database collections. -->
<!-- Tables help Claude answer "what's the list of X?" without reading all source files. -->

## Notes for Claude

<!-- Things Claude must know that aren't in the code or other rules: -->
<!-- - Domain-specific invariants -->
<!-- - Known gotchas / historical bugs to avoid repeating -->
<!-- - Performance or cost constraints -->
