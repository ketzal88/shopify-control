#!/usr/bin/env python3
"""PreToolUse hook: blocks `git push` until manifest gates pass.

Reads gates.prePush.steps from stack.json. For each step, resolves the
command from commands.<step> or ratchets.<step>. Absent key = step skipped.

All steps run regardless of individual failures (mirrors CI if:always()).

SKIP_PREPUSH=1 allowed only when ALL changed files match CI_PATHS_IGNORE.

1.5.0 - DETECTION: the push is found in any segment of the command
(`cd x && git push`, `git -C x push`, `npm test && git push`), not only when
the command starts with `git push`; the checks run in the directory the push
targets. gates.pushWrappers (array of regexes) names project scripts that push
on your behalf (e.g. "npm run (ship|release)"): they are treated as a push,
so the operator-only policy cannot be dodged by calling the wrapper.

1.5.3 - ONE POLICY ACROSS NESTED REPOS: every push target is checked, not
only the first, and the project root manifest is the floor (a nested
stack.json can tighten gates.push, never loosen it). Steps run per target;
a target whose manifest lists none inherits the root's.

1.5.5 - PARSER HOLES CLOSED: `! git push`, `if git push; then`, git aliases
(`-c alias.p=push p` and aliases in config) and `-n --no-dry-run` (the last
flag wins) no longer slip past the policy.

1.5.6 - ALIASES FAIL CLOSED: an alias that the same command could (re)define
(`git config`, GIT_CONFIG_*, --config-env, HOME=) or that cannot be resolved
is OPAQUE, which this guard counts as a push.

Input contract (stdin JSON from Claude Code harness):
    { "tool_input": { "command": "git push ..." }, ... }
"""
import json
import os
import re
import subprocess
import sys
import time

TIMEOUT_SEC = int(os.environ.get("PREPUSH_TIMEOUT", "300"))
TAIL_LINES = 40
CI_PATHS_IGNORE = [
    r"\.md$",
    r"^\.claude/",
    r"^docs/",
    r"^\.gitignore$",
    r"^\.gitattributes$",
]

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
READ_CONFIG = os.path.join(SCRIPT_DIR, "read-config.py")
sys.path.insert(0, SCRIPT_DIR)
import git_target  # noqa: E402


def cfg(key, repo=None):
    """Read a dotted key from stack.json via read-config.py.

    `repo` is the directory to search upward from. The caller always checks
    the project root too: a nested manifest adds gates, it never removes them.
    """
    try:
        r = subprocess.run(
            [sys.executable, READ_CONFIG, key],
            capture_output=True, text=True, timeout=5, cwd=repo or None,
        )
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception:
        return None


def changed_files(cwd=None):
    for args in [
        ["git", "diff", "--name-only", "origin/main...HEAD"],
        ["git", "diff", "--name-only", "HEAD~1"],
    ]:
        try:
            r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                return r.stdout.strip().splitlines()
        except Exception:
            pass
    return []


def all_docs_only(files):
    if not files:
        return False
    return all(any(re.search(p, f) for p in CI_PATHS_IGNORE) for f in files)


def tail(text, n):
    lines = text.splitlines()
    return lines[-n:] if len(lines) > n else lines


# `git push` options that take the next word as their value.
PUSH_OPTS_WITH_VALUE = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}


def is_dry_run(args):
    """True only for a real -n/--dry-run flag, not a word that is an option value.

    The last flag wins, like git's own parser: `-n --no-dry-run` is a real push.
    """
    dry = False
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--":
            break
        if a in PUSH_OPTS_WITH_VALUE:
            i += 2
            continue
        if a == "--dry-run":
            dry = True
        elif a == "--no-dry-run":
            dry = False
        elif a.startswith("-") and not a.startswith("--") and len(a) > 1:
            for ch in a[1:]:
                if ch == "n":
                    dry = True
                if ch == "o":
                    break  # -oVALUE: the rest is the value
        i += 1
    return dry


def parse_steps(raw):
    if not raw:
        return []
    try:
        steps = json.loads(raw)
        return steps if isinstance(steps, list) else [str(steps)]
    except Exception:
        return [s.strip() for s in raw.split(",") if s.strip()]


