# shopify-control v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la fundación native-Claude de shopify-control (scaffold + estándares de blunua + 3 skills + hook de seguridad) para que un cliente ecom no técnico mejore descripciones (SEO/GEO) y consulte su tienda Shopify, con seguridad por diseño y sin que Gabriel apruebe cada acción.

**Architecture:** Nativo en Claude, sin backend. Connector oficial de Shopify (Admin API) = las manos; skills = procedimientos que reusan skills de handsOn; `clients/{slug}/store-standards.md` = conocimiento curado; un `PreToolUse` hook en Python fuerza backup antes de todo write; un linter mecánico refuerza el checklist de calidad.

**Tech Stack:** Markdown (skills, docs), JSON (settings, .mcp), Python 3 + pytest (hook + linter), git. Shopify connector (MCP) para el runtime.

**Modelo del v1 (importante):** v1 = *build + piloto operado por Gabriel*. Corre en el entorno de Gabriel, donde los skills reusados de handsOn (`humanizer`, `seo-geo`, etc.) y el connector de Shopify están disponibles. El empaquetado para el self-service del cliente (bundlear skills, distribuir) es D2 y queda **fuera de este plan**.

**Spec de referencia:** `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`

---

## Estado (actualizado 2026-07-19)

**Tasks 0 a 7: implementadas.** Task 8 (validación end-to-end): corrida contra una dev store, con el detalle de qué quedó verificado y qué no marcado ítem por ítem abajo.

Este plan se conserva como registro de cómo se construyó, así que **los bloques de código de abajo son el plan original, no el código final**. Donde el resultado real difiere se agregó una nota `⚠️ REALIDAD`. Los tres desvíos que más importan:

1. **Los campos.** El plan asumía `body_html` / `meta_title` / `meta_description` planos, y un solo write. La realidad son **dos writes**: `descriptionHtml` vía `Shopify:update-product`, y `seo.title`/`seo.description` vía `Shopify:graphql_mutation` con `productUpdate(product:{...})`.
2. **El SEO no va por metafields.** La nota M1 de Task 7 mandaba a usar `global.title_tag` / `global.description_tag`. Es falso: el SEO es el campo nativo `seo` del producto, se lee con `graphql_query` y se escribe con `productUpdate`. Además `get-product` **no** devuelve el SEO, y eso causó un bug real (backup con SEO vacío → el undo borraba el SEO del cliente).
3. **El guard creció.** De "no write sin backup" a cuatro capas: `permissions.deny`, alcance de campos en `backup_guard`, `description_lint` ejecutable, y los gates del framework (`core/` + `stack.json`). Ver spec §11.

---

## Supuestos y precondiciones

- Python 3 + `pytest` disponibles (handsOn ya usa hooks Python: `scripts/hooks/*.py`). Si falta pytest: `pip install pytest`.
- Los skills reusados viven en `handsOn-Worker/skills/` y en plugins instalados; en el entorno de Gabriel son accesibles. No se copian al repo en v1.
- El Shopify de blunua **todavía no está conectado**. Todo el plan es construible sin la tienda viva. La validación end-to-end (Task 8) se hace contra un **Shopify development store** (gratis, lo crea Gabriel) para no bloquear en blunua.
  - ⚠️ **REALIDAD:** la validación se corrió contra la dev store *Testing StandAlone Framework*. La tienda real de blunua ya quedó conectada y verificada, pero **todavía no se le escribió nada**.
- Unknown a resolver en runtime (Task 7/8): el **nombre exacto del/los tool(s) de escritura** del connector de Shopify y la forma de su payload. El hook se diseña parametrizable para ajustarlo sin reescribir lógica.
  - ⚠️ **RESUELTO.** Son dos tools, no uno: `Shopify:update-product` (payload plano `{id, descriptionHtml}`) y `Shopify:graphql_mutation` (`productUpdate`, con los campos en el query **o en `variables`**; el guard tiene que mirar los dos). El nombre MCP real que llega al hook es `mcp__claude_ai_Shopify__update-product`, así que el guard lo normaliza partiendo por `__` y `:`.

---

## File Structure

| Archivo | Responsabilidad |
|---|---|
| `CLAUDE.md` | Contexto del repo + convenciones (regla sin-jerga, cómo arranca Gabriel vs cliente, link a standards) |
| `README.md` | Entrada no técnica para el cliente |
| `.gitignore` | Ignora `__pycache__`, `.pytest_cache`, temporales |
| `.mcp.json` | Config del connector de Shopify (placeholder hasta conectar) |
| `.claude/settings.json` | Registra el `PreToolUse` hook. ⚠️ REALIDAD: además lleva `permissions.deny` con 7 tools de escritura del connector, y registra los hooks del framework (matcher `Bash`) |
| `.claude/hooks/backup_guard.py` | Hook: bloquea un write de Shopify si no hay backup que lo cubra. Código testeable. ⚠️ REALIDAD: también bloquea por alcance de tool y de campos |
| `.claude/hooks/description_lint.py` | Linter mecánico: em-dash, longitud, keyword. Lo corre el checklist. Código testeable. ⚠️ REALIDAD: además materiales falsos, lujo-vacío, claims médicos, voseo y bloque GEO, y tiene CLI |
| `tests/test_backup_guard.py` | pytest del hook |
| `tests/test_description_lint.py` | pytest del linter |
| `tests/test_secret_scan.py` | ⚠️ REALIDAD (no estaba en el plan): pytest del secret-scan del framework, con la regresión de CRLF en Windows |
| `stack.json` + `core/` | ⚠️ REALIDAD (no estaba en el plan): claude-code-framework de Worker. Aporta secret-scan en commit, pre-push con los tests, `push: operator-only` y close-protocol |
| `.claude/skills/mejorar-descripcion/SKILL.md` | Skill write (W1): flujo seguro de mejora de descripción |
| `.claude/skills/reporte-tienda/SKILL.md` | Skill read (R1): resultados/stock/alertas |
| `.claude/skills/armar-combo/SKILL.md` | Skill read (R2): recomendación de combos |
| `clients/_template/*` | Scaffold del próximo cliente (CLAUDE.md, store-standards.md, connection.md, worklog.md, backups/) |
| `clients/blunua/*` | Cliente piloto, con store-standards.md relleno |
| `docs/runbooks/conectar-tienda.md` | Runbook interactivo para que Gabriel conecte una tienda |

