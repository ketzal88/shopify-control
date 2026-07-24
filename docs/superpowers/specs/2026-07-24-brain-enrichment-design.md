# Brain enrichment / `refrescar-estandares` (W4-2) — Design Spec

- **Fecha:** 2026-07-24
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño (defaults tomados por Claude, sujetos a veto del operador). No implementado.
- **Cliente piloto:** blunua (Brain ID `LO4ob4dUxOggwTSlm07v`)
- **Es:** el segundo de los tres features de W4.
- **Depende de:** `2026-07-19-shopify-control-v1-design.md` §8.1 (ritual de refresh trimestral), §13 (W1.5), y la parte VIVA de `store-standards.md` (§4 keywords, §5 GEO, §10 señales del Brain).

---

## 1. Contexto y objetivo

`store-standards.md` tiene una parte **VIVA** (keywords SEO por categoría §4, ángulos GEO §5, y el placeholder de señales del Brain §10) que **decae**: keywords que convertían dejan de hacerlo, Google AI Overviews cambia, hay estacionalidad. El v1 la refresca **a mano** cada ~3 meses (§8.1). W4-2 le da **evidencia**: usa el Worker Brain para proponer, en ese refresh, qué keywords convierten y qué ángulos ganaron.

**Clave (spec §13 W1.5):** es **opt-in y no cambia el core.** No es que cada descripción consulte el Brain en vivo — es que el **refresh trimestral** de los estándares se hace con datos, y las descripciones/combos siguen leyendo los estándares curados como siempre.

### 1.1 Decisiones (defaults, sujetos a veto)

| # | Decisión | Default |
|---|---|---|
| B-D1 | ¿En vivo por request o en el refresh? | **En el refresh trimestral** (operador), no en vivo. Mantiene descripciones deterministas y respeta la frescura del Brain. |
| B-D2 | ¿Quién lo corre? | **Operador/curador** (Gabriel), no el cliente. Es una tarea de mantenimiento, no una acción de cliente. |
| B-D3 | Qué escribe | **`clients/{slug}/store-standards.md`** (§4/§5), un markdown del repo — **NO Shopify, NO guard.** |
| B-D4 | Qué señales | `get_seo_gaps` (keywords que convierten / con demanda sin cubrir), `get_creative_intelligence` (ángulos ganadores), `get_client_brief` (contexto). Combos NO: `customer-intelligence` no devuelve co-compra (verificado en `armar-combo`), sigue por órdenes. |

---

## 2. Alcance

**Dentro:**
- Skill **`refrescar-estandares`** (operador): consulta el Brain, propone updates a `store-standards §4/§5`, el operador revisa, escribe el markdown con backup + worklog.
- Manejo de frescura/ausencia del Brain (si un canal no está `ok`, no se usa el dato).
- Opt-in: sin Brain ID en `clients/{slug}/CLAUDE.md`, el skill lo dice y cae al refresh manual (como hoy).

**Fuera (YAGNI):**
- Enriquecimiento **en vivo** por request (una descripción tirando del Brain al vuelo): latencia + frescura, y rompe el determinismo. Diferido.
- Escribir `store-standards.md` **sin** revisión del operador (es la fuente de verdad curada; siempre pasa por OK humano).
- Co-compra desde el Brain para combos (no la devuelve; combos usan órdenes, W4-1).
- Auto-agendar el refresh (cron): es una acción que dispara el operador.

---

## 3. Flujo del skill `refrescar-estandares`

```
0. PASO 0 (adaptado) — identificar el cliente + su Brain ID (clients/{slug}/CLAUDE.md).
   OJO: acá el "paso 0" NO es la tienda de Shopify (no se escribe en Shopify), es el
   Brain ID. Si no hay Brain ID: avisar y caer al refresh manual (no abortar, solo
   sin la parte de evidencia).
1. LEER EL ESTADO ACTUAL — store-standards §4 (keywords por categoría) y §5 (GEO).
2. CONSULTAR EL BRAIN — get_client_brief (contexto + frescura por canal), get_seo_gaps
   (keywords con demanda / que convierten), get_creative_intelligence (ángulos ganadores).
   Si un canal viene stale/missing, no usar ese dato (regla de frescura de reporte-tienda).
3. PROPONER — un diff en texto claro: qué keywords AGREGAR/SACAR de §4 por categoría,
   qué ángulos GEO sumar a §5, con la evidencia de cada uno ("esta keyword trajo X y
   no está en tus estándares"). NO tocar la parte ESTABLE (§1,2,3,6,7,8).
4. GATE DEL OPERADOR — "¿aplico estos cambios a los estándares? sí/no". Es tarea de
   curador; el operador decide qué entra (el Brain propone, no manda — ver §4).
5. BACKUP + ESCRIBIR — backup del store-standards.md viejo (a clients/{slug}/backups/
   standards/), escribir el nuevo §4/§5, append al worklog.
6. CONFIRMAR — resumen de qué cambió, para el próximo refresh.
```

---

## 4. Las sugerencias del Brain NO son órdenes (hereda la regla de `reporte-tienda`)

El motor del Brain es genérico y **no conoce la estrategia del cliente.** Caso real de blunua: marca las búsquedas de la propia marca como gasto duplicado y sugiere pausarlas — pero esa inversión es **deliberada** (defiende el primer lugar). Por eso:
- El Brain **propone**; el operador **cura**. Toda sugerencia se contrasta contra la parte ESTABLE de `store-standards §2` (vocabulario prohibido, anti-referencias) y el criterio del operador.
- Una keyword sugerida que viole §2 (ej: un material que no es) **no entra**, aunque convierta.
- Nada se escribe sin el gate del operador (§3 paso 4).

---

## 5. Seguridad / límites

- **No toca Shopify ni el guard.** Escribe un markdown del repo (`store-standards.md`) vía el Edit tool, con backup. `backup_guard` no interviene (no es un tool de Shopify).
- **No es cliente-facing:** lo corre el operador. No hay jerga que cuidar con el cliente acá, pero el output igual es claro.
- **Frescura:** un dato viejo no es un dato (regla de `reporte-tienda`). Si el Brain no responde o el canal está stale, se refresca lo que se pueda y se dice qué quedó sin evidencia.
- **Autoridad:** el operador es el gate acá a propósito — no es "seguridad por diseño sin humano" como los writes de cliente, porque refrescar los estándares curados **es** una tarea de curador (spec §8.1). El humano cura la fuente de verdad.

---

## 6. Testing

- **Dry-run con Brain mockeado:** dado un `get_seo_gaps`/`get_creative_intelligence` de prueba, el skill propone el diff correcto sobre un `store-standards.md` de fixture, sin escribir.
- **Frescura:** si el brief marca un canal stale/missing, ese dato no aparece en la propuesta.
- **Opt-in:** sin Brain ID, cae al manual sin romper.
- **Vocabulario:** una keyword sugerida que viola §2 (material falso) no entra en la propuesta.
- **Backup:** el store-standards viejo queda respaldado antes de escribir.
- (No hay tests de guard: W4-2 no lo toca.)

---

## 7. Preguntas abiertas para el plan
- Los nombres/forma exactos de la salida de `get_seo_gaps` y `get_creative_intelligence` (confirmar con una llamada real de solo lectura al Brain en el plan).
- Si el refresh también toca §10 (placeholder de señales del Brain) o solo §4/§5.
- Formato del backup de `store-standards.md` (probablemente una copia datada del .md, no JSON — no lo lee ningún hook).
