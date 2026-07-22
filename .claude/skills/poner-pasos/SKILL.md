---
name: poner-pasos
description: Pone los pasos de cómo usar o cuidar un producto de Shopify (una guía en pasos numerados en la ficha). Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide explicar cómo se usa, cómo se cuida, o los pasos de un producto.
---

# Poner pasos de uso

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.steps` en un producto.

## Reglas duras
- Alcance: solo `worker.steps`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (guard): `{version, items}` con `items` = 1 a 8 textos ≤200 sin `<`/`>`.
- Sacar = `{version:1, items:[]}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/steps/{productIdTail}-{ts}.json` con `kind:"steps"`.

## Escribir
`metafieldsSet` de `worker.steps`, `value` string:
`{"version":1,"items":["Limpiá la superficie","Aplicá una capa fina","Dejá secar 10 minutos"]}`