**Formato de backup (contrato entre skill y hook):** `clients/{slug}/backups/{productIdTail}-{YYYYMMDD-HHMMSS}.json`:
```json
{ "productId": "gid://shopify/Product/123",
  "fields": { "descriptionHtml": "...", "seo_title": "...", "seo_description": "..." },
  "ts": "2026-07-19T12:00:00" }
```
El hook exige, antes de un write, un backup para ese `productId` cuyos `fields` cubran los campos del write y con mtime dentro de una ventana reciente. (Nota: el spec §6 menciona `.md`; se estandariza en `.json` a propósito para que el hook lo lea programáticamente. No "corregir" a `.md`. El spec ya quedó alineado a `.json`, dejando constancia de que el cambio fue deliberado.)

> ⚠️ **REALIDAD (así quedó implementado).** Las keys de `fields` son exactamente `descriptionHtml`, `seo_title`, `seo_description`, y van **siempre las tres juntas** (`REQUIRED_BACKUP_FIELDS` en `backup_guard.py`). No son los `body_html` / `meta_title` / `meta_description` que aparecen en los bloques de abajo. Dos refuerzos que se agregaron después:
> - El guard exige que los valores sean **strings y no estén los tres vacíos**. Un backup de placeholders satisfacía el guard viejo y después el undo restauraba vacío.
> - El campo `ts` es informativo: la frescura se mide por el **mtime del archivo**, no por `ts`.
>
> Los valores tienen que salir de **dos lecturas**: `get-product` para `descriptionHtml` y `graphql_query` (`product{ seo{ title description } }`) para el SEO, porque `get-product` no devuelve el bloque `seo`.

---

## Task 0: Scaffold del repo

**Files:**
- Create: `CLAUDE.md`, `README.md`, `.gitignore`, `.mcp.json`

- [ ] **Step 1: Crear `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.DS_Store
*.tmp
```

- [ ] **Step 2: Crear `CLAUDE.md`** (raíz)

```markdown
# shopify-control

Herramienta native-Claude para que clientes de ecommerce **no técnicos** de Worker
controlen y mejoren su tienda Shopify hablándole a Claude.

## Cómo se usa
- **Gabriel (operador/curador):** conecta la tienda, completa `clients/{slug}/store-standards.md`,
  corre el refresh trimestral. Arranca desde la raíz o desde `clients/{slug}/`.
- **Cliente (no técnico):** arranca Claude desde `clients/{slug}/` y habla en lenguaje natural
  ("mejorá la descripción del anillo X", "¿cómo venden los aros esta semana?").
  <!-- ⚠️ REALIDAD: esto quedó revertido. La sesión se abre SIEMPRE en la raíz del repo,
       desde VS Code con la extensión de Claude Code. Claude Code busca .claude/ en la
       carpeta que abrís: desde el subfolder no hay hooks ni skills, pero el connector
       igual escribe. Ver el CLAUDE.md final del repo y spec §5 decisión 1 / §10. -->


## Reglas duras (las respetan TODOS los skills)
1. **Sin jerga con el cliente:** nunca mostrar términos técnicos (nombres de campo, de skill,
   ni comandos). Entra en lenguaje natural, ve resultados en lenguaje natural.
2. **Humanizer obligatorio** antes de todo output cliente (reusa `handsOn/skills/humanizer`).
3. **Registro por cliente** según `store-standards.md` (blunua: español neutro, sin voseo).
4. **Todo write:** identificar → leer → generar → humanizer → checklist → preview → gate → backup → escribir → confirmar. Nunca escribir sin backup + confirmación explícita.
5. **Alcance de escritura v1:** solo descripción (`body_html`) + meta title + meta description.
   NUNCA precio, stock, status ni handle/URL.
   <!-- ⚠️ REALIDAD: el CLAUDE.md final dice, correctamente: solo descripción
        (`descriptionHtml`, vía Shopify:update-product) + SEO meta title/description
        (`seo.title`/`seo.description`, vía Shopify:graphql_mutation). Son dos writes. -->

## Estructura
- `.claude/skills/` — procedimientos (sirven a todos los clientes)
- `.claude/hooks/` — guardrails (backup_guard, description_lint)
- `clients/{slug}/` — contexto + estándares + backups + worklog por cliente
- `docs/` — spec, plan, runbooks

Spec: `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
```

- [ ] **Step 3: Crear `README.md`** (tono no técnico, español neutro)

```markdown
# Tu tienda, más fácil

