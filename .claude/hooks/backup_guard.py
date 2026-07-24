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
# Mutaciones de producto permitidas. `productupdate` escribe la descripción y el
# SEO (v1). W3 F2 suma el alta (`productset`, en status DRAFT y con campos
# cerrados) y el undo=archivar (`productchangestatus`, solo destino ARCHIVED);
# ambas se rutean por NOMBRE en `evaluate` a `_check_create`/`_check_status_change`,
# nunca al control de campos de `productupdate`. Lo demás se bloquea por no estar
# acá, no por estar en una lista de prohibidos —el catálogo de Shopify tiene 26
# mutaciones `product*` y crece.
PRODUCT_WRITE_ALLOWED = {"productupdate", "productset", "productchangestatus"}
# El v1 no escribe colecciones. Vacío a propósito: se bloquea por NO estar acá,
# no por estar en una lista de prohibidos. La familia crece y la blocklist no.
COLLECTION_WRITE_ALLOWED = set()
# Campos que el skill respalda SIEMPRE juntos (contrato con mejorar-descripcion):
REQUIRED_BACKUP_FIELDS = {"descriptionHtml", "seo_title", "seo_description"}
RECENT_WINDOW_SECONDS = 900  # 15 min
GID_RE = re.compile(r"gid://shopify/Product/\d+", re.I)
# Forma CANÓNICA exacta de un gid de producto (sin espacios, nada antes ni después).
# `"/Product/" in gid` aceptaba `"gid://…/1 "` (espacio al final), y dos formas del
# mismo producto se leían como productos distintos → falso "cruzado" que salteaba el
# ratio de mismo-producto (hallazgo LOW del review de BXGY).
PRODUCT_GID_RE = re.compile(r"^gid://shopify/Product/\d+$")

# --- Estilo del widget (spec §9): cosmético, cerrado, sin techo -------------
# El look que el cliente configura en el builder. No mueve plata, pero se valida
# igual (colores hex, textos acotados, keys cerradas) porque el widget lo pinta.
STYLE_COLOR_KEYS = {"ink", "sage", "taupe", "cream"}
STYLE_TEXT_KEYS = {"label", "badge"}
STYLE_KEYS = STYLE_COLOR_KEYS | STYLE_TEXT_KEYS
STYLE_TEXT_MAXLEN = 40
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# worker.faq (Pack LatAm F1): preguntas frecuentes, forma cerrada {version, items[{q,a}]}.
FAQ_MAX_ITEMS = 12
FAQ_Q_MAXLEN = 120
FAQ_A_MAXLEN = 600

# worker.trust (Pack LatAm F2/F3): ítems tipados de confianza (badge/message/whatsapp).
TRUST_MAX_ITEMS = 8
TRUST_BADGE_ICONS = {"cuotas", "transferencia", "envio", "garantia", "seguridad"}
TRUST_BADGE_MAXLEN = 40
TRUST_MSG_MAXLEN = 80
TRUST_WA_TEXT_MAXLEN = 120
PHONE_RE = re.compile(r"^\d{8,15}$")

# worker.countdown (cuenta regresiva): fecha de fin REAL + textos. worker.freeship
# (barra de envío gratis): monto umbral en centavos + textos.
COUNTDOWN_KEYS = {"version", "endsAt", "label", "expiredText"}
COUNTDOWN_TEXT_MAXLEN = 60
FREESHIP_KEYS = {"version", "threshold", "label", "successText"}
FREESHIP_TEXT_MAXLEN = 80

# Familias de "contenido" (uno por uno, estilo wigy). Las que llevan URL usan
# `_ok_url` (solo https, sin caracteres que permitan inyección).
CONTENT_MAX_ROWS = 12
CONTENT_MAX_ITEMS = 8
URL_RE = re.compile(r'^https://[^\s<>"\']{1,300}$')

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
# `publishablepublish` SE SACÓ en W3 F3: publicar al Online Store entra en alcance,
# pero por un check propio y estrecho (`_check_publish`), no por la blocklist —
# decisión tomada con el operador (spec §7.2). `publishableunpublish` (DESPUBLICAR)
# SIGUE bloqueado: sacar de la venta no está en alcance. Verificado: ninguno de los
# dos es substring del otro, así que sacar uno no destapa al otro.
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
# `stageduploadscreate` (W3 F2): pide un destino temporal para subir los bytes de
# una foto local. Es INERTE respecto del catálogo (no toca producto/precio/stock/
# colección); el attach real de la imagen pasa por `productSet.files`, que
# `_check_create` ya controla. `publishablepublish` (W3 F3): publica al Online Store
# bajo el check estrecho `_check_publish`. NINGUNO empieza con product/discount/
# collection ni es metafieldsset, así que ADEMÁS se clasifican explícitamente en el
# contador de `asuntos` de `evaluate` (si no, se colarían como vehículo/señuelo de
# otra mutación — la clase de bug HIGH del review de BXGY).
ROOT_FIELD_ALLOWED = (PRODUCT_WRITE_ALLOWED | DISCOUNT_CREATE | DISCOUNT_BXGY
                      | DISCOUNT_DEACTIVATE
                      | {"metafieldsset", "stageduploadscreate", "publishablepublish"})

# --- Alta de producto (W3 F2, spec §7.0/§7.1) -------------------------------
# La clase `create`: un `productSet` en status DRAFT con un set de campos CERRADO
# y mínimo. Los sets salen de la introspección real de `ProductSetInput` y son
# más restrictivos que el borrado del spec: EXCLUYEN a propósito `collections`
# (colecciones), `metafields` (escribiría worker.deal sin techo),
# `inventoryQuantities`/`inventoryItem` (stock) e `id` (un productSet con id es
# UPDATE, no alta). Todo lo prohibido cae por NO estar en el set, no por blocklist.
CREATE_ALLOWED_TOP = {"title", "handle", "descriptionhtml", "seo", "producttype",
                      "tags", "status", "productoptions", "variants", "files"}
