---
name: subir-productos
description: Sube productos nuevos a partir de un archivo que entrega el cliente (más una carpeta de fotos), cumpliendo los estándares de la tienda. Primero prepara y muestra un preview producto por producto en el chat (F1); con la confirmación del cliente, los crea en Shopify como BORRADORES con variantes, precio e imágenes (F2); y —si el cliente lo pide y pasan un chequeo de completitud— los publica al Online Store para que queden a la venta (F3). También permite deshacer (archivar). Usar cuando el cliente quiere subir productos nuevos desde un archivo, cargar un catálogo, o dice que tiene una lista de productos para agregar (o para publicar los que ya cargó).
---

# Subir productos nuevos (F1 preparar · F2 crear borradores · F3 publicar)

Skill de tres fases sobre datos que el cliente entrega.

- **F1 — preparar y revisar (no escribe nada):** lee el archivo, lo agrupa en productos, lo valida,
  chequea contra la tienda viva cuáles ya existen, genera la descripción y el SEO de cada uno con el
  mismo craft que `mejorar-descripcion`, y arma un preview sin jerga. Termina en el preview.
- **F2 — crear borradores (escribe, con protocolo):** con la confirmación explícita del cliente,
  crea los productos que quedaron listos como **borradores inertes** en la tienda real —con
  variantes, precio e imágenes—, deja un registro de cada alta, y permite deshacerlas (archivarlas).
- **F3 — publicar (escribe, con protocolo y gate de completitud):** opcional y aparte. Pone el
  producto ACTIVO y lo muestra en el Online Store para que quede a la venta, solo si pasó un chequeo
  de completitud y el cliente lo confirmó.

> **Al crear, los productos quedan como borradores: NO están a la venta.** Publicarlos es una fase
> aparte (F3), con su propio chequeo y su propia confirmación. Nunca publiques como parte del alta.

## Reglas duras (no negociables)
- **F1 no escribe nada. F2 escribe SOLO borradores, y solo por el camino permitido.** El alta va
  siempre por `Shopify:graphql_mutation` con `productSet` en `status: "DRAFT"`. El connector tiene
  denegado el tool `create-product` a propósito: no lo uses, no hay camino alternativo.
- **Alcance de lo que se escribe en un alta (cerrado y mínimo).** El `productSet` solo puede llevar:
  `title`, `handle`, `descriptionHtml`, `seo`, `productType`, `tags`, `status`, `productOptions`,
  `variants` y `files`. Cada variante solo: `optionValues`, `price`, `sku`, `barcode`, `file`.
  **NUNCA** `collections`, `metafields`, `inventoryQuantities`/`inventoryItem` (stock), ni `id`. Un
  `productSet` con `id` edita un producto existente, no es un alta. El guard de seguridad enforcea
  todo esto: si mandás un campo fuera de ese set, o un status distinto de DRAFT, o un precio fuera
  del techo del cliente, te bloquea. No hay que pelearle al guard: hay que mandar exactamente el set
  permitido.
- **El alta es siempre en borrador.** `status: "DRAFT"`, sin excepción. Publicar (poner ACTIVO y
  mostrar en el Online Store) es la fase F3, aparte, con su propio gate; nunca se hace como parte del
  alta.
- **Publicar (F3) tiene su propio alcance cerrado.** Solo `productChangeStatus` a `ACTIVE` y
  `publishablePublish` al canal de la política (`allowedPublicationIds`, el Online Store). NUNCA a
  otro canal, NUNCA con fecha programada (`publishDate`), y **despublicar** (`publishableUnpublish`)
  sigue prohibido. Los dos writes van en **pedidos separados** (el guard no deja mezclarlos). El
  guard enforcea todo esto: no le pelees, mandá exactamente eso.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de archivo
  técnico, de campo, de comando, de skill, ni las palabras "CSV", "JSON", "productSet", "borrador
  técnico" ni "CLI". Al cliente se le habla de "tu archivo", "tu carpeta de fotos", y de que los
  productos "quedaron cargados pero todavía no publicados".
