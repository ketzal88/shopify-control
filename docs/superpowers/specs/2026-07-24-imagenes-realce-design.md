# Imágenes: realce + adjuntar (W4-3) — Design Spec

- **Fecha:** 2026-07-24
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño (decisión de forma tomada; defaults del resto sujetos a veto). No implementado.
- **Cliente piloto:** blunua
- **Es:** el tercero de los tres features de W4.
- **Depende de:** `2026-07-24-subir-productos-w3-design.md` (F2: el camino de staged upload + `productSet.files`), `2026-07-19-shopify-control-v1-design.md` §11 (modelo de seguridad), `store-standards.md §7` (plantillas de imagen de marca).

---

## 1. Contexto y objetivo

La foto vende, sobre todo en joyería. Hoy la herramienta **adjunta** imágenes al crear productos (F2), pero no las **mejora**. W4-3 le da a la herramienta la capacidad de **tomar la foto REAL de un producto y realzarla con tratamiento de marca** (fondo limpio, colores de marca §7) y **adjuntarla** al producto.

### 1.1 Decisión de forma (tomada) e integridad

**Elegido: "realza la foto REAL + la adjunta"** (no "genera imágenes nuevas"). La razón es de **integridad**: una imagen generada por IA que no es el producto exacto **engaña al comprador** — inaceptable. W4-3 opera **sobre la foto real** (quitar/limpiar fondo, fondo de marca, encuadre, upscale), nunca inventa el producto. Esto es una **regla dura del skill** (§4): la imagen de salida tiene que derivar de la foto real del producto.

### 1.2 El corte de seguridad (por qué W4-3 toca el guard)

Adjuntar una imagen a un producto **que ya existe** es `productCreateMedia`, que **no está en la allowlist del guard** (bloquea por default). Para productos **nuevos**, F2 ya adjunta vía `productSet.files` (gateado por `_check_create`). Así que lo único nuevo en seguridad es una **clase de write `media`** para productos existentes: agregar SOLO imágenes, a un producto, con backup y undo.

---

## 2. Alcance

**Dentro:**
- Skill (cliente-facing) que realza la foto real de un producto y la adjunta (mejorar-fotos o similar).
- Realce vía Higgsfield sobre la foto real: `remove_background`, `outpaint_image` (fondo de marca), `upscale_image`, `generate_image` **con la foto real como referencia/base** (no from scratch).
- Clase de write **`media`** en el guard: `productCreateMedia` (solo IMAGE, un producto, backup, undo) + `productDeleteMedia` para el undo (solo un media id registrado).
- Para productos **nuevos**: sin cambio — F2 ya adjunta por `productSet.files`.
- Preview → gate → backup → escribir → undo, como todo write.

**Fuera (YAGNI):**
- **Generar imágenes nuevas** (lifestyle/on-model/escenas) que no derivan de la foto real: integridad. Diferido, y si vuelve, con reglas fuertes propias.
- Video / 3D (solo IMAGE).
- Editar/reordenar imágenes existentes, borrar las originales del cliente (solo AGREGA; el undo saca lo que agregó).
- Reemplazar la foto principal automáticamente (agrega; el cliente/operador decide el orden en el admin).

---

## 3. Mecanismo

- **Realce (Higgsfield, no toca Shopify):** partir de la foto real (URL de la imagen actual del producto, leída con `graphql_query`) → `remove_background`/`outpaint_image` con paleta §7 → `upscale_image`. Sale una imagen realzada, hosteada por Higgsfield (URL) o descargada.
- **Adjuntar:** `productCreateMedia(productId, media: [{ originalSource: <url|staged>, mediaContentType: IMAGE, alt }])`. Si la imagen realzada es una URL https pública → `originalSource` directo. Si es local (bytes) → staged upload (el camino de F2) → `resourceUrl`.
- **Undo:** `productDeleteMedia(productId, mediaIds: [<el que se agregó>])` — solo el media id que la herramienta registró.

---

## 4. Regla de integridad (dura, del skill)

- La imagen de salida **deriva de la foto real** del producto (fondo/encuadre/calidad), **nunca** se genera un producto que no es. Prohibido: cambiar la forma, el color real del producto, agregar piezas que no están, "mejorar" el producto en sí.
- El guard **no puede ver la imagen** (no verifica integridad) → es responsabilidad del skill + el gate humano (el cliente ve el antes/después y aprueba). El realce es acotado por diseño (tratamiento de fondo/calidad), no generación de producto.
- **Preferir transformaciones ACOTADAS** (`remove_background`, `outpaint_image`, `upscale_image`) sobre `generate_image` con la foto de referencia — este último es el camino de mayor "drift" (más riesgo de alejarse del producto real). Si se usa, con el gate humano mirando el antes/después.
- Sin jerga; registro por `store-standards §2`; el preview muestra **antes vs después** de la foto.

