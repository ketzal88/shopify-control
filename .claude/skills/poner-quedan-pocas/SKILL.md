---
name: poner-quedan-pocas
description: Muestra un aviso de "quedan pocas unidades" en un producto de Shopify, usando el stock REAL (nunca un número inventado). Muestra un preview, pide confirmación, guarda backup y permite sacarlo. Usar cuando el cliente pide mostrar poco stock, urgencia de stock, o "quedan pocas".
---

# Poner "quedan pocas"

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.lowstock` en un producto (el umbral y el texto). El bloque lee el **stock real** de la
variante y solo muestra el aviso si hay tracking y quedan entre 1 y el umbral — **nunca inventa** un
número.

## Reglas duras
- Alcance: solo `worker.lowstock`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (guard): `{version, threshold, text?}`. `threshold` entero 1–999. `text` ≤60 sin `<`/`>`.
- **Honestidad:** aclarale al cliente que solo aparece con stock real bajo (si el tema no muestra el
  stock, no se ve). Sacar = `{}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/lowstock/{productIdTail}-{ts}.json` con `kind:"lowstock"`.

## Escribir
`metafieldsSet` de `worker.lowstock`, `value` string: `{"version":1,"threshold":5,"text":"Quedan pocas"}`
