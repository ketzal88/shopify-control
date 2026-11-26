#!/usr/bin/env python3
"""git_target: find every git invocation inside a Bash command, and where it runs.

Shared helper for the PreToolUse guards (secret-scan-guard, pre-push-guard).
Not a hook by itself.

Why it exists: guards that only looked at `cmd.startswith("git commit")` were
bypassed by ordinary agent habits, and a token reached a shared repo that way:

    cd sub && git commit -m x          (leading cd)
    git add -A && git commit -m x      (commit is the second segment)
    git -C ../other commit -m x        (global option before the subcommand)
    FOO=1 git push                     (env assignment prefix)

So the command is split into segments on && || ; | and newlines (outside
quotes), each segment is parsed with shlex, a `cd X` segment moves the working
directory for the segments after it, and `git -C X` moves it for that one call.

1.5.5: shell reserved words in front of git (`! git push`, `if git push;
then`) are dropped like wrappers; `git -c alias.*` is OPAQUE; an alias from
git config is expanded (a shell alias `!...` is OPAQUE).

On Windows, MSYS paths (/c/Users/...) are converted to C:/Users/... so the
directory can be handed to subprocess.

ASCII-only on purpose: hook consoles on Windows are often cp1252.
"""
import os
import re
import shlex
import subprocess

# Global git options that consume the next argument (`git -C dir`, `git -c k=v`).
OPTS_WITH_VALUE = {"-C", "-c", "--exec-path", "--namespace", "--git-dir", "--work-tree", "--config-env"}
ENV_ASSIGN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
MSYS_DRIVE = re.compile(r"^/([a-zA-Z])(/|$)")
# Prefixes that run the next word as the real command (`env git push`).
WRAPPERS = {"env", "command", "exec", "nohup", "sudo", "time", "builtin", "xargs"}
# Wrapper options that consume the next word (`sudo -u git git push` must not
# read the user name as the command).
WRAPPER_OPTS_WITH_VALUE = {
    "sudo": {"-u", "-g", "-C", "-h", "-p", "-U", "-r", "-t", "-D", "-R", "-T"},
    "env": {"-u", "-C", "--unset", "--chdir"},
    "exec": {"-a"},
    "time": {"-f", "-o", "--format", "--output"},
    "xargs": {"-I", "-n", "-L", "-d", "-E", "-P", "-s", "-a", "--arg-file",
              "--delimiter", "--max-args", "--max-procs"},
}
SHELLS = {"bash", "sh", "zsh", "dash", "bash.exe", "sh.exe"}
SHELL_OPTS_WITH_VALUE = {"-o", "-O", "+o", "+O", "--rcfile", "--init-file"}
GIT_WORDS = {"git", "git.exe"}
# Shell reserved words that can sit in front of a command (`! git push`,
# `if git push; then`, `while git push; do`). Dropped like a wrapper (1.5.5).
RESERVED = {"!", "if", "then", "else", "elif", "do", "while", "until", "{"}
# Anything in a command that can change which aliases git sees: writing config,
# config injected through the environment, a different HOME. Once seen, a
# non-builtin subcommand cannot be resolved from the config on disk (it may be
# redefined before it runs), so it is OPAQUE (1.5.5).
CONFIG_TAINT = re.compile(
    r"\bconfig\b|GIT_CONFIG|GIT_DIR|\bHOME=|XDG_CONFIG_HOME|gitconfig|\.git/|--config-env|\binclude")
# Builtins that always exist, in case `git --list-cmds` is unavailable.
CORE_BUILTINS = {
    "add", "am", "apply", "bisect", "blame", "branch", "checkout", "cherry-pick", "clean",
    "clone", "commit", "config", "describe", "diff", "fetch", "format-patch", "gc", "grep",
    "init", "log", "ls-files", "ls-remote", "merge", "mv", "notes", "pull", "push", "rebase",
    "reflog", "remote", "reset", "restore", "rev-list", "rev-parse", "revert", "rm", "show",
    "stash", "status", "submodule", "switch", "tag", "worktree",
}
# Pseudo-subcommand for a git call the parser could not see into (a shell
# string nested too deep, `bash -c` without a readable string). Guards treat
# it as the worst case instead of letting it through.
OPAQUE = "__opaque__"


def normalize(path):
    """MSYS /c/foo -> C:/foo on Windows; anything else unchanged."""
    if os.name == "nt":
        m = MSYS_DRIVE.match(path)
        if m:
            return m.group(1).upper() + ":/" + path[len(m.group(0)):]
    return path


