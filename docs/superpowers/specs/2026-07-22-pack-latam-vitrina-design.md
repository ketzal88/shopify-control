# Pack LatAm — vitrina de confianza (diseño)

- **Fecha:** 2026-07-22
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño. **Elegido por Gabriel** como el primer build del programa de widgets. Falta
  spec-review, plan y implementación. Este spec toma las decisiones técnicas que el catálogo dejó
  como "mías" (owner, forma del guard, un bloque vs varios).
- **Cliente piloto:** blunua (joyería, COP)
- **Spec padre:** `2026-07-22-catalogo-widgets-design.md` (§6 familia Confianza + Vitrina + FAQ; §7 el
  registro cosmético). Este doc **implementa la 1ª familia cosmética** del programa.
- **Reusa:** el patrón `worker.style` (guard cosmético + backup `kind` + widget con fallback por-key)
  ya en `main` (commits `e838cc8`, `8680c54`).

---

## 1. Contexto y objetivo

El catálogo (§11) priorizó **Pack LatAm** como primer build: los cuatro widgets de mayor conversión en
Argentina/Colombia que además **encajan limpio** en la arquitectura sin backend:

1. **Botón de WhatsApp** — botón flotante que abre una conversación con un mensaje pre-cargado.
2. **Badge de cuotas** — "3 cuotas sin interés", cerca del precio.
3. **Badge de transferencia** — "10% off pagando por transferencia".
4. **Preguntas frecuentes** — acordeón de Q/A en la ficha, **con schema `FAQPage`** (gana SEO/GEO).

Ninguno depende de un dato inventado (§8 del catálogo): son claims del propio comercio sobre sus
propios términos (cuotas, transferencia, respuestas), honestos si los cumple. WhatsApp abre el chat;
no captura nada.

**Objetivo doble:**
- Entregar los cuatro widgets por el camino auditado (metafield `worker.*` cosmético + bloque Liquid).
- **Nacer el registro `COSMETIC_METAFIELDS`** en el guard (§7 del catálogo): es la 2ª familia
  cosmética, el momento donde la función-por-widget deja de escalar.

---

## 2. Decisiones tomadas

| # | Decisión | Elección |
|---|----------|----------|
| P1 | Metafields | **Dos:** `worker.faq` (forma Q/A + schema, propia) y `worker.trust` (ítems tipados de confianza: badges, mensajes, WhatsApp). No un metafield por widget. |
| P2 | Owner | `worker.faq` = **PRODUCT**. `worker.trust` = **PRODUCT o SHOP** (una badge puede ser por producto o de toda la tienda; WhatsApp es siempre SHOP). |
| P3 | Forma del guard | **Registro `COSMETIC_METAFIELDS`** (§7 catálogo). `_check_style` se **migra** a la 1ª entrada; `trust` y `faq` son la 2ª y 3ª. `_check_metafield` rutea por `key`. |
| P4 | Un bloque vs varios | `worker.trust` es **un** ítem-array tipado, renderizado por **dos** bloques (inline cerca del ATC + flotante para WhatsApp) que leen el mismo metafield. FAQ es su propio bloque. |
| P5 | Skills | **Uno por intención**, no por widget: `poner-confianza` (badges/mensajes/WhatsApp) y `armar-faq` (preguntas). Espejo del protocolo de `armar-escalones` sin la parte de plata. |
| P6 | El guard cosmético NO mueve plata | Sin techo (`deal-policy.json` no aplica). Validación = set/tipos cerrados + backup `kind` propio. Mismo aislamiento por ruta+kind que `style`/`deal`. |
| P7 | Orden de construcción | **FAQ primero** (product-scope puro, máximo SEO, no abre owner-SHOP), después Trust badges (abre `/Shop/`), después WhatsApp (reusa `/Shop/`). |
| P8 | Owner SHOP es un cambio de seguridad propio | Abrir `/Shop/` en el guard entra **en su fase** (Fase 2), con sus tests, no de contrabando en la Fase 1. |

---

## 3. Arquitectura

Reusa la receta de 6 piezas del catálogo (§3). Lo nuevo respecto de `worker.style`:

