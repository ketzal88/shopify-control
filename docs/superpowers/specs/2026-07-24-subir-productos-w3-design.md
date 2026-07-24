# W3 — `subir-productos` — Design Spec

- **Fecha:** 2026-07-24
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño. No implementado. Este doc es el contrato antes del plan. (Rev. 2 — incorpora el review adversarial de spec.)
- **Cliente piloto:** blunua (joyería de acero quirúrgico, COP/Colombia, Brain ID `LO4ob4dUxOggwTSlm07v`)
- **Depende de:** `2026-07-19-shopify-control-v1-design.md` (modelo de seguridad, §11), `2026-07-19-quantity-breaks-design.md` y `2026-07-22-regalo-gratis-bxgy-design.md` (patrón de write-class con techo), `2026-07-22-catalogo-widgets-design.md` (patrón de familia cosmética por `kind`+ruta).

---

## 1. Contexto y objetivo

W3 es el tercer write-win de shopify-control, listado como futuro en el v1 (§4, §13): **subir productos nuevos cumpliendo los estándares de la tienda, con `status: draft` por defecto y gate estructural.**

El cliente **no técnico** entrega un CSV con los datos crudos de sus productos nuevos y una carpeta con las fotos; W3 los valida contra la tienda y los estándares, **genera** la descripción + SEO de cada uno con el craft que ya existe, y los crea como **borradores inertes** en la tienda real. Opcionalmente, y detrás de un segundo gate de código, los publica.

### 1.1 Por qué W3 rompe el invariante del v1 (y por qué igual es tratable)

Todo lo construido hasta hoy —descripción, SEO, ofertas, widgets— opera sobre **productos que ya existen**. La arquitectura de seguridad se apoya en eso: `create-product`/`productCreate`/`productSet` están **denegados** (capa 1, `permissions.deny`) y **fuera de la allowlist** (capa 2, `ROOT_FIELD_ALLOWED`), y cada backup se ancla a un `productId` preexistente.

W3 tiene que **habilitar exactamente la operación que la arquitectura niega**. Lo que lo hace seguro es una asimetría: **un producto en `draft` es inerte** — ningún comprador lo ve hasta que alguien lo publica. El peligro no es *crear*, es *publicar*. Por eso W3 separa las dos cosas en **dos clases de write distintas, cada una con su gate**, y mantiene la creación siempre en `DRAFT`.

### 1.2 Decisiones tomadas (brainstorm 2026-07-24)

| # | Decisión | Elección |
|---|----------|----------|
| W3-D1 | Blast radius | **Borrador + publicar con gate de CÓDIGO** (no "solo borradores", no "solo-operador"). Publicar solo si pasa un gate estructural, nunca por ojo humano. |
| W3-D2 | Contenido | **El CSV trae datos crudos; W3 GENERA la copy** (descripción + SEO) reusando el craft de `mejorar-descripcion` (molde §3 + humanizer + `description_lint`). |
| W3-D3 | Formato del CSV | **Esquema nativo de export de Shopify** (85 columnas). No se inventa una plantilla Worker; se consume un subconjunto. Parser robusto al encoding. |
| W3-D4 | Imágenes | **URL si la fila la trae; si no, carpeta local por SKU.** Matching a nivel variante (carpeta-SKU, imagen-SKU). |
| W3-D5 | Skill | **Un solo skill `subir-productos`** (Enfoque A): crear y publicar gateados adentro. |
| W3-D6 | Undo | **Archivar** el borrador recién creado (no borrar), para NO reabrir `productDelete`. Ver §7.3. |
| W3-D7 | Precio | **`Variant Price`** (base, moneda de la tienda). Precios por mercado (Markets) fuera de v1. |

---

## 2. Alcance