Con esta herramienta podés pedirle a Claude que te ayude con tu tienda hablando normal.
Por ejemplo:

- "¿Cómo se vendieron los anillos esta semana?"
- "¿Qué productos están por quedarse sin stock?"
- "Mejorá la descripción del anillo NEXO plateado."

Claude siempre te muestra lo que va a hacer y te pide confirmación antes de cambiar nada
en tu tienda. Si algo no te gusta, se puede volver atrás.
```

- [ ] **Step 4: Crear `.mcp.json`** (placeholder documentado)

```json
{
  "//": "Placeholder. El connector de Shopify se conecta vía la app de Claude (OAuth) por tienda. Ver docs/runbooks/conectar-tienda.md. Cuando se conozca el nombre del server MCP, documentarlo acá.",
  "mcpServers": {}
}
```

- [ ] **Step 5: Commit**

```bash
git add CLAUDE.md README.md .gitignore .mcp.json
git commit -m "feat: scaffold base de shopify-control (CLAUDE, README, gitignore, mcp placeholder)"
```

---

## Task 1: Template de cliente (`clients/_template/`)

**Files:**
- Create: `clients/_template/CLAUDE.md`, `clients/_template/store-standards.md`, `clients/_template/connection.md`, `clients/_template/worklog.md`, `clients/_template/backups/.gitkeep`

- [ ] **Step 1: Crear `clients/_template/store-standards.md`** con la estructura de §8 del spec, todos los campos vacíos con `⚠️`. Marcar cada sección como `[ESTABLE]` o `[VIVO]` según §8.1. Usar exactamente las 10 secciones del spec (Marca, Registro y voz, Estructura de descripción, SEO, GEO, Naming/tags/categorías, Plantillas de imagen, Qué no tocar, Checklist, Señales del Brain).

- [ ] **Step 2: Crear `clients/_template/CLAUDE.md`**

```markdown
# Cliente: ⚠️ NOMBRE

**Tipo:** Ecommerce · **Moneda:** ⚠️ · **Plataforma:** Shopify

## Reglas de comunicación (heredadas de la raíz)
- Sin jerga técnica. Humanizer obligatorio. Registro: ⚠️ (definir en store-standards §2).

## Archivos
- `store-standards.md` — estándares de operación de producto (curados por Gabriel)
- `connection.md` — datos de conexión de la tienda
- `worklog.md` — log datado de cambios (append-only), incluye cada write + su backup
- `backups/` — snapshots de valores viejos (para revertir)

## Marca (contexto cualitativo)
→ Ver el folder del cliente en handsOn: `handsOn-Worker/clients/ecommerce/⚠️slug/`
  (brand-voice.md, icp.md, avatares). NO duplicar acá.
```

- [ ] **Step 3: Crear `clients/_template/connection.md`**

```markdown
# Conexión — ⚠️ NOMBRE

- **Store domain:** ⚠️ (ej: tienda.myshopify.com)
- **Connector:** Shopify oficial (Admin API)
- **Scopes v1:** read_products, read_orders/analytics, write_products
- **Estado:** ⚠️ no conectado / conectado (fecha)
- **Runbook de conexión:** ../../docs/runbooks/conectar-tienda.md
```

- [ ] **Step 4: Crear `clients/_template/worklog.md`**

```markdown
# Worklog — ⚠️ NOMBRE

Append-only. Cada write deja una entrada: `## YYYY-MM-DD [write] producto — backup: {archivo}`.

<!-- nuevas entradas arriba -->
```

- [ ] **Step 5: Crear `clients/_template/backups/.gitkeep`** (archivo vacío)

- [ ] **Step 6: Commit**

```bash
git add clients/_template
git commit -m "feat: template de cliente (standards, connection, worklog, backups)"
```

---

## Task 2: Cliente piloto blunua

**Files:**
- Create: `clients/blunua/CLAUDE.md`, `clients/blunua/store-standards.md`, `clients/blunua/connection.md`, `clients/blunua/worklog.md`, `clients/blunua/backups/.gitkeep`

- [ ] **Step 1: Copiar el template** a `clients/blunua/` y completar `CLAUDE.md` con los datos reales:
  - Nombre: Blunua. Moneda: COP. Brain ID: `LO4ob4dUxOggwTSlm07v`. Registro: español neutro, sin voseo.
  - Link marca: `handsOn-Worker/clients/ecommerce/blunua/`.

- [ ] **Step 2: Completar `clients/blunua/store-standards.md`** con los valores conocidos (de handsOn brand-voice.md + CLAUDE.md). Rellenar:
  - **§1 Marca [ESTABLE]:** joyería de acero quirúrgico hipoalergénico, +10 años, minimalista, aesthetic. Colecciones: general, NUA (previa), NEXO (nueva, "funciona sola o en conjunto").
  - **§2 Registro [ESTABLE]:** español neutro, sin voseo. Tono amigable, sobrio. Vocab SÍ: duradera, no irrita, segura, minimalista, hipoalergénico, resistente al agua, para regalar. Vocab NO: `⚠️` (evitar lujo-aspiracional y superlativos vacíos; no imitar a Pandora / Acero & Piedra / Joboly / Two Pieces / Maria Grazia Severin).
  - **§3 Estructura descripción [ESTABLE]:** el molde canónico (título → hook → 3 beneficios → material/garantía → 2-4 FAQ GEO). 80-150 palabras. Keywords tejidas. meta title + meta description como campos SEO separados.
  - **§4 SEO [VIVO]:** keywords núcleo: acero quirúrgico, hipoalergénico, resistente al agua, joyería minimalista. Por categoría: `⚠️`. Meta title ~60 char, meta description ~155 char.
  - **§5 GEO [VIVO]:** afirmaciones citables, bloque Q&A, datos concretos.
  - **§6 Naming/tags [ESTABLE]:** [Colección]+[tipo]+[material]+[color]; tags: colección (NEXO/NUA), material, género. Taxonomía: `⚠️`.
  - **§7 Imagen [ESTABLE]:** colores #4B4B4B / #9CB0B1 / #CEC4BA / #E9E6DD; estilo minimalista, fondo limpio; specs `⚠️`.
  - **§8 Qué no tocar:** field set = `descriptionHtml` + `seo.title` + `seo.description`; NUNCA precio/stock/status/handle. *(el plan original decía `body_html + meta title + meta description`; ver el bloque de Estado)*
  - **§9 Checklist "listo para publicar":** los 7 ítems del spec (incluye correr `description_lint`).
  - **§10 Señales del Brain [VIVO, placeholder]:** seo-gaps, creative-intelligence, customer-intelligence.

- [ ] **Step 3: Completar `connection.md`** de blunua (store domain `⚠️`, estado: no conectado).

- [ ] **Step 4: Seed `worklog.md`** con una entrada inicial `## 2026-07-19 [setup] estándares cargados desde handsOn`.