```
                    ┌───────────────────────────── backup_guard.py ──────────────────────────────┐
                    │  COSMETIC_METAFIELDS = {                                                    │
 metafieldsSet ────►│    "style": <validador flat: hex/texto>,      (migrado de _check_style)     │──► Shopify
 (worker.{key})     │    "faq":   <validador array {q,a}>,          (nuevo, Fase 1)               │
                    │    "trust": <validador array ítems tipados>,  (nuevo, Fase 2-3)             │
                    │  }                                                                          │
                    │  _check_metafield rutea por key → validador → _covering_cosmetic_backup      │
                    └─────────────────────────────────────────────────────────────────────────────┘
                              ▲                                              │
   poner-confianza / armar-faq (skills)                    worker.faq / worker.trust (metafields)
   preview → gate → backup(kind) → write                                    │
                              ▲                                              ▼
                    Cliente pide en lenguaje natural          Bloques Liquid: faq / trust-inline / whatsapp-float
```

**Nota de coherencia con `worker.style`:** el registro **generaliza** lo que hoy es bespoke. La
migración de `_check_style` es parte de la Fase 1 (no queda una función suelta + un registro en
paralelo). El backup cosmético se generaliza a `_covering_cosmetic_backup(key, ...)` con la misma regla
de cruce por ruta+`kind` (un backup `kind:"faq"` no habilita un write de `trust`, ni de `deal`, ni de
`style`).

---

## 4. Los metafields

### 4.1 `worker.faq` (PRODUCT)

```json
{ "version": 1,
  "items": [
    { "q": "¿El anillo es ajustable?", "a": "Sí, viene con ajuste gratis en tu primer pedido." },
    { "q": "¿Cuánto tarda el envío?", "a": "Entre 3 y 5 días hábiles a todo el país." }
  ] }
```

- `items`: array (1..`FAQ_MAX_ITEMS`, propongo 12) de `{q, a}`.
- `q`, `a`: texto, **sin `<`/`>`** (el widget usa `textContent`), `q ≤ 120`, `a ≤ 600`.
- El widget renderiza un acordeón **y** un `<script type="application/ld+json">` con `FAQPage`.

### 4.2 `worker.trust` (PRODUCT o SHOP)

```json
{ "version": 1,
  "items": [
    { "type": "badge",    "icon": "cuotas",       "text": "3 cuotas sin interés" },
    { "type": "badge",    "icon": "transferencia","text": "10% off por transferencia" },
    { "type": "message",  "text": "Envío gratis desde $80.000" },
    { "type": "whatsapp", "phone": "5491122334455", "text": "Hola, tengo una consulta 👋" }
  ] }
```

- `items`: array (1..`TRUST_MAX_ITEMS`, propongo 8) de ítems tipados.
- `type ∈ {badge, message, whatsapp}` (set cerrado; agregar un tipo = agregar una regla en el
  validador, no un metafield nuevo).
- `badge`: `icon ∈ {cuotas, transferencia, envio, garantia, seguridad}` (set cerrado de íconos SVG que
  trae el bloque; **no** URLs ni SVG del usuario) + `text` ≤ 40, sin `<`/`>`.
- `message`: `text` ≤ 80, sin `<`/`>`.
- `whatsapp`: `phone` = solo dígitos (`^\d{8,15}$`), `text` ≤ 120 sin `<`/`>`. **Único ítem que solo
  puede vivir en SHOP-scope** (un botón flotante es de toda la tienda).

---

## 5. El guard: registro cosmético

### 5.1 `COSMETIC_METAFIELDS` y el ruteo

`_check_metafield` hoy asume `worker.deal`/`worker.style`. Se generaliza:

```python
# backup_guard.py
COSMETIC_METAFIELDS = {
    "style": _check_style_body,   # migrado: la validación hex/texto de hoy, sin el I/O de backup
    "faq":   _check_faq_body,
    "trust": _check_trust_body,
}

def _check_cosmetic(key, tool_input, backups_root, now):
    # 1) parsea la única entrada; owner /Product/ (o /Shop/ si el spec lo permite, §5.3)
    # 2) valida el body con COSMETIC_METAFIELDS[key]
    # 3) exige _covering_cosmetic_backup(key, owner, now)  (ruta backups/{key}/ + kind==key)
```

