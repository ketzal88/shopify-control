---
name: poner-video-flotante
description: Pone un botón flotante de video en la tienda de Shopify (abre un video en un modal, por ejemplo del producto en uso o la historia de marca). Muestra un preview, pide confirmación, guarda backup y permite sacarlo. Usar cuando el cliente pide un video flotante, un botón de video, o mostrar un video en la tienda.
---

# Poner video flotante

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.video` **en la tienda** (SHOP).

## Reglas duras
- Alcance: solo `worker.video`. NUNCA precio, stock, status, tags, título, handle.
- Es de toda la tienda: owner = el **shop** (`gid://shopify/Shop/…`).
- Forma cerrada (guard): `{version, url, label?}`. `url` una URL **https** (YouTube o un video .mp4
  hospedado). `label` ≤60.
- Sacar = `{}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/video/{shopIdTail}-{ts}.json` con `kind:"video"`.

## Escribir
`metafieldsSet` de `worker.video` sobre el shop, `value` string:
`{"version":1,"url":"https://youtube.com/watch?v=XXXX","label":"Mirá cómo funciona"}`
