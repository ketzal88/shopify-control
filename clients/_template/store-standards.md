# store-standards — ⚠️ NOMBRE

> Estándares de operación de producto. Referencia la marca en handsOn; no la duplica.
> Campos **[ESTABLE]** se definen 1 vez en el onboarding. Campos **[VIVO]** se refrescan ~cada 3 meses.

## 1. Marca [ESTABLE]
→ Ver folder del cliente en handsOn: `handsOn-Worker/clients/ecommerce/⚠️slug/` (brand-voice.md, icp.md, avatares).
- Esencial inline: ⚠️ (qué vende, años, estética)

## 2. Registro y voz [ESTABLE]
- Idioma / dialecto: ⚠️ (ej: español neutro, sin voseo)
- Tono: ⚠️
- Vocabulario SÍ: ⚠️
- Vocabulario NO: ⚠️
- Humanizer: OBLIGATORIO antes de todo output

## 3. Estructura de descripción [ESTABLE] (molde canónico)
1) Título: [Producto] + [material/beneficio] + keyword
2) Hook: 1-2 líneas
3) Beneficios: 3 viñetas
4) Material / garantía
5) Bloque GEO: 2-4 preguntas frecuentes
- Keywords TEJIDAS en el texto (no bloque aparte).
- meta title + meta description = campos SEO separados (§4); se escriben junto con el body (field set del v1).
- Longitud target: ⚠️ (ej: 80-150 palabras)
- NO incluir: precio en el texto, promesas de envío/stock.

## 4. SEO [VIVO]
- Keywords núcleo: ⚠️
- Keywords por categoría: ⚠️
- Meta title: patrón + máx ~60 caracteres
- Meta description: patrón + ~155 caracteres
- Handle/URL: minúsculas-con-guiones, incluye keyword. SOLO para productos NUEVOS (W3 futuro); en v1 NO se edita el handle de un producto existente (rompe su URL).

## 5. GEO (búsqueda con IA) [VIVO]
- Afirmaciones citables y directas (no "podría ser", sí "es").
- Bloque Q&A en cada producto.
- Datos concretos > adjetivos vagos.

## 6. Naming / tags / categorías [ESTABLE]
- Nombre: [Colección] + [tipo] + [material] + [color]
- Tags obligatorios: ⚠️
- Taxonomía de colecciones: ⚠️

## 7. Plantillas de imagen [ESTABLE] (placeholder para W2 futuro)
- Colores de marca: ⚠️
- Estilo: ⚠️ (specs cuando lleguemos a imágenes)

## 8. Qué no tocar (alcance seguro) [ESTABLE]
- Los skills solo tocan el field set del v1: descripción (`descriptionHtml`, vía `update-product`) + SEO (`seo.title`/`seo.description`, vía `graphql_mutation`).
- NUNCA precio, stock, status ni handle/URL sin gate estructural (OK de Gabriel).
- Star products: ⚠️ (cuidado extra).

## 9. Checklist "listo para publicar" (el skill lo corre antes del preview)
- [ ] pasó humanizer
- [ ] registro correcto (según §2)
- [ ] tiene keyword
- [ ] tiene bloque GEO
- [ ] longitud OK
- [ ] vocabulario de marca
- [ ] sin palabras prohibidas
- [ ] corrió description_lint sin issues

## 10. Señales del Brain [VIVO] (placeholder futuro)
→ keywords que convierten (seo-gaps), ángulos que ganaron (creative-intelligence), co-compra real (customer-intelligence). Enriquece §4 y §5.
