# Catálogo de widgets — generalizar el patrón escalones (diseño)

- **Fecha:** 2026-07-22
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** **DRAFT autónomo** — escrito de una tirada sin brainstorm interactivo (Gabriel dormido,
  pidió "avanzar sin detenerte, mañana revisamos"). **NO es diseño aprobado.** Trae recomendaciones
  con default + las decisiones abiertas que necesito de Gabriel (§12). El brainstorm real es el review
  de la mañana.
- **Cliente piloto:** blunua (joyería, COP)
- **Spec padre:** `2026-07-19-quantity-breaks-design.md` (el widget) + `2026-07-21-escalones-builder-design.md`
  (el builder). Este doc **generaliza** esos dos a un programa de widgets.
- **Fuentes ingeridas:** `wigy.app/todos` (45 widgets) + `crecenube.com/#apps` (8 apps + 6 calculadoras).

> **Nota de reconciliación (post-commit, misma noche).** Mientras escribía esto, un stream paralelo
> (otro agente que Gabriel dejó corriendo el mismo "hace todo") commiteó en `main`: el guard de
> `worker.style` **ya shippeado** (`e838cc8`, `_check_style` bespoke en `backup_guard.py:689`), el
> render como fuente única (`8680c54`, `widget/render/worker-render.js` — Tasks 1-2 del plan del
> builder, hechos), y un **spec completo de regalo-gratis BxGy** (`8c881a0`,
> `2026-07-22-regalo-gratis-bxgy-design.md`). Eso cambia dos cosas acá, ya corregidas abajo:
> 1. **`worker.style` no es una decisión abierta: está construido bespoke.** El registro
>    `COSMETIC_METAFIELDS` pasa de "decisión antes de construir" a **refactor cuando lleguen las
>    familias cosméticas** (§7, §12-D1). No es urgente ni bloqueante.
> 2. **La familia Ofertas-ampliadas ya tiene diseño.** El regalo-gratis BxGy (mismo-producto = "2x1/3x2"
>    de wigy; cruzado = "productos complementarios/pack") está especificado en detalle en su propio
>    spec. Mi catálogo lo **referencia**, no lo re-diseña (§5, §6, §11).

---

## 1. Contexto y objetivo

El escalones (M2) probó, contra el connector real, que shopify-control puede darle a un cliente no
técnico un **widget de vitrina** sin salir de sus guardrails: el dato vive en un metafield `worker.*`
que Claude escribe por el camino auditado (`backup_guard` + techo), y un bloque Custom Liquid lo
renderiza en la tienda. Cero backend, cero hosting, cero infra nueva.

Gabriel pasó el catálogo de una app de widgets (el escalones salió de ahí — es el "Bundle de cantidad")
y ahora suma dos catálogos de referencia del mercado LatAm: **wigy** (45 widgets) y **crecenube**
(8 apps + calculadoras). La pregunta que abre: *¿cuáles de estos adoptamos, y cómo, sin romper la
promesa de "seguridad por diseño" ni la de "cero jerga con el cliente"?*

**Objetivo:** convertir el patrón escalones en un **programa de widgets** donde:
1. **Agregar un widget sea mecánico** (mismo modo que la capa de canales hizo para las plataformas):
   una receta fija, un registro en el guard, un template de skill.
2. **El guardrail sea el filtro explícito**, no una decisión caso por caso: una línea nítida entre lo
   que encaja en la arquitectura sin backend y lo que es "territorio de app".
3. **YAGNI se respete**: 45 widgets de wigy no son 45 proyectos. Se consolidan en ~7 familias (§6).

**Lo que este doc NO decide:** no construye nada, no aprueba alcance, no ratifica la forma del guard.
Es el mapa para que la mañana decida el orden y la primera familia a construir.

---

## 2. Fuentes y deduplicación (responde "no sé si están repetidas")

**Sí, están casi todas repetidas.** crecenube (vitrina) es un **subconjunto** de wigy:

| crecenube (app) | = wigy (widget) | Verdict compartido |
|---|---|---|
| Barra de Envío Gratis | Barra de progreso | ADOPTA (matiz cart) |
| Barra de Anuncios | Banner superior / deslizante | ADOPTA (shop) |
| Temporizador | Cuenta regresiva | ADOPTA |
| Urgencia de Stock | Urgencia de stock | ADOPTA (matiz: dato real) |
| Notificaciones de Stock | Aviso de stock | **FUERA** (email backend) |
| PopNube (social proof) | Notificaciones | **FUERA** (event stream) + honestidad |
| PopupExit | Pop-up + Cupón | **FUERA** (email + código) |
| FAQ de Producto | Preguntas frecuentes | ADOPTA |

**El aporte único de crecenube NO es de vitrina, es de operador:** seis **calculadoras** (margen,
descuentos, envío gratis, fiscal de envío, ROI de publicidad) + un animador de texto GIF. Esas no van
en la tienda del cliente — son utilidades del operador y tienen su propio bucket (§10).

**Conclusión:** el catálogo maestro se arma **sobre wigy** (el superconjunto de vitrina) y crecenube
solo aporta las calculadoras. No hay que mirar los dos como listas separadas.

---

## 3. El "recipe" del widget (el patrón escalones, generalizado)

Extraído del código real (`widget/worker-escalones.liquid`, `backup_guard.py`, el plan del builder).
Un widget adoptable son **seis piezas**, y agregar uno es llenarlas:

| # | Pieza | Qué es | Evidencia en escalones |
|---|---|---|---|
| 1 | **Metafield `worker.{key}`** (JSON) | El dato del widget. Owner PRODUCT (por producto) o SHOP (por tienda). Lo escribe Claude por el guard. | `worker.deal` (plata), `worker.style` (cosmético) |
| 2 | **Bloque Custom Liquid** `widget/worker-{key}.liquid` | Se pega UNA vez en el tema (los writes de tema están bloqueados por diseño → lo hace el operador). Vuelca el metafield a `<script type="application/json">`, JS vanilla **sin `innerHTML`**, sin dependencias externas. **Estado por defecto: si no hay dato, no renderiza nada.** | `{%- if deal and deal.tiers -%}`; `readJSON()`; fábrica de nodos `el()` |
| 3 | **Extensión del guard** | El guard aprende a validar `worker.{key}` con **set cerrado de keys** + **backup propio `kind:"{key}"`** discriminado por ruta+kind. Si mueve plata → techo por cliente en `{key}-policy.json`. Si es cosmético → validación cerrada, sin techo. | `_covering_deal_backup`, `_check_metafield`, el `_check_style`/`_covering_style_backup` del plan del builder |
| 4 | **Skill generador** (+ opcional builder visual) | Un skill que arma el dato en lenguaje natural, o un HTML autocontenido (playground) con handoff por pegado (marcador `🧩 {key}-config`). Corre el protocolo: paso 0 → contexto → preview → gate → backup → write. | `armar-escalones` + `generar-builder-escalones` |
| 5 | **Tests** | pytest (guard: acepta válido, bloquea key desconocida / owner ajeno / sin backup / cruce de `kind`). Node si hay lógica de dinero (redondeo por unidad, round-trip). | `test_backup_guard_deals.py`, la "lección del centavo" en Node |
| 6 | **Runbook** de instalación | Cómo el operador pega el bloque en el tema y verifica. | `docs/runbooks/instalar-widget-escalones.md` |

> **La receta ya distingue dos posturas de metafield**, y esa distinción es la que hace mecánico el
> resto: **plata** (con techo, backup `kind:"deal"`) vs. **cosmético** (sin techo, validación de set
> cerrado, backup `kind` propio). El builder de escalones está agregando la primera instancia
> cosmética (`worker.style`). Casi todos los widgets nuevos son de la clase cosmética.

---

## 4. Marco de clasificación (el guardrail como filtro)

Cada widget se evalúa contra cuatro preguntas. La **primera que dé "sí"** define el bucket:

1. **¿Necesita un write fuera de `{texto, ofertas}`** (precio, stock, status, tags, título, handle)?
   → si toca eso, **fuera de alcance** (lo bloquea el guard/`permissions.deny` por diseño).
2. **¿Necesita capturar PII o correr un backend** (emails, reseñas juntadas, formularios, stream de
   eventos, ML)? → **fuera de alcance (arquitectura):** shopify-control no tiene infra por diseño.
3. **¿Necesita estado por cliente final** (wishlist con login, favoritos persistentes)? → **fuera de
   alcance** salvo variante degradada por `localStorage` (borderline, §9).