En `evaluate()`/`_check_metafield`, tras aislar la entrada: si `key in COSMETIC_METAFIELDS` →
`_check_cosmetic(key, ...)`; si `key == "deal"` → la rama de plata de hoy; cualquier otra `worker.*` →
**bloquea** (postura cerrada intacta).

### 5.2 `_covering_cosmetic_backup(key, ...)`

Generaliza `_covering_style_backup` con `key` como parámetro: glob `**/backups/{key}/{tail}-*.json`,
exige `kind == key`, doble frescura (mtime + `ts`). **Cruce de discriminador** (test crítico): un
backup `kind:"faq"` no habilita `trust`, `style` ni `deal`, y viceversa en las cuatro direcciones.

### 5.3 Owner SHOP (Fase 2)

Hoy el guard exige `/Product/` en `ownerId`. Cada entrada del registro declara `owner_scope`:
`{"product"}`, `{"shop"}` o `{"product","shop"}`. El guard acepta `/Shop/` **solo** si el spec lo lista.
Sutileza del backup: un metafield de shop no tiene `productIdTail` → su backup se indexa por
`shop-{ts}.json` (la función de cobertura acepta el tail literal `shop`). **Esto entra en Fase 2**, con
su propio test de que un write de shop sin la marca `owner_scope⊇{shop}` sigue bloqueado.

### 5.4 Lo que NO cambia

- `worker.deal` y su techo, intactos.
- Los borrados de metafield siguen bloqueados (sacar un widget = escribir `{items:[]}`, nunca
  `metafieldDelete`).
- `metafieldsSet` sin `ownerId` sigue bloqueado.

---

## 6. Los bloques Liquid

Tres bloques nuevos en `widget/`, cada uno pegado una vez por el operador (los writes de tema siguen
bloqueados por diseño). Todos con el patrón probado: vuelcan JSON a `<script type="application/json">`,
JS vanilla **sin `innerHTML`**, estado por defecto = si no hay dato, no renderizan nada.

| Bloque | Lee | Dónde se pega | Nota |
|---|---|---|---|
| `worker-faq.liquid` | `product.metafields.worker.faq` | Ficha, debajo de la descripción | Acordeón + `FAQPage` JSON-LD |
| `worker-trust.liquid` | `worker.trust` (producto → fallback shop) | Ficha, cerca del ATC | Badges + mensajes inline; íconos SVG del set cerrado |
| `worker-whatsapp.liquid` | `shop.metafields.worker.trust` (ítem `whatsapp`) | Layout (flotante, toda la tienda) | Botón fijo → `https://wa.me/{phone}?text=...` |

**Resolución producto→shop de `worker-trust`:** un badge puede definirse por producto o para toda la
tienda. El bloque lee el de producto si existe; si no, cae al de shop. (Regla simple, documentada en el
runbook.)

---

## 7. Los skills

Espejo del protocolo de `armar-escalones` **sin la parte de plata** (no hay techo, no hay descuento):

- **`armar-faq`** — paso 0 (cliente + tienda) → identifica el producto → lee el `worker.faq` actual →
  propone/edita Q/A (puede sugerir preguntas desde la descripción o desde dudas frecuentes de la
  categoría) → **humanizer** → preview en el chat → gate → backup `kind:"faq"` → write → worklog.
- **`poner-confianza`** — igual, para `worker.trust`. Reconoce badges de cuotas/transferencia/envío,
  mensajes y el WhatsApp. Para WhatsApp exige SHOP-scope y valida el teléfono. Sacar = escribir
  `{items:[]}`.

Ambos **no mueven plata**, pero corren el mismo protocolo duro (preview → gate → backup → write): es
la regla del repo, no negociable por ser cosmético.

---

## 8. Testing

### 8.1 pytest (extiende el guard)

