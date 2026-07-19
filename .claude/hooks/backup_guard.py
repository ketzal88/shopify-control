"""PreToolUse hook: bloquea un write de producto de Shopify si no hay un backup
reciente que cubra los 3 campos en alcance del v1. Seguridad por diseño (spec §11).

Calibrado al connector oficial de Shopify (Task 7):
- La DESCRIPCIÓN se escribe con `Shopify:update-product` (campo `descriptionHtml`).
- El SEO (meta title / description) se escribe con `Shopify:graphql_mutation`
  usando `productUpdate { seo { title description } }`, porque update-product no
  cubre SEO.
Cualquiera de esos dos writes debe tener antes un backup que cubra los 3 campos.
Otros tools de escritura del connector (set-inventory, create-discount, etc.) NO
los vigila este hook en el v1: están fuera del flujo del skill (el "connector
restringido" para el cliente es trabajo futuro, D2).
"""
import sys, json, time, re
from pathlib import Path

# Acción (parte después de "Shopify:") que el skill usa para editar un producto:
GUARDED_PRODUCT_ACTIONS = {"update-product"}
# Campos que el skill respalda SIEMPRE juntos (contrato con mejorar-descripcion):
REQUIRED_BACKUP_FIELDS = {"descriptionHtml", "seo_title", "seo_description"}
RECENT_WINDOW_SECONDS = 900  # 15 min
GID_RE = re.compile(r"gid://shopify/Product/\d+")


def _action(tool_name: str) -> str:
    # Soporta el nombre real de MCP ("mcp__claude_ai_Shopify__update-product")
    # y el de display del app ("Shopify:update-product"). Devuelve "update-product".
    return re.split(r"__|:", (tool_name or ""))[-1].strip().lower()

def _graphql_query(tool_input) -> str:
    if isinstance(tool_input, dict):
        return tool_input.get("query") or tool_input.get("mutation") or ""
    return ""

def _is_product_write(tool_name: str, tool_input) -> bool:
    if "shopify" not in (tool_name or "").lower():
        return False
    action = _action(tool_name)
    if action in GUARDED_PRODUCT_ACTIONS:
        return True
    if action == "graphql_mutation":
        q = _graphql_query(tool_input).lower()
        return "gid://shopify/product/" in q and (
            "productupdate" in q or "seo" in q or "descriptionhtml" in q
        )
    return False

def _product_id(tool_name: str, tool_input) -> str:
    if _action(tool_name) == "graphql_mutation":
        m = GID_RE.search(_graphql_query(tool_input))
        return m.group(0) if m else ""
    if isinstance(tool_input, dict):
        return tool_input.get("id") or tool_input.get("productId") or ""
    return ""

def _covering_backup_exists(backups_root: Path, product_id: str, now: float) -> bool:
    tail = product_id.split("/")[-1]
    for p in Path(backups_root).glob(f"**/backups/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("productId") != product_id:
            continue
        if not REQUIRED_BACKUP_FIELDS.issubset(set((data.get("fields") or {}).keys())):
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        return True
    return False

def evaluate(payload: dict, backups_root, now: float):
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    if not _is_product_write(tool_name, tool_input):
        return "allow", "no es un write de producto vigilado"
    pid = _product_id(tool_name, tool_input)
    if not pid:
        return "block", "no pude identificar el producto del write"
    if _covering_backup_exists(Path(backups_root), pid, now):
        return "allow", "backup reciente encontrado"
    return "block", (f"Sin backup reciente para {pid} que cubra {sorted(REQUIRED_BACKUP_FIELDS)}. "
                     "El skill debe guardar el backup antes de escribir.")

def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # no pudimos leer el payload; no sabemos si es un write, no bloqueamos todo
    if not isinstance(payload, dict):
        sys.exit(0)
    backups_root = payload.get("cwd") or "."
    try:
        decision, reason = evaluate(payload, backups_root, time.time())
    except Exception as e:
        # Ante un error inesperado: si parece un write de producto, fallamos CERRADO.
        if _is_product_write(payload.get("tool_name", ""), payload.get("tool_input")):
            print(f"backup_guard error en un write de Shopify, bloqueo por seguridad: {e}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if decision == "block":
        print(reason, file=sys.stderr)
        sys.exit(2)   # exit 2 = bloquea el tool y muestra stderr al modelo
    sys.exit(0)

if __name__ == "__main__":
    main()