- [ ] **Step 5: Commit**

```bash
git add clients/blunua
git commit -m "feat: cliente piloto blunua con estándares cargados"
```

---

## Task 3: Hook de backup (`backup_guard.py`) — TDD

**Files:**
- Create: `.claude/hooks/backup_guard.py`, `tests/test_backup_guard.py`
- Create: `.claude/settings.json` (no existía; Task 0 no lo crea)

Núcleo testeable: `evaluate(payload, backups_root, now) -> (decision, reason)` donde `decision ∈ {"allow","block"}`. `main()` sólo hace IO (stdin → evaluate → exit code).

- [ ] **Step 1: Escribir los tests que fallan** (`tests/test_backup_guard.py`)

```python
import json, time, os
from pathlib import Path
from datetime import datetime
import importlib.util

spec = importlib.util.spec_from_file_location("backup_guard", Path(__file__).parent.parent/".claude/hooks/backup_guard.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

def write_backup(root, product_id, fields, age_seconds=0):
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({"productId": product_id, "fields": fields, "ts": "x"}))
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

WRITE = {"tool_name": "shopify_product_update",
         "tool_input": {"productId": "gid://shopify/Product/1", "fields": {"body_html": "new"}}}

def test_non_shopify_tool_is_allowed(tmp_path):
    d, _ = bg.evaluate({"tool_name": "Read", "tool_input": {}}, tmp_path, time.time())
    assert d == "allow"

def test_write_without_backup_is_blocked(tmp_path):
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "block"

def test_write_with_covering_recent_backup_is_allowed(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"})
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "allow"

def test_backup_missing_a_field_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"})
    payload = {"tool_name": "shopify_product_update",
               "tool_input": {"productId": "gid://shopify/Product/1",
                              "fields": {"body_html": "new", "meta_title": "new"}}}
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block"

def test_stale_backup_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"}, age_seconds=100000)
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "block"
```

- [ ] **Step 2: Correr los tests, verificar que fallan**

Run: `pytest tests/test_backup_guard.py -v`
Expected: FAIL (módulo/función inexistente).

- [ ] **Step 3: Implementar `.claude/hooks/backup_guard.py`**

```python
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
    pid, fields = _write_target(payload.get("tool_input") or {})
    if not pid or not fields:
        return "block", "no pude identificar producto/campos del write"
    if _covering_backup_exists(Path(backups_root), pid, fields, now):
        return "allow", "backup reciente encontrado"
    return "block", (f"Sin backup reciente para {pid} que cubra {sorted(fields)}. "
                     "El skill debe guardar el backup antes de escribir.")

def main():
    payload = json.load(sys.stdin)
    backups_root = payload.get("cwd") or "."
    decision, reason = evaluate(payload, backups_root, time.time())
    if decision == "block":
        print(reason, file=sys.stderr)
        sys.exit(2)   # exit 2 = bloquea el tool y muestra stderr al modelo
    sys.exit(0)

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Correr los tests, verificar que pasan**

Run: `pytest tests/test_backup_guard.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Registrar el hook en `.claude/settings.json`**

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          { "type": "command", "command": "python .claude/hooks/backup_guard.py" }
        ]
      }
    ]
  }
}
```
> Nota: verificar contra la doc de hooks de Claude Code el mecanismo de bloqueo (exit 2 vs JSON `permissionDecision: deny`) y el matcher para tools MCP. Ajustar `WRITE_TOOL_MARKERS`/`WRITE_ACTION_MARKERS` cuando se conozca el nombre real del tool (Task 7).

> ⚠️ **REALIDAD (verificado en runtime).** Tres cosas que este snippet no anticipaba:
> - **El mecanismo de bloqueo es `exit 2`.** Un `exit 1` NO bloquea: es un error no-bloqueante y el tool se ejecuta igual. Es el bug que tuvo el secret-scan del framework, que devolvía 1 y por eso nunca bloqueó un commit en ninguna plataforma (`docs/HANDOFF.md` #1b).
> - **El comando lleva `cd "$CLAUDE_PROJECT_DIR" &&`.** Sin eso, arrancar la sesión fuera de la raíz no encuentra el script.
> - **`settings.json` final tiene además `permissions.deny`** con 7 tools de escritura del connector (`set-inventory`, `bulk-update-product-status`, `create-discount`, `create-product`, `create-collection`, `update-collection`, `add-to-collection`), y registra los hooks del framework con matcher `Bash`. El matcher `.*` del guard propio captura bien el nombre MCP real (`mcp__claude_ai_Shopify__update-product`).
>
> Los hooks se arman al **iniciar** la sesión: tocar `settings.json` o `stack.json` exige reiniciar. Los *scripts*, en cambio, se releen en cada invocación, así que se pueden instrumentar sin reiniciar (así se diagnosticó el bug del exit code).

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/backup_guard.py tests/test_backup_guard.py .claude/settings.json
git commit -m "feat: hook backup_guard que bloquea writes de Shopify sin backup (TDD)"
```

