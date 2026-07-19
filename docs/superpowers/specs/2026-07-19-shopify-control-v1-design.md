# shopify-control v1 — Design Spec

- **Fecha:** 2026-07-19
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño aprobado en brainstorm, pendiente de review
- **Cliente piloto:** blunua (joyería de acero quirúrgico, COP/Colombia, Brain ID `LO4ob4dUxOggwTSlm07v`)

---

## 1. Contexto y objetivo

Worker quiere una herramienta para que un cliente de ecommerce **no técnico** controle y mejore su tienda Shopify hablándole a Claude (app de Claude o VSCode/Claude Code), sin depender de que Gabriel apruebe cada acción.

Casos de uso pedidos:
- Preguntar sobre resultados, stock y alertas de la tienda.
- Recomendaciones de combos en base a resultados.
- Mejorar descripciones de producto con criterio SEO y GEO.
- (Futuro) generar/variar imágenes de producto desde plantillas.
- (Futuro) subir productos cumpliendo los estándares de la tienda.

El piloto es **blunua**. La estructura se diseña para escalar a los ~15 ecommerce de Worker sin refactor.

---

## 2. Decisiones tomadas (brainstorm)

| # | Decisión | Elección |
|---|----------|----------|
| D1 | Forma de la solución | **Nativo en Claude** (connector + skills + base de conocimiento). Sin backend custom en v1. |
| D2 | Alcance del repo | **Un piloto (blunua) con estructura lista para escalar** (folder por cliente + `_template/`). |
| D3 | Fuente de datos de lectura (R1) | **Shopify directo** vía connector (sin depender del Brain en v1). |
| D4 | Alcance del v1 | **Directo al write win: mejorar descripciones (W1)**, más los read skills y la fundación. |
| D5 | Modelo de control | **Gabriel NO aprueba nada.** La seguridad la da la herramienta por diseño. |
| D6 | Interfaz del preview / OK | **Todo en el chat, texto claro sin jerga.** Sin HTML artifact (costo de tokens + no matchea Shopify). |
| D7 | Calidad de texto | **Humanizer obligatorio** antes de todo output + **registro definido por cliente** (blunua = español neutro, sin voseo). |

---

## 3. Arquitectura: 4 capas

La solución es la composición nativa de Claude, no un producto custom:

| Capa | Qué es | En blunua |
|------|--------|-----------|
| **Connector (MCP)** | Las manos: lee y escribe en Shopify | Connector oficial de Shopify (Admin API), scopes acotados |
| **Base de conocimiento** | El contexto curado que hace el output "de blunua" | `store-standards.md` + link a la memoria de marca en handsOn |
| **Skills** | Los procedimientos, on-demand | `mejorar-descripcion`, `reporte-tienda`, `armar-combo` |
| **Plugin** | El empaquetado para distribuir al cliente | shopify-control empaquetado (futuro, para el hand-off prolijo) |

**Sin backend custom en v1.** El connector oficial ya escribe; la seguridad y la calidad viven en los skills + hooks + base de conocimiento.

---

## 4. Alcance del v1

**Dentro:**
- Fundación: conexión de la tienda + doc de estándares (`store-standards.md`).
- `mejorar-descripcion` (W1): editar descripciones de producto con SEO/GEO, con flujo de escritura seguro.
- `reporte-tienda` (R1): Q&A read-only sobre resultados, stock y alertas.
- `armar-combo` (R2): recomendar combos como texto (no crea el combo en Shopify).
- Regla transversal de humanizer + registro + comunicación sin jerga.
- Estructura escalable (`clients/{slug}/` + `_template/`).

**Fuera del v1 (ver sección 13):**
- Generar/variar imágenes (W2).
- Subir productos nuevos (W3).
- Crear combos como write en Shopify.
- Input de enriquecimiento del Brain (Google Ads, Search Console, seo-gaps, co-compra).
- Empaquetado como plugin/connector propio para el hand-off final.

---

## 5. Estructura del repo

