---
name: refrescar-estandares
description: Skill de OPERADOR (no cliente-facing) para el refresh trimestral de los estándares. Refresca la parte VIVA de store-standards.md — §4 keywords SEO, §5 ángulos GEO y la nota de §10 — con evidencia del Worker Brain (keywords que convierten, ángulos que ganaron), pasa cada sugerencia por un screen de vocabulario mecánico, propone un diff con evidencia, y —con el OK del operador— hace un backup datado y una edición quirúrgica del markdown. NO toca Shopify ni el guard. Usar cuando toca refrescar/actualizar los estándares vivos de un cliente con datos del Brain.
---

# Refrescar estándares (operador — refresh trimestral con evidencia del Brain)

Skill de **mantenimiento** que corre el operador/curador (Gabriel), no el cliente. La parte VIVA de
`store-standards.md` decae: keywords que convertían dejan de hacerlo, los AI Overviews cambian, hay
estacionalidad. El v1 refresca esa parte a mano cada ~3 meses; este skill le da **evidencia** — usa
el Worker Brain para proponer qué keywords convierten (`get_seo_gaps`) y qué ángulos ganaron
(`get_creative_intelligence`) — pero **el operador cura**: el Brain propone, no manda.

> **Opt-in y no cambia el core.** Esto NO hace que cada descripción consulte el Brain en vivo. Es el
> refresh trimestral el que se hace con datos; las descripciones y combos siguen leyendo los
> estándares curados como siempre. Mantiene el determinismo.

## Reglas (no negociables)
- **Escribe SOLO la parte VIVA:** `store-standards.md` §4 (SEO) y §5 (GEO), más una nota datada en
  §10 (Señales del Brain). **NUNCA** una sección `[ESTABLE]` (§1 Marca, §2 Registro, §3 Estructura,
  §6 Naming/tags, §7 Imágenes, §8 Qué no tocar, §11 Ofertas) ni el checklist §9. Si una sugerencia
  del Brain implicaría tocar una sección ESTABLE, se descarta con nota.
- **El Brain propone; el operador cura.** El motor del Brain es genérico y no conoce la estrategia
  del cliente (caso real blunua: marca las búsquedas de la propia marca como gasto duplicado y
  sugiere pausarlas, pero esa inversión es deliberada — defiende el primer lugar). Toda sugerencia se
  contrasta contra §2 y el criterio del operador. **Nada se escribe sin el gate del operador.**
- **Screen de vocabulario mecánico ANTES del gate:** cada keyword propuesta pasa por
  `description_lint.py` en modo solo-vocabulario. Una keyword con material falso ("oro"/"plata"/
  chapado), lujo-vacío, claim médico o voseo **se descarta**, aunque convierta. Convierte "no entra"
  de juicio a chequeo.
- **Frescura: un dato viejo no es un dato.** Si un canal del brief viene `stale`/`missing`, ese dato
  no se usa y se dice qué quedó sin evidencia (misma regla que `reporte-tienda`).
- **No toca Shopify ni el guard.** Solo edita un markdown del repo (con backup). `backup_guard` no
  interviene (no es un tool de Shopify). No se llama ningún tool de Shopify en este flujo.
- **Autoridad humana a propósito:** acá el gate del operador NO es "seguridad por diseño sin humano"
  como los writes de cliente — refrescar la fuente de verdad curada **es** una tarea de curador.

## Paso 0 — Cliente + Brain ID (adaptado; acá NO es la tienda de Shopify)
Como no se escribe en Shopify, el paso 0 no verifica la tienda: identifica el cliente y su **Brain ID**.
1. Determiná el cliente activo (el slug de `clients/`). Si no está claro, preguntá antes de seguir.
2. Leé `clients/{slug}/AGENTS.md` y tomá el **Brain ID** (línea `**Brain ID:** \`...\``; blunua:
   `LO4ob4dUxOggwTSlm07v`). Leé también `clients/{slug}/store-standards.md`.
3. **Si no hay Brain ID:** avisá al operador y caé al **refresh manual** (revisás §4/§5 a criterio,
   sin la parte de evidencia del Brain). NO abortás: el refresh se puede hacer sin el Brain, solo sin
   los datos. El Brain ID es un valor estático del `AGENTS.md`, así que no hay riesgo de "repuntado en
   silencio" (no lleva verify-back como el `switch-shop` de los skills de Shopify).

## Flujo (en este orden)

1. **LEER EL ESTADO ACTUAL.** Abrí `clients/{slug}/store-standards.md` y leé §4 (keywords por
   categoría) y §5 (ángulos GEO). Esos dos bloques VIVOS son lo único que este skill puede reescribir
   (más la nota de §10).

