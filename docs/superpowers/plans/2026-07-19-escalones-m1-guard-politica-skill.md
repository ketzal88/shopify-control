# Escalones por cantidad — Milestone 1: guardrail, política y skill

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Habilitar que shopify-control cree y neutralice ofertas de escalones por cantidad en Shopify, con techo por cliente enforced por código, sin construir todavía el widget.

**Architecture:** Se extiende el hook `backup_guard.py` para que las mutaciones de descuento pasen de estar en una **blocklist** a estar en una **whitelist cerrada con condiciones** (techo de %, duración, scope explícito, backup fresco). El techo vive en un archivo nuevo `clients/{slug}/deal-policy.json` que el guard lee. Un skill nuevo `armar-escalones` orquesta el flujo. Todo el trabajo de este milestone es **testeable offline**: no requiere tocar Shopify.

**Tech Stack:** Python 3.10 + pytest (hooks y tests), Markdown (skills), JSON (política y metafield). Shopify Admin GraphQL API vía el connector MCP.

**Spec:** `docs/superpowers/specs/2026-07-19-quantity-breaks-design.md` (rev.4)

---

## Alcance de este plan

Este plan cubre **solo el Milestone 1** — el corte que sugiere §15 del spec:

| Dentro | Fuera (Milestone 2, plan aparte) |
|---|---|
| `deal-policy.json` + template | El widget (bloque Custom Liquid) |
| Extensión de `backup_guard.py` | La instalación en el tema |
| Skill `armar-escalones` + estrategias | Todo lo visual de §4 del spec |
| Actualización de `CLAUDE.md` y `store-standards.md` | |

**Por qué este corte:** el widget depende de la incógnita C (§14 del spec), que no está resuelta. El guard, la política y el skill son **agnósticos a las tres incógnitas** y se pueden construir y testear hoy, offline, sin development store.

**Qué queda funcionando al terminar:** se puede armar una oferta de escalones sobre un producto, con techo enforced, backup y undo. El descuento aplica de verdad en el checkout. Lo único que falta es que el comprador **vea** la oferta en la ficha — eso lo trae el widget.

---

## ⚠️ Precondiciones (leer antes de la Tarea 1)

1. **Coordinar con la otra sesión.** `backup_guard.py`, `CLAUDE.md` y `store-standards.md` los viene modificando otra sesión de Claude Code en este mismo repo. Antes de empezar: `git pull`, confirmar que el árbol está limpio y avisar.

2. **El connector apunta a producción.** `get-shop-info` devuelve **Blunua** (`www.blunua.com`, COP). Ninguna tarea de este plan escribe en Shopify, así que no hay riesgo — pero **no corras los tests empíricos de §14 acá**. Van contra development store, en el Milestone 2.

3. **El estado actual es más permisivo de lo que parece.** Verificado ejecutando el guard, no leyéndolo:

   | Mutación | Hoy | Después |
   |---|---|---|
   | `discountAutomaticBasicCreate` | **bloquea** (blocklist, línea 64) | permite con techo |
   | `discountCodeBasicCreate` | **bloquea** (línea 63) | permite si la estrategia está habilitada |
   | `discountAutomaticDelete` y las 4 variantes | **PERMITE** | bloquea |
   | `discountAutomaticBasicUpdate` | **PERMITE** | bloquea |
   | `discountAutomaticBxgyCreate`, free shipping, app | **PERMITE** | bloquea |
   | `discountAutomaticDeactivate` | **PERMITE** | permite (explícito, §9.8) |

   Por qué: la blocklist solo enumera dos mutaciones de descuento, y `GID_RE` solo matchea
   `gid://shopify/Product/\d+` — un gid de `DiscountAutomaticNode` cae en el `allow` final.

   O sea: el milestone **relaja dos** bloqueos y **cierra siete**. El balance neto es a favor de la
   seguridad, pero los dos que se relajan hay que hacerlos bien. Por eso Task 3 aterriza la
   whitelist y la relajación de la blocklist **en el mismo commit** (Step 8): no hay estado
   intermedio commiteado donde el bloqueo se levantó y el techo todavía no está.

---

## Estructura de archivos

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `clients/blunua/deal-policy.json` | Techo de ofertas de blunua | Crear |
| `clients/_template/deal-policy.json` | Techo por defecto de un cliente nuevo | Crear |
| `.claude/hooks/deal_policy.py` | Leer y validar la política; resolver el cliente activo | Crear |
| `.claude/hooks/backup_guard.py` | Whitelist de descuentos + validación del metafield | Modificar |
| `tests/test_deal_policy.py` | Tests de la carga de política | Crear |
| `tests/test_backup_guard_deals.py` | Tests del alcance de descuentos | Crear |
| `.claude/skills/armar-escalones/SKILL.md` | Orquestación del flujo | Crear |
| `.claude/skills/armar-escalones/strategies/automatic.md` | Procedimiento estrategia por defecto | Crear |
| `.claude/skills/armar-escalones/strategies/codes.md` | Procedimiento fallback | Crear |
| `clients/blunua/store-standards.md` | §8 reescrita + §11 Ofertas nueva | Modificar |
| `clients/_template/store-standards.md` | Lo mismo, con los valores del template | Modificar |
| `CLAUDE.md` | Regla 5: nueva clase de write | Modificar |

**Por qué `deal_policy.py` separado y no dentro de `backup_guard.py`:** `backup_guard.py` ya tiene 313 líneas y tres responsabilidades. La carga de política es una unidad con una interfaz clara (`load_policy(root) -> dict | None`) y se testea sola. Meterla adentro haría el guard más difícil de sostener en contexto.