```
shopify-control/
├── CLAUDE.md                     ← contexto + convenciones + cómo arranca el cliente vs Gabriel
├── README.md                     ← entrada no técnica (para blunua)
├── .mcp.json                     ← config/instrucción de conexión al connector de Shopify
├── .claude/
│   ├── settings.json             ← hook guardrail: "no write sin backup logueado"
│   └── skills/
│       ├── mejorar-descripcion/  ← W1 (write win del v1)
│       ├── reporte-tienda/       ← R1 (Q&A / resultados / stock / alertas, read)
│       └── armar-combo/          ← R2 (recomendador de combos, read-only)
├── clients/
│   ├── _template/                ← scaffold del próximo cliente (escala sin refactor)
│   │   ├── CLAUDE.md
│   │   ├── store-standards.md
│   │   ├── connection.md
│   │   ├── worklog.md
│   │   └── backups/
│   └── blunua/
│       ├── CLAUDE.md             ← auto-load: contexto blunua + link a su folder en handsOn
│       ├── store-standards.md
│       ├── connection.md
│       ├── worklog.md
│       └── backups/
└── docs/superpowers/specs/       ← este spec
```

Decisiones de diseño:
1. `clients/{slug}/` sigue la convención de handsOn. El cliente arranca Claude desde `clients/blunua/` y se auto-carga su contexto scopeado (sin context bleed entre clientes).
2. `store-standards.md` es el artefacto nuevo (operación de producto). **Referencia** la `brand-voice.md` de blunua en handsOn, no la duplica.
3. `worklog.md` + `backups/` son la red de seguridad (el undo que el connector no trae).
4. El hook en `settings.json` puede forzar que no haya write sin backup logueado.
5. Los skills viven en el repo (un set sirve a todos los clientes); el contexto lo pone el folder del cliente.

---

## 6. Flujo de escritura seguro: `mejorar-descripcion`

**Campos en alcance para v1 (el "field set" canónico):** descripción (`body_html`), meta title (SEO) y meta description (SEO). El **handle/URL queda FUERA** (cambiarlo rompe la URL del producto y genera 404s). Estos 3 campos se leen, respaldan, previsualizan, escriben y revierten **siempre juntos, como un solo set**. Es la regla que mantiene el undo consistente.

Flujo fijo, siempre igual:

```
1. IDENTIFICAR    "mejorá la descripción del anillo NEXO plateado"
                  → el connector busca el producto. Si hay +1 match, muestra
                    opciones y pregunta cuál. NUNCA adivina qué producto editar.
2. LEER           el connector trae el estado actual de los 3 campos en alcance
                  (body_html + meta title + meta description) + contexto de solo
                  lectura (título del producto, tags, fotos) para razonar.
3. CARGAR CONTEXTO store-standards.md + brand-voice (link handsOn).
4. GENERAR        cuerpo según el molde canónico de store-standards §3
                  (título → hook → beneficios → material/garantía → bloque GEO Q&A),
                  con las keywords tejidas en el texto, + meta title + meta description.
4.5 HUMANIZER     pasada obligatoria (reusa handsOn/skills/humanizer). Sin em-dashes,
                  sin voseo (blunua = neutro), sin AI tells.
4.6 CHECKLIST     corre el checklist "listo para publicar" de store-standards.md.
                  Si algo falla, corrige antes de mostrar.
5. PREVIEW        ANTES vs DESPUÉS de los 3 campos, en el chat, texto claro, sin jerga
                  (incluye cómo se verán el título y el resumen en Google).
6. GATE           NADA se escribe hasta que el cliente dice "sí, aplicá". Explícito.
7. BACKUP         guarda los 3 campos viejos en backups/{producto}-{fecha}.md
                  + entrada en worklog. (el hook verifica que el backup existe)
8. ESCRIBIR       recién ahí el connector hace el update de los 3 campos en alcance.
                  NO toca precio, stock, status ni handle/URL.
9. CONFIRMAR      "Listo. Para revertir: 'volvé a la anterior'."
```

**Escritura en lote** (ej: las 12 descripciones de NEXO): mismo flujo, preview resumido de los 12, backup de los 12, un solo gate de confirmación. Nunca escribe sin ese gate.

**Undo:** un flujo `revertir` lee el último backup del producto y reescribe el valor viejo. El cliente revierte hablando, sin tocar Shopify.

### 6.1 Formato del preview (aprobado)

Todo en el chat, texto plano, cero jerga. Ejemplo real (ya humanizado + registro neutro):

