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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deal_policy import load_policy

# Acción (parte después de "Shopify:") que el skill usa para editar un producto:
GUARDED_PRODUCT_ACTIONS = {"update-product"}
# Lo único que un update-product puede traer en el v1:
ALLOWED_UPDATE_KEYS = {"id", "descriptionhtml"}
# Lo único que puede tocar un productUpdate en el v1 (keys de primer nivel):
ALLOWED_PRODUCT_INPUT_KEYS = {"id", "descriptionhtml", "seo"}
# Única mutación de producto del v1: la descripción y el SEO. Lo demás se
# bloquea por no estar acá, no por estar en una lista de prohibidos —el
# catálogo de Shopify tiene 26 mutaciones `product*` y crece.
PRODUCT_WRITE_ALLOWED = {"productupdate"}
# El v1 no escribe colecciones. Vacío a propósito: se bloquea por NO estar acá,
# no por estar en una lista de prohibidos. La familia crece y la blocklist no.
COLLECTION_WRITE_ALLOWED = set()
# Campos que el skill respalda SIEMPRE juntos (contrato con mejorar-descripcion):
REQUIRED_BACKUP_FIELDS = {"descriptionHtml", "seo_title", "seo_description"}
RECENT_WINDOW_SECONDS = 900  # 15 min
GID_RE = re.compile(r"gid://shopify/Product/\d+", re.I)

# --- Estilo del widget (spec §9): cosmético, cerrado, sin techo -------------
# El look que el cliente configura en el builder. No mueve plata, pero se valida
# igual (colores hex, textos acotados, keys cerradas) porque el widget lo pinta.
STYLE_COLOR_KEYS = {"ink", "sage", "taupe", "cream"}
STYLE_TEXT_KEYS = {"label", "badge"}
STYLE_KEYS = STYLE_COLOR_KEYS | STYLE_TEXT_KEYS
STYLE_TEXT_MAXLEN = 40
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

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
    "inventorysetquantities",
    "inventoryadjustquantities",
    "inventoryactivate",
    "collectioncreate",
    "collectionupdate",
    "publishablepublish",
    "publishableunpublish",
}

# --- Ofertas (spec §9) ------------------------------------------------------
# Whitelist CERRADA: toda mutación `discount*` que no esté acá se bloquea.
DISCOUNT_CREATE = {"discountautomaticbasiccreate", "discountcodebasiccreate"}
DISCOUNT_DEACTIVATE = {"discountautomaticdeactivate", "discountcodedeactivate"}
# --- Regalo gratis / BXGY (spec 2026-07-22-regalo-gratis-bxgy §9) -----------
# Va en su PROPIO set y su propia función (`_check_bxgy`), NO en DISCOUNT_CREATE:
# `_check_discount` asume la forma Basic (percentage acotado por maxDiscountPct),
# y un regalo va por discountOnQuantity.effect.percentage, donde "gratis" es 1.0
# (=100%) y maxDiscountPct lo bloquearía siempre. Su techo es de otra naturaleza.
DISCOUNT_BXGY = {"discountautomaticbxgycreate"}

# --- Allowlist de root fields ----------------------------------------------
# EL DEFAULT ESTÁ INVERTIDO A PROPÓSITO: una familia de mutaciones que nadie
# enumeró BLOQUEA. Antes el guard solo conocía `discount*`, `metafieldsSet` y
# `product*`, y todo lo demás caía en un `return allow` final. Pasaban sueltas
# `inventorySetOnHandQuantities`, `inventoryMoveQuantities`, `themeFilesUpsert`,
# `customerUpdate`, `orderUpdate`, `webhookSubscriptionCreate`, `giftCardCreate`
# y `publicationUpdate`, entre otras; y pasaban también montadas sobre una
# operación legítima (un `productUpdate` de descripción adelante, o un
# `discountAutomaticDeactivate` que ni siquiera exige política ni backup).
# `inventorySetQuantities` SÍ estaba en la blocklist, pero el chequeo es por
# substring y `inventorySetOnHandQuantities` no la contiene: es la demostración
# de que enumerar prohibidos no escala contra un catálogo de cientos de
# mutaciones que crece cada release.
#
# La superficie de escritura del v1 es minúscula —descripción, SEO, ofertas—,
# así que la allowlist es a la vez correcta y corta.
ROOT_FIELD_ALLOWED = (PRODUCT_WRITE_ALLOWED | DISCOUNT_CREATE | DISCOUNT_BXGY
                      | DISCOUNT_DEACTIVATE | {"metafieldsset"})


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


def _query_text(tool_input) -> str:
    """SOLO el documento GraphQL, sin las variables pegadas atrás.

    `_graphql_text` sirve para buscar substrings; para leer la ESTRUCTURA del
    documento no, porque las llaves del JSON de las variables se mezclarían con
    las del query y desbaratarían el conteo de profundidad.
    """
    if not isinstance(tool_input, dict):
        return ""
    return tool_input.get("query") or tool_input.get("mutation") or ""