---

## Tarea 1: La política por cliente

**Files:**
- Create: `clients/blunua/deal-policy.json`
- Create: `clients/_template/deal-policy.json`
- Create: `.claude/hooks/deal_policy.py`
- Test: `tests/test_deal_policy.py`

- [ ] **Step 1: Escribir el test que falla**

```python
# tests/test_deal_policy.py
import json
from pathlib import Path
import importlib.util

MOD = Path(__file__).parent.parent / ".claude/hooks/deal_policy.py"
spec = importlib.util.spec_from_file_location("deal_policy", MOD)
dp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dp)

DEFAULTS = {"maxDiscountPct": 30, "maxDurationDays": 90, "maxTiers": 4,
            "requireEndsAt": True, "allowCollectionScope": False,
            "enabledStrategies": ["automatic"]}

def write_policy(root, slug="blunua", **over):
    d = Path(root)/"clients"/slug
    d.mkdir(parents=True, exist_ok=True)
    data = {**DEFAULTS, **over}
    (d/"deal-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d/"deal-policy.json"

def test_loads_the_only_policy_in_the_repo(tmp_path):
    write_policy(tmp_path)
    pol = dp.load_policy(tmp_path)
    assert pol["maxDiscountPct"] == 30

def test_missing_policy_returns_none(tmp_path):
    assert dp.load_policy(tmp_path) is None

def test_two_clients_is_ambiguous_and_returns_none(tmp_path):
    write_policy(tmp_path, slug="blunua")
    write_policy(tmp_path, slug="otra")
    # Con 2+ clientes el guard no puede saber cuál aplica (spec §9.7).
    assert dp.load_policy(tmp_path) is None

def test_template_does_not_count_as_a_client(tmp_path):
    """`_template/` es el scaffold del próximo cliente, no un cliente.
    Si contara, un repo con blunua + template sería 'ambiguo' y bloquearía todo."""
    write_policy(tmp_path, slug="blunua")
    write_policy(tmp_path, slug="_template")
    assert dp.load_policy(tmp_path) is not None
```

- [ ] **Step 2: Correr el test para verificar que falla**

Run: `python -m pytest tests/test_deal_policy.py -v`
Expected: FAIL — `No module named` / `AttributeError: load_policy`

- [ ] **Step 3: Implementación mínima**

```python
# .claude/hooks/deal_policy.py
"""Carga el techo de ofertas del cliente activo (spec §8).

JSON y no markdown a propósito: lo consume un guard de seguridad, y parsear
prosa dentro de un hook que decide si una escritura de precio pasa es frágil.
Misma lección que los backups (.json, no .md) del spec padre §6.

LIMITACIÓN CONOCIDA (spec §9.7): el guard no sabe cuál es el cliente activo.
Con un solo cliente en el repo no hay ambigüedad. Con dos o más devolvemos
None, que el guard traduce en BLOQUEO — falla cerrado, no abierto.
"""
import json
from pathlib import Path

REQUIRED_KEYS = {"maxDiscountPct", "maxDurationDays", "maxTiers",
                 "requireEndsAt", "allowCollectionScope", "enabledStrategies"}


def load_policy(root):
    """dict con la política, o None si no hay exactamente una."""
    hits = sorted(Path(root).glob("clients/*/deal-policy.json"))
    # El template no es un cliente: es el scaffold del próximo.
    hits = [p for p in hits if p.parent.name != "_template"]
    if len(hits) != 1:
        return None
    try:
        data = json.loads(hits[0].read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict) or not REQUIRED_KEYS.issubset(data.keys()):
        return None
    return data
```

- [ ] **Step 4: Correr el test — debe pasar**

Run: `python -m pytest tests/test_deal_policy.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Crear los dos archivos de política**

```json
// clients/blunua/deal-policy.json  Y  clients/_template/deal-policy.json
{
  "maxDiscountPct": 30,
  "maxDurationDays": 90,
  "maxTiers": 4,
  "requireEndsAt": true,
  "allowCollectionScope": false,
  "enabledStrategies": ["automatic"]
}
```

- [ ] **Step 6: Verificar que la suite entera sigue verde**

Run: `python -m pytest -q`
Expected: 69 passed (65 previos + 4 nuevos)

- [ ] **Step 7: Commit**

```bash
git add .claude/hooks/deal_policy.py tests/test_deal_policy.py \
        clients/blunua/deal-policy.json clients/_template/deal-policy.json
git commit -m "feat(ofertas): techo por cliente en deal-policy.json + su loader"
```

---

## Tarea 2: Backup de ofertas — contrato y validación

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_backup_guard_deals.py`

El backup de deal es un tipo **distinto** del de descripción. Se separa por **dos** condiciones simultáneas (spec §7.4): la ruta (`backups/deals/`) y el campo `kind == "deal"`.

- [ ] **Step 1: Escribir los tests que fallan**

