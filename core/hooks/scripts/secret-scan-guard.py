"""PreToolUse(Bash) guard: corre secret-scan.sh SOLO cuando el comando es `git commit`.

Por qué es un script-file y no un `python -c "..."` inline en settings.json:
el wrapper inline con comillas anidadas NO dispara de forma confiable en el
runtime de hooks de Windows (observado: un `git commit` con secreto no se
bloqueaba), mientras que los hooks del framework que usan el formato
`cd "$CLAUDE_PROJECT_DIR" && python core/hooks/scripts/X.py` (canonical-guard,
pre-push-guard, close-guard) sí disparan. Este archivo replica la lógica del
inline como script para usar ese mismo formato robusto.

Contrato: exit 0 = permitir; exit != 0 = bloquear (lo que devuelva secret-scan.sh).
"""
import json
import os
import subprocess
import sys


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # sin payload legible no sabemos si es commit: no bloqueamos
    if not isinstance(payload, dict):
        sys.exit(0)
    cmd = ((payload.get("tool_input") or {}).get("command") or "")
    if not cmd.lstrip().startswith("git commit"):
        sys.exit(0)  # solo nos importa `git commit`
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    script = os.path.join(root, "core", "hooks", "scripts", "secret-scan.sh")
    sys.exit(subprocess.call(["bash", script], cwd=root))


if __name__ == "__main__":
    main()