4. **¿El dato es honesto?** (¿la urgencia es real, la reseña existe, el countdown no resetea?) → si el
   widget **solo funciona mintiendo**, no se construye aunque sea técnicamente posible (§8).

Si pasó las cuatro → **adopta**, y cae en una de dos:
- **Adopta limpio:** presentacional, dirigido por metafield cosmético, sin nada de lo anterior.
- **Adopta con matiz:** encaja pero toca el camino de ofertas (descuentos con techo), o es cart/shop-
  scope, o lee dato en vivo (stock). Necesita una decisión de diseño puntual, no un rediseño.

Buckets finales: `YA CUBIERTO` · `ADOPTA` · `ADOPTA c/matiz` · `FUERA (arquitectura)` · `OPERADOR`.

---

## 5. Catálogo maestro (wigy 45, deduplicado, con verdict)

Columna "→": el metafield/owner propuesto. **PROD** = por producto, **SHOP** = por tienda.

| # | Widget (wigy) | Verdict | → propuesta | Nota |
|---|---|---|---|---|
| 2 | Bundle de cantidad | **YA CUBIERTO** | `worker.deal` PROD | Es el escalones (M2). |
| 32 | Texto libre | **YA CUBIERTO** | descripción | Cae en `mejorar-descripcion` (clase texto). |
| 6 | Mensaje de alerta | ADOPTA | `worker.trust` PROD | Familia Confianza (§6). |
| 7 | Mensaje de garantía | ADOPTA | `worker.trust` PROD | Familia Confianza. |
| 11 | Badge de envío | ADOPTA | `worker.trust` PROD/SHOP | Familia Confianza. |
| 12 | Badge de cuotas | ADOPTA | `worker.trust` SHOP | **Alto valor LatAm** (cuotas sin interés). |
| 13 | Badge de transferencia | ADOPTA | `worker.trust` SHOP | **Alto valor LatAm** (dto. transferencia). El descuento en sí es config de pago (fuera); el badge es copy. |
| 19 | Lista de beneficios | ADOPTA | `worker.trust` PROD | Familia Confianza. |
| 25 | Información de envío | ADOPTA | `worker.trust` SHOP | Familia Confianza. |
| 26 | Información de despacho | ADOPTA | `worker.trust` SHOP | Corte horario + reloj cliente. Honesto si el corte es real. |
| 38 | Tags (etiquetas sobre imagen) | ADOPTA | `worker.trust` PROD | Familia Confianza. |
| 15 | Preguntas frecuentes | ADOPTA | `worker.faq` PROD | **+ schema FAQPage** → gana SEO/GEO. Alinea con el foco de `mejorar-descripcion`. |
| 20 | Tabla de talles | ADOPTA | `worker.sizechart` PROD/COL | **Relevante joyería** (talles de anillo). |
| 16 | Cuenta regresiva | ADOPTA | `worker.countdown` PROD/SHOP | Se acopla al `endsAt` de una oferta. Honesto = no resetea (§8). |
| 18 | Comparador antes y después | ADOPTA | `worker.media` PROD | 2 URLs de imagen. |
| 24 | Slider de imágenes | ADOPTA | `worker.media` PROD | Familia Contenido. |
| 4 | Slider de videos | ADOPTA | `worker.media` PROD | Familia Contenido. |
| 29 | Video y texto | ADOPTA | `worker.media` PROD | Solapa descripción. |
| 30 | Imágenes y texto | ADOPTA | `worker.media` PROD | Solapa descripción. |
| 31 | Columnas de imágenes y texto | ADOPTA | `worker.media` PROD | Solapa descripción. |
| 27 | Pestañas de información | ADOPTA | `worker.media` PROD | Solapa descripción. |
| 33 | Pasos (timeline de uso) | ADOPTA | `worker.media` PROD | Ojo nombre: "Pasos" ≠ "escalones". |
| 34 | Comparador de marca | ADOPTA | `worker.media` PROD | Tabla marca vs. competencia. |
| 9 | Banner superior | ADOPTA | `worker.bar` SHOP | Familia Vitrina. |
| 10 | Banner deslizante | ADOPTA | `worker.bar` SHOP | Familia Vitrina. |
| 5 | Barra de acción (sticky ATC) | ADOPTA | bloque SHOP, sin dato | Familia Vitrina. Cosmético puro. |
| 35 | Video flotante | ADOPTA | `worker.float` SHOP | Familia Vitrina. |
| 36 | Botón de WhatsApp | ADOPTA | `worker.float` SHOP | **Quick win LatAm** (conversión). |
| 3 | Bundle 2x1, 3x2 | **EN DISEÑO** | `worker.deal` (`bxgy` same) | = regalo-gratis mismo-producto. **Ya especificado** en `2026-07-22-regalo-gratis-bxgy-design.md`. |
| 1 | Productos complementarios | ADOPTA c/matiz | `worker.combo` PROD | Cross-sell (recomendación). Solapa `armar-combo` (hoy propone, no escribe). Distinto del regalo cruzado (que sí regala). |
| 17 | Pack complementarios | ADOPTA c/matiz | `worker.combo` PROD | Bundle fijo con descuento. **Ojo:** el bundle no es descuento nativo de Shopify (regalo-gratis §15/G1 lo deja fuera); parte cae en regalo cruzado, parte necesita otro motor. |
| 45 | Conjunto de looks | ADOPTA c/matiz | `worker.combo` PROD | Combos de outfit; solapa `armar-combo`. |
| 14 | Cupón de descuento (badge) | ADOPTA c/matiz | `worker.deal` (codes) | El badge muestra un código que tiene que existir (estrategia `codes`, hoy off para blunua). |
| 43 | Barra de progreso (envío gratis) | ADOPTA c/matiz | `worker.freeship` SHOP | Cart-scope, lee total del carrito client-side. |
| 44 | Urgencia de stock | ADOPTA c/matiz | bloque PROD, dato real | Lee `inventory_quantity` (read-only). **Honesto solo si es real** (§8). |
| 8 | Reseñas de clientes | **FUERA** | — | Necesita juntar reseñas (backend). Estático por metafield = borderline. |
| 22 | Caja de opiniones | **FUERA** | — | Igual que reseñas. |
| 23 | Caja de contacto | **FUERA** | — | Form → backend. Degradado a `mailto`/WhatsApp = borderline. |
| 21 | Probador virtual | **FUERA** | — | ML/cámara. Fuera de alcance duro. |
| 28 | Favoritos (wishlist) | **FUERA** | — | Estado por cliente. `localStorage`-only = borderline (§9). |
| 37 | Raspá y ganá | **FUERA** | — | Captura de email + genera código. |
| 39 | Girá y ganá | **FUERA** | — | Captura de email. |
| 40 | Aviso de stock (restock) | **FUERA** | — | Suscripción por email → backend. |
| 41 | Pop-up (email capture) | **FUERA** | — | Sin captura pierde el sentido; con captura, backend. |
| 42 | Notificaciones (social proof) | **FUERA** + honestidad | — | Stream de eventos y/o **prueba social falsa** (§8). |

