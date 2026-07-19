"""PreToolUse(Bash) guard: corre secret-scan.sh SOLO cuando el comando es `git commit`.

CONTRATO DE EXIT CODES — esto era el bug de #1b:
Claude Code bloquea un tool SOLO con `exit 2`. Un `exit 1` lo trata como error
no-bloqueante y el tool se ejecuta igual. `secret-scan.sh` devuelve 1 cuando
detecta un secreto, asi que el wrapper original —que hacia
`sys.exit(subprocess.call(...))`— propagaba ese 1 y por lo tanto NUNCA bloqueaba
un commit. Mapeamos cualquier salida != 0 del scanner a exit 2.

El stderr del scanner (las lineas "BLOCKED: ...") se hereda y llega al modelo.
"""
import json
import os
import subprocess
import sys

BLOCK = 2  # Claude Code: exit 2 = bloquear el tool y mostrar stderr al modelo
ALLOW = 0


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(ALLOW)  # sin payload legible no sabemos si es commit: no bloqueamos
    if not isinstance(payload, dict):
        sys.exit(ALLOW)
    cmd = ((payload.get("tool_input") or {}).get("command") or "")
    if not cmd.lstrip().startswith("git commit"):
        sys.exit(ALLOW)  # solo nos importa `git commit`
    root = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or "."
    script = os.path.join(root, "core", "hooks", "scripts", "secret-scan.sh")
    rc = subprocess.call(["bash", script], cwd=root)
    sys.exit(BLOCK if rc != 0 else ALLOW)


if __name__ == "__main__":
    main()
