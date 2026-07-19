---
name: armar-combo
description: Recomienda combos o bundles de productos en base al catálogo y la lógica de colección de la tienda. Devuelve las propuestas como texto; no crea el combo en Shopify. Usar cuando el cliente pide ideas de combos, packs, sets o qué productos vender juntos.
---

# Armar combo (recomendación, solo lectura)

Skill de **lectura + razonamiento**. Propone combos como texto. NO crea el combo en Shopify (eso sería un write, va a una versión futura).

## Reglas
- Solo propone; no escribe nada en la tienda.
- Sin jerga con el cliente. Registro del cliente según `store-standards.md §2`.
- Humanizer antes de entregar.

## Skills que reusás
- `ecommerce-marketing-manager` — lógica de cross-sell y bundling, LTV.
- `marketing-psychology` — psicología del bundling (por qué un combo convierte).

## Flujo
1. Leé el catálogo vía el connector (productos, colecciones, tags).
2. Armá combos con criterio:
   - Productos de la misma colección que se complementan (ej: colección NEXO "funciona sola o en conjunto").
   - Producto estrella + accesorio.
   - Sets para regalo.
3. Presentá cada combo en texto simple: qué lleva, por qué tiene sentido, y una frase de cómo comunicarlo.

## Placeholder futuro (Brain)
Cuando esté disponible el input del Brain, usar la co-compra real (`customer-intelligence`) para basar los combos en lo que la gente ya compra junta, en vez de solo lógica de catálogo.

## Qué NO hace
- No crea el combo/bundle en Shopify.
- No cambia precios.
