# Worklog — Blunua

Append-only. Cada write deja una entrada: `## YYYY-MM-DD [write] producto — backup: {archivo}`.

<!-- nuevas entradas arriba -->

## 2026-07-19 [test] [e2e] Validación end-to-end en tienda de prueba
Tienda: **Testing StandAlone Framework** (dev store, USD). Producto: *The Complete Snowboard* (`gid://shopify/Product/10429846257981`).
- Leer catálogo/producto (`search_products`/`get-product`) y SEO (`graphql_query`): OK.
- Mejorar descripción (`update-product` → `descriptionHtml`) + SEO (`graphql_mutation` → `productUpdate{seo}`): OK, verificado por read-back del Admin API.
- Undo (restaurar original) y redo (re-aplicar mejora): OK. Ciclo reversible probado.
- ⚠️ Hallazgo: el `PreToolUse` hook NO se disparó en la sesión automatizada (un write sin backup lo rechazó Shopify por id inexistente, no el hook). **Verificar que sí se dispare en la sesión interactiva de VS Code.**
- Fix aplicado: usar `productUpdate(product:{...})` (el `input:` está deprecado).
- Playwright: storefront con password (dev store), verificación visual pública no posible; la fuente de verdad fue el Admin API.

## 2026-07-19 [setup] estándares cargados desde handsOn