**Dentro de W3 v1:**
- Skill `subir-productos`: CSV nativo + carpeta local de imágenes → borradores en la tienda real.
- Parser del CSV nativo (multi-fila por `Handle`, opciones→variantes, robusto al encoding).
- **Dedup contra la tienda viva** (por `Handle` y por `Variant SKU`): no crea lo que ya existe.
- Generación de descripción + SEO por producto, reusando el craft del v1.
- Resolución de imágenes URL-o-carpeta y subida a Shopify (staged upload) + attach por variante.
- Extensión de `backup_guard`: dos clases de write nuevas (`create`, `publish`) + `create-policy.json`.
- Preview sin jerga producto-por-producto, gate explícito, worklog, undo (archivar).

**Fuera de W3 v1 (futuro):**
- Precios por mercado / Shopify Markets (`Price / Colombia`, `Price / United States`).
- Imágenes desde Google Drive (solo carpeta local en v1).
- Editar/actualizar un producto existente vía CSV (W3 solo CREA; editar es `mejorar-descripcion` y los demás skills).
- Borrado real del producto (undo v1 archiva; ver §7.3).
- Metafields del catálogo (los ~30 `product.metafields.*` del export) más allá de los que el v1 ya escribe.
- Sanidad de precio por categoría (rango esperado por tipo de producto). v1 usa piso/techo simple.

---

## 3. Flujo del skill `subir-productos`

```
0. PASO 0 (obligatorio, idéntico a todos los skills)
   Identificar cliente activo → leer clients/{slug}/CLAUDE.md + store-standards.md →
   Shopify:get-shop-info vs connection.md. Si no coinciden, ABORTA.

1. RECIBIR
   El cliente indica, en lenguaje natural, dónde está el archivo y la carpeta de fotos.
   W3 traduce a dos paths locales. Sin jerga.

2. PARSEAR (§4)
   Lee el CSV nativo (encoding-robusto), agrupa filas por Handle → modelo de producto
   interno {handle, title, type, tags, options, variants[{sku, price, optionValues, barcode}],
   images[{src|null, sku, position, alt, variantSku}]}. Body(HTML) y SEO del CSV se
   GUARDAN como "lo que traías" (referencia en el preview), no se usan para crear.

3. VALIDAR + DEDUP (§4.3)  ⚠️ salvaguarda central
   (a) Estructural: título no vacío, ≥1 variante, precio numérico dentro de piso/techo,
       SKU presente, único dentro del lote, opciones consistentes.
   (b) DEDUP contra la tienda viva: search_products por Handle y por cada SKU. Si el
       producto YA existe, NO se crea; se marca "ya está en tu tienda, lo salto".
   (c) Reporta rechazados y salteados con motivo, en lenguaje natural.
   (d) Tope de lote: create-policy.maxProductsPerBatch.

4. GENERAR COPY (§6)
   Por cada producto que pasa: descripción + meta title + meta description con el molde
   canónico (store-standards §3), keywords por categoría (§4), humanizer y description_lint.
   No muestra ni crea nada que no pase el linter.

5. RESOLVER IMÁGENES (§5)
   Por slot de imagen: si la fila trae Image Src / Variant Image (URL https válida), se usa.
   Si no, se busca en la carpeta local por SKU. Se reportan las variantes sin foto.

6. PREVIEW (§8)
   Producto por producto (resumen navegable si son muchos), en el chat, sin jerga:
   título, precio, variantes, la descripción generada, cómo se ve en Google, y qué fotos
   matcheó / cuáles faltan. Marca cuáles pasarían el gate de publicación y cuáles no.

7. GATE crear
   "¿Creo estos N como borradores?" — sí/no explícito. Nada se escribe antes.

8. CREAR + REGISTRAR (§7.1)
   Por producto: productSet con status:DRAFT (+ opciones, variantes, precio, descripción,
   SEO, tags, media). Tras crear con éxito, escribe el registro de creación
   (kind:"create") con el id DEVUELTO, para habilitar el undo.

9. GATE publicar (opcional, §7.2)
   Solo los productos que pasan el gate de publicación (create-policy: imagen, longitud de
   descripción, precio sano, lint OK). "¿Publico estos M?" — sí/no. Los que no pasan quedan
   en borrador y se dice por qué.

10. WORKLOG + CONFIRMAR
    Append a clients/{slug}/worklog.md. "Listo, quedaron N como borradores (M publicados).
    Si querés deshacer, decime 'sacá los que subiste'."

11. UNDO (§7.3)
    "sacá los que subiste" → archiva (status:ARCHIVED) los productos cuyo id matchee un
    registro de creación reciente. Lleva su propio gate y preview, como todo write.
```

