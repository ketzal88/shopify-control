# Context Economics: the window is the bill

Every call re-sends the whole conversation. What you put in the window, you
pay for again on every later turn.

## Why

Measured over two weeks of daily agent work: about 98% of spend was
re-reading context, and most of it came from calls above 200k tokens.
Subagents, tool calls and output tokens were noise next to that. A fresh
session (~65k of system prompt, rules and tool schemas) costs less per call
than a compacted one, which carries the same floor plus its summary.

Two loops made it worse, and both looked like normal work while they ran:

- **Nested brain file larger than the compaction window.** A repo with a
  nested `CLAUDE.md` of ~100k tokens, under a 200k auto-compact window,
  compacted on every turn and wrote nothing.
- **Heavy MCP schemas in the main session.** One ads-platform server loaded
  ~58k tokens of tool schemas per batch. Each compaction reloaded them, the
  session compacted 20 times, and it re-uploaded the same assets three
  times because the summary lost what was already done.

## Rules

1. **One topic per session.** When the work changes subject, write the state
   down (worklog, project note, memory) and start a new session or `/clear`.
   Do not keep going in a window full of the previous task.
2. **Short chat, full deliverables.** Every word of a reply is re-read on
   every later call. Answer first, in one line; skip recaps of what you did.
   The deliverable (code, report, document) keeps the length it needs.
3. **Read the part you need.** Offset/limit or search, not whole files.
   Broad exploration goes to a subagent that returns the conclusion.
4. **Size-check nested brain files.** If a repo's nested `CLAUDE.md` is
   close to the compaction window, raise the window for sessions in that
   repo or split the file. Never run it under a window it cannot fit.
5. **Heavy MCP work goes to a subagent** with a closed brief. The main
   session only reads small results. After a compaction mid-task, first
   read what already exists in the target system before repeating any write.
6. **Keep the always-loaded layer small.** Reference tables (env vars,
   schemas, ID formats, route maps) live in on-demand skills, not in
   `CLAUDE.md` or auto-imported rules. Keep the skill-listing budget
   (`skillListingBudgetFraction`) low; a large listing is tens of thousands
   of tokens on every call.
7. **Browser work:** prefer an accessibility snapshot or a scripted
   evaluate over screenshots. Runs longer than ~10 actions go to a subagent
   so the screenshots stay in its window.

See `subagent-economics.md` for when a subagent pays for itself, and the
README's Context Layer for collapsing verbose command output.
