---
name: mejorar-descripcion
description: Mejora la descripción de un producto de Shopify con criterio SEO y GEO, cumpliendo los estándares de la tienda. Muestra un preview antes/después en el chat, pide confirmación, guarda un backup y permite revertir. Usar cuando el cliente pide mejorar, optimizar o reescribir la descripción de un producto, o cuando reporte-tienda detecta productos con descripción pobre.
---

# Mejorar descripción de producto

Skill de **escritura** sobre la tienda viva. Reusás el craft que ya existe; lo nuevo es el flujo seguro (preview → gate → backup → undo) y el cumplimiento de estándares.

## Reglas duras (no negociables)
- **Alcance:** solo tocás 3 campos: la descripción (`descriptionHtml`), el **meta title** (`seo.title`) y la **meta description** (`seo.description`). NUNCA precio, stock, status, tags, título ni handle/URL.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de skill ni comandos. Tampoco expliques limitaciones técnicas ("no tengo permisos", "falta un scope"): eso también es jerga.
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN voseo). Los textos literales de este archivo son **plantillas**: si el cliente tiene otro registro, adaptalos.
- **Nada se escribe sin:** (1) preview mostrado, (2) confirmación explícita del cliente, (3) backup guardado con los valores REALES.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)
La sesión se abre en la RAÍZ del repo, así que el contexto del cliente NO se carga solo.
1. Identificá el cliente y leé `clients/{slug}/CLAUDE.md` + `clients/{slug}/store-standards.md`.
2. Verificá con `Shopify:get-shop-info` **contra qué tienda** está conectado el connector.
3. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ** y avisá al operador. Nunca escribas sin confirmar la tienda: `switch-shop` existe y el connector puede estar apuntando a otra.

## Contexto que cargás (paso 1, ANTES de buscar el producto)
- `clients/{slug}/store-standards.md` (molde, registro, keywords por categoría, checklist, qué no tocar).
- La marca en handsOn (link en el `CLAUDE.md` del cliente): brand-voice, vocabulario.

Va **antes** de identificar el producto a propósito: la terminología del cliente vive ahí. Para blunua, §4 dice que en Colombia se dice **aretes** (nunca "aros") y **topitos**. Si buscás el producto sin ese vocabulario, buscás mal.

## Skills que reusás (no reinventes el craft)
- `handsOn-Worker/skills/humanizer/SKILL.md` — **obligatorio**. Hoy NO es invocable como skill desde este repo: leé ese archivo y aplicá sus reglas a mano.
- `seo-geo` — SEO + GEO.
- `generic-language-killer` — QA anti-genérico.
- `seo-schema` / `seo-content` / `seo-ecommerce` — schema y calidad de producto.
- `.claude/hooks/description_lint.py` — chequeo mecánico. **Se corre de verdad, por CLI, sobre el texto PLANO** (ver paso 6).

*(INTERNO: nunca nombres estos skills frente al cliente.)*

## Flujo (siempre en este orden)

1. **CARGAR CONTEXTO.** Lo de arriba.
2. **IDENTIFICAR.** El cliente dice qué producto. Buscalo con `Shopify:search_products`. **El filtro por título es difuso**: buscar `title:Anillo Cosmos` devuelve también otros anillos. Si hay más de un resultado, mostrá las opciones y preguntá cuál. NUNCA adivines qué producto editar.
3. **LEER EL ESTADO ACTUAL DE LOS 3 CAMPOS.** Son dos lecturas distintas:
   - **Descripción:** `Shopify:get-product` con el GID → `descriptionHtml`.
   - **SEO:** `Shopify:graphql_query` → `query($id: ID!){ product(id:$id){ seo { title description } } }`.

   ⚠️ **`get-product` NO devuelve el SEO.** Si backupeás lo que devuelve `get-product` y nada más, el backup queda con el SEO vacío, y entonces un "vuelve a la anterior" **borra el título y el resumen SEO reales del cliente** en vez de restaurarlos. Leé el SEO con la query de arriba, siempre.
