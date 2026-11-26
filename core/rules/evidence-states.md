# Evidence States: say how true it is

Every claim in a final report carries one of six states. "Done" is not a
state; it is a conclusion that needs evidence.

## Why

The expensive failures were not wrong code. They were true-sounding reports:
a scheduled job that ran 96 times a day for twelve days, every run a 401,
reported as "configured and running". Each step before it was real: the job
was configured, it executed. The broken link was between **executed** and
**had the intended effect**, and nobody looked at the destination.

## The six states

| State | Meaning | Evidence needed |
|---|---|---|
| **not verified** | You believe it, you did not check | None. Say so. |
| **configured** | The setting, file or job exists | You read it back |
| **executed** | The command or job ran | Exit code, log line, run record |
| **had effect** | The destination changed as intended | You looked at the destination |
| **outcome unknown** | It ran, the result is unreadable | Say what you could not read |
| **failed** | It ran and did not work | The error, verbatim |

## Rules

1. **Name the state and where you looked.** "Executed (exit 0), effect not
   verified" is a complete, honest report. "Done" without a source is not.
2. **Verify in the destination, not in the tool.** A 200 from an API, a
   commit hash, a "published" message: those are *executed*. *Had effect*
   means reading the record back from the system that should now hold it,
   ideally from outside the environment that made the change.
3. **Unknown outcome: look, do not retry.** If a write timed out or returned
   something unreadable, check the destination before retrying. Blind
   retries duplicate messages, uploads and charges.
4. **"Does not exist" is a claim too.** Before saying something is missing,
   not configured or not ranking, check. If you cannot, write "could not
   verify", which is a valid state.
5. **Never invent a number.** A metric that did not come from a source you
   read in this session does not go in the report.
6. **Advisory gates print what they inspected.** A non-blocking check that
   prints nothing is indistinguishable from one that never ran. Every
   advisory gate prints "N inspected" and has a canary: a fixture it must
   flag, run once to see it fail. (A real advisory gate ran in CI for months
   over zero files because of a path-prefix mismatch.)

The close status line in `close-protocol.md` is the git-shaped instance of
this rule: it reports a commit sha, not "committed".