# `sku` es campo DIRECTO de ProductVariantSetInput (introspección real), así que
# excluir `inventoryItem` NO pierde el SKU (clave de dedup de F1).
CREATE_ALLOWED_VARIANT = {"optionvalues", "price", "sku", "barcode", "file"}
# Claves que la política de alta tiene que traer (mismo criterio que deal_policy).
# HARD (las enforcea el guard): `minPriceCents`/`maxPriceCents` (techo de precio en
# `_check_create`) y `createRecordWindowHours` (ventana del undo en
# `_covering_create_record`). ADVISORY (las cumple el SKILL, el guard no las mira):
# `requireImage`, `requireDescriptionMinWords`, `maxProductsPerBatch`.
# `allowPublish` está RESERVADA para F3: hoy publicar (status ACTIVE) está
# HARD-bloqueado en `_check_status_change` pase lo que pase, así que este flag NO
# es un toggle vivo —no lo leas como "enforced pero roto"—; recién F3 lo consulta.
CREATE_POLICY_KEYS = {"maxProductsPerBatch", "minPriceCents", "maxPriceCents",
                      "allowPublish", "requireImage", "requireDescriptionMinWords",
                      "createRecordWindowHours"}


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

    Delega en `_ts_fresh_window` con la ventana de 15 min: eran byte-idénticas
    salvo la ventana. Tolera un minuto de desfase de reloj.
    """
    return _ts_fresh_window(data, now, RECENT_WINDOW_SECONDS)


def _covering_backup(backups_root: Path, product_id: str, now: float):
    """(hay_backup_valido, motivo_si_no). Recolecta todos los candidatos válidos."""
    tail = product_id.split("/")[-1]
    hits = []
    saw_unmarked_empty = False
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
        # Los valores tienen que ser strings de verdad. Los null NO se salvan ni con
        # la marca de seed: el skill respalda el estado REAL de un producto vacío como
        # "" (string), no None. Esta guarda va antes de todo lo demás, sin excepción.
        values = [fields.get(k) for k in REQUIRED_BACKUP_FIELDS]
        if any(not isinstance(v, str) for v in values):
            continue
        # La frescura se evalúa ANTES que la regla de vacío: así el motivo
        # `saw_unmarked_empty` de abajo solo se dispara con un backup reciente y
        # accionable (poné la marca), no con uno que simplemente venció.
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        if not _ts_fresh(data, now):
            continue
        # Un backup con los 3 campos vacíos era un placeholder que rompía el undo
        # (restauraba vacío en vez del contenido real), así que se rechazaba SIEMPRE.
        # Excepción: un producto genuinamente vacío. El skill lo declara con
        # `originalEmpty: true` tras leer el estado en vivo. `is True` estricto: un
        # "true" string o un 1 truthy no habilitan el seed.
        if all(not v.strip() for v in values) and data.get("originalEmpty") is not True:
            saw_unmarked_empty = True
            continue
        hits.append(p)

    if not hits:
        if saw_unmarked_empty:
            return False, ("hay un backup del producto pero con los 3 campos vacíos y sin la "
                           "marca originalEmpty. Si el producto está realmente vacío, el skill "
                           "debe respaldarlo con originalEmpty:true.")
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


def _covering_cosmetic_backup(key, backups_root, product_id: str, now: float):
    """(hay_backup_valido, motivo). Backup COSMÉTICO de la familia `key`,
    discriminado por ruta (`backups/{key}/`) Y `kind == key` — las dos, igual que
    oferta/estilo.

    Discriminador propio a propósito (spec §5.2): un backup cosmético de una
    familia NO habilita un write de plata (`worker.deal` / `discount*Create`) ni
    de otra familia cosmética, ni al revés. El aislamiento vale por ruta Y por
    kind, defensa en profundidad idéntica a la de oferta. Frescura doble (mtime +
    ts), igual que `_covering_deal_backup`.
    """
    tail = product_id.split("/")[-1]
    for p in Path(backups_root).glob(f"**/backups/{key}/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("kind") != key:
            continue
        if data.get("productId") != product_id:
            continue
        if now - p.stat().st_mtime > RECENT_WINDOW_SECONDS:
            continue
        if not _ts_fresh(data, now):
            continue
        return True, None
    return False, (f"Sin backup cosmético reciente ({key}) para {product_id}. "
                   "El skill debe guardar el backup antes de escribir.")


def _covering_style_backup(backups_root, product_id: str, now: float):
    """Compat: el estilo es la familia cosmética `style` (spec §9.1)."""
    return _covering_cosmetic_backup("style", backups_root, product_id, now)


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
    if not (isinstance(gid, str) and PRODUCT_GID_RE.match(gid)):
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
    # El `productId` —con el que se busca el backup y sobre el que se escribe el
    # metafield worker.deal— tiene que ser EXACTAMENTE el producto comprado. Sin
    # esta atadura, un backup fresco de cualquier producto autorizaba el write
    # sobre otro (hallazgo MED del review de BXGY). Se compara contra el buy_gid
    # canónico, y el backup se busca por ese, no por el productId sin validar.
    if product_gid.strip() != buy_gid:
        return "block", ("el `productId` no coincide con el producto que se compra en el regalo. "
                         "El respaldo y la oferta tienen que ser del mismo producto.")
    ok, why = _covering_deal_backup(backups_root, buy_gid, now)
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
    if not (isinstance(bp, str) and PRODUCT_GID_RE.match(bp)):
        return "falta el producto que se compra."
    if not (isinstance(gp, str) and PRODUCT_GID_RE.match(gp)):
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

    # Routing por key: las familias cosméticas (worker.style, worker.faq, …) van
    # sin techo a su check de registro, ANTES de cargar la política de plata (no
    # dependen de deal-policy). worker.deal cae abajo, a la rama de plata.
    key0 = entries[0].get("key")
    if entries[0].get("namespace") == "worker" and key0 in COSMETIC_METAFIELDS:
        return _check_cosmetic(key0, tool_input, backups_root, now)

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


def _ok_text(v, maxlen):
    """Texto de cliente aceptable: str no vacío, ≤maxlen, sin `<` ni `>` (el widget
    usa textContent, pero validar en el borde es barato y correcto)."""
    return isinstance(v, str) and bool(v.strip()) and len(v) <= maxlen and "<" not in v and ">" not in v


def _style_body(data):
    """Valida el cuerpo de `worker.style`: set cerrado de keys, colores hex (para
    que un valor no inyecte CSS por la var), textos acotados sin `<`/`>`. Devuelve
    un motivo (str) o None si es válido. Un `{}` (sacar el look) es válido: el loop
    no corre y cae a los defaults del widget."""
    for k, v in data.items():
        if k not in STYLE_KEYS:
            return f"clave de estilo desconocida: {k}."
        if k in STYLE_COLOR_KEYS:
            if not (isinstance(v, str) and HEX_RE.match(v)):
                return f"{k} tiene que ser un color hex (#RRGGBB)."
        else:
            if not isinstance(v, str) or len(v) > STYLE_TEXT_MAXLEN or "<" in v or ">" in v:
                return f"{k} tiene que ser texto de hasta {STYLE_TEXT_MAXLEN} sin < ni >."
    return None


def _faq_body(data):
    """Valida el cuerpo de `worker.faq`: `{version, items[{q,a}]}`, textos acotados
    sin `<`/`>` (el widget usa `textContent`, pero validar en el borde es barato),
    1..FAQ_MAX_ITEMS. Devuelve un motivo (str) o None si es válido. `items: []` es
    válido: es "sacar la FAQ" (el widget deja de mostrarse), espejo del `{}` de estilo."""
    extra = set(data.keys()) - {"version", "items"}
    if extra:
        return f"clave de FAQ desconocida: {sorted(extra)[0]}."
    items = data.get("items", [])
    if not isinstance(items, list):
        return "las preguntas tienen que venir en una lista."
    if len(items) > FAQ_MAX_ITEMS:
        return f"la FAQ tiene {len(items)} preguntas y el máximo es {FAQ_MAX_ITEMS}."
    for it in items:
        if not isinstance(it, dict) or set(it.keys()) != {"q", "a"}:
            return "cada pregunta tiene que tener exactamente pregunta y respuesta."
        q, a = it.get("q"), it.get("a")
        if not isinstance(q, str) or not q.strip() or len(q) > FAQ_Q_MAXLEN or "<" in q or ">" in q:
            return f"la pregunta tiene que ser texto de hasta {FAQ_Q_MAXLEN} sin < ni >."
        if not isinstance(a, str) or not a.strip() or len(a) > FAQ_A_MAXLEN or "<" in a or ">" in a:
            return f"la respuesta tiene que ser texto de hasta {FAQ_A_MAXLEN} sin < ni >."
    return None


def _trust_body(data):
    """Valida `worker.trust`: {version, items[...]} con ítems tipados. Cada tipo
    tiene su set cerrado de claves (badge: icono de un set cerrado + texto;
    message: texto; whatsapp: teléfono de solo dígitos + texto). `items: []` es
    válido: es "sacar la confianza" (el bloque deja de mostrarse)."""
    extra = set(data.keys()) - {"version", "items"}
    if extra:
        return f"clave de confianza desconocida: {sorted(extra)[0]}."
    items = data.get("items", [])
    if not isinstance(items, list):
        return "los ítems de confianza tienen que venir en una lista."
    if len(items) > TRUST_MAX_ITEMS:
        return f"la confianza tiene {len(items)} ítems y el máximo es {TRUST_MAX_ITEMS}."
    for it in items:
        if not isinstance(it, dict):
            return "cada ítem de confianza tiene que ser un objeto."
        t = it.get("type")
        if t == "badge":
            if set(it.keys()) != {"type", "icon", "text"}:
                return "un badge tiene que traer tipo, ícono y texto, nada más."
            if it.get("icon") not in TRUST_BADGE_ICONS:
                return f"ícono de badge desconocido: {it.get('icon')}."
            if not _ok_text(it.get("text"), TRUST_BADGE_MAXLEN):
                return f"el texto del badge tiene que ser hasta {TRUST_BADGE_MAXLEN} sin < ni >."
        elif t == "message":
            if set(it.keys()) != {"type", "text"}:
                return "un mensaje tiene que traer tipo y texto, nada más."
            if not _ok_text(it.get("text"), TRUST_MSG_MAXLEN):
                return f"el mensaje tiene que ser hasta {TRUST_MSG_MAXLEN} sin < ni >."
        elif t == "whatsapp":
            if set(it.keys()) != {"type", "phone", "text"}:
                return "el whatsapp tiene que traer tipo, teléfono y texto, nada más."
            if not (isinstance(it.get("phone"), str) and PHONE_RE.match(it.get("phone"))):
                return "el teléfono de whatsapp tiene que ser solo dígitos (8 a 15)."
            if not _ok_text(it.get("text"), TRUST_WA_TEXT_MAXLEN):
                return f"el texto del whatsapp tiene que ser hasta {TRUST_WA_TEXT_MAXLEN} sin < ni >."
        else:
            return f"tipo de ítem de confianza desconocido: {t}."
    return None


def _parse_iso(x):
    """datetime desde un ISO (acepta sufijo 'Z' y fecha sola). None si no parsea."""
    if not isinstance(x, str) or not x.strip():
        return None
    s = x.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        try:
            return datetime.fromisoformat(s[:10])
        except ValueError:
            return None


def _countdown_body(data):
    """worker.countdown: fecha de fin REAL (honesto — el widget cuenta hasta esa
    fecha y NO resetea) + textos acotados. `items` no aplica; es un objeto plano."""
    extra = set(data.keys()) - COUNTDOWN_KEYS
    if extra:
        return f"clave de cuenta regresiva desconocida: {sorted(extra)[0]}."
    if _parse_iso(data.get("endsAt")) is None:
        return "la cuenta regresiva necesita una fecha de fin válida."
    for k in ("label", "expiredText"):
        v = data.get(k)
        if v is not None and not _ok_text(v, COUNTDOWN_TEXT_MAXLEN):
            return f"el texto de la cuenta regresiva ({k}) tiene que ser hasta {COUNTDOWN_TEXT_MAXLEN} sin < ni >."
    return None


def _freeship_body(data):
    """worker.freeship: monto umbral en CENTAVOS (entero > 0) + textos acotados.
    El widget lee el total del carrito y calcula lo que falta — el umbral es dato."""
    extra = set(data.keys()) - FREESHIP_KEYS
    if extra:
        return f"clave de envío gratis desconocida: {sorted(extra)[0]}."
    th = data.get("threshold")
    if not (isinstance(th, int) and not isinstance(th, bool) and th > 0):
        return "el envío gratis necesita un monto (en centavos) mayor a cero."
    for k in ("label", "successText"):
        v = data.get(k)
        if v is not None and not _ok_text(v, FREESHIP_TEXT_MAXLEN):
            return f"el texto de envío gratis ({k}) tiene que ser hasta {FREESHIP_TEXT_MAXLEN} sin < ni >."
    return None


def _ok_url(v):
    """URL de cliente aceptable: solo https, sin espacios ni `<>\"'` (va a un `src`
    o `href`, así que un `javascript:` o comillas rompen la barrera)."""
    return isinstance(v, str) and bool(URL_RE.match(v))


def _rows_ok(rows, ncols, cell_max):
    """Filas de una tabla: lista no vacía (≤CONTENT_MAX_ROWS) de listas de exactamente
    ncols celdas, cada una texto aceptable ≤cell_max."""
    if not isinstance(rows, list) or not rows or len(rows) > CONTENT_MAX_ROWS:
        return False
    return all(isinstance(r, list) and len(r) == ncols and all(_ok_text(c, cell_max) for c in r)
               for r in rows)


def _sizechart_body(data):
    extra = set(data.keys()) - {"version", "title", "rows"}
    if extra:
        return f"clave de tabla de talles desconocida: {sorted(extra)[0]}."
    t = data.get("title")
    if t is not None and not _ok_text(t, 60):
        return "el título de la tabla tiene que ser texto ≤60 sin < ni >."
    if not _rows_ok(data.get("rows"), 2, 40):
        return "la tabla necesita filas de 2 columnas (talle y medida), texto ≤40."
    return None


def _announce_body(data):
    extra = set(data.keys()) - {"version", "text", "link"}
    if extra:
        return f"clave de barra de anuncios desconocida: {sorted(extra)[0]}."
    if not _ok_text(data.get("text"), 120):
        return "el anuncio tiene que ser texto ≤120 sin < ni >."
    link = data.get("link")
    if link is not None and not _ok_url(link):
        return "el link del anuncio tiene que ser una URL https."
    return None


def _lowstock_body(data):
    extra = set(data.keys()) - {"version", "threshold", "text"}
    if extra:
        return f"clave de 'quedan pocas' desconocida: {sorted(extra)[0]}."
    th = data.get("threshold")
    if not (isinstance(th, int) and not isinstance(th, bool) and 1 <= th <= 999):
        return "el umbral de 'quedan pocas' tiene que ser un entero entre 1 y 999."
    t = data.get("text")
    if t is not None and not _ok_text(t, 60):
        return "el texto de 'quedan pocas' tiene que ser ≤60 sin < ni >."
    return None


def _beforeafter_body(data):
    extra = set(data.keys()) - {"version", "before", "after", "beforeLabel", "afterLabel"}
    if extra:
        return f"clave de antes/después desconocida: {sorted(extra)[0]}."
    if not _ok_url(data.get("before")) or not _ok_url(data.get("after")):
        return "antes/después necesita dos imágenes con URL https."
    for k in ("beforeLabel", "afterLabel"):
        v = data.get(k)
        if v is not None and not _ok_text(v, 30):
            return f"el texto '{k}' tiene que ser ≤30 sin < ni >."
    return None


def _gallery_body(data):
    extra = set(data.keys()) - {"version", "images"}
    if extra:
        return f"clave de galería desconocida: {sorted(extra)[0]}."
    imgs = data.get("images")
    if not (isinstance(imgs, list) and 1 <= len(imgs) <= CONTENT_MAX_ROWS and all(_ok_url(x) for x in imgs)):
        return "la galería necesita entre 1 y 12 imágenes con URL https."
    return None


def _video_body(data):
    extra = set(data.keys()) - {"version", "url", "label"}
    if extra:
        return f"clave de video desconocida: {sorted(extra)[0]}."
    if not _ok_url(data.get("url")):
        return "el video necesita una URL https."
    lb = data.get("label")
    if lb is not None and not _ok_text(lb, 60):
        return "el texto del video tiene que ser ≤60 sin < ni >."
    return None


def _compare_body(data):
    extra = set(data.keys()) - {"version", "usLabel", "themLabel", "rows"}
    if extra:
        return f"clave de comparación desconocida: {sorted(extra)[0]}."
    for k in ("usLabel", "themLabel"):
        v = data.get(k)
        if v is not None and not _ok_text(v, 30):
            return f"el texto '{k}' tiene que ser ≤30 sin < ni >."
    if not _rows_ok(data.get("rows"), 3, 40):
        return "la comparación necesita filas de 3 columnas (ítem, vos, otros), texto ≤40."
    return None


def _steps_body(data):
    extra = set(data.keys()) - {"version", "items"}
    if extra:
        return f"clave de pasos desconocida: {sorted(extra)[0]}."
    items = data.get("items")
    if not (isinstance(items, list) and 1 <= len(items) <= CONTENT_MAX_ITEMS and all(_ok_text(x, 200) for x in items)):
        return "los pasos tienen que ser entre 1 y 8 textos ≤200 sin < ni >."
    return None


def _benefits_body(data):
    extra = set(data.keys()) - {"version", "items"}
    if extra:
        return f"clave de beneficios desconocida: {sorted(extra)[0]}."
    items = data.get("items")
    if not (isinstance(items, list) and 1 <= len(items) <= CONTENT_MAX_ITEMS and all(_ok_text(x, 60) for x in items)):
        return "los beneficios tienen que ser entre 1 y 8 textos ≤60 sin < ni >."
    return None


# Registro de familias cosméticas: key -> validador de cuerpo. Agregar un widget
# cosmético es agregar UNA entrada, no una función de guard nueva (catálogo §7).
# Cada familia tiene su backup propio `kind == key` — aislamiento por ruta+kind:
# un backup cosmético no habilita un write de plata ni de otra familia
# (`_covering_cosmetic_backup`). worker.deal (plata, con techo) NO está acá:
# sigue su rama propia en `_check_metafield`.
COSMETIC_METAFIELDS = {
    "style": _style_body,
    "faq": _faq_body,
    "trust": _trust_body,
    "countdown": _countdown_body,
    "freeship": _freeship_body,
    "sizechart": _sizechart_body,
    "announce": _announce_body,
    "lowstock": _lowstock_body,
    "beforeafter": _beforeafter_body,
    "gallery": _gallery_body,
    "video": _video_body,
    "compare": _compare_body,
    "steps": _steps_body,
    "benefits": _benefits_body,
}

# Familias cosméticas que además pueden vivir en el SHOP (no solo por producto).
# style/faq son product-only; el resto de vitrina/tienda pueden ser de toda la tienda.
COSMETIC_SHOP_OK = {"trust", "countdown", "freeship", "announce", "video"}


def _check_cosmetic(key, tool_input, backups_root, now: float):
    """metafieldsSet de una familia cosmética (`worker.{key}`): sin techo, forma
    cerrada por el validador del registro, backup propio `kind == key`.
    Product-scope (owner SHOP entra en F2, spec §5.3)."""
    variables = (tool_input or {}).get("variables") or {}
    entries = []
    for value in variables.values():
        if isinstance(value, list):
            entries.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict) and ("namespace" in value or "ownerId" in value):
            entries.append(value)
    if not entries:
        return "block", f"no pude leer el metafield ({key}) que se está escribiendo."
    if len(entries) > 1:
        return "block", "un cambio por vez."
    e = entries[0]
    if e.get("namespace") != "worker" or e.get("key") != key:
        return "block", f"solo worker.{key}, no {e.get('namespace')}.{e.get('key')}."
    owner = e.get("ownerId") or ""
    owner_ok = ("/Product/" in owner) or (key in COSMETIC_SHOP_OK and "/Shop/" in owner)
    if not owner_ok:
        if key in COSMETIC_SHOP_OK:
            return "block", f"el {key} tiene que traer el id del producto o de la tienda."
        return "block", f"el {key} tiene que traer el id del producto."
    try:
        data = json.loads(e.get("value") or "{}")
    except Exception:
        return "block", f"el {key} no es JSON válido."
    if not isinstance(data, dict):
        return "block", f"el {key} tiene que ser un objeto."
    why = COSMETIC_METAFIELDS[key](data)
    if why:
        return "block", why
    ok, why2 = _covering_cosmetic_backup(key, backups_root, owner, now)
    return ("allow", "ok") if ok else ("block", why2)


def _check_style(tool_input, backups_root, now: float):
    """Compat: worker.style es la familia cosmética `style` (spec §9)."""
    return _check_cosmetic("style", tool_input, backups_root, now)


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


def load_create_policy(root):
    """dict con la política de alta del cliente activo, o None si no hay
    exactamente una. Espejo EXACTO de `deal_policy.load_policy`: globea
    `clients/*/create-policy.json` y EXCLUYE `_template` (el scaffold del próximo
    cliente, no un cliente). Con 0 o 2+ clientes → None, y `_check_create`
    traduce ese None en BLOQUEO — falla cerrado, no abierto. El filtro de
    `_template` es load-bearing: sin él, blunua + _template se leen como 2 → None
    → toda alta bloqueada (la feature queda muerta y la causa no es obvia)."""
    hits = sorted(Path(root).glob("clients/*/create-policy.json"))
    hits = [p for p in hits if p.parent.name != "_template"]
    if len(hits) != 1:
        return None
    try:
        data = json.loads(hits[0].read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not CREATE_POLICY_KEYS.issubset(data.keys()):
        return None
    return data


def _productset_input_ref(query: str):
    """(modo, nombre) del argumento `input:` del `productSet(...)` del documento.

    modo ∈ {"var", "inline", "unknown"}. Con "var", `nombre` es la variable (sin
    `$`) que hay que resolver en `variables`. El argumento TIENE que ser una
    referencia a variable: un objeto inline (`input: {...}`) cierra el bypass
    inline+señuelo — sin esto, un `input:{status:ACTIVE, id:…}` inline + un `$p`
    manso en variables pasaría (el guard valida `$p`, el server ejecuta el inline).

    Lee SOLO el argumento del productSet, acotado a su grupo de paréntesis, con
    strings y comentarios ya borrados. Ante cualquier duda devuelve "unknown",
    que el llamador trata como bloqueo (fail-closed).
    """
    clean = re.sub(r"#[^\n]*", " ", query or "")
    clean = re.sub(r'"""(?:.|\n)*?"""', ' "" ', clean)
    clean = re.sub(r'"(?:[^"\\]|\\.)*"', ' "" ', clean)
    m = re.search(r"\bproductset\s*\(", clean, re.I)
    if not m:
        return "unknown", None
    depth, args = 0, None
    for i in range(m.end() - 1, len(clean)):
        if clean[i] == "(":
            depth += 1
        elif clean[i] == ")":
            depth -= 1
            if depth == 0:
                args = clean[m.end():i]
                break
    if args is None:
        return "unknown", None
    am = re.search(r"\binput\s*:\s*(\$\w+|\{)", args, re.I)
    if not am:
        return "unknown", None
    tok = am.group(1)
    if tok == "{":
        return "inline", None
    return "var", tok[1:]


def _check_create(tool_input, backups_root, now: float):
    """Alta de producto DRAFT (spec §7.0/§7.1). `productSet` con un set de campos
    CERRADO y mínimo, status DRAFT, techo de precio por variante, política por
    cliente. Fail-closed ante cualquier dato que no se pueda leer.

    El input del producto viaja por `variables` (mismo patrón que
    `_check_discount`): se valida SOLO la variable que el query referencia, las
    demás se ignoran (señuelos). `_check_create` NO exige backup previo: un alta
    no tiene estado viejo que respaldar (el registro de creación lo escribe el
    skill DESPUÉS, y habilita el undo=archivar en `_check_status_change`).
    `now` se recibe por uniformidad con el dispatch; el create no lo usa.
    """
    policy = load_create_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de alta única (create-policy.json). "
                         "Sin ella no puedo crear productos.")

    mode, ref = _productset_input_ref(_query_text(tool_input))
    if mode == "inline":
        return "block", ("los datos del producto tienen que ir en `variables`, "
                         "no escritos dentro del pedido.")
    if mode != "var" or not ref:
        return "block", ("no pude leer el alta del producto. "
                         "Tiene que ser un productSet con `input: $variable`.")

    variables = (tool_input or {}).get("variables") if isinstance(tool_input, dict) else None
    product = variables.get(ref) if isinstance(variables, dict) else None
    if not isinstance(product, dict):
        return "block", ("no encontré los datos del producto en las variables del pedido. "
                         "Tienen que ir en `variables`, no escritos dentro del pedido.")

    variants = product.get("variants")

    # `id` (en el producto o en cualquier variante) => es un UPDATE disfrazado.
    def _has_id(d):
        return isinstance(d, dict) and any(str(k).lower() == "id" for k in d)
    if _has_id(product) or (isinstance(variants, list) and any(_has_id(v) for v in variants)):
        return "block", ("un productSet con id edita un producto existente; "
                         "el alta va sin id.")

    # status PRESENTE y == DRAFT (case-insensitive). Ausente u otro => block.
    status = product.get("status")
    if not isinstance(status, str) or status.strip().upper() != "DRAFT":
        return "block", "el alta tiene que ser en borrador (status DRAFT)."

    # Keys de primer nivel dentro del set cerrado.
    extra = {str(k).lower() for k in product.keys()} - CREATE_ALLOWED_TOP
    if extra:
        return "block", (f"campo fuera de alcance en el alta: {sorted(extra)[0]}. "
                         "El alta solo escribe título, descripción, SEO, tipo, tags, "
                         "opciones, variantes e imágenes.")

    # Variantes: lista no vacía; cada una con set cerrado y precio dentro del techo.
    if not isinstance(variants, list) or not variants:
        return "block", "el alta tiene que traer al menos una variante."
    lo, hi = policy["minPriceCents"], policy["maxPriceCents"]
    for v in variants:
        if not isinstance(v, dict):
            return "block", "cada variante tiene que ser un objeto."
        vextra = {str(k).lower() for k in v.keys()} - CREATE_ALLOWED_VARIANT
        if vextra:
            return "block", (f"campo fuera de alcance en una variante: {sorted(vextra)[0]}. "
                             "Una variante solo lleva opciones, precio, SKU, código de barras e imagen.")
        if "price" not in v:
            return "block", "cada variante tiene que traer un precio."
        try:
            # round(), no int(): int() TRUNCA (int(float("1.15")*100) == 114 por
            # el error de coma flotante), mismo criterio que `_percentage_int` y
            # `_gift_effect_pct_int`. Trunca hacia abajo justo en el borde del techo.
            cents = round(float(v.get("price")) * 100)
        except (TypeError, ValueError, OverflowError):
            return "block", "no pude leer el precio de una variante."
        if cents < lo or cents > hi:
            return "block", ("el precio de una variante está fuera del rango permitido "
                             "para este cliente.")

    return "allow", "ok"


def _ts_fresh_window(data: dict, now: float, window_s: float) -> bool:
    """Como `_ts_fresh` pero con ventana parametrizable (la clase create la mide
    en horas, no en los 900s de descripción/oferta). Frescura por el `ts` del
    CONTENIDO: git no reescribe el ts, así que sobrevive a un pull/checkout que
    sí toca el mtime."""
    raw = data.get("ts")
    if not isinstance(raw, str) or not raw.strip():
        return False
    try:
        stamp = datetime.fromisoformat(raw.strip().replace("Z", "+00:00")).timestamp()
    except ValueError:
        return False
    age = now - stamp
    return -60 <= age <= window_s


def _covering_create_record(backups_root, product_id: str, now: float, window_hours):
    """(hay_registro, motivo). Registro de CREACIÓN (`kind:"create"`, ruta
    `backups/create/`) que habilita el undo=archivar de F2.

    Espejo de `_covering_deal_backup`: discrimina por ruta (`backups/create/`) Y
    `kind == "create"` —las dos, para que un backup de otra clase no habilite un
    archivar—, con frescura DOBLE (mtime + ts). La única diferencia es la
    ventana: en horas (`createRecordWindowHours`), no los 900s de las otras
    clases; un alta se puede deshacer más tarde, no en 15 minutos."""
    tail = product_id.split("/")[-1]
    window_s = float(window_hours) * 3600
    hits = []
    for p in Path(backups_root).glob(f"**/backups/create/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("kind") != "create":
            continue
        if data.get("productId") != product_id:
            continue
        if now - p.stat().st_mtime > window_s:
            continue
        if not _ts_fresh_window(data, now, window_s):
            continue
        hits.append(p)

    if not hits:
        return False, ("solo puedo archivar un producto que subí recién, y no encuentro "
                       "su registro de creación reciente.")

    # Mismo guard de colisión que `_covering_backup`: los ids numéricos de Shopify
    # son POR TIENDA, y el glob de registros de creación barre TODOS los clientes.
    # Si hay registros válidos bajo más de un cliente para el mismo id, no puedo
    # saber cuál corresponde al archivar. Ante la duda, bloqueo.
    clientes = {c for c in (_client_of(p) for p in hits) if c}
    if len(clientes) > 1:
        return False, (f"hay registros de creación de {sorted(clientes)} para el mismo id de "
                       "producto. Los ids de Shopify son por tienda, así que no puedo saber cuál corresponde.")
    return True, None


def _covering_publish_record(backups_root, product_id: str, now: float, window_hours):
    """(hay_registro, motivo). Registro de PUBLICACIÓN (`kind:"publish"`, ruta
    `backups/publish/`) que el skill escribe DESPUÉS de pasar el gate de
    completitud y ANTES de los writes de publicación (F3, spec §7.2/§7.4).

    Espejo EXACTO de `_covering_create_record`: discrimina por ruta Y `kind`,
    frescura DOBLE (mtime + ts), ventana en horas, y el mismo guard de colisión
    multi-cliente (los ids de Shopify son por tienda, y el glob barre todos los
    clientes). Un registro `create` NO habilita publicar y viceversa: cada clase
    tiene su ruta + kind, defensa en profundidad idéntica a oferta/cosmético."""
    tail = product_id.split("/")[-1]
    window_s = float(window_hours) * 3600
    hits = []
    for p in Path(backups_root).glob(f"**/backups/publish/{tail}-*.json"):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if data.get("kind") != "publish":
            continue
        if data.get("productId") != product_id:
            continue
        if now - p.stat().st_mtime > window_s:
            continue
        if not _ts_fresh_window(data, now, window_s):
            continue
        hits.append(p)

    if not hits:
        return False, ("antes de publicar tengo que revisar que el producto esté completo, "
                       "y no encuentro ese registro reciente.")

    clientes = {c for c in (_client_of(p) for p in hits) if c}
    if len(clientes) > 1:
        return False, (f"hay registros de publicación de {sorted(clientes)} para el mismo id de "
                       "producto. Los ids de Shopify son por tienda, así que no puedo saber cuál corresponde.")
    return True, None


def _call_args(text: str, open_idx: int):
    """Arg-string entre paréntesis desde `text[open_idx] == '('`, saltando string
    literals para que un `)` dentro de un string no cierre el grupo antes de
    tiempo. None si no cierra."""
    depth, i, n = 0, open_idx, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == '"':
                    i += 1
                    break
                i += 1
            continue
        if c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_idx + 1:i]
        i += 1
    return None


def _skip_string(text: str, i: int) -> int:
    """Índice justo después del string literal que arranca en `text[i] == '"'`
    (respeta `\\"`). Si el string no cierra, consume hasta el final."""
    i += 1
    n = len(text)
    while i < n:
        if text[i] == "\\":
            i += 2
            continue
        if text[i] == '"':
            return i + 1
        i += 1
    return i


def _skip_balanced(text: str, i: int) -> int:
    """Índice justo después del grupo balanceado `{..}`/`[..]`/`(..)` que arranca
    en `text[i]`, saltando string literals (un `}` dentro de un string no cierra)."""
    pairs = {"{": "}", "[": "]", "(": ")"}
    stack = [pairs[text[i]]]
    i += 1
    n = len(text)
    while i < n and stack:
        c = text[i]
        if c == '"':
            i = _skip_string(text, i)
            continue
        if c in pairs:
            stack.append(pairs[c])
        elif c == stack[-1]:
            stack.pop()
        i += 1
    return i


def _read_value(text: str, j: int):
    """(token, fin) de UN valor de argumento GraphQL desde `text[j]` (ya sin
    espacios delante): string literal (con comillas), `$variable`, objeto/lista
    balanceada, o token simple (enum/número). `('', j)` si no hay nada legible."""
    n = len(text)
    if j >= n:
        return "", j
    c = text[j]
    if c == '"':
        end = _skip_string(text, j)
        return text[j:end], end
    if c in "{[":
        end = _skip_balanced(text, j)
        return text[j:end], end
    m = re.match(r"\$[A-Za-z_][A-Za-z0-9_]*|[A-Za-z_][A-Za-z0-9_]*|[-+]?[0-9][0-9_.eE+\-]*",
                 text[j:])
    if m:
        return m.group(0), j + m.end()
    return "", j


_AMBIGUOUS_ARG = object()


def _top_level_args(args: str) -> dict:
    """Args de una llamada GraphQL leídos a NIVEL SUPERIOR y string-aware:
    `{nombre_lower: token_de_valor}`.

    La clave del arreglo #1: cada valor se consume ENTERO (string, objeto, lista,
    $var o token) antes de seguir escaneando, así que un `status:` que viva DENTRO
    del valor de otro argumento —p. ej. un string señuelo `note: "status:
    ARCHIVED"`— NO se confunde con el argumento real. Un `re.search` global sobre
    el texto crudo sí caía en ese señuelo (leía ARCHIVED del string mientras el
    status ejecutado era ACTIVE). Un argumento REPETIDO al tope se marca ambiguo
    (`_AMBIGUOUS_ARG`) para fallar cerrado en vez de adivinar cuál gana."""
    out = {}
    word = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
    i, n = 0, len(args)
    while i < n:
        c = args[i]
        if c == '"':
            i = _skip_string(args, i)
            continue
        if c in "{[(":
            i = _skip_balanced(args, i)
            continue
        m = word.match(args, i)
        if m:
            name = m.group(0).lower()
            j = m.end()
            while j < n and args[j].isspace():
                j += 1
            if j < n and args[j] == ":":
                j += 1
                while j < n and args[j].isspace():
                    j += 1
                val, j = _read_value(args, j)
                out[name] = _AMBIGUOUS_ARG if name in out else val
                i = j
                continue
            i = j
            continue
        i += 1
    return out


def _resolve_token(tok, variables: dict):
    """Resuelve un token de valor de argumento: `$x` → `variables["x"]`; `"..."` →
    string sin comillas; enum/número → tal cual. None si falta, está vacío o es
    ambiguo (arg repetido) — todos fallan cerrado en `_check_status_change`."""
    if tok is None or tok is _AMBIGUOUS_ARG or tok == "":
        return None
    if tok.startswith("$"):
        return variables.get(tok[1:])
    if tok.startswith('"'):
        return tok[1:-1]
    return tok


def _status_arg(args: str, variables: dict):
    """Valor del argumento `status:` REAL de la mutación (enum literal o `$var`
    resuelto contra `variables`), leído por CLAVE y string-aware (`_top_level_args`),
    no por un `re.search` global. Cierra dos señuelos a la vez: la variable no
    referenciada (`$s = "ARCHIVED"` con `status: ACTIVE` inline) y el string
    incrustado (`note: "status: ARCHIVED"`). None si no está."""
    return _resolve_token(_top_level_args(args).get("status"), variables)


def _productid_arg(args: str, variables: dict):
    """Valor del argumento `productId:` REAL (string literal o `$var` resuelto),
    leído por CLAVE y string-aware. None si no está."""
    return _resolve_token(_top_level_args(args).get("productid"), variables)


def _check_status_change(tool_input, backups_root, now: float):
    """`productChangeStatus(productId, status)`. DOS destinos permitidos:
    - ARCHIVED (F2, undo=archivar): exige un registro `create` fresco.
    - ACTIVE (F3, publicar): exige `allowPublish:true` + registro `create` fresco
      (lo subió W3) + registro `publish` fresco (el skill lo escribió tras el gate
      de completitud). DRAFT/UNLISTED u otro destino → block.

    `status` y `productId` se leen del argumento REAL de la mutación por CLAVE y
    string-aware (`_top_level_args`), nunca de una variable señuelo que el query
    no referencia ni de un string incrustado. Fail-closed ante la duda."""
    query = _query_text(tool_input)
    clean = re.sub(r"#[^\n]*", " ", query or "")
    m = re.search(r"\bproductchangestatus\s*\(", clean, re.I)
    if not m:
        return "block", "no pude leer la operación de cambio de estado."
    args = _call_args(clean, m.end() - 1)
    if args is None:
        return "block", "no pude leer la operación de cambio de estado."
    variables = (tool_input or {}).get("variables") if isinstance(tool_input, dict) else None
    variables = variables if isinstance(variables, dict) else {}

    status = _status_arg(args, variables)
    if not isinstance(status, str) or not status.strip():
        return "block", "no pude determinar a qué estado se cambia el producto."
    dest = status.strip().upper()
    if dest not in ("ARCHIVED", "ACTIVE"):
        return "block", "solo puedo archivar o publicar un producto, no cambiarlo a otro estado."

    product_id = _productid_arg(args, variables)
    if not (isinstance(product_id, str) and PRODUCT_GID_RE.match(product_id.strip())):
        verbo = "archiva" if dest == "ARCHIVED" else "publica"
        return "block", f"no pude identificar qué producto se {verbo}."
    product_id = product_id.strip()

    policy = load_create_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de alta única (create-policy.json). "
                         "Sin ella no puedo cambiar el estado de un producto.")
    window = policy["createRecordWindowHours"]

    if dest == "ARCHIVED":
        ok, why = _covering_create_record(backups_root, product_id, now, window)
        return ("allow", "ok") if ok else ("block", why)

    # dest == ACTIVE: publicar (F3). Gate en tres partes, fail-closed en cada una.
    if not policy.get("allowPublish"):
        return "block", "publicar no está habilitado para este cliente."
    ok, _ = _covering_create_record(backups_root, product_id, now, window)
    if not ok:
        return "block", "solo puedo publicar un producto que subí recién."
    ok2, _ = _covering_publish_record(backups_root, product_id, now, window)
    if not ok2:
        return "block", ("antes de publicar tengo que revisar que el producto esté completo.")
    return "allow", "ok"


def _check_staged_upload(tool_input, backups_root, now: float):
    """`stagedUploadsCreate`: pide un destino temporal para subir bytes (una foto
    local) y devuelve una URL de subida. Es INERTE respecto del catálogo: no toca
    ningún producto, precio, stock ni colección. El attach real de la imagen pasa
    DESPUÉS por `productSet.files`, que `_check_create` ya controla (status DRAFT,
    set de campos cerrado, techo de precio). Por eso se permite sin techo ni backup.

    La disciplina de 'un asunto por documento' (contador `asuntos` en `evaluate`)
    garantiza que llegue acá SOLO cuando es el único asunto del pedido: no puede
    viajar como vehículo ni señuelo de otra mutación. No se restringe el `resource`
    del input: aun con otro tipo sigue siendo inerte, y sobre-restringir solo
    rompería la subida de imágenes legítimas —el lado equivocado para fallar en una
    operación sin superficie peligrosa. `backups_root`/`now` van por uniformidad
    con el resto del dispatch; este check no los usa."""
    return "allow", "ok"


def _check_publish(tool_input, backups_root, now: float):
    """`publishablePublish(id: ID!, input: [PublicationInput!]!)` — publicar al
    Online Store (W3 F3, spec §7.2). `PublicationInput = {publicationId, publishDate}`.

    Gate estrecho, fail-closed en cada paso:
    1. `allowPublish: true` en la política; si no → block.
    2. UN solo `publishablePublish` por doc; el `input:` tiene que ser una
       referencia a variable (bloquear inline `[`, espejo de F2); el `id` se lee
       por CLAVE del argumento real (gid inline o `$var` resuelto).
    3. Lista de publicaciones NO vacía; cada item con `publicationId`. Se itera
       TODOS: si ALGUNO ∉ `allowedPublicationIds` (o la allowlist está vacía) →
       block. Validar todos —no el primero— es la lección de discount/BXGY.
    4. Cualquier `publishDate` presente → block (v1 no hace publicación programada).
    5. Registro `create` fresco (lo subió W3) + registro `publish` fresco (pasó el
       gate de completitud) para ese producto → allow; si no → block.
    """
    policy = load_create_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de alta única (create-policy.json). "
                         "Sin ella no puedo publicar.")
    if not policy.get("allowPublish"):
        return "block", "publicar no está habilitado para este cliente."

    query = _query_text(tool_input)
    clean = re.sub(r"#[^\n]*", " ", query or "")
    calls = list(re.finditer(r"\bpublishablepublish\s*\(", clean, re.I))
    if len(calls) != 1:
        return "block", "solo puedo verificar una publicación por pedido. Mandá una sola."
    args = _call_args(clean, calls[0].end() - 1)
    if args is None:
        return "block", "no pude leer la operación de publicación."
    variables = (tool_input or {}).get("variables") if isinstance(tool_input, dict) else None
    variables = variables if isinstance(variables, dict) else {}
    top = _top_level_args(args)

    # El `input:` tiene que venir por variable (no inline: un `[...]` inline con un
    # $var manso de señuelo colaría el inline, igual que en el create de F2).
    input_tok = top.get("input")
    if not isinstance(input_tok, str) or not input_tok:
        return "block", ("no pude leer a qué canal se publica. "
                         "Los datos de publicación tienen que ir en `variables`.")
    if input_tok.startswith("["):
        return "block", ("los datos de publicación tienen que ir en `variables`, "
                         "no escritos dentro del pedido.")
    if not input_tok.startswith("$"):
        return "block", "no pude leer a qué canal se publica."
    pubs = variables.get(input_tok[1:])
    if not isinstance(pubs, list) or not pubs:
        return "block", "no identifiqué el canal de publicación."

    # Se compara con `.strip()` en LAS DOS puntas: el gid de la política lo carga el
    # operador a mano, y un espacio al costado no puede hacer que un canal legítimo
    # falle-cerrado en silencio.
    allowed = {a.strip() for a in (policy.get("allowedPublicationIds") or []) if isinstance(a, str)}
    for item in pubs:
        if not isinstance(item, dict):
            return "block", "no identifiqué el canal de publicación."
        # Set de claves CERRADO, igual que `_check_create` (defensa en profundidad y
        # canario si Shopify agrega un campo a PublicationInput). Hoy el schema tiene
        # exactamente estas dos; cualquier otra key bloquea.
        extra = {str(k).lower() for k in item.keys()} - {"publicationid", "publishdate"}
        if extra:
            return "block", f"campo desconocido en la publicación: {sorted(extra)[0]}."
        pub_id = item.get("publicationId")
        if not isinstance(pub_id, str) or not pub_id.strip():
            return "block", "no identifiqué el canal de publicación."
        if item.get("publishDate") is not None:
            return "block", "no puedo programar la publicación para más adelante."
        if pub_id.strip() not in allowed:
            return "block", "solo puedo publicar al canal configurado (Online Store)."

    product_id = _resolve_token(top.get("id"), variables)
    if not (isinstance(product_id, str) and PRODUCT_GID_RE.match(product_id.strip())):
        return "block", "no pude identificar qué producto se publica."
    product_id = product_id.strip()

    window = policy["createRecordWindowHours"]
    ok, _ = _covering_create_record(backups_root, product_id, now, window)
    if not ok:
        return "block", "solo puedo publicar un producto que subí recién."
    ok2, _ = _covering_publish_record(backups_root, product_id, now, window)
    if not ok2:
        return "block", ("antes de publicar tengo que revisar que el producto esté completo.")
    return "allow", "ok"


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
        # Los ASUNTOS se clasifican desde `roots` — los root fields que ya pasaron
        # el gate de allowlist, calculados por `_root_mutation_fields` (borra
        # comentarios, consciente de llaves/paréntesis). Clasificar desde el MISMO
        # parser que decidió la allowlist cierra la clase de agujero donde un
        # segundo parser más débil (el regex `nombre\s*\(` sobre texto CRUDO de
        # `_discount_mutations`/`_product_mutations`) no reconoce una mutación que
        # un comentario o una coma separaron de su `(`: el write caía al camino de
        # producto pidiendo solo un backup de descripción, evadiendo el techo
        # entero. Era el bypass HIGH del review adversarial de BXGY, y reabría
        # escalones por igual (los dos usan este router). El defecto era mantener
        # dos formas de leer el documento y confiar la decisión final a la débil.
        discount_roots = [r for r in roots if r.startswith("discount")]
        product_roots = [r for r in roots if r.startswith("product")]
        collection_roots = [r for r in roots if r.startswith("collection")]
        has_metafield = "metafieldsset" in roots
        # `stageduploadscreate` NO empieza con product/discount/collection ni es
        # metafieldsset, así que NINGUNA de las familias de arriba lo clasifica.
        # Hay que contarlo como asunto propio a mano: si no, se colaría en un
        # documento junto a otra mutación (vehículo o señuelo) sin que el contador
        # lo vea, que es la MISMA clase de bug que el default invertido cerró para
        # el resto del catálogo.
        has_staged = "stageduploadscreate" in roots
        # `publishablepublish` (W3 F3): misma historia que `stageduploadscreate` —
        # no matchea ningún prefijo de familia, así que HAY QUE contarlo a mano. Sin
        # esta línea queda abierto un BYPASS DE CANAL ARBITRARIO: un doc con
        # `productChangeStatus(P, ACTIVE)` + `publishablePublish(P, CANAL_MALO)` sobre
        # un P con records válidos daría `asuntos=['cambios de producto']` (len 1, no
        # bloquea), el status-change se aprobaría y el `publishablePublish(CANAL_MALO)`
        # se ejecutaría SIN pasar por `_check_publish`. Contarlo obliga a mandar los
        # dos writes por separado, y cada uno pasa por su check.
        has_publish = "publishablepublish" in roots

        asuntos = []
        if discount_roots:
            asuntos.append("ofertas")
        if has_metafield:
            asuntos.append("metafields")
        if product_roots or collection_roots:
            asuntos.append("cambios de producto")
        if has_staged:
            asuntos.append("staged-upload")
        if has_publish:
            asuntos.append("publicación")
        if len(asuntos) > 1:
            return "block", (f"esta operación mezcla {' y '.join(asuntos)} en un mismo pedido "
                             "y no puedo verificar las dos cosas juntas. Mandalas por separado.")

        if discount_roots:
            # El regalo (BXGY) tiene su propia función y su propio techo: NO reusa
            # `_check_discount`, que asume la forma Basic acotada por maxDiscountPct.
            if any(n in DISCOUNT_BXGY for n in discount_roots):
                return _check_bxgy(discount_roots, tool_input, backups_root, now)
            return _check_discount(discount_roots, tool_input, backups_root, now)

        # 3. Metafield de oferta. ANTES del fallthrough por GID_RE.
        if has_metafield:
            return _check_metafield(tool_input, backups_root, now)

        # Subida de bytes de una foto local: inerte, y ya garantizado como único
        # asunto por el contador de arriba. Va junto al dispatch de oferta/metafield,
        # ANTES de la rama de producto.
        if has_staged:
            return _check_staged_upload(tool_input, backups_root, now)

        # Publicación (F3): va ANTES de la rama de producto a propósito. Un
        # `publishablePublish` solo trae un gid de Product en `id:`, así que si
        # cayera a la rama de producto, el fallthrough por GID_RE lo tomaría como
        # write de producto y bloquearía por el motivo equivocado. Acá lo agarra su
        # check propio, ya garantizado como único asunto por el contador de arriba.
        if has_publish:
            return _check_publish(tool_input, backups_root, now)

        # Familia de producto: whitelist CERRADA, desde `roots`. Tras el gate de
        # `desconocidas` el único root de producto posible es `productupdate`, así
        # que esto es defensa en profundidad; se mantiene por si la allowlist crece.
        # El control de campos (abajo) sigue mirando el objeto `input: {...}`.
        fuera_de_alcance = [m for m in product_roots if m not in PRODUCT_WRITE_ALLOWED]
        if fuera_de_alcance:
            return "block", (f"la mutación '{fuera_de_alcance[0]}' está fuera del alcance del v1. "
                             "Lo único que se puede escribir de un producto es su descripción y su SEO.")

        # Colecciones: misma whitelist cerrada, y vacía.
        col = [m for m in collection_roots if m not in COLLECTION_WRITE_ALLOWED]
        if col:
            return "block", (f"la mutación '{col[0]}' está fuera del alcance del v1: "
                             "las colecciones no se tocan desde acá.")

        # W3 F2: alta (`productset`) y undo=archivar (`productchangestatus`) se
        # rutean por NOMBRE a su propio check, ANTES del control de campos de
        # `productupdate`. Va acá arriba a propósito: un `productSet` de alta no
        # trae id ni "productupdate" en el texto, así que el fallthrough por
        # GID_RE de abajo lo dejaría pasar (el fail-open histórico). El ruteo por
        # nombre lo agarra.
        create_or_status = [m for m in product_roots
                            if m in ("productset", "productchangestatus")]
        if create_or_status:
            # UNA sola operación de producto por pedido: el input que se valida
            # sale de `variables` y es UNO; con dos, la segunda viajaría sin
            # control. ACOTADO a productset/productchangestatus a PROPÓSITO: un
            # documento con dos `productUpdate` NO cae acá, tiene que seguir al
            # control de campos de abajo (regresión de `_product_input_keys`, que
            # une las keys de TODOS los objetos input).
            if len(product_roots) != 1:
                return "block", ("solo puedo verificar una operación de producto por pedido. "
                                 "Mandá el alta (o el archivar) sola.")
            only = product_roots[0]
            if only == "productset":
                return _check_create(tool_input, backups_root, now)
            return _check_status_change(tool_input, backups_root, now)

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
