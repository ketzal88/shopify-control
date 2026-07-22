# HANDOFF — shopify-control (2026-07-19)

Punto de continuación para retomar en una sesión nueva de Claude Code (VS Code, abriendo la RAÍZ del repo). Este doc + el spec + el plan + el research te dan todo el contexto.

## Qué es
Herramienta native-Claude para que el operador (Worker) y clientes no técnicos controlen/mejoren su tienda Shopify hablándole a Claude Code. Connector oficial de Shopify. Piloto: **blunua**.

## Estado (todo en `main`, limpio)
- **v1 construido y validado end-to-end** contra el connector real (tienda de prueba *Testing StandAlone Framework*):
  - `mejorar-descripcion` (write seguro: `update-product` para descripción + `graphql_mutation` para SEO; backup → preview → confirmar → undo). Probado con *The Complete Snowboard* (quedó mejorado).
  - `reporte-tienda` (read: ventas/stock/alertas/candidatos a mejorar).
  - `armar-combo` (read: propone combos).
  - Guardrails: `backup_guard.py` (no write sin backup) + `description_lint.py` + `secret-scan` (regresión CRLF). 18 tests, verdes.
- **Framework de Worker adoptado** (`stack.json` + `core/`): secret-scan en commit, pre-push corre pytest, `push: operator-only`, close-protocol. Fix del edge-case del secret-scan hecho upstream (branch `fix/secret-scan-core-exemption` en claude-code-framework, **sin pushear** — te queda a vos).
- **Research de tooling** curado y versionado en `docs/research/2026-07-19-operator-tooling.md` (Shopify ops, imágenes, SEO/GEO, multi-cliente, **routines**, **merchandising/heatmap**).

## ✅ PENDIENTE #1 — RESUELTO (sesión fresca 2026-07-19)
Una sesión fresca **sí arma** los hooks. Verificado por comportamiento (no por `/hooks`, que no está disponible en este entorno):
- **`backup_guard` (el guard crítico de seguridad del cliente): ARMADO y BLOQUEA.** Se pidió un `update-product` sin backup (id falso, sin usar el skill) y cortó con *"Sin backup reciente…"*. El matcher `.*` captura el nombre MCP real (`mcp__claude_ai_Shopify__update-product`) y `_action()` lo reduce bien a `update-product`. Esto es la seguridad-por-diseño del producto: confirmada en runtime.

### ✅ #1b — RESUELTO (2026-07-19): el secret-scan tenía DOS bugs encadenados
Verificado end-to-end tras reiniciar: un `git commit` con una AWS key de ejemplo staged **ahora se bloquea**.

**Bug A — el exit code (el que realmente impedía bloquear, en TODAS las plataformas).**
Claude Code bloquea un tool **solo con `exit 2`**; un `exit 1` es error NO-bloqueante y el tool se ejecuta igual (así lo documenta `backup_guard.py`: `sys.exit(2) # exit 2 = bloquea el tool`). `secret-scan.sh` devuelve **1** al detectar un secreto, y el wrapper hacía `sys.exit(subprocess.call(...))` → propagaba el 1 → **el secret-scan nunca bloqueó un commit, en ningún sistema operativo.** Fix: `core/hooks/scripts/secret-scan-guard.py` mapea cualquier salida ≠0 del scanner a `exit 2`. → **PENDIENTE: subir esto al claude-code-framework** (su `core/hooks/settings.template.json` tiene el mismo `sys.exit(subprocess.call(...))` inline).

**Bug B — CRLF (específico de Windows), ya subido al framework (`d6e9f98`).** Ver detalle abajo.

**Cómo se diagnosticó** (útil si vuelve a pasar): los scripts de hook se releen en CADA invocación —solo la *config* se congela al iniciar—, así que se puede instrumentar un guard con logging y ver el payload real sin reiniciar. Eso mostró `is_commit: true`, `script_exists: true`, `scanner rc=1` y aun así el commit pasando → el problema era el código de salida, no el matcher ni el formato del comando.

<details><summary>Detalle histórico de los dos hallazgos</summary>

Al probar el hook de secret-scan (matcher `Bash`) salieron DOS cosas:
1. **Bug real, ARREGLADO.** Con `core.autocrlf=true` y sin `.gitattributes`, git hace checkout de `core/security/secret-patterns.txt` en CRLF; el loop `while read` dejaba un `\r` colgando en cada patrón → `grep -E "PATRON\r"` no matcheaba → **el scanner dejaba pasar TODO secreto en Windows.** Fix: strip de `\r` en `secret-scan.sh` + `.gitattributes` (`eol=lf`) + normalización a LF + test de regresión `tests/test_secret_scan.py` (incluye el caso CRLF). **18 tests verdes.** → **PENDIENTE: llevarlo canónicamente al claude-code-framework y re-sync `core/`** (igual que el fix anterior de la exención de `core/`).
2. **Runtime: el hook no cortó.** Aun con el script arreglado (que a mano devuelve `exit 1` sobre la key falsa), un `git commit` con el secreto NO fue bloqueado → el hook de secret-scan no se ejecuta en este runtime. **PISTA FUERTE (misma sesión):** el Stop hook `close-guard` —mismo formato `cd "$CLAUDE_PROJECT_DIR" && python core/hooks/scripts/X.py`— **SÍ disparó**, así que el formato y el armado del framework funcionan en Windows. El sospechoso queda acotado al **wrapper inline `python -c "..."` del secret-scan** (el único hook que no es un script-file; comillas anidadas frágiles en Windows). **Fix probable:** mover ese wrapper a `core/hooks/scripts/secret-scan-guard.py` (hace el `startswith('git commit')` + llama a `secret-scan.sh`) e invocarlo con `cd "$CLAUDE_PROJECT_DIR" && python core/hooks/scripts/secret-scan-guard.py`, como los demás. Confirmar con `/hooks` + `claude --debug`. `backup_guard` (`.*`) sí dispara. Los 4 `.sh` del framework estaban en CRLF; `.gitattributes` los normaliza hacia adelante.

