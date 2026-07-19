"""PreToolUse hook: cuida los writes de Shopify del v1.

Hace TRES cosas (antes hacía solo la primera, y por eso el alcance quedaba
enforced únicamente por la prosa de los skills):

1. ALCANCE DE TOOL: los tools de escritura del connector que el v1 no permite
   (stock, status masivo, descuentos, colecciones, alta de productos) se
   bloquean siempre. No hay backup que los habilite.
2. ALCANCE DE CAMPOS: un `update-product` solo puede traer `id` +
   `descriptionHtml`; una mutación de producto solo puede tocar
   `descriptionHtml` y/o `seo`. Cualquier otra key de primer nivel (handle,
   status, title, tags, variants, images...) bloquea. Antes, un backup válido
   funcionaba como llave de 15 minutos para cambiar precio o status.
3. BACKUP: sigue exigiendo un backup reciente que cubra los 3 campos, y ahora
   además valida que los VALORES sean strings y no estén los tres vacíos (un
   backup de placeholders satisfacía el guard y hacía que el "undo" borrara la
   descripción original en vez de restaurarla).

Calibrado al connector oficial de Shopify:
- La DESCRIPCIÓN se escribe con `Shopify:update-product` (`descriptionHtml`).
- El SEO se escribe con `Shopify:graphql_mutation` usando
  `productUpdate { seo { title description } }`.

Contrato de salida: exit 0 = permitir; exit 2 = BLOQUEAR (Claude Code solo
bloquea con 2; un exit 1 es error no-bloqueante y el tool se ejecuta igual).
"""
import sys, json, time, re
from datetime import datetime
from pathlib import Path

# Acción (parte después de "Shopify:") que el skill usa para editar un producto:
GUARDED_PRODUCT_ACTIONS = {"update-product"}
# Lo único que un update-product puede traer en el v1:
ALLOWED_UPDATE_KEYS = {"id", "descriptionhtml"}
# Lo único que puede tocar un productUpdate en el v1 (keys de primer nivel):
ALLOWED_PRODUCT_INPUT_KEYS = {"id", "descriptionhtml", "seo"}
# Campos que el skill respalda SIEMPRE juntos (contrato con mejorar-descripcion):
REQUIRED_BACKUP_FIELDS = {"descriptionHtml", "seo_title", "seo_description"}
RECENT_WINDOW_SECONDS = 900  # 15 min
GID_RE = re.compile(r"gid://shopify/Product/\d+", re.I)

# Tools de escritura del connector prohibidos en el v1 (alcance: descripción + SEO).
FORBIDDEN_ACTIONS = {
    "set-inventory",
    "bulk-update-product-status",
    "create-discount",
    "create-product",
    "create-collection",
    "update-collection",
    "add-to-collection",
}

# Mutaciones GraphQL prohibidas: tocan precio, stock, status, publicación o borran.
FORBIDDEN_MUTATIONS = {
    "productdelete",
    "productvariantsbulkupdate",
    "productvariantsbulkcreate",
    "productvariantsbulkdelete",
    "productchangestatus",
    "inventorysetquantities",
    "inventoryadjustquantities",
    "inventoryactivate",
    "discountcodebasiccreate",
    "discountautomaticbasiccreate",
    "collectioncreate",
    "collectionupdate",
    "collectionaddproducts",
    "publishablepublish",
    "publishableunpublish",
    "productdeletemedia",
}


def _action(tool_name: str) -> str:
    # Soporta el nombre real de MCP ("mcp__claude_ai_Shopify__update-product")
    # y el de display del app ("Shopify:update-product"). Devuelve "update-product".
    return re.split(r"__|:", (tool_name or ""))[-1].strip().lower()


def _is_shopify(tool_name: str) -> bool:
    return "shopify" in (tool_name or "").lower()


