---
name: poner-comparacion
description: Pone una tabla que compara tu producto con la competencia en la ficha de Shopify (una columna "nosotros" y otra "otros"). Muestra un preview, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide comparar su producto con otros, mostrar por qué conviene, o una tabla vs la competencia.
---

# Poner comparación con otros

Skill de escritura **cosmético** (no mueve plata): preview → gate → backup → write. Escribe
`worker.compare` en un producto.

## Reglas duras
- Alcance: solo `worker.compare`. NUNCA precio, stock, status, tags, título, handle.
- Forma cerrada (guard): `{version, usLabel?, themLabel?, rows}`. `rows` = filas de **3 columnas**
  (ítem, nosotros, otros), texto ≤40. Labels ≤30.
- Los datos tienen que ser justos/verdaderos (comparación honesta). Sacar = `{version:1, rows:[]}`.
- Sin jerga, **humanizer**, registro. Nada sin preview + gate + backup. Un asunto por llamada.

## Paso 0
Cliente + tienda (`get-shop-info` vs `connection.md`). Si no coinciden, **ABORTÁ**.

## Backup
`clients/{slug}/backups/compare/{productIdTail}-{ts}.json` con `kind:"compare"`.

## Escribir
`metafieldsSet` de `worker.compare`, `value` string:
`{"version":1,"usLabel":"Nosotros","themLabel":"Otros","rows":[["Garantía","Sí","No"],["Envío 24h","Sí","No"]]}`