> **Corrección:** la hipótesis del punto 2 (“el grupo matcher `Bash` no se ejecuta” / “es el formato del comando del hook”) resultó **falsa**. La instrumentación probó que el grupo `Bash` SÍ dispara y el guard SÍ se invoca; lo que fallaba era el exit code (Bug A). El cambio de wrapper inline → script-file quedó igual porque es más legible y testeable, pero no era la causa.

</details>

## 🔴 LEER: 7 agujeros de seguridad encontrados en `backup_guard.py` (2026-07-20)

Durante el milestone de escalones se encontraron **siete agujeros que ya estaban en `main`**.
Ninguno lo introdujo ese trabajo. Todos cerrados; 65 -> 146 tests.

El peor: **el backup de descripción era una llave maestra de 15 minutos.** Después de cada
`mejorar-descripcion`, 21 de las 26 mutaciones `product*` quedaban habilitadas —duplicar el
producto, reordenar variantes, cambiar opciones— porque el control de alcance de campos pasaba
*en el vacío* para las mutaciones sin objeto `input: {...}`.

Seis de los siete son la misma clase: **un parseo vacío tratado como "limpio" en vez de como
"no pude leer esto"**. El guard pasó de blocklists a whitelists cerradas por familia.

Detalle completo, con severidad y commit por hallazgo:
`docs/2026-07-20-hallazgos-de-seguridad-backup-guard.md`

## 🟡 A REVISAR CON GABRIEL — Catálogo de widgets (2026-07-22, DRAFT autónomo)
Sesión nocturna: Gabriel pidió sumar los catálogos de **wigy** (45 widgets) y **crecenube** (8 apps +
6 calculadoras) al plan de widgets. Escrito sin brainstorm (dormía) → es DRAFT, **no aprobado**.
- **Doc:** `docs/superpowers/specs/2026-07-22-catalogo-widgets-design.md`.
- **Qué dice:** generaliza el escalones a una "receta" de 6 piezas; deduplica (crecenube ⊂ wigy en
  vitrina; su aporte único son las calculadoras de operador); clasifica los 45 por guardrail
  (~26 adopta, ~7 adopta-con-matiz de plata, ~10 fuera por necesitar backend/PII/ML); consolida en
  **7 familias** en vez de 45 one-offs; propone un guardrail nuevo de **honestidad** (no fabricar
  urgencia/prueba social falsa); y prioriza para blunua (W1 quick wins de confianza → W4 ofertas BxGy).
- **Decisión clave que reencuadra el builder de escalones:** el `_check_style` bespoke del plan del
  builder debería nacer como la 1ª entrada de un **registro** `COSMETIC_METAFIELDS` en el guard (§7,
  D1). Por eso **no toqué `backup_guard.py`** esta noche.
- **Necesita tu call:** las 6 incógnitas de §12 (forma del guard, corte descripción/bloque, owner SHOP,
  honestidad como regla dura, y confirmar cuál fue "la app que me pasaste" — sospecho que wigy).

## PENDIENTE #2 — blunua real
Cargar los ⚠️ de `clients/blunua/store-standards.md` (vocabulario prohibido, keywords por categoría, taxonomía) + conectar el Shopify real de blunua (hoy conectada la dev store).

## Roadmap priorizado (del research)
1. **Shopify Dev MCP** (validación GraphQL, cero riesgo): `claude mcp add --transport stdio shopify-dev-mcp -- npx -y @shopify/dev-mcp@latest` (necesita Node/npx).
2. **Robar 40rty skill #1 (catalog SEO/metadata audit)** → enchufar a `reporte-tienda`.
3. **Robar #2 (Product JSON-LD + GTIN)** + `schema-dts` → enchufar a `mejorar-descripcion`.
4. **Routines** (Gabriel las quiere): briefing matutino, low-stock watchdog, fraude. Runtime = Claude Code cloud routines (`/schedule`), patrón loop-all-stores con `switch-shop`. Requiere el repo en GitHub.
5. **Skill `analizar-merchandising`** (idea de Gabriel): ShopifyQL + inventory → velocity/sell-through/ABC → heatmap (skill `dataviz`) → acciones reorder (`collectionReorderProducts` MANUAL) / restock / despriorizar.
6. Futuro: imágenes W2 (Photoroom → Nano Banana → Shopify upload-image), reporting multi-canal (GA4/GSC/Klaviyo MCP), subir productos W3.

## Docs de referencia
- Spec: `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
- Plan: `docs/superpowers/plans/2026-07-19-shopify-control-v1.md`
- Research: `docs/research/2026-07-19-operator-tooling.md`

## Notas de entorno
- Operar desde **VS Code + extensión de Claude Code**, abriendo la RAÍZ del repo (no el app pelado, no el subfolder), logueado con la cuenta claude.ai que tiene el connector de Shopify.
- Windows. Python 3.10 + pytest (`--user`). Node solo para el Dev MCP.