def main():
    try:
        payload = json.loads(sys.stdin.read().lstrip("\ufeff"))
    except Exception:
        return 0
    if not isinstance(payload, dict):
        return 0

    push_cmd = (payload.get("tool_input", {}) or {}).get("command", "") or ""
    if not push_cmd:
        return 0

    pushes = git_target.find(push_cmd, git_target.base_dir(payload), "push")
    real = [(a, d) for a, d in pushes if not is_dry_run(a)]
    # git hidden where the parser cannot see (a shell string too deep, a
    # `-c alias.*`, a shell alias): assume a push. 1.5.5 dropped the old
    # `"push" in cmd` condition, since an alias from config never names it.
    real += [([], d) for d in git_target.opaque(push_cmd, git_target.base_dir(payload))]
    wrapper = None
    wrappers_raw = None if real else cfg("gates.pushWrappers")
    if wrappers_raw:
        try:
            wrappers = json.loads(wrappers_raw)
        except Exception:
            wrappers = []
        for rx in wrappers if isinstance(wrappers, list) else []:
            try:
                if re.search(rx, push_cmd):
                    wrapper = rx
                    break
            except re.error:
                continue  # malformed pattern in config: never block on config bugs
    if not real and not wrapper:
        return 0
    # Every distinct directory the command pushes from, plus the project root.
    # The root manifest is the floor: a stack.json found under a push target
    # can TIGHTEN the policy for that repo, never loosen it (1.5.3; 1.5.2 read
    # only the first target's manifest, so a nested `{"gates": {}}` dropped
    # operator-only and the second push of `git push && git -C x push` was
    # never looked at).
    project = os.environ.get("CLAUDE_PROJECT_DIR") or git_target.base_dir(payload)
    targets = []
    for d in [d for _a, d in real] or [git_target.base_dir(payload)]:
        d = d if os.path.isdir(d) else None
        if d not in targets:
            targets.append(d)
    policy_dirs = [project] + [d for d in targets if d]

    # -- Push policy (close-protocol) -------------------------------------
    # gates.push = "operator-only" in stack.json => the agent NEVER pushes:
    # every `git push` (including --no-verify - that was the bypass agents
    # kept trying) blocks instantly with the correct close instruction,
    # BEFORE burning minutes of checks on a push the operator will do by
    # hand anyway. Explicit exception: ALLOW_CLAUDE_PUSH=1 (operator asked
    # in chat) -> the full check suite below runs before allowing it.
    if any(cfg("gates.push", d) == "operator-only" for d in policy_dirs):
        allow = os.environ.get("ALLOW_CLAUDE_PUSH") == "1" or "ALLOW_CLAUDE_PUSH=1" in push_cmd
        if not allow:
            sys.stderr.write(
                "[close-protocol] git push blocked: pushing belongs to the operator.\n"
                "  Do not retry or use bypasses (--no-verify / SKIP_PREPUSH).\n"
                "  Correct close: commit locally and end your message with\n"
                "  'committed: <short sha> - N commit(s) ready to push'.\n"
                "  If the operator explicitly asked you to push: ALLOW_CLAUDE_PUSH=1 git push ...\n"
            )
            return 2

    if "--no-verify" in push_cmd or (wrapper and not real):
        return 0  # a wrapper runs its own checks; the policy above is what matters

    if os.environ.get("SKIP_PREPUSH") == "1":
        if all(all_docs_only(changed_files(d)) for d in targets):
            return 0
        sys.stderr.write(
            "[pre-push] SKIP_PREPUSH=1 rejected: changed files include code.\n"
            "  Only allowed when ALL changes are docs/config (CI paths-ignore).\n"
        )
        return 2

    # Resolve steps per target. A target whose own manifest lists no steps
    # inherits the project's: an empty nested manifest must not skip them.
    checks = []
    for target_dir in targets:
        steps = parse_steps(cfg("gates.prePush.steps", target_dir))
        cfg_dir = target_dir
        if not steps:
            steps, cfg_dir = parse_steps(cfg("gates.prePush.steps", project)), project
        for step in steps:
            cmd_val = cfg(f"commands.{step}", cfg_dir) or cfg(f"ratchets.{step}", cfg_dir)
            if cmd_val:
                label = step if len(targets) == 1 else f"{step} @ {os.path.basename(target_dir or project)}"
                checks.append((label, cmd_val, target_dir))

    if not checks:
        return 0

    failures = []
    remaining = TIMEOUT_SEC

    for name, check_cmd, target_dir in checks:
        if remaining <= 2:
            failures.append((name, "skipped (budget exhausted)", ""))
            continue
        start = time.monotonic()
        env = {**os.environ, "NODE_OPTIONS": "--max-old-space-size=6144"}
        try:
            r = subprocess.run(
                ["bash", "-c", check_cmd], cwd=target_dir,
                capture_output=True, text=True,
                encoding="utf-8", errors="replace",
                timeout=remaining, env=env,
            )
        except subprocess.TimeoutExpired:
            failures.append((name, "timed out", ""))
            remaining = 0
            continue
        except FileNotFoundError:
            sys.stderr.write("[pre-push] bash not found - skipping guard.\n")
            return 0
        elapsed = time.monotonic() - start
        remaining = max(0, int(remaining - elapsed))
        if r.returncode != 0:
            out = (r.stdout or "") + ("\n" + r.stderr if r.stderr else "")
            failures.append((name, f"exit {r.returncode}", out))

    if not failures:
        return 0

    sys.stderr.write(f"[pre-push] {len(failures)} check(s) failed - blocking push:\n\n")
    for name, status, output in failures:
        sys.stderr.write(f"--- {name} ({status}) ---\n")
        for ln in tail(output, TAIL_LINES):
            sys.stderr.write(f"  {ln}\n")
        sys.stderr.write("\n")
    sys.stderr.write(
        "Fix the issues above, then push again.\n"
        "Docs-only bypass: SKIP_PREPUSH=1 git push ...\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
