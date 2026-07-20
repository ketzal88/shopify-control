# Escalones por cantidad (quantity breaks) — Design Spec

- **Fecha:** 2026-07-19
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** diseñado, sin implementar. Tres incógnitas empíricas abiertas (§14) que NO bloquean la construcción.
- **Cliente piloto:** blunua
- **Spec padre:** `2026-07-19-shopify-control-v1-design.md` (este documento extiende §13 "Combos como write")
- **Revisión:** rev.4 — cerrado tras 3 rondas de review (19 correcciones). Listo para planificar.

---

## 1. Contexto y objetivo

El v1 de shopify-control escribe texto: descripción + SEO. `armar-combo` recomienda combos pero
explícitamente **no los crea**. Este milestone agrega el primer write que mueve plata: **escalones
por cantidad** en la ficha de producto ("llevá 2 y ahorrá 10%, llevá 3 y ahorrá 18%"), con el
widget que lo muestra y el descuento nativo que lo cobra.

Motivación comercial: subir el ticket promedio. El análisis de dos tiendas de referencia
(brickwar2.com con Upsell Koala, store.profitkoala.com como demo) mostró que el módulo de mayor
impacto en ticket es la escalera de cantidad, colocada **arriba del botón de comprar**.

**Por qué sin app de terceros:** las apps del rubro resuelven la parte cara de construir —app block
+ discount function + matriz de variantes— pero **no toman ninguna decisión de negocio**: qué
producto, qué umbral, qué %. Esa decisión es donde Worker tiene ventaja (co-compra y ticket vía
Worker Brain). Este diseño se queda con la decisión y usa el motor nativo de Shopify para ejecutarla.

---

## 2. Decisiones tomadas (brainstorm)

| # | Decisión | Elección |
|---|----------|----------|
| E1 | Alcance del milestone | **Solo `quantity_breaks`** (+ regalo BXGY en un milestone posterior). Es lo único expresable con descuentos nativos. |
| E2 | Quién autoriza | **Quien pide es quien autoriza.** Sin gate externo, consistente con D5 del spec padre. |
| E3 | Techo duro | **Sí, por cliente.** Límites mecánicos que la confirmación humana no puede saltear. |
| E4 | Instalación del widget | **Bloque Custom Liquid del editor de temas.** Cero writes a archivos del tema. |
| E5 | Semántica del undo | **Desactivar, no borrar** (`discount*Deactivate`). Preserva el rastro histórico. Ver §6.3. |
| E6 | Capa de descuentos | **Estrategia intercambiable** (§6). Default `automatic`; `codes` como fallback. |
| E7 | Preselección en el widget | **Arranca en 1 unidad**, con el escalón 2 destacado pero no marcado. Ver §4.4. |
| E8 | Skill | **Skill nuevo `armar-escalones`**, no una extensión de `armar-combo`. Ver §7. |
| E9 | Semántica de carrito | El widget **fija** las cantidades por variante (`update.js`), no las suma. Ver §4.6. |
| E10 | Variantes | El escalón cuenta **unidades del producto, con variantes mezclables** — sujeto a la incógnita C. Ver §4.6 y §14. |
| E11 | Restore de ofertas | **No existe.** El backup es insumo del guard y rastro de auditoría. Ver §7.3. |

---

## 3. Arquitectura: cuatro piezas

| Pieza | Qué es | Cuándo se escribe | Depende de |
|---|---|---|---|
| **Widget** | Bloque Custom Liquid en la plantilla de producto | Una vez por cliente, a mano | del metafield |
| **Config** | Metafield `worker.deal` (JSON) por producto | Cada vez que se arma una oferta | de nada |
| **Descuento** | Objeto nativo (`DiscountAutomaticNode` o `DiscountCodeNode`) | Al publicar la oferta | de la estrategia (§6) |
| **Guardrail** | Extensión de `backup_guard.py` + `deal-policy.json` | — | del techo por cliente |

**Propiedad de aislamiento (con un límite real):** el widget lee del metafield y de nada más, y el
metafield lleva **todo** lo que el widget necesita bajo cualquiera de las dos estrategias (§5). Por
eso **las incógnitas A y B** de §14 no tocan schema ni widget: solo cambian qué mutaciones usa el
skill.

**La incógnita C sí toca el widget.** Si el umbral de cantidad resulta ser a nivel carrito, la
mitigación obliga a exigir N de la misma variante, o sea a sacar los selectores mezclables de §4.6.
No se puede planificar el widget como independiente de los tests: C es su precondición.

**Nota honesta sobre "estrategia intercambiable":** shopify-control no tiene runtime propio (son
skills en markdown + hooks de Python que solo hacen de guarda). La intercambiabilidad **no es
polimorfismo en código**: es un archivo de procedimiento por estrategia, y el skill apunta a uno.

---

## 4. El widget

### 4.1 Instalación

Bloque **Custom Liquid** agregado desde el editor de temas a la plantilla de producto, posicionado
inmediatamente **arriba** del botón "Agregar al carrito". Se pega una vez por cliente. No se
edita ningún archivo del tema ni se usa `themeFilesUpsert`.

El bloque contiene: un preámbulo Liquid que vuelca al DOM el metafield y la matriz de variantes
como `<script type="application/json">`, más el CSS y el JS del widget inline.

