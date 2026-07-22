# Regalo gratis (Buy X Get Y / BXGY) — Design Spec

- **Fecha:** 2026-07-22
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño. Brainstorm cerrado (decisiones G1–G16 abajo). Falta el review del spec, el plan y la implementación. Las cuatro incógnitas empíricas de §14 (D1–D4) están **sin resolver** (se resuelven contra la dev-store, igual que hizo escalones).
- **Cliente piloto:** blunua
- **Spec hermano:** `2026-07-19-quantity-breaks-design.md` (escalones). Este documento **reusa** su guard, su contrato de backup, su widget y su flujo de skill, y los **extiende** con un segundo tipo de oferta.
- **Spec del builder:** `2026-07-21-escalones-builder-design.md` + plan `2026-07-22-escalones-builder.md` (constructor visual, **aún sin implementar**). El regalo **se integra al builder** (§17) y **construye sobre su infraestructura** (`worker.style`, `worker-render.js`, el template). El builder se generaliza de "solo escalones" a "por tipo de oferta". Esta es la segunda mitad del pedido ("sumarlos al constructor visual").
- **Spec abuelo:** `2026-07-19-shopify-control-v1-design.md`

---

## 1. Contexto y objetivo

shopify-control ya escribe dos clases: **texto** (descripción + SEO) y **escalones por cantidad**
(el primer write que mueve plata, vía `worker.deal` + descuento automático nativo). Este milestone
agrega el segundo write que mueve plata: **regalo gratis** ("comprá 2 y el 3º es gratis", "comprá el
anillo y llevate los aros de regalo"), con su widget y el descuento nativo BXGY que lo cobra.

Motivación comercial: es el módulo de upsell clásico de las apps de referencia (Upsell/Profit Koala).
Sube el ticket por dos vías distintas de la de escalones: el **mismo-producto** empuja unidades del
ítem; el **cruzado** mueve **catálogo** (vende Q a quien vino por P). El spec de escalones (§15) ya lo
nombra como "siguiente candidato natural" — es lo único, además de escalones, expresable con
descuentos nativos de Shopify sin app de terceros, sin runtime propio y sin Shopify Function.

**Por qué sin app de terceros:** misma tesis que escalones (§1 del spec hermano). Las apps resuelven la
parte cara —app block + discount + matriz de variantes— pero no toman la decisión de negocio (qué
producto, qué regalo, qué umbral). Esa decisión es donde Worker tiene ventaja (co-compra vía Brain).

---

## 2. Decisiones tomadas (brainstorm)

| # | Decisión | Elección |
|---|----------|----------|
| G1 | Alcance | **Regalo gratis / BXGY**, en sus dos formas. No incluye volume/cart-volume/mix&match/bundle (§15 del hermano; el bundle no es nativo). |
| G2 | Formas | **Ambas: mismo-producto y cruzado.** Un solo `type:"bxgy"`, distinguidas por `scope`. |
| G3 | Valor del regalo | **Parcial, con techo configurable** por cliente (`maxGiftPct`). "Gratis" es el caso `pct:100`. `pct` entero 0–100, misma convención y misma defensa de unidades que escalones (§9.4 hermano). |
| G4 | Quién autoriza | **Quien pide es quien autoriza.** Sin gate externo (D5 del abuelo, E2 del hermano). |
| G5 | Techo duro | **Sí, por cliente**, en `deal-policy.json`. Dimensiones nuevas: `maxGiftPct`, `maxGetQty`, `minBuyGetRatio`, `allowCrossProductGift`, `giftableProducts`. |
| G6 | Bound del regalo cruzado | **Allowlist de productos regalables** (`giftableProducts: [gids]`). Es lo único que el guard puede enforzar sin ver precios (§9.5). Arranca `[]` → cruzado apagado hasta que el operador cure la lista. |
| G7 | Widget | **Un solo widget multi-tipo**, despacha por `deal.type`. Chrome compartido factorizado; render y carrito del regalo son ramas nuevas. |
| G8 | Skill | **Skill nuevo `armar-regalo`**, espejo de `armar-escalones`. No se extiende escalones (distinta oferta, distinto techo, distinta mutación). |
| G9 | Estrategia de descuento | **`automatic` únicamente** en v1 (`discountAutomaticBxgyCreate`). `codes` no se implementa (BXGY es un descuento único, no una escalera; el límite de automáticos no aprieta). |
| G10 | Backup | **Reusa el contrato de escalones** (`kind:"deal"`, `backups/deals/`, doble frescura mtime+ts). El backup se busca por el **producto comprado (P)** — el que el cliente configura. |
| G11 | Undo | **"Sacá el regalo"**, espejo de "sacar escalones": publica la ficha sin oferta primero, después desactiva el descuento. Nunca borra (`Deactivate`). |
| G12 | `usesPerOrderLimit` | **Forzado a 1.** El regalo no se multiplica solo en el carrito. Enforced por el guard. |
| G13 | Orden de construcción | **Mismo-producto primero, cruzado después** (fases del plan). La relajación del guard entra en incrementos testeados (§9.0 hermano). El cruzado nace apagado (`giftableProducts: []`). |
| G14 | Modelo de datos | **Un solo tipo `bxgy`** para las dos formas; la diferencia es `scope` + si `buy.product == get.product`. Mantiene guard y widget con un modelo mental. |
| G15 | Relación con el builder | **BXGY construye sobre la infraestructura del builder** (`worker.style`, `worker-render.js`, template). Orden de fases: builder-escalones (su plan) → BXGY backend → generalización del builder (§17). No se duplica nada. |
| G16 | Generalización del builder | **El builder pasa de solo-escalones a por-tipo-de-oferta** (§17). El cliente elige "escalones" o "regalo" y arma cualquiera con preview real y techo horneado. |

---

## 3. Arquitectura: las cuatro piezas (adaptando §3 del hermano)

| Pieza | Qué es | Qué cambia vs escalones |
|---|---|---|
| **Widget** | Mismo bloque Custom Liquid | Despacha por `deal.type`: `quantity_breaks` (escalones, intacto) vs `bxgy`. Chrome compartido factorizado; el render del regalo y —en cruzado— una 2ª línea de carrito son ramas nuevas (§4). |
| **Config** | Metafield `worker.deal` | Nuevo `type:"bxgy"` (§5). Una regla, no una escalera. |
| **Descuento** | Objeto nativo | `discountAutomaticBxgyCreate` (§6), no `Basic`. `usesPerOrderLimit` forzado. |
| **Guardrail** | `_check_bxgy` nuevo + `_check_metafield` ramificado + `deal-policy.json` extendido | Función propia; NO reusa `_check_discount` (§9). |

**Propiedad de aislamiento (con un límite nuevo):** el widget lee del metafield y —en el caso
cruzado— resuelve el producto regalado por su `handle` vía `all_products` de Liquid (§4.3). Es la
**única** dependencia nueva fuera del metafield, y existe porque el precio/imagen/variante del regalo
no pueden viajar congelados en el metafield sin quedar obsoletos. Se documenta como riesgo a verificar
(§14, incógnita D).

**Nota de coherencia:** shopify-control no tiene runtime propio (skills en markdown + hooks de Python
que solo guardan). "Multi-tipo" no es polimorfismo en código del widget salvo el `switch(deal.type)`;
en el skill es un archivo de procedimiento nuevo.

---

## 4. El widget

### 4.1 Instalación

**No cambia respecto de escalones** (E4 del hermano): mismo bloque Custom Liquid, pegado una vez arriba
del botón de comprar. El mismo bloque ya instalado para escalones sirve para regalo: el `switch(type)`
vive adentro. Un cliente que solo tenga escalones no ve diferencia; si además arma un regalo en otro
producto, el mismo bloque lo renderiza en la ficha de ese producto.

**A verificar en implementación:** que el bloque siga entrando en el presupuesto ≤ 20 KB con las dos
ramas de render. Si no entra, el fallback de §4.1 del hermano (alojar el JS como asset del tema) aplica
igual.

### 4.2 Dispatch por tipo

Al arrancar, el widget lee `deal.type` (hoy nunca leído — es el campo forward-compat que este milestone
por fin ejercita) y despacha:

- `quantity_breaks` (o ausente, por retrocompatibilidad) → render de escalones actual, **sin cambios**.
- `bxgy` → render de regalo (§4.4 / §4.5).

El **chrome compartido** se factoriza y lo usan las dos ramas: `formatMoney` + la "lección del centavo"
(§4 hermano: redondeo por unidad), el colapso mobile, `preselectFromCart`, el POST a `/cart/update.js`,
y el shell del CTA.

**Esta factorización se apoya en `widget/render/worker-render.js`** —la fuente única de render que
introduce el builder (Task 2 de su plan)—, extendida con la rama `bxgy`. El render de `bxgy` es **puro
y builder-safe** (solo construye/estila el DOM; misma "frontera crítica" del builder): `onBuy` —incluida
la 2ª línea de carrito del cruzado (§4.5)— y `preselectFromCart` **quedan fuera del render**, en el init
del `.liquid`, para que el builder pueda reusar el render inerte, sin tocar el carrito real. Por eso este
milestone **depende** de que la extracción de `worker-render.js` (builder) ya esté hecha (G15).

### 4.3 Datos que el bloque vuelca al DOM

Para `bxgy` cruzado el preámbulo Liquid agrega, además de lo actual, la resolución del producto regalado:

```liquid
{%- assign gift = all_products[deal.get.handle] -%}
```

y vuelca `{ variantId (primera disponible), title, imageUrl, price, available }` del regalo como JSON,
igual que hoy vuelca las variantes del producto principal. Si `gift` no resuelve (producto despublicado
o fuera del alcance de `all_products`), el widget **no renderiza el bloque de regalo** y lo reporta en
consola — la ficha queda como estaba (mismo criterio que "el widget no encuentra el metafield").

### 4.4 Render — mismo-producto ("llevá 3, pagás 2")

Una **tarjeta única** (no la escalera de escalones), con:

- La línea del regalo con badge **GRATIS** (si `pct==100`) o **−X%** (parcial).
- El total honesto: **`pagás buy.qty` unidades** (no un %). Modelar el total como porcentaje mentiría
  por redondeo contra el descuento nativo (que cobra `buy.qty` enteras + `get.qty` a `pct`), así que el
  total se calcula como `buy.qty × precio_unitario + get.qty × precio_unitario × (100-pct)/100`, con el
  redondeo-por-unidad de §4 hermano.
- La **barra de progreso** (reusada) empuja hacia el umbral: si el carrito tiene menos de `buy.qty`,
  "Sumá K y el 3º es gratis"; alcanzado el umbral, "✓ Tu regalo está incluido" (llena, tono acento).
- CTA que **canta**: `Llevar 3 · pagás 2 · $total`.

**Carrito:** reusa `onBuy` tal cual (§4.6 hermano). Pone `buy.qty + get.qty` de la variante elegida y 0
en las demás variantes del producto. El descuento BXGY nativo hace gratis/parcial la unidad regalada.

### 4.5 Render — cruzado ("comprá P, llevate Q de regalo")

Un **bloque distinto**: "Comprá {P} y llevate de regalo:" + tarjeta del regalo (imagen/título de Q
resueltos en §4.3) con badge GRATIS/−X%. CTA: `Agregar {P} + tu regalo`.

**Carrito (rama nueva):** `onBuy` para cruzado hace **una** llamada `update.js` con **dos** líneas —
la variante de P en `buy.qty` y la variante de Q en `get.qty`— más las otras variantes de P en 0
(regla 2 de §4.6 hermano, para no arrastrar unidades preexistentes de P). El descuento nativo zerea el
precio de Q. Es la divergencia real respecto de escalones: escalones nunca toca una segunda línea.

### 4.6 Preselección y estados

`preselectFromCart` reusado: cuenta unidades de P en el carrito y, para mismo-producto, preselecciona
alcanzado/no-alcanzado el umbral. Para cruzado, si Q ya está en el carrito lo indica ("tu regalo ya
está incluido"). El estado inicial sigue siendo conservador (E7 hermano): no fuerza el regalo, lo ofrece
con el botón cantando la acción completa.

---

## 5. El metafield `worker.deal` con `type:"bxgy"`

- **Owner:** `PRODUCT` (el producto **comprado**, P) · **namespace:** `worker` · **key:** `deal` · **type:** `json`

```json
// Mismo producto — "comprá 2, el 3º gratis"
{ "version": 1, "type": "bxgy", "scope": "same",
  "buy":  { "qty": 2, "product": "gid://shopify/Product/P" },
  "get":  { "qty": 1, "product": "gid://shopify/Product/P", "handle": "anillo-nexo", "pct": 100 },
  "strategy": "automatic", "usesPerOrderLimit": 1,
  "ref": "gid://shopify/DiscountAutomaticNode/333", "code": null,
  "startsAt": "2026-07-22T00:00:00Z", "endsAt": "2026-10-20T00:00:00Z",
  "createdBy": "shopify-control", "ts": "2026-07-22T10:00:00Z" }

// Cruzado — "comprá el anillo P, llevate los aros Q de regalo"
{ "version": 1, "type": "bxgy", "scope": "cross",
  "buy":  { "qty": 1, "product": "gid://shopify/Product/P" },
  "get":  { "qty": 1, "product": "gid://shopify/Product/Q", "handle": "aros-luna", "pct": 100 },
  … }
```

Reglas del schema (todas verificadas por el guard, §9):

- `type == "bxgy"` y `scope in {"same","cross"}`.
- `buy.product`, `get.product` son gids de producto. `scope=="same"` ⇒ `buy.product == get.product`;
  `scope=="cross"` ⇒ distintos **y** `get.product ∈ giftableProducts` de la política (§8).
- `buy.qty`, `get.qty` enteros ≥ 1. `get.qty ≤ maxGetQty`.
- `get.pct` entero 0–100, `≤ maxGiftPct`. (La conversión a fracción ocurre solo al construir la
  mutación, §6; §9.4 hermano.)
- `scope=="same"` ⇒ `buy.qty ≥ minBuyGetRatio × get.qty` (§8).
- `usesPerOrderLimit == 1`.
- `ref` guarda el gid del `DiscountAutomaticNode` (habilita el undo, G11).
- `get.handle` acompaña al gid solo para que Liquid resuelva el display del regalo (§4.3); el guard no
  lo usa.
- `strategy == "automatic"` (G9). El campo viaja en el dato por la misma razón forward-compat que en
  escalones.
- `version` permite migrar el schema sin romper widgets ya instalados.
- Un producto sin metafield, o con una oferta vencida, no muestra widget (estado por defecto).

**Nota de convivencia:** escalones y regalo **no pueden coexistir en el mismo producto**, porque el
metafield `worker.deal` es único por producto. El skill lo detecta en el paso 2 (preview ANTES vs
DESPUÉS) y ofrece reemplazar. No es una limitación grave: son dos ofertas distintas sobre la misma
ficha, y mostrarlas juntas confundiría al comprador.

---

## 6. Estrategia de descuento (`automatic`)

`.claude/skills/armar-regalo/strategies/automatic.md`, con las tres operaciones de siempre
(`crear` / `desactivar` / `verificar`), forma de entrada/salida espejo de escalones.

`crear`: **un** `DiscountAutomaticBxgyNode` por oferta (no uno por escalón — BXGY es regla única):

```graphql
mutation ($d: DiscountAutomaticBxgyInput!) {
  discountAutomaticBxgyCreate(automaticBxgyDiscount: $d) {
    automaticDiscountNode { id }
    userErrors { field code message }
  }
}
```

```json
{ "d": {
  "title": "shopify-control · Regalo · NEXO 2+1",
  "startsAt": "2026-07-22T00:00:00Z",
  "endsAt":   "2026-10-20T00:00:00Z",
  "usesPerOrderLimit": "1",
  "customerBuys": {
    "value": { "quantity": "2" },
    "items": { "products": { "productsToAdd": ["gid://shopify/Product/P"] } } },
  "customerGets": {
    "value": { "discountOnQuantity": { "quantity": "1", "effect": { "percentage": 1.0 } } },
    "items": { "products": { "productsToAdd": ["gid://shopify/Product/P"] } } },
  "combinesWith": { "productDiscounts": false, "orderDiscounts": true, "shippingDiscounts": true }
}}
```

Verificado contra el connector (introspección + `validate_graphql_codeblocks` = VALID; sin tocar tienda):

- **El regalo va SIEMPRE por `customerGets.value.discountOnQuantity.effect`.** Shopify **no soporta**
  `customerGets.value.percentage` ni `discountAmount` en BXGY (el schema lo dice literal). El guard
  rechaza esos dos caminos (§9.4).
- **`effect.percentage` es fracción 0.0–1.0.** "Gratis" = `1.0`. La conversión desde el `pct` entero
  del metafield ocurre acá.
- **Mismo-producto:** mismo gid en `customerBuys.items` y `customerGets.items`. **Cruzado:** gids
  distintos (confirmado por ejemplo oficial "Buy first product, get second product free").
- **`productId` como variable extra no declarada** (misma técnica que escalones §6.1): va el gid de P
  para que el guard encuentre el backup, sin declararlo en la firma (Shopify rechaza variable declarada
  y no usada).
- `productDiscounts: false` para no apilar el regalo con otros descuentos de producto.

`desactivar`: `discountAutomaticDeactivate` (reusa la primitiva de escalones §6.3). `verificar`: lee el
estado real del Admin API.

---

## 7. El skill `armar-regalo`

Skill nuevo, espejo de `armar-escalones`. `armar-combo` sigue siendo el upstream natural (recomienda qué
producto y qué regalo cruzado tiene co-compra); `armar-regalo` lo ejecuta.

### 7.1 Flujo fijo (0–9, espeja §7.1 hermano)

```
0. IDENTIFICAR CLIENTE  idéntico a escalones: CLAUDE.md + store-standards + deal-policy.json;
                        get-shop-info vs connection.md. Si no coinciden, ABORTA.
1. IDENTIFICAR PRODUCTO(S)  el comprado (P). Si es cruzado, también el regalo (Q); nunca adivina.
2. LEER                 metafield worker.deal actual de P + precios/variantes de P (y de Q si cruzado).
3. CARGAR TECHO         deal-policy.json: maxGiftPct, maxGetQty, minBuyGetRatio, allowCrossProductGift,
                        giftableProducts, requireEndsAt, maxDurationDays.
4. PROPONER             buy.qty, get.qty, get.pct, scope — DENTRO del techo. Cruzado: valida
                        Q ∈ giftableProducts antes de proponer; si no está, lo dice sin jerga.
5. PREVIEW              en el chat, sin jerga: qué ve quien compra, cuánto paga, cuándo arranca/vence.
6. GATE                 nada se escribe sin "sí" explícito.
7. BACKUP               clients/{slug}/backups/deals/{P-tail}-{timestamp}.json, kind:"deal".
8. ESCRIBIR             orden crear → publicar → desactivar (§7.2 hermano). Aunque el descuento es uno
                        solo, el orden vale igual si se reemplaza una oferta previa.
9. WORKLOG + CONFIRMAR  "Listo. Para sacarlo: 'sacá el regalo del anillo NEXO'."
```

### 7.2 Preview sin jerga

Reusa las reglas de §5 del hermano (prohibido decir metafield/descuento/gid/mutación/variante). La
palabra que el cliente usa para pedir/sacar —"regalo"— sí se permite. Copy: "**Comprá 2 y el 3º es
gratis**" / "**Comprá el anillo NEXO y llevate de regalo los aros LUNA**", con precio total y fecha de
vencimiento legibles. Caso ANTES vs DESPUÉS si el producto ya tiene una oferta (escalones o regalo).
Pasa por humanizer antes de mostrar.

### 7.3 Undo — "sacá el regalo"

Espeja "sacar escalones" (§7.3 hermano): preview + gate + backup; **publica la ficha sin oferta primero**
(el widget deja de anunciar) y **después desactiva** el descuento (nunca borra). No hay flujo "revertir".

### 7.4 Backup, worklog, huérfanos

Reusa el contrato de §7.4 hermano tal cual (`kind:"deal"`, doble frescura). Worklog y detección de
huérfanos por prefijo `shopify-control ·` reusados (§9 hermano). El backup se busca por el gid de **P**.

---

## 8. El techo: `deal-policy.json` extendido

Se agregan claves; las de escalones no cambian. Valores propuestos para blunua:

```json
{
  "maxDiscountPct": 30,            "maxTiers": 4,
  "maxDurationDays": 90,           "requireEndsAt": true,
  "allowCollectionScope": false,   "enabledStrategies": ["automatic"],

  "maxGiftPct": 100,
  "maxGetQty": 1,
  "minBuyGetRatio": 2,
  "allowCrossProductGift": true,
  "giftableProducts": []
}
```

| Clave | blunua | Qué acota | Aplica a |
|---|---|---|---|
| `maxGiftPct` | 100 | tope de `get.pct` (100 = permite gratis) | ambas |
| `maxGetQty` | 1 | máximo de unidades regaladas por oferta | ambas |
| `minBuyGetRatio` | 2 | `buy.qty ≥ ratio × get.qty` (prohíbe "comprá 1 llevá 1" = 50% off) | mismo-producto |
| `allowCrossProductGift` | true | habilita `scope:"cross"` | cruzado |
| `giftableProducts` | `[]` | allowlist de gids regalables (§9.5) | cruzado |

**Migración (obligatoria en la implementación):** `deal_policy.py` exige que estén **todas** las claves
requeridas o bloquea. Agregar estas cinco implica actualizar `REQUIRED_KEYS` **y** backfillear
`clients/blunua/deal-policy.json` y `clients/_template/deal-policy.json` en el **mismo** cambio, o el
guard bloquearía hasta escalones. `giftableProducts: []` es el default seguro: cruzado habilitado pero
nada regalable hasta que el operador cure la lista (G6, G13).

`store-standards.md` gana una subsección de regalo que apunta al JSON como fuente de verdad.

---

## 9. Guardrail: extensión de `backup_guard.py`

### 9.0 Postura

Se mantiene la whitelist cerrada del hermano (§9.0): todo `discount*` fuera de la tabla se bloquea. Este
milestone **agrega una entrada** (`discountAutomaticBxgyCreate`) con condiciones propias — es el punto
delicado, porque se relaja un bloqueo existente. Por eso el plan pone los tests de `_check_bxgy` **antes**
de tocar `ROOT_FIELD_ALLOWED`, y el orden de fases (G13) construye mismo-producto antes que cruzado.

### 9.1 Mutación permitida (nueva fila de la whitelist)

| Mutación | Condiciones |
|---|---|
| `discountAutomaticBxgyCreate` | `endsAt` presente · duración ≤ `maxDurationDays` · `customerGets` usa `discountOnQuantity.effect` (rechaza `percentage`/`discountAmount` top-level) · `pct = round(effect.percentage × 100) ≤ maxGiftPct` · `get.qty ≤ maxGetQty` · `usesPerOrderLimit == 1` · `customerBuys.items` y `customerGets.items` con **`products` de gids explícitos** (sin `collections`, sin `all`) · si buy≠get: `allowCrossProductGift` **y** `get.product ∈ giftableProducts` · si buy==get: `buy.qty ≥ minBuyGetRatio × get.qty` · `productId` (=gid de P) en variables · backup de deal fresco de P |

**Dos cosas que el guard hoy NO inspecciona y BXGY expone**, y que `_check_bxgy` debe cubrir:

1. **El lado `customerBuys`** (cantidad y scope). El scope de escalones solo mira `customerGets.items`;
   acá hay que validar los dos lados (que el "comprá" no sea `collections`/`all`, y que `buy.qty` sea sano).
2. **La cantidad regalada** (`customerGets...discountOnQuantity.quantity`) contra `maxGetQty`.

### 9.2 `_check_bxgy` es función propia (no reusa `_check_discount`)

Meter BXGY en el set `DISCOUNT_CREATE` lo rutearía a `_check_discount`, que asume la forma `Basic`
(`customerGets.value.percentage` acotado por `maxDiscountPct`). Con `percentage: 1.0` (gratis) eso
bloquea **todo regalo legítimo**. Por eso: `discountautomaticbxgycreate` entra en `ROOT_FIELD_ALLOWED`
y en un set nuevo, con dispatch propio a `_check_bxgy` en la rama de asuntos.

### 9.3 `_check_metafield` ramifica por `type`

Hoy `_check_metafield` valida `tiers` siempre. Debe leer `value.type`:

- `type == "bxgy"` → valida la forma BXGY de §5 (pct ≤ maxGiftPct, get.qty ≤ maxGetQty, ratio/allowlist
  según scope). **No** aplica el schema de escalones.
- `type == "quantity_breaks"` o ausente → valida `tiers` como hoy (retrocompatibilidad: las ofertas de
  escalones ya escritas no declaran `type` en algunos casos y deben seguir pasando).

Es el cambio que "enseña al guard a leer `type`" — el campo estaba plantado y sin lector.

### 9.4 Unidades y el 100 justo (trampa)

`effect.percentage` es fracción; el techo es entero. Regla única del proyecto (§9.4 hermano):
`pct_entero = round(percentage × 100)`, bloquear si `pct_entero > maxGiftPct`. **El caso `1.0` → 100
debe pasar** cuando `maxGiftPct == 100` (sin off-by-one: la comparación es `>`, no `>=`). Test explícito
para el borde 100.

### 9.5 Por qué allowlist y no tope de valor

El guard **no ve precios** (lee la mutación y el metafield; no llama a Shopify). Un tope "el regalo ≤ X%
de lo comprado" o "≤ $50.000" sería inenforzable por el guard → sería seguridad-por-prosa. La allowlist
de gids (`giftableProducts`) es lo único enforzable de verdad: el guard chequea `get.product ∈ lista`.
Es más controlado y curado por el operador, coherente con la postura de achicar superficie (§6.3 hermano).

### 9.6 Bloqueos duros que siguen valiendo

- Las cinco variantes de borrado de descuento (§9.2 hermano) siguen duramente bloqueadas: el undo de
  regalo también es `Deactivate`, nunca `Delete`.
- `customerGets.items.all` no lo soporta BXGY, pero `collections` sí y es el equivalente peligroso: el
  guard lo bloquea en **los dos** lados (buy y get) salvo gids explícitos.
- `discount*BasicUpdate` sigue fuera de la whitelist (§6.3 hermano): sin update no hay forma de estirar
  `endsAt` ni cambiar `pct` después de creado.

### 9.7 Contrato de bloqueo y limitación heredada

`exit 2`, falla cerrado ante excepción sobre un tool de Shopify (§9.6 hermano). El techo se lee de
`clients/{slug}/deal-policy.json` con la misma limitación de scoping multi-cliente ya conocida (§9.7
hermano): a cerrar antes del 2º cliente.

---

## 10. Gobernanza: qué se actualiza dentro del milestone

- **`create-discount` sigue denegado** (no puede llevar techo, `endsAt`, ni scope validado). El camino
  canónico es `graphql_mutation` por la whitelist de §9.1. **No se agrega ninguna permission nueva**:
  BXGY va por el mismo `graphql_mutation` ya permitido.
- **`CLAUDE.md` regla 5** y **`store-standards.md`** se actualizan **como parte del milestone**: la clase
  "ofertas" pasa a declarar explícitamente el regalo (BXGY) además de los escalones, con su techo.
- `clients/_template/` hereda las cinco claves nuevas con los defaults seguros.

---

## 11. Flujo de datos

```
armar-combo (opcional)        Brain: co-compra (qué Q regalar con qué P)
        │                                   │
        └────────► armar-regalo ◄───────────┘
                       │
            ┌──────────┴───────────┐
            ▼                      ▼
  strategies/automatic.md    deal-policy.json (techo + giftableProducts)
            │                      │
            ▼                      ▼
  graphql_mutation ───────► backup_guard._check_bxgy ──► Shopify
  (discountAutomaticBxgyCreate)   (whitelist §9.1)          │
            │                                               │
            ▼                                               ▼
  metafieldsSet (type:"bxgy") ──► _check_metafield(type) ──► worker.deal
                                                              │
                                                              ▼
                                        widget switch(type)=bxgy ──► comprador
```

---

## 12. Errores y casos borde

| Caso | Comportamiento |
|---|---|
| Producto ya tiene escalones y se pide regalo | Preview ANTES vs DESPUÉS; al confirmar, reemplaza (metafield único, §5) |
| Cruzado con Q fuera de `giftableProducts` | El guard bloquea; el skill lo explica sin jerga y ofrece pedirle al operador que agregue Q |
| `pct` pedido supera `maxGiftPct` | Guard bloquea; skill explica el límite |
| `get.qty` supera `maxGetQty` | Guard bloquea |
| Mismo-producto con ratio insuficiente ("comprá 1 llevá 1") | Guard bloquea por `minBuyGetRatio` |
| `all_products[handle]` no resuelve el regalo | El widget no renderiza el bloque de regalo; ficha intacta (§4.3) |
| Carrito con unidades preexistentes de P | `update.js` fija la línea (§4.4/4.5) |
| Stock insuficiente para el regalo | Advertencia en preview, no bloqueo |
| `endsAt` ya pasó | Widget no renderiza; skill lo reporta como oferta vencida |
| Descuento BXGY huérfano (prefijo, no referenciado) | "sacá el regalo" lo detecta y ofrece desactivar (§7.4) |

---

## 13. Testing

### 13.1 Automatizado (pytest, extiende los tests actuales)

Sobre `_check_bxgy`:
- bloquea `discountAutomaticBxgyCreate` sin `endsAt` / con duración > `maxDurationDays`.
- bloquea `pct` sobre `maxGiftPct`, **incluida la trampa de unidades** (`effect.percentage: 0.7` con
  `maxGiftPct: 30` debe bloquear) y **permite el borde `1.0`→100 con `maxGiftPct: 100`**.
- bloquea `get.qty` > `maxGetQty`.
- bloquea `customerGets.value.percentage` y `discountAmount` top-level (formas no soportadas por BXGY).
- bloquea `collections`/`all` en `customerBuys` **y** en `customerGets`.
- bloquea cruzado si `get.product ∉ giftableProducts` o `allowCrossProductGift == false`.
- bloquea mismo-producto con `buy.qty < minBuyGetRatio × get.qty`.
- bloquea `usesPerOrderLimit != 1`.
- exige `productId` (=P) en variables y backup fresco; bloquea sin backup.
- bloquea el bypass por `variables` (mutación parametrizada, input señuelo).

Sobre `_check_metafield` ramificado:
- `type:"bxgy"` valida forma BXGY; `type:"quantity_breaks"`/ausente sigue validando `tiers` (regresión).
- un metafield `bxgy` con `pct` sobre techo o `get.qty` sobre `maxGetQty` bloquea.

Regresión: los tests de escalones siguen verdes (whitelist, borrados, deactivate sin condiciones,
cruce de backups descripción↔deal).

### 13.2 Manual, contra development store (NO en blunua)

- Mismo-producto: comprá 2 → 3º gratis; el carrito paga lo que cantó el botón.
- Cruzado: comprá P → Q aparece a $0; que la línea de $0 renderice bien.
- `usesPerOrderLimit: 1`: comprá 4 en una oferta "buy 2 get 1" → **solo 1 gratis**.
- Ciclo crear → verificar en checkout → sacar → verificar que dejó de aplicar.
- Reemplazo de escalones por regalo en el mismo producto.

### 13.3 No se testea en la tienda del cliente (§13.3 hermano). Se usa la dev-store.

---

## 14. Incógnitas empíricas — A RESOLVER (contra dev-store, mirror §14 hermano)

Método: crear los descuentos reales pasando por el guard y medir con `draftOrderCalculate`
(`acceptAutomaticDiscounts: true`), sin persistir pedido. Paso 0 obligatorio: `get-shop-info` confirma
que **no** es blunua producción antes de crear nada.

- **D1 — ¿`all_products[handle]` resuelve el regalo cruzado en la plantilla de producto?** Es la única
  dependencia nueva fuera del metafield (§4.3). Riesgo: el límite histórico de `all_products`. Fallback:
  guardar el display del regalo (título/imagen/variante) en el metafield, asumiendo staleness.
- **D2 — ¿Una línea de carrito a $0 (el regalo cruzado) se muestra y checkoutea bien?** El descuento
  nativo zerea Q; verificar que no rompa el render del carrito ni el checkout.
- **D3 — ¿`usesPerOrderLimit: 1` se comporta como dice el schema** (una sola aplicación aunque el
  carrito califique varias veces)? Confirmar contra `draftOrderCalculate`.
- **D4 — ¿BXGY mismo-producto y escalones sobre el mismo producto conviven si por error quedaran los
  dos activos?** No debería pasar (metafield único), pero confirmar el comportamiento nativo si dos
  automáticos califican, para la detección de huérfanos.

---

## 15. Fuera de alcance

- Los otros motores de §15 hermano (volume, cart-volume, mix&match, bundle, related products).
- Estrategia `codes` para BXGY (G9).
- Regalo parcial con **dos** techos simultáneos por valor (se resolvió con allowlist, G6).
- Empujar el widget por API; traducción/multi-idioma; escribir la oferta desde el Brain
  automáticamente; restore de ofertas.
- Coexistencia escalones + regalo en el mismo producto (metafield único, §5).

**Corte del plan:** guard + política + skill primero; dentro de eso, mismo-producto antes que cruzado
(G13); widget al final. El cruzado nace apagado (`giftableProducts: []`).

---

## 16. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Meter BXGY relaja el guard y queda a medias | Tests de `_check_bxgy` antes de tocar la whitelist; mismo-producto antes que cruzado (§9.0, G13) |
| Un regalo caro se da por `pct: 100` sin control | `maxGiftPct` + `maxGetQty` + (cruzado) allowlist `giftableProducts` (§8, §9.5) |
| "Comprá 1 llevá 1" saltea el techo de 30% de escalones | `minBuyGetRatio` enforced (§8) |
| El regalo se multiplica en el carrito | `usesPerOrderLimit: 1` forzado por el guard (§9.1, G12) |
| El guard aplica el schema de escalones a un metafield BXGY | `_check_metafield` ramifica por `type` (§9.3) |
| El borde `pct: 100` se bloquea por off-by-one | Comparación `>` y test explícito del borde 100 (§9.4) |
| El widget cruzado no encuentra el display del regalo | `all_products[handle]` con fallback; incógnita D1 (§4.3, §14) |
| Una línea de carrito a $0 rompe el checkout | Incógnita D2, verificada en dev-store (§14) |
| Un `create-discount` esquiva el techo | Sigue denegado; camino canónico `graphql_mutation` (§10) |
| El repo queda con una regla dura que el skill viola | `CLAUDE.md` regla 5 + `store-standards` se actualizan dentro del milestone (§10) |
| Escalones y regalo chocan en el mismo producto | Metafield único; el skill hace preview ANTES/DESPUÉS y reemplaza (§5, §12) |
| Se generaliza el builder y se rompe el camino de escalones | La generalización no toca la plata (reusa guard §9 + `_check_style`); round-trip y preview testeados por tipo (§17.6) |
| BXGY reinventa el render y diverge del builder | La rama `bxgy` vive en `worker-render.js`, fuente única; depende de la extracción del builder (G15, §4.2) |

---

## 17. Integración con el builder visual (el "constructor")

Este milestone cumple también la segunda mitad del pedido: **sumar el regalo al builder visual**
(`2026-07-21-escalones-builder-design.md`). El builder hoy está scopeado a solo-escalones (su D2 / §11
YAGNI) y **todavía no está implementado** (tiene spec + plan de 5 tasks). Acá se **generaliza a
por-tipo-de-oferta**, reusando toda su infraestructura sin duplicarla.

### 17.1 Qué se reusa tal cual

- **`worker.style`** (metafield cosmético, su guard `_check_style`, su backup `kind:"style"`): el look
  (colores + copy) aplica **igual** al widget de regalo. La misma validación cerrada de keys sirve; a lo
  sumo el set de textos gana el copy propio del regalo (badge "GRATIS") — un cambio acotado del set
  cerrado, no una relajación.
- **`worker-render.js`** (fuente única del render): gana la rama `bxgy` (§4.2). El builder reusa
  `WorkerEscalones.render()` para el preview del regalo con el **código real**, igual que para escalones.
- **El template + la lógica del builder** (`escalones-builder.*`): se generalizan (17.2).

### 17.2 El builder pasa a ser "por tipo de oferta"

- Gana un **selector de tipo** arriba: **Escalones | Regalo**. Según el tipo, muestra la sección de
  escalones (tiers) o la de regalo (comprá `qty` / regalá `qty` / `%` / mismo-producto vs cruzado, con
  el selector de producto-regalo limitado a `giftableProducts` horneado).
- El **techo horneado** incluye ahora las claves de regalo (`maxGiftPct`, `maxGetQty`, `minBuyGetRatio`,
  `allowCrossProductGift`, `giftableProducts`): la UI **no deja construir** un regalo fuera del techo,
  igual que hoy con escalones. La frontera de confianza en tres lugares (§5 builder) queda intacta.
- El **preview en vivo** usa el render real de la rama `bxgy`, con precios reales y el total honesto
  "pagás N" (§4.4).

### 17.3 El formato de la config

Espeja `🧩 escalones-config` con un marcador propio:

```
🎁 regalo-config
{ "v": 1, "scope": "same",
  "buy":  { "product": { "id": "gid://…/P", "title": "Anillo NEXO" }, "qty": 2 },
  "get":  { "product": { "id": "gid://…/P", "title": "Anillo NEXO", "handle": "anillo-nexo" }, "qty": 1, "pct": 100 },
  "style": { "ink": "#4B4B4B", "label": "Comprá más y llevate un regalo", "badge": "GRATIS" } }
```

- Marcador `🎁 regalo-config`. Mismo principio: es una **request, no una orden** — `armar-regalo` corre
  igual su paso 0 → techo → preview → gate → backup → write. No saltea el gate; el builder no es de
  confianza y Claude revalida contra `deal-policy.json` (§5 builder, §9 de este spec).
- Mapeo: `buy`/`get`/`scope` → `worker.deal` (`type:"bxgy"`); `style` → `worker.style`. El skill agrega
  `strategy`/fechas/`ref`; la config no los trae.

### 17.4 Del lado de Claude

`armar-regalo` aprende a ingerir `🎁 regalo-config` (la versión tipada de lo que el cliente diría
hablando), corre su flujo normal (§7) y **suma el write de estilo** a `worker.style` — dos asuntos → dos
writes → dos backups (`deals/` y `style/`), exactamente como `armar-escalones` con el builder. El preview
de texto del gate usa el mismo redondeo por unidad que el builder y el widget.

### 17.5 Generación

`generar-builder-escalones` se generaliza (o nace un `generar-builder` único): hornea productos + techo
(con las claves de regalo) + el render real (con la rama `bxgy`) en el template generalizado. Sigue sin
escribir nada a Shopify; sigue siendo un archivo que el cliente abre.

### 17.6 Orden y dependencia (G15)

El builder-escalones tiene su plan propio y **se ejecuta primero** (establece `worker.style`,
`worker-render.js`, el template). BXGY backend va segundo. La generalización del builder va tercero,
sobre las dos bases. Cada fase deja software testeable; la generalización **no toca la plata** (reusa el
guard de §9 y el `_check_style` del builder). El cruzado nace apagado (`giftableProducts: []`) también en
el builder: sin lista curada, el selector de producto-regalo aparece vacío y la UI no deja armar un
cruzado.