def base_dir(payload):
    """Directory the Bash tool runs in: payload cwd, then CLAUDE_PROJECT_DIR, then ours."""
    cwd = (payload or {}).get("cwd") if isinstance(payload, dict) else None
    return cwd or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def segments(cmd):
    """Split a shell command on && || ; | & and newlines, respecting quotes.

    Also splits on ( ) and backticks (always shell metacharacters) and on
    { } when they stand alone as a word, so `(cd x && git commit)` and
    `{ git push; }` expose the git word while `-m{x}` stays one word. No heredoc parsing. Good enough to
    find a `git` word at command position, which is all the guards need.
    """
    out, buf, quote, i = [], [], None, 0
    while i < len(cmd):
        ch = cmd[i]
        if quote:
            buf.append(ch)
            if ch == "\\" and quote == '"' and i + 1 < len(cmd):
                buf.append(cmd[i + 1])
                i += 2
                continue
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        if ch in "{}" and not _standalone(cmd, i):
            buf.append(ch)  # a brace inside a word (-m{x}) is literal, not a group
            i += 1
            continue
        if ch in ";\n|&(){}`":
            out.append("".join(buf))
            buf = []
            # swallow the second char of && and ||
            if ch in "|&" and i + 1 < len(cmd) and cmd[i + 1] == ch:
                i += 1
            i += 1
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [s.strip() for s in out if s.strip()]


def _standalone(cmd, i):
    """True if cmd[i] is a word of its own (bash only treats { } as reserved then)."""
    before = cmd[i - 1] if i > 0 else " "
    after = cmd[i + 1] if i + 1 < len(cmd) else " "
    seps = " \t\n;&|()"
    return before in seps and after in seps


def _words(segment):
    try:
        return shlex.split(segment, posix=True)
    except ValueError:
        return segment.split()


def _resolve(cur, target):
    target = normalize(target)
    if target in ("~", "") or target.startswith("~/"):
        target = os.path.expanduser(target)
    return target if os.path.isabs(target) else os.path.normpath(os.path.join(cur, target))


def git_calls(cmd, start_dir):
    """Yield (subcommand, args, directory) for each git invocation in cmd.

    `directory` is where that git call operates (cd and -C applied).
    `args` are the words after the subcommand.
    """
    yield from _git_calls(cmd, normalize(start_dir), 0)


def _strip_prefixes(words):
    """Drop env assignments and wrapper commands in front of the real command.

    Returns (words, inner) where inner is a command string handed to a wrapper
    (`env -S "git push"`), or None.
    """
    wrapped = False
    while words:
        w = words[0]
        name = os.path.basename(w).lower()
        if ENV_ASSIGN.match(w) or w in RESERVED:
            words = words[1:]
        elif name in WRAPPERS:
            wrapped = True
            with_value = WRAPPER_OPTS_WITH_VALUE.get(name, set())
            words = words[1:]
            while words and words[0].startswith("-"):
                opt = words[0]
                if name == "env" and opt in ("-S", "--split-string") and len(words) > 1:
                    return [], words[1]
                if opt.startswith("--split-string=") or (name == "env" and opt.startswith("-S") and len(opt) > 2):
                    return [], opt.split("=", 1)[1] if "=" in opt else opt[2:]
                words = words[2:] if opt in with_value else words[1:]
        else:
            break
    if wrapped and words and os.path.basename(words[0]).lower() not in GIT_WORDS | SHELLS:
        # Unknown wrapper option with a value: fall back to the first git word.
        for k, w in enumerate(words):
            if os.path.basename(w).lower() in GIT_WORDS:
                return words[k:], None
    return words, None


def _shell_string(words):
    """The command string of `bash [opts] -c STRING`, or None."""
    i = 1
    while i < len(words):
        w = words[i]
        if w in SHELL_OPTS_WITH_VALUE:
            i += 2
            continue
        if w.startswith("-") and not w.startswith("--") and "c" in w[1:]:
            return words[i + 1] if i + 1 < len(words) else None
        if w.startswith("-") or w.startswith("+"):
            i += 1
            continue
        return None  # `bash script.sh`: a file, not a string we can read
    return None