4. **GENERAR.** Escribí la nueva descripción con el molde canónico de `store-standards §3`: título → hook → 3 beneficios → material/garantía → bloque GEO (2-4 preguntas frecuentes). Keywords tejidas en el texto, no en bloque aparte. Además generá meta title (~60 caracteres) y meta description (~155 caracteres).
5. **HUMANIZER (obligatorio).** Pasá todo el texto por el humanizer: sin em-dashes, sin voseo si el registro es neutro, sin significance inflation ni lenguaje promocional. Aplica a TODO lo que ve el cliente, no solo al cuerpo de la descripción.
6. **CHECKLIST.** Corré el linter de verdad, sobre el **texto plano** (no el HTML):

   ```
   python .claude/hooks/description_lint.py --keywords "acero quirúrgico,hipoalergénico" --dialect neutro
   ```
   (el texto va por stdin; sale 0 si está limpio, 1 y explica si hay issues)

   Chequea em-dash, longitud 80-150, keyword, **materiales falsos** (oro/plata/chapado: el material es acero quirúrgico), **lujo-vacío**, **claims médicos**, **voseo** y presencia del bloque GEO. Si algo falla, corregí ANTES del preview. **No muestres nada que no pase.** Después completá a mano los ítems que el linter no puede ver (vocabulario de marca, que el humanizer haya corrido).
7. **PREVIEW.** Mostrá el antes/después como **un mensaje normal en el chat** (NO dentro de ningún cuadro), con formato para que se lea fácil: títulos en negrita, viñetas y saltos de línea reales. Sin jerga. Orden: intro de una línea → la descripción nueva → "Cómo se va a ver en Google" → "Qué mejoré" en tildes → "Lo que decía antes" al final (secundario). Formato exacto abajo.
   > ⚠️ **El preview NUNCA va adentro del cuadro de confirmación del paso 8.** Ese cuadro aplasta los saltos de línea y las viñetas en un párrafo justificado ilegible (es el bug que veía el cliente: un muro de texto). El antes/después va SIEMPRE como mensaje de chat, que sí respeta el formato. El cuadro lleva SOLO la pregunta corta.
8. **GATE.** Recién después del preview, pedí el OK con un cuadro de confirmación (`AskUserQuestion`) que lleve **solo la pregunta corta**, sin nada del preview adentro:
   - Pregunta: `¿Lo aplico a tu tienda?`
   - Opciones: `Sí, aplicá` / `No, dejá como está`

   NO escribas nada hasta que elija "Sí, aplicá". Si elige "No", no escribís.
9. **BACKUP (antes de escribir).** Guardá los valores VIEJOS de los 3 campos en `clients/{slug}/backups/{productIdTail}-{YYYYMMDD-HHMMSS}.json`:
   ```json
   { "productId": "gid://shopify/Product/123", "fields": { "descriptionHtml": "...viejo...", "seo_title": "...viejo...", "seo_description": "...viejo..." }, "ts": "2026-07-19T12:00:00" }
   ```
   Las keys de `fields` son exactamente `descriptionHtml`, `seo_title`, `seo_description`, y **siempre los 3 juntos**. Los valores tienen que ser los REALES leídos en el paso 3: el guard rechaza un backup con los tres vacíos, justamente para que nadie se desbloquee con placeholders.

   **Producto genuinamente vacío (los 3 campos en `""`):** si en el paso 3 leíste la descripción Y el meta title Y el meta description los tres vacíos, agregá `"originalEmpty": true` al tope del JSON (al lado de `productId`, no dentro de `fields`) y dejá los 3 `fields` en `""`. Esa marca le declara al guard que el producto está vacío de verdad y habilita el primer write; sin ella, el guard bloquea. Ponela **solo** cuando de verdad leíste los tres vacíos, nunca sobre un producto con contenido. El undo no cambia: para volver a vacío, backupeás el estado actual (ya con contenido, así que backup normal sin marca) y reescribís los `""`. Ver `docs/superpowers/specs/2026-07-24-editar-producto-vacio-design.md`.

   *(Nota: `ts` NO es decorativo. El guard exige que el backup sea reciente por DOS medidas a la vez —la fecha de modificación del archivo Y el campo `ts` del contenido—, así que `ts` tiene que ser la hora real en que lo guardaste.)*
10. **ESCRIBIR (son DOS writes, porque el connector separa descripción y SEO).**
    - **Descripción:** `Shopify:update-product` con **solo** `{ id: <GID>, descriptionHtml: <nuevo> }`. No agregues ningún otro campo: el guard bloquea el write si aparece cualquier otra cosa.
    - **SEO:** `Shopify:graphql_mutation` con `productUpdate(product:{ id:<GID>, seo:{ title:<nuevo>, description:<nuevo> } })`. Usá `product:`, no `input:` (deprecado). Validá antes con `Shopify:validate_graphql_codeblocks`.

    El guard verifica en ambos writes que haya backup **y** que el write esté en alcance.
11. **WORKLOG.** Append a `clients/{slug}/worklog.md`: `## YYYY-MM-DD [write] {producto} — backup: {archivo}`.
12. **CONFIRMAR.** "Listo. Si no te convence, dime 'vuelve a la anterior' y lo dejo como estaba."

