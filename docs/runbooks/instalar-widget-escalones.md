# Runbook — Instalar el widget de escalones en el tema

**Qué es:** el bloque `widget/worker-escalones.liquid` que muestra en la ficha del producto la
escalera "Llevá más y ahorrá" (M2). Lee el metafield `worker.deal` que ya escribe el skill
`armar-escalones`.

**Por qué es manual (y no lo hace Claude):** escribir archivos de tema está bloqueado por diseño
—tanto por `backup_guard` (no está en la whitelist) como por el propio connector (solo permite
temas no publicados, nunca el live)—. Por eso el widget se **pega a mano una vez por cliente**
(spec §4.1, decisión E4). Claude escribe el código; el operador lo instala.

> **No toca ningún archivo del tema.** Es un bloque **Custom Liquid** que se agrega desde el editor,
> no un `themeFilesUpsert`. Sacarlo es borrar el bloque, sin rastro.

---

## Requisitos previos

1. **Que exista una oferta** en algún producto (metafield `worker.deal` con `tiers`). Hoy hay una
   viva en la dev store *Testing StandAlone Framework* → **The Multi-managed Snowboard** (2+ →10%,
   3+ →20%), ideal para la primera prueba.
2. **Que Liquid pueda leer el metafield.** En Shopify moderno `product.metafields.worker.deal` es
   legible desde el tema sin más. Si al previsualizar el widget **no aparece** (y la consola no tira
   error de JS), es que el metafield no está expuesto a Liquid: creá la **definición** del metafield
   una sola vez (setup, operador):
   - Admin → *Settings → Custom data → Products → Add definition*
   - Namespace/key: `worker.deal` · Type: **JSON** · (no hace falta nada más)
   - Esto es lo que §4.1 anticipa; `metafieldDefinitionCreate` es setup-only y operador-only (§9.1).

---

## Instalación (editor de temas)

1. Admin → **Online Store → Themes → Customize** (sobre el tema que quieras; probá primero en una
   **copia**, no en el live).
2. En el selector de plantilla arriba, elegí **Products → Default product** (o la plantilla del
   producto con la oferta).
3. En la columna de la ficha, ubicá el bloque **"Buy buttons"** (el que trae *Agregar al carrito*).
   Encima de él: **Add block → Custom Liquid**.
4. Pegá **todo** el contenido de [`widget/worker-escalones.liquid`](../../widget/worker-escalones.liquid)
   en el campo del bloque.
5. Arrastrá el bloque para que quede **inmediatamente arriba** de *Agregar al carrito*.
6. **Save.**

> **Límite de tamaño (§4.1):** el campo Custom Liquid tiene un tope. El widget está pensado para
> entrar **≤ 20 KB** sin minificar. Si el editor rechaza el pegado por tamaño, el fallback es alojar
> el JS como **asset nuevo** del tema (subir un archivo, no editar uno existente) y dejar en el
> bloque solo el preámbulo + un `<script src>`.

---

## Verificación (obligatoria — no se testea en la tienda del cliente, §13.3)

Sobre el producto con la oferta, en el **preview** del editor:

- [ ] El widget **aparece** arriba de *Agregar al carrito*, con una fila por escalón.
- [ ] El escalón destacado (el del `highlight`) lleva el badge **MÁS ELEGIDO**.
- [ ] Los **totales por escalón** coinciden al **centavo** con lo que después cobra el carrito.
      (Ojo: el widget redondea por unidad, igual que Shopify — ver la "lección del centavo" en el
      spec §14. Si ves 1¢ de diferencia, es bug, no redondeo.)
- [ ] La **barra de progreso** dice "Sumá N más → X%" y en el último escalón se llena con
      "✓ Ahorro máximo" (no desaparece).
- [ ] El botón **canta cantidad y total**: `Llevar 2 · $…`.
- [ ] Click en "Llevar 2" → el carrito queda con **exactamente 2** (no suma sobre lo que hubiera) y
      el descuento del 10% aplicado.
- [ ] En un viewport de **390px**, el widget colapsa al escalón elegido + "Ver los demás", y el
      botón de comprar queda **arriba del pliegue**.
- [ ] En un producto **sin** oferta, el widget **no** aparece (ni un hueco).

> El botón nativo *Agregar al carrito* del tema **sigue existiendo** debajo del widget: el bloque
> Custom Liquid no puede quitarlo. El botón "inteligente" (el que fija cantidad + total) es el del
> widget.

---

## Estado v1 y pendientes conocidos

- **Variantes:** el widget v1 usa **una sola variante** para las N unidades del escalón (la
  disponible por defecto). Los **N selectores mezclables** de §4.6 —elegir color distinto por
  unidad— quedan como mejora. Para productos de variante única (el caso más común de blunua) no
  cambia nada: no se renderiza ningún selector.
- **Redirección al carrito:** al confirmar, el widget redirige a `/cart`. Si el tema usa un cart
  drawer AJAX, puede preferirse refrescar el drawer en vez de navegar; es un ajuste por-tema, no
  bloqueante.
- **Estrategia `codes`:** implementada (redirige a `/discount/{code}`), pero hoy blunua corre en
  `automatic`, así que esa rama no se ejercita todavía.
