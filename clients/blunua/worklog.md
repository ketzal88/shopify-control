# Worklog — Blunua

Append-only. Cada write deja una entrada: `## YYYY-MM-DD [write] producto — backup: {archivo}`.

<!-- nuevas entradas arriba -->

## 2026-07-22 [merge] [test-devstore] Unificación BXGY+Pack LatAm + E2E de FAQ
Tienda: **Testing StandAlone Framework** (dev store, USD). **Nada escrito en blunua producción.**

- **Merge unificado (`9e60b17`, en main):** se juntaron los carriles paralelos — builder + FAQ +
  Pack LatAm (F1+F2+F3: `worker.faq`/`worker.trust`, owner SHOP, bloques confianza/whatsapp) + BXGY
  (regalo, `_check_bxgy`) + el fix de seguridad HIGH del review de BXGY. Merge limpio (regiones
  distintas del guard), **sin funciones duplicadas**. Verificado por la suite corriendo junta:
  **250 tests pytest + 3 de Node, todo verde.** La rama `feat/regalo-bxgy-m1` quedó como subconjunto
  de main (redundante).
- **E2E de FAQ, camino real por el guard** sobre *The Complete Snowboard*
  (`gid://shopify/Product/10429846257981`): backup `kind:"faq"` → `metafieldsSet worker.faq` por
  `graphql_mutation` a través del guard → metafield creado (`...386173`), leído de vuelta idéntico.
  El guard dejó pasar la FAQ válida con backup fresco, y **bloquea** una FAQ con `<script>` (probado
  en el módulo vivo). El **JSON-LD FAQPage** que emite el widget se validó estructuralmente (2
  Question/Answer bien formados).
- **Fixture vivo:** la FAQ quedó en *The Complete Snowboard* de la dev store a propósito, para ver el
  render al instalar el bloque. Para sacarla: "sacá las preguntas frecuentes de The Complete Snowboard".
- **Pendiente (operador, no automatizable):** instalar los bloques en el tema (write de tema bloqueado
  por diseño) + verificar el render visual + correr el Rich Results de Google (necesita URL pública;
  la dev store tiene contraseña).

## 2026-07-22 [oferta] [test-devstore] The Multi-managed Snowboard — flujo completo del builder
Tienda: **Testing StandAlone Framework** (dev store). **Nada en blunua producción.** Prueba
end-to-end del builder: config `🧩 escalones-config` pegada → revalidación contra el techo → preview
ANTES/DESPUÉS → gate → backup → write. Reemplazó la oferta demo (2/-10%, 3/-20%) por 2/-10%,
3/-18%, 4/-23%.

- Backup: `clients/blunua/backups/deals/10429846683965-20260722-103830.json` (`previous` = oferta demo).
- Creados:      `.../1765733761341` (2+ 10%), `.../1765733892413` (3+ 18%), `.../1765732679997` (4+ 23%).
- Desactivados: `.../1765235720509` (2+ 10% viejo), `.../1765235786045` (3+ 20% viejo) → EXPIRED.
- **HALLAZGO (título único):** al reemplazar, crear un nuevo `· 2+`/`· 3+` chocó con el viejo aún
  activo — **Shopify exige título único entre descuentos automáticos**. El `· 4+` entró (no había
  viejo). Recuperado con sufijo de timestamp (`· 103830`). **FIX pendiente en
  `strategies/automatic.md`:** el formato de título tiene que llevar un token único SIEMPRE, porque
  el orden crear→desactivar hace que el viejo siga vivo cuando se crea el nuevo. Sin eso, todo
  reemplazo de oferta falla a la mitad.

## 2026-07-21 [test] [e2e] §14 resuelto en vivo + widget M2 construido
Tienda: **Testing StandAlone Framework** (dev store, USD). **Nada escrito en blunua producción.**
Corrige la entrada de abajo (2026-07-20): la validación empírica de §14 **ya no es "pendiente para
el M2"** — se corrió y las tres incógnitas dieron favorable.

- **Demo en vivo, camino canónico completo** sobre *The Multi-managed Snowboard*
  (`gid://shopify/Product/10429846683965`, $629.95, variante única): backup de oferta → dos
  descuentos automáticos (`2+ →10%`, `3+ →20%`) por `graphql_mutation` a través del guard →
  metafield `worker.deal`. El guard dejó pasar exactamente las dos clases de escritura y nada más.
