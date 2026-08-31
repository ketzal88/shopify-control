# Worklog — Blunua

Append-only. Cada write deja una entrada: `## YYYY-MM-DD [write] producto — backup: {archivo}`.

<!-- nuevas entradas arriba -->

## 2026-08-31 [write] Fase 1, categoría Aretes — limpieza puntual de body (4 fichas), backups 20260831-105729
Primera tanda de esta fase que sí toca la descripción visible (`descriptionHtml`), a pedido
explícito del cliente: corregir 2 hallazgos anotados en tandas anteriores. Cambio quirúrgico
(una sola frase por ficha), sin reescribir el resto del texto. Backup de cada producto en
`clients/blunua/backups/{id}-20260831-105729.json`.

- **"Acero inoxidable" → "acero quirúrgico" (2 fichas):** Aretes Deep Sea (8869331763521) y
  Candongas Destiny (9766682362177) decían el material equivocado en el cuerpo del texto. El SEO
  de ambas ya estaba correcto desde las tandas 3 y 4.
- **Corrección sobre lo anotado antes:** Candongas Corazón Bold (9908750647617), que había
  quedado anotado en la tanda 4 como con el mismo problema, en realidad **no lo tenía** — el
  "acero inoxidable" que se vio ahí era de su descripción SEO vieja (ya corregida en esa misma
  tanda 4), no del cuerpo. Se verificó en vivo antes de escribir y no se tocó.
- **Vocabulario prohibido sacado del body (2 fichas):** "mágico" → "encantador" en Topitos de
  Seguridad Fairy (10158929903937); "Lo mejor" → "Versátil" en Aretes Halley (10058547986753).
- **Candongas Imponente (1653916532834), revisada y dejada intacta:** sigue con "espectacular"
  en el texto, pero es una cita textual de una clienta real (Carolina Rigueros) en un testimonio,
  no texto de marca — por instrucción explícita del cliente, no se toca. Queda marcada como
  revisada, no como pendiente.
- **Verificado:** los 4 `update-product` devolvieron el `descriptionHtml` nuevo character por
  character; nada más cambió (status, tags, variantes e inventario idénticos a antes).

## 2026-08-28 [write] Fase 1, categoría Aretes — tanda 5 (20 fichas), backups 20260828-171708
Mismo alcance que tandas 3 y 4: solo título y descripción SEO, sin tocar la descripción visible
ni agregar preguntas frecuentes. Tomó las 20 fichas de Aretes con el título y/o la descripción
SEO más largos que quedaban (títulos de 67 a 76 caracteres, descripciones de 152 a 176). Backup
de cada producto en `clients/blunua/backups/{id}-20260828-171708.json`.

- **Fichas:** Topitos de Seguridad Iris (10042071023937), Candongas Deep (8867943055681),
  Topitos Crystal Round (10323711689025), Solitario Candonga Spike (8867942891841), Aretes
  Little Round (9908368310593), Candongas Swing Mini (9656310038849), Candongas Long Heart
  (9328462397761), Topitos Puntico (10057120973121), Aretes Estrellita Nieve (10034644058433),
  Aretes Grand L (9589561393473), Topitos de Seguridad Púrpura (10323790528833), Aretes Praia
  Blanc (10169213157697), Candongas Hollow (9908368834881), Candongas Eco (9908368703809),
  Topitos de Seguridad Ópalo (9766681936193), Aretes Drip (9686845915457), Topitos Star Shine
  for Kids (9097951641921), Candongas Aura (8798243684673), Topitos de Seguridad Dot
  (6830851915881), Topitos Flowers White (10323712016705).
- **Qué se escribió:** título SEO (45-57 caracteres, antes 58-76) y descripción SEO (123-150
  caracteres, antes 152-176) en las 20. La descripción visible no cambió en ninguna.
- **2 correcciones de nombre encontradas al leer el texto completo:** el SEO de "Aretes Drip"
  decía "Candongas Drip" (producto equivocado); el de "Topitos Flowers White" decía "Topitos
  Floral White Kids". Ambos corregidos al nombre real del producto.
- **Verificado:** las 20 mutaciones devolvieron `userErrors: []`, sin errores.

## 2026-08-28 [write] Fase 1, categoría Aretes — tanda 4 (18 fichas), backups 20260828-170924
Mismo alcance reducido que la tanda 3: solo título y descripción SEO, sin tocar la
descripción visible ni agregar preguntas frecuentes. Tomó las 18 fichas de Aretes con el
título y/o la descripción SEO más largos del catálogo (títulos de 65 a 75 caracteres,
descripciones de 169 a 263). Backup de cada producto en
`clients/blunua/backups/{id}-20260828-170924.json`.

