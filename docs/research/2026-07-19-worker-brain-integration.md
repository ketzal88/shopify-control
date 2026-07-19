# Research — conectar Worker Brain a shopify-control

- **Fecha:** 2026-07-19
- **Objetivo:** que la IA de este repo use data de Google Ads, Meta, Search Console y GA4 para tomar
  mejores decisiones y sacar mejores conclusiones sobre la tienda.
- **Método:** inventario de la superficie MCP de Worker Brain + **validación en vivo contra blunua**
  (`get_client_brief`, `get_seo_gaps`). Los números de este doc son reales, no hipotéticos.

---

## Hallazgo central: la conexión YA EXISTE (como dato, no como código)

`clients/blunua/CLAUDE.md` ya declara **`Brain ID: LO4ob4dUxOggwTSlm07v`**, y el connector de
Worker Brain ya está disponible en la sesión. Ese campo **es** toda la primitiva de conexión.

> No hay que construir una integración. Hay que **enseñarle a los skills a usar un dato que ya está
> ahí.** El trabajo es de procedimiento (SKILL.md), no de infraestructura.

Esto reemplaza el plan Tier-2 del research anterior (montar MCPs separados de GA4 + GSC + Klaviyo):
Worker Brain **ya unifica esos canales por cliente**. Un connector que ya tenés > cuatro que no.

---

## Qué expone Worker Brain (validado contra blunua)

| Tool | Qué da | Para qué sirve acá |
|---|---|---|
| `get_client_brief` | Retrato completo en 1 llamada: identidad, objetivo, integraciones, **targets**, performance 7d/30d por canal **con delta %**, **frescura por canal**, alertas activas, perfil de onboarding | Entrada por defecto de todo análisis |
| `get_channel_metrics` | Serie diaria por canal: `META`, `GOOGLE`, `GA4`, `GSC`, `ECOMMERCE`, `EMAIL`, `INSTAGRAM` | Profundizar un canal puntual |
| `get_active_ads` | Piezas de Meta **realmente al aire** (imagen/video + copy + CTA), cruzado con entrega real de 3d | Saber qué está viendo el cliente hoy |
| `get_creative_intelligence` | KPIs + **ADN visual** (Gemini Vision) + **decisión del motor** (KILL/SCALE/ROTATE/HOLD) | "Qué ads funcionan mejor" — con el porqué |
| `get_seo_gaps` | Cruce GSC × Google Ads: `organicNotPaid` / `paidNotOrganic` / `cannibalized` | Alimentar copy y descripciones con demanda real |
| `get_attribution` | firstTouch por `acquisitionSource` + TrueROAS | De dónde vienen los clientes nuevos |

### Estado real de blunua (2026-07-19)

**Integraciones activas:** Meta ✅ · Google Ads ✅ · GA4 ✅ · Search Console ✅ · Shopify ✅ ·
Klaviyo ✅ · Instagram ✅ · Leads ❌ (no integrado).

**Targets cargados:** CPA objetivo `$40.000` · ROAS objetivo `5` · ticket promedio `$176.429` ·
margen bruto `20%` · volumen objetivo `800`.

**Frescura:** casi todo `ok` (1 día). **`GSC` viene `stale` (3 días).** ← esto importa, ver Guardrails.

**Ya hay conclusiones accionables esperando** (5 críticas / 11 warnings / 7 info), por ejemplo:
- 2 anuncios con **fuga de presupuesto**: `$81.961` y `$107.239` gastados con **cero conversiones**.
- 2 **picos de CPA**: +32% y +40% contra el período previo.
- 1 creativo marcado **ROTATE_CONCEPT** (hook rate 0.00%).

**`get_seo_gaps` devolvió señal directamente utilizable:**
- `organicNotPaid` → rankea sin cobertura paga: `anillos` (pos. 8.0, 1.785 impresiones),
  `aretes` (pos. 10.3), `acero quirurgico` (pos. 6.5), `ear cuff` (pos. 6.9).
- `paidNotOrganic` → paga sin presencia orgánica, **148 oportunidades**, muchas con 0 conversiones:
  `cadena para hombre`, `aretes hipoalergénicos`, `pulseras para parejas`,
  `como medir la talla de un anillo` (`$10.561` gastados, 0 conversiones).

---

## Arquitectura de integración

