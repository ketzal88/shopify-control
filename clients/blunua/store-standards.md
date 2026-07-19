# store-standards — Blunua

> Estándares de operación de producto. Referencia la marca en handsOn; no la duplica.
> Campos **[ESTABLE]** se definen 1 vez en el onboarding. Campos **[VIVO]** se refrescan ~cada 3 meses.

## 1. Marca [ESTABLE]
→ Ver folder del cliente en handsOn: `handsOn-Worker/clients/ecommerce/blunua/` (brand-voice.md, icp.md, avatares).
- Esencial inline: joyería de acero quirúrgico hipoalergénico, +10 años de trayectoria, minimalista y moderna (brand type aesthetic). Piezas para uso diario, resistentes al agua, pensadas como accesorios con significado.
- Colecciones: general (acero quirúrgico minimalista), **NUA** (previa), **NEXO** (nueva; joyas mixtas mujer/hombre, "funciona sola o en conjunto", idea de conexión y complementariedad).

## 2. Registro y voz [ESTABLE]
- Idioma / dialecto: **español neutro, sin voseo** (blunua es COP/Colombia).
- Tono: amigable, sobrio, sin exagerar.
- Vocabulario SÍ: duradera, no irrita, segura, minimalista, hipoalergénico, resistente al agua, para regalar, significativa, elegante pero sencilla.
- Vocabulario NO: ⚠️ (definir. Evitar lujo-aspiracional y superlativos vacíos; no imitar a Pandora, Acero & Piedra, Joboly, Two Pieces, Maria Grazia Severin).
- Humanizer: OBLIGATORIO antes de todo output.

## 3. Estructura de descripción [ESTABLE] (molde canónico)
1) Título: [Producto] + [material/beneficio] + keyword
2) Hook: 1-2 líneas
3) Beneficios: 3 viñetas
4) Material / garantía
5) Bloque GEO: 2-4 preguntas frecuentes
- Keywords TEJIDAS en el texto (no bloque aparte).
- meta title + meta description = campos SEO separados (§4); se escriben junto con el body (field set del v1).
- Longitud target: 80-150 palabras.
- NO incluir: precio en el texto, promesas de envío/stock.

## 4. SEO [VIVO]
- Keywords núcleo: acero quirúrgico, hipoalergénico, resistente al agua, joyería minimalista.
- Keywords por categoría: ⚠️ (anillos / collares / pulseras / aros).
- Meta title: patrón + máx ~60 caracteres.
- Meta description: patrón + ~155 caracteres.
- Handle/URL: minúsculas-con-guiones, incluye keyword. SOLO para productos NUEVOS (W3 futuro); en v1 NO se edita el handle de un producto existente (rompe su URL).

## 5. GEO (búsqueda con IA) [VIVO]
- Afirmaciones citables y directas (no "podría ser", sí "es").
- Bloque Q&A en cada producto.
- Datos concretos > adjetivos vagos.

## 6. Naming / tags / categorías [ESTABLE]
- Nombre: [Colección] + [tipo] + [material] + [color]
- Tags obligatorios: colección (NEXO/NUA), material (acero quirúrgico), género.
- Taxonomía de colecciones: ⚠️ (mapear las colecciones reales de la tienda).

## 7. Plantillas de imagen [ESTABLE] (placeholder para W2 futuro)
- Colores de marca: #4B4B4B / #9CB0B1 / #CEC4BA / #E9E6DD
- Estilo: minimalista, fondo limpio + ⚠️ (specs cuando lleguemos a imágenes).

## 8. Qué no tocar (alcance seguro) [ESTABLE]
- Los skills solo tocan el field set del v1: descripción (`descriptionHtml`, vía `update-product`) + SEO (`seo.title`/`seo.description`, vía `graphql_mutation`).
- NUNCA precio, stock, status ni handle/URL sin gate estructural (OK de Gabriel).
- Star products: colección general, NUA, NEXO (cuidado extra).

## 9. Checklist "listo para publicar" (el skill lo corre antes del preview)
- [ ] pasó humanizer
- [ ] registro correcto (español neutro, sin voseo)
- [ ] tiene keyword
- [ ] tiene bloque GEO
- [ ] longitud OK (80-150 palabras)
- [ ] vocabulario de marca
- [ ] sin palabras prohibidas
- [ ] corrió description_lint sin issues

## 10. Señales del Brain [VIVO] (placeholder futuro)
→ Brain ID blunua: `LO4ob4dUxOggwTSlm07v`. keywords que convierten (seo-gaps), ángulos que ganaron (creative-intelligence), co-compra real (customer-intelligence). Enriquece §4 y §5.