def _root_mutation_fields(query: str) -> list:
    """Los root fields del documento (profundidad 1), en minúscula.

    Recorre el texto contando llaves y paréntesis en vez de regexear nombres
    sueltos, porque hace falta distinguir el root field del campo anidado: en
    `productUpdate(input: {status: DRAFT}) { product { id } }` lo único que se
    ejecuta contra la tienda es `productUpdate`.

    Detalles que importan:
    - Los strings se vacían primero: un valor puede traer llaves.
    - Los alias (`b: productUpdate(...)`) no cuentan como nombre; el root field
      es el identificador que va DESPUÉS del `:`.
    - Solo se cosechan los bloques de una `mutation` (o de un documento anónimo).
      El cuerpo de un `fragment` o de una `query` también vive en profundidad 1
      y son campos de lectura, no writes.
    - Ante cualquier duda devuelve de más, no de menos: quien consume esta lista
      bloquea lo que no reconoce, así que equivocarse es equivocarse CERRADO.
    """
    clean = re.sub(r"#[^\n]*", " ", query or "")
    clean = re.sub(r'"""(?:.|\n)*?"""', ' "" ', clean)
    clean = re.sub(r'"(?:[^"\\]|\\.)*"', ' "" ', clean)
    word_re = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    names, depth, paren, top_kind, last_word = [], 0, 0, "", ""
    i, n = 0, len(clean)
    while i < n:
        c = clean[i]
        if c == "{":
            if depth == 0:
                top_kind = last_word
            depth += 1
        elif c == "}":
            depth -= 1
            if depth <= 0:
                depth, top_kind, last_word = 0, "", ""
        elif c == "(":
            paren += 1
        elif c == ")":
            paren = max(0, paren - 1)
        elif c == "@":
            # Directiva: el nombre que sigue no es un root field.
            m = word_re.match(clean, i + 1)
            i += 1 + (len(m.group(0)) if m else 0)
            continue
        else:
            m = word_re.match(clean, i)
            if m:
                word = m.group(0)
                i += len(word)
                if depth == 0 and paren == 0:
                    last_word = word.lower()
                elif depth == 1 and paren == 0 and top_kind in ("", "mutation"):
                    if not re.match(r"\s*:", clean[i:]):     # no es un alias
                        names.append(word.lower())
                continue
        i += 1
    return names


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
    """Unión de las keys de primer nivel de TODOS los objetos `product:`/`input:`.

    `finditer`, no `search`. La ironía vale la pena anotarla: el commit c9b2dea
    cerró exactamente esta clase de agujero para los NOMBRES de las mutaciones
    —dejar de mirar solo el primer match de un documento con varios root
    fields— y dejó vivo el mismo `re.search` dos funciones más abajo, en el
    control de CAMPOS. Con el primer match alcanzaba con poner un
    `productUpdate` legítimo adelante:

        mutation { productUpdate(input: {id: "...", descriptionHtml: "<p>ok</p>"}) { product { id } }
                   b: productUpdate(input: {id: "...", status: DRAFT, handle: "robado"}) { product { id } } }

    El primer objeto daba {id, descriptionhtml}, `extra` quedaba vacío y el
    write pasaba con el backup de la descripción como llave. El tell era que
    poniendo el objeto malo PRIMERO bloqueaba: el mismo documento, el mismo
    efecto sobre la tienda, distinta decisión según el orden.

    Unir en vez de elegir cubre además el caso de nombres de argumento mezclados
    (`product:` en una y `input:` en la otra).
    """
    keys = set()
    for m in re.finditer(r"\b(?:product|input)\s*:\s*\{", text, re.I):
        keys |= _top_level_keys(_balanced_object(text, m.end() - 1))
    return keys


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