---

## Task 4: Linter de descripciones (`description_lint.py`) — TDD

**Files:**
- Create: `.claude/hooks/description_lint.py`, `tests/test_description_lint.py`

Función pura `lint(text, required_keywords, min_words, max_words) -> list[str]` (lista de issues; vacía = OK). Chequeos mecánicos de bajo falso-positivo: em-dash presente, longitud fuera de rango, ninguna keyword requerida presente. El tono/voseo lo cubre `humanizer` (nivel prompt), no el linter.

> ⚠️ **REALIDAD (el linter creció).** Dejar el voseo y el vocabulario prohibido "a nivel prompt" no alcanzaba, y encima el linter **no tenía CLI**, así que el "corré el lint" del skill era autorreportado. El archivo final:
> - **Se ejecuta de verdad:** `python .claude/hooks/description_lint.py --keywords "..." --dialect neutro`, texto por stdin, exit 1 si hay issues. Se lintea el **texto plano**, no el HTML (el CLI despeja los tags).
> - **Bloquea además:** materiales falsos (`oro`, `plata`, `chapado`, `bañado en oro`: el material es acero quirúrgico, así que declararlos es un claim falso; "dorado"/"plateado" sí valen porque describen el acabado), lujo-vacío y superlativos, claims médicos, **voseo** cuando el dialecto es neutro, y presencia de bloque GEO.
> - **Decisión deliberada:** *no* se lintea "mágico", aunque figure en la lista curada, porque la tienda tiene colecciones llamadas "Brillo mágico". Un linter que se dispara con el nombre de una colección de la marca termina desactivado.

- [ ] **Step 1: Tests que fallan** (`tests/test_description_lint.py`)

```python
from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("description_lint", Path(__file__).parent.parent/".claude/hooks/description_lint.py")
dl = importlib.util.module_from_spec(spec); spec.loader.exec_module(dl)

KW = ["acero quirúrgico", "hipoalergénico"]

def test_clean_text_has_no_issues():
    txt = "Anillo minimalista en acero quirúrgico, hipoalergénico y resistente al agua. " * 3
    assert dl.lint(txt, KW, 10, 200) == []

def test_em_dash_is_flagged():
    txt = "Anillo en acero quirúrgico — hipoalergénico y duradero para uso diario todos los dias."
    assert any("em-dash" in i for i in dl.lint(txt, KW, 3, 200))

def test_too_short_is_flagged():
    assert any("corto" in i.lower() for i in dl.lint("acero quirúrgico hipoalergénico", KW, 50, 200))

def test_missing_keyword_is_flagged():
    txt = "Un anillo lindo y bonito para todos los dias, elegante y sencillo, ideal para regalar."
    assert any("keyword" in i.lower() for i in dl.lint(txt, KW, 3, 200))
```

- [ ] **Step 2: Correr, verificar fallo.** Run: `pytest tests/test_description_lint.py -v` → FAIL.

- [ ] **Step 3: Implementar `.claude/hooks/description_lint.py`**

```python
"""Linter mecánico para descripciones (spec §8.9). No reemplaza al humanizer;
lo complementa con chequeos de bajo falso-positivo."""

def lint(text: str, required_keywords, min_words: int, max_words: int):
    issues = []
    if "—" in text or "–" in text:
        issues.append("em-dash detectado (AI tell): reemplazar por coma/dos puntos")
    n = len(text.split())
    if n < min_words:
        issues.append(f"texto demasiado corto ({n} palabras, mínimo {min_words})")
    if n > max_words:
        issues.append(f"texto demasiado largo ({n} palabras, máximo {max_words})")
    low = text.lower()
    if required_keywords and not any(k.lower() in low for k in required_keywords):
        issues.append(f"falta al menos una keyword requerida: {required_keywords}")
    return issues
```

