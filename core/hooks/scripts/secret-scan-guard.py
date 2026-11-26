"""PreToolUse(Bash) guard: run secret-scan.sh before ANY git commit in the command.

EXIT-CODE CONTRACT: Claude Code blocks a tool ONLY on exit 2. Exit 1 is a
non-blocking error and the tool runs anyway. secret-scan.sh exits 1 on a hit,
so this wrapper maps any non-zero scanner exit to 2. (A wrapper that propagated
the 1 blocked nothing for months; tests pin the mapping.)

DETECTION (1.5.0): the commit is found in any segment of the command, with
`cd X &&` and `git -C X` applied (see git_target.py). Until 1.4 only commands
that STARTED with `git commit` were scanned, and `git add -A && git commit`
let a token through to a shared repo.

PENDING MODE: in `git add ... && git commit` (or `git commit -a`) nothing is
staged yet when this hook runs, because the add has not executed. In that case
the scanner runs with SECRET_SCAN_MODE=pending and also inspects unstaged and
untracked files, which is what the add is about to stage.

Missing scanner = setup error, not a secret: the commit is allowed with a loud
message instead of blocking every commit forever.
"""
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import git_target  # noqa: E402

BLOCK = 2  # Claude Code: exit 2 = deny the tool and show stderr to the model
ALLOW = 0


# `git commit` options that take the next word as their value.
COMMIT_OPTS_WITH_VALUE = {
    "-m", "-F", "-C", "-c", "-t", "--message", "--file", "--reuse-message",
    "--reedit-message", "--template", "--author", "--date", "--fixup",
    "--squash", "--cleanup", "--trailer",
}
# Long options known NOT to add anything beyond the index. Anything else
# (--pathspec-from-file, a typo, a future flag) is treated as staging more:
# deny by default, the cost is only a wider scan.
COMMIT_SAFE_LONG = {
    "--quiet", "--verbose", "--signoff", "--no-signoff", "--no-verify",
    "--verify", "--no-edit", "--edit", "--amend", "--allow-empty",
    "--allow-empty-message", "--dry-run", "--short", "--porcelain", "--long",
    "--null", "--status", "--no-status", "--reset-author", "--no-post-rewrite",
    "--gpg-sign", "--no-gpg-sign", "--untracked-files", "--branch",
}
# Short flags known not to stage more (a, i, o and unknown letters do).
COMMIT_SAFE_SHORT = set("qvsneSzu")


def commit_stages_more(args):
    """True if `git commit` itself may pick up more than the index.

    That is -a/--all (also inside a short cluster such as -am), -i/-o/
    --include/--only, any pathspec (a positional word, or anything after
    `--`), and any option this guard does not know. Option values (-m "msg",
    --author x) are skipped, not parsed, so a message cannot hide a later -a.
    """
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            return i + 1 < len(args)
        if a in COMMIT_OPTS_WITH_VALUE:
            i += 2
            continue
        if a.startswith("--"):
            name = a.split("=", 1)[0]
            if name in COMMIT_OPTS_WITH_VALUE or name in COMMIT_SAFE_LONG:
                i += 1
                continue
            return True  # --all, --include, --only, --pathspec-from-file, unknown
        if a.startswith("-") and len(a) > 1:
            flags = a[1:]
            for j, ch in enumerate(flags):
                if "-" + ch in COMMIT_OPTS_WITH_VALUE:
                    # -mmsg carries its value inline; -m alone takes the next word
                    if j == len(flags) - 1:
                        i += 1
                    break
                if ch not in COMMIT_SAFE_SHORT:
                    return True  # a, i, o or a flag we do not know
            i += 1
            continue
        return True  # positional word = pathspec
    return False


def main():
    try:
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except Exception:
        sys.exit(ALLOW)  # unreadable payload: we cannot tell if it is a commit
    if not isinstance(payload, dict):
        sys.exit(ALLOW)
    cmd = ((payload.get("tool_input") or {}).get("command") or "")
    if "commit" not in cmd:
        sys.exit(ALLOW)

    calls = list(git_target.git_calls(cmd, git_target.base_dir(payload)))
    targets = {}  # directory -> mode
    # Any staging call anywhere in the command (add, stage, rm, mv) makes every
    # commit in it a pending scan. Comparing directories is not safe: `git add`
    # in a subfolder and `git commit` at the root are the same repo.
    stages = any(sub in ("add", "stage", "rm", "mv") for sub, _a, _d in calls)
    for sub, args, directory in calls:
        if sub == git_target.OPAQUE:
            # A git call hidden where the parser cannot read it: scan everything.
            targets[directory] = "pending"
        elif sub == "commit":
            pending = stages or commit_stages_more(args)
            if pending or directory not in targets:
                targets[directory] = "pending" if pending else "staged"
    if not targets:
        sys.exit(ALLOW)

    # Resolve the scanner next to THIS file: core/ can live anywhere, and a wrong
    # guess makes bash fail, which would map to BLOCK and deny every commit.
    script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "secret-scan.sh")
    if not os.path.isfile(script):
        print(
            f"secret-scan-guard: scanner not found at {script} - commit ALLOWED "
            f"because this is a setup error, not a detected secret. Fix the install.",
            file=sys.stderr,
        )
        sys.exit(ALLOW)

    for directory, mode in targets.items():
        if not os.path.isdir(directory):
            # The command creates the directory before committing in it, so
            # there is nothing to scan yet. Fail closed: commit in a second call.
            print(f"secret-scan-guard: {directory} does not exist yet, so its "
                  f"commit cannot be scanned. Create it first, then commit in a "
                  f"separate command.", file=sys.stderr)
            sys.exit(BLOCK)
        env = dict(os.environ, SECRET_SCAN_MODE=mode)
        rc = subprocess.call(["bash", script], cwd=directory, env=env)
        if rc != 0:
            print(f"secret-scan-guard: commit in {directory} blocked ({mode} scan).",
                  file=sys.stderr)
            sys.exit(BLOCK)
    sys.exit(ALLOW)


if __name__ == "__main__":
    main()
