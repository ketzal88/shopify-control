# W3 · F2 — Clase `create` + imágenes + undo(archivar) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `subir-productos` cree productos **borradores inertes** en la tienda real (con variantes, precio e imágenes), extendiendo `backup_guard.py` con una clase de write `create` que solo permite `productSet` en `status: DRAFT` con un set de campos cerrado y mínimo, y un undo que **archiva** (no borra).

**Architecture:** Dos frentes. (1) **Guard** (`backup_guard.py`): nueva función `_check_create` (whitelist de campos + status DRAFT + techo de precio + política), la restructura del router de §7.0.1 (rutear `productset`/`productchangestatus` por NOMBRE, una sola mutación de producto por documento), y `_check_status_change` con la rama ARCHIVED (undo). Nueva `create-policy.json` por cliente. (2) **Skill** (`subir-productos/SKILL.md`): el flujo de creación real (gate → `productSet` DRAFT → registro de creación → undo=archivar), incluyendo el staged upload de imágenes locales. **Publicar (status ACTIVE) es F3, no F2.**

**Tech Stack:** Python 3 (stdlib), pytest. GraphQL Admin API: `productSet` (create), `productChangeStatus` (archive), `stagedUploadsCreate` (subir bytes locales). Mismo patrón de guard que las clases `discount`/`cosmetic` ya existentes.

**Spec:** `docs/superpowers/specs/2026-07-24-subir-productos-w3-design.md` §7.0, §7.0.1, §7.1, §7.3, §7.4, §5. **Corrección sobre el spec** (de la introspección real de `ProductSetInput`, ver Task 2): el allowed-key set es más restrictivo que el borrado del §7.1 — excluye `collections`, `metafields` (producto y variante) e `inventoryQuantities`, que son campos reales de `ProductSetInput` que romperían el alcance (colecciones / techo de ofertas / stock).

---

## Contexto del guard (leer antes de tocar `backup_guard.py`)

El router vive en `evaluate()` (`backup_guard.py:1375`). Para `graphql_mutation`:
1. `FORBIDDEN_MUTATIONS` (substring) bloquea siempre — incluye `productdelete`, `publishablepublish`, `inventory*`. **NO se toca.** `productset`/`productchangestatus` NO están ahí.
2. `ROOT_FIELD_ALLOWED` (allowlist, línea 145) es la **unión** de `PRODUCT_WRITE_ALLOWED` + otras — para habilitar `productset`/`productchangestatus` se agregan a `PRODUCT_WRITE_ALLOWED` (Task 3), NO sueltos a `ROOT_FIELD_ALLOWED`.
3. Un asunto por documento (contador `asuntos`), después dispatch por familia.
4. Rama de producto: hoy `PRODUCT_WRITE_ALLOWED = {"productupdate"}`, y todo lo demás cae a `fuera_de_alcance` (bloquea) o al `return "allow"` final (línea ~1505).

Patrones a imitar: `_check_discount` (whitelist + techo + `load_policy`), `_check_cosmetic` (routing por key + backup por `kind`+ruta), `_discount_inputs` (leer el objeto desde `variables`, bloquear si hay más de uno o si viene inline), `_covering_deal_backup` (frescura doble mtime+ts, discriminación por ruta+kind).

**Contrato de bloqueo: `exit 2`. Fail-closed ante la duda.** Todo dato que no se pueda parsear = DESCONOCIDO = bloquea.

---

## Task 1: `create-policy.json` (política que lee el guard)

**Files:**
- Create: `clients/blunua/create-policy.json`
- Create: `clients/_template/create-policy.json`
- Test: `tests/test_create_guard.py`

- [ ] **Step 1: Escribir el test que falla** (loader de política, reusa el patrón de `deal_policy.load_policy`)

```python
# tests/test_create_guard.py
import sys, json, importlib.util
from pathlib import Path
HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

def test_create_policy_exists_and_has_ceilings(tmp_path):
    # la política de blunua tiene las claves que el guard necesita
    root = Path(__file__).resolve().parents[1]
    pol = json.loads((root / "clients" / "blunua" / "create-policy.json").read_text(encoding="utf-8"))
    for k in ("maxProductsPerBatch","minPriceCents","maxPriceCents","allowPublish",
              "requireImage","requireDescriptionMinWords","createRecordWindowHours"):
        assert k in pol
```