El repo es native-Claude: no hay backend, los skills son procedimientos en Markdown. Entonces
"conectar Worker Brain" = que cada skill (a) lea el `Brain ID` del `CLAUDE.md` del cliente,
(b) llame los tools que correspondan, (c) **fusione** con la data viva de Shopify, (d) pase por
humanizer, (e) responda en lenguaje natural.

### Superficie A — `reporte-tienda` pasa de mono-canal a multi-canal *(mayor ganancia)*

Hoy lee solo Shopify (ventas/stock/alertas/candidatos). Con Brain, la misma pregunta natural
("¿cómo va mi tienda esta semana?") pasa a responderse con contexto que **ningún dashboard suelto
le da al cliente**: qué campañas están quemando plata, de dónde viene el tráfico que sí compra,
qué búsquedas lo traen, y cómo se compara contra sus propios targets.

Clave: **Worker Brain ya corrió el análisis.** shopify-control no re-analiza — traduce y fusiona.

### Superficie B — `mejorar-descripcion` escribe sobre demanda real, no sobre intuición

Hoy mejora la descripción con criterio SEO/GEO + estándares de tienda. Con Brain suma:
- `get_seo_gaps.organicNotPaid` → keywords donde blunua **ya rankea** y conviene reforzar.
- `get_seo_gaps.paidNotOrganic` → términos que se **pagan y no tienen contenido** (ej.
  `aretes hipoalergénicos`, `cadena para hombre`) → la descripción los cubre y baja dependencia de Ads.
- `profile.onboardingProfile.customerVoice` → el vocabulario textual del cliente real:
  *"duradera", "segura", "minimalista", "no irrita la piel", "para regalar"*.

Esto **no amplía el alcance de escritura v1** (sigue siendo `descriptionHtml` + `seo.title/description`).
Solo mejora la materia prima de lo que ya escribimos.

### Superficie C — skill nuevo de pulso de negocio *(futuro)*

Fusiona Brain + Shopify en un "cómo viene el negocio" proactivo. Es el **briefing matutino** que ya
estaba en el roadmap, pero multi-canal en vez de solo-Shopify.

---

## Guardrails (no negociables)

1. **La recomendación del motor ≠ consejo para el cliente.** ← *el hallazgo más importante*
   `get_seo_gaps` marcó `blunua` y `blunua joyas` como canibalizadas y sugiere
   *"podés pausar Ads y ahorrar $44.822/período"*. **Pero los ads de marca de blunua son
   intencionales** (defender posición 1). El motor es genéricamente correcto y estratégicamente
   equivocado para este cliente. → **Todo `suggestedAction` se filtra contra el contexto
   estratégico del cliente antes de mostrarse.** Nunca se reenvía crudo.

2. **Honrar la frescura.** El brief trae `ok / stale / missing / not_integrated` por canal. Si un
   canal no está `ok`, sus números **no se reportan como hechos**. Hoy `GSC` está `stale` (3 días).

3. **Atribución con validez.** TrueROAS solo está validado para el cliente piloto (Paia); para
   blunua devuelve `available:false`. **Nunca inventar un número de atribución.** `firstTouch` sí
   está disponible y se presenta como lo que es.

