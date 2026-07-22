# Instalar los 9 bloques de contenido (operador)

Cada uno es un bloque Custom Liquid que se pega **una vez**. No se edita el tema. Los que son de
producto van en la plantilla de **producto**; los de tienda, en el **layout** (`theme.liquid`).

| Bloque | Archivo | Dónde | Aparece si… |
|---|---|---|---|
| Tabla de talles | `worker-sizechart.liquid` | ficha | el producto tiene `worker.sizechart` |
| Lista de beneficios | `worker-benefits.liquid` | ficha, cerca del precio | tiene `worker.benefits` |
| Pasos de uso | `worker-steps.liquid` | ficha | tiene `worker.steps` |
| Comparación con otros | `worker-compare.liquid` | ficha | tiene `worker.compare` |
| Antes y después | `worker-beforeafter.liquid` | ficha | tiene las 2 imágenes |
| Galería de fotos | `worker-gallery.liquid` | ficha | tiene `worker.gallery` |
| Quedan pocas | `worker-lowstock.liquid` | ficha, cerca del precio | hay tracking de stock y queda poco |
| Barra de anuncios | `worker-announce.liquid` | **layout** (arriba de todo) | la tienda tiene `worker.announce` |
| Video flotante | `worker-video.liquid` | **layout** (antes de `</body>`) | la tienda tiene `worker.video` |

## Instalar (patrón común)

**Los de ficha:** Online Store → Themes → Customize → plantilla de producto → **Add block → Custom
Liquid** → pegar el archivo → ubicarlo (los de "cerca del precio" arriba del botón; el resto donde
prefieras) → **Save**.

**Los de tienda (barra de anuncios y video):** ⋯ → Edit code → `layout/theme.liquid` → pegar el
contenido (la barra bien arriba, el video antes de `</body>`) → **Save**. O un Custom Liquid a nivel
global si el tema lo permite.

## Verificar
Cargá el dato con el skill correspondiente (`poner-tabla-talles`, `poner-galeria`, etc.) y abrí el
producto / la tienda. Sin dato, el bloque no aparece (ni un hueco).

## Sacar
No se toca el tema. El cliente pide "sacá la galería del [producto]" / "sacá la barra de anuncios" y el
skill escribe el vacío por el camino auditado.

## Notas
- **Imágenes** (galería, antes/después): tienen que estar hospedadas en https (CDN de Shopify u otro).
- **Quedan pocas**: solo se ve si el tema expone el stock real; si está oculto, no aparece (por diseño).
- **Video**: acepta YouTube o un .mp4 hospedado (https).