- **Registro:** el que diga `clients/{slug}/store-standards.md §2` (blunua: español neutro, SIN
  voseo). Los textos literales de este archivo son **plantillas**: adaptalos al registro del cliente.
- **Humanizer obligatorio** antes de todo texto que vea el cliente (preview y confirmaciones):
  `handsOn-Worker/skills/humanizer/SKILL.md`. Hoy no es invocable como skill desde este repo — leé
  ese archivo y aplicá sus reglas a mano.
- **Todo write lleva el protocolo completo** (confirmar tienda → cargar contexto → identificar →
  leer → generar → humanizer → checklist → preview → **gate explícito** → escribir → **registro de
  creación** → confirmar). **El undo (archivar) también es un write** y lleva su propio gate.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)
La sesión se abre en la RAÍZ del repo, así que el contexto del cliente NO se carga solo.
1. Identificá el cliente y leé `clients/{slug}/CLAUDE.md` + `clients/{slug}/store-standards.md`.
2. Verificá con `Shopify:get-shop-info` **contra qué tienda** está conectado el connector.
3. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ** y avisá al operador.
   Nunca sigas sin confirmar la tienda: `switch-shop` existe y el connector puede estar apuntando a
   otra.

## Contexto que cargás (antes de generar copy)
- `clients/{slug}/store-standards.md` (molde canónico §3, registro §2, keywords por categoría §4,
  checklist §9).
- La marca en handsOn (link en el `CLAUDE.md` del cliente): brand-voice, vocabulario.
- El techo de alta del cliente vive en `clients/{slug}/create-policy.json` (lo aplica el guard: piso
  y techo de precio, tamaño de lote, ventana para deshacer). No hace falta que lo cites al cliente;
  sí respetalo.

## Flujo F1 (siempre en este orden)

1. **RECIBIR.** Pedile al cliente, en lenguaje natural, dónde está el archivo con los productos
   nuevos y dónde está la carpeta con las fotos. Traducilo a dos rutas locales. No hace falta que el
   cliente sepa qué formato tiene el archivo: si viene de Shopify, ya sirve tal cual.

2. **PARSEAR.** Corré:

   ```
   python .claude/hooks/product_csv.py "<ruta del archivo>"
   ```

   Leé el resultado (por salida estándar): trae, por cada producto, un estado —`crear` o
   `rechazado`— y, si fue rechazado, el motivo en texto. Esto es trabajo interno: nunca lo mencionés
   al cliente con esos nombres. Si el archivo no se pudo leer o el comando falla, decile al cliente
   en lenguaje natural que no se pudo abrir el archivo y avisá al operador; no sigas adivinando el
   contenido.

3. **DEDUP VIVO.** Por cada producto que quedó en `crear`, buscá si ya existe en la tienda real:
   - `Shopify:search_products` por `handle:<handle del producto>`.
   - `Shopify:search_products` por `sku:<sku>` de cada variante.

   Si cualquiera de las dos búsquedas encuentra un match, ese producto pasa a "ya existe" y no se
   procesa más (no se le genera copy ni se crea). Guardá a qué producto de la tienda corresponde,
   para poder mencionarlo en el preview si hace falta.

4. **GENERAR COPY.** Por cada producto que sigue en `crear` (ni rechazado ni "ya existe"):
   - Escribí la descripción con el molde canónico de `store-standards §3`: título → hook → 3
     beneficios → material/garantía → bloque GEO (2-4 preguntas frecuentes). Tejé las keywords de
     `§4` en el texto, no en bloque aparte.
   - Generá también meta title (~60 caracteres) y meta description (~155 caracteres).
   - Pasá todo por el humanizer (obligatorio): `handsOn-Worker/skills/humanizer/SKILL.md`. Sin
     em-dashes, sin voseo si el registro es neutro, sin lenguaje promocional vacío.
   - Corré el linter de verdad, sobre el **texto plano** (no el HTML). El texto va por entrada
     estándar (por eso el `echo` adelante, si no el comando se queda esperando):

     ```
     echo "<texto plano de la descripción>" | python .claude/hooks/description_lint.py --keywords "<keywords de la categoría>" --dialect neutro
     ```

     Sale 0 si está limpio; 1 y explica cada issue si no. Si algo falla, corregí antes de seguir.
     **No mostrés en el preview ninguna descripción que no pase el linter.**