```
💍 Anillo NEXO Plateado — encontré la descripción actual y te propongo esta mejora:

ASÍ ESTÁ AHORA:
"Anillo NEXO de acero. Color plateado. Ajustable. Material resistente."

ASÍ QUEDARÍA:
  Anillo NEXO Plateado en acero quirúrgico, no irrita la piel

  Un anillo minimalista para todos los días. Se ve elegante pero sencillo,
  y está hecho en acero quirúrgico hipoalergénico que no destiñe ni irrita,
  incluso en pieles sensibles. Es parte de la colección NEXO, pensada para
  combinarse: funciona sola o en conjunto.

  Por qué dura:
  • Acero quirúrgico hipoalergénico, seguro para piel sensible y uso diario
  • Resistente al agua, no se oxida ni pierde el brillo
  • Diseño minimalista que combina con tu estilo sin robar protagonismo

  Preguntas frecuentes:
  • ¿Se puede mojar? Sí, resiste el agua sin problema.
  • ¿Sirve para piel sensible? Sí, el acero quirúrgico es hipoalergénico.
  • ¿Es ajustable? Sí, se adapta a tu dedo.

Cómo se va a ver en Google (título y resumen del buscador):
  ANTES:    Anillo NEXO | blunua
            (sin resumen)
  QUEDARÍA: Anillo NEXO en acero quirúrgico hipoalergénico | blunua
            Anillo minimalista que no irrita la piel, resiste el agua y dura.
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

Nota: no se intenta replicar el look exacto de Shopify (setea expectativa con la línea aclaratoria).

---

## 7. Skills read-only

**`reporte-tienda` (R1):** responde preguntas de la tienda vía connector directo.
- Resultados: ventas, productos top, qué se mueve.
- Stock: bajo stock, agotados.
- Alertas: stock crítico, productos sin descripción o sin imagen (candidatos a mejorar).
- Read-only, cero riesgo. Output en texto simple, sin jerga. No escribe.

**`armar-combo` (R2):** recomienda combos/bundles.
- v1: mira el catálogo + la lógica de colección (NEXO "funciona sola o en conjunto") y **propone** combos como texto.
- No crea el combo en Shopify (eso es write, va a milestone posterior con gate).
- Placeholder para el input del Brain (co-compra real) que lo mejora mucho.

### 7.1 Skills reutilizados (no reinventamos el craft)

Los 3 skills del v1 son **orquestadores finitos** que componen skills existentes de handsOn + plugins. Lo nuevo es la orquestación + los guardrails + el `store-standards.md`; el "cómo se escribe bien" ya existe.

| Skill v1 | Reusa | Aporta |
|---|---|---|
| `mejorar-descripcion` | `humanizer`, `seo-geo` (data Princeton 2024), `generic-language-killer`, `voice-extractor` (onboarding), plugins `seo-schema`/`seo-content`/`seo-ecommerce` | tono sin AI tells, GEO+SEO real, QA anti-genérico, schema de producto |
| `reporte-tienda` | `ecommerce-marketing-manager`, `alerts-system`, `shopify-api` | leer métricas ecom, framing de alertas, campos Shopify |
| `armar-combo` | `ecommerce-marketing-manager`, `marketing-psychology` | lógica cross-sell/bundle, psicología de bundling |

Skill para construir los nuevos: `skill-creator`.

**Dependencia (importante):** estos skills viven en handsOn-Worker y en plugins. En el entorno de Gabriel están disponibles, así que el v1 (Gabriel operando) los invoca directo. Para el hand-off a blunua (su app de Claude) hay que **empaquetar los skills necesarios** junto con shopify-control (ver §13, D2). Verificar en planning qué skills son imprescindibles para el runtime del cliente vs cuáles son solo de setup (Gabriel).

---

## 8. store-standards.md (estructura)

Doc curado por cliente. Los campos marcados ⚠️ hay que completarlos con Gabriel/cliente.

```
1. MARCA (link, no duplica)
   → apunta a handsOn/clients/ecommerce/blunua/ (brand-voice, icp, avatares)
   → esencial inline: joyería acero quirúrgico, +10 años, minimalista, aesthetic

2. REGISTRO Y VOZ
   • Idioma: español NEUTRO, sin voseo (blunua es COP/Colombia)
   • Tono: amigable, sobrio, sin exagerar
   • Vocabulario SÍ: duradera, no irrita, segura, minimalista, hipoalergénico,
     resistente al agua, para regalar
   • Vocabulario NO: ⚠️ (nada de lujo-aspiracional, sin superlativos vacíos,
     sin imitar a Pandora/Two Pieces/Joboly/Acero & Piedra/Maria Grazia Severin)
   • Humanizer: OBLIGATORIO

