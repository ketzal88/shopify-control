# Builder visual de escalones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un constructor HTML autocontenido, client-facing, dedicado solo a la oferta de escalones, que arma oferta + look con preview del código real del widget y emite un texto que el cliente pega en el chat para que Claude lo aplique por el camino guardado.

**Architecture:** El write nunca sale del par Claude+`backup_guard` (el builder no escribe). Cuatro capas, de abajo hacia arriba: (1) el guard aprende a validar `worker.style` con su backup propio `kind:"style"`; (2) el widget lee `worker.style` y aplica el look con fallback por-key; (3) `armar-escalones` ingiere la config del builder y suma el write de estilo; (4) el builder se genera por sesión horneando productos + techo + el CSS/JS real del widget.

**Tech Stack:** Python (hook `backup_guard.py` + pytest), Liquid + JS vanilla (widget), HTML/CSS/JS autocontenido (builder), Node (tests de la lógica JS de dinero/techo/round-trip), skills en markdown.

**Spec:** `docs/superpowers/specs/2026-07-21-escalones-builder-design.md`

---

## File Structure

| Archivo | Responsabilidad | Acción |
|---|---|---|
| `.claude/hooks/backup_guard.py` | Validación de `worker.style` + `_covering_style_backup` + routing por key | Modificar |
| `tests/test_backup_guard_style.py` | Tests del guard para estilo + cruce de discriminador | Crear |
| `widget/worker-escalones.liquid` | Preámbulo que vuelca `worker.style`; render re-ejecutable; aplicación por-key del look | Modificar |
| `widget/render/worker-render.js` | El render del widget extraído como fuente única (lo inlinea el `.liquid` y lo hornea el builder) | Crear |
| `widget/render/worker-render.test.js` | Tests Node: redondeo por unidad + aplicación de estilo por-key | Crear |
| `widget/escalones-builder.template.html` | El builder: UI (producto / escalones con techo / look / preview / salida). Con slots `__PRODUCTS__`, `__CEILING__`, `__RENDER_JS__`, `__RENDER_CSS__` | Crear |
| `widget/escalones-builder.logic.js` | Lógica pura del builder (techo, cálculo, emit/parse de config) — la inlinea el template y la testea Node | Crear |
| `widget/escalones-builder.test.js` | Tests Node: el techo no deja construir inválido; round-trip config | Crear |
| `.claude/skills/armar-escalones/SKILL.md` | Reconocer `🧩 escalones-config`, ingerirla, y sumar el write de estilo | Modificar |
| `.claude/skills/armar-escalones/strategies/style.md` | Contrato del write de `worker.style` + su backup `kind:"style"` | Crear |
| `.claude/skills/generar-builder-escalones/SKILL.md` | Genera el builder por sesión (lee productos + techo + render, llena el template) | Crear |
| `docs/runbooks/usar-builder-escalones.md` | Cómo el operador entrega el builder al cliente y aplica la config | Crear |

**Nota de decomposición:** cada Task deja software testeable por sí solo. El orden es de abajo hacia arriba: el guard primero (sin él, ningún write de estilo es seguro), después el widget (para que haya algo que estilar), después el skill (el camino de write) y por último el builder (la UI que produce la config).

---

## Task 1: El guard valida `worker.style` con backup propio

**Files:**
- Modify: `.claude/hooks/backup_guard.py`
- Test: `tests/test_backup_guard_style.py` (crear)

Referencia obligatoria antes de empezar: leer `_covering_deal_backup` (`backup_guard.py:350-377`), `_check_metafield` (`:587-644`) y `_check_tiers_schema` para copiar el patrón exacto (glob por ruta + `kind`, doble frescura mtime+ts, "vacío es desconocido").

- [ ] **Step 1: Escribir el test de cobertura del backup de estilo (falla)**

```python
# tests/test_backup_guard_style.py
import json, time, importlib.util
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "backup_guard.py"
spec = importlib.util.spec_from_file_location("backup_guard", SPEC)
guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(guard)

def _write_style_backup(root, product_gid, ts_iso, kind="style", sub="style"):
    tail = product_gid.split("/")[-1]
    d = root / "clients" / "blunua" / "backups" / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tail}-x.json").write_text(json.dumps(
        {"kind": kind, "productId": product_gid, "previous": None, "ts": ts_iso}), encoding="utf-8")

def test_covering_style_backup_accepts_fresh_style_kind(tmp_path):
    gid = "gid://shopify/Product/9"
    now = time.time()
    ts = guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")
    _write_style_backup(tmp_path, gid, ts)
    ok, why = guard._covering_style_backup(tmp_path, gid, now)
    assert ok is True, why
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_backup_guard_style.py::test_covering_style_backup_accepts_fresh_style_kind -q`
Expected: FAIL con `AttributeError: module 'backup_guard' has no attribute '_covering_style_backup'`

