# Canales de marketing digital — Design Spec

- **Fecha:** 2026-07-20
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** diseñado, sin implementar.
- **Cliente piloto:** blunua
- **Spec padre:** `2026-07-19-shopify-control-v1-design.md`
- **Research base:** `docs/research/2026-07-19-worker-brain-integration.md` (este spec **reabre y
  reemplaza su Decisión #1**, ver §4)
- **Revisión:** rev.3 — cerrado tras 2 rondas de review (7 correcciones). Listo para planificar.

---

## 1. Contexto y objetivo

Hoy shopify-control entiende **la tienda**. `reporte-tienda` ya consulta Worker Brain para preguntas
de negocio, pero el conocimiento de cómo se lee cada canal vive disperso: parte en el research, parte
en la cabeza del operador, nada en el repo.

**Objetivo:** que el repo entienda lo que pasa a nivel de marketing digital general —Google Ads,
Search Console, GA4, Meta (ads, pixel, catálogo), Merchant Center, Klaviyo— y **obre sobre la tienda
en base a eso**. El diagnóstico es multi-canal; la ejecución sigue siendo sobre Shopify.

Es una capa que se va a seguir ampliando (más canales, más acciones), así que el diseño se optimiza
para que **agregar un canal sea mecánico** y no requiera rediseñar nada.

---

## 2. Decisiones tomadas (brainstorm)

| # | Decisión | Elección |
|---|----------|----------|
| C1 | Forma de la capa de conocimiento | **Referencia por canal** (`.claude/channels/*.md`), NO un skill por plataforma. Ver §3.1 |
| C2 | Audiencia | **El cliente no técnico** (+ Claude como consumidor interno). Reabre D#1 del research |
| C3 | Alcance de acción | **Lee todos los canales, escribe solo en la tienda.** El canal se diagnostica, la tienda se cura |
| C4 | Corte de visibilidad | **El canal clasifica, el cliente autoriza.** Ver §4 |
| C5 | Merchant Center | **Fuera de M1.** No existe data en Brain (§6). Proyecto propio |
| C6 | Pixel + Catálogo de Meta | Brain los calcula pero **no los expone por MCP**. Requiere trabajo en `ai-analyzer` (§6) |
| C7 | Campos de feed fuera de alcance de escritura | **Se diagnostican, no se corrigen** en M1. Ampliación posterior con el patrón escalones (§7) |
| C8 | Skills nuevos en M1 | **Uno solo: `cubrir-demanda`.** Más `reporte-tienda` ampliado. Nada más (YAGNI) |
| C9 | Reglas que valen para todos los canales | Van a **`_comun.md`**, no duplicadas en cada canal ni encerradas en un skill. Ver §3.1.2 |

---

## 3. Arquitectura: dos capas + una política

### 3.1 Capa de referencia — `.claude/channels/`

**No son skills.** No tienen frontmatter, no se auto-disparan, no compiten por activarse. Los lee un
skill de intención con `Read`, igual que el repo ya hace con `humanizer`.

**Por qué no un skill por plataforma:** Claude elige skills matcheando la `description` contra lo que
dice el cliente. El cliente nunca dice *"revisá GA4"*; dice *"¿por qué bajaron las ventas?"* — una
pregunta que cruza cuatro canales. Seis skills por plataforma se solaparían, competirían por
dispararse, y ninguno respondería solo la pregunta real. La descomposición del repo es **por
intención** (`mejorar-descripcion`, `armar-combo`, `armar-escalones`) y esta capa la respeta.

**Beneficio secundario:** costo de contexto. Una pregunta de Search Console lee dos `.md`, no siete.

#### 3.1.1 Los archivos por canal — 7 bloques fijos

Mismo orden y mismos títulos en todos, para que agregar un canal sea mecánico:

| # | Bloque | Para qué |
|---|---|---|
| 1 | Qué es este canal, en una frase de cliente | Que nunca se nombre en jerga |
| 2 | **De dónde sale la data:** tool MCP exacto + campos | Sin esto el skill inventa |
| 3 | Qué significa "fresco" en este canal | La *política* de frescura vive en `_comun.md`; acá va la particularidad |
| 4 | Diccionario de traducción: métrica → frase natural | Dos columnas: término crudo → frase de cliente |
| 5 | **Clasificación de visibilidad**, en dos columnas: dato → nivel (`diagnostico`/`plata`/`adOps`) | Ver §4 |
| 6 | **Qué acción en la tienda corrige qué problema del canal** | El puente diagnóstico→ejecución |
| 7 | Trampas conocidas de este canal | Absolutos sumados, ads de marca intencionales, etc. |

**Los archivos por canal son client-agnostic.** No mencionan a ningún cliente. El bloque 5
**clasifica** (este dato es `plata`); no decide si se muestra — eso es del cliente (§4).

**El bloque 6 es la razón de ser de esta capa.** Es lo que convierte "entender marketing" en "obrar
en la tienda". Ejemplos ya validados contra data real de blunua:

| Señal del canal | Acción en la tienda |
|---|---|
| GSC: término pago sin contenido orgánico (`aretes hipoalergénicos`, 148 casos) | Escribir esa descripción → baja dependencia de Ads |
| GSC: muchas impresiones, pocos clicks | Reescribir meta title/description |
| GSC: ya rankea sin cobertura paga (`anillos` pos. 8.0) | Reforzar ese contenido |
| Meta Catálogo: ítem rechazado por descripción faltante | Completar la descripción |
| Merchant: producto desaprobado por campo fuera de alcance | **Anotar para el equipo** (§7) |

#### 3.1.2 `_comun.md` — lo que vale para todos los canales

Las reglas transversales **no se duplican en cada canal ni se encierran en un skill**, porque
aplican a `reporte-tienda` y a `cubrir-demanda` por igual. Duplicarlas en dos skills es el mismo
modo de falla que duplicarlas en cinco canales.

Contiene:
1. Política de frescura: qué se hace cuando un canal no está `ok` (§8.2).
2. Deltas sobre absolutos (§8.4).
3. Validez de atribución (§8.3).
4. Filtro de `suggestedAction` contra `store-standards.md` (§8.1).
5. **Mecánica del corte de visibilidad**: cómo se lee `channel-visibility.json` y cómo compone con
   el bloque 5 (§4).
6. Cero jerga y traducción de métricas transversales (ticket promedio, visitas, conversión) — la
   tabla que hoy vive inline en `reporte-tienda`.
7. **El punto de entrada a Brain:** dónde sale el `Brain ID` (`clients/{slug}/CLAUDE.md`), la regla
   de entrar siempre por `get_client_brief` —que trae la frescura de **todos** los canales en una
   llamada—, y la **degradación elegante**: si el cliente no tiene `Brain ID` cargado o Brain no
   responde, se sigue con Shopify solo y **no se lo menciona**. No es un error que haya que
   explicarle a nadie.

**Regla de orden de lectura, para todo skill que toque canales:** primero `_comun.md`, después el/los
`.md` de canal que hagan falta, después `channel-visibility.json` del cliente activo.

### 3.2 Capa de intención — skills

| Skill | Estado | Qué cambia en M1 |
|---|---|---|
| `reporte-tienda` | existe | Mueve el conocimiento por canal a la capa de referencia. Ver §9.1 |
| `cubrir-demanda` | **nuevo** | Entra por la demanda, no por el producto. Ver §5 |
| `mejorar-descripcion` | existe | **Nada.** `cubrir-demanda` delega en él tal como está hoy |

**Sobre `mejorar-descripcion`:** el research proponía que consumiera `get_seo_gaps` + `customerVoice`
(su Fase 2). **Eso queda fuera de M1** y no es prerequisito de nada acá: `cubrir-demanda` ya hace ese
cruce aguas arriba y le pasa el término concreto a cubrir. Duplicarlo del otro lado sería trabajo sin
ganancia hasta que exista evidencia de que hace falta.

### 3.3 Política por cliente — `clients/{slug}/channel-visibility.json`

Sigue el patrón que ya usa el repo para escalones (`deal-policy.json`): **la capacidad se declara
como dato por cliente, no como prosa en un skill.** Ver §4 para el contenido y los consumidores.

---

## 4. El corte de visibilidad (reabre la Decisión #1)

El research de Brain cerró: *"Si la acción vive en Shopify → la ve el cliente. Si vive en el ad
manager → es del operador"*, y dejó fuera del alcance del cliente el gasto, el CPA, el ROAS y las
alertas de campaña.

**Este spec lo reabre a propósito**, porque C2 puso al cliente como audiencia de los canales. Pero lo
reabre con una distinción que antes no estaba: **entre el diagnóstico y la plata**.

### 4.1 Los tres niveles

| Nivel | Qué incluye | Default |
|---|---|---|
| `diagnostico` | Qué está pasando y por qué. De dónde vienen las ventas, qué búsquedas traen gente, qué productos no se están mostrando, si la tienda está midiendo bien | **`true`** |
| `plata` | Gasto, costo por venta, retorno por campaña | **`false`** |
| `adOps` | Decisiones del motor (`KILL`/`SCALE`/`ROTATE`), presupuestos, canibalización | **`false`** |

`adOps` no tiene plan de abrirse: no es cuestión de confianza sino de competencia — son decisiones
que toma el equipo con contexto que el cliente no tiene. El caso testigo está en §8.1.

### 4.2 Cómo componen las dos piezas

**El canal clasifica. El cliente autoriza.**

```
bloque 5 del canal          channel-visibility.json         resultado
(igual para todos)     ×    (distinto por cliente)     =    qué se dice

"costo por venta"           { "plata": false }              no se menciona
  → nivel: plata
```

`clients/{slug}/channel-visibility.json`:

```json
{
  "diagnostico": true,
  "plata": false,
  "adOps": false
}
```

**Consumidores (esto es lo que evita que el archivo sea un artefacto muerto):** todo skill que lea un
`.md` de canal lo lee en el **paso 0**, junto con `store-standards.md` — es parte de cargar el
contexto del cliente, no un chequeo aparte. En M1 son `reporte-tienda` (§9.1) y `cubrir-demanda`
(§5).

**Si el archivo falta:** se asume el default más cerrado (`diagnostico: true`, resto `false`). No se
bloquea la respuesta; se omite lo no autorizado. Un cliente sin el archivo se comporta como el
default seguro, que es el comportamiento de hoy.

### 4.3 Limitación honesta: esto NO es un límite de seguridad

Los hooks interceptan **llamadas a tools**, no el texto que Claude le escribe al cliente. Ningún hook
puede impedir que Claude mencione un CPA. El corte de visibilidad es **presentación**, no
enforcement — a diferencia de `backup_guard` y `deal_policy`, que sí son límites reales.

> El límite real tiene que estar del lado del servidor: que el MCP de Brain **no devuelva** lo que el
> cliente no debe ver.

Esto es lo que el research ya marcó como bloqueante (§ "Bloqueante para entregarle el repo al
cliente"): el scoping por cliente del MCP de Brain está implementado en `ai-analyzer` (commit
`39f67edd`, **ya mergeado a `main`**) pero **le falta verificación e2e y deploy**.

**Consecuencia para este milestone:** todo lo de acá se puede construir y usar **en modo operador**
desde el día uno. **No se le entrega a blunua** hasta que el scoping esté deployado y verificado. Es
una dependencia externa a este repo (fase S), no una tarea de este plan.

---

## 5. Skill nuevo: `cubrir-demanda`

**La pregunta que responde:** *"¿qué le falta a mi tienda que la gente está buscando?"*

**Por qué es el skill de mayor valor de esta capa:** invierte el punto de entrada. Hoy
`mejorar-descripcion` entra por el producto ("mejorá el anillo X") — el cliente tiene que saber qué
pedir. `cubrir-demanda` entra por **la demanda real medida**: Brain ya sabe que blunua paga por
`aretes hipoalergénicos` y no tiene contenido para ese término. Son 148 oportunidades esperando, con
plata ya gastada encima (`como medir la talla de un anillo`: $10.561, cero conversiones).

**Flujo:**

0. **Paso 0 del repo** (idéntico a los demás skills): confirmar cliente activo, leer
   `clients/{slug}/CLAUDE.md` + `store-standards.md` + **`channel-visibility.json`**, verificar la
   tienda conectada con `get-shop-info` contra `connection.md`. Si no coincide, abortar.
1. Leer `.claude/channels/_comun.md`, después `gsc.md` y `google-ads.md`.
2. `get_seo_gaps` → `paidNotOrganic` (pagás y no tenés contenido) + `organicNotPaid` (ya rankeás,
   reforzá).
3. Cruzar contra el catálogo de Shopify: ¿qué producto existente cubre ese término?
4. Filtrar contra `store-standards.md` (§8.1: no toda oportunidad es deseable) y contra
   `channel-visibility.json` (si `plata` está en `false`, la oportunidad se presenta sin el monto
   gastado).
5. Presentar en lenguaje natural, ordenado por oportunidad, **diciendo el alcance de lo que se miró**.
6. Si el cliente elige una → delega en `mejorar-descripcion`, que ya tiene el protocolo de write
   completo (preview → gate → backup → escribir → worklog).

**`cubrir-demanda` no escribe.** Diagnostica y delega. Todo write pasa por el skill que ya tiene el
protocolo probado. Esto mantiene un solo camino de escritura auditado.

---

## 6. Estado real de la data por canal (verificado)

**Transversales (no pertenecen a ningún canal — viven en `_comun.md`, §3.1.2 item 7):**
`get_client_brief` es la entrada por defecto de todo análisis: trae los canales activos, el
rendimiento 7d/30d con delta y **la frescura de todos los canales en una sola llamada**.
`get_alerts` cruza canales igual. Ninguno de los dos va en el bloque 2 de un `.md` de canal.

| Canal | Fuente (además de la entrada transversal) | Estado |
|---|---|---|
| Google Ads | `get_channel_metrics(GOOGLE)`, `run_gads_skill` | ✅ listo |
| GA4 | `get_channel_metrics(GA4)` | ✅ listo |
| Search Console | `get_channel_metrics(GSC)`, `get_seo_gaps` | ✅ listo (ojo frescura: `stale` 3d) |
| Meta Ads | `get_channel_metrics(META)`, `get_active_ads`, `get_creative_intelligence` | ✅ listo |
| Klaviyo | `get_channel_metrics(EMAIL)` | ✅ listo |
| **Meta Pixel** | `signal-health-service.ts` calcula `pixelEmq`/`pixelStatus` — **no expuesto por MCP** | ⚠️ falta tool |
| **Meta Catálogo** | idem `catalogErrors`/`catalogStatus` (+ `/diagnostics` contra la API de Meta) | ⚠️ falta tool |
| **Merchant Center** | **no existe**: ni canal, ni servicio, ni sync, ni tipo | ❌ integración nueva |

**Pixel y catálogo están resueltos del lado difícil.** Falta exponerlos: un `get_signal_health` en
`ai-analyzer/src/lib/mcp/tools-ads.ts` **más su entrada en `scope.ts`**. Ojo con el matiz: `scope.ts`
corta antes cuando `clientId === null`, así que un tool sin clasificar corre igual para el operador
`@worker.ar` y solo se deniega para clientes scopeados. O sea: **si falta la entrada en `scope.ts`,
funciona en modo operador y falla recién cuando se entrega al cliente** — el peor momento para
descubrirlo. La entrada no es opcional.

**Merchant Center es otra categoría.** OAuth + sync + storage + canal nuevo (el union de canales es
`META | GOOGLE | GA4 | GSC | ECOMMERCE | EMAIL | LEADS | INSTAGRAM`; no hay lugar para Merchant). Es
un proyecto propio en `ai-analyzer`, no una tarea de este spec.

---

## 7. Qué pasa con lo que no se puede arreglar

La mayoría de los rechazos de Merchant Center y Meta Catálogo **no se arreglan con descripción**: se
arreglan con `title`, `gtin`, `product_type`, `google_product_category`, imagen o precio. Todos esos
campos los bloquea `backup_guard` hoy, por diseño.

El repo tiene hoy dos clases de escritura: **texto** (descripción + SEO meta) y **ofertas**
(escalones por cantidad, con techo por cliente). Los campos de feed no caen en ninguna.

**Decisión C7 — se diagnostica, no se corrige:**

1. Lo que cae en la clase texto (descripción, SEO meta) → se ofrece arreglar.
2. El resto → se anota en `clients/{slug}/worklog.md` como pendiente del equipo, y al cliente se le
   dice con el guion de fuera de alcance que ya existe.
3. **Nunca** se le explica al cliente la limitación técnica ni se nombran campos (regla dura #1).

**Por qué no ampliar el alcance ahora:** ampliar el guard es el trabajo caro y hay que hacerlo con el
patrón escalones (whitelist cerrada + política por cliente + hook + tests). Diagnosticar primero
genera **data real de qué campos se rompen más seguido en blunua** — mejor insumo para diseñar esa
whitelist que adivinarla hoy. La ampliación es una fase posterior (F5), no un pendiente difuso.

---

## 8. Guardrails (heredados del research, ahora con hogar en `_comun.md`)

1. **Una sugerencia del motor NO es un consejo para el cliente.** `get_seo_gaps` marca `blunua` y
   `blunua joyas` como canibalizadas y sugiere pausar Ads para ahorrar $44.822. **Los ads de marca de
   blunua son deliberados** (defender posición 1). El motor es genéricamente correcto y
   estratégicamente equivocado. Todo `suggestedAction` se contrasta contra `store-standards.md`; si
   no está contemplado, no se dice: se anota en `worklog.md`.
2. **Frescura:** si un canal no está `ok`, sus números no se reportan como hechos.
3. **Atribución:** TrueROAS solo está validado para el cliente piloto (Paia). Para el resto devuelve
   `available:false` y **no se estima**.
4. **Deltas sobre absolutos:** varias métricas del brief vienen sumadas por día (CTR 109% a 30d,
   bounceRate 382%). Las variaciones y los ordenamientos son confiables; los niveles absolutos se
   sanity-checkean antes de decirlos.
5. **Cero jerga** (regla dura #1): nunca `BUDGET_BLEED`, `CPA_SPIKE`, `ROAS`, `opportunityScore` ni
   nombres de tools.
6. **Brain es solo lectura.** Esta capa no pausa ni edita campañas. El alcance de escritura del repo
   no cambia en M1.

---

## 9. Fases

| Fase | Qué | Depende de | Riesgo |
|---|---|---|---|
| **F0** | `_comun.md` + 5 `.md` de canal (google-ads, gsc, ga4, meta, klaviyo) + `channel-visibility.json` en `_template` y blunua + **`Brain ID` en `clients/_template/CLAUDE.md`** (hoy solo lo tiene blunua) | nada | Nulo (docs) |
| **F1** | `reporte-tienda` migra a la capa de referencia. Ver §9.1 | F0 | Bajo (read-only) |
| **F2** | `cubrir-demanda` (nuevo skill) | F0 | Bajo (delega el write) |
| **F3** | `get_signal_health` + entrada en `scope.ts` en `ai-analyzer` → `meta.md` gana pixel + catálogo | repo hermano | Medio (cross-repo) |
| **F4** | Merchant Center: integración en Brain → `merchant-center.md` | proyecto propio | Alto (integración nueva) |
| **F5** | Ampliar alcance de escritura a campos de feed (patrón escalones) | F3/F4 + data real | Alto (toca el guard) |
| **S** | **Scoping del MCP de Brain: e2e + deploy** — bloqueante de la entrega al cliente | `ai-analyzer` | Alto si se omite |

**M1 = F0 + F1 + F2.** Todo lo demás es milestone aparte.

### 9.1 Qué se mueve y qué se queda en `reporte-tienda` (F1)

El skill tiene hoy dos tipos de conocimiento mezclados. La migración los separa:

| Se mueve a la capa de referencia | Se queda en el skill |
|---|---|
| Significado y traducción de métricas **por canal** → `{canal}.md` bloque 4 | El flujo del skill (paso 0, entender, leer, traducir, ofrecer siguiente paso) |
| Qué tool trae qué dato → `{canal}.md` bloque 2 | Qué preguntas ameritan consultar Brain y cuáles se responden solo con Shopify |
| Trampas por canal → `{canal}.md` bloque 7 | "Candidatos a mejorar: qué se puede prometer de verdad" (es de Shopify, no de canales) |
| Tabla de traducción transversal (ticket promedio, visitas, conversión) → `_comun.md` | El guion de fuera de alcance |
| Guardrails de frescura, atribución, deltas y `suggestedAction` → `_comun.md` | La sección "Qué NO hace" |
| Tabla "qué ve el cliente / qué no" → reemplazada por §4 (bloque 5 + JSON) | — |

**Criterio:** si la regla cambia cuando cambia el canal, va al `.md` de canal. Si vale para todos los
canales, va a `_comun.md`. Si es sobre Shopify o sobre cómo conversa el skill, se queda.

**Y el skill GANA tres lecturas nuevas** (sin esto, F1 entrega un skill al que le sacaron el
conocimiento y no le dejaron el puntero a dónde fue): en el paso 0 pasa a leer `_comun.md`, el/los
`.md` de canal que la pregunta requiera, y `channel-visibility.json` del cliente activo — en ese
orden (§3.1.2).

**Referencias colgadas:** el skill tiene un bullet en "Reglas" que dice *"ver 'Traducir las métricas'
abajo"*. Esa sección se va a `_comun.md`; F1 arregla el cross-reference.

---

## 10. Testing

El repo testea hooks con pytest (`tests/test_backup_guard.py`, `test_deal_policy.py`, …). Los `.md`
de canal son prosa y no tienen tests unitarios, pero **sí tienen un modo de falla testeable**: que un
canal cite un tool MCP que no existe. Ese es exactamente el bug que convierte un skill en ficción.

**`tests/test_channels_docs.py` (nuevo):**

1. **Estructura:** todo `.claude/channels/{canal}.md` (excluyendo `_comun.md`) tiene los 7 bloques,
   con los títulos exactos y en orden.
2. **Tools reales:** todo tool MCP nombrado en **cualquier archivo de `.claude/channels/`** —
   incluido `_comun.md`— existe en una allowlist de los 34 tools reales de Brain. Falla si alguien
   inventa `get_merchant_status`. El alcance es la carpeta entera y no solo el bloque 2, porque
   `_comun.md` es quien nombra el tool más usado del repo (`get_client_brief`) y quedaría sin cubrir.
   *Límite conocido:* la allowlist vive en este repo y los tools en `ai-analyzer`, así que atrapa
   invenciones y typos, no un rename aguas arriba. Es el modo de falla que importa.
3. **Política:** todo `clients/*/channel-visibility.json` tiene exactamente las tres claves de §4.1,
   todas booleanas.
4. **Jerga:** en el bloque 4, la **columna derecha** (la frase de cliente) no contiene ninguno de los
   términos de la lista negra. La columna izquierda sí los contiene por definición —es el diccionario—
   así que el test solo mira el lado que ve el cliente.
   La lista negra es un `frozenset` en el propio test, sembrado con los términos de la tabla de
   `reporte-tienda` (AOV, ROAS, LTV, CTR, conversión, sesiones, SKU, variante) más los de §8.5
   (`BUDGET_BLEED`, `CPA_SPIKE`, `opportunityScore`).
5. **Clasificación:** todo dato listado en el bloque 5 tiene exactamente una de las tres etiquetas de
   §4.1. Sin etiqueta, un dato no tiene forma de filtrarse.

Barato, corre en el gate de pre-push que ya existe, y ataca los modos de falla reales.

**Verificación manual (no automatizable), dos pasos:**

1. Correr `cubrir-demanda` contra blunua en vivo y comparar las oportunidades que devuelve contra las
   148 de `paidNotOrganic` ya validadas en el research.
2. **Verificar la costura del handoff:** elegir una oportunidad, dejar que delegue en
   `mejorar-descripcion`, y confirmar que **el término elegido sobrevive hasta la descripción
   escrita**. Es la única costura nueva de M1 sin test automático: `mejorar-descripcion` toma sus
   keywords de `store-standards §3/§4`, no de un llamador, y el término viaja por contexto de
   conversación. Si no sobrevive, el arreglo es una línea en su paso 4 — no un rediseño.

---

## 11. Incógnitas abiertas (no bloquean la construcción)

1. **¿`cubrir-demanda` propone productos nuevos?** Hoy solo cruza demanda contra catálogo existente.
   Si un término no tiene ningún producto que lo cubra, eso es una señal de negocio (hueco de
   catálogo) que el repo no tiene alcance para accionar. Se anota en `worklog.md`, no se acciona.
2. **Klaviyo: ¿qué acción en la tienda corrige un problema de email?** Es el canal donde el bloque 6
   está más flojo. Si en F0 no aparece una acción concreta sobre Shopify, el `.md` se escribe igual
   (sirve para diagnóstico) pero se deja marcado como pendiente.

> El contexto estratégico que filtra los `suggestedAction` **ya está decidido**: vive en
> `store-standards.md` del cliente, que es lo que el `reporte-tienda` en producción ya hace. No es
> una incógnita.
