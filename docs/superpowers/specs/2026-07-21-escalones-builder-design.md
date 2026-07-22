# Diseño — Builder visual de escalones (cliente)

- **Fecha:** 2026-07-21
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño aprobado en brainstorm; pendiente de spec-review y plan de implementación.
- **Cliente piloto:** blunua
- **Spec padre:** `2026-07-19-quantity-breaks-design.md` (extiende §4 "El widget" y §7 "El skill")

---

## 1. Contexto y objetivo

El widget de escalones (M2) ya está construido y validado en vivo: lee `worker.deal` y renderiza la
escalera. Hoy, para **armar o cambiar** una oferta, el cliente le habla a Claude en lenguaje natural
y Claude escribe por el camino guardado.

Este proyecto agrega una **superficie visual para el cliente, dedicada exclusivamente a los
escalones**: un constructor donde el cliente arma su oferta *(producto, escalones, %)* y elige el
*look* (colores, textos) con un **preview en vivo que usa el código real del widget**, y después
**pega el resultado en el chat** para que Claude lo aplique.

**Lo que este builder NO es:** un constructor genérico. Solo escalones. Nada de descripciones, SEO,
combos ni ninguna otra superficie. YAGNI explícito.

## 2. Decisiones tomadas (brainstorm 2026-07-21)

| # | Decisión | Nota |
|---|---|---|
| D1 | **Usuario: el cliente no técnico.** | Antes el cliente solo hablaba; ahora tiene UI para esta oferta. |
| D2 | **Alcance: solo la oferta de escalones** (oferta + look), no un builder general. | Corta la superficie de raíz. |
| D3 | **El write vuelve a Claude, no lo hace el builder.** | La plata sigue pasando por `backup_guard` + techo. El builder no escribe nada. |
| D4 | **El cliente ve UI HTML.** | **Revisa** la decisión previa "previews del cliente en texto, no HTML artifacts" — a propósito, solo para este builder. |
| D5 | **Handoff por pegado.** Un HTML autocontenido (skill `playground`) que emite un texto para pegar en el chat. | Sin hosting ni callback. Cero infra nueva. |
| D6 | **El look va en un metafield aparte `worker.style`.** | Mantiene puro el schema de plata de `worker.deal`; lifecycle propio; el guard lo valida como cosmético. |

## 3. Arquitectura

Cuatro piezas, cada una con una frontera clara:

```
┌────────────────┐   genera con datos    ┌─────────────────────┐
│ Claude (skill) │ ────────────────────► │ escalones-builder    │  HTML autocontenido
│  generar-builder│   + techo adentro     │  (lo abre el cliente)│  (playground)
└────────────────┘                        └─────────────────────┘
        ▲                                            │  emite texto (config)
        │  el cliente pega el texto                  ▼
┌────────────────┐   re-valida + escribe   ┌─────────────────────┐
│ armar-escalones│ ◄────────────────────── │  Cliente pega en chat│
│  + write estilo│   (guard + techo)       └─────────────────────┘
└────────────────┘
        │ worker.deal (oferta) + worker.style (look)
        ▼
┌────────────────┐
│  Widget        │  ya instalado; toma la data nueva
└────────────────┘
```

**Flujo:** el cliente pide armar una oferta → Claude lee los productos del connector y **genera el
builder con esos datos y el techo ya adentro** → el cliente configura y ve el preview con el código
real → el builder emite un texto → el cliente lo pega → Claude re-valida contra el techo y escribe
por el camino guardado → el widget ya instalado toma la data nueva.

## 4. El builder (`escalones-builder`, HTML autocontenido)

> **Prerequisito:** M2 dejó un **archivo canónico en el repo**, `widget/worker-escalones.liquid`, del
> que salen tanto el bloque que se pega en el tema como el CSS/JS que el builder hornea para su
> preview. §8 lo mantiene como fuente única. Sin ese archivo el preview WYSIWYG no es posible.

- **Lo genera Claude por sesión**, horneando adentro: la lista de productos del cliente (id, título,
  precio unitario en centavos, imagen) leída del connector, y los límites de `deal-policy.json`. Por
  eso el preview usa **precios reales** y el cliente elige de una lista, no tipea a ciegas.
- **Autocontenido** (CSS/JS inline, imágenes por URL de CDN de Shopify). Sin dependencias externas,
  sin tokens, sin acceso a la tienda. **No puede escribir nada**: solo produce texto.