- **Fichas:** Topitos Heart-O (9328463348033), Topitos Halo (9733833032001), Aretes Purity
  (9863459733825), Candongas Corazón Bold (9908750647617), Aretes Bodena (9805307838785),
  Topitos de Seguridad Orión (9733832933697), Aretes Mini Love (10000335012161), Topitos de
  Seguridad Triple (9328461250881), Candongas Cloud (9766682132801), Candongas Almond
  (9656309907777), Candongas Perla Rosa (9850279625025), Topitos de Seguridad Circle Mini
  (9328460726593), Candongas Destiny (9766682362177), Candongas Plum (9766684590401), Topitos
  Amatista Square (10323713950017), Aretes Seren (10169211879745), Arete Solitario Shine
  (10057720856897), Candongas Ether (8867943547201).
- **Qué se escribió:** título SEO (46-60 caracteres, antes 55-75) y descripción SEO (128-144
  caracteres, antes 169-263) en las 18. La descripción visible no cambió en ninguna.
- **Hallazgo anotado, no corregido (fuera de alcance de esta tanda):** Candongas Corazón Bold y
  Candongas Destiny dicen "acero inoxidable" en su descripción visible en vez de "acero
  quirúrgico". El SEO nuevo usa el material correcto de marca; la descripción visible queda
  pendiente para la tanda que toque body (mismo caso que Aretes Deep Sea en la tanda 3).
- **Verificado:** las 18 mutaciones devolvieron `userErrors: []`, sin errores.

## 2026-08-28 [write] Fase 1, categoría Aretes — tanda 3 (11 fichas), backups 20260828-170444
Primera tanda con alcance reducido a pedido del cliente: **solo campos SEO** (título y
descripción SEO), sin tocar la descripción visible ni agregar preguntas frecuentes — eso
queda para otra tanda. Tomó las 11 fichas de Aretes que no tenían nada de SEO cargado (10 sin
título ni descripción, 1 con solo título). Backup de cada producto en
`clients/blunua/backups/{id}-20260828-170444.json`.

- **Fichas:** Topitos Cycle (10058568630593), Candongas Venus (9766683476289), Candongas Ball
  (9686874030401), Aretes Deep Sea (8869331763521), Candongas Starfish (8867944530241), Topitos
  de Seguridad Spike XS (8867943186753), Topitos de Seguridad Spike (8867943153985), Topitos
  Starfish (8867943088449), Topitos de Seguridad Cruz (8047943778625), Topitos de Seguridad
  Corazoncito (8043223187777), Topitos Corazón Definido (1653938520162).
- **Qué se escribió:** título SEO (bajo 60 caracteres) y descripción SEO (bajo 150) en las 11.
  La descripción visible (`descriptionHtml`) no cambió en ninguna.
- **Corrección de estándar previa a esta tanda:** Gabriel confirmó que los productos dorados y
  rosados sí llevan un baño de oro de 14K/18K real, así que "baño de oro" dejó de ser vocabulario
  prohibido para esos casos (ver actualización en `store-standards.md §2`, commit `86cd723`).
  5 de estas 11 fichas mencionan el baño de oro en su SEO nuevo porque el producto lo tiene.
- **Hallazgo anotado, no corregido (fuera de alcance de esta tanda):** "Aretes Deep Sea" dice
  "acero inoxidable" en su descripción visible en vez de "acero quirúrgico" (material de marca).
  El SEO nuevo usa el material correcto; la descripción visible queda pendiente para la tanda que
  toque body.
- **Verificado:** las 11 mutaciones devolvieron `userErrors: []`, sin errores.

## 2026-08-28 [write] Fase 1, categoría Aretes — tanda 2 (15 fichas), backups 20260828-120420
Segunda tanda dentro de Aretes. A diferencia de la tanda 1 (que atacaba fichas sin SEO), esta
tomó las 15 fichas con el título SEO más largo del catálogo (77 a 86 caracteres, se cortaban en
Google) y les aplicó el mismo tratamiento completo: título acortado, bloque de preguntas
frecuentes agregado, y cualquier problema de exactitud que apareciera al leer el texto completo.
Backup de cada producto en `clients/blunua/backups/{id}-20260828-120420.json`.

- **Títulos acortados:** los 15 bajaron de 76-86 caracteres a 44-62.
- **Vocabulario prohibido sacado (2):** "mágico" en Topitos de Seguridad Unicornio,
  "espectaculares" en Candongas Red Love.
- **Nombre real vs. texto (1, mismo patrón que Aretes Sutil en la Fase 0):** el producto se llama
  "Candongas Petit for Kids" pero el título SEO y la ficha decían "Candongas Mini" — corregido en
  los dos lugares.
- **Typo (1):** "pierdra natural Jade" → "piedra natural Jade" (Candongas Mare).
- **Concordancia de género (3):** Candongas Mare y Candongas Praia decían "hipoalergénicos y
  livianos" (debía ser "hipoalergénicas y livianas"); Candongas Maxi decía "hipoalergénico
  gruesos" — las tres corregidas.
