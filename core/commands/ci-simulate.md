---
description: Run all CI gate commands locally in order, reporting all failures at once
---

Run the full CI gate sequence from `stack.json` locally, mirroring CI's "always run all steps" behavior.

Steps:
1. Read `gates.prePush.steps` from `stack.json`. For each step, resolve the command from `commands.<step>` or `ratchets.<step>`.
2. Run all steps in order, capturing output. **Continue even if a step fails** (mirrors CI `if: always()`).
3. Report:
   - ✅ PASS / ❌ FAIL for each step
   - For failures: full output + what fix to apply
   - If all pass: "CI-ready — safe to push"

If `language` is a JVM or Node.js language, set `NODE_OPTIONS=--max-old-space-size=6144` to mirror CI memory settings.

This is the same logic as the pre-push guard but run on-demand with full output instead of blocking.