```python
# tests/test_backup_guard_deals.py
import json, time, os
from datetime import datetime
from pathlib import Path
import importlib.util

GUARD = Path(__file__).parent.parent / ".claude/hooks/backup_guard.py"
spec = importlib.util.spec_from_file_location("backup_guard", GUARD)
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

PID = "gid://shopify/Product/1"

def write_deal_backup(root, product_id=PID, kind="deal", age_seconds=0, previous=None):
    d = Path(root)/"clients/blunua/backups/deals"
    d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-20260719-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_seconds).isoformat()
    p.write_text(json.dumps({"kind": kind, "productId": product_id,
                             "previous": previous, "ts": ts}), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

def write_description_backup(root, product_id=PID):
    """El backup del OTRO tipo. No debe habilitar un write de deal."""
    d = Path(root)/"clients/blunua/backups"
    d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({
        "productId": product_id,
        "fields": {"descriptionHtml": "old", "seo_title": "o", "seo_description": "o"},
        "ts": datetime.now().isoformat()}), encoding="utf-8")
    return p


def test_fresh_deal_backup_is_accepted(tmp_path):
    write_deal_backup(tmp_path)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is True

def test_deal_backup_without_kind_is_rejected(tmp_path):
    write_deal_backup(tmp_path, kind="otra-cosa")
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_stale_deal_backup_is_rejected(tmp_path):
    write_deal_backup(tmp_path, age_seconds=100000)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_description_backup_does_not_enable_a_deal_write(tmp_path):
    write_description_backup(tmp_path)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_deal_backup_does_not_enable_a_description_write(tmp_path):
    """El glob de descripciones exige el archivo directo bajo backups/,
    y el de deals vive un nivel más abajo. Cruce cerrado en las dos direcciones."""
    write_deal_backup(tmp_path)
    ok, _ = bg._covering_backup(tmp_path, PID, time.time())
    assert ok is False
```

- [ ] **Step 2: Correr — debe fallar**

Run: `python -m pytest tests/test_backup_guard_deals.py -v`
Expected: **4 failed, 1 passed** — los 4 mueren con `AttributeError: module has no attribute
'_covering_deal_backup'`. El que pasa es `test_deal_backup_does_not_enable_a_description_write`,
que llama a `_covering_backup` (el que ya existe) y por eso no toca la funcion nueva.

- [ ] **Step 3: Implementar en `backup_guard.py`**

Agregar después de `_covering_backup` (línea ~229):

```python
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
```

- [ ] **Step 4: Correr — debe pasar**

Run: `python -m pytest tests/test_backup_guard_deals.py -v`
Expected: PASS (5 tests)

- [ ] **Step 5: Verificar que no se rompió nada**

Run: `python -m pytest -q`
Expected: 74 passed

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/backup_guard.py tests/test_backup_guard_deals.py
git commit -m "feat(ofertas): backup de deal con discriminador kind + ruta"
```

---

## Tarea 3: La whitelist de descuentos (el corazón del milestone)

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_backup_guard_deals.py`

⚠️ **Esta tarea escribe los tests ANTES de relajar la blocklist.** Al terminar el Step 4 los tests pasan porque la blocklist sigue bloqueando todo; el Step 5 recién ahí mueve la mutación a la whitelist y los tests siguen verdes por la razón correcta.

- [ ] **Step 1: Escribir los tests de las condiciones**

Agregar a `tests/test_backup_guard_deals.py`:

```python
T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"

def policy(tmp_path, **over):
    from tests.test_deal_policy import write_policy
    return write_policy(tmp_path, **over)

def create_discount(pct=0.10, ends="2026-10-18T00:00:00Z",
                    starts="2026-07-20T00:00:00Z", items=None, product_id=PID):
    """`productId` va SIEMPRE como variable aparte.

    Razón: cuando el descuento apunta a variantes (`productVariantsToAdd`), el
    gid de variante no sirve para buscar el backup, que está indexado por
    producto. El guard exige este campo en vez de intentar derivarlo.
    """
    items = items or {"products": {"productsToAdd": [product_id]}}
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($d: DiscountAutomaticBasicInput!, $productId: ID!) { discountAutomaticBasicCreate(automaticBasicDiscount: $d) { automaticDiscountNode { id } } }",
        "variables": {"productId": product_id, "d": {
            "title": "shopify-control - test",
            "startsAt": starts, "endsAt": ends,
            "minimumRequirement": {"quantity": {"greaterThanOrEqualToQuantity": "2"}},
            "customerGets": {"value": {"percentage": pct}, "items": items},
        }}}}

def test_create_discount_happy_path(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "allow"

def test_create_discount_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "block"

def test_percentage_unit_trap(tmp_path):
    """0.7 es 70%, NO 0.7%. Comparar contra maxDiscountPct=30 sin convertir
    dejaría pasar 0.7 <= 30. Spec §9.4."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(create_discount(pct=0.7), tmp_path, time.time())
    assert d == "block", f"70% debe bloquear con techo 30%, dio: {why}"

def test_missing_endsAt_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(ends=None), tmp_path, time.time())
    assert d == "block"

def test_duration_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(ends="2031-01-01T00:00:00Z"), tmp_path, time.time())
    assert d == "block"

def test_items_all_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(items={"all": True}), tmp_path, time.time())
    assert d == "block"

def test_collection_scope_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(
        create_discount(items={"collections": {"add": ["gid://shopify/Collection/9"]}}),
        tmp_path, time.time())
    assert d == "block"

def test_product_variants_scope_is_allowed(tmp_path):
    """Mitigación de la incógnita C (spec §14): si el umbral resulta ser a nivel
    carrito, el escalón pasa a exigir N de la misma variante.

    El backup se busca por el `productId` de las variables, NO por el gid de
    variante: `"/Product/" in "gid://shopify/ProductVariant/5"` es False."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(
        create_discount(items={"products": {"productVariantsToAdd": ["gid://shopify/ProductVariant/5"]}}),
        tmp_path, time.time())
    assert d == "allow"

def test_discount_without_productId_variable_is_blocked(tmp_path):
    """Sin `productId` no hay forma de saber qué backup respalda este write."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    del p["tool_input"]["variables"]["productId"]
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_codes_strategy_blocked_unless_enabled(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    p["tool_input"]["query"] = p["tool_input"]["query"].replace(
        "discountAutomaticBasicCreate", "discountCodeBasicCreate")
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_no_policy_fails_closed(tmp_path):
    """Sin deal-policy.json no hay techo que aplicar => se bloquea."""
    write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "block"

def test_deactivate_is_always_allowed(tmp_path):
    """Spec §9.8: la compensación no puede estar condicionada a un estado que
    la compensación misma modifica. Sin política y sin backup, igual pasa."""
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/7") { automaticDiscountNode { id } } }'}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow"

def test_update_mutation_is_blocked(tmp_path):
    """Spec §6.3: sin camino de update no hay forma de estirar endsAt ni
    cambiar el percentage después de creado."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { discountAutomaticBasicUpdate(id: "gid://shopify/DiscountAutomaticNode/7", automaticBasicDiscount: {endsAt: "2031-01-01T00:00:00Z"}) { automaticDiscountNode { id } } }'}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_all_delete_variants_are_blocked(tmp_path):
    """Las cinco. Las tres Bulk faltaban en la primera redacción del spec."""
    policy(tmp_path); write_deal_backup(tmp_path)
    for mut in ["discountAutomaticDelete", "discountCodeDelete",
                "discountAutomaticBulkDelete", "discountCodeBulkDelete",
                "discountCodeRedeemCodeBulkDelete"]:
        p = {"tool_name": T_GQL, "tool_input": {
            "query": f'mutation {{ {mut}(id: "gid://shopify/DiscountAutomaticNode/7") {{ deletedId }} }}'}}
        d, _ = bg.evaluate(p, tmp_path, time.time())
        assert d == "block", f"{mut} no bloqueó"

def test_unlisted_discount_mutation_is_blocked(tmp_path):
    """Whitelist CERRADA (spec §9.0): lo no enumerado se bloquea."""
    policy(tmp_path); write_deal_backup(tmp_path)
    for mut in ["discountAutomaticBxgyCreate", "discountAutomaticFreeShippingCreate",
                "discountAutomaticAppCreate", "discountRedeemCodeBulkAdd"]:
        p = {"tool_name": T_GQL, "tool_input": {"query": f"mutation {{ {mut}(x: 1) {{ id }} }}"}}
        d, _ = bg.evaluate(p, tmp_path, time.time())
        assert d == "block", f"{mut} no bloqueó"
```

