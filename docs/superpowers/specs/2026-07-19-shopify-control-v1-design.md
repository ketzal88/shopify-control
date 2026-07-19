# shopify-control v1 — Design Spec

- **Fecha:** 2026-07-19
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** v1 construido y validado end-to-end contra el connector real. Este doc está **actualizado a lo que se construyó** (2026-07-19): las secciones con nota "corregido en implementación" difieren del diseño original a propósito.
- **Cliente piloto:** blunua (joyería de acero quirúrgico, COP/Colombia, Brain ID `LO4ob4dUxOggwTSlm07v`)

---

## 1. Contexto y objetivo

Worker quiere una herramienta para que un cliente de ecommerce **no técnico** controle y mejore su tienda Shopify hablándole a Claude, sin depender de que Gabriel apruebe cada acción.

> **Corregido en implementación:** el runtime del v1 es **VS Code + la extensión de Claude Code, abierta en la RAÍZ de este repo**. No el app de Claude pelado. El app no carga los skills ni los hooks, así que el connector escribiría sin ninguna de las capas de seguridad de §11. Ver §10.

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
│   ├── settings.json             ← permissions.deny + registro de hooks (propios y del framework)
│   ├── hooks/
│   │   ├── backup_guard.py       ← guard de writes: alcance de tool, alcance de campos, backup
│   │   └── description_lint.py   ← linter mecánico del checklist (ejecutable por CLI)
│   └── skills/
│       ├── mejorar-descripcion/  ← W1 (write win del v1)
│       ├── reporte-tienda/       ← R1 (Q&A / resultados / stock / alertas, read)
│       └── armar-combo/          ← R2 (recomendador de combos, read-only)
├── core/                         ← claude-code-framework de Worker (hooks de calidad/seguridad)
├── stack.json                    ← manifest del framework: test, secret-scan, pre-push, close-protocol
├── tests/                        ← pytest de backup_guard, description_lint y secret-scan
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
1. ~~El cliente arranca Claude desde `clients/blunua/` y se auto-carga su contexto scopeado.~~ **Corregido en implementación: la sesión se abre SIEMPRE en la RAÍZ del repo, nunca en `clients/{slug}/`.** Claude Code busca `.claude/` en la carpeta que abrís: desde el subfolder no hay hooks ni skills, pero el connector de Shopify **sí sigue estando disponible y escribiendo**. Es la peor combinación posible (manos sin guardrails), así que abrir el subfolder queda prohibido. `clients/{slug}/` sigue siendo la convención de handsOn para guardar el contexto, pero ese contexto ya no se auto-carga.
   - **Corolario:** como el contexto del cliente no entra solo, **los tres skills arrancan con un paso 0 obligatorio**: identificar el cliente activo, leer su `CLAUDE.md` + `store-standards.md`, y confirmar con `Shopify:get-shop-info` contra qué tienda está apuntando el connector, comparándola con `connection.md`. Si no coinciden, se aborta. (`switch-shop` existe: la tienda conectada no es un dato asumible.)
2. `store-standards.md` es el artefacto nuevo (operación de producto). **Referencia** la `brand-voice.md` de blunua en handsOn, no la duplica.
3. `worklog.md` + `backups/` son la red de seguridad (el undo que el connector no trae).
4. El hook en `settings.json` fuerza que no haya write sin backup logueado, y además acota qué campos puede tocar cada write (§11).
5. Los skills viven en el repo (un set sirve a todos los clientes); el contexto lo pone el folder del cliente.
6. `core/` + `stack.json` son el **claude-code-framework de Worker**, adoptado config-driven. Aporta gates de repo (secret-scan en commit, tests en pre-push, `push: operator-only`, close-protocol) que **conviven** con los guardrails propios: los del framework matchean `Bash` (commits/pushes), el nuestro matchea `.*` (los writes de Shopify). Ver §11 capa 4.

---

## 6. Flujo de escritura seguro: `mejorar-descripcion`

**Campos en alcance para v1 (el "field set" canónico):** descripción (`descriptionHtml`), meta title (`seo.title`) y meta description (`seo.description`). El **handle/URL queda FUERA** (cambiarlo rompe la URL del producto y genera 404s). Estos 3 campos se leen, respaldan, previsualizan, escriben y revierten **siempre juntos, como un solo set**. Es la regla que mantiene el undo consistente.