- [ ] **Step 4: Correr, verificar que pasan.** Run: `pytest tests/test_description_lint.py -v` → PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/hooks/description_lint.py tests/test_description_lint.py
git commit -m "feat: linter mecánico de descripciones (em-dash, longitud, keyword) (TDD)"
```

---

## Task 5: Skill `mejorar-descripcion` (W1)

**Files:**
- Create: `.claude/skills/mejorar-descripcion/SKILL.md`

Validación = checklist (no pytest; es un artefacto de instrucción). El executor escribe el SKILL.md siguiendo el spec §6.

- [ ] **Step 1: Escribir `SKILL.md`** con:
  - **Frontmatter:** `name: mejorar-descripcion`, `description:` que dispare con "mejorar/optimizar descripción de producto, SEO, GEO" y aclare que hace preview + backup + confirmación.
  - **Body con el flujo exacto de §6** (identificar → leer 3 campos → cargar store-standards + link handsOn → generar según molde canónico → **invocar `humanizer`** → correr `description_lint.py` + checklist §8.9 → preview §6.1 → gate sí/no → escribir backup JSON en `clients/{slug}/backups/` con el contrato de formato → escribir vía connector → **append al `worklog.md`** (producto + archivo de backup + fecha) → confirmar + instrucciones de undo).
  - **Reuso explícito:** referenciar `handsOn-Worker/skills/humanizer/SKILL.md`, `seo-geo`, `generic-language-killer`, plugins `seo-schema`/`seo-content`/`seo-ecommerce`.
  - **Field set:** solo `descriptionHtml` + `seo.title` + `seo.description`. Prohibido precio/stock/status/handle. **Son dos writes** (`update-product` para la descripción, `graphql_mutation`/`productUpdate` para el SEO) y **dos lecturas** (`get-product` no trae el SEO).
  - ⚠️ **REALIDAD, paso 0 obligatorio que el plan no tenía:** como la sesión se abre en la raíz, el contexto del cliente no se auto-carga. El skill arranca identificando el cliente, leyendo su `CLAUDE.md` + `store-standards.md`, y confirmando con `Shopify:get-shop-info` contra qué tienda apunta el connector, comparándola con `connection.md`. Si no coinciden, aborta. Aplica igual a `reporte-tienda` y `armar-combo`.
  - **Preview:** formato de §6.1, en chat, sin jerga, con el bloque "Cómo se va a ver en Google".
  - **Lote:** preview resumido + backup de cada uno + un solo gate.
  - **Undo (`revertir`):** trata la reversión como cualquier otro write, así pasa el hook aunque hayan pasado horas: (1) lee el valor **actual** de los 3 campos vía connector, (2) escribe un backup fresco de ese valor actual (esto además habilita el *redo*), (3) recién ahí reescribe los valores viejos del backup elegido, (4) append al worklog. NO depende de que exista un backup "reciente" previo.

- [ ] **Step 2: Validación (checklist manual)** — verificar que el SKILL.md:
  - [ ] Nunca escribe antes del gate ni sin backup.
  - [ ] Escribe el backup en el formato que espera `backup_guard.py` (mismos keys: productId, fields, ts).
  - [ ] Corre humanizer + `description_lint` antes del preview.
  - [ ] No incluye precio/stock/status/handle en el write.
  - [ ] El preview no tiene jerga técnica.
  - [ ] Append al `worklog.md` en cada write (producto + backup + fecha).
  - [ ] `revertir` backupea el valor actual ANTES de restaurar (no depende de un backup reciente previo).

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/mejorar-descripcion
git commit -m "feat: skill mejorar-descripcion (write SEO/GEO con flujo seguro)"
```

---

## Task 6: Skills read `reporte-tienda` y `armar-combo`

**Files:**
- Create: `.claude/skills/reporte-tienda/SKILL.md`, `.claude/skills/armar-combo/SKILL.md`

- [ ] **Step 1: `reporte-tienda/SKILL.md`** — read-only. Responde resultados/stock/alertas vía connector directo. Reusa `ecommerce-marketing-manager`, `alerts-system`, `shopify-api`. Output en texto simple sin jerga. **No escribe** (el hook igual lo protege). Detecta candidatos a mejorar (productos sin descripción/imagen) y ofrece pasar a `mejorar-descripcion`.

- [ ] **Step 2: `armar-combo/SKILL.md`** — read-only. Propone combos como texto usando catálogo + lógica de colección (NEXO). Reusa `ecommerce-marketing-manager`, `marketing-psychology`. **No crea** el combo en Shopify. Deja placeholder para el input de co-compra del Brain.