- [ ] **Step 2: Correr y comparar contra ESTA tabla**

Run: `python -m pytest tests/test_backup_guard_deals.py -v`

Resultado esperado, verificado contra el guard actual:

| Test | Hoy | Por qué |
|---|---|---|
| `test_create_discount_happy_path` | ❌ FAIL | la blocklist bloquea el create |
| `test_product_variants_scope_is_allowed` | ❌ FAIL | ídem |
| `test_discount_without_productId_variable_is_blocked` | ✅ pasa | por la razón equivocada (blocklist) |
| `test_deactivate_is_always_allowed` | ✅ **ya pasa** | `Deactivate` no está en la blocklist y `GID_RE` solo matchea gids de Product, así que cae en el `allow` final |
| `test_update_mutation_is_blocked` | ❌ FAIL | **hoy se permite** |
| `test_all_delete_variants_are_blocked` | ❌ FAIL | **hoy se permiten las cinco** |
| `test_unlisted_discount_mutation_is_blocked` | ❌ FAIL | **hoy se permiten BXGY, free shipping, app y redeem-bulk** |
| el resto de los `block` | ✅ pasan | blocklist |

Total: **`5 failed, 15 passed`**, y las 5 son exactamente las marcadas ❌.

> **No es contabilidad.** Si esperabas "los de block ya pasan" y ves cinco fallas, vas a pensar que
> los tests están mal escritos. Están bien: **el guard de hoy permite borrar descuentos, cambiarles
> el porcentaje después de creados, y crear BXGY.** Esas fallas son el trabajo de este milestone.

- [ ] **Step 3: Implementar la whitelist**

Agregar a `backup_guard.py`, después de `FORBIDDEN_MUTATIONS`:

```python
# --- Ofertas (spec §9) ------------------------------------------------------
# Whitelist CERRADA: toda mutación `discount*` que no esté acá se bloquea.
DISCOUNT_CREATE = {"discountautomaticbasiccreate", "discountcodebasiccreate"}
DISCOUNT_DEACTIVATE = {"discountautomaticdeactivate", "discountcodedeactivate"}
```

Y la función de validación:

Primero el import — **inmediatamente después de los imports que ya tiene el archivo** (línea 29,
debajo de `from pathlib import Path`), nunca arriba de todo:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from deal_policy import load_policy
```

> **Por qué después y no antes:** este snippet usa `Path`, que se importa en la línea 29. Pegado
> al principio del archivo da `NameError: name 'Path' is not defined` y la collection se
> interrumpe. (`sys` ya está importado en la línea 27, no hace falta agregarlo.)
>
> **Y por qué el `insert` no es opcional:** los tests cargan el guard con
> `importlib.util.spec_from_file_location` + `exec_module`, que **no** agrega el directorio del
> módulo a `sys.path`. Sin él, el import explota con `ModuleNotFoundError` en tiempo de
> **collection**: no fallan algunos tests, **no corre ninguno** — los dos archivos de test del
> guard mueren, incluidos los 65 que hoy están verdes.
>
> El camino del hook real (`python .claude/hooks/backup_guard.py`) sí funciona sin el insert,
> porque pone `.claude/hooks` en `sys.path[0]`. O sea que **el test de humo del Step 7 pasaría en
> verde con la suite entera muerta.**

Y ahora sí, las funciones de validación:

```python
def _discount_mutation(text: str) -> str:
    """Nombre de la mutación `discount*` presente en el query, o ''.

    Case-sensitive sobre el prefijo en minúscula a propósito: así NO matchea
    `"gid://shopify/DiscountAutomaticNode/111"` dentro del valor de un
    metafield. Puede dar falso positivo con un campo de selección como
    `discountApplications(first:5)`, y eso falla CERRADO (bloquea), que es el
    lado correcto para equivocarse.
    """
    m = re.search(r"\b(discount[A-Za-z]*)\s*\(", text)
    return m.group(1).lower() if m else ""


