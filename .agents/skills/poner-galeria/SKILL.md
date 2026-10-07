---
name: poner-galeria
description: Pone una galería o carrusel de fotos extra en la ficha de un producto de Shopify. Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide una galería, un carrusel de fotos, o mostrar más imágenes del producto.
---

# Poner galería de fotos

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.gallery` en un producto.

## Reglas duras
- Alcance: solo `worker.gallery`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (guard): `{version, images}` con `images` = 1 a 12 URLs de imagen **https**.
- Sacar = `{version:1, images:[]}`. Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/gallery/{productIdTail}-{ts}.json` con `kind:"gallery"`.

## Escribir
`metafieldsSet` de `worker.gallery`, `value` string:
`{"version":1,"images":["https://cdn.shopify.com/.../1.jpg","https://cdn.shopify.com/.../2.jpg"]}`

## Nota
Las imágenes deben estar hospedadas (https). Podés usar las imágenes del propio producto (ya están en
el CDN de Shopify) o subir nuevas. Si el cliente manda fotos sueltas, hay que subirlas primero.
