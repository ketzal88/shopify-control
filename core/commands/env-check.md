---
description: Validate that env vars documented in CLAUDE.md exist in the local environment file
---

Validate environment variable completeness against the documented list.

Steps:
1. Extract the env-var table from `CLAUDE.md` (look for a section named "Environment Variables" or similar).
2. Read `.env.local` (or `.env`, `.env.development` — whichever the project uses) and list the keys defined.
3. Produce a table:
   | Var | Documented | In local env | Notes |
   |---|---|---|---|
   | `DATABASE_URL` | ✅ | ✅ | |
   | `API_KEY` | ✅ | ❌ | Required for X feature |

4. Highlight:
   - **Missing locally** — would cause runtime errors
   - **Present but undocumented** — consider adding to CLAUDE.md or removing if unused
   - **Placeholder values** — anything matching `TODO|REPLACE_ME|xxx|your_*`

5. For missing required vars, show where they're used:
   ```bash
   grep -rn "<VAR>" src/ -l
   ```

Never print actual values — only var names and presence booleans.