def _check_discount(name: str, tool_input, backups_root, now: float):
    """Whitelist de descuentos con techo (spec §9.0-9.4)."""
    if name in DISCOUNT_DEACTIVATE:
        # Sin condiciones a propósito (spec §9.8): la compensación no puede
        # depender de un estado que la compensación misma modifica.
        return "allow", "desactivar siempre está permitido"

    if name not in DISCOUNT_CREATE:
        return "block", (f"'{name}' no está en la whitelist de descuentos. "
                         "Solo se permiten crear (con techo) y desactivar.")

    policy = load_policy(backups_root)
    if policy is None:
        return "block", ("no encontré una política de ofertas única (deal-policy.json). "
                         "Sin techo que aplicar, no se crean descuentos.")

    if name == "discountcodebasiccreate" and "codes" not in policy.get("enabledStrategies", []):
        return "block", "la estrategia de códigos no está habilitada para este cliente."

    d = _discount_input(tool_input)
    if not isinstance(d, dict):
        return "block", "no pude leer los campos del descuento"

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
```

Helpers (agregar junto a los otros):

```python
def _discount_input(tool_input) -> dict:
    """El objeto del descuento, venga por `variables` o inline en el query."""
    if not isinstance(tool_input, dict):
        return {}
    variables = tool_input.get("variables")
    if isinstance(variables, dict):
        for value in variables.values():
            if isinstance(value, dict) and "customerGets" in value:
                return value
    return {}


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


```

> **Decisión tomada (era un hueco en la rev.1 de este plan):** el `productId` va como **variable
> explícita** de la mutación. La alternativa —derivarlo de los ids del `items`— no funciona cuando
> el scope es por variante, que es justamente la mitigación de la incógnita C que §9.1 del spec
> whitelistea. El skill tiene que incluirlo siempre; el test
> `test_discount_without_productId_variable_is_blocked` lo enforcea.

- [ ] **Step 4: Conectar en `evaluate()` — la blocklist va PRIMERO**

En `evaluate()`, dentro de la rama `graphql_mutation`, **después** del loop de `FORBIDDEN_MUTATIONS`:

```python
    if action == "graphql_mutation":
        text = _graphql_text(tool_input)
        low = text.lower()

        # 1. La blocklist general SIEMPRE primero. Ver la nota de abajo.
        for mutation in FORBIDDEN_MUTATIONS:
            if mutation in low:
                return "block", (f"la mutación '{mutation}' está fuera del alcance ...")

        # 2. Recién ahí, ofertas: whitelist cerrada con techo.
        name = _discount_mutation(text)
        if name:
            return _check_discount(name, tool_input, backups_root, now)

        # 3. Metafield de oferta. ANTES del fallthrough por GID_RE — ver Task 4.
        if "metafieldsset" in low:
            return _check_metafield(tool_input, backups_root, now)

        if "productupdate" not in low and not GID_RE.search(text):
            ...
```

> ### ⚠️ Por qué el orden importa (bypass real, no teórico)
>
> **GraphQL admite varios root fields en un mismo documento.** Con la whitelist primero:
>
> ```graphql
> mutation {
>   discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/7") { … }
>   productDelete(input: { id: "gid://shopify/Product/1" }) { … }
> }
> ```
>
> `_discount_mutation` matchea `discountAutomaticDeactivate` → `_check_discount` lo permite **sin
> condiciones** (§9.8) → retorna → **el loop de la blocklist nunca corre** → el `productDelete`
> pasa. Se borra un producto usando la vía rápida de la compensación como llave.
>
> Con la blocklist primero el bypass se cierra y **no cuesta nada**: ninguna de las mutaciones de
> los tests de esta tarea aparece en `FORBIDDEN_MUTATIONS`, así que todos siguen dando lo mismo.

- [ ] **Step 5: Sacar las dos mutaciones de la blocklist**

En `FORBIDDEN_MUTATIONS`, borrar estas dos líneas (ahora las cubre la whitelist con condiciones):

```python
    "discountcodebasiccreate",       # <- borrar
    "discountautomaticbasiccreate",  # <- borrar