4. **Cero jerga (regla dura #1).** El cliente jamás ve `BUDGET_BLEED`, `CPA_SPIKE`, `ROAS`,
   `opportunityScore` ni nombres de tools. Se dice *"hay una publicidad que gastó sin generar
   ventas; conviene revisarla"*, no *"BUDGET_BLEED, impactScore 90"*.

5. **Brain es solo lectura, y no habilita accionar ads.** shopify-control puede *señalar* que un
   anuncio está quemando plata, pero **no pausa ni edita campañas** — eso vive en ad-ops, fuera de
   este repo y de sus connectors. El alcance de escritura sigue siendo descripción + SEO meta.

6. **Preferir deltas y rankings sobre valores absolutos.** Varias métricas del brief se ven como
   sumas por día (ej. `ctr` 109% a 30d, `bounceRate` 382%, `frequency` 12.7, `engagementRate` 317%).
   Los **deltas %** y los **ordenamientos** son confiables; los niveles absolutos hay que
   sanity-checkearlos antes de decir un número en voz alta.

---

## ⚠️ Bloqueante para entregarle el repo al cliente

Todo lo de abajo funciona **hoy en modo operador** (Gabriel es `@worker.ar`, es su data). Pero
**entregarle este repo a blunua con el connector de Worker Brain estaba bloqueado**, y no por
conveniencia: el MCP de Brain **no tenía scoping por cliente**. `executeMcpTool(tool, args)` no
recibía la identidad del caller, así que cualquier token válido podía pasar cualquier `clientId`.
`list_clients` devolvía los 45 clientes de la cartera y `query_firestore` aceptaba filtros
arbitrarios.

El riesgo no era un cliente malicioso: era que **Claude es servicial**. Una pregunta inocente
("¿con qué datos contás?") bastaba para volcarle la cartera entera en el chat.

> Un filtro escrito en un `SKILL.md` **no es un límite de seguridad** — es una convención de
> cortesía. El límite tiene que estar del lado del servidor.

**Estado:** resuelto en `ai-analyzer`, branch `feat/mcp-client-scoping` (commit `39f67edd`).
Enforcement central en el dispatcher, fail-closed para tools no clasificados, token de email
externo atado a un único cliente vía `allowedEmails`. 367/367 tests, `tsc` y lint limpios.
**Falta la verificación end-to-end** (camino Firestore + flujo OAuth con email externo) y el
deploy. Hasta que eso esté, el repo no se entrega con el connector de Brain.

Con el scoping del lado del servidor, la decisión #1 de abajo vuelve a ser lo que debe ser:
**una decisión de presentación en el `SKILL.md`**, no un control de seguridad.

## Fases propuestas

| Fase | Qué | Estado | Riesgo |
|---|---|---|---|
| **0** | Llevar `Brain ID` a `clients/_template/` + al runbook de onboarding (blunua ya lo tiene; el template no) | pendiente | Nulo |
| **1** | `reporte-tienda` consume `get_client_brief` cuando la pregunta es de negocio. Honra frescura. Humanizer | **hecho** (sin probar en vivo) | Bajo (read-only) |
| **2** | `mejorar-descripcion` consume `get_seo_gaps` + `customerVoice` | pendiente | Bajo (no cambia alcance de escritura) |
| **3** | Skill de pulso/briefing multi-canal + routine | pendiente | Medio (requiere repo en GitHub) |
| **S** | **Scoping por cliente en el MCP de Brain** — bloqueante de la entrega al cliente | código listo, falta e2e + deploy | Alto si se omite |

---

## Decisiones

### ✅ #1 RESUELTA (Gabriel, 2026-07-19) — el cliente ve lo accionable, no el ad-ops

**Regla operativa derivada:**

> **Si la acción vive en Shopify → la ve el cliente.
> Si vive en el ad manager → es del operador.**

Coincide con el límite de escritura que ya tiene el repo (v1 solo toca descripción + SEO meta):
shopify-control le habla al cliente de **su tienda**, no de sus campañas.

| Superficie de Brain | Cliente | Operador |
|---|:--:|:--:|
| De dónde vienen las ventas (canal / `firstTouch`) | ✅ | ✅ |
| Qué búsquedas traen gente a la tienda (GSC queries) | ✅ | ✅ |
| Keywords donde ya rankea → reforzar contenido | ✅ | ✅ |
| Términos pagos sin contenido orgánico → escribir descripción | ✅ | ✅ |
| Ventas / tráfico de la semana vs anterior (deltas) | ✅ | ✅ |
| Alertas `BUDGET_BLEED` / `CPA_SPIKE` | ❌ | ✅ |
| Spend / CPA / ROAS por campaña o creativo | ❌ | ✅ |
| Decisiones del motor `KILL` / `SCALE` / `ROTATE` | ❌ | ✅ |
| Canibalización SEO×Ads y sugerencias de pausar Ads | ❌ | ✅ |

Nota: el corte es **por superficie, no por sensibilidad**. La data de ads igual alimenta el
razonamiento del skill cuando le habla al cliente (ej. "estas búsquedas te traen gente" sale de
Google Ads), pero **la conclusión que se muestra siempre es accionable sobre la tienda.**

### Abiertas

2. **¿Dónde vive el contexto estratégico** que filtra los `suggestedAction` (caso ads de marca)?
   Propuesta: una sección nueva en `store-standards.md` del cliente.

3. **¿Qué preguntas disparan una llamada a Brain** y cuáles se responden solo con Shopify?
   (evitar pagar latencia/tokens de Brain en un "¿cuánto stock queda del anillo X?").

---

## Fuentes
Validación en vivo vía connector Worker Brain (`brain.worker.ar/api/mcp-server`) contra
`clientId=LO4ob4dUxOggwTSlm07v` · `docs/research/2026-07-19-operator-tooling.md` ·
`docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
