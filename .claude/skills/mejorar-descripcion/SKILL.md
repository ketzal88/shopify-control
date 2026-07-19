---
name: mejorar-descripcion
description: Mejora la descripción de un producto de Shopify con criterio SEO y GEO, cumpliendo los estándares de la tienda. Muestra un preview antes/después en el chat, pide confirmación, guarda un backup y permite revertir. Usar cuando el cliente pide mejorar, optimizar o reescribir la descripción de un producto, o cuando reporte-tienda detecta productos con descripción pobre.
---

# Mejorar descripción de producto

Skill de **escritura** sobre la tienda viva. Reusás el craft que ya existe; lo nuevo es el flujo seguro (preview → backup → confirmación → undo) y el cumplimiento de estándares.

## Reglas duras (no negociables)
- **Alcance:** solo tocás 3 campos: la descripción (`descriptionHtml`), el **meta title** (`seo.title`) y la **meta description** (`seo.description`). NUNCA precio, stock, status ni handle/URL.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de skill ni comandos.
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, sin voseo).
- **Nada se escribe sin:** (1) preview mostrado, (2) confirmación explícita del cliente, (3) backup guardado.

## Contexto que cargás antes de empezar
- `clients/{slug}/store-standards.md` (molde, registro, keywords, checklist, qué no tocar).
- La marca en handsOn (link en el `CLAUDE.md` del cliente): brand-voice, vocabulario.

## Skills que reusás (no reinventes el craft)
- `handsOn-Worker/skills/humanizer/SKILL.md` — obligatorio, elimina AI tells (em-dashes, etc.).
- `seo-geo` — SEO + GEO (incluye data Princeton 2024).
- `generic-language-killer` — QA anti-genérico.
- `seo-schema` / `seo-content` / `seo-ecommerce` — schema y calidad de producto.
- `.claude/hooks/description_lint.py` — chequeo mecánico (em-dash, longitud, keyword) del checklist.

## Flujo (siempre en este orden)

1. **IDENTIFICAR.** El cliente dice qué producto ("mejorá la descripción del anillo NEXO plateado"). Buscá el producto vía el connector. Si hay más de un match, mostrá las opciones y preguntá cuál. NUNCA adivines qué producto editar.
2. **LEER.** Con `Shopify:search_products` (por nombre/SKU) obtené el **GID** del producto (`gid://shopify/Product/...`; no acepta el número pelado), y con `Shopify:get-product` traé el estado actual de los 3 campos: descripción (`descriptionHtml`) y SEO (`seo.title`, `seo.description`), más contexto de solo lectura (título, tags, fotos).
3. **CARGAR CONTEXTO.** Leé `store-standards.md` del cliente + la brand-voice de handsOn.
4. **GENERAR.** Escribí la nueva descripción con el molde canónico de `store-standards §3`: título → hook → 3 beneficios → material/garantía → bloque GEO (2-4 preguntas frecuentes). Keywords tejidas en el texto. Además generá meta title (~60 caracteres) y meta description (~155 caracteres).
5. **HUMANIZER (obligatorio).** Pasá todo el texto por el humanizer. Sin em-dashes, sin voseo si el registro es neutro, sin significance inflation ni lenguaje promocional.
6. **CHECKLIST.** Corré el checklist "listo para publicar" de `store-standards §9`, incluido `description_lint.py` (con las keywords núcleo del cliente y la longitud target). Si algo falla, corregí ANTES de mostrar el preview. No muestres nada que no pase el checklist.
7. **PREVIEW.** Mostrá al cliente, en el chat, en texto plano y sin jerga: el "ASÍ ESTÁ AHORA" vs "ASÍ QUEDARÍA" de la descripción, el bloque "Cómo se va a ver en Google" (meta title + meta description en lenguaje simple), y "Qué mejoré" en bullets simples. Aclará: "En tu tienda los títulos se ven en negrita y las viñetas como lista." (Ver formato ejemplo abajo.)
8. **GATE.** Preguntá: "¿Lo aplico a tu tienda? Respondé **sí** o **no**." NO escribas nada hasta un "sí" explícito. Si dice no, no escribís.
9. **BACKUP (antes de escribir).** Guardá el valor VIEJO de los 3 campos en `clients/{slug}/backups/{productIdTail}-{YYYYMMDD-HHMMSS}.json` con este formato EXACTO (el hook lo exige):
   ```json
   { "productId": "gid://shopify/Product/123", "fields": { "descriptionHtml": "...viejo...", "seo_title": "...viejo...", "seo_description": "...viejo..." }, "ts": "2026-07-19T12:00:00" }
   ```
   `{productIdTail}` es la última parte del gid (ej: `123`). Las keys de `fields` son exactamente `descriptionHtml`, `seo_title`, `seo_description`. **Siempre respaldás los 3 juntos** (aunque solo cambies la descripción), porque el hook exige el set completo.
