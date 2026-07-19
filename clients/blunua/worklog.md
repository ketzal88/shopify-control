# Worklog — Blunua

Append-only. Cada write deja una entrada: `## YYYY-MM-DD [write] producto — backup: {archivo}`.

<!-- nuevas entradas arriba -->

## 2026-07-19 [undo + redo] Collar Amaral — backups: ...-202103.json y ...-202226.json

Prueba del ciclo completo de reversión sobre datos reales, para validar la red de seguridad
antes de presentarle la herramienta al cliente. El producto quedó con la versión mejorada.

- **Undo:** se restauraron los 3 campos al valor previo. Verificado por hash SHA-256: los tres
  quedaron **idénticos carácter por carácter** al backup de las 20:08, no "parecidos".
- **Redo:** se volvió a aplicar la mejora, así que el producto terminó con la versión buena.
- **Qué NO cambió en ningún momento del ciclo:** precio ($129.000), stock (140), estado
  (ACTIVE) y handle. Verificado leyendo la tienda, no asumido.
- **Backups generados:** `...-202103.json` (valor nuevo, es el que habilita el redo) y
  `...-202226.json` (valor viejo, antes de re-aplicar). Cada write respaldó lo que iba a pisar,
  que es lo que hace que cada paso del ciclo sea a su vez reversible.

## 2026-07-19 [write] Collar Amaral — backup: 9999944450369-20260719-200814.json

**Primer write real sobre la tienda de blunua.** Deja sin efecto el "todavía no se le escribió
nada" de la entrada de abajo. Producto elegido a propósito por bajo riesgo: cero ventas en 30
días, aunque activo y con 140 unidades en stock.

- **Qué cambió:** descripción (`descriptionHtml`) y SEO (`seo.title`, `seo.description`).
- **Qué NO cambió:** precio ($129.000), stock (140), estado (ACTIVE), tags y handle. Verificado
  en la respuesta de los dos writes, no asumido.
- **Mejoras aplicadas:** se agregó bloque de preguntas frecuentes (no tenía ninguna), se acortó
  el título de Google de 72 a 57 caracteres (se estaba cortando en el buscador), se quitó
  "sin esfuerzo" que aparecía repetido dos veces, y se limpió el HTML pegado de un editor
  (`data-start`/`data-end`, `<strong>` vacíos).
- **Checklist:** `description_lint` pasó sin issues ANTES del preview.
- **Qué validó del v1:** este write ejercitó las dos lecturas separadas (descripción con
  `get-product`, SEO con `graphql_query`), que es el arreglo del bug por el que el backup
  quedaba con el SEO vacío y el undo lo borraba. El backup guardó los 3 campos con contenido
  real (678 / 72 / 165 caracteres). El write del SEO se mandó por `variables`, que era
  justamente el camino que antes esquivaba el guard.

## 2026-07-19 [corrección] El hook SÍ bloquea + aclaración sobre las entradas viejas
Dos cosas, para que nadie lea mal este log:

1. **Queda sin efecto el hallazgo "el `PreToolUse` hook NO se disparó"** de la entrada del
   2026-07-19 más abajo. Se verificó en una sesión fresca de VS Code (raíz del repo) que
   `backup_guard` **está armado y bloquea**: un `update-product` sin backup previo se corta
   con *"Sin backup reciente…"*. El bug era el **código de salida** (Claude Code solo bloquea
   con `exit 2`; un `exit 1` no bloquea), no el matcher. Detalle completo en `docs/HANDOFF.md`
   (PENDIENTE #1 y #1b).
2. **Las entradas anteriores de este worklog NO son cambios en la tienda de blunua.** Todos
   esos writes se hicieron contra la dev store **Testing StandAlone Framework** (USD),
   usada para validar el v1. La tienda real de blunua (`blunua-jewelry.myshopify.com`, COP,
   678 productos) quedó conectada y verificada hoy, pero **todavía no se le escribió nada**.

Recordatorio operativo: la sesión se abre siempre en la **raíz** del repo (abrir
`clients/blunua/` deja la sesión sin hooks ni skills), y antes de operar hay que confirmar
cliente activo y tienda conectada.

## 2026-07-19 [test] [e2e] Validación de reporte-tienda y armar-combo (lectura)
Tienda: Testing StandAlone Framework.
- `reporte-tienda`: `run-analytics-query` OK (0 ventas, tienda nueva); `list-orders` OK (0). Stock: 3 productos sin stock, 1 con stock bajo. Candidatos a mejorar: ~14 productos con descripción vacía + colecciones sin descripción.
- `armar-combo`: `search_collections` + `get-collection` OK (3 colecciones). Combos propuestos desde catálogo + colección Hydrogen.
- Los 3 skills del v1 quedaron validados contra el connector real. Único pendiente: confirmar que el hook se dispara en sesión fresca de VS Code.

## 2026-07-19 [test] [e2e] Validación end-to-end en tienda de prueba
Tienda: **Testing StandAlone Framework** (dev store, USD). Producto: *The Complete Snowboard* (`gid://shopify/Product/10429846257981`).
- Leer catálogo/producto (`search_products`/`get-product`) y SEO (`graphql_query`): OK.
- Mejorar descripción (`update-product` → `descriptionHtml`) + SEO (`graphql_mutation` → `productUpdate{seo}`): OK, verificado por read-back del Admin API.
- Undo (restaurar original) y redo (re-aplicar mejora): OK. Ciclo reversible probado.
- ⚠️ Hallazgo: el `PreToolUse` hook NO se disparó en la sesión automatizada (un write sin backup lo rechazó Shopify por id inexistente, no el hook). **Verificar que sí se dispare en la sesión interactiva de VS Code.**
- Fix aplicado: usar `productUpdate(product:{...})` (el `input:` está deprecado).
- Playwright: storefront con password (dev store), verificación visual pública no posible; la fuente de verdad fue el Admin API.

## 2026-07-19 [setup] estándares cargados desde handsOn
