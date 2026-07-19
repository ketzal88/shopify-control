"""PreToolUse(Bash) guard: bloquea llamadas directas a la Admin API de Shopify.

`backup_guard` filtra por NOMBRE DE TOOL ("shopify" en el nombre), así que ve los
writes del connector pero es ciego a un `curl` contra
`https://<tienda>.myshopify.com/admin/api/2024-10/graphql.json`. Ese camino
esquiva backup, alcance de campos y gate de confirmación de una sola vez.

En el v1 no hay ninguna razón legítima para pegarle a la Admin API desde la
shell: todo pasa por el connector. Así que se bloquea siempre, en lectura y en
escritura (una lectura por shell suele ser el paso previo a un write por shell).

Contrato: exit 0 = permitir; exit 2 = BLOQUEAR (Claude Code solo bloquea con 2).
"""
import json
import re
import sys

# Endpoints de la Admin API. Cubre el dominio de tienda y las rutas de API.
ADMIN_API_PATTERNS = [
    r"myshopify\.com/admin",
    r"/admin/api/\d{4}-\d{2}/",
    r"admin/api/graphql",
    r"shopify\.com/admin/oauth",
]

# Clientes HTTP de línea de comando.
HTTP_CLIENTS = r"\b(curl|wget|http|https|httpie|Invoke-RestMethod|Invoke-WebRequest)\b"

BLOCK = 2
ALLOW = 0


def is_admin_api_call(command: str) -> bool:
    if not command:
        return False
    if not re.search(HTTP_CLIENTS, command, re.I):
        return False
    return any(re.search(p, command, re.I) for p in ADMIN_API_PATTERNS)


def main():
    # La consola de Windows no es UTF-8 por default y este mensaje lleva acentos:
    # sin esto, quien lo invoque desde otro proceso no puede leer el stderr.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(ALLOW)
    if not isinstance(payload, dict):
        sys.exit(ALLOW)
    command = ((payload.get("tool_input") or {}).get("command") or "")
    if is_admin_api_call(command):
        print("Llamada directa a la Admin API de Shopify desde la shell: bloqueada. "
              "En el v1 todo pasa por el connector, que es lo que tiene backup, "
              "control de alcance y confirmación del cliente.", file=sys.stderr)
        sys.exit(BLOCK)
    sys.exit(ALLOW)


if __name__ == "__main__":
    main()