---

## 4. Parser del CSV nativo

### 4.1 Forma del archivo (verificada contra el export real de blunua)

- **85 columnas**, esquema nativo de export de Shopify. Columnas que W3 consume:
  `Handle`, `Title`, `Type`, `Tags`, `Option1/2/3 Name`, `Option1/2/3 Value`,
  `Variant SKU`, `Variant Price`, `Variant Barcode`, `Variant Grams`,
  `Image Src`, `Image Position`, `Image Alt Text`, `Variant Image`, `Status`.
  El resto (metafields, Google Shopping, Markets, `Body (HTML)`, `SEO *`) se **ignora para crear**;
  `Body (HTML)` y `SEO Title/Description` se retienen solo como "lo que traías".
- **Multi-fila por producto:** la primera fila de un `Handle` trae los campos de producto; las
  filas siguientes con el mismo `Handle` y `Title` vacío agregan variantes e imágenes. En el
  export real hay productos de 1 a 21 filas.
- **Encoding sucio:** el header del export real tiene mojibake (`Categor�a`, `Dise�o`). El parser
  **debe** intentar `utf-8-sig` y caer a `cp1252`/`latin-1` si falla, y normalizar. Asumir UTF-8
  limpio rompe el parseo.

### 4.2 Modelo interno (una sola fuente de verdad para los pasos siguientes)

Cada producto se reduce a un objeto plano:
```
{ handle, title, productType, tags[],
  options: [ {name, values[]} ],           # de Option1/2/3 Name/Value
  variants: [ {sku, priceCents, optionValues[], barcode, grams} ],
  images:  [ {url|null, localSku|null, position, alt, variantSku|null} ],
  csvBody, csvSeoTitle, csvSeoDescription   # referencia, NO se crean
}
```
Precio: se lee `Variant Price`, se normaliza a centavos enteros (§7 lo exige entero). Si viene
vacío o no numérico → rechazo estructural (no se inventa precio).

### 4.3 Validación y dedup (la salvaguarda contra duplicar el catálogo)

El archivo de prueba **es el catálogo completo (678 productos)**: correrlo sin dedup crearía 678
duplicados. Reglas:

- **Estructural (rechaza la fila, no el lote):** título presente; ≥1 variante; `priceCents` en
  `[minPriceCents, maxPriceCents]`; SKU presente; SKU único dentro del lote; cada variante con
  valores para todas las opciones declaradas.
- **Dedup contra la tienda viva:** para cada producto, `search_products` por `handle:<h>` y por
  cada `sku:<s>`. Si hay match, **no se crea** y se marca "ya existe". Handle y SKU son las dos
  claves naturales de identidad; se chequean las dos porque un cliente puede cambiar el handle
  pero repetir SKU, o viceversa.
- **Tope de lote:** `create-policy.maxProductsPerBatch`. Si el CSV trae más, se procesa en tandas
  y se avisa (nunca se saltea en silencio).
- **Reporte:** cada producto termina en un estado — `crear`, `ya-existe`, `rechazado:<motivo>` —
  y el preview lo dice en lenguaje natural.

> **El dedup es SOLO del skill; el guard no lo respalda** (ver §11). El único freno del lado del
> guard contra un runaway es `maxProductsPerBatch`. Es intencional (el guard no fetchea la tienda),
> pero hay que tenerlo presente dado el escenario de los 678 duplicados.

