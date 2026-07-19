# Research — herramientas para potenciar al operador (shopify-control)

- **Fecha:** 2026-07-19
- **Objetivo:** repos / MCP / skills que hagan más simple y potente el trabajo del operador (agencia Worker) sobre Shopify.
- **Método:** 4 investigadores en paralelo (web search + fetch verificado) + 3 links aportados por Gabriel.

> Nota transversal: ya tenemos gates (`backup_guard`, secret-scan, pre-push con tests). Todo lo que ESCRIBE se adopta **detrás de esos gates + backup**. Cada MCP con write es blast radius: preferir el connector oficial + validación, no sumar MCPs redundantes.

---

## Tier 1 — Adoptar ya (ganancia inmediata, bajo riesgo)

| Recurso | URL | Qué le da al operador | Fit |
|---|---|---|---|
| **40rty Shopify Admin Skills** | github.com/40RTY-ai/shopify-admin-skills | 116 skills + 20 rutinas cron, 11 categorías. Patrón `dry_run → confirmar`. MIT, 167⭐, v1.1.0 | ADOPT (cherry-pick + adaptar) |
| **kgelster/awesome-ecom-skills** | github.com/kgelster/awesome-ecom-skills | 9 skills MIT con doctrina preview/backup-first/readback | ADOPT (templates) |
| **Shopify Dev MCP** (oficial) | shopify.dev/docs/apps/build/devmcp | Valida GraphQL contra el schema **antes** de escribir. Solo docs/schema, cero data-risk | ADOPT (validación) |
| **DataForSEO MCP** (+ AI Optimization / LLM Mentions) | github.com/dataforseo/mcp-server-typescript | Keywords reales por categoría + **medir citación en ChatGPT/Perplexity** antes/después de un rewrite | ADOPT (wire a mejorar-descripcion) |
| **google/schema-dts** | github.com/google/schema-dts | JSON-LD de `Product`/`Offer` type-safe (rich results + facts citables para IA) | ADOPT (structured data) |

## Tier 2 — Próximo (habilita features futuras)

**Imágenes (W2) — pipeline validado:**
`Photoroom` (recorte + normalizar a canvas de marca) → `Nano Banana / Gemini MCP` (fondo on-brand + variantes) → **Shopify `upload-image`** → `update-product`. El asset final queda en el CDN de Shopify (sin hosting externo). `Higgsfield` (ya usado en advertising-ops/carousel) como opción hosted con "Soul" (consistencia de marca entrenada). `rembg-mcp` como recorte gratis local. `ComfyUI MCP` como v2 (GPU, costo por imagen ~0, control total).

**Reporting multi-canal (extiende reporte-tienda):**
MCPs oficiales `GA4` (googleanalytics/google-analytics-mcp) + `Klaviyo` (mcp.klaviyo.com) + community `GSC` (github.com/AminForou/mcp-gsc), orquestados con **subagentes nativos** (un subagente por cliente = aislamiento de contexto). "Reporte de los 5 clientes" en un comando.

## Tier 3 — Referencia / minar (patrones, no dependencias)

- **awesome-claude-code** (github.com/hesreallyhim/awesome-claude-code, 50k⭐) — fuente #1 de descubrimiento.
- **anthropics/claude-plugins-official** — canal de instalación *confiable* (importante si un plugin puede mutar tiendas).
- **queso/shopify-backup** (export read-only pre-mutación = rollback real) + **Shopify/bulk-operations-sample-app** (Bulk API async para editar miles sin rate-limits).
- **GEO-optim/GEO** (Princeton KDD 2024) — autoridad de qué tácticas GEO funcionan (ya usada vía seo-geo).
- **Shopify/agent-skills → `shopify-custom-data`** — metafields/metaobjects con `validate.js` (schema check antes de escribir).

## Saltear / con cuidado
- MCPs de Shopify community redundantes (GeLi2001/shopify-mcp 228⭐, etc.): el connector oficial ya cubre y con menos blast radius.
- **Agent teams** (experimental; en Windows el split-pane no anda — usar subagentes).
- Aggregators (claudemarketplaces, aitmpl, clauderegistry): mucho volumen, poca señal. Para *encontrar*, no para *confiar*.

---

## Deep-eval 40rty: las 5 skills para robar primero

El 40rty (y kgelster) siguen `dry_run → confirmar`, que mapea limpio sobre nuestro `backup_guard` + preview. Elegidas por ahorro de clics × bajo riesgo × fit con lo que ya tenemos:

1. **Catalog SEO/metadata audit + product-data-completeness** → potencia el "candidatos a mejorar" de `reporte-tienda` (hoy detecta descripción vacía; esto suma metadata, alt-text, campos faltantes).
2. **Product JSON-LD & GTIN backfill** → suma structured data a `mejorar-descripcion` (SEO + GEO), con `schema-dts` para validar el shape.
3. **Image alt-text generation** → quick win, bajo riesgo, feed de SEO/accesibilidad; puente natural a W2 (imágenes).
4. **Dead stock identification** → extensión directa de `reporte-tienda` (valor real para el operador, solo lectura).
5. **Daily briefing / morning digest (rutina)** → el mayor lever "operador más simple": un resumen proactivo por cliente (ventas, stock, alertas, candidatos a mejorar) en vez de que el operador vaya a buscar.

