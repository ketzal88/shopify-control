# Escalones por cantidad (quantity breaks) — Design Spec

- **Fecha:** 2026-07-19
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** diseñado, sin implementar. Dos incógnitas empíricas abiertas (§13) que NO bloquean la construcción.
- **Cliente piloto:** blunua
- **Spec padre:** `2026-07-19-shopify-control-v1-design.md` (este documento extiende §13 "Combos como write")

---

## 1. Contexto y objetivo

El v1 de shopify-control escribe texto: descripción + SEO. `armar-combo` recomienda combos pero
explícitamente **no los crea**. Este milestone agrega el primer write que mueve plata: **escalones
por cantidad** en la ficha de producto ("llevá 2 y ahorrá 10%, llevá 3 y ahorrá 18%"), con el
widget que lo muestra y el descuento nativo que lo cobra.

Motivación comercial: subir el ticket promedio. El análisis de dos tiendas de referencia
(brickwar2.com con Upsell Koala, store.profitkoala.com como demo) mostró que el módulo de mayor
impacto en ticket es la escalera de cantidad, colocada **arriba del botón de comprar**.

**Por qué sin app de terceros:** las apps del rubro (Upsell Koala y equivalentes) resuelven la parte
cara de construir —app block + discount function + matriz de variantes— pero **no toman ninguna
decisión de negocio**: qué producto, qué umbral, qué %. Esa decisión es donde Worker tiene ventaja
(datos de co-compra y de ticket vía Worker Brain). Este diseño se queda con la decisión y usa el
motor nativo de Shopify para ejecutarla.

---

## 2. Decisiones tomadas (brainstorm)

| # | Decisión | Elección |
|---|----------|----------|
| E1 | Alcance del milestone | **Solo `quantity_breaks`** (+ regalo opcional vía BXGY en un milestone posterior). Es lo único expresable con descuentos nativos. |
| E2 | Quién autoriza | **Quien pide es quien autoriza.** Sin gate externo, consistente con D5 del spec padre. |
| E3 | Techo duro | **Sí, por cliente.** Límites mecánicos que la confirmación humana no puede saltear. |
| E4 | Instalación del widget | **Bloque Custom Liquid del editor de temas.** Cero writes a archivos del tema. |
| E5 | Semántica del undo | **Vencer, no borrar** (`endsAt = ahora`). Preserva el rastro histórico. |
| E6 | Capa de descuentos | **Estrategia intercambiable** (§6). Default `automatic`; `codes` como fallback documentado. |
| E7 | Preselección en el widget | **Arranca en 1 unidad**, con el escalón 2 destacado pero no marcado. Ver §4.3. |
| E8 | Skill | **Skill nuevo `armar-escalones`**, no una extensión de `armar-combo`. Ver §7. |

---

## 3. Arquitectura: cuatro piezas

| Pieza | Qué es | Cuándo se escribe | Depende de |
|---|---|---|---|
| **Widget** | Bloque Custom Liquid en la plantilla de producto | Una vez por cliente, a mano | del metafield |
| **Config** | Metafield `worker.deal` (JSON) por producto | Cada vez que se arma una oferta | de nada |
| **Descuento** | Objeto `DiscountAutomaticNode` nativo | Al publicar la oferta | de la estrategia (§6) |
| **Guardrail** | Extensión de `backup_guard.py` + `deal-policy.json` | — | del techo por cliente |

**Propiedad de aislamiento clave:** el widget lee del metafield y de nada más. No sabe si el
descuento se implementó como automático o como código. Por eso las incógnitas de §13 no lo tocan.

**Nota honesta sobre "estrategia intercambiable":** shopify-control no tiene runtime propio (son
skills en markdown + hooks de Python que solo hacen de guarda). La intercambiabilidad **no es
polimorfismo en código**: es un archivo de procedimiento por estrategia, y el skill apunta a uno.
Cumple el objetivo (cambiar de estrategia sin tocar widget, metafield, guard ni flujo) con un
mecanismo deliberadamente humilde.

---

## 4. El widget

### 4.1 Instalación

Bloque **Custom Liquid** agregado desde el editor de temas a la plantilla de producto, posicionado
inmediatamente **arriba** del botón "Agregar al carrito". Se pega una vez por cliente. No se
edita ningún archivo del tema ni se usa `themeFilesUpsert`.

El bloque contiene: un preámbulo Liquid que vuelca al DOM el metafield y la matriz de variantes
como `<script type="application/json">`, más el CSS y el JS del widget inline.

**Restricción a verificar en implementación:** que el bloque entre en el límite de tamaño del
setting de Custom Liquid. Presupuesto objetivo: **≤ 20 KB** sin minificar. Si no entra, el fallback
es alojar el JS como asset del tema (requiere subir un archivo, no editar uno existente).