---

## 5. Resolución de imágenes

Contrato URL-o-carpeta (W3-D4), por slot de imagen:

1. **URL en la fila** (`Image Src` / `Variant Image`): si es `https://…` válida (misma validación
   `_ok_url` del guard), se pasa a Shopify por `productCreateMedia`/`productSet` con `originalSource`.
2. **Carpeta local por SKU**: si la fila no trae URL, se busca el archivo en la carpeta indicada,
   matcheando por SKU (carpeta `<SKU>/` o archivo `<SKU>.*`). Se sube por **staged upload**
   (`stagedUploadsCreate` → PUT de los bytes → `resourceUrl` a `productCreateMedia`).
3. **Sin match**: la variante queda sin foto. Se reporta en el preview; no bloquea la creación como
   borrador, pero **sí** cuenta para el gate de publicación (`requireImage`).

Matching a nivel variante: la imagen se asocia a la variante cuyo SKU coincide; las imágenes de
producto (sin `variantSku`) van al producto. `Image Position` ordena la galería.

> **Límite de v1:** solo carpeta LOCAL en la máquina de VS Code. Google Drive es futuro (W3-D4,
> §2). El staged upload de bytes locales es el único camino nuevo de plomería.

---

## 6. Generación de copy (reusa el craft, no lo reinventa)

W3 **no** puede invocar `mejorar-descripcion` tal cual: ese skill lee los 3 campos de un producto
**existente** y escribe sobre su id. En W3 el producto todavía no existe. Entonces W3 reusa el
**craft**, no el skill:

- Molde canónico de `store-standards §3` (título → hook → 3 beneficios → material/garantía → bloque
  GEO Q&A), keywords tejidas de `§4` por categoría, humanizer obligatorio.
- `description_lint.py` por CLI sobre el texto plano (materiales falsos, lujo-vacío, claims médicos,
  voseo, longitud, keyword, bloque GEO). **No se crea ni se muestra nada que no pase el linter.**
- La descripción y el SEO generados viajan **dentro del `productSet` de creación** (§7.1), no por un
  `update-product` aparte: el producto se crea ya con buena copy en un solo write.

Si el CSV traía `Body (HTML)`/`SEO`, se muestran en el preview como "lo que traías" para que el
cliente compare, pero **no** se usan para crear (W3-D2).

---

## 7. Extensión del modelo de seguridad (el corazón de W3)

W3 agrega **dos clases de write** a la taxonomía del guard, siguiendo el patrón de ofertas y
cosméticos: cada clase tiene su whitelist, su discriminador de backup por `kind`+ruta, y su función
propia. **El default sigue invertido: lo que no está explícitamente permitido, bloquea.**

### 7.0 Cambios en `permissions.deny` y en las listas del guard

- **`permissions.deny` (capa 1):** `create-product` **sigue denegado** — W3 no usa el tool
  `create-product` (limitado, sin variantes+media en un shot). W3 crea por `graphql_mutation`
  (`productSet`), que pasa por el guard. No se afloja la capa 1.
- **`ROOT_FIELD_ALLOWED` (capa 2):** se agregan `productset` y `productchangestatus`. Además se
  agregan a `PRODUCT_WRITE_ALLOWED` (si no, la rama de producto los bloquea por `fuera_de_alcance`),
  pero **solo** en conjunto con la restructura del router de §7.0.1, que los rutea por NOMBRE a su
  check. Agregarlos sueltos a `PRODUCT_WRITE_ALLOWED` sin rutearlos sería el fail-open descrito abajo.
- **`FORBIDDEN_MUTATIONS`:** `productdelete`, `publishablepublish/unpublish` y los `inventory*`
  **siguen bloqueados siempre**. W3 **no** reabre `productDelete` (por eso el undo archiva, §7.3).
  `productchangestatus` NO está en la blocklist hoy; se permite solo vía su check nuevo.

