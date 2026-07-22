---
name: generar-builder-escalones
description: Genera el constructor visual de escalones para que el cliente arme su oferta (producto, escalones, look) en una página y después la pegue en el chat. Produce un archivo HTML autocontenido con los productos y el techo del cliente ya adentro; no escribe nada en Shopify. Usar cuando el cliente pide armar la oferta de forma visual, "un constructor", "una pantalla para armar la oferta", o cuando el operador quiere entregarle el builder.
---

# Generar el builder visual de escalones

Arma el archivo HTML que el cliente abre para configurar su oferta de "llevá más y ahorrá"
visualmente. **No escribe nada en la tienda.** El cliente configura, copia un texto y lo pega en el
chat; ahí recién `armar-escalones` lo aplica por el camino guardado.

## Paso 0 — Confirmar cliente y tienda (obligatorio)

Igual que `armar-escalones`: determiná el cliente activo, leé su `CLAUDE.md` + `store-standards.md` +
`deal-policy.json`, y verificá con `Shopify:get-shop-info` que el connector apunta a la tienda del
cliente. Si no coinciden, avisá al operador y no sigas: el builder lleva los productos de la tienda
adentro, así que generar contra la tienda equivocada mostraría el catálogo de otro.

## Qué hornea adentro (por sesión, con datos frescos)

1. **Productos** — `Shopify:search_products` (activos). Por cada uno, armá el objeto que el builder
   espera:
   ```json
   { "id": "gid://shopify/Product/999", "title": "Anillo NEXO",
     "unitPriceCents": 8900000, "imageUrl": "https://cdn.shopify.com/...",
     "moneyFormat": "${{amount_no_decimals_with_comma_separator}}",
     "variants": [ { "id": "gid://shopify/ProductVariant/1", "title": "Default Title",
                     "price": 8900000, "available": true } ] }
   ```
   `unitPriceCents`/`price` en **centavos** (enteros). `moneyFormat` es `shop.money_format` de
   `get-shop-info`/la tienda (COP suele ser `${{amount_no_decimals_with_comma_separator}}`).
2. **Techo** — `clients/{slug}/deal-policy.json` tal cual (el objeto con `maxDiscountPct`,
   `maxTiers`, etc.).
3. **Render real** — el contenido de `widget/render/worker-render.js` (fuente única).
4. **CSS del widget** — el bloque `<style>…</style>` de `widget/worker-escalones.liquid` (para que el
   preview se vea igual que la ficha).
5. **Lógica del builder** — el contenido de `widget/escalones-builder.logic.js`.

## Armar el archivo

Tomá `widget/escalones-builder.template.html` y reemplazá los slots:

| Slot | Con |
|---|---|
| `__PRODUCTS_JSON__` | el array de productos (JSON) |
| `__CEILING_JSON__` | el `deal-policy.json` (JSON) |
| `__RENDER_JS__` | el contenido de `worker-render.js` |
| `__RENDER_CSS__` | el `<style>` de `worker-escalones.liquid` (sin las etiquetas `<style>`) |
| `__BUILDER_LOGIC__` | el contenido de `escalones-builder.logic.js` |

Escribí el resultado en `clients/{slug}/escalones-builder.html` y decile al cliente que lo abra
(doble click). En lenguaje natural, sin jerga:

> *"Te dejé una pantallita para armar tu oferta a ojo. Abrila, elegí el producto y cuánto ahorran, y
> cuando te guste cómo se ve, copiá el texto que te da abajo y pegámelo acá. Yo la reviso y la activo."*

## Lo que NO hace

- **No escribe en Shopify.** Ni descuentos, ni metafields. Solo genera el archivo.
- **No es de confianza.** Cuando el cliente pegue la config, `armar-escalones` la **revalida** contra
  el techo (no confía en lo que venga del builder). Ver la sección "Config del builder" de
  `armar-escalones`.
- No incluye tokens ni credenciales: es HTML estático que corre en el browser del cliente.

## Mantener sincronizado

`__RENDER_JS__` y `__RENDER_CSS__` salen de los archivos reales del widget, así que el preview del
builder **siempre** coincide con la ficha. Si el widget cambia, el próximo builder que generes toma
la versión nueva sola. `DEFAULT_STYLE` de `worker-render.js` tiene que seguir igual al `<style>` del
`.liquid` (ver la nota en ambos archivos).