**Tally:** 2 ya cubiertos · ~26 adopta · ~7 adopta c/matiz · ~10 fuera. La masa adoptable es
**presentacional-cosmética** → la clase `worker.style` que el builder de escalones ya está inaugurando.

---

## 6. Consolidación: 7 familias, no 45 one-offs (YAGNI)

Construir 45 bloques sería traicionar el YAGNI del repo. La mitad de la tabla es "un pedacito de copy
o media en la página de producto". Se consolidan en **familias**, cada una un bloque configurable con
N ítems:

| Familia | Metafield | Absorbe | Owner |
|---|---|---|---|
| **Ofertas** | `worker.deal` | escalones (**M2 done**), regalo/BxGy 2x1-3x2 + cruzado (**spec `regalo-gratis-bxgy`, en curso**), cupón (estrategia `codes`, off) | PROD |
| **Confianza** | `worker.trust` | alertas, garantía, badges (envío/cuotas/transferencia), beneficios, info envío/despacho, tags | PROD + SHOP |
| **Contenido enriquecido** | `worker.media` | video/imágenes y texto, columnas, pestañas, pasos, comparadores, sliders | PROD |
| **FAQ** | `worker.faq` | preguntas frecuentes (+ schema FAQPage) | PROD |
| **Talles** | `worker.sizechart` | tabla de talles | PROD/COL |
| **Urgencia honesta** | `worker.countdown` / `worker.freeship` | cuenta regresiva, barra de envío gratis, urgencia de stock (dato real) | PROD/SHOP |
| **Vitrina** | `worker.bar` / `worker.float` | banner/anuncios, barra de acción, WhatsApp, video flotante | SHOP |