**A verificar en implementación (dos cosas, ninguna asumible):**
1. Que el bloque entre en el límite de tamaño del setting. Presupuesto objetivo **≤ 20 KB** sin
   minificar. Fallback si no entra: alojar el JS como asset del tema (subir un archivo nuevo, no
   editar uno existente).
2. Que `product.metafields.worker.deal` sea legible desde Liquid. Si requiere
   `metafieldDefinitionCreate`, esa mutación está permitida **solo en setup y solo por operador**
   (§9.1); no forma parte del flujo del cliente.

### 4.2 Comportamiento

- Una fila por escalón: cantidad, precio total del escalón, precio tachado, badge de ahorro.
- El escalón con `highlight` lleva el badge "MÁS ELEGIDO".
- Debajo, una **barra de progreso** con el empujón al siguiente escalón.
- El botón **canta cantidad y total**: `Llevar 2 · $160.200`.
- Al hacer click, según `strategy` del metafield:
  - `automatic` → fija la línea del carrito (§4.6) y listo.
  - `codes` → fija la línea y luego redirige a `/discount/{code}?redirect=/cart`, tomando `code`
    del tier elegido (§5). Es la **única** rama del widget sensible a la estrategia.

### 4.3 Estados de la barra de progreso

| Escalón | Barra | Texto |
|---|---|---|
| Primero (sin descuento) | vacía | `1 más → 10%` |
| Intermedio | proporcional | `1 más → 18%` |
| Último (tope) | **llena, tono de acento** | `✓ Ahorro máximo` |

En el tope la barra **no desaparece**: se llena y cambia de tono. Desaparecer se lee como que algo
se rompió; llena, cierra el recorrido.

### 4.4 Preselección (E7)

El widget **arranca con 1 unidad seleccionada**. El escalón 2 lleva el badge "MÁS ELEGIDO" y la
barra empuja hacia él, pero la persona elige activamente subir.

Se evaluó preseleccionar el escalón 2 (sube el ticket). Se descartó por conservadurismo en una
frontera que el proyecto ya trazó al rechazar el checkbox de suscripción pre-tildado observado en
brickwar2. **Decisión revisable:** si se cambia, la condición no negociable es que el botón siga
cantando cantidad y total — el problema del default agresivo no es su tamaño sino que la
información quede fuera del momento de decidir.

### 4.5 Responsive

- **Desktop:** los escalones visibles para comparar.
- **Mobile (< 480px):** colapsa al escalón seleccionado + enlace "ver los demás". Sin colapso, el
  widget empuja el botón de comprar abajo del pliegue en un viewport de 390px.

### 4.6 Semántica de carrito y de variantes (E9 + E10) — un solo algoritmo

El widget **fija** las cantidades del producto en el carrito; no las suma. Una sola llamada, que
cubre tanto el caso mono-variante como el mezclado:

```
POST /cart/update.js
{ "updates": {
    "<variantId elegida #1>": <n1>,
    "<variantId elegida #2>": <n2>,
    "<toda otra variante del producto>": 0
} }
```

Reglas del algoritmo:

1. El widget arma un mapa `variantId → cantidad` con las variantes elegidas para el escalón.
   `Σ cantidades == qty` del escalón.
2. **Toda otra variante del mismo producto va explícitamente en 0.** Sin esto, unidades
   preexistentes de otra variante quedan en el carrito y el total supera el escalón anunciado.
3. Ninguna variante de **otros** productos se toca.

Por qué `update.js` y no `add.js` ni `change.js`: `add.js` suma (si ya había 1 y el botón dice
"Llevar 2", quedan 3 y aplica otro escalón — el botón mintió). `change.js` opera sobre **una** línea
por llamada, lo que no sirve con variantes mezcladas. `update.js` fija por variante, es idempotente
y resuelve los dos casos con una sola escritura.

**Estado inicial:** al cargar la ficha, el widget suma las unidades del producto **en todas sus
variantes**, preselecciona el escalón correspondiente (o el inmediato inferior si no coincide con
ninguno) y lo indica: "ya tenés 2 en el carrito".

**Selectores de variante:** para un escalón de N, el widget muestra N selectores, uno por unidad, y
permite mezclarlas — sujeto a la incógnita C de §14. Para productos con una sola variante
(`has_only_default_variant`), no se renderizan.

---

## 5. El metafield `worker.deal`

- **Owner:** `PRODUCT` · **namespace:** `worker` · **key:** `deal` · **type:** `json`

```json
{
  "version": 1,
  "type": "quantity_breaks",
  "tiers": [
    { "qty": 1, "pct": 0 },
    { "qty": 2, "pct": 10, "highlight": true,
      "ref": "gid://shopify/DiscountAutomaticNode/111", "code": null },
    { "qty": 3, "pct": 18,
      "ref": "gid://shopify/DiscountAutomaticNode/222", "code": null }
  ],
  "strategy": "automatic",
  "startsAt": "2026-07-20T00:00:00Z",
  "endsAt":   "2026-10-18T00:00:00Z",
  "createdBy": "shopify-control",
  "ts": "2026-07-19T22:40:00Z"
}
```

Reglas del schema (todas verificadas por el guard, §9.1):

