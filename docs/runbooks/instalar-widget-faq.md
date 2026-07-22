# Instalar el bloque de Preguntas frecuentes (operador)

Igual que el de escalones: se pega **una vez** por tema, desde el editor de temas de Shopify. No se
edita ningún archivo del tema, y los writes de tema están bloqueados por diseño → **lo hace el
operador a mano**, no Claude.

## Antes de empezar

- Tenés que estar en el **admin de Shopify** de la tienda del cliente (la que confirma `get-shop-info`
  contra `connection.md`).
- El cliente ya tiene que haber armado al menos una FAQ (o la armás vos con el skill `armar-faq`); si
  el producto no tiene `worker.faq`, el bloque no muestra nada — no rompe, solo no aparece.

## Pasos

1. **Admin → Online Store → Themes → Customize** (en el tema activo).
2. Arriba, elegí una plantilla de **producto** (Templates → Products → Default product).
3. En la columna de secciones, en la zona de la **descripción del producto**, tocá **Add block** →
   **Custom Liquid** (o **Add section → Custom Liquid** si tu tema no permite bloque ahí).
4. Pegá **todo** el contenido de `widget/worker-faq.liquid` en el campo de Custom Liquid.
5. Ubicá el bloque **debajo de la descripción** del producto (arrastrándolo).
6. **Save**.

## Verificar

- Abrí en el storefront un producto **que tenga** FAQ cargada: tiene que aparecer "Preguntas
  frecuentes" con el acordeón (tocar una pregunta la abre/cierra).
- Abrí un producto **sin** FAQ: no tiene que aparecer nada (ni un hueco).
- **Datos estructurados:** pegá la URL del producto en el
  [Rich Results Test de Google](https://search.google.com/test/rich-results); tiene que detectar
  **FAQPage** con las preguntas. Eso es lo que habilita que Google/los buscadores con IA citen las
  respuestas.

## Sacar una FAQ

No se toca el tema. El cliente le pide a Claude "sacá las preguntas frecuentes del anillo X" y el skill
escribe la lista vacía (`items: []`) por el camino auditado. El bloque deja de mostrarse solo.
