#!/bin/bash
# Secret scanner — invoked by settings.template.json PreToolUse on `git commit`.
#
# MUST be PreToolUse, NOT PostToolUse.
# After commit completes, git diff --cached is empty — PostToolUse cannot catch staged secrets.
#
# Reads patterns from core/security/secret-patterns.txt (one regex per line, # = comment).
# Falls back to embedded patterns if the file is missing.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATTERNS_FILE="$SCRIPT_DIR/../../security/secret-patterns.txt"

STAGED=$(git diff --cached --name-only 2>/dev/null || true)
[ -z "$STAGED" ] && exit 0

# 1. Filename check
for file in $STAGED; do
    # Infra del framework (el propio scanner + sus patrones) no es un archivo de secretos.
    # El chequeo de CONTENIDO (abajo) igual les aplica.
    [[ "$file" == core/* ]] && continue
    if [[ "$file" == *.env ]] || [[ "$file" == *.env.* ]] || \
       [[ "$file" == *credentials* ]] || \
       [[ "$file" == *secret* && "$file" != *secret*.md ]]; then
        echo "BLOCKED: $file looks like a secrets file. Use environment variables instead." >&2
        exit 1
    fi
done

# 2. Content patterns check
DIFF=$(git diff --cached -U0 2>/dev/null || true)
[ -z "$DIFF" ] && exit 0

FOUND=0

if [ -f "$PATTERNS_FILE" ]; then
    while IFS= read -r pattern || [ -n "$pattern" ]; do
        [[ "$pattern" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${pattern// }" ]] && continue
        if echo "$DIFF" | grep -qiE "$pattern" 2>/dev/null; then
            echo "BLOCKED: staged diff matches secret pattern: $pattern" >&2
            FOUND=1
        fi
    done < "$PATTERNS_FILE"
else
    # Embedded fallback patterns
    FALLBACK=(
        'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'
        'AKIA[0-9A-Z]{16}'
        'sk-ant-[A-Za-z0-9\-_]+'
        'sk-[A-Za-z0-9]{32,}'
        '(api[_-]?key|apikey|access[_-]?token)\s*[=:]\s*["\x27][A-Za-z0-9_\-\.]{16,}'
    )
    for pattern in "${FALLBACK[@]}"; do
        if echo "$DIFF" | grep -qiE "$pattern" 2>/dev/null; then
            echo "BLOCKED: staged diff matches secret pattern: $pattern" >&2
            FOUND=1
        fi
    done
fi

if [ "$FOUND" -eq 1 ]; then
    echo "Remove the secret, add the file to .gitignore, and use environment variables." >&2
    exit 1
fi

exit 0