def _graphql_text(tool_input) -> str:
    """Query + variables serializadas.

    Incluir las variables es deliberado: la forma idiomática de GraphQL pasa el
    id y los campos por `variables`, así que mirar solo el string del query
    dejaba pasar cualquier mutación parametrizada sin ver el gid ni los campos.
    """
    if not isinstance(tool_input, dict):
        return ""
    text = tool_input.get("query") or tool_input.get("mutation") or ""
    variables = tool_input.get("variables")
    if variables is not None:
        try:
            text += " " + json.dumps(variables, ensure_ascii=False)
        except Exception:
            text += " " + str(variables)
    return text


def _balanced_object(text: str, start: int) -> str:
    """Substring del objeto {...} que arranca en text[start] == '{'."""
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return text[start:i + 1]
    return text[start:]


def _top_level_keys(obj_text: str) -> set:
    """Keys de primer nivel de un objeto tipo `{ id: "x", seo: { title: "y" } }`.

    Colapsa los objetos anidados antes de buscar, para que `seo.title` NO cuente
    como key de primer nivel. Esto es lo que permite aceptar la mutación de SEO
    legítima y rechazar `handle`/`status` al tope del mismo objeto.
    """
    body = obj_text[1:-1] if obj_text.startswith("{") else obj_text
    # Borrar los literales de string ANTES de buscar keys: un valor como
    # "gid://shopify/Product/1" contiene "gid:" y se leería como key.
    body = re.sub(r'"(?:[^"\\]|\\.)*"', " ", body)
    body = re.sub(r"'(?:[^'\\]|\\.)*'", " ", body)
    prev = None
    while prev != body:
        prev = body
        body = re.sub(r"\{[^{}]*\}", " ", body)
    return {m.group(1).lower() for m in re.finditer(r"(\w+)\s*:", body)}


def _product_input_keys(text: str) -> set:
    """Keys de primer nivel del objeto `product:` / `input:` de la mutación."""
    m = re.search(r"\b(?:product|input)\s*:\s*\{", text, re.I)
    if not m:
        return set()
    return _top_level_keys(_balanced_object(text, m.end() - 1))


def _variables_product_keys(tool_input) -> set:
    """Keys del objeto de producto pasado por `variables` (bypass del guard viejo)."""
    keys = set()
    variables = tool_input.get("variables") if isinstance(tool_input, dict) else None
    if isinstance(variables, dict):
        for value in variables.values():
            if isinstance(value, dict) and any(str(k).lower() == "id" for k in value):
                keys |= {str(k).lower() for k in value.keys()}
    return keys


def _product_id(tool_name: str, tool_input) -> str:
    if _action(tool_name) == "graphql_mutation":
        m = GID_RE.search(_graphql_text(tool_input))
        return m.group(0) if m else ""
    if isinstance(tool_input, dict):
        return tool_input.get("id") or tool_input.get("productId") or ""
    return ""


def _client_of(path: Path) -> str:
    """Slug del cliente dueño del backup, si está bajo `clients/<slug>/`."""
    parts = [p.lower() for p in path.parts]
    if "clients" in parts:
        i = parts.index("clients")
        if i + 1 < len(parts):
            return parts[i + 1]
    return ""


def _ts_fresh(data: dict, now: float) -> bool:
    """Frescura por el `ts` del CONTENIDO, no solo por el mtime del archivo.

    El mtime lo refresca cualquier operación de git: un `git pull` o un cambio de
    branch toca todos los archivos del checkout, y eso resucitaba backups viejos
    (una ventana en la que el guard quedaba efectivamente desactivado). El `ts`
    viaja dentro del archivo y git no lo reescribe, así que exigimos los dos.
    """
    raw = data.get("ts")
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False
    age = now - stamp
    return -60 <= age <= RECENT_WINDOW_SECONDS   # tolera un minuto de desfase de reloj