Todas: adaptar a nuestro repo (registro sin jerga, humanizer, gates), no correr crudas sobre tienda viva.

## Orden de integración propuesto
1. **Shopify Dev MCP** (validación, cero riesgo). Caveat: usa `npx` → necesita Node. Comando: `claude mcp add --transport stdio shopify-dev-mcp -- npx -y @shopify/dev-mcp@latest`.
2. **Robar skill #1 (audit)** → conectar a `reporte-tienda`.
3. **Robar #2 (JSON-LD) + schema-dts** → conectar a `mejorar-descripcion`.
4. **DataForSEO AI Optimization** → medir GEO antes/después.
5. **#5 (daily briefing)** como rutina por cliente.
6. Tier 2 (imágenes + reporting multi-canal) cuando lleguemos a W2/W3.

## Routines (automatizaciones programadas) — Gabriel las quiere

**Runtime:** **Claude Code cloud routines** (`/schedule` → claude.ai/code/routines): prompt + repo(s) de GitHub (se clonan en cada run → así llegan los skills y el contexto por cliente) + connectors + trigger cron. Corre en infra de Anthropic (compu apagada). **Mínimo 1h.** El connector de Shopify y Slack están disponibles dentro de la routine, sin allowlist. Caveat: research preview + **tope diario de runs por cuenta**.

**Formato de autoría:** robar el de **40rty** (YAML frontmatter `routine_id`/`cron`/`skills_used`/`notify` + prompt self-contained). **n8n** solo para sub-hora o checks deterministas (rompe el "todo native").

**Escala 15 clientes (gotcha central):** NO crear 15 copias de cada routine (revienta el tope diario). Patrón: **una routine que loopea clientes con `switch-shop`** y postea a `#{cliente}-alerts`. O per-client accounts post-hand-off (D2).

**Top 3 a construir:**
1. **Briefing matutino** — envuelve `reporte-tienda` (read-only), mata el "loguearse a 15 admins cada mañana".
2. **Low-stock / restock watchdog** — thresholds por cliente en `store-standards.md`; protege revenue en hero SKUs (NEXO/NUA).
3. **Fraude / orden riesgosa** — el tag es write seguro; el hold va por gate. Construir con el patrón loop-all-stores desde el día 1.
Otras: refund-rate spike, weekly business review, abandoned-cart (watch read-only; recovery por gate), SEO drift continuo (reemplaza el refresh trimestral §8.1 por continuo).

## Merchandising intelligence + heatmap — idea de Gabriel

Dos sentidos de "heatmap":
- **Merchandising heatmap** (lo que pediste): grilla producto×métrica coloreada por performance (velocity, sell-through, margen) → acciones "featurear / reordenar / restock / despriorizar". Se arma con la data que **YA tenemos** (ShopifyQL + inventory).
- **Behavioral heatmap** (dónde clickean/scrollean): **Microsoft Clarity** — gratis, app nativa de Shopify. Su Export API da solo **agregados por URL** (scroll depth, rage/dead clicks), NO la imagen del heatmap. Señal complementaria útil (¿llegan a ver los productos abajo del fold?). Hotjar: SKIP (su API es solo surveys). PostHog: REFERENCE (tiene MCP oficial).

**Skill v1 propuesto `analizar-merchandising`:** `run-analytics-query` (ShopifyQL) + `get-inventory-levels` → por producto: **velocity, sell-through, clase ABC** (revenue + margen), **trend período-a-período** → render **heatmap con el skill `dataviz`** → acciones concretas:
- **Reordenar:** `collectionReorderProducts` (sort `MANUAL`) para inyectar tu ranking, o flip a `BEST_SELLING`.
- **Restock/disponibilidad:** reorder point simple = `velocity × lead-time + safety stock`.
- **Despriorizar/discontinuar:** items clase C con sell-through <40%.
Ojo: **necesita historial de ventas real** (dev store recién creada da vacío → el skill tiene que degradar con gracia: detectar "sin ventas aún" y caer a inventory + metadata).

## Fuentes
40RTY-ai/shopify-admin-skills · kgelster/awesome-ecom-skills · shopify.dev/devmcp · dataforseo/mcp-server-typescript · google/schema-dts · googleanalytics/google-analytics-mcp · AminForou/mcp-gsc · developers.klaviyo.com/mcp · hesreallyhim/awesome-claude-code · anthropics/claude-plugins-official · zhongweili/nanobanana-mcp-server · higgsfield.ai/mcp · photoroom.com/api · GEO-optim/GEO · guides.tenfoldmarketing.com/shopify-claude-code · skills.40rty.ai