- **Secciones:**
  1. **Producto** — selector/búsqueda sobre la lista horneada. Uno por oferta.
  2. **Escalones** — agregar/quitar tiers (hasta `maxTiers`), cantidad + %, con el techo aplicado en
     la UI: no deja superar `maxDiscountPct`, exige orden ascendente, un solo destacado, primer
     escalón en 0%. El cliente **no puede construir** una oferta inválida.
  3. **Look** — pickers de color (las CSS vars: ink/sage/taupe/cream) y campos de texto acotados
     (el rótulo "Llevá más y ahorrá", el badge). Sin editor CSS libre.
  4. **Preview en vivo** — renderiza el widget con el **mismo CSS/JS que producción**, horneado desde
     `widget/worker-escalones.liquid` (el archivo canónico del prerequisito), no una maqueta. Con el
     precio real. WYSIWYG, incluido el redondeo por unidad.
  5. **Salida** — un bloque "copiá esto y pegáselo a Claude" (ver §6).

## 5. Frontera de confianza: el techo en tres lugares

El techo se aplica en **tres** lugares, y no es redundancia boba — cada uno cumple un rol distinto:

1. **La UI del builder** — para **fallar temprano y amable**: el cliente no puede ni dibujar algo
   fuera del techo. Es UX, no seguridad.
2. **`backup_guard`** — el **backstop de seguridad**. Revalida el techo en cada write de plata.
3. **`armar-escalones`** — cierra el protocolo (preview → gate → backup → write).

**El builder NO es de confianza.** Es HTML que le damos al cliente; cualquiera puede editarlo. Por
eso Claude **nunca confía en el texto pegado**: lo revalida contra `deal-policy.json` como si viniera
de cualquier lado. Si el texto pide algo fuera del techo, Claude lo explica y ofrece el máximo que
entra, igual que hoy con lenguaje natural.

## 6. El formato de la config (lo que se pega)

Un bloque reconocible con un marcador + un JSON compacto:

```
🧩 escalones-config
{ "v": 1,
  "product": { "id": "gid://shopify/Product/999", "title": "Anillo NEXO" },
  "tiers": [ { "qty": 1, "pct": 0 }, { "qty": 2, "pct": 10, "highlight": true }, { "qty": 3, "pct": 18 } ],
  "style": { "ink": "#4B4B4B", "sage": "#9CB0B1", "taupe": "#CEC4BA", "cream": "#E9E6DD",
             "label": "Llevá más y ahorrá", "badge": "MÁS ELEGIDO" } }
```

- El marcador `🧩 escalones-config` es lo que le dice a Claude "esto es una oferta armada en el
  builder", para no confundirlo con texto libre.
- **Mapeo a metafields:** el skill toma `product` + `tiers` → `worker.deal` (sumándole `strategy`,
  `startsAt`/`endsAt` y los `ref` de los descuentos que crea) y `style` → `worker.style`. El `v` de
  la config es la versión del **formato del builder**, distinto del `version` del metafield; la config
  **no trae fechas ni refs** (los pone el skill al escribir).
- Es **una request, no una orden**: no saltea el gate. `armar-escalones` corre igual su
  preview → "¿la activo?" → backup → write. El cliente ya vio el preview visual; el gate de texto es
  la confirmación de plata, y no se elimina (regla dura del proyecto: nada se escribe sin gate +
  backup).

## 7. Del lado de Claude

`armar-escalones` aprende a **ingerir la config del builder** como entrada estructurada (es la versión
tipada de lo que el cliente diría hablando). Corre su flujo normal (paso 0, contexto, techo, preview,
gate, backup, write de oferta) y **suma un write de estilo** a `worker.style`. La oferta y el estilo
son **dos asuntos separados** (regla del guard: un asunto por documento) → dos writes, cada uno con su
propio backup (ver §9).

El **preview de texto del gate usa el mismo redondeo por unidad** que el builder y el widget (§10.3),
así el total que el cliente aprobó en el builder es idéntico al que ve al confirmar. Es la única fuente
de verdad de los montos, y no puede divergir por método de redondeo.

## 8. Upgrade del widget (obligatorio para el look)

Hoy el widget tiene colores y textos hardcodeados. Cambio retrocompatible:

- El preámbulo Liquid vuelca también `product.metafields.worker.style` como JSON.
- El JS aplica esos valores como **CSS custom properties** (`--we-ink`, etc.) y overrides de copy,
  con **fallback por-key**: cada clave que falte o venga vacía cae al default del `.liquid`. Así un
  `worker.style` vacío (`{}`) —el camino de "sacar el look" de §9.2— resetea **todo** a los defaults,
  no solo el caso de ausencia total del metafield.
- Un producto sin `worker.style` se ve exactamente como hoy. Nada se rompe.

## 9. El metafield `worker.style` (nuevo)