- **Terminología de marca (1):** Candongas Re-mini for Kids decía "acero inoxidable" en vez de
  "acero quirúrgico" (el término que usa la marca en todo el resto del catálogo).
- **Color incompleto (1):** Topitos de Seguridad Eros For Kids solo mencionaba "plateado
  brillante" en el SEO pero el producto también viene en dorado — corregido.
- **Productos:** Topitos de Seguridad Unicornio, Aretes Equilibrio, Candongas Mare, Aretes Grand
  long, Candongas Praia, Candongas Maxi, Aretes Jewel, Candongas Re-mini for Kids, Topitos
  Básicos, Topitos de Seguridad Básicos Mini, Candongas Canal, Arete Solitario Bolitas, Topitos de
  Seguridad Eros For Kids, Candongas Red Love, Candongas Petit for Kids.
- **Qué NO cambió:** precio, stock, status, tags, handle.
- **Verificado:** las 30 escrituras (15 `update-product` + 15 `productUpdate.seo`) devolvieron
  `userErrors: []`.
- **Van 35 de 235 fichas de Aretes tratadas** (3 en la Fase 0: Aretes Sutil, Topitos Amapola,
  Topitos Flora + 17 en la tanda 1 + 15 en esta tanda). Quedan la mayoría de "Aretes Candongas"
  (85) y "Aretes Topitos" (44) sin tocar todavía.

## 2026-08-28 [write] Fase 1, categoría Aretes — tanda 1 (17 fichas), backups 20260828-114753
Primera tanda de la mejora de fondo por categoría (empezando por Aretes, a pedido del cliente).
Se tomaron las 17 fichas de Aretes que no tenían título y/o descripción SEO (de 19 detectadas,
2 ya se habían resuelto en la Fase 0: Topitos Amapola y Topitos Flora). Backup de cada producto en
`clients/blunua/backups/{id}-20260828-114753.json`.

- **Completado en las 17:** título SEO (donde faltaba), descripción SEO (donde faltaba), y el
  bloque de preguntas frecuentes en la ficha visible (mismo formato que ya usa Pulsera Savia:
  "Preguntas frecuentes:" + 2-3 ítems). Las preguntas sobre color se armaron mirando las variantes
  reales de cada producto (no se inventó ningún color).
- **Dos correcciones de exactitud encontradas al leer el texto (no eran solo falta de SEO):**
  - Topitos de Seguridad Star Shine: la ficha decía "en tonos dorado, plateado o negro" pero el
    producto solo tiene variantes Plateado/Negro — se sacó "dorado" del texto.
  - Candongas Amapola: decía "acero quirúrgico con baño dorado" — frase muy cerca de "bañado en
    oro" (vocabulario prohibido de §2, implica un chapado que no es el material real) — se cambió
    a "acero quirúrgico en tono dorado".
- **Rosca de seguridad:** tratada aparte (es un repuesto, no una pieza de diseño) — se completó
  el SEO y se sumaron preguntas frecuentes propias de un repuesto (compatibilidad, colores,
  material), sin forzar el molde de beneficios de una joya.
- **Productos:** Rosca de seguridad, Topitos de Seguridad Star Shine, Solitario Candonga Lek,
  Candongas Mara, Earcuff Dan, Candongas Savia, Topitos Sara, Candongas Sara, Candongas Amapola,
  Candongas Aire, Topitos Aire, Topitos Gaia, Aretes Petal, Aretes Mist, Candongas Mist Bold,
  Aretes Aster, Topitos de Seguridad Glow.
- **Qué NO cambió:** precio, stock, status, tags, handle — no tocados por este flujo.
- **Verificado:** las 34 escrituras (17 `update-product` + 17 `productUpdate.seo`) devolvieron
  `userErrors: []`.
- **Pendiente dentro de Aretes:** quedan ~200 fichas más en la categoría con SEO ya completo pero
  sin bloque de preguntas frecuentes, y con títulos SEO largos (185 de 235 superan los 60
  caracteres) — próxima tanda.

## 2026-08-28 [write] Fase 0 del repaso SEO/GEO — 11 fichas, backups 20260828-110957
Después de un repaso completo de las 710 fichas (título/descripción SEO en todo el catálogo +
lectura profunda de 32 productos) se armó una lista de correcciones puntuales (bugs, no mejoras
de fondo) y se aplicaron con el OK del cliente. Backup de cada producto en
`clients/blunua/backups/{id}-20260828-110957.json` (los 3 campos, previo a escribir).