def _covering_deal_backup(backups_root, product_id: str, now: float):
    """(hay_backup_valido, motivo). Backup de OFERTA, no de descripción.

    Dos condiciones simultáneas separan los tipos (spec §7.4): la ruta
    (`backups/deals/`) y `kind == "deal"`. Con una sola, un backup de
    descripción podría habilitar un write de descuento.

    Frescura DOBLE (mtime + ts), igual que `_covering_backup`: cualquier
    operación de git refresca el mtime de todo el checkout y resucitaría
    backups viejos.
    """
    tail = product_id.split("/")[-1]
    for p in Path(backups_root).glob(f"**/backups/deals/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("kind") != "deal":
            continue
        if data.get("productId") != product_id:
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        if not _ts_fresh(data, now):
            continue
        return True, None
    return False, (f"Sin backup de oferta reciente para {product_id}. "
                   "El skill debe guardar el backup antes de escribir.")


def _covering_style_backup(backups_root, product_id: str, now: float):
    """(hay_backup_valido, motivo). Backup de ESTILO, discriminado por ruta
    (`backups/style/`) y `kind == "style"` — las dos, igual que el de oferta.

    Discriminador propio a propósito (spec §9.1): un backup de estilo NO puede
    habilitar un write de plata (`worker.deal` / `discount*Create`) ni al revés.
    El aislamiento vale por ruta Y por kind, defensa en profundidad idéntica al
    de oferta. Frescura doble (mtime + ts), igual que `_covering_deal_backup`.
    """
    tail = product_id.split("/")[-1]
    for p in Path(backups_root).glob(f"**/backups/style/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("kind") != "style":
            continue
        if data.get("productId") != product_id:
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        if not _ts_fresh(data, now):
            continue
        return True, None
    return False, (f"Sin backup de estilo reciente para {product_id}. "
                   "El skill debe guardar el backup de estilo antes de escribir.")


def _discount_mutations(text: str) -> list:
    """TODAS las mutaciones `discount*` del documento, en minúscula.

    Devuelve la lista completa, NO la primera. No es una optimización pendiente:
    con `re.search` (primer match) este documento pasaba entero,

        mutation { discountAutomaticDeactivate(id: "...") { ... }
                   discountAutomaticDelete(id: "...") { deletedId } }

    porque matcheaba el `Deactivate`, que se permite sin condiciones (§9.8), se
    retornaba "allow" y el `Delete` de atrás nunca se miraba. Las mutaciones de
    descuento no están en `FORBIDDEN_MUTATIONS` —se sacaron a propósito para
    que las cubra esta whitelist—, así que el loop de la blocklist tampoco lo
    frenaba: se borraba un descuento usando la compensación como llave, que es
    exactamente el invariante que el milestone enforcea por código.

    Case-sensitive sobre el prefijo en minúscula a propósito: así NO matchea
    `"gid://shopify/DiscountAutomaticNode/111"` dentro del valor de un
    metafield. Puede dar falso positivo con un campo de selección como
    `discountApplications(first:5)`, y eso falla CERRADO (bloquea), que es el
    lado correcto para equivocarse.
    """
    return [m.lower() for m in re.findall(r"\b(discount[A-Za-z0-9]*)\s*\(", text)]


def _product_mutations(text: str) -> list:
    """Todas las mutaciones `product*` del documento, en minúscula.

    Espejo de `_discount_mutations`, y se usa para lo mismo: saber QUÉ asuntos
    toca el documento antes de decidir. Detecta también las que el guard no
    nombra en ninguna lista (`productSet`, `productCreate`...), que es lo que
    permitía colar un write de producto detrás de una oferta.

    Exige el paréntesis pegado al nombre a propósito: así `"productsToAdd":
    [...]` dentro de las variables de un descuento —que es una key JSON, no una
    llamada— NO cuenta como write de producto. Sin eso, toda oferta legítima
    quedaría clasificada como documento mixto.
    """
    return [m.lower() for m in re.findall(r"\b(product[A-Za-z0-9]*)\s*\(", text)]


def _collection_mutations(text: str) -> list:
    """Todas las mutaciones `collection*` del documento, en minúscula.

    Misma historia que `product*`: `FORBIDDEN_MUTATIONS` nombraba solo
    `collectionCreate` y `collectionUpdate`, así que `collectionDelete`,
    `collectionDuplicate` y `collectionReorderProducts` pasaban. `permissions.deny`
    cierra los TOOLS del connector, no el camino GraphQL.
    """
    return [m.lower() for m in re.findall(r"\b(collection[A-Za-z0-9]*)\s*\(", text)]


def _check_discount(names, tool_input, backups_root, now: float):
    """Whitelist de descuentos con techo (spec §9.0-9.4).

    Recibe TODAS las mutaciones del documento: cada una tiene que ser
    aceptable por sí sola. Ninguna se vuelve inocente por la compañía.
    """
    fuera = [n for n in names if n not in DISCOUNT_CREATE | DISCOUNT_DEACTIVATE]
    if fuera:
        return "block", (f"'{fuera[0]}' no está en la whitelist de descuentos. "
                         "Solo se permiten crear (con techo) y desactivar.")

    creates = [n for n in names if n in DISCOUNT_CREATE]
    if not creates:
        # Puras desactivaciones: sin condiciones a propósito (spec §9.8), la
        # compensación no puede depender de un estado que ella misma modifica.
        return "allow", "desactivar siempre está permitido"

    # Un solo create por documento: el objeto que se valida sale de `variables`
    # y es UNO solo, así que con dos creates el segundo viajaría sin techo.
    if len(creates) > 1:
        return "block", ("hay más de una oferta en la misma operación y solo puedo "
                         "verificar el techo de una. Mandalas de a una.")
    name = creates[0]

    policy = load_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de ofertas única (deal-policy.json). "
                         "Sin techo que aplicar, no se crean descuentos.")

    if name == "discountcodebasiccreate" and "codes" not in policy.get("enabledStrategies", []):
        return "block", "la estrategia de códigos no está habilitada para este cliente."

    # Un solo descuento en las variables. Ver `_discount_inputs`: con más de uno
    # no hay forma de saber cuál ejecuta el servidor, y validar "el primero" era
    # una invitación a mandar un señuelo manso adelante.
    candidatos = _discount_inputs(tool_input)
    if len(candidatos) > 1:
        return "block", ("las variables del pedido traen más de un descuento y no puedo "
                         "saber cuál se aplica. Mandá uno solo.")
    d = candidatos[0] if candidatos else {}
    if not d:
        # Distinguir "no encontré el objeto" de "el objeto no tiene endsAt" NO es
        # cosmético. `_discount_input` solo lee `variables`; con el payload escrito
        # inline en el query devuelve {}, que es un dict, así que el isinstance
        # pasaba y la ejecución caía en el chequeo de `endsAt` — respondiendo
        # "toda oferta necesita fecha de fin" sobre un documento que tiene el
        # endsAt a la vista. El mensaje mandaba a arreglar el lugar equivocado.
        return "block", ("no encontré los datos del descuento en las variables del pedido. "
                         "Tienen que ir en `variables`, no escritos dentro del query.")

    # endsAt obligatorio y duración acotada
    starts, ends = d.get("startsAt"), d.get("endsAt")
    if policy.get("requireEndsAt") and not ends:
        return "block", "toda oferta necesita fecha de fin."
    if ends:
        days = _duration_days(starts, ends)
        if days is None:
            return "block", "no pude leer las fechas de la oferta."
        if days > policy["maxDurationDays"]:
            return "block", (f"la oferta dura {days} días y el máximo es "
                             f"{policy['maxDurationDays']}.")

    # Techo de porcentaje. OJO: la API va en fracción y el techo en entero.
    pct = _percentage_int(d)
    if pct is None:
        return "block", "no pude leer el porcentaje del descuento."
    if pct > policy["maxDiscountPct"]:
        return "block", (f"el descuento es de {pct}% y el máximo para este "
                         f"cliente es {policy['maxDiscountPct']}%.")

    # Scope: ids explícitos, nunca `all`, nunca colección (salvo que se habilite)
    items = ((d.get("customerGets") or {}).get("items")) or {}
    if items.get("all"):
        return "block", "un descuento sobre TODO el catálogo no se permite."
    if "collections" in items and not policy.get("allowCollectionScope"):
        return "block", "un descuento a nivel colección no se permite para este cliente."
    products = items.get("products") or {}
    ids = (products.get("productsToAdd") or []) + (products.get("productVariantsToAdd") or [])
    if not ids:
        return "block", "el descuento tiene que apuntar a productos o variantes explícitos."

    # El backup se busca por el PRODUCTO, y el gid de variante no sirve para eso
    # ("/Product/" no es substring de "gid://shopify/ProductVariant/5"). Por eso
    # se exige `productId` como variable explícita en vez de intentar derivarlo.
    product_gid = ((tool_input or {}).get("variables") or {}).get("productId")
    if not isinstance(product_gid, str) or "/Product/" not in product_gid:
        return "block", ("la mutación tiene que traer `productId` en las variables, "
                         "con el gid del producto de la oferta.")

    ok, why = _covering_deal_backup(backups_root, product_gid, now)
    return ("allow", "ok") if ok else ("block", why)


def _discount_inputs(tool_input) -> list:
    """TODOS los objetos de `variables` que tienen forma de descuento.

    Devuelve la lista completa, NO el primero. Con el primero, una variable
    SEÑUELO derrotaba todos los techos de golpe: el query nombra la variable que
    realmente usa, el guard nunca correlacionaba las dos cosas, y las variables
    no declaradas el servidor las ignora sin chistar.

        query:     mutation ($real: DiscountAutomaticBasicInput!) { discountAutomaticBasicCreate(automaticBasicDiscount: $real) {...} }
        variables: { "aaa_decoy": <5%, 12 días, un producto>,
                     "real":      <100%, 10 años, una colección entera> }

    El guard validaba `aaa_decoy` (que no ejecuta nadie) y aprobaba `real`.
    Ordenar alfabéticamente el señuelo alcanzaba, porque los dicts de JSON
    conservan el orden de inserción.

    No intentamos parsear QUÉ variable referencia el query: correlacionar es
    frágil (alias, fragmentos, defaults, varias operaciones en un documento) y
    un error de parseo ahí falla ABIERTO. Negarse ante la ambigüedad no. Una
    llamada legítima trae exactamente un descuento.
    """
    if not isinstance(tool_input, dict):
        return []
    variables = tool_input.get("variables")
    if not isinstance(variables, dict):
        return []
    return [v for v in variables.values()
            if isinstance(v, dict) and "customerGets" in v]


def _percentage_int(d: dict):
    """Porcentaje como ENTERO 0-100.

    TRAMPA (spec §9.4): la API toma fracción (0.10 == 10%) y la política está
    en entero (30 == 30%). Comparar sin convertir deja pasar 0.7 (=70%) contra
    un techo de 30, porque 0.7 <= 30.
    """
    value = ((d.get("customerGets") or {}).get("value")) or {}
    raw = value.get("percentage")
    if raw is None:
        return None
    try:
        return round(float(raw) * 100)
    except (TypeError, ValueError):
        return None


# --- Regalo gratis / BXGY (spec 2026-07-22-regalo-gratis-bxgy §9) -----------

def _as_pos_int(x):
    """Entero positivo desde int o string de dígitos. None si no lo es.

    Las cantidades de la API son `UnsignedInt64` y viajan como string ("2").
    Estricto a propósito: un float (`2.9`) o un string no-dígito no cuentan —
    `int(2.9)` truncaría en silencio, que es justo lo que un guard no quiere.
    """
    if isinstance(x, bool):
        return None
    if isinstance(x, int):
        return x if x >= 0 else None
    if isinstance(x, str) and x.strip().isdigit():
        return int(x.strip())
    return None


def _bxgy_inputs(tool_input) -> list:
    """Objetos de `variables` con forma de BXGY: traen customerBuys Y customerGets.

    Mismo criterio anti-señuelo que `_discount_inputs`: devuelve TODOS, y con más
    de uno el guard bloquea en vez de adivinar cuál ejecuta el servidor. Un Basic
    no tiene `customerBuys`, así que el filtro los separa.
    """
    if not isinstance(tool_input, dict):
        return []
    variables = tool_input.get("variables")
    if not isinstance(variables, dict):
        return []
    return [v for v in variables.values()
            if isinstance(v, dict) and "customerBuys" in v and "customerGets" in v]


def _gift_effect_pct_int(d):
    """(pct_entero, error). El regalo VA por `customerGets.value.discountOnQuantity.
    effect.percentage`. BXGY NO soporta `percentage` ni `discountAmount` al tope de
    `value` (lo dice el schema), así que verlos ahí es forma inválida → 'unsupported'.

    TRAMPA de unidades igual que escalones (§9.4): la API va en fracción 0.0-1.0,
    el techo en entero. 'gratis' = 1.0 → 100. Convertir antes de comparar.
    """
    value = ((d.get("customerGets") or {}).get("value")) or {}
    if "percentage" in value or "discountAmount" in value:
        return None, "unsupported"
    effect = ((value.get("discountOnQuantity") or {}).get("effect")) or {}
    raw = effect.get("percentage")
    if raw is None:
        return None, "missing"
    try:
        return round(float(raw) * 100), None
    except (TypeError, ValueError):
        return None, "missing"


def _bxgy_single_product(items):
    """(gid_de_producto, error). Exactamente UN producto explícito, sin `all` ni
    colección ni variantes. v1 del regalo es producto→producto; el gid de variante
    no sirve para el mismo/cruzado ni para buscar el backup.
    """
    if not isinstance(items, dict):
        return None, "missing"
    if items.get("all"):
        return None, "all"
    if "collections" in items:
        return None, "collections"
    products = items.get("products") or {}
    if products.get("productVariantsToAdd"):
        return None, "variants"
    ids = products.get("productsToAdd") or []
    if len(ids) != 1:
        return None, ("multi" if ids else "missing")
    gid = ids[0]
    if not (isinstance(gid, str) and "/Product/" in gid):
        return None, "bad"
    return gid, None


def _gift_ceilings(policy):
    """(maxGiftPct, maxGetQty, minBuyGetRatio) o None si el cliente no los tiene.

    Claves OPCIONALES en la política (no rompen a escalones): si faltan, el regalo
    no se puede crear. Fail closed — un cliente sin techo de regalos no regala.
    """
    mg, mq, mr = policy.get("maxGiftPct"), policy.get("maxGetQty"), policy.get("minBuyGetRatio")
    if all(isinstance(x, int) and not isinstance(x, bool) for x in (mg, mq, mr)):
        return mg, mq, mr
    return None


def _bxgy_scope_ok(policy, buy_gid, get_gid, buy_qty, get_qty, min_ratio):
    """Motivo de bloqueo del alcance del regalo, o None. Compartido por el create
    (donde los gids salen de la mutación) y el metafield (donde salen del JSON)."""
    if buy_gid == get_gid:
        # Mismo producto: el ratio evita 'comprá 1 llevá 1' (=50% off encubierto),
        # que saltearía el maxDiscountPct de escalones por otra vía.
        if buy_qty < min_ratio * get_qty:
            return (f"en el mismo producto hay que comprar al menos {min_ratio} por cada "
                    f"unidad regalada; pedís comprar {buy_qty} y regalar {get_qty}.")
        return None
    # Cruzado: solo si está habilitado y el regalo está en la lista curada.
    if not policy.get("allowCrossProductGift"):
        return "los regalos de otro producto no están habilitados para este cliente."
    if get_gid not in (policy.get("giftableProducts") or []):
        return "ese producto no está en la lista de regalables del cliente."
    return None


def _check_bxgy(names, tool_input, backups_root, now: float):
    """Whitelist del regalo (spec §9.1). Recibe TODAS las mutaciones del documento;
    cada una tiene que ser aceptable por sí sola (ninguna se vuelve inocente por
    compartir documento con un deactivate)."""
    fuera = [n for n in names if n not in DISCOUNT_BXGY | DISCOUNT_DEACTIVATE]
    if fuera:
        return "block", (f"'{fuera[0]}' no puede ir junto a un regalo en la misma operación.")
    creates = [n for n in names if n in DISCOUNT_BXGY]
    if len(creates) > 1:
        return "block", "hay más de un regalo en la misma operación. Mandalos de a uno."

    policy = load_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de ofertas única (deal-policy.json). "
                         "Sin techo que aplicar, no se crean regalos.")
    ceils = _gift_ceilings(policy)
    if ceils is None:
        return "block", "este cliente no tiene configurado el techo de regalos."
    max_gift, max_get, min_ratio = ceils

    cands = _bxgy_inputs(tool_input)
    if len(cands) > 1:
        return "block", ("las variables traen más de un regalo y no puedo saber cuál se "
                         "aplica. Mandá uno solo.")
    d = cands[0] if cands else {}
    if not d:
        return "block", ("no encontré los datos del regalo en las variables. "
                         "Tienen que ir en `variables`, no escritos dentro del query.")

    # endsAt obligatorio y duración acotada (mismo criterio que escalones)
    starts, ends = d.get("startsAt"), d.get("endsAt")
    if policy.get("requireEndsAt") and not ends:
        return "block", "todo regalo necesita fecha de fin."
    if ends:
        days = _duration_days(starts, ends)
        if days is None:
            return "block", "no pude leer las fechas del regalo."
        if days > policy["maxDurationDays"]:
            return "block", (f"el regalo dura {days} días y el máximo es "
                             f"{policy['maxDurationDays']}.")

    # usesPerOrderLimit forzado a 1: el regalo no se multiplica solo en el carrito.
    if _as_pos_int(d.get("usesPerOrderLimit")) != 1:
        return "block", "el regalo tiene que limitarse a una vez por pedido (usesPerOrderLimit: 1)."

    # % del regalo: solo discountOnQuantity.effect.percentage, con la trampa de unidades.
    pct, err = _gift_effect_pct_int(d)
    if err == "unsupported":
        return "block", ("el regalo tiene que expresarse como 'discountOnQuantity'; "
                         "un BXGY no soporta percentage ni discountAmount al tope.")
    if pct is None:
        return "block", "no pude leer el porcentaje del regalo."
    if pct > max_gift:
        return "block", (f"el regalo descuenta {pct}% y el máximo para este cliente "
                         f"es {max_gift}%.")

    # Cantidad regalada
    get_qty = _as_pos_int(((d.get("customerGets") or {}).get("value") or {})
                          .get("discountOnQuantity", {}).get("quantity"))
    if not get_qty or get_qty < 1:
        return "block", "no pude leer cuántas unidades regala el descuento."
    if get_qty > max_get:
        return "block", f"el regalo es de {get_qty} unidades y el máximo es {max_get}."

    # Scope: exactamente un producto explícito en la compra y en el regalo.
    buy_gid, be = _bxgy_single_product((d.get("customerBuys") or {}).get("items"))
    get_gid, ge = _bxgy_single_product((d.get("customerGets") or {}).get("items"))
    if "all" in (be, ge):
        return "block", "un regalo sobre TODO el catálogo no se permite."
    if "collections" in (be, ge):
        return "block", "un regalo a nivel colección no se permite."
    if be or ge:
        return "block", ("el regalo tiene que apuntar a un producto explícito para comprar "
                         "y uno para regalar.")

    buy_qty = _as_pos_int((d.get("customerBuys") or {}).get("value", {}).get("quantity"))
    if not buy_qty or buy_qty < 1:
        return "block", "no pude leer cuántas unidades hay que comprar."

    why = _bxgy_scope_ok(policy, buy_gid, get_gid, buy_qty, get_qty, min_ratio)
    if why:
        return "block", why

    # El backup se busca por el producto COMPRADO (P), que es el que configura el
    # cliente y sobre el que se escribe el metafield worker.deal.
    product_gid = ((tool_input or {}).get("variables") or {}).get("productId")
    if not isinstance(product_gid, str) or "/Product/" not in product_gid:
        return "block", ("la mutación tiene que traer `productId` en las variables, "
                         "con el gid del producto de la oferta.")
    ok, why = _covering_deal_backup(backups_root, product_gid, now)
    return ("allow", "ok") if ok else ("block", why)