### 4.2 Comportamiento

- Renderiza una fila por escalón: cantidad, precio total del escalón, precio tachado, badge de ahorro.
- El escalón marcado como `highlight` lleva el badge "MÁS ELEGIDO".
- Debajo de las filas, una **barra de progreso** con el empujón al siguiente escalón.
- El botón de comprar **canta la cantidad y el total**: `Agregar 2 al carrito · $160.200`.
- Al hacer click: `POST /cart/add.js` con la cantidad del escalón elegido.
- Si `strategy == "codes"`, después del add redirige a `/discount/{code}?redirect=/cart`.
  Es la **única** línea del widget sensible a la estrategia, y lee la bandera del metafield.

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
brickwar2. **Es una decisión revisable:** si se cambia, la condición no negociable es que el botón
siga cantando cantidad y total, porque el problema del default agresivo no es su tamaño sino que
la información quede fuera del momento de decidir.

### 4.5 Responsive

- **Desktop:** los tres escalones visibles para comparar.
- **Mobile (< 480px):** colapsa al escalón seleccionado + enlace "ver los demás". Sin colapso, el
  widget empuja el botón de comprar abajo del pliegue en un viewport de 390px.

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
      "ref": "gid://shopify/DiscountAutomaticNode/111" },
    { "qty": 3, "pct": 18,
      "ref": "gid://shopify/DiscountAutomaticNode/222" }
  ],
  "strategy": "automatic",
  "startsAt": "2026-07-20T00:00:00Z",
  "endsAt":   "2026-10-18T00:00:00Z",
  "createdBy": "shopify-control",
  "ts": "2026-07-19T22:40:00Z"
}
```

Reglas del schema:

- `tiers` ordenado ascendente por `qty`. El primer tier siempre `pct: 0`.
- Exactamente un tier con `highlight: true`.
- `ref` guarda el ID del descuento creado. **Es lo que hace posible el undo de E5**: sin él,
  "sacá los escalones" tendría que buscar el descuento por título, que es frágil.
- `strategy` viaja en el dato, no solo en el skill: si se migra de `automatic` a `codes`, los
  productos viejos siguen declarando cómo fueron creados y el undo sabe qué hacer con cada uno.
- `version` permite cambiar el schema sin romper widgets ya instalados en otros clientes.
- Un producto **sin** el metafield, o con `tiers: []`, no muestra widget. Es el estado por defecto.

---

## 6. Estrategia de descuentos

```
.claude/skills/armar-escalones/strategies/
├── automatic.md    ← discountAutomaticBasicCreate   (default)
└── codes.md        ← discountCodeBasicCreate        (fallback, ver §13)
```

Cada archivo documenta tres operaciones con la misma forma de entrada y salida:

| Operación | Entrada | Salida |
|---|---|---|
| `crear` | product gid, tiers, startsAt, endsAt | un `ref` por tier con `pct > 0` |
| `vencer` | lista de `ref` | — (deja `endsAt = ahora`) |
| `verificar` | lista de `ref` | estado real leído del Admin API |

### 6.1 Estrategia `automatic` (default)

Un `DiscountAutomaticNode` por escalón con `pct > 0`. Mutación verificada contra el schema del
connector:

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

- `productDiscounts: false` para que los escalones entre sí no se acumulen (uno u otro).
- `orderDiscounts` y `shippingDiscounts` en `true` para no bloquear promos de envío del cliente.
- **`title` con prefijo `shopify-control ·`**: es lo que permite auditar en el admin de Shopify qué
  descuentos creó la herramienta y cuáles puso una persona a mano.

`vencer` usa `discountAutomaticBasicUpdate` sobre el mismo id, con `endsAt` = ahora.

### 6.2 Estrategia `codes` (fallback)

Un `DiscountCodeBasicNode` por escalón, con el **mismo** `minimumRequirement` de cantidad — así el
código no aplica aunque alguien lo comparta sin cumplir la condición. El widget aplica el código
vía `/discount/{code}?redirect=/cart` después del `cart/add.js`.

Existe porque **elimina las dos incógnitas de §13**: el widget decide qué código aplicar (no
Shopify), y el límite de códigos es órdenes de magnitud mayor que el de automáticos.

Se documenta ahora y **se implementa solo si el test de §13 lo exige.**

---

## 7. El skill `armar-escalones`

Skill nuevo, no una extensión de `armar-combo`. Razones:

1. `armar-combo` es read-only por diseño y por su propia descripción ("no crea el combo en
   Shopify"). Meterle un write rompe ese contrato.
2. Distinta clase de riesgo (plata vs texto) → distinto camino de guard, distinto backup, distinto gate.

`armar-combo` queda como el **upstream natural**: recomienda qué producto merece escalones;
`armar-escalones` los ejecuta.

### 7.1 Flujo fijo

Espeja el flujo de 9 pasos de `mejorar-descripcion` (§6 del spec padre), que es el patrón
establecido del repo:

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
7. BACKUP               clients/{slug}/backups/deals/{tail}-{fecha}.json con el metafield
                        anterior y sus refs (o null si no había).
8. ESCRIBIR             (a) crear descuentos según la estrategia → obtener refs
                        (b) metafieldsSet con los refs incluidos
                        Si (b) falla, vencer lo creado en (a) y reportar. Ver §11.
9. CONFIRMAR            "Listo. Para sacarlo: 'sacá los escalones del anillo NEXO'."
```

