"""PreToolUse hook: bloquea un write de producto de Shopify si no hay un backup
reciente que cubra los campos que se van a escribir. Seguridad por diseño (spec §11)."""
import sys, json, time
from pathlib import Path

# Ajustable cuando se conozca el connector real (Task 7):
WRITE_TOOL_MARKERS = ("shopify",)                # el tool_name debe contener alguno
WRITE_ACTION_MARKERS = ("product_update", "productupdate", "product_set", "update_product")
RECENT_WINDOW_SECONDS = 900                       # 15 min

def _is_shopify_product_write(tool_name: str) -> bool:
    t = (tool_name or "").lower()
    return any(m in t for m in WRITE_TOOL_MARKERS) and any(a in t for a in WRITE_ACTION_MARKERS)

def _write_target(tool_input: dict):
    pid = tool_input.get("productId") or tool_input.get("id") or ""
    fields = tool_input.get("fields") or {}
    return pid, set(fields.keys())

def _covering_backup_exists(backups_root: Path, product_id: str, fields: set, now: float) -> bool:
    tail = product_id.split("/")[-1]
    for p in Path(backups_root).glob(f"**/backups/{tail}-*.json"):
        try:
            data = json.loads(p.read_text())
        except Exception:
            continue
        if data.get("productId") != product_id:
            continue
        if not fields.issubset(set((data.get("fields") or {}).keys())):
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        return True
    return False

def evaluate(payload: dict, backups_root, now: float):
    tool_name = payload.get("tool_name", "")
    if not _is_shopify_product_write(tool_name):
        return "allow", "no es un write de producto de Shopify"
    tool_input = payload.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        return "block", "tool_input inesperado en un write de Shopify"
    pid, fields = _write_target(tool_input)
    if not pid or not fields:
        return "block", "no pude identificar producto/campos del write"
    if _covering_backup_exists(Path(backups_root), pid, fields, now):
        return "allow", "backup reciente encontrado"
    return "block", (f"Sin backup reciente para {pid} que cubra {sorted(fields)}. "
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
        # Ante un error inesperado: si parece un write de Shopify, fallamos CERRADO (bloqueamos).
        if _is_shopify_product_write(payload.get("tool_name", "")):
            print(f"backup_guard error en un write de Shopify, bloqueo por seguridad: {e}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if decision == "block":
        print(reason, file=sys.stderr)
        sys.exit(2)   # exit 2 = bloquea el tool y muestra stderr al modelo
    sys.exit(0)

if __name__ == "__main__":
    main()
