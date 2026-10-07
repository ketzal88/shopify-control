---
name: mejorar-fotos
description: Realza la foto REAL de un producto de Shopify con el tratamiento de marca (fondo limpio de la paleta, encuadre, más calidad) y la adjunta al producto. Muestra un antes/después, pide confirmación, guarda backup y permite sacar la foto agregada. Nunca inventa el producto: parte siempre de la foto real. Usar cuando el cliente pide mejorar la foto de un producto, ponerle un fondo lindo, o subir la calidad de una imagen.
---

# Mejorar fotos (realce de la foto real + adjuntar)

Skill cliente-facing que **toma la foto real** de un producto y la **realza con el tratamiento de
marca** (fondo limpio de la paleta §7, encuadre, calidad) usando Higgsfield, y la **adjunta** al
producto. Solo AGREGA una foto; el cliente decide el orden en su tienda. Es un write, con todo el
protocolo (preview → gate → backup → escribir → undo).

> **Regla de integridad (dura, no negociable):** la imagen de salida **deriva de la foto REAL** del
> producto — fondo, encuadre, calidad. **Nunca** se cambia la forma, el color real de la pieza, ni
> se agregan elementos que no están. Una imagen que no es el producto exacto **engaña al comprador**:
> inaceptable. Preferí las transformaciones ACOTADAS (`remove_background`, `outpaint_image`,
> `upscale_image`) sobre `generate_image` con referencia (más "drift"). El guard no ve la imagen —
> la integridad es responsabilidad de este skill + el gate humano (el cliente ve el antes/después).

## Reglas duras
- **Solo agrega imágenes IMAGE, a UN producto, por el camino permitido.** El adjuntar va por
  `Shopify:graphql_mutation` con `productCreateMedia` (solo `mediaContentType: IMAGE`). Nunca video
  ni 3D. El guard lo enforcea: si mandás otra cosa, o más de `maxImagesPerCall`, o sin registro, te
  bloquea.
- **El undo saca SOLO lo que agregó.** Sacar una foto es `productDeleteMedia` **del media id que la
  herramienta registró** al agregarla. Nunca se borran las fotos originales del cliente (el guard
  bloquea borrar un id que no está en el registro de la herramienta).
- **Higgsfield es una dependencia externa.** Si no está disponible, decilo en natural y no adjustes
  nada; no inventes una imagen ni sigas sin el realce.
- **Sin jerga con el cliente:** "foto", "fondo", "quedó más nítida"; nunca "productCreateMedia",
  "media id", nombres de campo ni de herramienta.
- **Registro** por `clients/{slug}/store-standards.md §2`; **humanizer** antes de todo texto de cliente.
- **Todo write lleva el protocolo:** confirmar tienda → identificar → leer la foto → realzar →
  preview antes/después → gate → registro `media` (pre-write) → escribir → registrar el id devuelto
  (post-write) → confirmar. El undo también es un write, con su propio gate.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)
La sesión se abre en la RAÍZ del repo, así que el contexto del cliente NO se carga solo.
1. Identificá el cliente y leé `clients/{slug}/AGENTS.md`, `clients/{slug}/store-standards.md` (sobre
   todo **§7**, la plantilla de imagen de marca) y `media-policy.json`.
2. Verificá con `Shopify:get-shop-info` contra qué tienda está conectado el connector.
3. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ** y avisá al operador.
   `switch-shop` es decisión del operador, no tuya.

## Flujo

1. **IDENTIFICAR el producto.** `Shopify:search_products` por lo que dijo el cliente. Si hay más de
   uno posible, preguntá cuál. Guardá su `id` (gid del producto).

2. **LEER la foto actual.** `Shopify:graphql_query` de las imágenes/media del producto (`media` /
   `images`). Tomá la URL de la foto principal (la foto REAL de la que se parte).

