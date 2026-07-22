---
name: armar-faq
description: Arma la sección de preguntas frecuentes de un producto de Shopify (aparece en la ficha, con datos estructurados para Google). Muestra un preview en el chat, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide agregar preguntas frecuentes, un FAQ, o responder dudas comunes en la página del producto.
---

# Armar preguntas frecuentes (FAQ)

Skill de **escritura** sobre la tienda viva. **No mueve plata** (es cosmético), pero es un write
igual: lleva el mismo protocolo duro que el resto —preview, gate, backup— porque en este repo nada se
escribe sin eso. Escribe el metafield `worker.faq`, que lee el bloque de la ficha, y de paso genera
los datos estructurados (`FAQPage`) que ayudan a que Google y los buscadores con IA muestren las
respuestas.

`mejorar-descripcion` es el vecino natural: si una duda se responde mejor dentro del texto del
producto, va ahí; el FAQ es para las preguntas repetidas y puntuales (talle, envío, garantía).

## Reglas duras (no negociables)

- **Alcance:** solo escribir `worker.faq` sobre **un** producto. NUNCA precio, stock, status, tags,
  título, handle, colecciones ni ningún otro campo.
- **Nunca inventes una respuesta.** Podés **sugerir preguntas** (desde la descripción, la categoría o
  dudas típicas), pero cada respuesta la **confirma el cliente** en el preview. Una respuesta falsa
  sobre envío o garantía es peor que no tener FAQ.
- **Forma cerrada** (la valida el guard, no la fuerces): hasta **12 preguntas**, cada una con pregunta
  (hasta 120 caracteres) y respuesta (hasta 600), **sin `<` ni `>`**.
- **Sacar la FAQ = escribir `items: []`** (lista vacía), nunca borrar el metafield: `metafieldDelete`
  está bloqueado por diseño. Con la lista vacía, el bloque deja de mostrarse.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de skill ni
  comandos. Tampoco expliques limitaciones técnicas ("no tengo permisos", "el guard lo bloquea").
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN voseo).
- **Humanizer obligatorio** antes de todo output cliente: leé `handsOn-Worker/skills/humanizer/SKILL.md`
  y aplicá sus reglas a mano (hoy no es invocable como skill desde este repo).
- **Nada se escribe sin:** (1) preview mostrado, (2) "sí" explícito del cliente, (3) backup guardado.
- **Un solo producto por pedido.**

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)

Igual que el resto de los skills de escritura:

1. Confirmá el **cliente activo** y leé `clients/{slug}/CLAUDE.md` + `store-standards.md`.
2. Verificá la tienda conectada con `get-shop-info` contra `clients/{slug}/connection.md`.
3. **Si no coinciden, ABORTÁ.** Escribir en la tienda equivocada es el peor error posible.

## Flujo

1. **Identificar el producto.** El cliente lo nombra; nunca adivines. Buscalo con `search_products`.
2. **Leer.** El `worker.faq` actual del producto (para el `previous` del backup) + la descripción y el
   título (para poder sugerir preguntas con contexto).
3. **Proponer / editar.** Armá o ajustá la lista de preguntas y respuestas. Podés proponer preguntas
   típicas de la categoría (talle, materiales, envío, cuidado, garantía), pero las respuestas salen de
   lo que el cliente confirma o de datos ya escritos en la tienda — **nunca inventadas**.
4. **Humanizer.** Pasá las preguntas y respuestas por las reglas del humanizer y el registro del
   cliente (blunua: español neutro, sin voseo).
5. **Preview en el chat.** Mostrá la lista completa (todas las preguntas con su respuesta, texto
   completo), sin jerga. El cliente no puede aprobar lo que no vio.
6. **Gate.** Nada se escribe sin un "sí" explícito.
7. **Backup** (ver contrato abajo), ANTES de escribir.
8. **Escribir** el metafield (ver mutación abajo).
9. **Worklog + confirmar.** Dejá la entrada en `clients/{slug}/worklog.md` y confirmá en lenguaje
   natural: "Listo. Para sacarlas: 'sacá las preguntas frecuentes del anillo NEXO'."

## Backup (contrato)

Antes de la escritura, guardás:

`clients/{slug}/backups/faq/{productIdTail}-{YYYYMMDD-HHMMSS}.json`

```json
{ "kind": "faq",
  "productId": "gid://shopify/Product/999",
  "previous": null,
  "ts": "2026-07-22T22:40:00" }
```

- **`kind: "faq"` es obligatorio**, y la carpeta **tiene que ser `backups/faq/`**. Las dos condiciones
  juntas: es lo que impide que un backup de FAQ habilite un write de plata, y viceversa (aislamiento
  por ruta + kind, igual que oferta y estilo).
- `previous` = el `worker.faq` anterior tal cual estaba (leelo antes), o `null` si no había.
- `ts` en hora local sin zona; vale 15 minutos (mismo contrato de frescura que los demás).

## `escribir` la FAQ

```graphql
mutation ($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id }
    userErrors { field message }
  }
}
```

```json
{ "metafields": [ {
    "ownerId": "gid://shopify/Product/999",
    "namespace": "worker",
    "key": "faq",
    "type": "json",
    "value": "{\"version\":1,\"items\":[{\"q\":\"¿El anillo es ajustable?\",\"a\":\"Sí, con ajuste gratis en tu primer pedido.\"}]}"
} ] }
```

- **`ownerId` obligatorio** con el gid del producto (sin él no hay contra qué buscar el backup).
- `value` es un **string** con el JSON adentro (`type: "json"`), no un objeto.
- **Un solo asunto por llamada:** la FAQ va sola, nunca mezclada con una oferta ni con el estilo en el
  mismo `metafieldsSet` (el guard rechaza el documento que toca dos asuntos).

## Sacar la FAQ

Es un write como cualquiera (preview → gate → backup → escribir), con `value` = `{"version":1,"items":[]}`.
El bloque deja de mostrarse. No hay "restore" de FAQs anteriores (igual que con las ofertas).

## Qué NO hace

- No toca la descripción (eso es `mejorar-descripcion`).
- No inventa respuestas ni promete cosas que el cliente no confirmó (envío, garantía, devoluciones).
- No instala el bloque en el tema (eso lo hace el operador una vez; ver el runbook).