### 7.0.1 Restructura del router de `evaluate()` (obligatoria — sin esto el guard falla)

`productset` y `productchangestatus` **empiezan con `product`**, así que el router actual los mete a
todos en el mismo cubo `product_roots` → asunto `"cambios de producto"`, y después la rama de producto
bloquea todo lo que no sea `productupdate` (`fuera_de_alcance` contra `PRODUCT_WRITE_ALLOWED`). Dos
modos de falla que hay que evitar explícitamente:

- **Fail-closed:** si se agregan a `ROOT_FIELD_ALLOWED` pero no se rutean antes del bloqueo de
  `fuera_de_alcance`, la feature nunca funciona (todo create bloquea).
- **Fail-open (grave):** si se agregan a `PRODUCT_WRITE_ALLOWED` "para que pasen", un `productSet`
  de creación —que **no trae `id`**, así que `GID_RE.search` no lo ve— cae al `return "allow"` final
  de `evaluate()` (línea ~1505) y **crea un producto sin ningún chequeo**.

La restructura, dentro de la rama de producto de `evaluate()`:

1. **Una sola mutación de producto por documento:** `len(product_roots) == 1`, si no bloquea. Esto
   **reemplaza** la dependencia del contador de `asuntos` para separar dos `product*` entre sí (ver
   §10): el contador de asuntos NO distingue `productset` de `productchangestatus` porque los dos
   caen en el mismo asunto `"cambios de producto"`.
2. **Ruteo por NOMBRE de root field** (no por presencia de gid), desde `roots` (que
   `_root_mutation_fields` sí parsea aunque no haya id): `productset` → `_check_create`;
   `productchangestatus` → `_check_status_change`; `productupdate` → el camino de descripción/SEO.
3. El ruteo es **exhaustivo**: ningún `productset`/`productchangestatus` puede alcanzar el camino de
   campos de `productupdate` ni el `return "allow"` final. Lo que no se reconoce, bloquea.

### 7.1 Clase `create` — `_check_create(...)`

`productSet` **sin `id`** (un `productSet` con `id` es un UPDATE de un producto existente y queda
fuera de esta clase — se bloquea). El input **debe** venir por `variables` como JSON estructurado, no
inline en el query: el guard lo parsea como objeto (espejo de `_discount_inputs`/`_check_discount`).
Razón: `_top_level_keys`/`_product_input_keys` **colapsan** los objetos anidados, así que NO pueden
ver el `price` por variante dentro de `variants: [...]`; un input inline se bloquea por indescifrable.

Condiciones, todas obligatorias:

- **`status` PRESENTE y == `DRAFT`.** No alcanza "no es otro status": Shopify **defaultea a `ACTIVE`**
  cuando se omite `status`, así que un create sin `status` publicaría un producto vivo y rompería el
  invariante inerte del §1.1. El guard exige `status` explícito e igual a `DRAFT`; si falta o es
  otro, **falla cerrado**.
- **Alcance de campos del create:** las keys de primer nivel del input se limitan a un set cerrado
  apropiado para alta — `title`, `handle`, `descriptionHtml`, `seo`, `productType`, `tags`,
  `status`, `productOptions`, `variants`, `files`/`media`. Cualquier otra key (p. ej. algo que
  intente tocar `metafields` de plata, publicaciones a canales, etc.) bloquea.
- **Precio de cada variante en `[minPriceCents, maxPriceCents]`** (piso/techo de `create-policy`).
  Atrapa el `$0` y el error de tipeo grosero (`$5.000.000`); el error "sutil" ($56 vs $560) lo
  atrapa el preview + gate humano, no el guard (ver §11).
- **No publica:** el input no puede traer publicaciones a canales (eso es publicar, §7.2).
- **Sin backup previo** (asimetría con los otros writes): un create no tiene "valor viejo" que
  respaldar. El registro de creación se escribe **después** de crear (con el id devuelto), y es lo
  que habilita el undo — no un requisito previo. `_check_create` NO exige backup; gatea por
  status+campos+precio.