- **SEO cruzado/equivocado corregido (7 fichas, solo SEO):**
  - Collar Origen ID F (`9686848602433`): título/descripción decían "letra N" — corregido a "letra F".
  - Collar Paua (`10172893200705`): tenía la descripción SEO de Candongas Mare (hablaba de aros y
    piedra Jade) — reescrita para el propio producto.
  - Collar Duo Fer (`10323710673217`): tenía la descripción de Collar Fer (no mencionaba la cadena
    doble) — reescrita.
  - Tobillera Figaro (`10323712278849`): la descripción SEO decía "Pulsera Figaro" — corregida a
    tobillera.
- **Sin título SEO + descripción genérica compartida entre pareja (4 fichas, solo SEO):**
  Topitos Amapola (`10211817750849`), Topitos Flora (`10211818144065`), Pulsera Amapola
  (`10211817947457`), Pulsera Flora (`10211818078529`) — cada una recibió título y descripción
  SEO propios (antes compartían el mismo texto genérico y no tenían título).
- **Vocabulario de marca (2 fichas):**
  - Collar Mega (`9686853157185`): la descripción SEO nombraba "plata" como material — pasó a
    "tono plateado"; "acero inoxidable" → "acero quirúrgico" (consistencia de término). Solo SEO.
  - Pulsera Unicornio (`8867944005953`): "mágico"/"magia" aparecía 3 veces (título SEO,
    descripción SEO y 2 veces en la ficha visible) — se sacó en las 3. Aprovechando el toque, la
    ficha visible pasó de "materiales resistentes y cómodos" (vago) a nombrar el material real
    (acero quirúrgico hipoalergénico, resistente al agua). Descripción + SEO.
- **Nombre equivocado en la ficha visible (1 ficha):** Aretes Sutil (`9805307740481`) se llamaba
  a sí mismo "Candongas Sutil" dos veces en el texto — corregido a "Aretes Sutil", con el ajuste
  de género correspondiente (Fabricados/hipoalergénicos, no Fabricadas/hipoalergénicas).
  Descripción + SEO.
- **Qué NO se tocó:** Collar Origen ID N, Candongas Mare, Collar Fer y Pulsera Figaro — su propio
  texto ya estaba bien, el error estaba solo en la ficha "pareja". Tampoco se tocó la reseña de
  clienta en Candongas Imponente (usa "espectacular"): decisión explícita del cliente de no editar
  opiniones de clientes reales, aunque la palabra esté en la lista de vocabulario prohibido de
  marca — la regla aplica a la voz de la marca, no a citas textuales de terceros.
- **Qué NO cambió:** precio, stock, status, tags, handle — ningún write tocó esos campos (fuera
  de alcance de este flujo).
- **Verificado:** los 11 `productUpdate`/`update-product` devolvieron `userErrors: []`.
- **Pendiente:** Fase 1 (agregar bloque de preguntas frecuentes + completar SEO faltante +
  acortar títulos largos), por categoría, empezando por Pulseras/Charms/Tobilleras — ver el
  repaso completo más arriba en esta conversación (no queda en este worklog, es contexto de chat).

## 2026-07-24 [sizechart] Pulsera Savia — backup: sizechart/10211725803841-20260724-100228.json
Tabla de talles (`worker.sizechart`), medidas reales confirmadas por el cliente: largo base 17.5 cm +
extensión de +4 cm aprox. `previous: null` (no había tabla antes).

## 2026-07-24 [oferta] [trust] Pulsera Savia — backup: trust/10211725803841-20260724-100015.json
Sellos de confianza (`worker.trust`), solo en esta ficha (owner = producto, no shop). `previous: null`
(no había ninguno antes). 4 ítems: badge de cuotas (confirmado por el cliente: hasta 3 cuotas sin
interés con ADDI) + 3 mensajes cortos (apta para piel sensible, a prueba de agua, empaque listo para
regalar). Pendiente: tabla de talles (talla única) — el cliente pidió mostrarla junto con este sello,
queda para el siguiente paso.

## 2026-07-24 [write] Pulsera Savia — backup: 10211725803841-20260724-094416.json
Producto detectado sin ventas en los últimos 15 días, con el meta título de Google vacío y
descripción sin bloque de beneficios ni preguntas frecuentes. Se aplicó el molde canónico
(hook + 3 beneficios + material/garantía + 3 preguntas frecuentes) y se completó el SEO.
- **Descripción:** reescrita con viñetas de beneficios y bloque GEO.
- **SEO:** título completado (antes vacío) — "Pulsera Savia en acero quirúrgico hipoalergénico | blunua";
  resumen reescrito.
- **Qué NO cambió:** precio ($92.000), stock (96 u.), estado (ACTIVE), tags, handle. No verificado
  con lectura posterior en esta sesión — recomendable confirmar en el próximo `get-product`.
- **Pendiente (fuera de alcance de este skill):** foto genérica de caja de regalo en la galería,
  imágenes sin alt text — no tocables por este flujo (solo descripción + SEO).

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