```

- [ ] **Step 6: Correr todo — debe pasar**

Run: `python -m pytest -q`
Expected: 89 passed

- [ ] **Step 7: Test de humo del hook real (no solo `evaluate`)**

El hook corre como subproceso leyendo stdin. Los tests llaman `evaluate()` directo, así que un error de import **no se detectaría**. Verificar el camino real:

```bash
echo '{"tool_name":"mcp__claude_ai_Shopify__graphql_mutation","tool_input":{"query":"mutation { discountAutomaticDeactivate(id: \"gid://shopify/DiscountAutomaticNode/7\") { automaticDiscountNode { id } } }"},"cwd":"."}' | python .claude/hooks/backup_guard.py; echo "exit=$?"
```

Expected: `exit=0` (permitido, sin traceback en stderr)

```bash
echo '{"tool_name":"mcp__claude_ai_Shopify__graphql_mutation","tool_input":{"query":"mutation { discountAutomaticBxgyCreate(x:1) { id } }"},"cwd":"."}' | python .claude/hooks/backup_guard.py; echo "exit=$?"
```

Expected: `exit=2` (bloqueado)

> Esto cumple la regla de `core/rules/learning-loop.md` sobre **verificar
> automatizaciones headless**: un hook que solo se probó por función puede estar
> roto en su camino real.

- [ ] **Step 8: Commit**

```bash
git add .claude/hooks/backup_guard.py tests/test_backup_guard_deals.py
git commit -m "feat(ofertas): whitelist cerrada de descuentos con techo por cliente"
```

---

## Tarea 4: Validación del metafield `worker.deal`

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_backup_guard_deals.py`

El widget lee del **metafield**, no del descuento. Un metafield con `pct: 90` anunciaría un precio que el carrito no respeta — el bug de brickwar2 (spec §9.3).

- [ ] **Step 1: Tests**

```python
def metafield_set(tiers, namespace="worker", key="deal"):
    value = json.dumps({"version": 1, "type": "quantity_breaks", "tiers": tiers,
                        "strategy": "automatic", "startsAt": "2026-07-20T00:00:00Z",
                        "endsAt": "2026-10-18T00:00:00Z"})
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [{"ownerId": PID, "namespace": namespace, "key": key,
                             "type": "json", "value": value}]}}}

TIERS_OK = [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}]

def test_metafield_happy_path(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK), tmp_path, time.time())
    assert d == "allow"

def test_metafield_pct_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set([{"qty": 1, "pct": 0}, {"qty": 2, "pct": 90}]),
                       tmp_path, time.time())
    assert d == "block"

def test_metafield_too_many_tiers_is_blocked(tmp_path):
    policy(tmp_path, maxTiers=2); write_deal_backup(tmp_path)
    tiers = [{"qty": n, "pct": n} for n in range(1, 6)]
    d, _ = bg.evaluate(metafield_set(tiers), tmp_path, time.time())
    assert d == "block"

def test_metafield_other_namespace_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK, namespace="otro"), tmp_path, time.time())
    assert d == "block"

def test_metafield_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK), tmp_path, time.time())
    assert d == "block"

def test_metafield_empty_tiers_is_allowed(tmp_path):
    """`sacar escalones` escribe tiers: [] — tiene que poder."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set([]), tmp_path, time.time())
    assert d == "allow"

# --- schema de §5, que el spec afirma "verificado por el guard" -------------

def test_metafield_unordered_tiers_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 0}, {"qty": 5, "pct": 20, "highlight": True}, {"qty": 3, "pct": 10}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_duplicate_qty_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}, {"qty": 2, "pct": 15}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_first_tier_with_discount_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 5}, {"qty": 2, "pct": 10, "highlight": True}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_needs_exactly_one_highlight(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    for tiers in (
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10}],                                    # ninguno
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True},
         {"qty": 3, "pct": 15, "highlight": True}],                                       # dos
    ):
        d, _ = bg.evaluate(metafield_set(tiers), tmp_path, time.time())
        assert d == "block"
```

- [ ] **Step 2: Correr y comparar contra ESTA tabla**

Run: `python -m pytest tests/test_backup_guard_deals.py -k metafield -v`

Resultado esperado: **`2 failed, 8 passed`**.

| Test | Antes del wiring | Por qué |
|---|---|---|
| `test_metafield_happy_path` | ❌ FAIL | es el único que espera `allow` con oferta |
| `test_metafield_empty_tiers_is_allowed` | ❌ FAIL | ídem con `tiers: []` |
| los otros 8 | ✅ pasan | **por la razón equivocada** |

> **Los 8 que pasan son una trampa.** Sin el wiring, `metafieldsSet` cae en `_check_backup`, que
> exige un backup de **descripción** y bloquea. Todos los `assert d == "block"` quedan satisfechos
> por accidente, sin que ninguna de las condiciones del Step 3 exista todavía.
>
> Por eso el Step 4 —correr la suite completa— no es opcional: es lo único que distingue "bloquea
> por la condición correcta" de "bloquea porque cayó en otro camino".

- [ ] **Step 3: Implementar**

```python
def _check_metafield(tool_input, backups_root, now: float):
    """metafieldsSet: solo `worker.deal`, con techo (spec §9.1, §9.3)."""
    variables = (tool_input or {}).get("variables") or {}
    entries = []
    for value in variables.values():
        if isinstance(value, list):
            entries.extend(x for x in value if isinstance(x, dict))
        elif isinstance(value, dict) and "namespace" in value:
            entries.append(value)
    if not entries:
        return "block", "no pude leer el metafield que se está escribiendo."

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
        tiers = data.get("tiers")
        if not isinstance(tiers, list):
            return "block", "la oferta no tiene escalones."
        if len(tiers) > policy["maxTiers"]:
            return "block", (f"la oferta tiene {len(tiers)} escalones y el máximo "
                             f"es {policy['maxTiers']}.")
        why = _check_tiers_schema(tiers, policy)
        if why:
            return "block", why

    ok, why = _covering_deal_backup(backups_root, owner, now)
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
```

**Dónde va la llamada en `evaluate()`:** en el bloque del Step 4 de la Task 3, en la posición
marcada como `# 3.` — antes de la línea `if "productupdate" not in low and not GID_RE.search(text)`.

