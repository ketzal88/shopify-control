---
name: poner-cuenta-regresiva
description: Pone una cuenta regresiva (un reloj de "la oferta termina en…") en un producto o en toda la tienda de Shopify. Cuenta hasta una fecha real que fijás; cuando llega, muestra un mensaje o se oculta. Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide un contador, un reloj de oferta, o mostrar cuánto falta para que termine una promo.
---

# Poner cuenta regresiva

Skill de **escritura** cosmético (no mueve plata), con el mismo protocolo duro que el resto:
preview → gate → backup → write. Escribe `worker.countdown`, que lee el bloque de la tienda.

**Honestidad (regla dura):** el reloj cuenta hasta una **fecha real** que fija el cliente y **no
resetea** por sesión. Cuando la fecha pasa, muestra el texto de vencido o se oculta — nunca inventa
urgencia ni se reinicia solo. Si la oferta tiene fecha de fin (escalones/regalo), usá **esa** fecha.

## Reglas duras

- **Alcance:** solo `worker.countdown`. NUNCA precio, stock, status, tags, título, handle.
- **Forma cerrada** (la valida el guard): `{version, endsAt, label?, expiredText?}`. `endsAt` es una
  fecha ISO válida; `label` y `expiredText` textos ≤60 sin `<`/`>`.
- **Dónde vive:** por producto (owner del producto) o de toda la tienda (owner del shop, para una
  promo general). Si no aclara, preguntá.
- **Sacar = escribir `{}`** (objeto vacío) o directamente no dejar `endsAt`; nunca borrar el metafield.
- **Sin jerga**, **humanizer** antes de mostrar, **registro** del cliente (`store-standards.md §2`).
- **Nada sin:** preview, "sí" explícito, backup. **Un asunto por llamada.**

## Paso 0 — Confirmar cliente y tienda
Confirmá cliente activo (`CLAUDE.md` + `store-standards.md`) y tienda (`get-shop-info` vs
`connection.md`). Si no coinciden, **ABORTÁ**.

## Flujo
1. Entender qué oferta/fecha. Si hay una oferta con `endsAt`, proponé esa fecha.
2. Leer el `worker.countdown` actual (para el `previous`).
3. Armar `{version:1, endsAt, label, expiredText?}`. Humanizer sobre los textos.
4. Preview en el chat, sin jerga (qué va a ver quien entra, hasta cuándo cuenta).
5. Gate → backup → write → worklog + confirmar.

## Backup
`clients/{slug}/backups/countdown/{ownerIdTail}-{YYYYMMDD-HHMMSS}.json`
```json
{ "kind": "countdown", "productId": "gid://shopify/Product/999", "previous": null, "ts": "2026-07-22T22:40:00" }
```
`kind:"countdown"` + carpeta `backups/countdown/` (las dos). `productId` = el owner (producto o shop).

## Escribir
```graphql
mutation ($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) { metafields { id } userErrors { field message } }
}
```
```json
{ "metafields": [ { "ownerId": "gid://shopify/Product/999", "namespace": "worker", "key": "countdown",
  "type": "json", "value": "{\"version\":1,\"endsAt\":\"2026-09-20T00:00:00Z\",\"label\":\"La oferta termina en\"}" } ] }
```
`value` es string con el JSON adentro. `endsAt` en ISO (con hora y, si podés, zona).

## Qué NO hace
No crea la oferta ni el descuento (eso es `armar-escalones`/`armar-regalo`); solo el reloj. No inventa
fechas: la pone el cliente o sale de una oferta existente.