- `tiers` ordenado ascendente por `qty`; el primero siempre `pct: 0`; sin `qty` repetidos.
- Exactamente un tier con `highlight: true`.
- `pct` es **entero, 0–100**. Ver §9.4 sobre el desajuste de unidades con la API.
- `len(tiers)` ≤ `maxTiers` de la política.
- `ref` guarda el ID del descuento. Es lo que hace posible el undo de E5.
- **`code`** guarda el string del código cuando `strategy == "codes"`, y `null` cuando es
  `automatic`. **Sin este campo la estrategia de fallback es inimplementable**, porque desde el gid
  de un `DiscountCodeNode` el widget no puede derivar el código a aplicar.
  - Formato: `{HANDLE_MAYUS_SIN_GUIONES_MAX12}-X{qty}` (ej. `ANILLONEXO-X2`).
  - Unicidad: el skill consulta el código antes de crearlo; si existe, sufija `-2`, `-3`, etc.
- `strategy` viaja en el dato, no solo en el skill: si se migra, los productos viejos siguen
  declarando cómo fueron creados y el undo sabe qué hacer con cada uno.
- `version` permite cambiar el schema sin romper widgets ya instalados en otros clientes.
- Un producto sin el metafield, o con `tiers: []`, no muestra widget. Es el estado por defecto.

---

## 6. Estrategia de descuentos

```
.claude/skills/armar-escalones/strategies/
├── automatic.md    ← discountAutomaticBasicCreate   (default)
└── codes.md        ← discountCodeBasicCreate        (fallback, ver §14)
```

Cada archivo documenta tres operaciones con la misma forma de entrada y salida:

| Operación | Entrada | Salida |
|---|---|---|
| `crear` | product gid, tiers, startsAt, endsAt | por tier con `pct > 0`: `ref` y (si aplica) `code` |
| `desactivar` | lista de `ref` | — (ver §6.3) |
| `verificar` | lista de `ref` | estado real leído del Admin API |

### 6.1 Estrategia `automatic` (default)

Un `DiscountAutomaticNode` por escalón con `pct > 0`:

```graphql
mutation ($d: DiscountAutomaticBasicInput!) {
  discountAutomaticBasicCreate(automaticBasicDiscount: $d) {
    automaticDiscountNode { id }
    userErrors { field message }
  }
}
```

```json
{ "d": {
  "title": "shopify-control · NEXO Plateado · 2+",
  "startsAt": "2026-07-20T00:00:00Z",
  "endsAt":   "2026-10-18T00:00:00Z",
  "minimumRequirement": { "quantity": { "greaterThanOrEqualToQuantity": "2" } },
  "customerGets": {
    "value": { "percentage": 0.10 },
    "items": { "products": { "productsToAdd": ["gid://shopify/Product/999"] } }
  },
  "combinesWith": { "productDiscounts": false, "orderDiscounts": true, "shippingDiscounts": true }
}}
```

- `productDiscounts: false` para que los escalones entre sí no se acumulen.
- `orderDiscounts` y `shippingDiscounts` en `true` para no bloquear promos de envío del cliente.
- **`title` con prefijo `shopify-control ·`**: permite auditar en el admin qué descuentos creó la
  herramienta y cuáles puso una persona a mano.

`desactivar` usa `discountAutomaticDeactivate` (§6.3).

### 6.2 Estrategia `codes` (fallback)

Un `DiscountCodeBasicNode` por escalón, con el **mismo** `minimumRequirement` de cantidad — el
código no aplica aunque alguien lo comparta sin cumplir la condición. El widget aplica el código
vía `/discount/{code}?redirect=/cart` (§4.2), tomando `code` del metafield.

Existe porque **elimina las incógnitas A y B de §14**: el widget decide qué código aplicar (no
Shopify), y el límite de códigos es órdenes de magnitud mayor que el de automáticos.

`desactivar` usa `discountCodeDeactivate` (§6.3).

**Rige el mismo techo que `automatic`** (§9.1): `endsAt` presente, duración y `pct` bajo límite,
ids explícitos. Activar el fallback no puede degradar E3.

Se documenta ahora y **se implementa solo si el test de §14 lo exige.**

### 6.3 `desactivar`: por qué `Deactivate` y no `endsAt = ahora`

La primitiva de neutralización es `discountAutomaticDeactivate` / `discountCodeDeactivate`.
**No** se usa `discount*BasicUpdate` con `endsAt = ahora`.

Razón, y es una trampa real: **Shopify rechaza `endsAt <= startsAt`.** Una oferta con `startsAt`
futuro —que el flujo soporta, porque §7.1 paso 5 previsualiza cuándo arranca— sería
**imposible de neutralizar**: el update fallaría, `discount*Delete` está duramente bloqueado
(§9.2), y quedaría un descuento huérfano que entra en vigencia al día siguiente sin forma de
frenarlo. El camino de compensación de §7.2 sería inalcanzable justo cuando más se lo necesita.

`Deactivate` es independiente de fechas, funciona igual con `startsAt` pasado o futuro, y preserva
el objeto con su historial — que es lo que E5 protege. "Vencer" y "borrar" no eran las únicas dos
opciones.

**Corolario:** `discountAutomaticBasicUpdate` y `discountCodeBasicUpdate` **no entran en la
whitelist** (§9.1). Sin camino de update no hay forma de estirar `endsAt` a 2031 y saltear
`maxDurationDays`, ni de tocar el `percentage` después de creado. La superficie se achica en vez
de acotarse con condiciones.

---

## 7. El skill `armar-escalones`