3. **REALZAR con Higgsfield (sobre la foto real, no toca Shopify).** Aplicá la plantilla de marca de
   `store-standards §7`, preferentemente con transformaciones acotadas:
   - `remove_background` — cutout de la pieza real.
   - `outpaint_image` — fondo liso de la paleta §7 (uno de los 4 colores), con aire y encuadre
     centrado.
   - `upscale_image` — subir calidad/resolución.
   Respetá la **regla de integridad**: fondo/encuadre/calidad, nunca el producto en sí. Si la foto
   local hay que subirla a Shopify después, usás el staged upload de F2 (`stagedUploadsCreate`) para
   obtener un `resourceUrl` https; si Higgsfield ya te da una URL https pública, usala directo.

4. **PREVIEW — antes vs después.** Mostrá en el chat la foto original y la realzada, lado a lado o
   una arriba de otra, sin jerga: "así está hoy" / "así quedaría". Que el cliente vea que es **la
   misma pieza**, mejor presentada.

5. **GATE.** Preguntá explícito, sí/no: *"¿La agrego a tu producto?"*. Solo seguís con un sí.

6. **REGISTRO `media` (pre-write, antes de escribir).** Escribí
   `clients/{slug}/backups/media/{idTail}-{YYYYMMDD-HHMMSS}.json` con
   `{"kind":"media","productId":"gid://…","note":"foto realzada","ts":"<ISO>"}`. El guard exige este
   registro para dejar adjuntar; y marca el punto de undo.

7. **ESCRIBIR — adjuntar la foto.** Validá con `Shopify:validate_graphql_codeblocks` y corré
   `Shopify:graphql_mutation` con `productCreateMedia(productId: $pid, media: $m)`, con `$m` en
   `variables` (no inline): `[{ "mediaContentType": "IMAGE", "originalSource": "<url https|staged>",
   "alt": "<texto alt>" }]`. **Siempre `IMAGE`**, `originalSource` https. Leé del resultado el/los
   **media id** que devolvió (`media { id }`).

8. **REGISTRO post-write.** Sumá esos media ids al registro `media` del paso 6
   (`{"mediaIds":["gid://shopify/MediaImage/…"]}`). Sin esto no vas a poder sacar la foto después: el
   undo solo puede borrar ids que estén en el registro (así nunca toca las fotos originales del
   cliente).

9. **WORKLOG + CONFIRMAR.** Append a `clients/{slug}/worklog.md`:
   `## YYYY-MM-DD [write] mejorar-fotos — foto realzada agregada al producto {id}; backup: backups/media/…`.
   Al cliente, en natural: *"Listo, la foto nueva ya está en tu producto. Si querés sacarla, decime
   'sacá esa foto'."*

## Sacar la foto (undo)
Su propio gate. Después `Shopify:graphql_mutation` con `productDeleteMedia(productId, mediaIds: [<el
id registrado>])` — **solo** el media id que quedó en el registro `media`. Si el cliente pide sacar
una foto que la herramienta no agregó, no la toques: decile en natural que esa no la subiste vos y
que no la vas a borrar (podría ser una foto original suya). Anotá el undo en el worklog.

## Productos nuevos
Si el producto **todavía no existe** (se está subiendo con `subir-productos`, F2), el realce se suma
ahí en el mismo `productSet.files` del alta — no hace falta `productCreateMedia`. Ese es el camino ya
gateado por `_check_create`.

## Si algo no está disponible
- **Higgsfield caído / sin acceso:** decilo en natural ("ahora no puedo mejorar la foto, lo reviso") y
  no adjuntes nada.
- **Adjuntar no habilitado** (`allowMedia:false` o sin `media-policy`): el guard lo bloquea; decile al
  cliente que agregar fotos todavía no está disponible y anotalo para el equipo. No fuerces otro camino.

## Nota interna
Nunca nombres frente al cliente el comando, los nombres de campo (`productCreateMedia`, `mediaId`,
`mediaContentType`, etc.) ni las herramientas. Todo se traduce a lenguaje natural en el preview y las
confirmaciones.