> **Nota sobre `ownerType`:** no se valida, a propósito. `MetafieldsSetInput` **no tiene ese
> campo** — validarlo sería comparar contra `None` siempre. La restricción real de que la oferta
> vaya sobre un producto la da el `ownerId`, que es el gid con el que se busca el backup.

> **Limitación conocida:** el loop hace `owner = e.get("ownerId") or owner`, así que un
> `metafieldsSet` en lote sobre dos productos solo verifica el backup **del último**. El techo
> (`pct`, `maxTiers`, namespace) sí se aplica a **todas** las entradas, así que el riesgo de plata
> está acotado; lo que se relaja es la garantía de backup. El skill escribe un producto por vez.

- [ ] **Step 4: Correr todo**

Run: `python -m pytest -q`
Expected: 99 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/backup_guard.py tests/test_backup_guard_deals.py
git commit -m "feat(ofertas): techo tambien en el metafield, no solo en el descuento"
```

---

## Tarea 5: El skill `armar-escalones`

**Files:**
- Create: `.claude/skills/armar-escalones/SKILL.md`
- Create: `.claude/skills/armar-escalones/strategies/automatic.md`
- Create: `.claude/skills/armar-escalones/strategies/codes.md`

Seguir el patrón de `.claude/skills/mejorar-descripcion/SKILL.md` — **leerlo primero**, sobre todo el paso 0 (identificar cliente + `get-shop-info` contra `connection.md`) y el formato del preview sin jerga.

- [ ] **Step 1: Leer el skill de referencia**

Run: `cat .claude/skills/mejorar-descripcion/SKILL.md`

- [ ] **Step 2: Escribir `SKILL.md`**

Frontmatter (la `description` es lo que decide cuándo se invoca):

```yaml
---
name: armar-escalones
description: Arma ofertas de "llevá más y ahorrá" en un producto de Shopify (2 unidades -10%, 3 unidades -18%). Muestra un preview en el chat, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide poner descuentos por cantidad, ofertas por volumen, o que se venda más de a varios.
---
```

Cuerpo: el flujo de 9 pasos de §7.1 del spec, con el orden de escritura de §7.2 (**crear → publicar → desactivar**) y el flujo de `sacar escalones` de §7.3. Reglas duras a incluir textualmente:

- Paso 0 obligatorio: cliente + `get-shop-info` vs `connection.md`, abortar si no coinciden.
- Nunca adivinar el producto.
- El preview va en **lenguaje natural, sin jerga** (nada de "metafield", "gid", "mutation").
- El gate es explícito: no se escribe sin un "sí" del cliente.
- El backup va **antes** de escribir, en `clients/{slug}/backups/deals/{tail}-{YYYYMMDD-HHMMSS}.json`.
- Registrar en `worklog.md` cada `ref` creado y desactivado (auditoría, **no** permiso — §9.8).

- [ ] **Step 3: Escribir las dos estrategias**

`automatic.md` con la mutación de §6.1 del spec y `codes.md` con la de §6.2, cada una documentando `crear` / `desactivar` / `verificar`.

- [ ] **Step 4: Verificar que el skill se descubre**

Reiniciar la sesión de Claude Code y confirmar que `armar-escalones` aparece en la lista de skills.

> Los skills y hooks se cargan al **iniciar** la sesión (ver `CLAUDE.md`). Sin reiniciar, no aparece.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/armar-escalones/
git commit -m "feat(ofertas): skill armar-escalones con sus dos estrategias"
```

---

## Tarea 6: Gobernanza — actualizar las reglas que este milestone contradice

**Files:**
- Modify: `CLAUDE.md`
- Modify: `clients/blunua/store-standards.md`
- Modify: `clients/_template/store-standards.md`

Sin esto el repo queda con una regla dura que el skill nuevo viola (spec §10).

- [ ] **Step 1: `CLAUDE.md`, regla 5**

⚠️ **Releer el archivo antes de editar.** Este bloque quedó desactualizado una vez ya (otra sesión
cambió la regla 5 mientras se escribía este plan). Verificar que las tres líneas de abajo siguen
siendo las que están.

Reemplazar **solo estas tres líneas** (hoy 37-39):

```markdown
5. **Alcance de escritura v1:** solo descripción (`descriptionHtml`, vía `Shopify:update-product`)
   + SEO meta title/description (`seo.title`/`seo.description`, vía `Shopify:graphql_mutation`).
   NUNCA precio, stock, status, tags, título ni handle/URL.
```

por:

```markdown
5. **Alcance de escritura:** dos clases, cada una con su guardrail.
   - **Texto:** descripción (`descriptionHtml`, vía `Shopify:update-product`) + SEO meta
     title/description (`seo.title`/`seo.description`, vía `Shopify:graphql_mutation`).
   - **Ofertas:** escalones por cantidad — descuentos nativos + metafield `worker.deal`, con
     techo por cliente en `deal-policy.json` que el hook enforcea. Ver
     `docs/superpowers/specs/2026-07-19-quantity-breaks-design.md`.
   - NUNCA precio de lista, stock, status, tags, título ni handle/URL.
```

> **Dos cosas que NO hay que perder:**
> 1. **`tags` y `título` siguen en la lista de prohibidos.** El código los sigue bloqueando
>    (`ALLOWED_PRODUCT_INPUT_KEYS`), pero la regla 5 es el texto que gobierna: si se caen de acá,
>    la prosa queda más débil que el código.
> 2. **Las líneas 40-42 (`**Esto está enforced por diseño, no por prosa:**` …) se dejan intactas.**
>    Spec §10 se apoya en ellas: son las que dicen que `permissions.deny` y `backup_guard` hacen
>    cumplir el alcance. Borrarlas al "reemplazar la regla 5" sería quitar la justificación de por
>    qué `create-discount` sigue denegado.