5. **PREVIEW.** Armá el mensaje de chat (nunca dentro de un cuadro de confirmación: eso aplasta el
   formato) con:
   - Un índice arriba de todo: cuántos productos quedaron listos para crear, cuántos ya existen en
     la tienda, y cuántos tienen algún problema (y por qué, en lenguaje natural).
   - El detalle de cada producto que quedó listo para crear: nombre, precio, variantes (por ejemplo
     color o talla), la descripción generada, cómo se va a ver en Google (título y resumen), y el
     estado de las fotos (si el archivo trae fotos o no para ese producto).
   - Los productos con problemas o que ya existen: mencionalos con el motivo, sin detalle técnico
     ("ese ya está en tu tienda, lo salteo" / "a ese le falta el precio, revisalo y lo volvemos a
     intentar").
   - **Cerrá el preview preguntando si querés que los cargue como borradores** (el gate de F2, abajo).
     No los cargues sin esa confirmación.

## Fase F2 — Crear los borradores

### 1. Gate de crear (explícito, sí/no)
Después del preview, preguntá en lenguaje natural si el cliente quiere que cargue esos productos.
Dejá claro **qué** se va a hacer y **qué no**:

> "Puedo cargarlos en tu tienda como borradores: van a quedar con sus fotos, variantes y precio,
> pero **todavía no a la venta**. Ponerlos a la venta es un paso aparte. ¿Los cargo así?"

Solo seguí si el cliente dice que sí. Si dice que no, quedate en el preview. Cargá **solo** los
productos que quedaron "listos para crear" (nunca los rechazados ni los que ya existen).

### 2. Imágenes (antes de crear cada producto)
Por cada foto del producto:
- **Si es una URL** (la foto ya vive en internet): usala directo como `files[].originalSource`.
- **Si es un archivo local** (está en la carpeta de fotos del cliente): subí los bytes con
  `Shopify:graphql_mutation` usando `stagedUploadsCreate` (resource `IMAGE`). Eso te devuelve un
  destino con `url` y `parameters`; hacé el `PUT`/`POST` de los bytes de la imagen a ese destino, y
  después usá el `resourceUrl` que te devolvió como `originalSource` en `files[]`.

Cada imagen que quieras mostrar va en `files[]`. Para atar una imagen a una variante puntual, poné
esa imagen también en `variants[].file` (y asegurate de que esté además en `files[]`).

> El pedido de subida (`stagedUploadsCreate`) va **solo**, sin ninguna otra operación en el mismo
> pedido: el guard bloquea mezclarlo con un alta o cualquier otra mutación. Hacé la subida primero,
> y recién después el `productSet` con la URL que te devolvió. Si por lo que sea la subida no sale,
> pedile al cliente la foto como link (URL) y usala directo en `originalSource`. Nunca fuerces otro
> camino de escritura.

### 3. Crear (un `productSet` en DRAFT por producto)
Armá la mutación y **validala antes** con `Shopify:validate_graphql_codeblocks`. Después corré
`Shopify:graphql_mutation` con `productSet(input: $p, synchronous: true)`, pasando el producto en
`variables` (no escrito dentro del query). El objeto `$p` lleva **solo** campos del set permitido:

```graphql
mutation($p: ProductSetInput!) {
  productSet(input: $p, synchronous: true) {
    product { id handle status }
    userErrors { field message }
  }
}
```

`variables`:

```json
{
  "p": {
    "title": "…",
    "handle": "…",
    "descriptionHtml": "…",
    "seo": { "title": "…", "description": "…" },
    "productType": "…",
    "tags": ["…"],
    "status": "DRAFT",
    "productOptions": [{ "name": "Color", "values": [{ "name": "Plata" }] }],
    "variants": [
      { "optionValues": [{ "optionName": "Color", "name": "Plata" }],
        "price": "120.00", "sku": "AX-1", "barcode": "…", "file": { "originalSource": "…" } }
    ],
    "files": [{ "originalSource": "…" }]
  }
}
```

- `status` **siempre** `"DRAFT"`.
- **Nunca** `collections`, `metafields`, `inventoryQuantities`/`inventoryItem`, ni `id`.
- Un producto por mutación (el guard bloquea dos operaciones de producto en el mismo pedido).
- Si `userErrors` vuelve con algo, no inventes: contáselo al cliente en lenguaje natural y frená ese
  producto.

### 4. Registro de creación (obligatorio, apenas el alta sale OK)
El registro es lo que habilita deshacer después. Apenas el `productSet` devuelve un `product.id`,
escribí `clients/{slug}/backups/create/{idTail}-{YYYYMMDD-HHMMSS}.json` (donde `idTail` es la parte
numérica del id) con exactamente:

```json
{ "kind": "create", "productId": "gid://shopify/Product/…", "handle": "…",
  "createdBy": "subir-productos", "ts": "<ISO 8601>" }
```

Sin este registro no vas a poder archivar el producto después (el guard exige un registro de
creación reciente para permitir el archivar).

### 5. Lote parcial y ventana
- Si el lote es grande, avisale al cliente que puede tardar y cargá de a uno.
- Si algo falla a mitad del lote, decile **exactamente cuáles quedaron cargados y cuáles no**, para
  que no queden dudas. No reintentes en silencio un producto que ya se creó (crearía un duplicado).
- El registro de creación tiene una ventana (la del `create-policy.json` del cliente) dentro de la
  cual se puede deshacer. Si el cliente quiere deshacer más tarde, avisale que quizás ya pasó la
  ventana.

### 6. Confirmar al cliente
Cerrá con un mensaje humanizado, sin jerga, que diga:
- Cuántos productos quedaron cargados y con qué nombre.
- Que quedaron **como borradores: todavía no están a la venta.**
- Que, si quiere, en un paso aparte los puedo **publicar** (dejarlos a la venta), y que antes de eso
  reviso que estén completos (ver F3, abajo).
- Que si se arrepiente, los puede sacar (archivar; ver abajo).

Registralo en `clients/{slug}/worklog.md`, por ejemplo:
`## YYYY-MM-DD [write] subir-productos — creé N borradores (M ya existían, K con problemas)`.

## Deshacer ("sacá los que subiste" / "borralos")
Deshacer **archiva** el producto (lo saca de la vista); no lo borra. Lleva su propio protocolo:
1. **Gate:** confirmá con el cliente cuáles quiere sacar y avisá que van a quedar archivados (no a
   la venta y fuera de la vitrina), no eliminados.
2. Por cada producto a archivar que tenga un **registro de creación reciente**, corré
   `Shopify:graphql_mutation` con `productChangeStatus(productId: …, status: ARCHIVED)`. Solo
   ARCHIVED: el guard bloquea cualquier otro destino (poner a la venta es F3; bajar a borrador no
   aplica).
3. Si un producto no tiene registro de creación reciente, no lo archives por este camino: decíselo
   al cliente ("ese no lo subí yo recién, así que desde acá no lo puedo sacar").
4. Registralo en el worklog:
   `## YYYY-MM-DD [write] subir-productos — archivé N borradores (undo)`.

## Fase F3 — Publicar (opcional, después de crear)
Publicar de verdad son **dos** cosas: poner el producto ACTIVO y **mostrarlo en el Online Store**. Un
producto activo no aparece solo en la tienda; hay que publicarlo al canal. Por eso son dos escrituras
separadas, cada una con su gate. Solo se publica lo que ya existe como borrador creado por acá.

### 1. Gate de completitud (código, ANTES del gate humano)
Antes de ofrecer publicar, revisá cada producto candidato y dejá afuera los que no estén completos.
Por cada uno:
- Tiene al menos una imagen (si la política del cliente pide imagen).
- La descripción llega al mínimo de palabras de la política.
- El precio es sano (dentro del techo del cliente).
- La descripción pasa `description_lint` (igual que en F1).

Los que no pasan **quedan como borradores** y se lo decís al cliente con el motivo, en lenguaje
natural ("a ese le falta una foto, lo dejo en borrador hasta que la sumemos").

### 2. Gate humano (explícito, sí/no)
Preguntá en natural: "¿Publico estos M?" y esperá el sí. Publicás **solo** los que pasaron el gate de
completitud y que el cliente confirmó.

### 3. Registro de publicación (obligatorio, ANTES de los writes)
Por cada producto que va a publicarse, tras pasar el gate de completitud y ANTES de escribir nada,
escribí `clients/{slug}/backups/publish/{idTail}-{YYYYMMDD-HHMMSS}.json` con exactamente:

```json
{ "kind": "publish", "productId": "gid://shopify/Product/…", "ts": "<ISO 8601>" }
```

El guard exige este registro (y el de creación de F2) para dejar publicar. Sin él, los dos writes de
abajo se bloquean.

### 4. Publicar (dos writes gateados, en DOS pedidos SEPARADOS)
No se pueden mezclar en un mismo pedido (el guard los separa a propósito). Uno por vez:
1. `Shopify:graphql_mutation` con `productChangeStatus(productId: …, status: ACTIVE)`.
2. `Shopify:graphql_mutation` con `publishablePublish(id: <productId>, input: $pubs)`, con `$pubs` en
   `variables` (**no** inline): `[{ "publicationId": "<gid del Online Store>" }]`.

El gid del Online Store lo sacás con una consulta de **solo lectura** de las publicaciones de la
tienda (`publications`) y **tiene que estar** en `allowedPublicationIds` de la política; si no
coincide, el guard bloquea. **Sin `publishDate`** (no hay publicación programada). Validá ambas
mutaciones con `Shopify:validate_graphql_codeblocks` antes.

### 5. Falla parcial de los dos writes
Si (1) ACTIVE sale bien pero (2) `publishablePublish` falla (por ejemplo, canal mal configurado), el
producto queda **activo pero sin mostrarse**. Detectá ese medio-estado y decíselo al cliente en
natural ("quedó listo pero no llegó a mostrarse en la tienda; lo reviso"), nunca lo dejes ambiguo —
igual que el lote parcial de F2.

### 6. Confirmar y registrar
Al cliente, en natural: "quedó publicado / a la venta". Registralo en el worklog:
`## YYYY-MM-DD [write] subir-productos — publiqué N productos`.

### Si publicar todavía no está configurado
Si `allowedPublicationIds` está vacío (el operador aún no cargó el canal), publicar no está
disponible: decíselo al cliente en natural ("todavía no puedo dejarlos a la venta desde acá; lo dejo
anotado para el equipo") y anotalo para el operador. No expliques el detalle técnico ni fuerces otro
camino.

### Despublicar / sacar de la venta
"Despublicá" o "sacá de la venta" **no está en alcance** (esa operación sigue bloqueada). Lo que sí
podés es **archivar** el producto (el "deshacer" de más arriba), que lo saca de la vista. Aclarale al
cliente esa diferencia si lo pide.

## Nota interna
Nunca nombres frente al cliente el comando, el archivo de resultado, los nombres de campo internos
(`handle`, `sku`, `status`, `productSet`, `publishablePublish`, `metafields`, etc.) ni la palabra
"borrador técnico". Todo eso se traduce a lenguaje natural en el preview y en las confirmaciones.