- [ ] **Step 2: Verificar que falla** → FAIL (archivo no existe).

- [ ] **Step 3: Crear los dos archivos.** `clients/blunua/create-policy.json`:

```json
{
  "maxProductsPerBatch": 50,
  "minPriceCents": 100,
  "maxPriceCents": 100000000,
  "allowPublish": true,
  "requireImage": true,
  "requireDescriptionMinWords": 40,
  "createRecordWindowHours": 72
}
```
`clients/_template/create-policy.json`: idéntico (es el scaffold del próximo cliente).

> ⚠️ **Load-bearing:** como ahora hay DOS archivos (`blunua` y `_template`), el `load_create_policy` de Task 2 **tiene que excluir `_template`** igual que `deal_policy.load_policy` (`deal_policy.py:20-23` dropea `_template` y devuelve `None` salvo que quede exactamente uno). Si el loader copia el glob sin ese filtro, ve 2 archivos → `None` → `_check_create` bloquea TODO create (fail-closed, "seguro" pero la feature queda muerta y la causa no es obvia). Task 2 lleva un test contra el **repo root real** (no `tmp_path`) que lo garantiza.

- [ ] **Step 4: Verificar que pasa** → PASS.
- [ ] **Step 5: Commit** → `git add clients/blunua/create-policy.json clients/_template/create-policy.json tests/test_create_guard.py && git commit -m "feat(w3): create-policy.json por cliente (F2)"`

---

## Task 2: `_check_create` — la clase de creación (el corazón de F2)

**Files:**
- Modify: `.claude/hooks/backup_guard.py` (agregar constantes + `_check_create`, NO wire al router todavía — eso es Task 3)
- Test: `tests/test_create_guard.py`

**Allowed-key sets (de la introspección real de `ProductSetInput` — cerrados y mínimos):**
- Top-level permitidos: `{title, handle, descriptionhtml, seo, producttype, tags, status, productoptions, variants, files}` (lowercase).
- Por variante permitidos: `{optionvalues, price, sku, barcode, file}` (lowercase).
- **Prohibidos explícitos aunque `ProductSetInput` los acepte** (romperían el alcance): `collections`, `metafields` (producto y variante → escribiría `worker.deal`), `inventoryquantities`/`inventoryitem` (stock), `id` (un `productSet` con id es UPDATE, no create), `claimownership`, `combinedlistingrole`. Todos caen por NO estar en el allowed-set.

> **`sku` confirmado como campo DIRECTO de `ProductVariantSetInput`** (introspección real): `{"name":"sku","description":"The SKU for the variant. Case-sensitive string."}`. Por eso excluir `inventoryItem` **no** pierde el SKU (que es la clave de dedup de F1). No hace falta abrir `inventoryItem`.

**Reglas de `_check_create(tool_input, backups_root, now)`** (recibe el `graphql_mutation` tool_input; el input del producto viene en `variables`):
1. Cargar `create-policy` con `load_create_policy` (mismo patrón que `deal_policy.load_policy`: globea `clients/*/create-policy.json` y **excluye `_template`**, ver Task 1). Si no hay exactamente una → block (fail-closed).
2. **El argumento `input:` del `productSet` tiene que ser una referencia a variable (`$nombre`), NO un objeto inline.** Parsear del query el nombre de la variable que referencia `productSet(input: $NOMBRE)`. Si tras `input:` viene un `{` (payload inline) → block ("los datos del producto tienen que ir en `variables`, no escritos dentro del pedido"). Esto cierra el **bypass inline+señuelo**: sin él, un `input:{status:ACTIVE, id:…, collections:…}` inline + un `$p` manso en variables pasaría (el guard valida `$p`, el server ejecuta el inline).
2b. Resolver **esa** variable (`variables[$NOMBRE]`): tiene que existir y ser un dict. Se valida SOLO esa, se ignoran las demás variables (señuelos). Si no existe / no es dict → block.
3. `id` presente en el objeto (producto o cualquier variante) → block ("un productSet con id edita un producto existente; el alta va sin id").
4. `status` PRESENTE y == `"DRAFT"` (case-insensitive). Ausente u otro (ACTIVE/ARCHIVED/UNLISTED) → block ("el alta tiene que ser en borrador").
5. Keys de primer nivel ⊆ allowed top-level; si hay extra → block nombrando la primera (`collections`, `metafields`, etc.).
6. `variants` es lista no vacía; cada variante: keys ⊆ allowed-variant; `price` presente y, convertido a centavos (int(float(price)*100)), en `[minPriceCents, maxPriceCents]`; fuera de rango → block.
7. Todo OK → allow. (El registro de creación se escribe DESPUÉS por el skill; `_check_create` NO exige backup previo — un alta no tiene estado viejo.)