> **Corregido en implementación (vocabulario real del connector).** El diseño original decía `body_html` y hablaba de un solo write. Contra el connector oficial son **dos writes distintos**:
> - **Descripción:** `Shopify:update-product` con `{ id, descriptionHtml }`.
> - **SEO:** `Shopify:graphql_mutation` con `productUpdate(product:{ id, seo:{ title, description } })`. Se usa `product:`, no `input:` (deprecado).
>
> Y **dos lecturas distintas**, que es donde estuvo el bug real:
> - **Descripción:** `Shopify:get-product` → `descriptionHtml`.
> - **SEO:** `Shopify:graphql_query` → `product(id:$id){ seo { title description } }`.
>
> ⚠️ **`get-product` NO devuelve el SEO.** Backupear lo que devuelve `get-product` y nada más deja el backup con el SEO vacío, y entonces un "vuelve a la anterior" **borra** el título y el resumen SEO reales del cliente en vez de restaurarlos. Pasó de verdad; por eso el guard hoy exige que el backup traiga valores string no vacíos (§11 capa 2).
>
> **El SEO NO va por metafields.** El diseño y el plan asumían los metafields `global.title_tag` / `global.description_tag`. Es falso para este camino: el SEO se lee y se escribe como el campo nativo `seo` del producto.

Flujo fijo, siempre igual:

```
1. IDENTIFICAR    "mejorá la descripción del anillo NEXO plateado"
                  → el connector busca el producto. Si hay +1 match, muestra
                    opciones y pregunta cuál. NUNCA adivina qué producto editar.
2. LEER           el estado actual de los 3 campos, en DOS lecturas: get-product
                  para descriptionHtml y graphql_query para seo{title,description}
                  (get-product no trae el SEO), + contexto de solo lectura
                  (título del producto, tags, fotos) para razonar.
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
7. BACKUP         guarda los 3 campos viejos en backups/{productIdTail}-{fecha}.json
                  + entrada en worklog. (el hook verifica que el backup existe,
                  que cubre los 3 campos y que los valores son REALES)
8. ESCRIBIR       recién ahí, DOS writes: update-product para la descripción y
                  graphql_mutation (productUpdate) para el SEO.
                  NO toca precio, stock, status ni handle/URL.
9. CONFIRMAR      "Listo. Para revertir: 'volvé a la anterior'."
```

> **Formato de backup: `.json`, no `.md`.** El diseño original decía `.md`; el plan lo cambió a `.json` **a propósito** y así quedó implementado, porque el hook tiene que leerlo programáticamente para decidir si permite el write. No "corregirlo" de vuelta a `.md`. Contrato exacto:
>
> ```json
> { "productId": "gid://shopify/Product/123",
>   "fields": { "descriptionHtml": "...", "seo_title": "...", "seo_description": "..." },
>   "ts": "2026-07-19T12:00:00" }
> ```
>
> Las keys de `fields` son exactamente esas tres y van **siempre juntas**. El campo `ts` es informativo: la frescura la mide el guard por el mtime del archivo, no por `ts`.

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

> **Corregido en implementación:** el `humanizer` **no es invocable como skill desde este repo** (vive en handsOn-Worker, que no es un skill descubrible acá). Sigue siendo obligatorio, pero se cumple leyendo `handsOn-Worker/skills/humanizer/SKILL.md` y aplicando sus reglas a mano. Es una dependencia de disponibilidad, no de diseño: refuerza que el empaquetado (§13, D2) es condición para el hand-off.

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
   • Los skills solo tocan el field set del v1: descriptionHtml + seo.title + seo.description
   • NUNCA precio, stock, status ni handle/URL sin gate estructural (OK de Gabriel)
   • Star products (NEXO, NUA, colección general): cuidado extra

9. CHECKLIST "LISTO PARA PUBLICAR" (el skill lo corre antes del preview)
   ☐ pasó humanizer   ☐ registro neutro sin voseo   ☐ tiene keyword
   ☐ tiene bloque GEO  ☐ longitud OK   ☐ vocabulario de marca
   ☐ sin palabras prohibidas
   → La mayoría de estos ítems los chequea MECÁNICAMENTE description_lint.py,
     que se corre por CLI sobre el TEXTO PLANO (no el HTML):
       python .claude/hooks/description_lint.py --keywords "..." --dialect neutro
     Cubre: em-dash, longitud, keyword, materiales falsos (oro/plata/chapado),
     lujo-vacío, claims médicos, voseo y presencia de bloque GEO.
     Quedan a mano: que el humanizer haya corrido y el vocabulario de marca.

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