3. ESTRUCTURA DE DESCRIPCIÓN (molde CANÓNICO — esta es la fuente de verdad)
   1) Título: [Producto] + [material/beneficio] + keyword
   2) Hook: 1-2 líneas
   3) Beneficios: 3 viñetas
   4) Material / garantía
   5) Bloque GEO: 2-4 preguntas frecuentes
   • Las keywords van TEJIDAS en el texto, no como bloque aparte.
   • meta title + meta description son campos SEO SEPARADOS (sección 4), no
     parte del cuerpo. Se escriben junto con el body como el "field set" del v1.
   • Longitud target: 80-150 palabras
   • NO incluir: precio en el texto, promesas de envío/stock

4. SEO
   • Keywords núcleo: acero quirúrgico, hipoalergénico, resistente al agua,
     joyería minimalista + ⚠️ (por categoría: anillos/collares/pulseras)
   • Meta title: patrón + máx ~60 caracteres   [EN ALCANCE del v1]
   • Meta description: patrón + ~155 caracteres [EN ALCANCE del v1]
   • Handle/URL: minúsculas-con-guiones, incluye keyword
     → convención SOLO para productos NUEVOS (W3 futuro). En v1 NO se
       edita el handle de un producto existente (rompe su URL).

5. GEO (búsqueda con IA)
   • Afirmaciones citables y directas (no "podría ser", sí "es")
   • Bloque Q&A en cada producto
   • Datos concretos > adjetivos vagos
   • (puede invocar los skills seo-geo existentes)

6. NAMING / TAGS / CATEGORÍAS
   • Nombre: [Colección] + [tipo] + [material] + [color]
   • Tags obligatorios: colección (NEXO/NUA), material, género
   • Taxonomía de colecciones: ⚠️ (mapear las colecciones reales)

7. PLANTILLAS DE IMAGEN [placeholder para W2 futuro]
   • Colores de marca: #4B4B4B / #9CB0B1 / #CEC4BA / #E9E6DD
   • Estilo: minimalista, fondo limpio + ⚠️ (specs cuando lleguemos a imágenes)

8. QUÉ NO TOCAR (alcance seguro)
   • Los skills solo tocan el field set del v1: body_html + meta title + meta description
   • NUNCA precio, stock, status ni handle/URL sin gate estructural (OK de Gabriel)
   • Star products (NEXO, NUA, colección general): cuidado extra

9. CHECKLIST "LISTO PARA PUBLICAR" (el skill lo corre antes del preview)
   ☐ pasó humanizer   ☐ registro neutro sin voseo   ☐ tiene keyword
   ☐ tiene bloque GEO  ☐ longitud OK   ☐ vocabulario de marca
   ☐ sin palabras prohibidas

10. SEÑALES DEL BRAIN [placeholder futuro]
    → keywords que convierten (seo-gaps), ángulos que ganaron (creative-intelligence),
      co-compra real (customer-intelligence). Enriquece 4 y 5.