def _check_bxgy_metafield(data, policy):
    """Reglas del schema `type:"bxgy"` de §5 (motivo de bloqueo, o None).

    El widget lee del metafield, no del descuento: un metafield con pct 100 y un
    ref a un descuento acotado produciría la divergencia widget↔carrito. Por eso el
    techo de regalo también se enforcea acá, no solo en el create.
    """
    ceils = _gift_ceilings(policy)
    if ceils is None:
        return "este cliente no tiene configurado el techo de regalos."
    max_gift, max_get, min_ratio = ceils

    scope = data.get("scope")
    if scope not in ("same", "cross"):
        return "el regalo tiene que ser del mismo producto o cruzado."
    buy, get = data.get("buy") or {}, data.get("get") or {}
    bq, gq, gpct = buy.get("qty"), get.get("qty"), get.get("pct")
    if not (isinstance(bq, int) and not isinstance(bq, bool) and bq >= 1):
        return "la compra requerida del regalo no es válida."
    if not (isinstance(gq, int) and not isinstance(gq, bool) and gq >= 1):
        return "la cantidad regalada no es válida."
    if gq > max_get:
        return f"el regalo es de {gq} unidades y el máximo es {max_get}."
    if not (isinstance(gpct, int) and not isinstance(gpct, bool) and 0 <= gpct <= 100):
        return "el porcentaje del regalo tiene que ser un entero entre 0 y 100."
    if gpct > max_gift:
        return f"el regalo descuenta {gpct}% y el máximo es {max_gift}%."
    bp, gp = buy.get("product"), get.get("product")
    if not (isinstance(bp, str) and "/Product/" in bp):
        return "falta el producto que se compra."
    if not (isinstance(gp, str) and "/Product/" in gp):
        return "falta el producto que se regala."
    if scope == "same" and bp != gp:
        return "un regalo del mismo producto tiene que comprar y regalar el mismo producto."
    if scope == "cross" and bp == gp:
        return "un regalo cruzado tiene que ser de otro producto."
    return _bxgy_scope_ok(policy, bp, gp, bq, gq, min_ratio)


