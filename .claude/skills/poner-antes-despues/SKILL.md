---
name: poner-antes-despues
description: Pone un comparador "antes y después" (un deslizador entre dos fotos) en la ficha de un producto de Shopify. Muestra un preview, pide confirmación, guarda backup y permite sacarlo. Usar cuando el cliente pide mostrar antes/después, una transformación, o comparar dos fotos.
---

# Poner antes y después

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.beforeafter` en un producto.

## Reglas duras
- Alcance: solo `worker.beforeafter`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (guard): `{version, before, after, beforeLabel?, afterLabel?}`. `before` y `after` son
  URLs de imagen **https** (subilas antes a Shopify o usá una URL https válida). Labels ≤30.
- Sacar = `{}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/beforeafter/{productIdTail}-{ts}.json` con `kind:"beforeafter"`.

## Escribir
`metafieldsSet` de `worker.beforeafter`, `value` string:
`{"version":1,"before":"https://cdn.shopify.com/.../antes.jpg","after":"https://cdn.shopify.com/.../despues.jpg","beforeLabel":"Antes","afterLabel":"Después"}`

## Nota
Las imágenes deben estar hospedadas (https). Si el cliente manda fotos sueltas, hay que subirlas a
Shopify primero (o a un hosting https) y usar esas URLs.