- [ ] **Step 3: Validación (checklist)** — ninguno de los dos escribe en Shopify; ambos respetan la regla sin-jerga.

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/reporte-tienda .claude/skills/armar-combo
git commit -m "feat: skills read reporte-tienda y armar-combo"
```

---

## Task 7: Runbook de conexión + calibración del connector

**Files:**
- Create: `docs/runbooks/conectar-tienda.md`
- Modify: `.mcp.json`, `.claude/hooks/backup_guard.py` (ajustar markers)

- [ ] **Step 1: Escribir `docs/runbooks/conectar-tienda.md`** — pasos para Gabriel: conectar el connector oficial de Shopify (OAuth) para una tienda, scopes v1 (read_products, read_orders/analytics, write_products), y cómo verificar que quedó conectado.

- [ ] **Step 2: Con un Shopify development store conectado**, inspeccionar el/los tool name(s) reales de escritura de producto del connector y la forma del payload (product id + campos). Documentarlo en el runbook.

- [ ] **Step 3: Ajustar** `WRITE_TOOL_MARKERS` / `WRITE_ACTION_MARKERS` / `_write_target()` en `backup_guard.py` para que matcheen el tool real. Actualizar los tests si cambia la forma del payload. Correr `pytest tests/ -v` → PASS.
  - **(M1 del review final) Vocabulario de campos real:** el Admin API NO usa `meta_title`/`meta_description` planos — usa `descriptionHtml`/`body_html` para la descripción y metafields `global.title_tag` / `global.description_tag` para el SEO. Al calibrar, mover en **lockstep los 3 lugares**: (a) las keys que escribe el backup en `mejorar-descripcion/SKILL.md` paso 9, (b) `_write_target()` + el subset check del hook, (c) la prosa de `store-standards §8`. Los 12 tests que hoy pasan pueden dar falsa confianza mientras el payload sea el mock.

    > ⚠️ **REALIDAD: la parte de metafields de M1 es FALSA. No la sigas.** El SEO **no** se maneja con `global.title_tag` / `global.description_tag`. Es el campo nativo `seo` del producto:
    > - **Leer:** `Shopify:graphql_query` → `query($id: ID!){ product(id:$id){ seo { title description } } }`.
    > - **Escribir:** `Shopify:graphql_mutation` → `productUpdate(product:{ id, seo:{ title, description } })`. Se usa `product:`, no `input:` (deprecado). Se valida antes con `Shopify:validate_graphql_codeblocks`.
    >
    > Y el punto que costó caro: **`get-product` NO devuelve el bloque `seo`.** Backupear solo lo que devuelve `get-product` deja el SEO vacío en el backup, y entonces el "vuelve a la anterior" **borra** el título y el resumen SEO reales del cliente en vez de restaurarlos. Fue un bug real, no hipotético. De ahí salió el chequeo de valores no vacíos del guard.
    >
    > Lo que sí acertó M1: mover los 3 lugares en lockstep. Se hizo, con las keys `descriptionHtml` / `seo_title` / `seo_description`.

- [ ] **Step 3b (I2 del review final): scopear el backup al cliente actual.** El glob del hook es repo-wide y los gid de Shopify son por-tienda (dos tiendas distintas pueden tener `Product/123`). Antes de onboardear un 2º cliente, limitar la búsqueda de backups a la carpeta del cliente activo (o incluir el store domain en el match). No se dispara con un solo cliente, pero cerrarlo antes de escalar.
  - **Estado: ABIERTO.** Sigue sin cerrarse; se está cerrando en la tanda actual. No bloquea mientras blunua sea el único cliente.

- [ ] **Step 3c (⚠️ REALIDAD, no estaba en el plan): endurecer el alcance por código.** La calibración destapó que el alcance vivía solo en la prosa de los skills, y que un backup válido funcionaba como llave de 15 minutos para escribir cualquier campo. Lo que se agregó:
  - `permissions.deny` en `settings.json` sobre 7 tools de escritura del connector.
  - **Alcance de campos** en `backup_guard`: `update-product` solo `{id, descriptionHtml}`; mutación de producto solo `{id, descriptionHtml, seo}`; cualquier otra key de primer nivel bloquea.
  - **Lectura de `tool_input.variables`**, no solo del string del query: un `productUpdate` parametrizado (la forma idiomática de GraphQL) esquivaba el guard viejo entero.
  - Lista de **mutaciones GraphQL prohibidas** (`productDelete`, `productVariantsBulkUpdate`, `productChangeStatus`, `inventorySetQuantities`, `collectionUpdate`, `publishablePublish`, etc.), que es el camino que `permissions.deny` no puede enumerar.
  - **Fallo cerrado:** ante una excepción inesperada sobre un tool de Shopify, el guard bloquea.

- [ ] **Step 3d (⚠️ REALIDAD, no estaba en el plan): adoptar el claude-code-framework de Worker.** `stack.json` + `core/`: secret-scan bloqueante en `git commit`, pre-push que corre `python -m pytest -q`, `push: operator-only`, close-protocol. Convive con el guard propio (los del framework matchean `Bash`, el nuestro `.*`). Se encontraron y arreglaron dos bugs del secret-scan: el **exit code** (devolvía 1, que no bloquea) y **CRLF** en Windows (dejaba pasar todo secreto). Ver `docs/HANDOFF.md` #1b.

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks/conectar-tienda.md .mcp.json .claude/hooks/backup_guard.py tests/
git commit -m "feat: runbook de conexión + calibración del hook al connector real"
```

---

## Task 8: Validación end-to-end en dev store (gated)

**Precondición:** un Shopify development store conectado con al menos 1 producto de prueba. (No requiere la tienda de blunua.)

**Files:**
- Modify: `clients/blunua/worklog.md` (registrar resultados)

**Corrida real:** dev store *Testing StandAlone Framework* (USD), producto *The Complete Snowboard* (`gid://shopify/Product/10429846257981`). Detalle en `clients/blunua/worklog.md` y `docs/HANDOFF.md`.

