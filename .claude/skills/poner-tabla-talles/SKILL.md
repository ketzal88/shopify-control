---
name: poner-tabla-talles
description: Pone una tabla de talles o de medidas en la página de un producto de Shopify. Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide una tabla de talles, una guía de medidas, o mostrar las medidas de un producto (anillos, ropa, calzado).
---

# Poner tabla de talles

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.sizechart` en un producto, que lee el bloque de la ficha.

## Reglas duras
- Alcance: solo `worker.sizechart`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (la valida el guard): `{version, title?, rows}`. `rows` = lista de filas de **2
  columnas** (talle, medida), texto ≤40. `title` ≤60. **La primera fila se muestra como encabezado.**
- Sacar = escribir `{version:1, rows:[]}` (o `{}`); nunca borrar el metafield.
- Sin jerga, **humanizer**, registro del cliente. Nada sin preview + gate + backup. Un asunto por llamada.

## Paso 0
Confirmar cliente (`CLAUDE.md` + `store-standards.md`) y tienda (`get-shop-info` vs `connection.md`).
Si no coinciden, **ABORTÁ**.

## Flujo
Identificar producto → leer el `worker.sizechart` actual (para el `previous`) → armar las filas con el
cliente (las medidas reales, no inventadas) → humanizer → preview → gate → backup → write → worklog.

## Backup
`clients/{slug}/backups/sizechart/{productIdTail}-{YYYYMMDD-HHMMSS}.json`
```json
{ "kind": "sizechart", "productId": "gid://shopify/Product/999", "previous": null, "ts": "2026-07-22T22:40:00" }
```

## Escribir
```json
{ "metafields": [ { "ownerId": "gid://shopify/Product/999", "namespace": "worker", "key": "sizechart",
  "type": "json", "value": "{\"version\":1,\"title\":\"Medidas\",\"rows\":[[\"Talle\",\"Medida\"],[\"6\",\"16,5 mm\"],[\"7\",\"17,3 mm\"]]}" } ] }
```
`metafieldsSet` (mutación estándar). `value` es string con el JSON. Las medidas las confirma el cliente.
