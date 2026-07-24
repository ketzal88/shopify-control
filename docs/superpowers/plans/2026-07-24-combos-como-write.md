# Combos como write (W4-1) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que `armar-combo` cree combos de verdad — un descuento BXGY "comprá A, llevate B con X% off" basado en la co-compra real — extendiendo el guard de ofertas con una **caja combo** (OR con la caja regalo) de techo/scope propios, fail-closed.

**Architecture:** Reuso de la clase BXGY (`discountAutomaticBxgyCreate` + `worker.deal`). En `backup_guard.py`: `_check_bxgy` acepta el discount si satisface la caja **regalo** (actual, intacta) **o** la caja **combo** (nueva, estricta-o-igual salvo el giftable relajado); `_check_metafield` rutea `type:"combo"` a un `_check_combo_metafield` propio; `_combo_ceilings` gatea fail-closed. `deal-policy.json` suma claves **opcionales**. `armar-combo/SKILL.md` gana el camino de escritura.

**Tech Stack:** Python 3 (stdlib), pytest. GraphQL: `discountAutomaticBxgyCreate` (pct<100), `metafieldsSet` (worker.deal type:combo), `discountAutomaticDeactivate` (undo). Todo ya en la whitelist del guard.

**Spec:** `docs/superpowers/specs/2026-07-24-combos-como-write-design.md`.

## Contexto del guard (leer antes de tocar `backup_guard.py`)
- `_check_bxgy(names, tool_input, backups_root, now)` valida el `discountAutomaticBxgyCreate` con las reglas del regalo: `_gift_ceilings` (maxGiftPct/maxGetQty/minBuyGetRatio), `_bxgy_inputs`, `_gift_effect_pct_int`, `_bxgy_single_product`, `_bxgy_scope_ok` (giftable para cruzado), buy_qty≥1, get_qty≤maxGetQty, usesPerOrderLimit==1, endsAt, backup, productId==buy_gid.
- `_check_metafield` rutea por `data.get("type")`: `"bxgy"` → `_check_bxgy_metafield` (termina en `_bxgy_scope_ok`), `tiers` → escalones.
- `_gift_ceilings(policy)` devuelve la tupla o None (con `is True` estricto e int-no-bool).
- `deal_policy.load_policy` globa `clients/*/deal-policy.json`, excluye `_template`, exige `REQUIRED_KEYS.issubset`.
- **Fail-closed, exit 2.** Cada caja se evalúa COMPLETA por sí sola (nunca mezclar dimensiones — spec §4.1).

---

## Task 1: `deal-policy` gana las claves de combo (opcionales) + `_combo_ceilings`

**Files:**
- Modify: `clients/blunua/deal-policy.json`, `clients/_template/deal-policy.json`
- Modify: `.claude/hooks/backup_guard.py` (`_combo_ceilings`)
- Test: `tests/test_combo_guard.py`

- [ ] **Step 1: Tests que fallan**

```python
# tests/test_combo_guard.py — cargar el módulo por importlib (patrón del repo)
import importlib.util, json
from pathlib import Path
HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

def test_combo_ceilings_present_and_valid():
    pol = {"allowCombo": True, "maxComboPct": 25, "maxComboGetQty": 2}
    assert bg._combo_ceilings(pol) == (25, 2)

def test_combo_ceilings_none_when_disabled_or_missing_or_malformed():
    assert bg._combo_ceilings({"allowCombo": False, "maxComboPct": 25, "maxComboGetQty": 2}) is None
    assert bg._combo_ceilings({"maxComboPct": 25, "maxComboGetQty": 2}) is None   # allowCombo ausente
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": 25}) is None    # falta getqty
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": "25", "maxComboGetQty": 2}) is None  # str
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": True, "maxComboGetQty": 2}) is None  # bool no es int

def test_existing_deal_policy_still_loads():
    # las claves nuevas son OPCIONALES: deal-policy.json sigue cargando (no en REQUIRED_KEYS)
    root = Path(__file__).resolve().parents[1]
    from importlib import import_module
    dp_spec = importlib.util.spec_from_file_location("deal_policy", HOOKS / "deal_policy.py")
    dp = importlib.util.module_from_spec(dp_spec); dp_spec.loader.exec_module(dp)
    assert dp.load_policy(str(root)) is not None
```