def _duration_days(starts, ends):
    def parse(x):
        if not isinstance(x, str) or not x.strip():
            return None
        try:
            return datetime.fromisoformat(x.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    e = parse(ends)
    if e is None:
        return None
    s = parse(starts) or datetime.now(e.tzinfo)
    return (e - s).days


def _check_metafield(tool_input, backups_root, now: float):
    """metafieldsSet: solo `worker.deal`, con techo (spec §9.1, §9.3)."""
    variables = (tool_input or {}).get("variables") or {}
    entries = []
    for value in variables.values():
        if isinstance(value, list):
            entries.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict) and ("namespace" in value or "ownerId" in value):
            entries.append(value)
    if not entries:
        return "block", "no pude leer el metafield que se está escribiendo."

    # Una sola entrada, por el mismo motivo que un solo descuento. Acá el
    # esconderse era todavía más barato: el loop de abajo valida TODAS las
    # entradas, pero `owner` se pisa en cada vuelta (`owner = e.get("ownerId") or
    # owner`), así que gana la ÚLTIMA. Dos entradas worker.deal impecables sobre
    # productos distintos —la primera sobre un producto sin backup, la segunda
    # sobre el que sí lo tiene— pasaban enteras: el backup de la segunda
    # habilitaba la escritura de la primera, que quedaba sin undo posible.
    if len(entries) > 1:
        return "block", ("el pedido escribe más de una oferta a la vez y solo puedo "
                         "verificar el respaldo de una. Mandalas de a una.")

    # Routing por key: worker.style es cosmético (sin techo) → su propio check,
    # ANTES de cargar la política de plata (el estilo no depende de deal-policy).
    if entries[0].get("namespace") == "worker" and entries[0].get("key") == "style":
        return _check_style(tool_input, backups_root, now)

    policy = load_policy(backups_root)
    if policy is None:
        return "block", "no encontré una política de ofertas única (deal-policy.json)."

    owner = ""
    for e in entries:
        if e.get("namespace") != "worker" or e.get("key") != "deal":
            return "block", (f"solo se puede escribir el metafield worker.deal, "
                             f"no {e.get('namespace')}.{e.get('key')}.")
        owner = e.get("ownerId") or owner
        try:
            data = json.loads(e.get("value") or "{}")
        except Exception:
            return "block", "el contenido de la oferta no es JSON válido."
        # Ramifica por tipo de oferta: un regalo (type:"bxgy") NO tiene `tiers`,
        # así que aplicarle el schema de escalones lo bloquearía siempre. El campo
        # `type` estaba plantado forward-compat; este milestone por fin lo lee.
        if data.get("type") == "bxgy":
            why = _check_bxgy_metafield(data, policy)
            if why:
                return "block", why
            continue
        tiers = data.get("tiers")
        if not isinstance(tiers, list):
            return "block", "la oferta no tiene escalones."
        if len(tiers) > policy["maxTiers"]:
            return "block", (f"la oferta tiene {len(tiers)} escalones y el máximo "
                             f"es {policy['maxTiers']}.")
        why = _check_tiers_schema(tiers, policy)
        if why:
            return "block", why

    # Mismo criterio que `_check_discount`: sin un gid de producto reconocible no
    # hay contra qué buscar el backup. Sin esta guarda, un `metafieldsSet` sin
    # `ownerId` deja `owner` vacío, el glob queda `**/backups/deals/-*.json`, y un
    # archivo llamado `-lo-que-sea.json` lo satisface. Bloqueaba de casualidad —
    # porque ese nombre no suele existir—, no por diseño. Vacío es DESCONOCIDO.
    if "/Product/" not in owner:
        return "block", ("no pude identificar sobre qué producto se está escribiendo la oferta. "
                         "El metafield tiene que traer el id del producto.")

    ok, why = _covering_deal_backup(backups_root, owner, now)
    return ("allow", "ok") if ok else ("block", why)