## Si el cliente pide algo fuera de alcance
Precio, stock, pausar o publicar un producto, cambiar el nombre o la dirección web, crear descuentos o colecciones: **no se hace y no se intenta.** Esos caminos además están bloqueados por diseño, así que intentarlo solo genera un error feo.

Guion (neutro, adaptar según `store-standards §2`):
> "Eso todavía no lo puedo cambiar yo. Lo anoto y lo vemos con el equipo."

Registralo en el worklog y seguí con lo que sí podés hacer. No expliques por qué no podés en términos técnicos.

## Preview — formato exacto (ejemplo blunua, registro neutro)

Esto va como **mensaje de chat** (el markdown de abajo se renderiza con negritas y viñetas: por eso se lee fácil). El cuadro de confirmación viene **después** y solo con la pregunta.

--- 8< --- así se ve el mensaje de chat --- 8< ---

**Anillo NEXO Plateado** — encontré la descripción actual y te propongo esta mejora.

**Así quedaría la descripción**

Anillo NEXO Plateado en acero quirúrgico, no irrita la piel.

Un anillo minimalista para todos los días. Se ve elegante pero sencillo, y está hecho en acero quirúrgico hipoalergénico que no destiñe ni irrita, incluso en pieles sensibles. Es parte de la colección NEXO, pensada para combinarse: funciona sola o en conjunto.

Por qué dura:
- Acero quirúrgico hipoalergénico, seguro para piel sensible y uso diario
- Resistente al agua, no se oxida ni pierde el brillo
- Diseño minimalista que combina con tu estilo sin robar protagonismo

Preguntas frecuentes:
- ¿Se puede mojar? Sí, resiste el agua sin problema.
- ¿Sirve para piel sensible? Sí, el acero quirúrgico es hipoalergénico.
- ¿Es ajustable? Sí, se adapta a tu dedo.

**Cómo se va a ver en Google**
- **Título:** Anillo NEXO en acero quirúrgico hipoalergénico | blunua
- **Resumen:** Anillo minimalista que no irrita la piel, resiste el agua y dura. Ideal para uso diario y para regalar.

**Qué mejoré**
- ✅ Agregué las palabras que la gente busca en Google
- ✅ Sumé preguntas frecuentes, que ayudan a aparecer en respuestas de Google y ChatGPT
- ✅ Usé la voz de blunua: cercana y clara, sin exagerar
- ✅ Dejé claro el beneficio principal: no irrita, dura, para uso diario

**Lo que decía antes**
> Anillo NEXO de acero. Color plateado. Ajustable. Material resistente.

*(En tu tienda el look final puede variar un poco: los títulos se ven en negrita y las viñetas como lista.)*

--- 8< --- fin del mensaje de chat --- 8< ---

Y **recién ahí** el cuadro de confirmación (paso 8), solo con la pregunta:

> `¿Lo aplico a tu tienda?`  →  `Sí, aplicá`  /  `No, dejá como está`

## Escritura en lote
- **Máximo 5 productos por lote.** Si el cliente pide más, hacelo en tandas y avisale.
- El preview muestra el **texto completo de cada uno**, no un resumen: el cliente no puede aprobar lo que no vio.
- Un solo gate para el lote, pero con los textos completos arriba.
- **Ventana del guard:** el backup vale 15 minutos. En un lote largo los primeros backups vencen y los últimos writes se bloquean. Si pasaron más de ~10 minutos desde que guardaste un backup, **volvé a guardarlo** antes de escribir ese producto.
- **Si el lote falla a la mitad:** decile al cliente exactamente cuáles quedaron aplicados y cuáles no, en lenguaje natural, y ofrecé retomar los que faltan. Nunca dejes el estado ambiguo.

## Revertir (undo)
"Vuelve a la anterior" es un write como cualquier otro: lleva preview, gate y confirmación.
1. Leé el valor ACTUAL de los 3 campos (descripción con `get-product`, SEO con `graphql_query`).
2. **Preview:** como **mensaje de chat** (mismo formato que arriba, nunca dentro del cuadro), mostrale a qué texto va a volver: "Ahora dice" vs "Volvería a decir".
3. **Gate:** cuadro de confirmación con **solo la pregunta corta** — `¿Lo dejo como estaba antes?` → `Sí, volvé` / `No, dejá lo nuevo`.
4. Guardá un backup fresco del valor ACTUAL (esto habilita también el *redo*), mismo formato y carpeta. Va primero: así el write pasa el guard aunque hayan pasado horas desde el cambio original.
5. Escribí los valores VIEJOS del último backup: descripción con `update-product`, SEO con `graphql_mutation`.
6. Append al worklog.
7. Confirmá: "Listo, quedó como estaba antes."