Tras el create, el skill escribe `clients/{slug}/backups/create/{newIdTail}-{ts}.json`:
```json
{ "kind": "create", "productId": "gid://shopify/Product/NEW", "handle": "...",
  "createdBy": "subir-productos", "ts": "2026-07-24T12:00:00" }
```

### 7.2 Clase `publish` — `_check_publish(...)` (dentro de `_check_status_change`)

`productChangeStatus` con status **destino** `ACTIVE`. `productChangeStatus` solo lleva el status
destino (no el origen), así que el check razona sobre lo que SÍ puede ver:

- **Destino == `ACTIVE`** (cualquier otro destino no es publicar).
- **Un solo producto por operación.**
- **El producto tiene un registro de creación (`kind:"create"`) reciente** — o sea, lo creó W3. Esto
  es lo que ata `publish` a un producto de W3 y no a cualquier producto de la tienda.
- **Requiere un registro `publish`** (`kind:"publish"`, ruta `backups/publish/`) fresco, que el skill
  escribe tras correr el gate de publicación (imagen presente, longitud de descripción ≥
  `requireDescriptionMinWords`, lint OK, precio sano). Es autoatestado por el skill — misma naturaleza
  que `description_lint` (advisory respecto del write). El guard aporta lo que SÍ puede ver
  (destino ACTIVE, producto creado por W3, uno a la vez, registro presente y fresco, `allowPublish`);
  la completitud del producto vivo la verifica el skill. Ver §11 (límite conocido, honesto).
- **`allowPublish` en `create-policy`**: kill-switch por cliente. Si es `false`, `_check_publish`
  bloquea siempre y W3 solo deja borradores.

> **Frescura (§7.4):** "reciente" para los registros `create`/`publish` usa `createRecordWindowHours`
> (default 72h), NO la ventana de 15 min de los backups del v1. El loop de W3 (crear → revisar muchos
> productos → publicar/undo) es humano y largo; 15 min lo haría inusable. La misma ventana larga vale
> para el undo (§7.3).

> **Choreografía de API a verificar en el plan:** hacer un producto `ACTIVE` no lo publica al canal
> Online Store si su publicación no está seteada. Se resuelve seteando la publicación Online Store
> **en el create** (dentro de `productSet`, sin canales exóticos) para que publicar sea solo el flip
> de status. Si el plan prueba que hace falta `publishablePublish`, ese tool NO se desbloquea sin su
> propio check acotado; hasta entonces sigue en `FORBIDDEN_MUTATIONS`.

### 7.3 Clase `undo` (archivar) — dentro de `_check_status_change`

`productChangeStatus` con destino **`ARCHIVED`**, **solo** si el id matchea un registro de creación
(`kind:"create"`) dentro de `createRecordWindowHours`. Un producto archivado es reversible y no borra
datos. Se elige archivar en vez de borrar a propósito: borrar exigiría **reabrir `productDelete`** (hoy
en la blocklist por buenas razones), y el riesgo de un delete gateado que se equivoque de id no
compensa la prolijidad de no dejar un draft archivado. Borrado real = futuro (§2), con su propio spec.

`_check_status_change` es la función única para `productChangeStatus`: acepta destino `ACTIVE` (publish,
con registro publish + registro create) o `ARCHIVED` (undo, con registro create). **Cualquier otro
destino bloquea** — no hay `*`→`DRAFT` ni transiciones sobre productos que W3 no creó.

### 7.4 `create-policy.json` (por cliente, lo lee el guard)

Mismo patrón que `deal-policy.json`. Fuente de verdad del techo, la lee el hook:
```json
{
  "maxProductsPerBatch": 50,
  "minPriceCents": 100,
  "maxPriceCents": 100000000,
  "allowPublish": true,
  "requireImage": true,
  "requireDescriptionMinWords": 40,
  "createRecordWindowHours": 72
}
```
Si falta el archivo, `_check_create` y `_check_publish` **fallan cerrado** (no se crea ni se publica),
igual que `deal-policy` para ofertas.