### 7.2 Flujo `sacar escalones` (undo)

```
1. leer el metafield actual → obtener refs y strategy
2. vencer cada ref según su strategy (endsAt = ahora). NUNCA borrar.
3. escribir el metafield con tiers: [] (el widget desaparece)
4. registrar en worklog
```

Si el metafield ya está vacío pero existen descuentos con prefijo `shopify-control ·` para ese
producto, el skill lo reporta como inconsistencia y ofrece vencerlos. Es el caso de un write a
medias del §11.

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
programáticamente para decidir si bloquea. Es exactamente la lección que el spec padre ya aprendió
con los backups (§6: "el hook tiene que leerlo programáticamente, por eso `.json` y no `.md`").
Parsear prosa markdown dentro de un guard de seguridad es frágil.

`store-standards.md` gana una sección **§11 Ofertas** que documenta la política en prosa para
humanos y apunta al JSON como fuente de verdad. `clients/_template/` lo hereda con valores
conservadores.

---

## 9. Guardrail: extensión de `backup_guard.py`

### 9.1 Mutaciones permitidas (nuevas)

Todas por `graphql_mutation`, y **solo** si pasan sus condiciones:

| Mutación | Condiciones |
|---|---|
| `discountAutomaticBasicCreate` | `endsAt` presente · duración ≤ `maxDurationDays` · `percentage` ≤ `maxDiscountPct` · `items.products` con ids explícitos · backup fresco |
| `discountAutomaticBasicUpdate` | solo si el único cambio es `endsAt` (es la operación de vencer) |
| `metafieldsSet` | `namespace == "worker"` · `key == "deal"` · `ownerType == PRODUCT` · el JSON valida contra el schema de §5 |
| `discountCodeBasicCreate` | **solo** si `"codes" in enabledStrategies` del cliente |

### 9.2 Bloqueos duros (no hay backup que los habilite)

- `discountAutomaticDelete` y `discountCodeDelete` — **la decisión E5 (vencer, no borrar) queda
  enforced por código**, no por prosa del skill.
- Cualquier descuento con `customerGets.items.all: true`.
- Cualquier descuento con `customerGets.items.collections` si `allowCollectionScope` es false.
  Es el bloqueo de mayor valor: un descuento a nivel colección es el que puede vender el catálogo
  entero con rebaja.
- `metafieldsSet` sobre cualquier namespace distinto de `worker`.

### 9.3 Lectura de variables

Igual que la corrección ya aplicada en el guard (§11 capa 2 del spec padre): hay que inspeccionar
**el query y `tool_input.variables`**. Mirar solo el string del query deja pasar cualquier mutación
parametrizada, que es la forma idiomática de escribir GraphQL.

### 9.4 Contrato de bloqueo

`exit 2`, como el resto. Ante excepción inesperada sobre un tool de Shopify, **falla cerrado**.

### 9.5 Limitación heredada

El techo se lee de `clients/{slug}/deal-policy.json`, pero el guard **no sabe cuál es el cliente
activo** — es la misma limitación de scoping multi-cliente ya documentada en §12 del spec padre.
Con un solo cliente no hay ambigüedad. **Antes del 2º cliente hay que cerrar las dos juntas**
(scoping de backups y resolución del cliente activo), porque comparten causa raíz.

---

## 10. Flujo de datos completo

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
      (crear descuentos)         (valida)             │
              │                                       │
              ▼                                       ▼
      metafieldsSet ────────────────────────► worker.deal
                                                      │
                                                      ▼
                                        widget (Custom Liquid) ──► comprador