- [ ] **Step 2: `store-standards.md` §8 — en LOS DOS archivos**

⚠️ **Esta edición va en `clients/blunua/store-standards.md` (línea 78) Y en
`clients/_template/store-standards.md` (línea 51).** Los dos tienen la misma línea. Hacer solo uno
deja el grep del Step 4 devolviendo la del template — o sea, la puerta de verificación del propio
plan no pasa.

Ambos dicen hoy:

```markdown
- NUNCA precio, stock, status ni handle/URL sin gate estructural (OK de Gabriel).
```

Reemplazar esa línea **y la de arriba** por:

```markdown
- Los skills tocan dos field sets, cada uno con su guardrail:
  - **Texto:** descripción (`descriptionHtml`, vía `update-product`) + SEO (`seo.title`/`seo.description`, vía `graphql_mutation`).
  - **Ofertas:** escalones por cantidad — descuentos nativos + metafield `worker.deal`, con el techo de §11.
- NUNCA precio de lista, stock, status ni handle/URL.
```

> El "sin gate estructural (OK de Gabriel)" se va a propósito: contradice D5 del spec padre
> (Gabriel no es gate) y el techo de §11 ya cumple esa función por código.

- [ ] **Step 3: `store-standards.md` §11 nueva**

Respetar el formato del archivo: `## N. Título [ESTABLE|VIVO]` + viñetas con `-`.

```markdown
## 11. Ofertas — escalones por cantidad [ESTABLE]
- La política vive en `deal-policy.json` (misma carpeta). **Ese archivo es la fuente de verdad:
  lo lee el hook.** Esta sección solo lo explica en palabras.
- Techo actual: **30%** máximo por escalón, **90 días** máximo de duración, **4 escalones** máximo.
- Toda oferta necesita fecha de fin. No hay ofertas eternas.
- Nunca a nivel colección ni sobre todo el catálogo: siempre productos o variantes explícitos.
- Para sacar una oferta se **desactiva**, no se borra: queda el registro de qué se ofreció y cuándo.
```

Mismo bloque en `clients/_template/store-standards.md`, con los ⚠️ del template en los valores.

- [ ] **Step 4: Verificar que no quedó ninguna contradicción**

Run: `grep -rn "NUNCA precio, stock\|nunca precio, stock" CLAUDE.md clients/`

Expected: **cero resultados.** Si aparece alguno, es una copia de la regla vieja que quedó sin
actualizar — hay que reemplazarla por la nueva redacción de `CLAUDE.md` regla 5.

Run: `grep -rn "solo descripción\|solo descripcion" CLAUDE.md clients/*/store-standards.md`

Expected: cero, o solo dentro de la nueva redacción que enumera **dos** field sets.

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md clients/blunua/store-standards.md clients/_template/store-standards.md
git commit -m "docs(ofertas): regla 5 y store-standards reconocen la clase ofertas"
```

---

## Tarea 7: Cierre del milestone

- [ ] **Step 1: Suite completa**

Run: `python -m pytest -q`
Expected: 99 passed

- [ ] **Step 2: Los dos tests de humo del hook** (Tarea 3, Step 7) — repetir y confirmar `exit=0` / `exit=2`

- [ ] **Step 3: Verificar que `permissions.deny` NO cambió**

Run: `grep -c "create-discount" .claude/settings.json`
Expected: `1` — sigue denegado (spec §10). Si alguien lo sacó, revertir.

- [ ] **Step 4: Actualizar el worklog de blunua** con lo que se construyó y lo que queda pendiente.

- [ ] **Step 5: Commit final**

```bash
git add clients/blunua/worklog.md
git commit -m "docs: worklog del milestone 1 de escalones"
```

---

## Cabos sueltos conocidos (decididos, no olvidados)

Ninguno bloquea el milestone. Se documentan para que nadie los "descubra" y los arregle mal.

| Cabo | Decisión |
|---|---|
| `metafieldDefinitionCreate` (§9.1, setup solo-operador) cae en el `allow` final del guard | Se deja así en M1. Solo se usa una vez, en setup, y no hay flujo de cliente que lo alcance. Si el M2 lo necesita, se le agrega su condición. |
| El happy path usa exactamente 90 días contra `maxDurationDays: 90` y pasa porque la comparación es `>` | Correcto y deliberado: el techo es inclusivo. Vale un test de borde a cada lado (89 y 91) si se quiere ser explícito. |
| `_discount_mutation` da falso positivo con campos de selección tipo `discountApplications(first:5)` | Falla **cerrado** (bloquea), que es el lado correcto. Documentado en el docstring. |
| `from tests.test_deal_policy import write_policy` en `test_backup_guard_deals.py` | Funciona con `python -m pytest` desde la raíz, que es lo que fija `stack.json`. Falla solo si se invoca pytest desde adentro de `tests/`. |

---

## Lo que queda para el Milestone 2

1. **Correr los tres tests empíricos de §14** contra development store. **Bloqueante** para el widget.
2. **El widget** (§4 del spec), cuya forma depende del resultado de la incógnita C.
3. **Instalación** del bloque Custom Liquid en el tema de blunua.

**No arrancar el Milestone 2 sin el punto 1.** Si la incógnita C sale mal, el widget cambia de forma y se rehace trabajo.
