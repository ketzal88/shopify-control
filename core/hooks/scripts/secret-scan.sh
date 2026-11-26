#!/bin/bash
# Secret scanner - invoked by secret-scan-guard.py (PreToolUse) before a git commit.
# Also usable from CI or a git pre-commit hook: bash core/hooks/scripts/secret-scan.sh
#
# MUST run before the commit (PreToolUse, NOT PostToolUse): after the commit,
# git diff --cached is empty and nothing can be caught.
#
# Modes (SECRET_SCAN_MODE):
#   staged  (default) - what is staged now (git diff --cached).
#   pending           - staged + unstaged tracked changes + untracked files. Used when
#                       the command is `git add ... && git commit` or `git commit -a`:
#                       the add has not run yet, so the index does not show it.
#
# What is scanned: ADDED lines only. Removed lines and the "+++ b/file" headers are
# ignored, so a commit that DELETES a secret is never blocked (1.4 blocked it).
# Deleted files are skipped by the filename check for the same reason.
#
# False positive? Put `secret-scan:allow` on the offending line (same idea as
# gitleaks:allow) and say why in the commit message. Never bypass the hook.
#
# Patterns: core/security/secret-patterns.txt (one grep -E regex per line, # = comment).
# Embedded fallback patterns if that file is missing.
# Exit 1 = secret found (the Python wrapper maps it to exit 2 = deny).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATTERNS_FILE="$SCRIPT_DIR/../../security/secret-patterns.txt"
MODE="${SECRET_SCAN_MODE:-staged}"

git rev-parse --git-dir >/dev/null 2>&1 || exit 0
HAS_HEAD=0
git rev-parse --verify -q HEAD >/dev/null 2>&1 && HAS_HEAD=1

# NUL-separated file list: filenames with spaces are safe.
list_files() {
    git diff --cached --name-only -z --diff-filter=ACMR 2>/dev/null
    if [ "$MODE" = "pending" ]; then
        git diff --name-only -z --diff-filter=ACMR 2>/dev/null
        git ls-files --others --exclude-standard -z 2>/dev/null
    fi
}

added_lines() {
    {
        if [ "$MODE" = "pending" ] && [ "$HAS_HEAD" = "1" ]; then
            git diff HEAD -U0 --no-color --no-ext-diff 2>/dev/null
        else
            git diff --cached -U0 --no-color --no-ext-diff 2>/dev/null
            [ "$MODE" = "pending" ] && git diff -U0 --no-color --no-ext-diff 2>/dev/null
        fi
    } | grep '^+' | grep -v '^+++'
    if [ "$MODE" = "pending" ]; then
        git ls-files --others --exclude-standard -z 2>/dev/null |
        while IFS= read -r -d '' f; do
            [ -f "$f" ] || continue
            grep -Iq . "$f" 2>/dev/null || continue   # skip binary / empty
            sed 's/^/+/' "$f"
        done
    fi
}

# 1. Filename check
BAD_FILE=0
while IFS= read -r -d '' file; do
    base="${file##*/}"
    # The framework's own scanner infrastructure describes secrets, it does not hold them.
    case "$file" in
        core/*|*secret-scan.sh|*secret-scan-guard.py|*secret-patterns.txt) continue ;;
    esac
    # Templates that only list variable NAMES are allowed.
    case "$base" in
        .env.example|.env.sample|.env.template|.env.dist|*.env.example|*.env.sample) continue ;;
    esac
    blocked=0
    case "$base" in
        .env|*.env|.env.*|*.pem|*.p12|*.pfx|*.key|*.keystore|*.jks) blocked=1 ;;
        *firebase-adminsdk*.json|*service-account*.json|*serviceAccount*.json) blocked=1 ;;
        *credentials*) blocked=1 ;;
        *secret*) [[ "$base" != *.md ]] && blocked=1 ;;
    esac
    case "$file" in
        .vercel/*|*/.vercel/*) blocked=1 ;;
    esac
    if [ "$blocked" = "1" ]; then
        echo "BLOCKED: $file looks like a secrets file. Use environment variables instead." >&2
        BAD_FILE=1
    fi
done < <(list_files | sort -zu)
[ "$BAD_FILE" = "1" ] && exit 1

# 2. Content check on added lines only, minus explicitly allowed lines.
ADDED=$(added_lines | grep -viE 'secret-scan:allow|gitleaks:allow' || true)
[ -z "$ADDED" ] && exit 0

FOUND=0
check() {
    if printf '%s\n' "$ADDED" | grep -qiE -- "$1" 2>/dev/null; then
        echo "BLOCKED: added lines match secret pattern: $1" >&2
        FOUND=1
    fi
}

if [ -f "$PATTERNS_FILE" ]; then
    while IFS= read -r pattern || [ -n "$pattern" ]; do
        pattern="${pattern%$'\r'}"   # tolerate CRLF pattern files (autocrlf)
        [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${pattern// }" ]] && continue
        check "$pattern"
    done < "$PATTERNS_FILE"
else
    for pattern in \
        'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY' \
        'AKIA[0-9A-Z]{16}' \
        'AIza[0-9A-Za-z_-]{35}' \
        'sk-ant-[A-Za-z0-9_-]+' \
        'sk-[A-Za-z0-9]{32,}' \
        '(api[_-]?key|apikey|access[_-]?token|secret|password)["'"'"']?\s*[=:]\s*["'"'"'][A-Za-z0-9_./+=-]{16,}'; do
        check "$pattern"
    done
fi

if [ "$FOUND" -eq 1 ]; then
    echo "Remove the secret, add the file to .gitignore, and use environment variables." >&2
    echo "False positive: add 'secret-scan:allow' on that line and explain it in the commit." >&2
    exit 1
fi
exit 0
