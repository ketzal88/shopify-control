# Instalar los bloques de Confianza y WhatsApp (operador)

Son **dos** bloques, cada uno se pega **una vez** por tema. No se edita ningún archivo del tema, y los
writes de tema están bloqueados por diseño → **lo hace el operador a mano**.

## 1. Bloque de badges/mensajes (`worker-trust.liquid`) — en la ficha

1. **Admin → Online Store → Themes → Customize** (tema activo).
2. Elegí una plantilla de **producto** (Templates → Products → Default product).
3. Cerca del botón **Agregar al carrito**, tocá **Add block → Custom Liquid**.
4. Pegá todo el contenido de `widget/worker-trust.liquid`.
5. Ubicá el bloque cerca del precio / botón de compra. **Save**.

Muestra los badges (cuotas, transferencia, envío, garantía, seguridad) y los mensajes cortos. Lee
primero el `worker.trust` del producto; si no hay, cae al de toda la tienda. Los ítems de WhatsApp no
aparecen acá (van en el botón flotante).

## 2. Botón de WhatsApp (`worker-whatsapp.liquid`) — en toda la tienda

Este va en el **layout**, no en una plantilla, para que aparezca en todas las páginas.

1. En el editor de temas: **⋯ (More actions) → Edit code**.
2. Abrí `layout/theme.liquid`.
3. Justo **antes de `</body>`**, agregá una línea que incluya el bloque, o pegá directamente el
   contenido de `widget/worker-whatsapp.liquid` ahí.
   > Alternativa sin tocar código: si el tema permite un bloque **Custom Liquid** a nivel de todas las
   > páginas (algunos lo permiten en el footer), pegalo ahí.
4. **Save**.

Lee el ítem `whatsapp` de `worker.trust` **de la tienda** (SHOP). Si no hay, no aparece nada.

## Verificar

- **Badges:** cargá algún badge con el skill (`poner-confianza`) y abrí un producto: tienen que
  aparecer los sellos cerca del precio. Un producto/tienda sin nada → no aparece nada (ni un hueco).
- **WhatsApp:** con un número cargado, el botón verde tiene que aparecer abajo a la derecha en
  cualquier página, y al tocarlo abrir WhatsApp con el mensaje pre-cargado.

## Sacar

No se toca el tema. El cliente le pide a Claude "sacá los sellos" o "sacá el botón de WhatsApp" y el
skill escribe la lista vacía por el camino auditado. Los bloques dejan de mostrarse solos.
