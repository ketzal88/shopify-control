# Close Protocol — how every substantial turn must end

From a friction audit of 100+ real production sessions: the single most
common end-of-session pattern was the operator chasing the agent with
"did you commit?", and the agent retrying `git push` against an
intentional deny — burning turns on a push that was never going to
happen. The close was prose; this rule makes it protocol, and two hooks
enforce it deterministically.

## The protocol (agent-side, every substantial turn)

1. **Run the quality self-check** (ratchets, typecheck, tests for what you
   touched) — via the project's commit-checkpoint command.
2. **Commit without being asked.** Never end a turn with a dirty working
   tree silently. If the dirt is deliberate WIP or another session's debt,
   say so explicitly (which files, why) in the final message.
3. **Always end the final message with a git status line:**
   `committed: <short sha> — N commit(s) ready to push`
   (or `no code changes`). A non-developer operator needs exactly this
   line — nothing more — to decide when to push.
4. **Never run `git push` or attempt bypasses** (`--no-verify`,
   skip-flags for code changes). Pushing belongs to the operator, always.
   The only exception: the operator explicitly asks in chat →
   `ALLOW_CLAUDE_PUSH=1 git push ...` (runs the full check suite first).

## Enforcement (hooks)

| Hook | Trigger | Config key (stack.json) |
|---|---|---|
| `core/hooks/scripts/pre-push-guard.py` | any `git push` from the agent | `gates.push: "operator-only"` |
| `core/hooks/scripts/close-guard.py` | Stop with uncommitted code files | `gates.closeProtocol: "blocking"` |
| `core/hooks/scripts/close-guard.py` | Stop with commits never pushed (optional) | `gates.closeUnpushed: "report"` |

Both follow the framework convention: absent key = silent no-op. The
close-guard blocks exactly ONCE per close (`stop_hook_active` breaks the
loop) — it is a reminder with teeth, not a wall.

## Session scope (1.5.0)

Several sessions often share one checkout. The close-guard only blocks on
files **this session** edited, wrote, committed or named in its shell
commands (read from the transcript via `session_files.py`). Other sessions'
dirty files are reported as a count, never as yours:

- `git add` the paths you changed **by name**. Never `git add -A` or `.`:
  it sweeps another session's work into your commit.
- Do not list another session's WIP in your final message.
- If the transcript is unreadable, the guard falls back to the whole tree
  (it never fails open).
- Repos nested one level down are checked too, and commits ahead of
  upstream are reported so the operator knows what is waiting to push.
- With `gates.closeUnpushed: "report"` (1.5.3), unpushed commits alone
  trigger the reminder, even on a clean tree. The agent does not push
  them (unless the push policy allows it); it names each repo and its
  count in the final message.

## One policy for nested repos (1.5.3)

A push can target a nested repo with its own `stack.json`. The root
manifest is the floor: a nested manifest can tighten the push policy for
its repo, never loosen it. Every target of a compound command
(`git push && git -C sub push`, `--git-dir`, `--work-tree`) is checked,
not only the first. A nested manifest without `prePush.steps` inherits
the root's steps.

## Why hooks and not prose

The same audit showed that written rules ("always commit before
closing") had near-zero compliance over weeks, while blocking hooks
(ratchets, secret-scan) had 100%. Any close-critical behavior must live
in a deterministic gate; the prose exists to explain the gate.
