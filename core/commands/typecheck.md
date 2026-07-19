---
description: Run the typecheck gate and report errors
---

Run the typecheck command from `stack.json` and report results.

Steps:
1. Read `commands.typecheck` from `stack.json`. If absent, report "typecheck not configured in stack.json" and stop.
2. Run the command:
   ```bash
   $TYPECHECK_CMD 2>&1
   ```
3. Report:
   - **Zero errors** → "✅ Clean (0 errors)".
   - **Any errors** → group by file, show file:line with 1-sentence diagnosis per error.
4. Do NOT fix anything unless explicitly asked.

Note: this command is diagnostic only. The pre-push guard runs the same check automatically before every push.
