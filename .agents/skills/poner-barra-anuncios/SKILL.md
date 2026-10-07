---
name: poner-barra-anuncios
description: Pone una barra o cinta de anuncios arriba de toda la tienda de Shopify (para una promo, un lanzamiento o el envío gratis). Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide una barra de anuncios, una cinta arriba, o anunciar algo en toda la tienda.
---

# Poner barra de anuncios

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.announce` **en la tienda** (SHOP).

## Reglas duras
- Alcance: solo `worker.announce`. NUNCA precio, stock, status, tags, título, handle.
- Es de toda la tienda: owner = el **shop** (`gid://shopify/Shop/…`).
- Forma cerrada (guard): `{version, text, link?}`. `text` ≤120 sin `<`/`>`. `link` una URL **https**.
- Sacar = `{}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/announce/{shopIdTail}-{ts}.json` con `kind:"announce"`.

## Escribir
`metafieldsSet` de `worker.announce` sobre el shop, `value` string:
`{"version":1,"text":"Envío gratis en compras +$80.000","link":"https://tutienda.com/envios"}`
