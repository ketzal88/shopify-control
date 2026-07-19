---
name: reporte-tienda
description: Responde preguntas sobre la tienda Shopify del cliente — resultados de ventas, stock, y alertas — leyendo en vivo vía el connector. Solo lectura, no cambia nada. Usar cuando el cliente pregunta cómo va su tienda, qué se vende, qué productos están por agotarse, o qué conviene mejorar.
---

# Reporte de tienda (solo lectura)

Skill de **lectura**. Responde preguntas sobre la tienda vía el connector directo. NO escribe nada.

## Reglas
- Solo lectura. Nunca modificás productos, precios, stock ni nada.
- Sin jerga con el cliente: respuestas en lenguaje natural, claras y simples.
- Registro del cliente según `store-standards.md §2` (blunua: español neutro, sin voseo).
- Humanizer antes de entregar el texto.

## Skills que reusás
- `ecommerce-marketing-manager` — cómo leer métricas ecom (ventas, ROAS, LTV).
- `alerts-system` — cómo enmarcar alertas.
- `handsOn-Worker/skills/shopify-api/SKILL.md` — referencia de campos de Shopify.

## Qué responde
- **Resultados:** ventas del período, productos top, qué se mueve y qué no.
- **Stock:** productos con bajo stock, agotados.
- **Alertas:** stock crítico, y productos "candidatos a mejorar" (sin descripción, descripción muy corta, o sin imagen).

## Flujo
1. Entendé la pregunta del cliente (período, categoría, producto).
2. Leé la data vía el connector (órdenes/analytics para resultados; productos/inventario para stock).
3. Respondé en texto simple, sin jerga. Números claros y con contexto ("esta semana vendiste X, un poco más que la anterior").
4. Si detectás candidatos a mejorar (descripción pobre o sin imagen), ofrecé el siguiente paso en lenguaje natural: "Vi que estos 3 productos tienen descripciones muy cortas, ¿querés que mejore alguna?" (esto dispara el skill mejorar-descripcion).

## Qué NO hace
- No escribe ni cambia nada en la tienda.
- No inventa números: si la data no está disponible, lo dice.