- [ ] **Step 1: Tests que fallan** (uno por regla; todos construyen un `tool_input` con `query` + `variables`)

```python
def _create_ti(product):   # helper: arma el tool_input de un productSet por variables
    return {"query": "mutation($p: ProductSetInput!){ productSet(input:$p, synchronous:true){ product{ id } userErrors{ message } } }",
            "variables": {"p": product}}

def _ok_product(**over):
    p = {"title":"Anillo X","status":"DRAFT",
         "variants":[{"sku":"AX-1","price":"120.00","optionValues":[{"optionName":"Color","name":"Plata"}]}]}
    p.update(over); return p

def test_create_allows_valid_draft(monkeypatch, tmp_path):
    # con create-policy presente y todo en orden → allow
    decision,_ = bg._check_create(_create_ti(_ok_product()), <backups_root con policy>, now)
    assert decision == "allow"

def test_create_blocks_status_active():
    d,why = bg._check_create(_create_ti(_ok_product(status="ACTIVE")), root, now)
    assert d == "block" and "borrador" in why.lower()

def test_create_blocks_status_missing():
    prod = _ok_product(); prod.pop("status")
    assert bg._check_create(_create_ti(prod), root, now)[0] == "block"

def test_create_blocks_id_present():
    assert bg._check_create(_create_ti(_ok_product(id="gid://shopify/Product/1")), root, now)[0] == "block"

def test_create_blocks_collections():
    assert bg._check_create(_create_ti(_ok_product(collections=["gid://shopify/Collection/1"])), root, now)[0] == "block"

def test_create_blocks_product_metafields():
    assert bg._check_create(_create_ti(_ok_product(metafields=[{"namespace":"worker","key":"deal","value":"{}"}])), root, now)[0] == "block"

def test_create_blocks_variant_metafields_and_inventory():
    v = _ok_product(variants=[{"sku":"X","price":"120.00","optionValues":[],
                               "inventoryQuantities":[{"locationId":"gid://shopify/Location/1","name":"available","quantity":10}]}])
    assert bg._check_create(_create_ti(v), root, now)[0] == "block"

def test_create_blocks_price_over_ceiling():
    assert bg._check_create(_create_ti(_ok_product(variants=[{"sku":"X","price":"9999999999.00","optionValues":[]}])), root, now)[0] == "block"

def test_create_blocks_price_under_floor():
    assert bg._check_create(_create_ti(_ok_product(variants=[{"sku":"X","price":"0.50","optionValues":[]}])), root, now)[0] == "block"

def test_create_blocks_inline_payload_no_variables():
    ti = {"query":"mutation{ productSet(input:{title:\"X\", status:DRAFT}){ product{id} } }"}
    assert bg._check_create(ti, root, now)[0] == "block"

def test_create_blocks_missing_policy(tmp_path):
    # backups_root sin create-policy.json → block fail-closed
    assert bg._check_create(_create_ti(_ok_product()), str(tmp_path), now)[0] == "block"

def test_load_create_policy_excludes_template():
    # REGRESIÓN issue-3: con blunua Y _template presentes, el loader devuelve UNA política
    # (no None). Contra el REPO ROOT real, no tmp_path.
    root = str(Path(__file__).resolve().parents[1])
    assert bg.load_create_policy(root) is not None

def test_create_blocks_inline_payload_with_decoy_variable():
    # bypass inline+señuelo: input inline ACTIVE/id + $p manso en variables → block
    ti = {"query": 'mutation($p: ProductSetInput!){ productSet(input: {status: ACTIVE, id: "gid://shopify/Product/1"}){ product{id} } }',
          "variables": {"p": _ok_product()}}
    assert bg._check_create(ti, root, now)[0] == "block"
```
(El implementer resuelve el `root con policy`: crear un `create-policy.json` bajo un `tmp_path` y pasar ese root, o apuntar al de blunua vía el repo root. Seguir cómo `test_backup_guard_deals.py` monta `deal-policy.json` para sus tests.)

