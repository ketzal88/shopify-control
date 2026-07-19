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
- Vocabulario NO (curado 2026-07-19, fuente: brand-voice + anti-referencias):
  - **Materiales que no son** (sería falso; el material es acero quirúrgico): oro, plata, oro laminado, chapado/enchapado, bañado en oro. Sí se puede describir el *acabado* ("tono dorado/plateado"), nunca como material.
  - **Lujo-vacío / superlativos**: lujo, de lujo, exclusivo, glamour, deslumbrante, el/la mejor, único en el mundo, espectacular, increíble, de ensueño. (≠ "calidad premium", que la marca SÍ usa como garantía.)
  - **Claims médicos**: cura, curativo, propiedades medicinales, mágico. Sí permitido: "no irrita", "apto para pieles sensibles".
  - **Registro**: sin voseo ni argentinismos (Colombia, español neutro).
  - No imitar a: Pandora, Acero & Piedra, Joboly, Two Pieces, Maria Grazia Severin.
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
- Keywords por categoría (curado 2026-07-19, fuente: Google Search Console 90d — términos donde blunua ya aparece; **términos colombianos**):
  - **Aretes** (NO "aros" — Colombia dice "aretes"): aretes, aretes antialérgicos, aretes de acero quirúrgico, arete hipoalergénico, candongas, aretes de clip, ear cuff / earcuff, **topitos** (así los llama la tienda; "topos" aparece solo como variante en Ads), aretes para niñas.
  - **Anillos**: anillo ajustable, anillos delgados, anillo de acero, anillos de promesa. (Utilidades: medidor de anillos, tallas de anillos.)
  - **Collares**: collares, choker, cadena hipoalergénica.
  - **Pulseras**: **57 productos en tienda pero casi nada de demanda orgánica capturada** → no es falta de catálogo, es falta de visibilidad. Oportunidad SEO clara (misma lectura para Charms 68 y Tobilleras 10).
  - **Piercings**: piercings, piercing oreja.
  - Ojo: pagan Ads por "titanio" pero el material es acero quirúrgico — no reclamar titanio salvo que sea real.
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
- Taxonomía de colecciones (mapeada en vivo 2026-07-19 desde la tienda real, 678 productos):
  **Patrón estructural:** categoría (colección por `TYPE`) × segmento (`Her` / `Him` / `Kids`, por `TAG`) × subtipo. Las colecciones de segmento se arman por **TAG**, así que *el tag decide en qué colección cae el producto* — por eso los tags de §6 son obligatorios.

  | Categoría (handle) | Productos | Subtipos | Segmentos |
  |---|---|---|---|
  | Collares (`collares`) | 244 | Choker 19 · Midis 81 · Largos 11 | Her 178 · Him 18 · Kids 3 |
  | Aretes (`aretes`) | 193 | Candongas 76 · Topitos 37 · Topitos de Seguridad 37 · Earcuffs 19 · Largos 17 | Her 43 · Him 24 · Kids 18 |
  | Charms (`charms`) | 68 | — | — |
  | Pulseras (`pulseras`) | 57 | Pulseras+Tobilleras 62 | Her 40 · Him 7 · Kids 1 |
  | Anillos (`anillos`) | 50 | Ajustables · Delgados · Gruesos · Midis · Piedras/Cristales | Her 43 · Him 6 |
  | Conjuntos (`conjuntos`) | 15 | — | Her 17 · Him 5 · Kids 6 |
  | Tobilleras (`tobilleras`) | 10 | — | — |

  **Curadas / de campaña — NO son taxonomía, no tratarlas como categoría:** Earstacking (230, transversal), Brillo mágico, Círculos de amor, Cosmos, Cristales, Dorados, Full of Love, combos/conjuntos armados, `Disc_*` y `BFCM *` (descuentos, 0 productos fuera de campaña) y `all` (678, técnica).

  **Terminología confirmada en vivo:** la tienda dice **Topitos** (no "topos"), **Candongas**, **Earcuff**. Confirma §4: nunca "aros".

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