> ⚠️ **Dependencia sin definir (MEDIUM del review):** `store-standards §7` (plantillas de imagen de marca) es hoy un **placeholder** — solo los 4 colores hex y "minimalista, fondo limpio". El realce de marca cuelga de §7, así que **definir §7 (fondo, encuadre, cómo aplican los colores) es un deliverable del plan**, si no el "realce de marca" queda indefinido.

---

## 5. Guard — la clase `media`

`productCreateMedia` y `productDeleteMedia` no están en la allowlist. Se agregan con checks propios, **fail-closed**. ⚠️ **Tres puntos críticos (del review adversarial):**

### 5.1 Colisión de substring: `productdelete` ⊂ `productdeletemedia` — HAY que tocar `FORBIDDEN_MUTATIONS`
`FORBIDDEN_MUTATIONS` contiene `"productdelete"`, y el scan de la blocklist es por **substring** sobre el query lowercased (`if mutation in low`), así que `"productdelete" in "productdeletemedia"` → **True**: `productDeleteMedia` queda force-bloqueado ANTES de cualquier check. Falla cerrado (el undo nunca andaría), pero reabrir el delete obliga a **modificar la línea más sensible del guard**: cambiar el match de `productdelete` a **word-boundary** (`\bproductdelete\b`, que NO matchee `productdeletemedia`) o special-casear la colisión. Misma clase que las que los autores ya cuidan (`publishableunpublish` vs `publishablepublish`, `inventorySetOnHandQuantities` vs `inventorySetQuantities`). `productCreateMedia` **no** colisiona (`productcreate` no está en la blocklist); solo el delete.

### 5.2 Router: rutear media POR NOMBRE (precedente W3 §7.0.1, NO publishablePublish)
Media **empieza con `product`**, así que hoy cae automáticamente en `product_roots` → asunto `"cambios de producto"`. El precedente correcto NO es `publishablePublish`/`stagedUploadsCreate` (que no empiezan con product) sino la **restructura del router de W3 §7.0.1**.
- **Fail-open que esto cierra:** `productCreateMedia(P) + productUpdate(P, descriptionHtml)` en un doc → hoy daría `asuntos=["cambios de producto"]` (len 1, no bloquea), `create_or_status` vacío (la regla `len(product_roots)==1` no dispara), `"productupdate" in low` → el field check ve `{id, descriptionHtml}` → **ALLOW**, y el `productCreateMedia` se ejecuta SIN el check de IMAGE/source/tope. Decoy fail-open real.
- **Fix:** (a) rutear `productcreatemedia`→`_check_media_create` y `productdeletemedia`→`_check_media_delete` **por nombre, ANTES** del camino de campos de `productupdate`; (b) **excluir** media del bucket `product_roots` y darle su propio asunto `media` (si no, un media solo doble-contaría a `len(asuntos)==2` y moriría fail-closed); (c) **`len(media_roots) == 1` — bloquear si hay más de una mutación de media en el documento.** ⚠️ Sin esto, un asunto `media` único NO separa `productCreateMedia` de `productDeleteMedia` entre sí: `productCreateMedia(P) + productDeleteMedia(P, originales)` → `asuntos=["media"]` (len 1, pasa), el router despacha una sola rama y la **delete corre SIN `_check_media_delete`** → borra las fotos originales del cliente montada en un create válido. Es la regla `len(product_roots)==1` de W3 §7.0.1 punto 1, que el precedente marca como **obligatoria** por esta misma razón (el contador de asuntos no distingue dos mutaciones de la misma familia). Los checks per-mutación (§5.3/§5.4 "un solo X por doc") NO lo agarran — cada uno solo cuenta lo suyo.

### 5.3 `_check_media_create` (productCreateMedia)
`allowMedia:true` en policy; un solo `productCreateMedia` por doc; el `media` es una **referencia a variable** (no inline `[`); lista de **solo `mediaContentType: IMAGE`** (VIDEO/EXTERNAL_VIDEO/MODEL_3D → block); `productId` leído **por clave, string-aware** (`_top_level_args`/`_productid_arg`, NO `GID_RE` suelto), único; `originalSource` https válido (`_ok_url`) o staged `resourceUrl`; tope `maxImagesPerCall`; **registro de creación** (ver §5.5). `CreateMediaInput` = `{alt, mediaContentType, originalSource}` (confirmar con `graphql_schema`) — sin campo peligroso oculto.

### 5.4 `_check_media_delete` (productDeleteMedia — el undo, la parte destructiva)
`productDeleteMedia(productId, mediaIds: [ID!])` toma una **lista**. Reglas:
- Un solo `productDeleteMedia` por doc; `productId` por clave string-aware.
- **Cada `mediaId`** tiene que estar en el registro de media que la herramienta **creó** para ese producto (§5.5). **Iterar TODOS** (lección validate-all de discount/BXGY): si ALGUNO no está registrado → **block**. Esto es lo que impide borrar las fotos **ORIGINALES** del cliente — solo se pueden borrar los ids que la herramienta agregó.
- Sin registro / id no registrado → block (fail-closed).