- [ ] **Step 3: Implementar `_covering_style_backup` (copia de `_covering_deal_backup`, swap deals→style / "deal"→"style")**

```python
# backup_guard.py — junto a _covering_deal_backup
def _covering_style_backup(backups_root, product_id: str, now: float):
    """(hay_backup_valido, motivo). Backup de ESTILO, discriminado por ruta
    (`backups/style/`) y `kind == "style"` — las dos, igual que el de oferta.
    Un backup de estilo NO habilita un write de plata y viceversa (spec §9.1)."""
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
```

- [ ] **Step 4: Correr el test y verificar que pasa**

Run: `python -m pytest tests/test_backup_guard_style.py -q`
Expected: PASS

- [ ] **Step 5: Test del cruce de discriminador (crítico) — falla**

```python
def test_style_backup_does_not_enable_deal_write(tmp_path):
    gid = "gid://shopify/Product/9"; now = time.time()
    ts = guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")
    _write_style_backup(tmp_path, gid, ts, kind="style", sub="style")
    ok, _ = guard._covering_deal_backup(tmp_path, gid, now)   # write de PLATA
    assert ok is False   # el backup de estilo NO habilita el de oferta

def test_deal_backup_does_not_enable_style_write(tmp_path):
    gid = "gid://shopify/Product/9"; now = time.time()
    ts = guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")
    _write_style_backup(tmp_path, gid, ts, kind="deal", sub="deals")  # backup de oferta
    ok, _ = guard._covering_style_backup(tmp_path, gid, now)
    assert ok is False   # el backup de oferta NO habilita el de estilo
```

- [ ] **Step 6: Correr — deben pasar sin tocar código** (el aislamiento por ruta+kind ya lo garantiza). Si alguno falla, el bug está en el glob o en el check de `kind`.

Run: `python -m pytest tests/test_backup_guard_style.py -q`
Expected: PASS (3 tests)

- [ ] **Step 7: Test de `_check_style` (validación cosmética) — falla**

```python
def _payload(value_dict, owner="gid://shopify/Product/9"):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": "style", "type": "json", "value": json.dumps(value_dict)}]}}

def test_style_accepts_valid(tmp_path, monkeypatch):
    gid = "gid://shopify/Product/9"; now = time.time()
    ts = guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")
    _write_style_backup(tmp_path, gid, ts)
    ok, why = guard._check_style(_payload(
        {"ink": "#4B4B4B", "label": "Llevá más y ahorrá"}), tmp_path, now)
    assert ok == "allow", why

def test_style_blocks_non_hex_color(tmp_path):
    ok, _ = guard._check_style(_payload({"ink": "red; }"}), tmp_path, time.time())
    assert ok == "block"

def test_style_blocks_unknown_key(tmp_path):
    ok, _ = guard._check_style(_payload({"evil": "#000000"}), tmp_path, time.time())
    assert ok == "block"

def test_style_blocks_long_or_angle_text(tmp_path):
    ok, _ = guard._check_style(_payload({"label": "<script>"}), tmp_path, time.time())
    assert ok == "block"
    ok2, _ = guard._check_style(_payload({"label": "x" * 41}), tmp_path, time.time())
    assert ok2 == "block"
```

- [ ] **Step 8: Correr y verificar que falla** (no existe `_check_style`)

Run: `python -m pytest tests/test_backup_guard_style.py -k style_ -q`
Expected: FAIL

- [ ] **Step 9: Implementar `_check_style` + constantes**

```python
# backup_guard.py — constantes arriba
STYLE_COLOR_KEYS = {"ink", "sage", "taupe", "cream"}
STYLE_TEXT_KEYS = {"label", "badge"}
STYLE_KEYS = STYLE_COLOR_KEYS | STYLE_TEXT_KEYS
STYLE_TEXT_MAXLEN = 40
HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

def _check_style(tool_input, backups_root, now: float):
    """metafieldsSet de worker.style: cosmético, cerrado, sin techo (spec §9)."""
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
                return "block", f"{k} tiene que ser texto ≤{STYLE_TEXT_MAXLEN} sin < ni >."
    ok, why = _covering_style_backup(backups_root, owner, now)
    return ("allow", "ok") if ok else ("block", why)
```

