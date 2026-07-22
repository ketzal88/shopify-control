---
name: poner-beneficios
description: Pone una lista de beneficios (puntos fuertes con tildes) en la página de un producto de Shopify, cerca del precio. Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide destacar los beneficios, ventajas o puntos fuertes de un producto.
---

# Poner lista de beneficios

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.benefits` en un producto.

## Reglas duras
- Alcance: solo `worker.benefits`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (la valida el guard): `{version, items}` con `items` = 1 a 8 textos ≤60 sin `<`/`>`.
- Los beneficios tienen que ser **verdad** (los confirma el cliente). Sacar = `{version:1, items:[]}`.
- Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup. Un asunto por llamada.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/benefits/{productIdTail}-{ts}.json` con `kind:"benefits"`.

## Escribir
`metafieldsSet` de `worker.benefits`, `value` string:
`{"version":1,"items":["Hipoalergénico","Ajuste gratis","Garantía 1 año"]}`