**Dónde se abre la sesión (decisión tomada, no negociable):** siempre en la **RAÍZ del repo**, desde VS Code con la extensión de Claude Code, logueado con la cuenta que tiene el connector. Nunca en `clients/{slug}/` ni en el app de Claude pelado: en esos dos casos el connector escribe igual pero no se cargan los skills ni los hooks, así que se pierden todas las capas de §11. Ver §5, decisión 1.

**El connector no está anclado a una tienda.** `switch-shop` existe y la conexión puede estar apuntando a otra tienda de la que uno cree. Por eso los skills verifican con `get-shop-info` contra `connection.md` antes de operar, y abortan si no coinciden.

---

## 11. Modelo de seguridad (consolidado)

Gabriel no es gate. La seguridad la da la herramienta.

> **Corregido en implementación.** El diseño original ponía casi todo el peso en una capa (el hook de backup) y confiaba el alcance a la **prosa del skill**. Eso dejaba dos agujeros reales: (a) las tools peligrosas del connector seguían siendo alcanzables, y (b) un backup válido funcionaba como llave de 15 minutos para escribir *cualquier* campo, incluido precio o status. Hoy el alcance está enforced por código, en cuatro capas independientes.

### Capa 1: `permissions.deny` (la tool ni siquiera es alcanzable)

En `.claude/settings.json`, 7 tools de escritura del connector están denegadas a nivel de permisos, así que no hay skill ni prompt que las invoque:

`set-inventory`, `bulk-update-product-status`, `create-discount`, `create-product`, `create-collection`, `update-collection`, `add-to-collection`.

Es la capa más fuerte porque no depende de que nadie razone bien. Aproxima el "físicamente imposible" que antes se pensaba que requería un MCP custom.

### Capa 2: `backup_guard.py` (`PreToolUse`, matcher `.*`), que hace alcance de tool, alcance de CAMPOS y backup

Hace tres cosas, no una:

1. **Alcance de tool.** Las mismas 7 acciones de la capa 1, más una lista de mutaciones GraphQL prohibidas (`productDelete`, `productVariantsBulkUpdate`, `productChangeStatus`, `inventorySetQuantities`, `collectionUpdate`, `publishablePublish`, etc.), se bloquean siempre. No hay backup que las habilite. Es defensa en profundidad: cubre el camino GraphQL, que `permissions.deny` no puede enumerar.
2. **Alcance de campos** (esto es lo nuevo). Un `update-product` solo puede traer `{id, descriptionHtml}`; una mutación de producto solo `{id, descriptionHtml, seo}`. Cualquier otra key de primer nivel (handle, status, title, tags, variants, images) bloquea. Para el camino GraphQL el guard lee **el query y también `tool_input.variables`**: mirar solo el string del query dejaba pasar cualquier `productUpdate` parametrizado, que es la forma idiomática de escribir GraphQL.
3. **Backup con valores reales.** Sigue exigiendo un backup reciente (15 min) que cubra los 3 campos, y además valida que los valores sean strings y no estén los tres vacíos. Un backup de placeholders satisfacía el guard viejo y hacía que el undo borrara la descripción original en vez de restaurarla.