2. **CONSULTAR EL BRAIN** (solo lectura), con el Brain ID como `client_id`:
   - `Worker_Brain:get_client_brief` — contexto general y **frescura por canal** (qué fuentes están
     `ok` vs `stale`/`missing`).
   - `Worker_Brain:get_seo_gaps` — keywords con demanda / que convierten y que no están en §4.
   - `Worker_Brain:get_creative_intelligence` — ángulos/mensajes que ganaron, para §5 (GEO).
   - Combos NO salen del Brain: `customer-intelligence` no devuelve co-compra (verificado en
     `armar-combo`); la co-compra se saca de las órdenes, no acá.
   - **Frescura:** si un canal viene `stale`/`missing` en el brief, **no uses ese dato** y anotá que
     esa parte quedó sin evidencia fresca.

3. **SCREEN DE VOCABULARIO (mecánico, SOLO-VOCABULARIO).** Por cada keyword candidata, corré el
   linter en modo solo-vocabulario (longitud relajada, sin GEO, **sin `--keywords`**), así solo
   disparan los chequeos de §2 (material falso / lujo / médico / voseo) y NO "muy corta" ni "falta
   GEO" (que marcarían toda keyword corta):

   ```
   echo "<keyword candidata>" | python .Codex/hooks/description_lint.py --min 1 --max 9999 --no-geo
   ```

   Sale 0 = limpia; 1 = tiene un problema de vocabulario → **descartá esa keyword** y anotá el
   motivo. **No** uses los defaults del linter (min 80 + GEO): sobre una keyword corta marcarían
   "muy corta / sin GEO" y descartarían todo. Además del screen mecánico, contrastá cada sugerencia
   contra el **vocabulario prohibido y las anti-referencias de §2** (juicio del operador).

4. **PROPONER EL DIFF** en texto claro, con evidencia por ítem. Por ejemplo:
   - "§4 · Aretes — AGREGAR `aretes hipoalergénicos para niñas`: trajo demanda sin cubrir (seo-gaps),
     no está en tus estándares."
   - "§5 · GEO — sumar el ángulo `apto para pieles sensibles`: fue el mensaje ganador
     (creative-intelligence)."
   - "DESCARTADA `aretes de oro`: material que la marca no usa (screen §2)."
   No incluyas evidencia cruda ni datos del Brain sin procesar; el diff es la conclusión curada.

5. **GATE DEL OPERADOR** — preguntá explícito: *"¿Aplico estos cambios a §4/§5? sí/no"*. El operador
   decide qué entra. Solo seguís con un sí; si dice que no, terminás sin escribir.

6. **BACKUP (verbatim, antes de escribir).** Copiá el `store-standards.md` **tal cual** (verbatim,
   byte por byte) a `clients/{slug}/backups/standards/{YYYY-MM-DD}.md`. Ese es el undo real: si el
   refresh sale mal, se restaura ese archivo. No lo edites ni lo "limpies" al copiarlo.

7. **ESCRIBIR (edición QUIRÚRGICA, nunca un Write de todo el archivo).** Aplicá los cambios con el
   tool **`Edit`**, reemplazando **solo** el bloque puntual que cambia:
   - El contenido de §4 (la lista de keywords por categoría) y/o §5 (los ángulos GEO).
   - En §10, agregá una **nota datada** de trazabilidad, por ejemplo:
     `- Última actualización: {YYYY-MM-DD} — fuentes: seo-gaps, creative-intelligence.`
   - **NUNCA un `Write` del archivo completo:** un rewrite total arriesga pisar en silencio las
     secciones `[ESTABLE]`. Usá string-replacement acotado a las líneas de §4/§5/§10. Después de
     editar, verificá que las secciones ESTABLE quedaron intactas (mismo texto que antes).

8. **WORKLOG + CONFIRMAR.** Append a `clients/{slug}/worklog.md`, por ejemplo:
   `## YYYY-MM-DD [write] refrescar-estandares — §4/§5 refrescados (N keywords +, M -, K descartadas por §2); backup: backups/standards/YYYY-MM-DD.md`.
   Después, resumile al operador qué cambió y qué quedó sin evidencia fresca, para el próximo refresh.

## Qué NO hace (prohibiciones duras)
- No escribe ninguna sección `[ESTABLE]` de `store-standards.md` (§1,2,3,6,7,8,11) ni el checklist §9.
- No hace un `Write` del archivo completo (solo `Edit` quirúrgico de §4/§5/§10).
- No llama ningún tool de Shopify ni toca el catálogo, precios, stock, descuentos ni descripciones.
- No escribe nada sin el backup verbatim y el gate explícito del operador.
- No usa un dato del Brain que venga `stale`/`missing`.
- No mete evidencia cruda del Brain en `store-standards.md`: solo la conclusión curada (y la nota
  datada de §10).

## Nota interna
El placeholder viejo de §10 mandaba a `customer-intelligence` para la co-compra. **Ese tool NO
devuelve co-compra** (devuelve valor de vida, recompra, fuentes de adquisición); la co-compra sale de
las órdenes (lo usa `armar-combo`). Este refresh toma de `seo-gaps` (keywords) y
`creative-intelligence` (ángulos), no de `customer-intelligence`.