10. **ESCRIBIR (son DOS writes, porque el connector separa descripción y SEO).** Recién ahora:
    - **Descripción:** `Shopify:update-product` con `{ id: <GID>, descriptionHtml: <nuevo> }`.
    - **SEO:** `Shopify:graphql_mutation` con `productUpdate(product:{ id:<GID>, seo:{ title:<nuevo>, description:<nuevo> } })`. (Usá `product:`, NO `input:` que está deprecado.) **Antes de mandarla, validá con `Shopify:validate_graphql_codeblocks`.**
    El hook `backup_guard` verifica el backup en **ambos** writes; si falta, los bloquea.
11. **WORKLOG.** Agregá una entrada a `clients/{slug}/worklog.md`: `## YYYY-MM-DD [write] {producto} — backup: {archivo}`.
12. **CONFIRMAR.** "Listo ✅. Si no te convence, decime 'volvé a la anterior' y lo dejo como estaba."

## Preview — formato exacto (ejemplo blunua, ya humanizado y en registro neutro)

```
💍 Anillo NEXO Plateado — encontré la descripción actual y te propongo esta mejora:

ASÍ ESTÁ AHORA:
"Anillo NEXO de acero. Color plateado. Ajustable. Material resistente."

ASÍ QUEDARÍA:
  Anillo NEXO Plateado en acero quirúrgico, no irrita la piel

  Un anillo minimalista para todos los días. Se ve elegante pero sencillo, y está
  hecho en acero quirúrgico hipoalergénico que no destiñe ni irrita, incluso en
  pieles sensibles. Es parte de la colección NEXO, pensada para combinarse: funciona
  sola o en conjunto.

  Por qué dura:
  • Acero quirúrgico hipoalergénico, seguro para piel sensible y uso diario
  • Resistente al agua, no se oxida ni pierde el brillo
  • Diseño minimalista que combina con tu estilo sin robar protagonismo

  Preguntas frecuentes:
  • ¿Se puede mojar? Sí, resiste el agua sin problema.
  • ¿Sirve para piel sensible? Sí, el acero quirúrgico es hipoalergénico.
  • ¿Es ajustable? Sí, se adapta a tu dedo.

Cómo se va a ver en Google (título y resumen del buscador):
  Título: Anillo NEXO en acero quirúrgico hipoalergénico | blunua
  Resumen: Anillo minimalista que no irrita la piel, resiste el agua y dura.
           Ideal para uso diario y para regalar.

Qué mejoré:
✅ Agregué las palabras que la gente busca en Google
✅ Sumé preguntas frecuentes → ayuda a aparecer en respuestas de Google y ChatGPT
✅ Usé la voz de blunua: cercana y clara, sin exagerar
✅ Dejé claro el beneficio principal: no irrita, dura, para uso diario

(En tu tienda los títulos se ven en negrita y las viñetas como lista.)

¿Lo aplico a tu tienda? Respondé sí o no.
(si después no te convence, decime "volvé a la anterior" y lo dejo como estaba)
```

## Escritura en lote
Si el cliente pide varias ("mejorá las 12 descripciones de NEXO"): mismo flujo, pero el preview es un resumen de las 12, se guarda backup de las 12, y hay UN solo gate de confirmación para el lote. Nunca escribas sin ese gate.

## Revertir (undo)
Cuando el cliente dice "volvé a la anterior" (o similar):
1. Leé el valor ACTUAL de los 3 campos (`get-product`).
2. Escribí un backup fresco de ese valor actual (esto habilita también el *redo*) — mismo formato y carpeta.
3. Reescribí los valores VIEJOS del último backup: la descripción con `update-product` y el SEO con `graphql_mutation` (igual que el paso 10).
4. Append al worklog.

Importante: revertir es un write como cualquier otro, por eso backupea el valor actual PRIMERO. Así pasa el hook aunque hayan pasado horas desde el cambio original. NO depende de que exista un backup "reciente" previo.