- [ ] **Step 10: Rutear en `_check_metafield` por `key`** — modificar la rama de metafield para que `key == "style"` vaya a `_check_style`. En `evaluate()`, donde hoy dice `if "metafieldsset" in low: return _check_metafield(...)`, delegar primero por key:

```python
# En _check_metafield, ANTES de asumir worker.deal: si la entrada es worker.style,
# derivar. (Alternativa: un dispatcher en evaluate que mire la key.) Implementación
# mínima: al principio de _check_metafield, detectar la key y delegar.
    # ... tras armar `entries` y validar len==1 ...
    e0 = entries[0]
    if e0.get("namespace") == "worker" and e0.get("key") == "style":
        return _check_style(tool_input, backups_root, now)
    # resto: worker.deal como hoy
```

- [ ] **Step 11: Correr toda la suite de estilo + la de deals (no debe romper nada)**

Run: `python -m pytest tests/test_backup_guard_style.py tests/test_backup_guard_deals.py -q`
Expected: PASS (todos)

- [ ] **Step 12: Commit**

```bash
git add .claude/hooks/backup_guard.py tests/test_backup_guard_style.py
git commit -m "feat(guard): validar worker.style con backup propio kind:style"
```

---

## Task 2: El widget lee `worker.style` (fuente única re-ejecutable)

**Files:**
- Create: `widget/render/worker-render.js` (el render extraído)
- Create: `widget/render/worker-render.test.js` (Node)
- Modify: `widget/worker-escalones.liquid` (preámbulo de estilo + inline del render + init re-ejecutable)

**Por qué extraer el render:** hoy el JS del widget es un IIFE que corre una vez. El builder necesita re-renderizar en cada cambio con el MISMO código. Se saca el render a `worker-render.js` como `window.WorkerEscalones.render(root, data)` reutilizable; el `.liquid` lo inlinea y lo llama una vez, el builder lo llama en cada cambio. Fuente única, sin duplicar la lección del centavo.

- [ ] **Step 1: Test Node del redondeo por unidad + aplicación de estilo por-key (falla)**