Siete familias es un roadmap manejable y en el espíritu del repo. **Nota de solapamiento:** Contenido
enriquecido pisa fuerte a `mejorar-descripcion`. Antes de construir esa familia hay que decidir qué
va en la descripción (SEO, indexable) y qué en un bloque aparte (§12, decisión abierta).

---

## 7. Lo que el guard tiene que crecer (para que sea mecánico)

Hoy `backup_guard._check_metafield` está cableado a `worker.deal`, y el plan del builder le agrega
`worker.style` con un `_check_style` **hecho a mano**. Con 7 familias cosméticas, una función por
widget no escala. La generalización:

1. **Registro de validadores cosméticos**, no una función por key. Un dict
   `COSMETIC_METAFIELDS = { "style": StyleSpec, "trust": TrustSpec, "faq": FaqSpec, ... }` donde cada
   spec declara: set cerrado de keys, tipo por key (hex / texto ≤N / lista / url), y `kind` de backup.
   `_check_metafield` rutea por `key` al spec. Agregar un widget cosmético = agregar una entrada, no
   editar el guard.
2. **Owner SHOP además de PRODUCT.** Hoy el guard exige `/Product/` en `ownerId`. Los widgets de
   vitrina (WhatsApp, banner, envío gratis) escriben `worker.{key}` en el **SHOP**. El guard tiene que
   aceptar `/Shop/` **solo** para specs marcados `owner: shop`, y seguir exigiendo `/Product/` para el
   resto. (Ojo: un metafield de shop no tiene "producto de respaldo" → su backup se indexa por shop,
   no por `productIdTail`.)
3. **Backup `kind` por familia**, con la misma regla de cruce que ya se probó: un backup `kind:"trust"`
   no habilita un write de `deal`, y viceversa (el aislamiento por ruta+kind del §9.1 del builder es el
   patrón a copiar). Cada spec cosmético declara su `kind`.
4. **Las ofertas c/matiz tocan el techo, no el registro cosmético.** El regalo/BxGy (2x1/3x2 + cruzado)
   es **plata**: extiende la whitelist de descuentos (`discountAutomaticBxgyCreate` con un techo en
   `deal-policy.json`), no el registro cosmético. Es la parte cara y arriesgada → su propia ronda de
   review adversarial. **Ya tiene diseño** (`2026-07-22-regalo-gratis-bxgy-design.md`, `_check_bxgy`
   función propia, no reusa `_check_discount`).

> **Estado real (post-commit):** `_check_style` **ya está en `main`** bespoke (`e838cc8`,
> `backup_guard.py:689`) — lo shippeó el stream paralelo. El registro `COSMETIC_METAFIELDS` **no** es
> una decisión "antes de construir": es un **refactor para cuando llegue la 2ª familia cosmética**
> (Confianza, FAQ), no antes. Con una sola entrada (`style`) el bespoke está bien; la función-por-widget
> recién duele en la 3ª o 4ª. La regla se mantiene —*cuando* se agregue la 2ª, se hace el registro en vez
> de copiar `_check_style`—, pero no hay nada que revertir hoy. **Yo no toqué `backup_guard.py`**: el
> stream paralelo es dueño de ese archivo esta noche, y tocar el guard de plata desde dos sesiones a la
> vez es pedir un conflicto justo donde no se puede.

---

## 8. Guardrail de honestidad (nuevo, propio de este repo)