```

---

## 11. Errores y casos borde

| Caso | Comportamiento |
|---|---|
| Los descuentos se crean pero `metafieldsSet` falla | El skill **vence lo creado** y reporta. Deja la tienda en el estado previo. |
| Un `discountAutomaticBasicCreate` falla a mitad de los escalones | Vence los ya creados y aborta. No se escribe metafield parcial. |
| El producto ya tiene un `worker.deal` activo | El preview muestra ANTES vs DESPUÉS. Al confirmar, vence los descuentos viejos antes de crear los nuevos. |
| Descuentos huérfanos (existen con el prefijo, sin metafield) | `sacar escalones` los detecta y ofrece vencerlos (§7.2). |
| El % pedido supera el techo | El guard bloquea y el skill explica el límite en lenguaje natural, sin jerga. |
| El producto no tiene stock suficiente para el escalón mayor | Advertencia en el preview, no bloqueo: Shopify ya maneja el oversell según la política de la tienda. |
| El widget no encuentra el metafield | No renderiza nada. La ficha queda como estaba. |
| `endsAt` ya pasó | El widget no renderiza y el skill lo reporta como oferta vencida. |

---

## 12. Testing

### 12.1 Automatizado (pytest, extiende los 65 tests actuales)

Sobre el guard:
- bloquea `discountAutomaticBasicCreate` sin `endsAt`
- bloquea `percentage` por encima de `maxDiscountPct`
- bloquea duración por encima de `maxDurationDays`
- bloquea `items.all: true`
- bloquea scope por colección cuando `allowCollectionScope: false`
- bloquea `discountAutomaticDelete` **siempre**
- bloquea `metafieldsSet` con namespace distinto de `worker`
- bloquea el bypass por `variables` (mutación parametrizada)
- permite el camino feliz completo con backup fresco
- valida el JSON del metafield contra el schema de §5

### 12.2 Manual, contra development store

- Matriz de widget: desktop / mobile 390px, cambio de escalón, colapso en mobile.
- Que la cantidad en el carrito coincida con la que cantaba el botón.
- Que el precio del carrito coincida con el que mostraba el widget (**el fallo que se
  observó en brickwar2: widget mostrando un total que el carrito no respeta**).
- Ciclo completo crear → verificar en checkout → sacar → verificar que dejó de aplicar.

### 12.3 No se testea en la tienda del cliente

Los descuentos automáticos son objetos a nivel tienda que se evalúan en cada checkout. La
verificación va contra development store. Un producto en `DRAFT` no sirve: su URL da 404 y no se
puede agregar al carrito, que es justamente lo que hay que probar.

---

## 13. Las dos incógnitas empíricas

Ninguna bloquea la construcción del widget, el metafield, el skill ni el guard. Ambas se responden
contra development store, y solo determinan cuál de las dos estrategias de §6 queda activa.

**A — ¿Shopify permite más de un descuento automático activo a la vez?**
Es eliminatoria para la estrategia `automatic`: los escalones necesitan uno por tier. Si la
respuesta es no, se activa `codes` y no se toca nada más.

**B — Si dos califican a la vez, ¿cuál aplica?**
Un comprador que lleva 3 califica para "min 2" y para "min 3". Si Shopify aplica el más favorable,
los escalones funcionan solos. Si aplica por orden de creación o exige prioridad manual, hay que
administrar prioridades o pasar a `codes`.

**Procedimiento:** crear dos descuentos automáticos sobre un producto de prueba (min 2 → 10%,
min 3 → 20%), agregar 3 unidades al carrito y leer el precio en el checkout.

---

## 14. Fuera de alcance de este milestone

- Los otros 5 motores relevados (volume, cart volume, bundle por composición, mix & match,
  related products). El bundle por composición **no es expresable** con descuentos nativos:
  `minimumRequirement` solo admite cantidad o subtotal, no composición. Exige Discount Function.
- Regalo gratis (`discountAutomaticBxgyCreate`). Es el siguiente candidato natural.
- Escribir la config de la oferta desde el Brain automáticamente. Por ahora `armar-combo` propone
  en texto y una persona decide.
- Empujar el widget a la tienda por API. Se pega a mano una vez (E4).
- Traducción / multi-idioma del widget.

---

## 15. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un descuento mal scopeado vende el catálogo con rebaja | `allowCollectionScope: false` + bloqueo de `items.all` en el guard (§9.2) |
| Un typo en el % (7 → 70) llega a producción | `maxDiscountPct` en `deal-policy.json`, enforced por código, no salteable por confirmación (E3) |
| Oferta que nunca termina | `requireEndsAt` + `maxDurationDays` (§9.1) |
| El widget muestra un precio que el carrito no respeta | Test explícito en §12.2. Es el bug observado en brickwar2. |
| Write a medias (descuentos sí, metafield no) | Compensación explícita en §11: vencer lo creado y reportar |
| Se elige `automatic` y resulta inviable | Estrategia intercambiable (§6) — cambia un puntero, no el diseño |
| Descuentos creados a mano se confunden con los de la herramienta | Prefijo `shopify-control ·` en el `title` (§6.1) |
| El techo se lee del cliente equivocado con 2+ clientes | Limitación conocida y heredada (§9.5). A cerrar junto con el scoping de backups del spec padre §12. |
| El bloque Custom Liquid no entra en el límite de tamaño | Presupuesto ≤ 20 KB + fallback documentado a asset del tema (§4.1) |
