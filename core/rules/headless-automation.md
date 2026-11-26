# Headless Automation: no human, no excuses

Child sessions (`claude -p`, dispatch scripts), scheduled jobs and hooks run
with nobody watching. Their failures are silent by default, so the guard
rails have to be built in, not assumed.

## Why

- A scheduled agent job ran for about a day without doing anything: the
  CLI login had expired, the process exited 1 with an **empty stderr**, and
  the real error sat in the JSON on stdout (`is_error: true`). The loop
  around it looked healthy.
- Hooks written as inline `python -c "..."` in settings died on Windows
  (four layers of quoting between JSON, the shell and Python) and stayed
  dead for weeks. Nobody noticed, because a dead hook blocks nothing.
- File content interpolated into a shell string (`node -e "..."` with
  backticks inside) executed a seed script against production.

## Rules for child sessions

1. **Explicit deny list:** `git push`, deploy CLIs, `gh`, `reset --hard`,
   and generic interpreters (`node -e`, `python`, `npx tsx`), which bypass
   any command-level deny.
2. **Stripped environment:** remove every `*TOKEN*`, `*SECRET*`, `*KEY*`
   variable and give git no credentials (`GIT_ASKPASS=echo`), so a push
   fails even if it slips past the list.
3. **Closed brief:** what to change, constraints, how to verify. One command
   per call, no `cd` chains or redirects (prefix allowlists break on them).
4. **Verify after the run, independently of the child's summary:** new
   commits, files left dirty, remote refs unchanged, permissions denied.
   Review the diff of the first run in any real repo.

## Rules for scheduled jobs

5. **Authenticate explicitly.** Point the job at the right config directory
   or a long-lived token loaded from an env var outside any repo; never rely
   on an interactive login staying valid.
6. **Check the structured result, not only the exit code,** and alert on
   failure. A job that cannot report failure will fail quietly.

## Rules for hooks and shell

7. **Hooks are script files,** invoked in `args` form, never inline
   `python -c`. Background workers spawn the script itself with a flag.
   Pipe-test every hook with a synthetic payload before calling it live.
8. **Write files with the file-writing tool,** never by interpolating their
   content into a shell string or a long heredoc.
9. **Output compressors never wrap `git push`** (or `git -C ... push`).
   They swallow the hook output and exit code the push gate depends on.
10. **Concurrent sessions on one checkout:** `git add` by path, never `-A`;
    another session's dirty files are not yours to commit or report.

See `evidence-states.md` for how to report what a headless run actually did.