### 5.5 Registro de media en DOS FASES (los ids no existen antes de crear)
Los media ids solo existen DESPUÉS de que `productCreateMedia` devuelve, así que el pre-write backup no puede contenerlos. Modelado en el `kind:"create"` de W3 (que se escribe DESPUÉS del éxito):
- **Pre-write:** registro `kind:"media"` con el `productId` (habilita el create-gate + marca el punto de undo).
- **Post-write:** tras el `productCreateMedia` OK, el skill lee los **media ids devueltos** y los suma al registro. `_check_media_delete` matchea contra ESOS ids, no contra un conteo.

### 5.6 Policy
**`media-policy.json` propio** (chico) — NO reusar `deal-policy.json` (es el techo de PLATA; mezclarlo es un smell). Claves: `allowMedia` (flag), `maxImagesPerCall`, y **`mediaRecordWindowHours`** (default 72, como el `createRecordWindowHours` de W3 — si el delete-gate usara los 15 min de `RECENT_WINDOW_SECONDS`, "sacá esa foto" una hora después fallaría cerrado y se sentiría roto; fail-closed igual, es usabilidad). Ausente/false → fail-closed (no se adjunta).

### 5.7 Docs de alcance a actualizar en lockstep
Una clase de write nueva (`media`) obliga a actualizar `CLAUDE.md` regla 5 y `store-standards §8` (que hoy enumeran texto/ofertas/estilo y dicen "NUNCA" lo demás), o el guard/skill diverge del alcance declarado.

---

## 6. Flujo del skill

```
0. PASO 0 — confirmar cliente + tienda (get-shop-info vs connection.md), como todo write.
1. IDENTIFICAR el producto (search_products; si hay +1, preguntar).
2. LEER la foto actual (graphql_query media/images del producto).
3. REALZAR con Higgsfield sobre la foto real (fondo de marca §7, upscale). Regla §4.
4. PREVIEW — antes vs después de la foto, en el chat. Sin jerga.
5. GATE — "¿la agrego a tu producto? sí/no".
6. BACKUP — kind:"media" (productId + descripción de lo que se agrega) antes de escribir.
7. ESCRIBIR — productCreateMedia (IMAGE). Registrar el media id devuelto (para el undo).
8. WORKLOG + CONFIRMAR — "listo, la foto nueva está en tu producto. Para sacarla, decime 'sacá esa foto'."
9. UNDO — productDeleteMedia del id registrado.
```

Productos **nuevos** (subir-productos, F2): el realce se puede sumar ahí en el mismo `productSet.files`, sin `productCreateMedia` — es el camino ya gateado.

---

## 7. Testing

- **pytest de `_check_media_create`:** permite `productCreateMedia` de una IMAGE con url https + backup `media` + productId único + allowMedia; bloquea VIDEO/3D; bloquea sin backup `media`; bloquea `allowMedia:false`/ausente (fail-closed); bloquea inline (no variable); bloquea > `maxImagesPerCall`; bloquea productId ausente/múltiple; bloquea mezclado con otra mutación (asuntos).
- **pytest de `_check_media_delete`:** permite borrar un media id registrado en un backup `media` reciente; bloquea un delete de un id NO registrado (no borra fotos originales del cliente); bloquea si ALGUNO de la lista `mediaIds` no está registrado (iterar todos); bloquea sin backup propio.
- **pytest `len(media_roots) == 1` (el residual del re-review):** `productCreateMedia(P) + productDeleteMedia(P, originales)` en un doc → **block** (si no, la delete correría sin `_check_media_delete` montada en el create). Este es el test que cierra el fail-open destructivo.
- **Regresión:** toda la suite (guard de ofertas/productos/combos/descripción) verde; `FORBIDDEN_MUTATIONS`/`permissions.deny` intactos.
- **e2e manual (operador, dev store):** realzar la foto de un producto, adjuntar, verificar en el admin, sacar (undo). Higgsfield real.

---

## 8. Riesgos y límites
- **Integridad no verificable por código:** el guard no ve la imagen; el realce-no-genera es regla del skill + gate humano. Aceptado (el modelo de amenaza es el operador/cliente se equivocan, no un actor hostil).
- **`productDeleteMedia` reabierto:** acotado al undo de ids registrados; un delete arbitrario de fotos del cliente bloquea. Es la misma disciplina que `publishablePublish` (reabrir con check estrecho).
- **Higgsfield:** dependencia externa; si no está disponible, el skill lo dice y no adjunta nada.
- **Costo:** generar/realzar imágenes cuesta (Higgsfield); no es un problema de seguridad, pero el skill no realza en lote sin gate.

## 9. Preguntas abiertas para el plan
- La forma exacta de `productCreateMedia`/`productDeleteMedia` y `CreateMediaInput`/`mediaContentType` (confirmar con `graphql_schema`).
- **Resuelto (§5.6):** policy es un `media-policy.json` propio (no `deal-policy.json` ni `create-policy.json`).
- Qué tools de Higgsfield exactos para "fondo de marca" (remove_background + outpaint vs generate con referencia) — decidir en el plan con una prueba.
