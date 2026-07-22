# Instalar Cuenta regresiva y Barra de envío gratis (operador)

Dos bloques Custom Liquid, cada uno se pega **una vez**. No se edita el tema.

## 1. Cuenta regresiva (`worker-countdown.liquid`) — en la ficha

1. **Online Store → Themes → Customize** → plantilla de **producto**.
2. Cerca del precio o de la oferta: **Add block → Custom Liquid**.
3. Pegá todo `widget/worker-countdown.liquid`. **Save**.

Aparece si el producto (o la tienda) tiene una cuenta regresiva cargada. Cuenta hasta la fecha real;
al vencer muestra el texto de vencido o se oculta. Se puede cargar por producto o para toda la tienda.

## 2. Barra de envío gratis (`worker-freeship.liquid`) — en toda la tienda

Es de toda la tienda (lee el metafield del shop y el total del carrito). Va donde se vea siempre:

1. En el editor: **⋯ → Edit code** → `layout/theme.liquid`.
2. Pegá el contenido de `widget/worker-freeship.liquid` (por ejemplo cerca del header, o en el carrito).
   > Alternativa sin código: un bloque **Custom Liquid** en el header o el carrito, si el tema lo permite.
3. **Save**.

## Verificar

- **Cuenta regresiva:** cargá una con el skill (`poner-cuenta-regresiva`) con una fecha futura → tiene
  que aparecer el reloj corriendo. Con una fecha pasada → muestra el texto de vencido o no aparece.
- **Envío gratis:** cargá el umbral con `poner-envio-gratis` → agregá algo al carrito → tiene que
  mostrar "Te faltan $X…" y la barra; al superar el umbral, el mensaje de logrado.

## Sacar

No se toca el tema. El cliente pide "sacá la cuenta regresiva" / "sacá la barra de envío gratis" y el
skill escribe el vacío por el camino auditado. Los bloques dejan de mostrarse.
