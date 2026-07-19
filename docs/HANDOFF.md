# HANDOFF — shopify-control (2026-07-19)

Punto de continuación para retomar en una sesión nueva de Claude Code (VS Code, abriendo la RAÍZ del repo). Este doc + el spec + el plan + el research te dan todo el contexto.

## Qué es
Herramienta native-Claude para que el operador (Worker) y clientes no técnicos controlen/mejoren su tienda Shopify hablándole a Claude Code. Connector oficial de Shopify. Piloto: **blunua**.

## Estado (todo en `main`, limpio)
- **v1 construido y validado end-to-end** contra el connector real (tienda de prueba *Testing StandAlone Framework*):
  - `mejorar-descripcion` (write seguro: `update-product` para descripción + `graphql_mutation` para SEO; backup → preview → confirmar → undo). Probado con *The Complete Snowboard* (quedó mejorado).
  - `reporte-tienda` (read: ventas/stock/alertas/candidatos a mejorar).
  - `armar-combo` (read: propone combos).
  - Guardrails: `backup_guard.py` (no write sin backup) + `description_lint.py`. 15 tests, verdes.
- **Framework de Worker adoptado** (`stack.json` + `core/`): secret-scan en commit, pre-push corre pytest, `push: operator-only`, close-protocol. Fix del edge-case del secret-scan hecho upstream (branch `fix/secret-scan-core-exemption` en claude-code-framework, **sin pushear** — te queda a vos).
- **Research de tooling** curado y versionado en `docs/research/2026-07-19-operator-tooling.md` (Shopify ops, imágenes, SEO/GEO, multi-cliente, **routines**, **merchandising/heatmap**).

## ⚠️ PENDIENTE #1 — probar los hooks (este chat nuevo es la prueba)
Los hooks (`backup_guard` + los del framework) NO se armaron en la sesión anterior porque se crearon a mitad de sesión (Claude Code congela hooks al iniciar). **Una sesión fresca los arma.** Al abrir el repo:
1. `/hooks` → deberían aparecer `backup_guard.py` (PreToolUse) + los del framework (canonical/pre-push/secret-scan) + Stop (ratchet/close).
2. Probar el bloqueo: pedir *"sin usar el skill, cambiá la descripción de un producto sin backup"* → **tiene que bloquear** con "sin backup reciente". La lógica ya está testeada (15 tests); esto confirma que el runtime lo arma.
3. Si NO bloquea → es tema de matcher/formato del hook sobre tools MCP; debuggear ahí.

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