Skill nuevo, no una extensión de `armar-combo`. Razones:

1. `armar-combo` es read-only por diseño y por su propia descripción ("no crea el combo en
   Shopify"). Meterle un write rompe ese contrato.
2. Distinta clase de riesgo (plata vs texto) → distinto camino de guard, distinto backup, distinto gate.

`armar-combo` queda como el **upstream natural**: recomienda qué producto merece escalones;
`armar-escalones` los ejecuta.

### 7.1 Flujo fijo

Espeja el flujo de 9 pasos de `mejorar-descripcion` (§6 del spec padre):

```
0. IDENTIFICAR CLIENTE  leer clients/{slug}/CLAUDE.md + store-standards.md + deal-policy.json;
                        get-shop-info vs connection.md. Si no coinciden, ABORTA.
1. IDENTIFICAR PRODUCTO nunca adivina: si hay +1 match, muestra opciones y pregunta.
2. LEER                 metafield worker.deal actual (si existe) + precio + variantes.
3. CARGAR TECHO         deal-policy.json del cliente (§8).
4. PROPONER             cantidades y % de cada escalón, DENTRO del techo.
5. PREVIEW              en el chat, texto sin jerga: qué va a ver quien compra, cuánto sale
                        cada escalón, cuándo arranca y cuándo vence.
6. GATE                 nada se escribe hasta confirmación explícita.
7. BACKUP               clients/{slug}/backups/deals/{tail}-{timestamp}.json (§7.4).
8. ESCRIBIR             ver §7.2 — el orden importa.
9. CONFIRMAR            "Listo. Para sacarlo: 'sacá los escalones del anillo NEXO'."
```

### 7.2 Orden de escritura (falla del lado seguro)

El orden es **crear → publicar → desactivar**, nunca al revés:

```
a. crear los descuentos nuevos          → refs (+ codes)
b. metafieldsSet con los refs nuevos    → el widget ya anuncia lo que el carrito aplica
c. desactivar los descuentos VIEJOS (si los había)
```

Razón: en cualquier punto de fallo, el estado intermedio es coherente.

| Falla en | Estado resultante | Acción |
|---|---|---|
| (a) | nada publicado; se desactivan los parciales creados | aborta y reporta |
| (b) | descuentos nuevos activos pero no anunciados; los viejos siguen vigentes y anunciados | se desactivan los nuevos; la oferta vieja sigue funcionando intacta |
| (c) | ambos vigentes; el metafield anuncia el nuevo | se reintenta desactivar y se reporta. Ver la advertencia abajo |

El orden inverso (desactivar primero) deja una ventana donde **el widget anuncia escalones que el
carrito ya no aplica** — el bug de brickwar2 causado por nuestra propia compensación.

**Advertencia sobre el estado (c):** no es inocuo. Con los dos juegos vigentes, si la oferta nueva
es **menor** que la vieja, Shopify aplica la vieja por ser más favorable, y el comprador paga menos
de lo que el widget anuncia. Es divergencia widget↔carrito, aunque a favor del comprador. Por eso
(c) se reintenta y, si el reintento falla, se registra en `worklog.md` como inconsistencia
pendiente y se reporta en lenguaje natural. No hay reintento silencioso ni se da por cerrado.

### 7.3 Flujo `sacar escalones` (E11)

```
1. leer el metafield → refs y strategy
2. BACKUP (§7.4)                        ← habilita el metafieldsSet del paso 3
3. metafieldsSet con tiers: []          ← el widget deja de anunciar
4. desactivar cada ref (§6.3). NUNCA borrar.
5. registrar en worklog
```

Mismo criterio de orden: se deja de anunciar antes de dejar de aplicar. **El paso 2 no es
opcional:** `metafieldsSet` exige backup fresco (§9.1), así que sin él el propio guard bloquearía
el undo.

**No existe un flujo `revertir` para ofertas** (E11). Si alguien quiere volver a una oferta
anterior, la vuelve a armar. El backup de §7.4 es insumo del guard y rastro de auditoría, no
fuente de restore: reactivar descuentos ya desactivados reintroduce ambigüedad sobre qué estuvo
vigente cuándo, y las órdenes ya cobradas no se recalculan.

**Detección de huérfanos.** El skill reporta como inconsistencia todo descuento con prefijo
`shopify-control ·` sobre ese producto que **no esté referenciado por algún `ref` del metafield
actual**, y ofrece desactivarlo.

La condición se define así, y no como "si el metafield está vacío", precisamente para cubrir el
estado (c) de §7.2: ahí el metafield **no** está vacío —anuncia la oferta nueva— y los huérfanos
son los viejos que quedaron activos. Una condición basada en el metafield vacío no dispararía justo
en el único caso donde hace falta.

### 7.4 Contrato del backup de ofertas

`clients/{slug}/backups/deals/{productIdTail}-{YYYYMMDD-HHMMSS}.json`

El nombre lleva **timestamp**, no fecha: dos escrituras al mismo producto el mismo día colisionan.
(Los backups de descripción del spec padre heredan ese defecto; acá no se replica.)

```json
{ "kind": "deal",
  "productId": "gid://shopify/Product/999",
  "previous": { "...": "el metafield worker.deal anterior, o null si no había" },
  "ts": "2026-07-19T22:40:00Z" }
```

**El campo `kind` es obligatorio y es lo que separa los dos tipos de backup.** El guard del spec
padre valida backups de descripción exigiendo `fields.{descriptionHtml, seo_title, seo_description}`
con un glob repo-wide. Sin discriminador, pasarían dos cosas malas: un backup de deal nunca
satisfaría la condición de "backup fresco" para descripciones, y —peor— un backup de descripción
podría habilitar un write de descuento.

Regla en el guard: el backup que habilita un write de deal debe estar **bajo `backups/deals/`**
y tener **`kind == "deal"`**. Las dos condiciones, no una. Los backups de descripción conservan su
forma actual sin cambios y no ganan `kind` (su ruta ya los distingue).

**Frescura:** misma ventana de 15 minutos que el guard padre, y con su **doble condición**: el
`mtime` del archivo **y** el `ts` de adentro tienen que estar dentro de la ventana
(`backup_guard.py:173-189`). No es redundancia: cualquier operación de git —un `pull`, un cambio de
branch— refresca el mtime de todo el checkout y resucitaría backups viejos, abriendo una ventana
donde el guard queda efectivamente desactivado. El `ts` viaja dentro del archivo y git no lo
reescribe.

Se hereda también su limitación conocida: es un proxy de "se respaldó lo que se está por
sobrescribir", no una garantía.

**Qué writes exige backup:** `metafieldsSet` **y** las mutaciones de creación de descuento. Los
dos caminos, porque los dos alteran lo que el comprador ve o paga. `discount*Deactivate` **no**
lo exige: es la operación de compensación, y condicionarla a un backup fresco haría que un fallo
de backup impidiera limpiar un estado inconsistente.

---

## 8. El techo: `deal-policy.json`

Archivo nuevo por cliente: `clients/{slug}/deal-policy.json`

```json
{
  "maxDiscountPct": 30,
  "maxDurationDays": 90,
  "maxTiers": 4,
  "requireEndsAt": true,
  "allowCollectionScope": false,
  "enabledStrategies": ["automatic"]
}
```

**Por qué JSON y no una sección de `store-standards.md`:** el guard tiene que leerlo
programáticamente para decidir si bloquea. Es la lección que el spec padre ya aprendió con los
backups (§6: "el hook tiene que leerlo programáticamente, por eso `.json` y no `.md`"). Parsear
prosa markdown dentro de un guard de seguridad es frágil.

`store-standards.md` gana una sección **§11 Ofertas** que documenta la política en prosa para
humanos y apunta al JSON como fuente de verdad. `clients/_template/` lo hereda con estos valores.

---

## 9. Guardrail: extensión de `backup_guard.py`

### 9.0 Postura: whitelist cerrada

**Toda mutación cuyo nombre matchee `discount*` y no esté en la tabla de §9.1 se bloquea.**

> **Estado actual del código (a corregir en implementación):** `backup_guard.py:63-64` hoy tiene
> `discountcodebasiccreate` y `discountautomaticbasiccreate` dentro de `FORBIDDEN_MUTATIONS`, es
> decir en la **blocklist**. La implementación tiene que **sacarlos de ahí y enrutarlos por la
> whitelist con condiciones** — no simplemente borrarlos. Es el punto más delicado del milestone:
> se está relajando un bloqueo existente, y si el paso de "agregar las condiciones" quedara a
> medias, el resultado neto sería menos seguro que hoy. Por eso el orden de tareas del plan pone
> los tests de la whitelist **antes** de tocar la blocklist.

No es un detalle de redacción. El guard del spec padre opera por blocklist; heredado tal cual,
todo lo no enumerado pasaría sin techo — incluidos `discountAutomaticBxgyCreate`,
`discountAutomaticFreeShippingCreate`, `discountAutomaticAppCreate`, `discountRedeemCodeBulkAdd`
y los `discount*Activate/Deactivate`. El caso más grave es `discountCodeBasicUpdate` sin acotar:
permitiría **cambiar el `percentage` después de creado** y saltear `maxDiscountPct` por completo,
dejando abierto justo el riesgo "typo 7 → 70" que §16 dice cerrar.

Lo mismo para `metafieldsSet`: se bloquea cualquier namespace distinto de `worker`.

### 9.1 Mutaciones permitidas (whitelist)

| Mutación | Condiciones |
|---|---|
| `discountAutomaticBasicCreate` | `endsAt` presente · duración ≤ `maxDurationDays` · pct ≤ `maxDiscountPct` (§9.4) · **`items.products` o `items.productVariants`**, con ids explícitos en cualquiera de los dos · backup de deal fresco (§7.4) |
| `discountCodeBasicCreate` | **las mismas condiciones** + `"codes" in enabledStrategies` |
| `discountAutomaticDeactivate` | **sin condiciones.** Ver §9.8 |
| `discountCodeDeactivate` | **sin condiciones.** Ver §9.8 |
| `metafieldsSet` | `namespace == "worker"` · `key == "deal"` · `ownerType == PRODUCT` · JSON válido contra §5 · **`pct` de cada tier ≤ `maxDiscountPct`** · `len(tiers)` ≤ `maxTiers` · backup de deal fresco |
| `metafieldDefinitionCreate` | **solo setup, solo operador**, namespace `worker`. No alcanzable desde el flujo del cliente. |

**`discount*BasicUpdate` NO está en la whitelist**, a propósito (§6.3). Sin camino de update, no hay
forma de estirar `endsAt` para saltear `maxDurationDays` ni de cambiar el `percentage` después de
creado. Achicar la superficie es más robusto que acotarla con condiciones.

### 9.2 Bloqueos duros (no hay backup que los habilite)

- **Todas las variantes de borrado**: `discountAutomaticDelete`, `discountCodeDelete`,
  `discountAutomaticBulkDelete`, `discountCodeBulkDelete`, `discountCodeRedeemCodeBulkDelete`.
  **E5 (desactivar, no borrar) queda enforced por código**, no por prosa del skill.
  > Enumerarlas todas es ilustrativo, no la defensa: la defensa es §9.0. En la primera redacción
  > de esta lista faltaban las tres variantes `Bulk`, que habrían salteado el bloqueo por completo.
  > Sobre una superficie de 28 mutaciones `discount*`, una blocklist es indefendible.
- Cualquier descuento con `customerGets.items.all: true`.
- Cualquier descuento con `customerGets.items.collections` si `allowCollectionScope` es false.
  Es el bloqueo de mayor valor: un descuento a nivel colección puede vender el catálogo entero
  con rebaja.
- Todo lo que caiga bajo §9.0.

### 9.3 El metafield también lleva techo

`metafieldsSet` valida `pct` y `maxTiers` (§9.1), no solo la forma del JSON. Razón: **el widget lee
del metafield, no del descuento**. Un metafield con `pct: 90` y un `ref` a un descuento vencido
pasaría un guard que solo validara estructura, y produciría exactamente la divergencia
widget↔carrito que §13.2 testea y que §16 nombra como el riesgo más caro.

### 9.4 Unidades de porcentaje (trampa)

La API toma **fracción** (`"percentage": 0.10`) y la política está en **entero** (`maxDiscountPct: 30`).
Comparar `percentage <= maxDiscountPct` tal cual **deja pasar 70%**, porque `0.7 <= 30`.

Regla única en todo el proyecto:

```
pct_entero = round(percentage_api * 100)
bloquear si  pct_entero > maxDiscountPct
```

`worker.deal` guarda **entero** (§5). La conversión a fracción ocurre solo al construir la mutación.

### 9.5 Lectura de variables

Igual que la corrección ya aplicada en el guard (§11 capa 2 del spec padre): hay que inspeccionar
**el query y `tool_input.variables`**. Mirar solo el string del query deja pasar cualquier mutación
parametrizada, que es la forma idiomática de escribir GraphQL.

### 9.6 Contrato de bloqueo

`exit 2`, como el resto. Ante excepción inesperada sobre un tool de Shopify, **falla cerrado**.

### 9.7 Limitación heredada

El techo se lee de `clients/{slug}/deal-policy.json`, pero el guard **no sabe cuál es el cliente
activo** — misma limitación de scoping multi-cliente ya documentada en §12 del spec padre. Con un
solo cliente no hay ambigüedad. **Antes del 2º cliente hay que cerrar las dos juntas** (scoping de
backups y resolución del cliente activo), porque comparten causa raíz.

### 9.8 Por qué `Deactivate` va sin condiciones

Una versión anterior de §9.1 exigía que el `id` a desactivar estuviera referenciado por algún
`worker.deal`. **Esa condición bloqueaba todos los caminos que necesitan desactivar**, sin
excepción: §7.2(c) desactiva los refs viejos *después* de haber escrito los nuevos en el metafield;
§7.3 desactiva *después* de escribir `tiers: []`; los huérfanos están definidos como ids **no**
referenciados; y los parciales de §7.2(a) nunca llegaron a persistirse en ningún lado. La
compensación quedaba trabada exactamente en los cuatro escenarios para los que existe.

**Regla general que sale de ahí, y que aplica más allá de este spec:** un camino de compensación no
puede estar condicionado a un estado que la compensación misma modifica.

Se acepta el riesgo residual —desactivar un descuento que el cliente creó a mano— porque:

1. `Deactivate` es **reversible**: existe `discountAutomaticActivate` / `discountCodeActivate`, y
   el cliente lo reactiva con un click desde el admin de Shopify.
2. Lo **irreversible** sigue duramente bloqueado: las cinco variantes de borrado (§9.2).
3. El modelo de amenaza del v1 (spec padre §15) es "el operador o el cliente se equivocan", no un
   actor hostil. Un desactivado por error es molesto y recuperable; un borrado no.

**El journal sí se implementa, pero como auditoría, no como permiso.** El skill registra en
`worklog.md` cada descuento que crea y cada uno que desactiva, con su `ref`. Sirve para detectar
huérfanos y para reconstruir qué pasó. **No puede bloquear una limpieza** — si el registro fallara,
la compensación tiene que seguir estando disponible.

---

## 10. Gobernanza: qué NO se toca y qué se actualiza

Este milestone contradice en apariencia dos reglas vigentes. Se resuelve así, explícitamente:

- **`create-discount` sigue denegado** en `permissions.deny` (§11 capa 1 del spec padre). **No se
  saca del deny.** Esa tool no tiene forma de llevar techo, `endsAt` ni scope validado. El camino
  canónico es `graphql_mutation` pasando por la whitelist de §9.1, que sí los enforcea.
- **`CLAUDE.md` regla 5** ("solo descripción + SEO; nunca precio") y **`store-standards.md` §8** se
  actualizan **como parte de este milestone**, no después: pasan a declarar la nueva clase de write
  (ofertas) con su techo y sus límites. Dejarlas sin tocar deja al repo con una regla dura que el
  skill nuevo viola.

---

## 11. Flujo de datos completo

```
armar-combo (opcional)          Brain: co-compra, histograma de ticket
        │                                      │
        └──────────► armar-escalones ◄─────────┘
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
   strategies/automatic.md      deal-policy.json
              │                       │ (techo)
              ▼                       ▼
      graphql_mutation ──────► backup_guard.py ──► Shopify
      (crear descuentos)         (whitelist §9)       │
              │                                       │
              ▼                                       ▼
      metafieldsSet ────────────────────────► worker.deal
      (tambien con techo)                             │
                                                      ▼
                                        widget (Custom Liquid) ──► comprador
```

---

## 12. Errores y casos borde

| Caso | Comportamiento |
|---|---|
| Falla al crear parte de los descuentos | Desactiva los ya creados y aborta. No se escribe metafield parcial. |
| Falla `metafieldsSet` | Desactiva los nuevos. La oferta vieja (si había) sigue intacta — ver §7.2 |
| Falla la desactivación de los viejos | Ver §7.2 fila (c): NO es inocuo. Se reintenta, se registra en worklog y se reporta. |
| El producto ya tiene oferta activa | Preview ANTES vs DESPUÉS. Al confirmar, orden de §7.2 |
| Descuentos huérfanos (con prefijo, no referenciados por el metafield) | `sacar escalones` los detecta y ofrece desactivarlos (§7.3) |
| El % pedido supera el techo | El guard bloquea; el skill explica el límite sin jerga |
| Carrito con unidades preexistentes del producto | El widget **fija** la línea (§4.6): la promesa del botón se cumple |
| Producto multi-variante | N selectores, variantes mezclables (§4.6), sujeto a la incognita C |
| Stock insuficiente para el escalón mayor | Advertencia en el preview, no bloqueo. Shopify ya maneja el oversell |
| El widget no encuentra el metafield | No renderiza. La ficha queda como estaba |
| `endsAt` ya pasó | El widget no renderiza; el skill lo reporta como oferta vencida |

---

## 13. Testing

### 13.1 Automatizado (pytest, extiende los 65 tests actuales)

Sobre el guard:
- bloquea `discountAutomaticBasicCreate` sin `endsAt`
- bloquea pct por encima de `maxDiscountPct`, **incluida la trampa de unidades de §9.4**
  (un `percentage: 0.7` debe bloquear con `maxDiscountPct: 30`)
- bloquea duración por encima de `maxDurationDays`
- bloquea `items.all: true`
- bloquea scope por colección con `allowCollectionScope: false`
- bloquea **las cinco** variantes de borrado, incluidas `discountAutomaticBulkDelete`,
  `discountCodeBulkDelete` y `discountCodeRedeemCodeBulkDelete` (§9.2)
- bloquea `discountAutomaticBasicUpdate` y `discountCodeBasicUpdate` **siempre** (§6.3),
  incluido el caso `endsAt: "2031-01-01"` que estiraría la oferta más allá de `maxDurationDays`
- **permite `discount*Deactivate` siempre**, incluso para un id que no figura en ningún
  `worker.deal` — es el caso de los huérfanos y el de la compensación de §7.2 (§9.8)
- **`metafieldsSet` exige backup fresco**; `discount*Deactivate` **no** (§7.4)
- **bloquea toda mutación `discount*` fuera de la whitelist** (§9.0): BXGY, free shipping, app,
  redeem-code-bulk-add
- bloquea `metafieldsSet` con namespace ≠ `worker`
- bloquea `metafieldsSet` con `pct` sobre el techo o `len(tiers) > maxTiers`
- bloquea `discountCodeBasicCreate` si `"codes"` no está en `enabledStrategies`
- **no** acepta un backup de descripción como habilitante de un write de deal, ni viceversa (§7.4)
- bloquea el bypass por `variables` (mutación parametrizada)
- permite el camino feliz completo con backup de deal fresco

### 13.2 Manual, contra development store

- Matriz de widget: desktop / mobile 390px, cambio de escalón, colapso en mobile.
- Que la cantidad en el carrito coincida con la que cantaba el botón.
- **Carrito con unidades preexistentes del mismo producto** (§4.6).
- **Producto multi-variante con variantes mezcladas** en un mismo escalón (§4.6).
- Que el precio del carrito coincida con el que mostraba el widget — **el fallo observado en
  brickwar2**.
- Ciclo completo crear → verificar en checkout → sacar → verificar que dejó de aplicar.
- Reemplazo de oferta existente, verificando el orden de §7.2.

### 13.3 No se testea en la tienda del cliente

Los descuentos automáticos son objetos a nivel tienda que se evalúan en cada checkout. La
verificación va contra development store. Un producto en `DRAFT` no sirve: su URL da 404 y no se
puede agregar al carrito, que es justamente lo que hay que probar.

---

## 14. Las tres incógnitas empíricas

Ninguna bloquea la construcción del widget, el metafield, el skill ni el guard. Las tres se
responden contra development store. A y B determinan qué estrategia de §6 queda activa; C puede
obligar a acotar el alcance del widget.

**A — ¿Shopify permite más de un descuento automático activo a la vez?**
Eliminatoria para `automatic`: los escalones necesitan uno por tier. Si la respuesta es no, se
activa `codes`. Gracias al campo `code` de §5 y al techo compartido de §6.2, ese cambio **no toca
schema, widget, guard ni flujo**.

**B — Si dos califican a la vez, ¿cuál aplica?**
Un comprador que lleva 3 califica para "min 2" y para "min 3". Si Shopify aplica el más favorable,
los escalones funcionan solos. Si aplica por orden de creación, o exige prioridad manual, se pasa a
`codes` — **ni el metafield ni los archivos de estrategia tienen dónde registrar una prioridad, y
deliberadamente no se agrega**: administrar prioridades de descuento es complejidad que el fallback
evita por completo.

**C — ¿`minimumRequirement.quantity` cuenta unidades del producto entitled, o de todo el carrito?**

`minimumRequirement` y `customerGets.items` son **dos inputs separados** de la API. El segundo dice
qué se descuenta; el primero dice cuánto hay que llevar — pero la documentación describe el umbral
sobre "qualifying items in the customer's cart", lo que **no resuelve** si "qualifying" significa
"los del `items`" o "los del carrito".

Rev.2 de este spec afirmaba el scoping a nivel producto como hecho establecido. **No lo está**, y
la diferencia es grave: si el umbral es a nivel carrito, llevar 1 anillo + 1 collar dispara el
escalón "2+" del anillo, y el widget anuncia un precio que el carrito no respeta — exactamente el
riesgo que §16 dice cerrar. **La estrategia `codes` no lo arregla**: §6.2 usa el mismo
`minimumRequirement`.

Si resulta ser a nivel carrito, la mitigación es que el escalón exija N de la **misma variante**
(con `productVariantsToAdd` en vez de `productsToAdd`), lo que obliga a sacar las variantes
mezclables de §4.6.

**Procedimientos:**

| | Test | Qué se mira |
|---|---|---|
| **A + B** | dos descuentos automáticos sobre el mismo producto (min 2 → 10%, min 3 → 20%); agregar **3 unidades de ese producto** | ¿coexisten? ¿cuál aplica? |
| **C** | un solo descuento (min 2 → 10%) sobre el producto A; agregar **1 unidad de A + 1 unidad de B** | si descuenta A, el umbral es a nivel carrito |

El test de C es indispensable por separado: el de A/B usa 3 unidades de un mismo producto y
**pasaría igual con cualquiera de los dos scopings**, así que no lo detecta.

---

## 15. Fuera de alcance de este milestone

- Los otros 5 motores relevados (volume, cart volume, bundle por composición, mix & match,
  related products). El bundle por composición **no es expresable** con descuentos nativos:
  `minimumRequirement` solo admite cantidad o subtotal, no composición. Exige Discount Function.
- Regalo gratis (`discountAutomaticBxgyCreate`). Siguiente candidato natural.
- Escribir la config de la oferta desde el Brain automáticamente.
- Empujar el widget a la tienda por API. Se pega a mano una vez (E4).
- Traducción / multi-idioma del widget.
- Restore de ofertas anteriores (E11).

**Corte sugerido si el plan se parte en dos:** guard + política + skill primero, widget después.
§3 los aísla bien y el widget es inútil sin el backend.

---

## 16. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un descuento mal scopeado vende el catálogo con rebaja | `allowCollectionScope: false` + bloqueo de `items.all` (§9.2) |
| Un typo en el % (7 → 70) llega a producción | `maxDiscountPct` enforced por código en **los dos** caminos (crear y metafield), con la conversión de unidades fijada en §9.4 |
| Una mutación de descuento no prevista saltea el techo | Whitelist cerrada (§9.0) |
| El `percentage` o la duración se cambian después de creado | `discount*BasicUpdate` fuera de la whitelist (§6.3). Sin camino de update no hay bypass que acotar |
| Una oferta con `startsAt` futuro queda imposible de neutralizar | `Deactivate` en vez de `endsAt = ahora`: es independiente de fechas (§6.3) |
| El umbral de cantidad resulta ser a nivel carrito y no de producto | Incógnita C de §14, con test propio. Si se confirma, el escalón pasa a exigir N de la misma variante |
| Oferta que nunca termina | `requireEndsAt` + `maxDurationDays` |
| El widget muestra un precio que el carrito no respeta | Techo en el metafield (§9.3) + semántica de carrito (§4.6) + test explícito (§13.2) |
| Write a medias deja el widget anunciando lo que el carrito no aplica | Orden crear → publicar → desactivar (§7.2) |
| Un backup de descripción habilita un write de descuento | Discriminador `kind` + ruta, ambas condiciones (§7.4) |
| Se elige `automatic` y resulta inviable | Estrategia intercambiable con el campo `code` ya en el schema (§5, §14) |
| Descuentos creados a mano se confunden con los de la herramienta | Prefijo `shopify-control ·` en el `title` (§6.1) |
| El repo queda con una regla dura que el skill nuevo viola | `CLAUDE.md` regla 5 y `store-standards` §8 se actualizan dentro del milestone (§10) |
| El techo se lee del cliente equivocado con 2+ clientes | Limitación conocida (§9.7), a cerrar junto con el scoping de backups del padre |
| El bloque Custom Liquid no entra en el límite de tamaño | Presupuesto ≤ 20 KB + fallback documentado (§4.1) |