def _check_style(tool_input, backups_root, now: float):
    """metafieldsSet de `worker.style`: cosmético, cerrado, sin techo (spec §9).

    No mueve plata, así que no carga `deal-policy.json`. Pero valida igual: keys
    de un set cerrado, colores hex (para que un valor no inyecte CSS por la var),
    textos acotados sin `<`/`>`. Y exige backup de ESTILO (`_covering_style_backup`,
    kind y ruta propios) — nunca el de oferta.
    """
    variables = (tool_input or {}).get("variables") or {}
    entries = []
    for value in variables.values():
        if isinstance(value, list):
            entries.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict) and ("namespace" in value or "ownerId" in value):
            entries.append(value)
    if not entries:
        return "block", "no pude leer el metafield de estilo."
    if len(entries) > 1:
        return "block", "un estilo por vez."
    e = entries[0]
    if e.get("namespace") != "worker" or e.get("key") != "style":
        return "block", f"solo worker.style, no {e.get('namespace')}.{e.get('key')}."
    owner = e.get("ownerId") or ""
    if "/Product/" not in owner:
        return "block", "el estilo tiene que traer el id del producto."
    try:
        data = json.loads(e.get("value") or "{}")
    except Exception:
        return "block", "el estilo no es JSON válido."
    if not isinstance(data, dict):
        return "block", "el estilo tiene que ser un objeto."
    for k, v in data.items():
        if k not in STYLE_KEYS:
            return "block", f"clave de estilo desconocida: {k}."
        if k in STYLE_COLOR_KEYS:
            if not (isinstance(v, str) and HEX_RE.match(v)):
                return "block", f"{k} tiene que ser un color hex (#RRGGBB)."
        else:
            if not isinstance(v, str) or len(v) > STYLE_TEXT_MAXLEN or "<" in v or ">" in v:
                return "block", f"{k} tiene que ser texto de hasta {STYLE_TEXT_MAXLEN} sin < ni >."
    ok, why = _covering_style_backup(backups_root, owner, now)
    return ("allow", "ok") if ok else ("block", why)


