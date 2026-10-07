---
name: poner-envio-gratis
description: Pone la barra de "te faltan $X para el envío gratis" en la tienda de Shopify. Lee el total real del carrito y muestra cuánto falta para llegar al monto de envío gratis. Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide una barra de envío gratis, mostrar cuánto falta para el envío gratis, o subir el ticket promedio.
---

# Poner barra de envío gratis

Skill de **escritura** cosmético (no mueve plata), mismo protocolo duro: preview → gate → backup →
write. Escribe `worker.freeship` **en la tienda** (SHOP), que lee el bloque. La barra lee el total
**real** del carrito y calcula lo que falta — no inventa nada.

## Reglas duras

- **Alcance:** solo `worker.freeship`. NUNCA precio, stock, status, tags, título, handle.
- **Es de toda la tienda:** owner = el **shop** (`gid://shopify/Shop/…`).
- **Forma cerrada** (la valida el guard): `{version, threshold, label?, successText?}`.
  - `threshold`: el monto de envío gratis **en centavos** (entero > 0). Ej: $80.000 → `8000000`.
  - `label`: usa el marcador `{falta}` donde va el monto que falta (ej. "Te faltan {falta} para el
    envío gratis"). `successText`: el mensaje al llegar. Textos ≤80 sin `<`/`>`.
- **El monto tiene que ser real:** el umbral tiene que coincidir con el envío gratis que el comercio
  de verdad ofrece (su configuración de envíos). No pongas un número que no cumple.
- **Sacar = escribir `{}`** o no dejar `threshold`; nunca borrar el metafield.
- **Sin jerga**, **humanizer**, **registro** del cliente. **Nada sin** preview + gate + backup.

## Paso 0 — Confirmar cliente y tienda
Igual que el resto: cliente activo + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Flujo
1. Preguntar/confirmar el **monto de envío gratis** (y pasarlo a centavos).
2. Leer el `worker.freeship` actual del shop (para el `previous`).
3. Armar `{version:1, threshold, label, successText}`. Humanizer sobre los textos.
4. Preview: mostrar cómo se ve ("Te faltan $X…") y aclarar que se actualiza solo con el carrito.
5. Gate → backup → write → worklog + confirmar.

## Backup
`clients/{slug}/backups/freeship/{shopIdTail}-{YYYYMMDD-HHMMSS}.json`
```json
{ "kind": "freeship", "productId": "gid://shopify/Shop/101009064253", "previous": null, "ts": "2026-07-22T22:40:00" }
```
`kind:"freeship"` + carpeta `backups/freeship/` (las dos). `productId` guarda el gid del shop.

## Escribir
```graphql
mutation ($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) { metafields { id } userErrors { field message } }
}
```
```json
{ "metafields": [ { "ownerId": "gid://shopify/Shop/101009064253", "namespace": "worker", "key": "freeship",
  "type": "json", "value": "{\"version\":1,\"threshold\":8000000,\"label\":\"Te faltan {falta} para el envío gratis\",\"successText\":\"¡Tenés envío gratis!\"}" } ] }
```
`threshold` en **centavos**. `value` es string con el JSON adentro.

## Qué NO hace
No configura el envío gratis de verdad (eso es la configuración de envíos de Shopify): solo muestra el
**cartel** de lo que el comercio ya ofrece. No inventa el monto.