- [x] **Step 1 (discovery): VERIFICADO, con resultado negativo → decisión tomada.** Desde `clients/blunua/` Claude Code **no** descubre ni el hook ni los skills: busca `.claude/` en la carpeta que abrís. Peor: el connector de Shopify **sí** sigue disponible, o sea manos sin guardrails. Se eligió la opción (a): **el v1 se opera siempre desde la RAÍZ del repo**, en VS Code con la extensión de Claude Code. No se duplicó `.claude/` en cada cliente. Corolario: los tres skills arrancan con un paso 0 que confirma cliente activo y tienda conectada.
- [x] **Step 2: VERIFICADO.** `mejorar-descripcion` end-to-end: leer los 3 campos (dos lecturas), preview sin jerga, gate explícito, backup JSON antes del write, y los **dos** writes (`update-product` → `descriptionHtml`, `graphql_mutation` → `productUpdate{seo}`). Confirmado por read-back del Admin API.
- [x] **Step 3: VERIFICADO, el hook bloquea un write sin backup.** En sesión fresca de VS Code se pidió un `update-product` sin backup previo y cortó con *"Sin backup reciente…"*. El matcher `.*` captura el nombre MCP real (`mcp__claude_ai_Shopify__update-product`) y el guard lo reduce bien a `update-product`.
  - **Contrato de bloqueo: `exit 2`.** Claude Code bloquea **solo** con exit 2; un `exit 1` es error no-bloqueante y el tool se ejecuta igual. No es teoría: el secret-scan del framework devolvía 1 y por eso nunca bloqueó un commit, en ninguna plataforma (`docs/HANDOFF.md` #1b).
  - **Nota histórica:** una corrida automatizada anterior había concluido que el hook no se disparaba. Era falso: el write lo había rechazado Shopify por id inexistente, antes de que se notara el hook. La verificación válida es la de sesión interactiva.
- [x] **Step 4: VERIFICADO.** Undo y redo probados, ciclo reversible sobre los 3 campos. *(El plan decía `body_html + meta title + meta description`; son `descriptionHtml` + `seo.title` + `seo.description`.)* De acá salió el hallazgo del SEO: como `get-product` no devuelve `seo`, un backup armado solo con `get-product` hacía que el undo **borrara** el SEO del cliente. Corregido en el skill (lectura con `graphql_query`) y en el guard (rechaza backups con los tres valores vacíos).
- [x] **Step 5: VERIFICADO (y ampliado).** `description_lint` frena em-dash y falta de keyword. Además ahora es **ejecutable por CLI** y bloquea materiales falsos, lujo-vacío, claims médicos y voseo. Antes no tenía CLI, así que el "corré el lint" era autorreportado.
- [x] **Step 6: VERIFICADO.** `reporte-tienda` (`run-analytics-query`, `list-orders`, stock, candidatos a mejorar) y `armar-combo` (`search_collections`, `get-collection`) contra el connector real, sin escribir nada.
- [x] **Step 7: HECHO.** Resultados registrados en `clients/blunua/worklog.md` y commiteados.
- [x] **Step 8: HECHO, y la lista de límites creció.** Documentados como conocidos y aceptados:
  - **(I3) Frescura del backup: es un proxy.** El guard exige "existe algún backup cubriente con mtime < 15 min", no "se respaldó exactamente el valor que se está por sobrescribir". Riesgo bajo por ser single-operator y secuencial. **ABIERTO, se está cerrando en la tanda actual.**
  - **(I2) Scoping multi-cliente:** el glob de backups es repo-wide y los gid son por tienda. **ABIERTO, se está cerrando en la tanda actual.** No se dispara con un solo cliente.
  - **(M3) `description_lint` es advisory** respecto del write: corre en el checklist del skill, no como `PreToolUse` que corte la mutación. Protege la marca, no la tienda. Se mitigó volviéndolo ejecutable y ampliando su cobertura.
  - **Bypass por shell:** las capas de seguridad cubren los tools del connector; nada impide que alguien con acceso al repo llame al Admin API desde una terminal. El modelo de amenaza del v1 es "el operador o el cliente se equivocan", no "un actor hostil con shell". **ABIERTO, se está cerrando en la tanda actual.**

**No verificado todavía:**
- [ ] El flujo de **lote** (gate único, backups completos por producto, y revalidación de la ventana de 15 min a mitad de lote: en un lote largo los primeros backups vencen y los últimos writes se bloquean).
- [ ] Todo lo anterior contra la tienda **real de blunua** (`blunua-jewelry.myshopify.com`, COP, 678 productos). Está conectada y verificada, pero **no se le escribió nada**.

```bash
git add clients/blunua/worklog.md
git commit -m "test: validación end-to-end del v1 en dev store"
```

---

## Fuera de este plan (v1)
- Empaquetado para hand-off al cliente (D2): bundlear skills reusados, distribuir.
- Input del Brain en el refresh trimestral (W1.5), imágenes (W2), subir productos (W3), combos como write.
- Skills `onboardear-cliente` y `refrescar-estandares` (en v1 son tareas manuales de Gabriel).

## Definition of Done (v1)
- [x] `pytest tests/ -q` en verde: **65 tests** (backup_guard con alcance de campos y frescura, description_lint con palabras prohibidas y voseo, secret-scan con su regresión de CRLF, y el guard de shell; los dos últimos no estaban en el plan).
- [x] Los 3 skills existen y pasan sus checklists.
- [x] El hook bloquea un write sin backup y el undo restaura los 3 campos (verificado en dev store, Task 8).
- [x] blunua tiene su `store-standards.md` con los ESTABLES cargados y los `⚠️` (onboarding/vivo) claramente marcados. *(Los `⚠️` de vocabulario prohibido, keywords por categoría y taxonomía siguen abiertos: son inputs de onboarding, no gaps de build. Ver `docs/HANDOFF.md` PENDIENTE #2.)*
- [x] **Agregado sobre el plan original:** el alcance está enforced por código y no por prosa (`permissions.deny` + alcance de campos en el guard), y el repo adoptó el claude-code-framework (secret-scan, pre-push, close-protocol).