- **Las tres incógnitas de §14, verificadas contra el carrito real** (mejor que `draftOrderCalculate`,
  que el guard bloquea): A) los dos automáticos coexisten `ACTIVE`; B) a 3 unidades gana el 20%, no
  se apila con el 10% (`combinesWith.productDiscounts:false`); C) 1 snowboard + 1 producto distinto
  → **sin descuento** (umbral por producto). 2u = $1,133.92 (10%), 3u = $1,511.88 (20%).
- **Lección del centavo:** el carrito cobró $1,133.**92**, no $1,133.**91**. Shopify redondea
  **por unidad** y después multiplica. El widget calcula igual (verificado en Node, todo verde).
- **Backup de prueba borrado** (era transitorio, sobre id de dev store). La **oferta demo quedó
  VIVA** en la dev store a propósito: es el fixture para instalar y ver el widget. No es blunua.
- **Widget M2 construido:** `widget/worker-escalones.liquid` (híbrido del brainstorm: tarjetas +
  barra de progreso, colapso mobile, botón que canta cantidad+total, `update.js` que fija) +
  `docs/runbooks/instalar-widget-escalones.md`.
- **Pendiente M2:** instalación manual del bloque en el tema (E4, operador — los writes de tema
  están bloqueados por diseño) y los N selectores mezclables de §4.6 (v1 usa una variante).

## 2026-07-20 [milestone] Escalones por cantidad — M1 (guard + política + skill)

**No se escribió nada en la tienda de blunua.** Este milestone es código y documentación: agrega
la segunda clase de escritura (ofertas) con su guardrail, pero todavía no se usó contra la tienda
real. La validación empírica contra development store queda para el M2 y es **bloqueante**.

- **Lo que se construyó (7 tareas planificadas):** techo por cliente en `deal-policy.json` + su
  loader; backup de oferta como tipo propio (discriminado por ruta `backups/deals/` **y** por
  `kind == "deal"`); whitelist cerrada de descuentos con el techo aplicado; validación del
  metafield `worker.deal` con el mismo techo que el descuento; el skill `armar-escalones` con sus
  dos estrategias; y esta actualización de gobernanza.
- **Seis arreglos de seguridad NO planificados**, todos sobre agujeros que **ya existían en `main`
  antes de este trabajo** — no los introdujo el milestone, los destapó:
  1. El guard inspeccionaba solo la **primera** mutación del documento: el resto pasaba sin mirar.
  2. Un mismo documento podía **mezclar asuntos** (oferta + metafield + edición de producto) y
     colarse por la rama más permisiva. Ahora es un solo asunto por documento.
  3. La familia `product*` era blocklist, no whitelist: **21 mutaciones** entraban por no estar
     enumeradas. Hoy solo pasa `productUpdate`.
  4. Un query vacío se leía como permitido en vez de **desconocido**; `collection*` no tenía
     whitelist (ahora no se permite ninguna); y un regex se comía los dígitos del nombre.
  5. `metafieldsSet` sin `ownerId` se bloqueaba de casualidad, no por diseño.
  6. El mensaje del payload inline decía algo que no era cierto sobre lo que había revisado.
- **Tests: 65 → 146.** Todos verdes. Los tres smokes del hook real (proceso + stdin, no solo
  `evaluate()`) pasan: desactivar oferta permitido, `discountAutomaticBxgyCreate` bloqueado,
  metafield con namespace ajeno bloqueado.
- **Lo que NO cambió de política:** `create-discount` sigue **denegado** en `permissions.deny`
  (verificado por aserción, no por grep). El camino válido es `graphql_mutation` a través de la
  whitelist, que es el único que puede aplicar el techo. Los borrados siguen bloqueados en sus
  cinco variantes: una oferta se **desactiva**, nunca se borra.
- **Techo vigente para blunua** (en `deal-policy.json`, explicado en §11 de `store-standards.md`):
  30% máximo por escalón, 90 días máximo, 4 escalones máximo, fecha de fin obligatoria, nunca a
  nivel colección.
- **Pendiente para el M2:** correr los tres tests empíricos contra development store
  (**bloqueante** — de su resultado depende la forma del widget), el widget en sí, y la
  instalación del bloque Custom Liquid en el tema.

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