---

## 8. Preview y gate (sin jerga)

Hereda las reglas del v1 (§6.1): todo en el chat, texto plano, cero jerga, gate explícito sí/no.
Diferencias propias de W3:

- **Producto por producto**, pero navegable: si son muchos, muestra un índice ("12 productos listos,
  1 ya existe, 2 con problemas") y el detalle de cada uno bajo demanda o en bloque acotado. El cliente
  no aprueba lo que no vio.
- Cada producto muestra: nombre, precio, variantes (color/talla), la descripción generada, cómo se ve
  en Google, y el estado de fotos ("3 de 4 variantes con foto; falta la del color negro").
- Marca visualmente **cuáles se van a poder publicar** y cuáles quedan en borrador por qué (sin foto,
  descripción corta).
- **Dos gates separados:** uno para crear (borradores), otro para publicar. Nunca uno solo: crear es
  inerte, publicar es a la venta.
- **Lote parcial:** si falla a la mitad, se dice exactamente cuáles se crearon y cuáles no, y se ofrece
  retomar. Nunca estado ambiguo (misma regla que el lote de `mejorar-descripcion`).

---

## 9. Estructura de archivos nueva

```
.claude/skills/subir-productos/SKILL.md        ← el procedimiento
.claude/hooks/backup_guard.py                  ← + _check_create, _check_status_change (publish/undo),
                                                  + productset/productchangestatus ruteados por nombre (§7.0.1)
clients/{slug}/create-policy.json              ← techo de creación (nuevo, por cliente)
clients/_template/create-policy.json           ← scaffold para el próximo cliente
clients/{slug}/backups/create/                 ← registros de creación (kind:"create")
clients/{slug}/backups/publish/                ← registros de publicación (kind:"publish")
tests/test_create_guard.py                     ← pytest de las dos clases nuevas
```

El skill NO se toca por cliente (sirve a todos); `create-policy.json` pone el techo por cliente, igual
que `deal-policy.json`.

---

## 10. Testing / validación

- **pytest de `_check_create`:** bloquea `productSet` con `status:ACTIVE`; **bloquea con `status`
  ausente** (Shopify defaultea ACTIVE); bloquea con `id` presente (update disfrazado de create);
  bloquea input inline (no en `variables`); bloquea key fuera del set de create; bloquea precio bajo
  piso / sobre techo; permite el create DRAFT válido por `variables`; falla cerrado sin `create-policy.json`.
- **pytest de `_check_status_change` (publish/undo):** bloquea todo destino que no sea ACTIVE o
  ARCHIVED; bloquea publish sin registro `publish` fresco; bloquea publish sin registro `create`;
  bloquea publish con `allowPublish:false`; bloquea archive de un id sin registro `create`; bloquea
  registros fuera de `createRecordWindowHours`; permite el par correcto.
- **pytest anti-bypass (hereda la disciplina de BXGY/escalones):** un documento que mezcla un
  `productset` con un `productupdate`, o dos `product*` cualesquiera, **bloquea por la regla
  `len(product_roots) == 1` de §7.0.1** — NO por el contador de `asuntos`, que no separa dos `product*`
  entre sí (por eso la regla nueva es necesaria); un create con un `discountAutomaticDeactivate`
  adelante bloquea (asuntos mixtos); señuelos en `variables`; un `productSet` sin id que intenta caer
  al `return allow` final es interceptado por el ruteo por nombre.
- **Parser:** fixture = el export real (2MB, 678 productos). Tests: agrupa bien multi-fila; lee
  encoding sucio; dedup detecta los 678 como "ya existe" contra una tienda mock; rechaza precio no
  numérico.
- **Falso positivo del substring de `FORBIDDEN_MUTATIONS`:** el guard escanea `FORBIDDEN_MUTATIONS`
  como substring case-insensitive sobre `query + variables` (líneas ~1404-1407). Hasta ahora corría
  sobre writes chicos (descripción/SEO); el payload de create es un blob grande y libre (descripción
  generada, tags, URLs de media). Un payload que por casualidad contenga un token como `productdelete`
  o `inventoryactivate` como substring se bloquearía. **Falla cerrado** (seguro, no es agujero), y es
  improbabilísimo en copy de joyería en español ya pasada por lint+humanizer, pero el test del
  create-path debe confirmar que un payload generado realista no lo dispara.
- **End-to-end contra la dev store** (`Testing StandAlone Framework`), no contra blunua: crear 2-3
  borradores con variantes e imágenes locales, verificar por read-back, publicar uno, archivar (undo).

---

## 11. Límites conocidos y aceptados

- **El guard no puede verificar la completitud del producto VIVO al publicar.** No fetchea el producto;
  confía en el registro `publish` que escribe el skill tras correr el gate. Es la misma naturaleza que
  `description_lint` (advisory respecto del write, §11 del v1). Mitigación: el guard sí acota lo que ve
  (destino ACTIVE, producto creado por W3, uno a la vez, registro fresco, `allowPublish`), y el preview
  + gate humano ven el producto antes de publicar.
- **El dedup no tiene backstop en el guard.** Es 100% del skill (§4.3). El único límite del lado del
  guard contra un runaway de creación es `maxProductsPerBatch`. Aceptado (el guard no fetchea la tienda),
  pero listado por el escenario de los 678 duplicados.
- **Sanidad de precio: piso/techo, no rango por categoría.** El guard atrapa `$0` y el tipeo grosero,
  no el error "sutil" ($56 vs $560, ambos válidos). Ese lo atrapa el preview + gate humano. Rango por
  categoría es futuro (§2).
- **Undo archiva, no borra.** Deja un draft archivado en la tienda. Es el precio de no reabrir
  `productDelete`. Aceptado.
- **Solo carpeta local** (no Drive) y **precio base** (no Markets) en v1.
- **Autoatestación del registro:** como en ofertas, el skill escribe su propio registro. El guard valida
  lo que puede (forma, frescura, `kind`+ruta, ids), no la intención. El modelo de amenaza sigue siendo
  "el operador o el cliente se equivocan", no "un actor hostil con shell" (§15 del v1).

---

## 12. Fases de implementación (cada una es su propio plan)

Las tres fases son sustanciales (parser + fixture de 678; plomería nueva de staged upload; dos clases
de guard). **Cada fase se planifica y ejecuta por separado** — no un solo plan gigante.

1. **F1 — Parser + dedup + preview (sin escribir nada).** El valor y el riesgo más bajos primero: leer
   el CSV, validar, dedupear contra la tienda, generar copy, mostrar el preview. Termina sin un solo
   write. Testeable de punta a punta en seco.
2. **F2 — Clase `create` + imágenes.** `_check_create`, `create-policy.json`, staged upload, el create
   DRAFT real, el registro de creación, el undo (archivar). Es el write-win: borradores inertes.
3. **F3 — Clase `publish`.** `_check_publish`/`_check_status_change` (destino ACTIVE), el gate de
   publicación, el segundo gate del skill. Se puede diferir sin bloquear F2 (un cliente puede vivir
   creando borradores y publicando a mano en el admin).

---

## 13. Preguntas abiertas para el plan

- La choreografía exacta de `productSet` para variantes + opciones + media en un shot, y si publicar
  necesita `publishablePublish` además del flip de status (§7.2). Se resuelve contra la API real en el
  plan, con `graphql_schema`/`validate_graphql_codeblocks`.
- El formato exacto del matching de carpeta local por SKU (subcarpeta vs archivo; extensiones).
- Si `maxProductsPerBatch` = 50 y `createRecordWindowHours` = 72 son los números correctos para blunua.
