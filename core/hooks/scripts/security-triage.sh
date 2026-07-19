#!/bin/bash
# security-triage: deterministic first-pass security-review checks, driven by stack.json.
# Each hit is a CANDIDATE, not a verdict — read the code. Each check skips silently when its
# config key is absent (framework philosophy: absent key = safe no-op).
#
# Reads: security.review.{apiDir,tenantParam,authSignals,cronCheck,publicEnvScan}
# Usage: bash core/hooks/scripts/security-triage.sh   (run from anywhere in the repo)

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"

cfg() { python3 "$SCRIPT_DIR/read-config.py" "security.review.$1" 2>/dev/null || true; }

API_DIR="$(cfg apiDir)"
if [ -z "$API_DIR" ]; then
  [ -d "src/app/api" ] && API_DIR="src/app/api" || API_DIR="app/api"
fi
TENANT_PARAM="$(cfg tenantParam)"
AUTH_SIGNALS="$(cfg authSignals)"
CRON_CHECK="$(cfg cronCheck)"
PUBLIC_ENV_PREFIX="$(cfg publicEnvPrefix)"  # e.g. NEXT_PUBLIC_ | VITE_ | PUBLIC_ — set to enable the scan
PUBLIC_ENV_ALLOW="$(cfg publicEnvAllow)"    # optional regex of known-public exceptions (e.g. FIREBASE)

echo "════════════════════════════════════════════════════════════"
echo " Security triage — first pass (every hit is a candidate, read the code)"
echo " apiDir=$API_DIR"
echo "════════════════════════════════════════════════════════════"

ran=0

# 1. Cron/scheduled routes that don't check their secret
if [ -n "$CRON_CHECK" ] && [ -d "$API_DIR/cron" ]; then
  ran=1
  echo ""
  echo "── Cron routes missing a secret check ($CRON_CHECK) ──────────"
  miss=0
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    grep -qE "$CRON_CHECK" "$f" || { echo "  ⚠ $f"; miss=1; }
  done < <(find "$API_DIR/cron" -name 'route.*' 2>/dev/null)
  [ "$miss" -eq 0 ] && echo "  ✓ all cron routes check the secret"
fi

# 2. Client-bundle secret exposure: env vars a build inlines into the browser bundle.
#    Opt-in via publicEnvPrefix (framework-specific prefix). Agnostic: no tool name hardcoded.
if [ -n "$PUBLIC_ENV_PREFIX" ]; then
  ran=1
  echo ""
  echo "── Secrets exposed via ${PUBLIC_ENV_PREFIX} (shipped to the browser) ─"
  hits=$(grep -rnE "${PUBLIC_ENV_PREFIX}[A-Z_]*(SECRET|PRIVATE|TOKEN|PASSWORD)" src/ app/ 2>/dev/null || true)
  [ -n "$PUBLIC_ENV_ALLOW" ] && hits=$(printf '%s\n' "$hits" | grep -vE "$PUBLIC_ENV_ALLOW" || true)
  if [ -n "$hits" ]; then echo "$hits" | sed 's/^/  ⚠ /'; else echo "  ✓ none"; fi
fi

# 3. Routes with a tenant id and NO visible auth signal (high false-positive — read each)
if [ -n "$TENANT_PARAM" ] && [ -n "$AUTH_SIGNALS" ] && [ -d "$API_DIR" ]; then
  ran=1
  echo ""
  echo "── Routes with a tenant id and NO visible auth signal ────────"
  residual=$(while IFS= read -r f; do
      [ -z "$f" ] && continue
      if grep -qE "$TENANT_PARAM|params\.id" "$f" && ! grep -qiE "$AUTH_SIGNALS" "$f"; then echo "$f"; fi
    done < <(grep -rlE "$TENANT_PARAM|params\.id" "$API_DIR" --include='route.*' 2>/dev/null))
  total=$(grep -rlE "$TENANT_PARAM|params\.id" "$API_DIR" --include='route.*' 2>/dev/null | wc -l | tr -d ' ')
  if [ -z "$residual" ]; then
    echo "  ✓ the $total routes with a tenant id show some auth signal"
  else
    rcount=$(printf '%s\n' "$residual" | wc -l | tr -d ' ')
    echo "  $rcount of $total routes with a tenant id show no auth signal — read each:"
    printf '%s\n' "$residual" | head -25 | sed 's/^/  ? /'
    [ "$rcount" -gt 25 ] && echo "  … (+$(( rcount - 25 )) more)"
  fi
  echo "  (read-only of non-sensitive data may be intentional; verify)"
fi

echo ""
if [ "$ran" -eq 0 ]; then
  echo "No checks configured. Set security.review.{tenantParam,authSignals,cronCheck,publicEnvScan} in stack.json."
else
  echo "Done. Next: read your stack's security references and verify each candidate."
fi