- **Registro:** `_check_cosmetic` acepta `faq`/`trust` válidos; bloquea key desconocida (`worker.evil`),
  item type desconocido, texto con `<`/`>` o sobre el máximo, `icon` fuera del set, `phone` no-dígitos.
- **Backup por key:** `_covering_cosmetic_backup("faq", ...)` acepta el fresco correcto; **cruce en las
  4 direcciones** (faq↔trust↔style↔deal no se habilitan entre sí).
- **Migración de `style`:** los tests de `test_backup_guard_style.py` **siguen verdes** tras mover la
  validación al registro (regresión: la migración no cambia comportamiento).
- **Owner SHOP (Fase 2):** un `worker.trust` de shop pasa solo si el spec marca `owner_scope⊇{shop}`;
  un `worker.faq` de shop **bloquea** (faq es product-only).
- **Deal intacto:** los tests de escalones/regalo siguen verdes.

### 8.2 Node (si hace falta)

FAQ y trust no tienen lógica de dinero → probablemente sin tests Node. El único cálculo es el schema
`FAQPage`, que se puede verificar con un test de que el JSON-LD emitido valida contra la forma
`FAQPage`.

### 8.3 Manual (dev-store, NO blunua)

Pegar los tres bloques; armar una FAQ y un par de badges + WhatsApp; verificar render, el `wa.me` con
el mensaje pre-cargado, y que el rich-result test de Google reconozca el `FAQPage`. Sacar cada uno
(`{items:[]}`) y verificar que el bloque desaparece.

---

## 9. Fases

| Fase | Qué | Abre | Riesgo |
|---|---|---|---|
| **F1** | Registro `COSMETIC_METAFIELDS` + migrar `style` + `worker.faq` + `worker-faq.liquid` (con schema) + `armar-faq` | El registro | Medio (toca el guard, pero cosmético) |
| **F2** | `worker.trust` (badges/mensajes) + owner SHOP en el guard + `worker-trust.liquid` + `poner-confianza` | `/Shop/` | Medio (cambio de seguridad chico) |
| **F3** | Ítem `whatsapp` + `worker-whatsapp.liquid` (flotante) | — (reusa SHOP) | Bajo |

F1 entrega valor solo (FAQ + SEO) sin abrir owner-SHOP. Cada fase deja tests verdes.

---

## 10. Coordinación (evitar colisión con los otros carriles)

`backup_guard.py` es el archivo caliente del repo — el carril de BXGY también lo va a tocar
(`_check_bxgy`). **Regla, igual que la nota de BXGY:** el guard tiene **un solo dueño por vez**. Este
spec y el de BXGY tocan ramas distintas (`_check_cosmetic` vs `_check_bxgy`) pero el mismo archivo →
la implementación de ambos se **serializa**, no se paraleliza. El builder de escalones ya terminó
(`01ffcda`), así que la infra base (`worker-render.js`, `worker.style`) está estable en `main`.

---

## 11. Fuera de alcance (YAGNI)

- Reseñas, pop-ups, ruleta, probador virtual, favoritos: fuera por arquitectura (§9 del catálogo).
- Editor visual (builder) de estos widgets: el builder hoy es solo escalones; generalizarlo a
  confianza/FAQ es un proyecto posterior (§16 del builder), no de este spec. Estos se arman hablándole
  a Claude.
- Íconos custom / SVG del usuario en badges: set cerrado (evita inyección + mantiene la estética).
- Countdown / urgencia de stock / prueba social: son W3/otra familia (§8 catálogo), no Pack LatAm.
- Multi-idioma de los textos.

## 12. Incógnitas abiertas

- **¿`worker.trust` badge por producto O por shop, o los dos con fallback?** Propuse fallback
  producto→shop (§6). Si en la práctica confunde, se simplifica a shop-only para badges.
- **¿`armar-faq` sugiere preguntas o solo las guarda?** Propongo que sugiera desde la descripción/
  categoría (más valor), pero sin inventar respuestas: las respuestas las confirma el cliente en el
  preview. A validar en el review.
- **Set de íconos de badge:** arranco con `{cuotas, transferencia, envio, garantia, seguridad}`.
  ¿Falta alguno obvio para joyería/LatAm?