**Contrato de bloqueo: `exit 2`.** Claude Code bloquea un tool **solo** con exit 2; un `exit 1` es un error no-bloqueante y el tool se ejecuta igual. No es un detalle: fue exactamente el bug que tuvo el secret-scan del framework (ver `docs/HANDOFF.md` #1b). Ante una excepción inesperada sobre un tool de Shopify, el guard **falla cerrado** (bloquea).

### Capa 3: `description_lint.py` (calidad enforced, no autorreportada)

Antes cubría 3 ítems del checklist y **no era ejecutable** (no tenía CLI), así que el "corré el lint" del skill era autorreportado. Hoy se corre de verdad por CLI, sobre el texto plano, y bloquea: materiales falsos (oro/plata/chapado, cuando el material es acero quirúrgico), lujo-vacío y superlativos, claims médicos, voseo cuando el registro es neutro, más em-dash, longitud, keyword y presencia de bloque GEO.

Sigue siendo **advisory respecto del write** (lo corre el skill antes del preview; no es un `PreToolUse` que corte la mutación). Protege la marca, no la tienda.

### Capa 4: el framework de Worker (`core/` + `stack.json`), gates de repo

Adoptado config-driven, matcher `Bash`, conviviendo con el guard propio:

- **secret-scan** bloqueante en cada `git commit` (tokens de tienda, API keys).
- **pre-push** corre los tests (`python -m pytest -q`); `push: operator-only`.
- **close-protocol** bloqueante si el turno cierra con código sin commitear.
- **canonical-guard** sobre los comandos prohibidos declarados en `stack.json`.

Es la capa que protege el repo (que la herramienta no filtre credenciales ni se degrade), no la tienda del cliente.

### Y encima de las cuatro
- **Preview + confirmación explícita** del cliente antes de escribir.
- **Undo en 1 paso** desde el último backup.

Nota honesta: el connector oficial escribe **inmediato, sin rollback nativo**. Por eso el backup/undo lo implementa el skill.

**Límites conocidos y aceptados** (ver §15): la frescura del backup es un proxy, el glob de backups no está scopeado por cliente, y las capas 2 y 3 no cubren un bypass por shell.

---

## 12. Escalar a más clientes

- Cliente nuevo = copiar `clients/_template/`, completar los campos ⚠️ de `store-standards.md`, documentar `connection.md`, conectar el connector.
- Los skills no se tocan (sirven a todos). El contexto lo pone el folder del cliente.
- Los guardrails tampoco se tocan: `permissions.deny`, `backup_guard` y los gates del framework son del repo, así que un cliente nuevo los hereda sin configurar nada. Es la razón principal por la que la sesión se abre en la raíz (§5, decisión 1).

**A cerrar antes del 2º cliente (no se dispara con uno solo):**
- **Scoping multi-cliente del backup.** El glob de `backup_guard` es repo-wide (`**/backups/{tail}-*.json`) y los gid de Shopify son **por tienda**: dos tiendas distintas pueden tener `Product/123`. Con un cliente no hay colisión posible; con dos, el backup de un cliente podría habilitar un write sobre el otro. Hay que limitar la búsqueda a la carpeta del cliente activo, o incluir el store domain en el match.
- **Confirmación de tienda por sesión.** El paso 0 de los skills (`get-shop-info` vs `connection.md`) ya cubre el caso "el connector apunta a otra tienda", pero es una verificación del skill, no del guard. Con varios clientes conviene bajarla también a código.

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
- **MCP custom constrained:** casi descartado. `permissions.deny` + el alcance de campos del guard (§11, capas 1 y 2) ya dan el "imposible por diseño" que motivaba esta idea, sin mantener un MCP propio. Solo volvería a la mesa si hiciera falta cubrir un actor con acceso a shell, que hoy está fuera del modelo de amenaza (§15).

---

## 14. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Write inmediato sin rollback nativo del connector | Backup obligatorio + hook + undo en 1 paso (sección 11) |
| Cliente no técnico se asusta con jerga y no confía | Regla sin-jerga + preview claro + gate simple sí/no (secciones 6.1, 9) |
| Output suena a IA y daña la marca | Humanizer obligatorio + checklist (secciones 8.9, 9) |
| Registro equivocado (voseo en tienda colombiana) | Registro fijado en store-standards.md por cliente |
| Connector expone ops peligrosas (borrar, precios) | Resuelto por código, no por prosa: `permissions.deny` sobre 7 tools de escritura + lista de mutaciones GraphQL prohibidas y alcance de campos en `backup_guard` (§11, capas 1 y 2) |
| Sesión abierta en el subfolder o en el app pelado: connector con manos, sin guardrails | Regla dura: la sesión se abre siempre en la raíz (§5 decisión 1, §10) + paso 0 de los skills que confirma cliente y tienda |
| El connector apunta a otra tienda de la que uno cree (`switch-shop`) | Paso 0: `get-shop-info` contra `connection.md`, y se aborta si no coinciden (§10) |
| Un backup de placeholders o con el SEO vacío hace que el undo borre en vez de restaurar | El guard exige valores string no vacíos; el skill lee el SEO con `graphql_query` porque `get-product` no lo trae (§6, §11 capa 2) |
| Ambigüedad de producto al editar | Paso 1 nunca adivina: muestra matches y pregunta |
| Skills reutilizados no disponibles en el entorno del cliente | En v1 opera Gabriel (los tiene). Para el hand-off se empaquetan los imprescindibles (§7.1, §13 D2) |
| SEO/GEO se congela el día de la instalación | Estándares con parte viva + ritual de refresh trimestral (§8.1) |

---

## 15. Testing / validación

**Ya verificado** (dev store *Testing StandAlone Framework*, producto *The Complete Snowboard*; detalle en `docs/HANDOFF.md` y en `clients/blunua/worklog.md`):

- ✅ `mejorar-descripcion` end-to-end contra el connector real: leer los 3 campos, generar, preview, gate, backup, los dos writes (`update-product` + `productUpdate`), verificado por read-back del Admin API.
- ✅ **El hook bloquea un write sin backup.** Verificado en sesión fresca de VS Code, por comportamiento: un `update-product` sin backup previo se corta con *"Sin backup reciente…"*. El matcher `.*` captura el nombre MCP real (`mcp__claude_ai_Shopify__update-product`) y el guard lo reduce bien a `update-product`.
- ✅ **El contrato de bloqueo es `exit 2`.** Un `exit 1` NO bloquea: es un error no-bloqueante y el tool se ejecuta igual. Se descubrió porque el secret-scan del framework devolvía 1 y por eso nunca bloqueó un commit, en ninguna plataforma (`HANDOFF.md` #1b).
- ✅ Undo y redo: ciclo reversible probado, inmediato y diferido.
- ✅ `reporte-tienda` y `armar-combo`: lectura contra el connector real, sin escribir nada.
- ✅ `pytest`: 18 tests verdes (backup_guard, description_lint, secret-scan con su regresión de CRLF).
- ✅ **Descubrimiento de hooks y skills desde el subfolder: NO funciona.** Abrir `clients/blunua/` deja la sesión sin `.claude/`, o sea sin hooks ni skills, mientras el connector sigue escribiendo. Resuelto por decisión, no por workaround: la sesión se abre siempre en la raíz (§5, decisión 1; §10).

**Límites conocidos y aceptados del v1** (se están cerrando en la tanda actual):

- **Frescura del backup: es un proxy.** El guard exige "existe algún backup cubriente con mtime < 15 min", no "se respaldó exactamente el valor que se está por sobrescribir". Riesgo bajo mientras sea single-operator y secuencial.
- **Scoping multi-cliente:** el glob de backups es repo-wide y los gid son por tienda. Ver §12.
- **Bypass por shell:** las capas 1 a 3 cubren los tools del connector. Nada impide que alguien con acceso al repo llame al Admin API por su cuenta desde una terminal. El modelo de amenaza del v1 es "el operador o el cliente se equivocan", no "un actor hostil con shell".
- **`description_lint` es advisory** respecto del write: corre en el checklist del skill, no como gate duro.

**Pendiente de verificar:**
- El flujo de lote (gate único, backups completos por producto, revalidación de la ventana de 15 min a mitad de lote).
- Todo lo anterior contra la tienda **real** de blunua, no la dev store.

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

**Verificado contra el connector real (2026-07-19):**
- La descripción se escribe con `Shopify:update-product` (`descriptionHtml`) y se lee con `Shopify:get-product`.
- El SEO se escribe con `Shopify:graphql_mutation` → `productUpdate(product:{ id, seo:{ title, description } })` y se lee con `Shopify:graphql_query` → `product(id:$id){ seo { title description } }`. **No** se usan los metafields `global.title_tag` / `global.description_tag`: esa suposición del diseño original era falsa para este camino.
- `get-product` **no devuelve** el bloque `seo`. Es la causa del bug de backup con SEO vacío (§6).
- En `productUpdate` se usa el argumento `product:`; `input:` está deprecado.
- `Shopify:validate_graphql_codeblocks` sirve para validar la mutación antes de mandarla.

Fuentes: shopify.dev (Storefront/Admin MCP docs), claudefa.st (Shopify MCP for Claude Code 2026), github.com/miller-joe/shopify-mcp, polaranalytics.com (Shopify MCP guide), claude.com/connectors/shopify.