- [ ] **Step 2: Verificar que fallan** → FAIL.
- [ ] **Step 3: Implementar.** Agregar a ambos `deal-policy.json`: `"allowCombo": true, "maxComboPct": 25, "maxComboGetQty": 2`. **NO** tocar `deal_policy.REQUIRED_KEYS`. Implementar `_combo_ceilings(policy)` espejo de `_gift_ceilings` (int-no-bool, `allowCombo is True`).
- [ ] **Step 4: Verificar que pasan** + `python -m pytest tests/test_deal_policy.py -q` (no romper la carga). → PASS.
- [ ] **Step 5: Commit** → `git add clients/blunua/deal-policy.json clients/_template/deal-policy.json .claude/hooks/backup_guard.py tests/test_combo_guard.py && git commit -m "feat(w4): _combo_ceilings + claves de combo opcionales en deal-policy"`

---

## Task 2: caja combo en `_check_bxgy` (el OR)

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_combo_guard.py`

`_check_bxgy` acepta el discount si pasa la caja regalo (actual) **o** la caja combo. Refactor sugerido: extraer la lógica regalo actual en `_bxgy_gift_box(...)` (devuelve (ok, why)) sin cambiar su comportamiento, agregar `_bxgy_combo_box(...)`, y que `_check_bxgy` devuelva allow si alguna da ok, si no el `why` más informativo. **Cada caja evalúa TODAS sus condiciones (completa); nunca se comparten dimensiones.**

Caja combo (spec §4.1): `_combo_ceilings` no None; `0 < pct ≤ maxComboPct`; `pct < 100`; buy = producto único (`_bxgy_single_product`, no all/collection/variant); `buy_qty ≥ 1`; get = producto único (sin giftable); `1 ≤ get_qty ≤ maxComboGetQty`; `usesPerOrderLimit == 1`; `endsAt` (+duración); backup (`_covering_deal_backup`); `productId == buy_gid`.

- [ ] **Step 1: Tests que fallan** (por `evaluate`, el camino real)

```python
def _combo_bxgy_vars(pct=0.20, buy_qty=1, get_qty=1, uses=1, buy="gid://shopify/Product/1", get="gid://shopify/Product/2"):
    # arma el objeto de variables de un discountAutomaticBxgyCreate combo
    ...  # el implementer lo arma siguiendo test_backup_guard_bxgy.py

def test_combo_cross_to_non_giftable_allowed(tmp_path):        # 20% cruzado a no-giftable, get_qty 1 → allow
def test_combo_blocks_over_maxcombopct(tmp_path):              # 30% > 25 → block
def test_combo_blocks_free(tmp_path):                          # pct 100 → block (no es combo)
def test_combo_blocks_when_allowcombo_false(tmp_path):         # allowCombo:false → block
def test_combo_blocks_get_qty_over_cap(tmp_path):              # "comprá 1, llevate 1000 al 25%" → block (el hueco)
def test_combo_blocks_uses_per_order_not_one(tmp_path):        # usesPerOrderLimit != 1 → block
def test_combo_blocks_buy_qty_zero(tmp_path):                  # buy_qty 0 = cupón → block
def test_combo_blocks_buy_collection(tmp_path):                # buy = colección/all → block
def test_gift_box_still_intact(tmp_path):                      # regalo gratis a giftable sigue allow; cruzado no-giftable 100% sigue block
def test_no_mix_and_match(tmp_path):                           # 100% + no-giftable no toma "no-giftable" del combo y "pct<=100" del regalo → block
```

- [ ] **Step 2: Verificar que fallan** → FAIL (hoy un cruzado no-giftable al 25% bloquea).
- [ ] **Step 3: Implementar** las dos cajas + el OR. Reusar `_gift_effect_pct_int`, `_bxgy_single_product`, `_as_pos_int`, `_duration_days`, `_covering_deal_backup`.
- [ ] **Step 4: Verificar que pasan** + `python -m pytest tests/test_backup_guard_bxgy.py tests/test_backup_guard_deals.py -q` (regalo/escalones intactos). → PASS.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w4): caja combo en _check_bxgy (OR con la caja regalo), fail-closed (W4-1)"`