def _git_calls(cmd, cur, depth, tainted=False):
    for seg in segments(cmd):
        tainted = tainted or bool(CONFIG_TAINT.search(seg))
        words, inner = _strip_prefixes(_words(seg))
        if inner is not None:
            yield from _nested(inner, cur, depth, seg, tainted)
            continue
        if not words:
            continue
        name = os.path.basename(words[0]).lower()
        # bash -c "git commit ..." / sh -lc '...' / eval "...": look inside
        if name in SHELLS or name == "eval":
            inner = " ".join(words[1:]) if name == "eval" else _shell_string(words)
            if inner is not None:
                yield from _nested(inner, cur, depth, seg, tainted)
            elif "git" in seg:
                yield OPAQUE, words[1:], cur
            continue
        if words[0] == "cd":
            if len(words) > 1:
                cur = _resolve(cur, words[1])
            continue
        if name not in GIT_WORDS:
            continue
        here = cur
        i = 1
        sub = None
        aliased = False
        while i < len(words):
            w = words[i]
            low = w.lower()
            if w in ("-c", "--config-env") and i + 1 < len(words) and words[i + 1].lower().startswith("alias."):
                aliased = True  # `git -c alias.p=push p`: the real subcommand is hidden
            elif low.startswith(("-calias.", "--config-env=alias.")):
                aliased = True
            if w.startswith(("--git-dir=", "--work-tree=", "--config-env=")):
                w, val = w.split("=", 1)
                words = words[:i] + [w, val] + words[i + 1:]
            if w in OPTS_WITH_VALUE:
                if i + 1 < len(words):
                    if w in ("-C", "--work-tree"):
                        here = _resolve(here, words[i + 1])
                    elif w == "--git-dir":
                        # the repo is the parent of a .git dir; a bare repo is its own dir
                        gd = _resolve(here, words[i + 1])
                        here = os.path.dirname(gd) if os.path.basename(gd) == ".git" else gd
                i += 2
                continue
            if w.startswith("-"):
                i += 1
                continue
            sub = w
            break
        if aliased:
            yield OPAQUE, words[i + 1:] if sub else [], here
            continue
        if sub:
            if _is_builtin(sub):
                yield sub, words[i + 1:], here
            elif tainted:
                yield OPAQUE, words[i + 1:], here  # alias may be (re)defined in this command
            else:
                sub, args = _expand_alias(sub, words[i + 1:], here)
                yield sub, args, here


def _expand_alias(sub, args, here, hops=0):
    """Resolve a git alias from config (`git p` with alias.p=push).

    Git ignores aliases that shadow a builtin, so a builtin never resolves.
    Fails closed: a shell alias (`!...`), a chain deeper than 5, a lookup that
    errors, or a name that is neither an alias nor a known git command (an
    external `git-foo` on PATH) comes back as OPAQUE.
    """
    if sub == OPAQUE or hops > 5:
        return OPAQUE, args
    if _is_builtin(sub):
        return sub, args
    try:
        r = subprocess.run(
            ["git", "config", "--get", "alias." + sub], cwd=here if os.path.isdir(here) else None,
            capture_output=True, text=True, timeout=3,
        )
    except Exception:
        return OPAQUE, args
    value = (r.stdout or "").strip() if r.returncode == 0 else ""
    if not value:
        return (sub, args) if sub in _known_commands() else (OPAQUE, args)
    if value.startswith("!"):
        return OPAQUE, args
    parts = _words(value)
    if not parts:
        return OPAQUE, args
    return _expand_alias(parts[0], parts[1:] + args, here, hops + 1)


_CMDS = {}


def _list_cmds(kind):
    if kind not in _CMDS:
        try:
            r = subprocess.run(["git", "--list-cmds=" + kind], capture_output=True, text=True, timeout=3)
            _CMDS[kind] = set(r.stdout.split()) if r.returncode == 0 else set()
        except Exception:
            _CMDS[kind] = set()
    return _CMDS[kind]


def _is_builtin(sub):
    """True when `sub` is a git builtin (aliases cannot override those)."""
    return sub in CORE_BUILTINS or sub in _list_cmds("main")


def _known_commands():
    """Builtins plus external git-* commands found on PATH (git lfs, git flow)."""
    return CORE_BUILTINS | _list_cmds("main") | _list_cmds("others")


def _nested(inner, cur, depth, seg, tainted=False):
    if depth >= 3:
        if "git" in seg:
            yield OPAQUE, [], cur  # too deep to read: let the guard assume the worst
        return
    yield from _git_calls(inner, cur, depth + 1, tainted)


def opaque(cmd, start_dir):
    """Directories of git calls hidden in a shell string the parser could not read."""
    return [d for s, _a, d in git_calls(cmd, start_dir) if s == OPAQUE]


def find(cmd, start_dir, subcommand):
    """All (args, directory) for one subcommand, e.g. find(cmd, d, "commit")."""
    return [(a, d) for s, a, d in git_calls(cmd, start_dir) if s == subcommand]