- [ ] **Step 2: Verificar que fallan** → FAIL (no existe `_check_create`).
- [ ] **Step 3: Implementar** las constantes (`CREATE_ALLOWED_TOP`, `CREATE_ALLOWED_VARIANT`), el loader `load_create_policy` y `_check_create`, siguiendo el estilo de `_check_discount` (leer de `variables`, fail-closed, mensajes en español sin jerga). NO wire al router todavía.
- [ ] **Step 4: Verificar que pasan** → todos PASS.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): _check_create — alta de producto DRAFT con campos cerrados y techo de precio (F2)"`

---

## Task 3: Restructura del router (§7.0.1) — rutear `productset` por nombre

**Files:**
- Modify: `.claude/hooks/backup_guard.py` (`ROOT_FIELD_ALLOWED`, `PRODUCT_WRITE_ALLOWED`, la rama de producto de `evaluate()`)
- Test: `tests/test_create_guard.py`

- [ ] **Step 1: Tests que fallan** (end-to-end por `evaluate`, el camino real del hook)

```python
def _payload(query, variables=None):
    ti = {"query": query}
    if variables is not None: ti["variables"] = variables
    return {"tool_name":"mcp__claude_ai_Shopify__graphql_mutation","tool_input":ti,"cwd":<repo root>}

def test_evaluate_routes_productset_create_allow():
    d,_ = bg.evaluate(_payload(*_create_ti(_ok_product()).values_as_query_vars()), root, now)  # productSet DRAFT válido
    assert d == "allow"

def test_evaluate_blocks_two_product_mutations_one_doc():
    q = ("mutation($p:ProductSetInput!){ a: productSet(input:$p){product{id}} "
         "b: productChangeStatus(productId:\"gid://shopify/Product/1\", status:ACTIVE){product{id}} }")
    assert bg.evaluate(_payload(q, {"p":_ok_product()}), root, now)[0] == "block"   # len(product_roots)!=1

def test_evaluate_blocks_bare_productset_no_variables_not_fail_open():
    # el fail-open histórico: productSet sin id no lo ve GID_RE; el ruteo por nombre lo agarra
    assert bg.evaluate(_payload("mutation{ productSet(input:{title:\"x\"}){product{id}} }"), root, now)[0] == "block"

def test_evaluate_blocks_productset_mixed_with_discount():
    q = ("mutation($p:ProductSetInput!){ productSet(input:$p){product{id}} "
         "discountAutomaticDeactivate(id:\"gid://shopify/DiscountAutomaticNode/1\"){ automaticDiscountId } }")
    assert bg.evaluate(_payload(q, {"p":_ok_product()}), root, now)[0] == "block"   # asuntos mixtos
```