def _check_tiers_schema(tiers, policy):
    """Reglas del schema de §5. Devuelve el motivo del bloqueo, o None.

    §5 del spec dice que estas reglas están "todas verificadas por el guard".
    Sin esto, esa afirmación sería falsa y el widget podría recibir una oferta
    incoherente (escalones desordenados, dos destacados, cantidades repetidas).
    """
    if not tiers:
        return None                      # tiers: [] es "sacar la oferta", válido
    qtys = []
    for t in tiers:
        if not isinstance(t, dict):
            return "cada escalón tiene que ser un objeto."
        qty, pct = t.get("qty"), t.get("pct")
        if not isinstance(qty, int) or qty < 1:
            return "cada escalón necesita una cantidad entera de 1 o más."
        if not isinstance(pct, int) or not (0 <= pct <= 100):
            return "cada escalón necesita un porcentaje entero entre 0 y 100."
        if pct > policy["maxDiscountPct"]:
            return (f"un escalón tiene {pct}% y el máximo para este cliente es "
                    f"{policy['maxDiscountPct']}%.")
        qtys.append(qty)
    if qtys != sorted(qtys):
        return "los escalones tienen que estar ordenados de menor a mayor cantidad."
    if len(set(qtys)) != len(qtys):
        return "hay dos escalones con la misma cantidad."
    if tiers[0].get("pct") != 0:
        return "el primer escalón no puede tener descuento."
    destacados = sum(1 for t in tiers if t.get("highlight"))
    if destacados != 1:
        return "tiene que haber exactamente un escalón destacado."
    return None


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
        # 1. La blocklist general SIEMPRE primero: si está en el documento
        #    bloquea, venga acompañada de lo que venga.
        for mutation in FORBIDDEN_MUTATIONS:
            if mutation in low:
                return "block", (f"la mutación '{mutation}' está fuera del alcance del v1 "
                                 "(toca precio, stock, status, publicación o borra).")

        # 2. ALLOWLIST DE ROOT FIELDS: el default se invierte.
        #
        # Todo lo que sigue (asuntos, whitelists por familia, control de campos)
        # solo sabe razonar sobre `discount*`, `metafieldsSet` y `product*`. El
        # resto del catálogo del Admin API —cientos de mutaciones, y más en cada
        # release— llegaba al `return allow` del final. Enumerar prohibidos es
        # perseguir un blanco móvil; enumerar permitidos no, porque la superficie
        # de escritura del v1 no se mueve.
        #
        # Va acá arriba, antes de identificar asuntos, para que ninguna operación
        # legítima adelante pueda servir de vehículo a una desconocida atrás.
        roots = _root_mutation_fields(_query_text(tool_input))
        if not roots:
            # VACÍO ES DESCONOCIDO, NO LIMPIO: mismo criterio que el control de
            # campos. Si no pudimos leer qué se ejecuta, no lo dejamos ejecutar.
            return "block", ("no pude leer qué mutaciones ejecuta este pedido. "
                             "La operación tiene que venir en `query`, como un documento GraphQL.")
        desconocidas = [r for r in roots if r not in ROOT_FIELD_ALLOWED]
        if desconocidas:
            return "block", (f"la mutación '{desconocidas[0]}' está fuera del alcance del v1. "
                             "Desde acá solo se escriben la descripción y el SEO de un producto, "
                             "y las ofertas por cantidad.")

        # 3. UN SOLO ASUNTO POR DOCUMENTO.
        #
        # GraphQL admite varios root fields en un mismo documento. Esta rama
        # antes retornaba apenas reconocía el primero, así que cada dispatch
        # nuevo podía tapar a todos los demás: un `discountAutomaticDeactivate`
        # adelante —que se permite sin condiciones, §9.8— colaba atrás un
        # delete, un `productUpdate` con `status`/`handle`, o mañana un
        # `metafieldsSet`. Parchear par por par es combinatorio: cada dispatch
        # nuevo se multiplica contra todos los que ya están.
        #
        # Así que primero se IDENTIFICA qué asuntos toca el documento y recién
        # después se decide. Mezclar dos bloquea: el skill no tiene ningún
        # motivo legítimo para mandar una oferta, un metafield y una edición de
        # producto en el mismo pedido, y negarse es mucho más fácil de razonar
        # que intentar satisfacer todas las combinaciones a la vez.
        names = _discount_mutations(text)
        asuntos = []
        if names:
            asuntos.append("ofertas")
        if "metafieldsset" in low:
            asuntos.append("metafields")
        if _product_mutations(text):
            asuntos.append("cambios de producto")
        if len(asuntos) > 1:
            return "block", (f"esta operación mezcla {' y '.join(asuntos)} en un mismo pedido "
                             "y no puedo verificar las dos cosas juntas. Mandalas por separado.")

        if names:
            # El regalo (BXGY) tiene su propia función y su propio techo: NO reusa
            # `_check_discount`, que asume la forma Basic acotada por maxDiscountPct.
            if any(n in DISCOUNT_BXGY for n in names):
                return _check_bxgy(names, tool_input, backups_root, now)
            return _check_discount(names, tool_input, backups_root, now)

        # 3. Metafield de oferta. ANTES del fallthrough por GID_RE.
        if "metafieldsset" in low:
            return _check_metafield(tool_input, backups_root, now)

        # Familia de producto: whitelist CERRADA, por nombre y antes del control
        # de campos. El control de campos solo mira el objeto `input: {...}` /
        # `product: {...}`, así que las mutaciones que reciben `productId:` más
        # arrays (`options:`, `positions:`, `moves:`, `sellingPlanGroupIds:`)
        # no exponen ninguna key: `_product_input_keys` devuelve un conjunto
        # VACÍO, el chequeo de alcance pasa en el vacío y quedaban gobernadas
        # solo por el backup — o sea que un backup de descripción fresco era una
        # llave de 15 minutos para duplicar el producto, reordenar variantes o
        # cambiarle las opciones. Eran 21 de las 26 mutaciones `product*`.
        fuera_de_alcance = [m for m in _product_mutations(text)
                            if m not in PRODUCT_WRITE_ALLOWED]
        if fuera_de_alcance:
            return "block", (f"la mutación '{fuera_de_alcance[0]}' está fuera del alcance del v1. "
                             "Lo único que se puede escribir de un producto es su descripción y su SEO.")

        # Colecciones: misma whitelist cerrada, y vacía.
        col = [m for m in _collection_mutations(text) if m not in COLLECTION_WRITE_ALLOWED]
        if col:
            return "block", (f"la mutación '{col[0]}' está fuera del alcance del v1: "
                             "las colecciones no se tocan desde acá.")

        # El gid suelto sigue siendo señal de write de producto: cubre una
        # mutación parametrizada cuyo nombre no reconocemos. Queda acá abajo, y
        # no como asunto, porque las ofertas legítimas traen gids de producto
        # en `productsToAdd` sin ser un write de producto.
        if "productupdate" not in low and not GID_RE.search(text):
            return "allow", "no es un write de producto vigilado"
        keys = _product_input_keys(text) | _variables_product_keys(tool_input)
        # VACÍO ES DESCONOCIDO, NO LIMPIO. Un conjunto de keys sin `id` significa
        # que no pudimos parsear el payload, no que el write venga limpio.
        # Tratarlo como "no hay nada fuera de alcance" es la raíz de toda esta
        # clase de agujeros, y seguía viva por otra vía: en
        # `productUpdate(input:$input)` con un `input` que no trae `id`,
        # `_variables_product_keys` no cosecha nada (solo mira los dicts que
        # tienen `id`), `extra` queda vacío, y el write pasaba con `handle` y
        # `status` adentro. Hoy solo lo salvaba que Shopify exige `input.id`
        # del lado del servidor — o sea, la validación de la API, no el guard.
        if "id" not in keys:
            return "block", ("no pude identificar qué campos toca este write de producto. "
                             "La mutación tiene que traer el id del producto junto con los campos.")
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