```js
// widget/render/worker-render.test.js
const assert = require('assert');
const { computeTierTotalCents, resolveStyle, DEFAULT_STYLE } = require('./worker-render.js');

// lección del centavo
assert.strictEqual(computeTierTotalCents(62995, 10, 2), 113392);
assert.strictEqual(computeTierTotalCents(62995, 20, 3), 151188);

// fallback por-key: {} => todo default
assert.deepStrictEqual(resolveStyle({}), DEFAULT_STYLE);
// key vacía => default de esa key
assert.strictEqual(resolveStyle({ ink: '' }).ink, DEFAULT_STYLE.ink);
// key presente => override solo de esa key
assert.strictEqual(resolveStyle({ ink: '#000000' }).ink, '#000000');
assert.strictEqual(resolveStyle({ ink: '#000000' }).sage, DEFAULT_STYLE.sage);
console.log('OK worker-render');
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `node widget/render/worker-render.test.js`
Expected: FAIL (`Cannot find module './worker-render.js'`)

- [ ] **Step 3: Crear `worker-render.js`** con: `DEFAULT_STYLE`, `resolveStyle(style)` (fallback por-key), `computeTierUnitCents`/`computeTierTotalCents` (redondeo por unidad), `formatMoney`, y `render(root, data)` que construye el DOM (mover acá la lógica de `buildRows`/`paintNudge`/`paintCta`/`select` del `.liquid`, sin `innerHTML`). Exponer por `module.exports` (Node) y por `window.WorkerEscalones` (browser). Aplicar el estilo resuelto como CSS vars sobre `root.style.setProperty('--we-ink', s.ink)` etc., y `label`/`badge` como textos.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `node widget/render/worker-render.test.js`
Expected: `OK worker-render`

- [ ] **Step 5: Modificar `worker-escalones.liquid`** — (a) el preámbulo vuelca `product.metafields.worker.style` como `<script type="application/json" data-worker-style>{{ product.metafields.worker.style.value | json }}</script>` (o `{}` si no hay); (b) reemplazar el IIFE por: inline de `worker-render.js` (dentro de `{% raw %}`) + una llamada `WorkerEscalones.render(root, { deal, variants, cfg, style })`. Verificar que sin `worker.style` el render usa `DEFAULT_STYLE` (se ve como hoy).

- [ ] **Step 6: Sanity manual del `.liquid`** (no se puede correr Liquid local): revisar que el bloque `{% raw %}...{% endraw %}` envuelve todo el JS con `{{`, y que el JSON de estilo cae a `{}` cuando el metafield no existe.

- [ ] **Step 7: Commit**

```bash
git add widget/render/worker-render.js widget/render/worker-render.test.js widget/worker-escalones.liquid
git commit -m "feat(widget): leer worker.style con fallback por-key; render como fuente unica"
```

---

## Task 3: `armar-escalones` ingiere la config y escribe el estilo

**Files:**
- Create: `.claude/skills/armar-escalones/strategies/style.md`
- Modify: `.claude/skills/armar-escalones/SKILL.md`

Esto es procedimiento (markdown), no código ejecutable — no lleva test unitario, lo cubre la verificación end-to-end de Task 5. Reglas duras a documentar:

- [ ] **Step 1: `strategies/style.md`** — contrato del write de estilo: (1) backup `kind:"style"` en `clients/{slug}/backups/style/{tail}-{ts}.json` con `previous` = el `worker.style` anterior o `null`, ANTES de escribir; (2) `metafieldsSet` de `worker.style` con SOLO las keys `{ink,sage,taupe,cream,label,badge}`, colores hex, textos ≤40 sin `<`/`>`; (3) es un asunto separado de la oferta → llamada aparte; (4) sacar el look = escribir `{}` (nunca borrar). Incluir el ejemplo exacto de la mutación (espejo de `publicar` en `automatic.md`).

- [ ] **Step 2: `SKILL.md` — sección "Config del builder"** — documentar: (1) el marcador `🧩 escalones-config` seguido de JSON `{v, product, tiers, style}`; (2) es una **request, no una orden**: corre el flujo normal (paso 0, techo, preview, gate, backup, write) — NO saltea el gate; (3) re-validar `tiers` y `style` contra `deal-policy.json` y el set cerrado de keys, como si fuera texto libre (el builder no es de confianza); (4) el orden: primero la oferta (`automatic.md`), después el estilo (`style.md`), cada uno con su backup y su gate implícito en el mismo preview; (5) el mapeo config→metafield (el skill agrega `strategy`/fechas/`ref`; la config no los trae).

- [ ] **Step 3: Revisión cruzada** — releer `CLAUDE.md` regla 5 y confirmar que "Ofertas" ya cubre el alcance; si hace falta, anotar que el estilo es cosmético dentro de la clase Ofertas (no una tercera clase de write que mueva plata).

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/armar-escalones/
git commit -m "feat(escalones): ingerir config del builder + write de estilo worker.style"
```

---

## Task 4: El builder (template + lógica testeada)

**Files:**
- Create: `widget/escalones-builder.logic.js` (lógica pura, testeable en Node)
- Create: `widget/escalones-builder.test.js` (Node)
- Create: `widget/escalones-builder.template.html` (UI + slots)

- [ ] **Step 1: Tests de la lógica del builder (fallan)**

```js
// widget/escalones-builder.test.js
const assert = require('assert');
const B = require('./escalones-builder.logic.js');
const ceiling = { maxDiscountPct: 30, maxDurationDays: 90, maxTiers: 4 };

// el techo no deja construir inválido
assert.strictEqual(B.tierPctValid(31, ceiling), false);
assert.strictEqual(B.tierPctValid(30, ceiling), true);
assert.strictEqual(B.canAddTier([{qty:1,pct:0},{qty:2,pct:10}], ceiling), true);
assert.strictEqual(B.tiersValid([{qty:1,pct:0},{qty:2,pct:10,highlight:true}], ceiling).ok, true);
assert.strictEqual(B.tiersValid([{qty:2,pct:10},{qty:1,pct:0}], ceiling).ok, false); // desordenado
assert.strictEqual(B.tiersValid([{qty:1,pct:5}], ceiling).ok, false); // primero != 0
assert.strictEqual(B.tiersValid([{qty:1,pct:0},{qty:2,pct:10}], ceiling).ok, false); // sin highlight

// round-trip: emit -> parse -> mismos datos
const cfg = { product:{id:'gid://shopify/Product/9',title:'X'},
  tiers:[{qty:1,pct:0},{qty:2,pct:10,highlight:true}], style:{ink:'#000000'} };
const text = B.emitConfig(cfg);
assert.ok(text.includes('🧩 escalones-config'));
assert.deepStrictEqual(B.parseConfig(text), { v:1, ...cfg });
console.log('OK builder logic');
```

- [ ] **Step 2: Correr y verificar que falla**

Run: `node widget/escalones-builder.test.js`
Expected: FAIL (módulo inexistente)

- [ ] **Step 3: Implementar `escalones-builder.logic.js`** — `tierPctValid`, `canAddTier`, `tiersValid` (mismas reglas que `_check_tiers_schema` del guard: orden, único, primero pct 0, exactamente un highlight, ≤maxTiers, ≤maxDiscountPct), `emitConfig(cfg)` (agrega `v:1`, serializa con el marcador), `parseConfig(text)` (extrae el JSON del bloque). Exponer por `module.exports` y `window`.

- [ ] **Step 4: Correr y verificar que pasa**

Run: `node widget/escalones-builder.test.js`
Expected: `OK builder logic`

- [ ] **Step 5: Crear `escalones-builder.template.html`** — autocontenido, con slots `__PRODUCTS_JSON__`, `__CEILING_JSON__`, `__RENDER_JS__`, `__RENDER_CSS__`, `__BUILDER_LOGIC__`. Secciones: (a) selector de producto (de `__PRODUCTS_JSON__`); (b) editor de escalones que usa `tiersValid`/`canAddTier` para deshabilitar lo inválido (no deja pasar el techo); (c) pickers de color (los 4) + campos `label`/`badge` con `maxlength=40`; (d) **preview en vivo** = un `<div>` donde en cada cambio se llama `WorkerEscalones.render(previewRoot, {deal,variants,cfg,style})` (el render real de Task 2, inyectado por `__RENDER_JS__`); (e) caja de salida con `emitConfig(...)` y un botón "copiar". El estilo emitido descarta keys iguales al default (para no escribir ruido).

- [ ] **Step 6: Test de humo del template** — un test Node que lee el template, verifica que los 5 slots existen y que, tras un reemplazo trivial, `parseConfig(emitConfig(x))` sigue funcionando embebido (regex de slots presente).

- [ ] **Step 7: Commit**

```bash
git add widget/escalones-builder.*
git commit -m "feat(builder): template + logica con techo enforced y round-trip de config"
```

---

## Task 5: Generación del builder + runbook + verificación end-to-end

**Files:**
- Create: `.claude/skills/generar-builder-escalones/SKILL.md`
- Create: `docs/runbooks/usar-builder-escalones.md`

- [ ] **Step 1: `generar-builder-escalones/SKILL.md`** — flujo: (0) paso 0 (confirmar cliente + tienda, igual que armar-escalones); (1) leer productos vía `Shopify:search_products` (id, título, precio unitario en centavos, imagen); (2) leer `clients/{slug}/deal-policy.json`; (3) extraer `<style>...</style>` y el JS de render de `widget/worker-escalones.liquid` (o leer `widget/render/worker-render.js` directo — preferido, fuente única); (4) llenar `escalones-builder.template.html` reemplazando los slots; (5) escribir el resultado a `clients/{slug}/escalones-builder.html` y decirle al cliente que lo abra. NO escribe a Shopify.

- [ ] **Step 2: `docs/runbooks/usar-builder-escalones.md`** — para el operador: cómo se dispara la generación, cómo el cliente abre el archivo, arma su oferta+look, copia el texto y lo pega en el chat; y qué hace Claude al recibirlo (revalida + preview + gate + backup + write). Checklist de verificación E2E.

- [ ] **Step 3: Verificación end-to-end (manual, contra dev store)** — con el connector en la dev store: generar el builder, abrirlo, armar 2u@10%/3u@20% + cambiar un color, copiar el texto, pegarlo, confirmar que: (a) el preview del builder == el preview del chat == el widget == el carrito, al centavo; (b) el color viaja a `worker.style` y el widget lo aplica; (c) un intento de pegar 40% lo rechaza el techo; (d) los dos backups (`deals/` y `style/`) se crean con su `kind` correcto. Registrar en el worklog. Limpiar (desactivar descuentos, `worker.style` a `{}`, borrar backups de prueba).

- [ ] **Step 4: Correr toda la suite**

Run: `python -m pytest -q && node widget/render/worker-render.test.js && node widget/escalones-builder.test.js`
Expected: todo verde

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/generar-builder-escalones/ docs/runbooks/usar-builder-escalones.md
git commit -m "feat(builder): skill de generacion + runbook + verificacion e2e"
```

---

## Notas de riesgo para el ejecutor

- **El builder no es de confianza:** toda validación del techo en la UI es UX; la de verdad la hace el guard + `armar-escalones` al pegar. No mover ninguna decisión de plata al builder.
- **Fuente única del render:** si en Task 2 no se extrae `worker-render.js`, Task 4 duplicaría la lección del centavo y divergiría. La extracción es obligatoria, no opcional.
- **Instalación del builder ≠ instalación del widget:** el widget se pega al tema una vez (runbook de M2). El builder es un archivo que el cliente abre, no toca el tema.