- [ ] **Step 2: Verificar que fallan** (hoy `productset` no está en `ROOT_FIELD_ALLOWED` → bloquea por "fuera de alcance", así que algunos "block" pasan por el motivo equivocado y el `allow` falla) → FAIL.
- [ ] **Step 3: Implementar la restructura** (spec §7.0.1):
  - Agregar `productset` y `productchangestatus` a `PRODUCT_WRITE_ALLOWED` (que ya se une a `ROOT_FIELD_ALLOWED` en la línea 145, así que con eso alcanza; no tocar `ROOT_FIELD_ALLOWED` aparte).
  - En la rama de producto de `evaluate()`, ANTES del chequeo de campos de `productupdate`: **si `product_roots` contiene algún `productset` o `productchangestatus` Y `len(product_roots) != 1` → block** ("una sola operación de producto por pedido").
    - ⚠️ **La condición se acota a productset/productchangestatus A PROPÓSITO.** Un documento con dos `productUpdate` NO debe caer acá: tiene que seguir al chequeo de campos existente (`_product_input_keys` con `finditer`-union), porque `test_backup_guard_deals.py:668` (`test_segundo_product_update_no_escapa_al_control_de_campos`) y `:680` (`test_el_orden_de_los_objetos_no_cambia_la_decision`) verifican que dos `productUpdate` bloquean **por alcance de campo**, con el motivo nombrando `status`/`handle` (regresión c9b2dea). Si la regla nueva dispara sobre multi-`productUpdate`, esos tests fallan porque el motivo cambia. NO se resuelve guteando esas aserciones.
  - Después rutear por nombre: `productset` → `_check_create`; `productchangestatus` → `_check_status_change` (Task 4); `productupdate` → el camino existente de descripción/SEO. Ningún `productset`/`productchangestatus` llega al `return "allow"` final.
- [ ] **Step 4: Verificar que pasan** (y correr TODA la suite de guard existente: `python -m pytest tests/test_backup_guard*.py tests/test_create_guard.py -q` — la restructura NO debe romper ofertas/cosméticos/descripción) → PASS.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): router rutea productset/productchangestatus por nombre, una op de producto por doc (F2)"`

---

## Task 4: `_check_status_change` — rama ARCHIVED (undo)

**Files:**
- Modify: `.claude/hooks/backup_guard.py` (`_check_status_change`, `_covering_create_record`)
- Test: `tests/test_create_guard.py`

`productChangeStatus(productId, status)`. En F2 solo se permite el destino **ARCHIVED** (publicar=ACTIVE es F3). Reglas:
1. Leer `status` y `productId` **del argumento REAL de la mutación `productChangeStatus(...)` en el query** — no de una variable suelta que el query no referencia. Si el argumento es un literal enum (`status: ARCHIVED`) se usa ese; si es una referencia `status: $s`, se resuelve `variables[$s]`. Mismo criterio para `productId`. Esto cierra el mismo **bypass de señuelo** que en el create: un `status: ACTIVE` inline con un `$s = "ARCHIVED"` de señuelo en variables NO puede colar un publish leyendo la variable. Si no se puede determinar un único destino atado al argumento ejecutado → block.
2. `status` destino == `ARCHIVED` → seguir; == `ACTIVE` → block con "publicar todavía no está disponible" (F3 lo habilita); otro (DRAFT/UNLISTED) → block.
3. Existe un registro de creación (`kind:"create"`, ruta `backups/create/`) para ese `productId`, fresco dentro de `createRecordWindowHours` → allow; si no → block ("solo puedo archivar un producto que subí recién").

`_covering_create_record(backups_root, product_id, now, window_hours)`: espejo de `_covering_deal_backup` pero ruta `backups/create/`, `kind=="create"`, y ventana en horas (no los 900s). Frescura doble mtime+ts.

- [ ] **Step 1: Tests que fallan**

```python
def test_status_change_blocks_active_in_f2():
    q = 'mutation{ productChangeStatus(productId:"gid://shopify/Product/1", status:ACTIVE){ product{id} } }'
    assert bg.evaluate(_payload(q), root, now)[0] == "block"

def test_status_change_archive_needs_create_record(tmp_path):
    q = 'mutation{ productChangeStatus(productId:"gid://shopify/Product/1", status:ARCHIVED){ product{id} } }'
    # sin registro create → block
    assert bg.evaluate(_payload_with_root(q, tmp_path), tmp_path, now)[0] == "block"

def test_status_change_archive_allows_with_fresh_create_record(tmp_path):
    # escribir clients/x/backups/create/1-<ts>.json {kind:create, productId:.../1, ts:reciente}
    # → allow
    ...
```

- [ ] **Step 2: Verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar** `_check_status_change` (solo rama ARCHIVED) + `_covering_create_record`, y wire en Task 3's dispatch.
- [ ] **Step 4: Verificar que pasan** → PASS.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): _check_status_change rama ARCHIVED (undo) con registro de creación (F2)"`

---

## Task 5: Anti-bypass + regresión (suite de guard completa)