Varios widgets de wigy/crecenube **solo funcionan mintiendo**: prueba social inventada ("alguien
acaba de comprar" cuando no pasó), countdown que resetea al recargar, "quedan 2 unidades" sin stock
real. El repo tiene una obsesión documentada con *"verificado, no asumido"* (todo el worklog). Ese
valor se hace regla:

> **No se construye un widget que dependa de un dato falso, aunque sea técnicamente trivial.**
> - Countdown → atado a una fecha real (`endsAt` de una oferta, o una fecha que el cliente fija y que
>   **no** se resetea por sesión).
> - Urgencia de stock → lee `inventory_quantity` real; si no hay tracking, el widget no se muestra.
> - Prueba social ("Notificaciones"/PopNube) → **rechazada**: sin un stream de eventos real es engaño,
>   y con uno real es backend (fuera de alcance de todos modos). Doble no.

Esto también protege la marca de Worker: la herramienta que "no puede bajar un precio por accidente"
tampoco debería poder fabricar urgencia falsa.

---

## 9. Fuera de alcance por arquitectura (se diagnostica, no se construye)

Paralelo exacto a la Decisión **C7** de la capa de canales ("se diagnostica, no se corrige"). Los ~10
widgets que necesitan backend/PII/ML **no se construyen en shopify-control** — son territorio de una
app (wigy, crecenube, o una propia con infra). Qué hace el repo con ellos:

1. **Los reconoce como oportunidad** cuando el cliente los pide, en lenguaje natural, sin nombrar la
   limitación técnica (regla dura #1).
2. **Los anota** como "necesita una app / trabajo del equipo" en `worklog.md`.
3. **Borderline con degradación honesta** (candidatos a discutir, no a asumir):
   - *Caja de contacto* → un `mailto:` o botón de WhatsApp (ya adoptado) cubre el 80% sin backend.
   - *Favoritos* → wishlist por `localStorage` (sin login, se pierde entre dispositivos). Poco valor;
     probablemente no vale la pena.
   - *Reseñas* → testimonios **estáticos** curados por el operador en un metafield (no es un sistema de
     reseñas, es contenido; honesto si son reales y con permiso). Distinto de "juntar reseñas".

**Por qué no ampliar la arquitectura ahora:** meter un backend rompe la premisa central ("native-
Claude, cero infra, seguridad por diseño"). Si en algún momento se justifica, es un proyecto propio
—como Merchant Center en la capa de canales—, no una tarea de este programa.

---

## 10. Bucket operador: las calculadoras de crecenube

No son widgets de vitrina; son utilidades del **operador** (Gabriel) y encajan del lado interno del
repo, no en la tienda del cliente:

| Calculadora | Dónde enchufa |
|---|---|
| Precio con margen | Informa el **techo de escalones** (`deal-policy.json`): un descuento que borra el margen es un techo mal puesto. |
| Descuentos | Idem: valida que un escalón no venda a pérdida. |
| Envío gratis | Fija el umbral honesto de la Barra de envío gratis (§6, familia Urgencia). |
| Fiscal del envío | Contexto de costeo; no toca la tienda. |
| ROI de publicidad | Vive en la **capa de canales** (`google-ads.md`/`meta.md`), no acá. |
| Animador de texto GIF | Cosmético de operador; candidato débil, probablemente fuera. |

**Recomendación:** no construir calculadoras como features; **absorber su lógica** como reglas de
sanidad donde ya hay una decisión (el techo, el umbral de envío). Una calculadora suelta es una
feature; una regla de "no dejes armar un escalón bajo margen" es seguridad por diseño.

---

## 11. Prioridad para blunua (joyería, COP) — propuesta de milestones

Orden por **valor × bajo riesgo × encaje limpio**. Los quick wins son cosméticos (registro nuevo,
sin tocar plata):

- **W1 — Vitrina de confianza (quick wins).** Botón de WhatsApp, Badge de cuotas, Badge de
  transferencia, FAQ (+schema). Alto impacto de conversión en LatAm, todo `worker.trust`/`worker.faq`/
  `worker.float`, cosmético. Estrena el **registro de validadores** del §7. *Depende de: builder de
  escalones (que ya inaugura `worker.style` y el patrón cosmético).*
- **W2 — Talles + Contenido.** Tabla de talles (joyería) + la familia media, **después de decidir el
  corte descripción-vs-bloque** (§12-D2).
- **W3 — Urgencia honesta.** Cuenta regresiva (atada a `endsAt`), Barra de envío gratis, Urgencia de
  stock real. Introduce cart-scope y lectura de dato en vivo.
- **W4 — Ofertas ampliadas (la parte cara).** Regalo/BxGy: 2x1/3x2 (mismo-producto) + cruzado. Toca el
  guard de plata → review adversarial propia, como el M1 de escalones. **Ya en curso en paralelo:** spec
  `2026-07-22-regalo-gratis-bxgy-design.md` cerrado (brainstorm G1–G16), pendiente plan + implementación.
  Esta W corre en su propio carril, no depende de W1-W3.
- **Fuera de programa:** reseñas/social/wishlist/probador → §9, se anotan, no se construyen.

**Regla de secuencia:** primero lo cosmético (barato, estrena el registro), después lo de plata (caro,
riesgoso, review propio). Es la misma curva de riesgo que ya validó el repo.

---

## 12. Incógnitas abiertas — decisiones que necesito de vos (el review de la mañana)

Estas son las que **no** decidí solo porque cambian la forma de lo que se construye:

- **D1 — Cuándo refactorizar a registro cosmético.** `_check_style` ya está en `main` bespoke
  (`e838cc8`). No hay decisión "antes de construir": la pregunta es *cuándo* migrar a
  `COSMETIC_METAFIELDS` (§7). Mi recomendación: al construir la **2ª** familia cosmética (W1: Confianza/
  FAQ), no antes. Hoy no hay nada que revertir.
- **D2 — Corte descripción vs. bloque.** La familia Contenido (§6) pisa `mejorar-descripcion`. ¿Qué va
  en la descripción (indexable, SEO) y qué en un bloque aparte? Sin este corte, W2 duplica superficie.
- **D3 — ¿Owner SHOP entra ya o después?** Los quick wins de W1 (WhatsApp, badges de tienda) son
  shop-scope. Abrir `/Shop/` en el guard es un cambio de seguridad chico pero real. ¿Va en W1 o
  arrancamos W1 solo con lo product-scope (FAQ, badge de envío por producto)?
- **D4 — ¿"Confianza" es un bloque o varios?** Propongo **uno** (`worker.trust`, N ítems tipados).
  ¿De acuerdo, o preferís badges separados por control fino de posición en el tema?
- **D5 — Honestidad como regla dura.** ¿Ratificás §8 (rechazar prueba social falsa y urgencia falsa
  aunque el cliente las pida)? Es una postura de marca, no solo técnica.
- **D6 — "La app que te pasaste".** No tengo en contexto cuál fue (se resumió). ¿Era wigy, o una
  tercera? Si era otra, pasámela y hago el mismo merge — pero por lo que veo, wigy es superconjunto de
  todo lo de vitrina, así que probablemente no cambie el catálogo.

---

## 13. Relación con lo ya existente

- **Hay un carril paralelo corriendo** (otro agente, misma noche): ejecutó Tasks 1-2 del builder
  (guard `worker.style` + `worker-render.js`, commits `e838cc8`/`8680c54`) y cerró el spec de
  regalo-gratis BxGy (`8c881a0`). Este catálogo es el **mapa** que ubica esos dos trabajos dentro del
  programa: el builder es la primera instancia del patrón, el regalo es la 1ª familia de plata nueva.
  Los tres son piezas del mismo programa, no esfuerzos sueltos.
- **El builder de escalones sigue siendo la primera instancia** de este programa, no un desvío. Su
  `worker.style` es la semilla del registro cosmético (§7). El plan `2026-07-22-escalones-builder.md`
  se ejecuta igual; Tasks 1-2 ya están en `main`.
- **`armar-combo`** ya es el generador de la familia Ofertas-combo (hoy propone, no escribe). Cuando se
  construya `worker.combo`, ese skill gana el camino de write (como `armar-escalones` lo tiene).
- **La capa de canales** (`cubrir-demanda`, etc.) es ortogonal: diagnostica marketing, no pone widgets.
  Pero comparten el ADN "agregar X es mecánico" (canales → `.md` por canal; widgets → entrada de
  registro + receta).

---

## 14. Fuera de alcance de este doc (YAGNI)

- No construye ningún widget. Es el mapa, no la obra.
- No ratifica alcance ni forma del guard (eso es §12 + la mañana).
- No re-diseña el builder de escalones (solo marca dónde lo reencuadra: D1).
- No toca `backup_guard.py` ni ningún archivo de plata: cambiar el guard de dinero de forma autónoma,
  de noche, sin review, está explícitamente fuera de lo que hago solo.