---

## Task 3: `_check_combo_metafield` + ruteo `type:"combo"`

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_combo_guard.py`

`_check_combo_metafield(data, policy)` PROPIO (no reusar `_check_bxgy_metafield`): mismas caps que la caja combo — `_combo_ceilings` no None, pct en (0,100) ≤ maxComboPct, `1 ≤ get_qty ≤ maxComboGetQty`, `buy_qty ≥ 1`, buy y get productos explícitos (sin giftable). Rutear en `_check_metafield`: `data.get("type") == "combo"` → `_check_combo_metafield`.

- [ ] **Step 1: Tests que fallan:** `type:"combo"` con pct (0,100)≤techo y get_qty≤techo → allow; pct 100 → block; pct>techo → block; get_qty>techo → block; buy/get sin producto explícito → block; `allowCombo:false` → block.
- [ ] **Step 2: Verificar** → FAIL.
- [ ] **Step 3: Implementar** `_check_combo_metafield` + el ruteo.
- [ ] **Step 4: Verificar** + suite de ofertas verde → PASS.
- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w4): _check_combo_metafield + ruteo type:combo (W4-1)"`

---

## Task 4: anti-bypass + regresión

**Files:**
- Test: `tests/test_combo_guard.py`

- [ ] Tests: combo mezclado con otra mutación → block (un asunto por doc, ya existe); señuelo de segundo BXGY en variables → block; el mix-and-match del §6; y correr TODA la suite de ofertas (`tests/test_backup_guard*.py`) + `tests/test_combo_guard.py` verde.
- [ ] Commit → `git add -A && git commit -m "test(w4): anti-bypass y regresión de la caja combo (W4-1)"`

---

## Task 5: `armar-combo/SKILL.md` — el camino de escritura

**Files:**
- Modify: `.claude/skills/armar-combo/SKILL.md`

- [ ] Extender el skill (que hoy es solo-lectura) con el write (spec §5): tras proponer y que el cliente elija, copy de combo + humanizer + checklist → preview → gate → backup de oferta (kind:"deal") → `discountAutomaticBxgyCreate` (pct<100) + `metafieldsSet` worker.deal `type:"combo"` (validar con `validate_graphql_codeblocks`) → worklog → undo (`discountAutomaticDeactivate`). Sin jerga ("combo", no "BXGY"); registro por `store-standards §2`; humanizer. Si `allowCombo:false`/sin techo: decir en natural que armar el combo todavía no está disponible y anotarlo (no intentar el write). Actualizar el frontmatter/description y las "prohibiciones duras" (que ya no son todas prohibiciones: crear el combo ahora SÍ, dentro del techo).
- [ ] Verificar a mano: paso 0 intacto; el write solo toca discount+metafield; ningún tool prohibido.
- [ ] Commit → `git add .claude/skills/armar-combo/SKILL.md && git commit -m "feat(w4): armar-combo gana el camino de escritura (combo BXGY) (W4-1)"`

---

## Cierre
- [ ] Suite completa `python -m pytest -q` verde (nada roto en escalones/regalos/productos/descripción).
- [ ] `permissions.deny` y `FORBIDDEN_MUTATIONS` intactos; `deal_policy.REQUIRED_KEYS` intacto (claves de combo opcionales).
- [ ] e2e manual (operador, dev store): crear un combo, verificar el descuento en checkout, desactivar (undo).