**Files:**
- Test: `tests/test_create_guard.py`
- Modify (si algún test revela un hueco): `.claude/hooks/backup_guard.py`

- [ ] **Step 1: Tests anti-bypass** (misma disciplina que BXGY/escalones):
  - Señuelo en `variables`: dos objetos ProductSetInput, uno manso y uno con `status:ACTIVE` / `collections` → block (más de un producto en variables).
  - Un `productSet` DRAFT válido adelante y un `productSet` con `metafields` atrás (dos product roots) → block por Task 3.
  - `productSet` con `id` presente disfrazado de create → block.
  - `productChangeStatus` a `DRAFT` (bajar de estado) → block (destino no permitido).
  - Confirmar que las clases viejas siguen intactas: correr `tests/test_backup_guard*.py` enteros.
- [ ] **Step 2-4:** ejecutar; si algo pasa que no debía, arreglar el guard (fail-closed) y re-correr.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "test(w3): anti-bypass de la clase create (señuelos, docs mixtos, id disfrazado) (F2)"`

---

## Task 6: SKILL.md — flujo de creación real (F2)

**Files:**
- Modify: `.claude/skills/subir-productos/SKILL.md`

- [ ] **Step 1:** Extender el SKILL.md (que hoy termina en preview) con la fase de creación:
  - **Gate crear** (explícito sí/no) tras el preview.
  - **Imágenes:** por cada imagen — si es URL, va directo a `files[].originalSource`; si es local, `stagedUploadsCreate` (resource IMAGE) → PUT de los bytes al target → usar el `resourceUrl` devuelto como `originalSource`. Asociar la imagen de variante vía `variants[].file` (que también debe estar en `files`).
  - **Crear:** `Shopify:graphql_mutation` con `productSet(input: $p, synchronous: true)`, `$p` en `variables`, `status: "DRAFT"`, solo los campos del allowed-set (title, handle, descriptionHtml, seo, productType, tags, productOptions, variants[{optionValues, price, sku, barcode, file}], files). **Nunca** collections/metafields/inventoryQuantities. Validar con `validate_graphql_codeblocks` antes.
  - **Registro de creación:** tras el create OK, leer el `product.id` devuelto y escribir `clients/{slug}/backups/create/{idTail}-{YYYYMMDD-HHMMSS}.json` = `{"kind":"create","productId":"gid://…","handle":"…","createdBy":"subir-productos","ts":"<ISO>"}`.
  - **Lote parcial / ventana:** si el lote es grande, avisar; si algo falla a mitad, decir exactamente cuáles se crearon.
  - **Undo ("sacá los que subiste"):** su propio gate + preview; `productChangeStatus(productId, status: ARCHIVED)` de cada id con registro de creación reciente; append al worklog.
  - **Sin jerga**, registro por `store-standards §2`, y aclarar al cliente que quedaron **como borradores** ("todavía no están a la venta; publicarlos es un paso aparte" — F3).
- [ ] **Step 2:** Verificar a mano: ningún paso llama a un tool prohibido; el `productSet` solo lleva campos del allowed-set; el paso 0 sigue intacto.
- [ ] **Step 3: Commit** → `git add .claude/skills/subir-productos/SKILL.md && git commit -m "feat(w3): skill subir-productos — flujo de creación DRAFT + undo(archivar) (F2)"`

---

## Cierre de F2

- [ ] Suite completa: `python -m pytest -q` verde (nada roto en ofertas/cosméticos/descripción).
- [ ] Confirmar que `permissions.deny` NO se aflojó (`create-product` sigue denegado; W3 crea por `productSet` vía guard) y que `FORBIDDEN_MUTATIONS` sigue con `productdelete`/`publishablepublish`/`inventory*`.
- [ ] **Smoke e2e (manual, contra la DEV store — crea borradores reales):** queda como verificación del operador, NO la corre un subagente. Crear 1-2 borradores con variante+imagen local, verificar por read-back que quedaron `DRAFT`, archivar (undo). Documentar en el worklog. (La dev store `Testing StandAlone Framework` es el target de prueba del v1, §15.)
- [ ] F3 (publicar / rama ACTIVE de `_check_status_change`) es el siguiente plan.