```

El `_template/store-standards.md` es este mismo doc con los valores vaciados.

### 8.1 Dos velocidades: campos estables vs vivos

Los campos del doc no cambian al mismo ritmo:

- **ESTABLES (se definen 1 vez en el onboarding):** marca (1), registro y voz (2), estructura de descripción (3), naming/tags/taxonomía (6), plantillas de imagen (7), qué no tocar (8). Cambian poco.
- **VIVOS (se refrescan ~cada 3 meses):** keywords SEO núcleo y por categoría (4), señales GEO (5), y el placeholder de señales del Brain (10). El SEO/GEO decae: keywords que convertían dejan de hacerlo, Google AI Overviews cambia, hay estacionalidad.

**Ritual de refresh trimestral** (tarea de Gabriel/curador, el cliente no lo toca):
- Revisar y actualizar la sección viva: qué keywords convirtieron este período, qué queries nuevas aparecieron, qué ángulos estacionales aplican.
- Es el punto de entrada natural del input del Brain (sección 13): cada trimestre se tiran de Search Console / `seo-gaps` las keywords reales del período y se actualiza el doc.
- v1: refresh manual, apoyado en los skills `seo-geo` + `gsc-seo`. Futuro: semi-automático con el Brain.
- Patrón existente reutilizado: handsOn ya tiene `/client-refresh` + worklog; esto es lo mismo aplicado a la tienda.

---

## 9. Reglas transversales

- **Comunicación sin jerga:** el cliente nunca ve términos técnicos (ni nombres de campo, ni de skill, ni comandos). Entra en lenguaje natural, ve resultados en lenguaje natural. Regla en el `CLAUDE.md` del cliente, la respetan todos los skills.
- **Humanizer obligatorio** antes de todo output cliente (reusa `handsOn/skills/humanizer` + `humanizer-policy.md`). Mata em-dashes, gerundios finales, significance inflation, promotional, filler.
- **Registro por cliente** definido en `store-standards.md`. blunua = español neutro, sin voseo.
- **Preview + gate + backup + undo** en todo write (sección 6).

---

## 10. Conexión / setup (F1)

`connection.md` por cliente documenta: store domain, connector usado, scopes.

- El connector oficial de Shopify se conecta desde la app de Claude vía OAuth.
- Setup lo hace Gabriel: conecta el store de blunua + carga los standards, después se lo pasa listo al cliente.
- Scopes acotados para v1: lectura de productos/analytics (reportes) + `write_products` (descripciones). Nada más.
- ⚠️ La conexión OAuth es interactiva (la hace Gabriel/cliente en la app, no se puede automatizar desde una sesión headless).

---

## 11. Modelo de seguridad (consolidado)

Gabriel no es gate. La seguridad la dan 4 capas, en orden de fuerza:

1. **Alcance acotado por diseño del skill:** `mejorar-descripcion` solo toca el field set del v1 (`body_html` + meta title + meta description). No toca precio, stock, status ni handle/URL. El daño posible queda limitado a campos de texto reversibles.
2. **Backup obligatorio antes de todo write** + `PreToolUse` hook que bloquea la mutación de Shopify si no hay backup logueado en la sesión. El hook inspecciona los args de la llamada MCP (product id + campos a mutar) y exige que exista una entrada en `backups/` de ESE producto y ESOS campos, creada en la sesión actual; si el set de campos del backup no cubre el set del write, bloquea. (Seguridad en la herramienta, no solo en la instrucción del skill.)
3. **Preview + confirmación explícita** del cliente antes de escribir.
4. **Undo en 1 paso** desde el último backup.

Nota honesta: el connector oficial escribe **inmediato, sin rollback nativo**. Por eso el backup/undo lo implementa el skill. El único escenario que justificaría un MCP custom es querer que sea *físicamente imposible* (no "el skill no lo hace") que el cliente toque algo peligroso. No es necesario para el v1 ni para el hand-off de descripciones. Ver sección 13.

---

## 12. Escalar a más clientes

- Cliente nuevo = copiar `clients/_template/`, completar los campos ⚠️ de `store-standards.md`, documentar `connection.md`, conectar el connector.
- Los skills no se tocan (sirven a todos). El contexto lo pone el folder del cliente.

---

## 13. Fuera del v1 / futuro

Ordenado por valor/proximidad estimada:

- **W1.5 — Input del Brain (enriquecimiento):** alimentar descripciones y combos con señales de performance (Google Ads, Search Console, `get_seo_gaps`, `get_creative_intelligence`, `get_customer_intelligence`). Las reglas siguen en `store-standards.md`; el Brain aporta la evidencia. Opt-in, no cambia el core. Se ejecuta dentro del **ritual de refresh trimestral** (§8.1), que es donde la parte viva de los estándares se actualiza.
- **W2 — Imágenes:** generar/variar imágenes de producto desde plantillas (sección 7 de standards). Referencia técnica: `miller-joe/shopify-mcp` ya combina productos + imágenes IA.
- **W3 — Subir productos nuevos** cumpliendo estándares (status `draft` por defecto, gate estructural).
- **Combos como write:** crear el bundle en Shopify (hoy `armar-combo` solo propone).
- **D2 — Empaquetado para el hand-off:** shopify-control como plugin/connector propio para el cliente en la app de Claude (candidato: patrón tipo ShopMCP). Incluye **empaquetar los skills reutilizados imprescindibles** para el runtime del cliente (§7.1), no solo los skills nuevos.
- **Onboarding y refresh como skills:** `onboardear-cliente` (llena los inputs de §16 una vez) y `refrescar-estandares` (corre el ritual trimestral de §8.1). En v1 son tareas manuales de Gabriel.
- **Preview con botón interactivo** (artifact runtime) en vez de responder por texto, si se justifica.
- **MCP custom constrained:** solo si se necesita hacer imposible por diseño el acceso a ops peligrosas.

---

## 14. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Write inmediato sin rollback nativo del connector | Backup obligatorio + hook + undo en 1 paso (sección 11) |
| Cliente no técnico se asusta con jerga y no confía | Regla sin-jerga + preview claro + gate simple sí/no (secciones 6.1, 9) |
| Output suena a IA y daña la marca | Humanizer obligatorio + checklist (secciones 8.9, 9) |
| Registro equivocado (voseo en tienda colombiana) | Registro fijado en store-standards.md por cliente |
| Connector expone ops peligrosas (borrar, precios) | Scope acotado + skill que no las incluye; MCP custom solo si hace falta |
| Ambigüedad de producto al editar | Paso 1 nunca adivina: muestra matches y pregunta |
| Skills reutilizados no disponibles en el entorno del cliente | En v1 opera Gabriel (los tiene). Para el hand-off se empaquetan los imprescindibles (§7.1, §13 D2) |
| SEO/GEO se congela el día de la instalación | Estándares con parte viva + ritual de refresh trimestral (§8.1) |

---

## 15. Testing / validación

- Probar `mejorar-descripcion` end-to-end en un **producto de prueba** de blunua (o store de desarrollo) antes de tocar productos reales.
- Verificar que el hook bloquea un write sin backup, y también un write cuyos campos no estén todos cubiertos por el backup.
- Verificar el undo: revertir deja los **3 campos** (`body_html` + meta title + meta description) idénticos al original.
- Verificar que el humanizer + checklist frenan un output con em-dashes / voseo / sin keyword.
- Verificar el flujo de lote (gate único, backups completos de los 3 campos por producto).
- Verificar (planning-time) que Claude Code descubre los skills de `.claude/skills/` del root cuando el cliente arranca desde `clients/blunua/`; si no, ajustar dónde viven los skills o desde dónde arranca.

---

## 16. Inputs de onboarding (⚠️ a completar al instalar, no son gaps de diseño)

Estos NO son huecos del diseño: son datos del cliente que Gabriel (curador) completa **una vez al instalar** la herramienta en el cliente, más algunos que se **refrescan cada trimestre** (ver §8.1).

**Se definen 1 vez (onboarding):**
1. Vocabulario prohibido de blunua (sección 2 de standards).
2. Taxonomía real de colecciones de la tienda de blunua (sección 6).
3. Store domain de blunua + confirmación de scopes disponibles en el plan de Shopify.
4. ¿El cliente de blunua es la persona que va a usar la herramienta, o alguien de su equipo? (afecta la simplicidad del onboarding).

**Se refrescan cada ~3 meses (parte viva, §8.1):**
5. Keywords SEO por categoría de producto (anillos/collares/pulseras) y señales GEO. Apoyado en `seo-geo` + `gsc-seo`, y a futuro en el input del Brain.

El onboarding y el refresh son tareas de Gabriel, no del cliente. Candidatos a futuros skills: `onboardear-cliente` y `refrescar-estandares`.

---

## 17. Dependencias técnicas verificadas

- El connector oficial de Shopify en Claude escribe vía **Admin API** (crea/edita productos, variantes, precios, colecciones, stock). Requiere scopes `read_products` + `write_products`.
- Hay 3 tipos de MCP de Shopify: **Storefront** (read, customer-facing), **Sidekick** (IA dentro del admin), **Admin/Dev** (read-write). Usamos Admin.
- Los writes del connector son inmediatos, sin capa de borrador ni rollback: el backup/undo es responsabilidad nuestra (skill).
- Post-enero 2026, los apps de Shopify usan Client ID + Client Secret del Dev Dashboard.

Fuentes: shopify.dev (Storefront/Admin MCP docs), claudefa.st (Shopify MCP for Claude Code 2026), github.com/miller-joe/shopify-mcp, polaranalytics.com (Shopify MCP guide), claude.com/connectors/shopify.