- **Owner:** PRODUCT · **namespace:** `worker` · **key:** `style` · **type:** `json`.
- Contenido: colores (hex) + textos de copy acotados. **No mueve plata → sin techo.**
- **Pero el guard lo valida igual, como cosmético:** hoy `_check_metafield` bloquea todo lo que no
  sea `worker.deal`. Se extiende para **también** aceptar `worker.style`, con validación propia:
  - **keys: set cerrado exacto** `{ink, sage, taupe, cream, label, badge}`. Cualquier otra key
    bloquea. (`ink/sage/taupe/cream` son colores; `label` es el rótulo "Llevá más y ahorrá"; `badge`
    es el texto del destacado, hoy "MÁS ELEGIDO".)
  - **colores** (`ink/sage/taupe/cream`): deben matchear `^#[0-9A-Fa-f]{6}$` — evita inyección de CSS
    por el valor de una var.
  - **textos** (`label/badge`): **máx. 40 caracteres**, sin `<` ni `>` (el widget usa `textContent`,
    pero validar en el borde es barato y correcto).
  - Sigue exigiendo `ownerId` con `/Product/`.

### 9.1 El backup de estilo tiene `kind` y ruta PROPIOS (invariante de §7.4)

El backup de estilo **NO** puede reusar el contrato del de oferta. Si un cambio cosmético minteara un
backup `kind:"deal"` en `backups/deals/`, ese backup —fresco, dentro de la ventana de 15 min—
satisfaría la verificación de un write de **plata** no relacionado (`worker.deal` o `discount*Create`),
con un `previous` que describe el *estilo*, no la oferta. Es exactamente "un backup de descripción
habilita un write de descuento" que §7.4 del spec padre existe para prevenir.

Por eso el estilo lleva **su propio discriminador**:

- `kind: "style"` (obligatorio) · ruta `clients/{slug}/backups/style/{productIdTail}-{ts}.json` ·
  `previous` = el `worker.style` anterior (o `null`).
- El guard gana una función de cobertura **distinta**, `_covering_style_backup`, que exige
  `kind == "style"` **y** ruta `backups/style/` (las dos, igual que `_covering_deal_backup`). Un
  backup de estilo **no** habilita un write de oferta, y uno de oferta **no** habilita un write de
  estilo. Frescura doble (mtime + `ts`), idéntico a los otros dos.

### 9.2 Quitar el look

Sacar el estilo es escribir `worker.style` vacío (`{}`) — **no borrarlo**: `metafieldDelete` está
fuera de la whitelist del guard (los borrados están bloqueados como clase), así que el camino es el
mismo que "sacar la oferta" (escribir vacío). El widget cae a los defaults del `.liquid` (§8). Es un
write como cualquiera → backup de estilo + gate. No hay "restore" de estilos anteriores, igual que con
las ofertas (E11).

## 10. Testing

1. **UI del builder:** no deja construir fuera del techo (max %, max tiers, orden, un destacado,
   primer escalón 0).
2. **Round-trip:** lo que emite el builder, Claude lo reconstruye idéntico (mismo producto, mismos
   tiers, mismo estilo).
3. **Preview builder == preview del chat == widget == carrito:** los cuatro coinciden al centavo,
   todos con **redondeo por unidad** como única fuente de verdad (extiende el test de Node de la
   lección del centavo). El del chat importa porque es el número que el cliente confirma en el gate.
4. **Guard `worker.style`:** acepta estilo válido; bloquea color no-hex, key desconocida, texto con
   `<` o de más de 40 chars, y falta de backup de estilo. **Cruce de discriminador (crítico):** un
   backup `kind:"style"` NO habilita un write de `worker.deal`/`discount*Create`, y un `kind:"deal"`
   NO habilita un write de `worker.style` (§9.1). (extiende `tests/test_backup_guard_deals.py`.)
5. **Widget con y sin `worker.style`:** aplica el estilo si viene; cae a defaults si no.

## 11. Fuera de alcance (YAGNI)

- Cualquier builder que no sea el de escalones (descripciones, SEO, combos): **no**.
- Editor CSS libre: el look es un set cerrado de colores + textos.
- Hosting / callback / self-service que escriba directo: se eligió el pegado (D3, D5).
- Mezclado de variantes (N selectores de §4.6): sigue afuera, como en el widget v1.
- Guardar/versionar ofertas anteriores: no existe restore (E11 del spec padre sigue vigente).

## 12. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| El cliente edita el HTML y pide una oferta fuera del techo | El builder no es de confianza; Claude revalida contra `deal-policy.json` en el pegado (§5) |
| Un valor de color inyecta CSS por la CSS var | Validación hex en el guard + en la UI (§9) |
| El preview del builder no coincide con el carrito | El preview importa el CSS/JS real del widget y redondea por unidad (§4, test §10.3) |
| El write de estilo se cuela como write de plata | Metafield y asunto separados; `worker.style` sin techo pero con su propia validación cerrada (§9) |
| El pegado saltea el gate de confirmación | La config es request, no orden: `armar-escalones` corre preview → gate → backup igual (§6) |
| La lista de productos horneada queda vieja | El builder se **genera por sesión** con datos frescos del connector (§4) |