def _covering_backup(backups_root: Path, product_id: str, now: float):
    """(hay_backup_valido, motivo_si_no). Recolecta todos los candidatos válidos."""
    tail = product_id.split("/")[-1]
    hits = []
    for p in Path(backups_root).glob(f"**/backups/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("productId") != product_id:
            continue
        fields = data.get("fields") or {}
        if not REQUIRED_BACKUP_FIELDS.issubset(set(fields.keys())):
            continue
        # Los valores tienen que ser strings de verdad. Un backup de placeholders
        # satisfacía el guard y después el "undo" restauraba vacío.
        values = [fields.get(k) for k in REQUIRED_BACKUP_FIELDS]
        if any(not isinstance(v, str) for v in values):
            continue
        if all(not v.strip() for v in values):
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        if not _ts_fresh(data, now):
            continue
        hits.append(p)

    if not hits:
        return False, None

    # Los ids numéricos de Shopify son POR TIENDA: el mismo id puede existir en
    # dos tiendas distintas. Si hay backups válidos bajo más de un cliente, no
    # hay forma de saber cuál corresponde al write. Ante la duda, bloqueamos.
    clientes = {c for c in (_client_of(p) for p in hits) if c}
    if len(clientes) > 1:
        return False, (f"hay backups de {sorted(clientes)} para el mismo id de producto. "
                       "Los ids de Shopify son por tienda, así que no puedo saber cuál corresponde.")
    return True, None


def _check_backup(product_id: str, backups_root, now: float):
    if not product_id:
        return "block", "no pude identificar el producto del write"
    ok, ambiguo = _covering_backup(Path(backups_root), product_id, now)
    if ok:
        return "allow", "backup reciente encontrado"
    if ambiguo:
        return "block", ambiguo
    return "block", (f"Sin backup reciente para {product_id} que cubra {sorted(REQUIRED_BACKUP_FIELDS)}. "
                     "El skill debe guardar el backup antes de escribir.")


def evaluate(payload: dict, backups_root, now: float):
    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    if not _is_shopify(tool_name):
        return "allow", "no es un tool de Shopify"

    action = _action(tool_name)

    # 1. Tools de escritura fuera del alcance del v1: bloqueo estructural.
    if action in FORBIDDEN_ACTIONS:
        return "block", (f"'{action}' está fuera del alcance del v1 (solo descripción y SEO). "
                         "Precio, stock, status, colecciones y descuentos no se tocan desde acá.")

    # 2. update-product: solo descripción.
    if action in GUARDED_PRODUCT_ACTIONS:
        if not isinstance(tool_input, dict):
            return "block", "no pude leer los campos del write"
        extra = {k.lower() for k in tool_input.keys()} - ALLOWED_UPDATE_KEYS
        if extra:
            return "block", (f"write fuera de alcance: {sorted(extra)}. "
                             "En el v1 update-product solo puede tocar la descripción.")
        return _check_backup(tool_input.get("id") or "", backups_root, now)

    # 3. graphql_mutation: solo productUpdate de descripción y/o SEO.
    if action == "graphql_mutation":
        text = _graphql_text(tool_input)
        low = text.lower()
        for mutation in FORBIDDEN_MUTATIONS:
            if mutation in low:
                return "block", (f"la mutación '{mutation}' está fuera del alcance del v1 "
                                 "(toca precio, stock, status, publicación o borra).")
        if "productupdate" not in low and not GID_RE.search(text):
            return "allow", "no es un write de producto vigilado"
        keys = _product_input_keys(text) | _variables_product_keys(tool_input)
        extra = keys - ALLOWED_PRODUCT_INPUT_KEYS
        if extra:
            return "block", (f"write fuera de alcance: {sorted(extra)}. "
                             "En el v1 una mutación de producto solo puede tocar descripción y SEO.")
        return _check_backup(_product_id(tool_name, tool_input), backups_root, now)

    return "allow", "no es un write de producto vigilado"


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
        # Ante un error inesperado sobre un tool de Shopify, fallamos CERRADO.
        # Se evalúa solo el nombre del tool (no vuelve a llamar a la lógica que
        # pudo haber lanzado) para que este camino no pueda fallar abierto.
        if _is_shopify(payload.get("tool_name", "")):
            print(f"backup_guard error en un tool de Shopify, bloqueo por seguridad: {e}", file=sys.stderr)
            sys.exit(2)
        sys.exit(0)
    if decision == "block":
        print(reason, file=sys.stderr)
        sys.exit(2)   # exit 2 = bloquea el tool y muestra stderr al modelo
    sys.exit(0)


if __name__ == "__main__":
    main()
