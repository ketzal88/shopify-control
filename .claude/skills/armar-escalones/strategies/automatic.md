# Estrategia `automatic` (default)

Un descuento automático por escalón con descuento. El comprador no ingresa nada: la tienda aplica el
porcentaje sola cuando el carrito cumple la cantidad mínima.

Es la estrategia por defecto. Usala salvo que `deal-policy.json` del cliente **no** la habilite en
`enabledStrategies`, o que el operador indique lo contrario.

Documenta cuatro operaciones: **crear**, **publicar** (común a las dos estrategias), **desactivar** y
**verificar**.

---

## Reglas que valen para las cuatro operaciones

Son las que hacen que la operación pase. Ninguna es opcional y ninguna se puede inferir del ejemplo:

1. **El objeto del descuento va en `variables`, NUNCA escrito adentro del texto de la consulta.**
   La validación lee `tool_input["variables"]` y nada más. Si armás el payload inline dentro del
   string —`discountAutomaticBasicCreate(automaticBasicDiscount: { title: "...", ... })`— no hay
   nada que leer, se rechaza **el 100% de las llamadas**, y el mensaje de error no va a explicar por
   qué. Escribí la consulta con variables tipadas y mandá los valores aparte, siempre.

2. **`productId` va siempre como variable, aunque la mutación no lo consuma.** Es lo que se usa para
   encontrar el backup que habilita la escritura. Cuando el alcance es por variante
   (`productVariantsToAdd`), los ids de adentro de `items` son de variante y **no contienen el gid
   del producto**, así que no hay de dónde derivarlo. Sin `productId` no pasa ninguna creación.

3. **Una sola creación por llamada.** Tres escalones con descuento son tres llamadas. Si mandás dos
   creaciones en el mismo pedido, se rechaza entero: solo se puede verificar el techo de una.

4. **Un solo asunto por pedido.** Crear, publicar y desactivar van en llamadas separadas. Un pedido
   que mezcle un descuento con la oferta del widget, o con una edición de producto, se rechaza
   completo.

5. **Los porcentajes se convierten acá y en ningún otro lado.** El escalón dice `pct: 10` (entero).
   La API pide **fracción**: `0.10`. La conversión es `pct / 100` y ocurre **solo** al armar esta
   mutación. Al revés —mandar `10` donde va `0.10`— crearías un descuento de **1000%**.

6. **`endsAt` siempre.** Una creación sin fecha de fin se rechaza, y la duración no puede superar
   `maxDurationDays`.

7. **Backup fresco de oferta** (`kind: "deal"`, bajo `backups/deals/`, ≤ 15 minutos) antes de crear
   y antes de publicar. Desactivar **no** lo exige, a propósito: la limpieza no puede depender de un
   estado que ella misma modifica.

8. Validá el documento con `Shopify:validate_graphql_codeblocks` antes de mandarlo.

---

## `crear`

**Entrada:** gid del producto, escalones (`qty` + `pct` entero), `startsAt`, `endsAt`.
**Salida:** por cada escalón con `pct > 0`, el `ref` (el id del descuento creado).

Una llamada a `Shopify:graphql_mutation` **por escalón con descuento**. El escalón de 1 unidad no
genera descuento: es el precio normal.

```graphql
mutation ($d: DiscountAutomaticBasicInput!) {
  discountAutomaticBasicCreate(automaticBasicDiscount: $d) {
    automaticDiscountNode { id }
    userErrors { field message }
  }
}
```

Variables (esto va en `variables`, no en el texto de arriba). **`productId` va acá aunque el query
NO lo declare** (`$productId: ID!` en la firma hace que Shopify rechace la mutación por "variable
declarada y no usada"; como variable extra no declarada, Shopify la ignora y el guard la lee):

```json
{ "productId": "gid://shopify/Product/999",
  "d": { "title": "shopify-control · NEXO Plateado · 2+",
         "startsAt": "2026-07-20T00:00:00Z",
         "endsAt":   "2026-10-18T00:00:00Z",
         "minimumRequirement": { "quantity": { "greaterThanOrEqualToQuantity": "2" } },
         "customerGets": { "value": { "percentage": 0.10 },
                           "items": { "products": { "productsToAdd": ["gid://shopify/Product/999"] } } },
         "combinesWith": { "productDiscounts": false, "orderDiscounts": true, "shippingDiscounts": true } } }
```

Campo por campo, y por qué:

- **`title` con prefijo `shopify-control ·`** — obligatorio. Es lo que permite después distinguir en
  el admin qué descuentos creó la herramienta y cuáles puso una persona a mano, y es la base de la
  detección de huérfanos. Formato: `shopify-control · {producto} · {qty}+`.
- **`greaterThanOrEqualToQuantity`** viaja como **string** (`"2"`), no como número. Es la API.
- **`percentage`** es fracción: `pct / 100`. `10` → `0.10`.
- **`items.products.productsToAdd`** con ids **explícitos**. Nunca `all: true` (descuento sobre todo
  el catálogo) y nunca `collections` salvo que la política del cliente lo habilite; las dos cosas se
  rechazan.
  - Si el escalón tiene que exigir N unidades de la **misma variante**, se usa
    `items.productVariants.productVariantsToAdd` con los gids de variante — y ahí `productId` como
    variable es todavía más necesario, porque el gid del producto ya no aparece en ningún otro lado.
- **`combinesWith.productDiscounts: false`** — para que los escalones entre sí no se acumulen.
  `orderDiscounts` y `shippingDiscounts` en `true` para no romper las promos de envío del cliente.
- **`productId`** — redundante a propósito. Ver la regla 2.

**Si falla alguna creación a mitad de camino:** desactivá las que ya creaste (abajo), abortá, y
contáselo al cliente. No publiques una oferta a medias.

---

## `publicar` (común a las dos estrategias)

Escribe la oferta que lee el widget de la ficha. Va **después** de crear y **antes** de desactivar
lo viejo.

```graphql
mutation ($metafields: [MetafieldsSetInput!]!) {
  metafieldsSet(metafields: $metafields) {
    metafields { id }
    userErrors { field message }
  }
}
```

```json
{ "metafields": [ {
    "ownerId": "gid://shopify/Product/999",
    "namespace": "worker",
    "key": "deal",
    "type": "json",
    "value": "{\"version\":1,\"type\":\"quantity_breaks\",\"tiers\":[{\"qty\":1,\"pct\":0},{\"qty\":2,\"pct\":10,\"highlight\":true,\"ref\":\"gid://shopify/DiscountAutomaticNode/111\",\"code\":null},{\"qty\":3,\"pct\":18,\"ref\":\"gid://shopify/DiscountAutomaticNode/222\",\"code\":null}],\"strategy\":\"automatic\",\"startsAt\":\"2026-07-20T00:00:00Z\",\"endsAt\":\"2026-10-18T00:00:00Z\",\"createdBy\":\"shopify-control\",\"ts\":\"2026-07-19T22:40:00Z\"}"
} ] }
```

- **`ownerId` es obligatorio y tiene que ser el gid del producto.** Sin él no hay contra qué buscar el
  backup y se rechaza.
- **`namespace` solo `worker`, `key` solo `deal`.** Cualquier otro par se rechaza.
- **`value` es un string** con el JSON adentro (`type: "json"`), no un objeto.
- Las entradas van en `variables`, en una lista. No inline.

Reglas del contenido, **todas verificadas antes de escribir**; si alguna falla, se rechaza:

| Regla | Detalle |
|---|---|
| `pct` **entero 0–100** | `10`, no `0.10`. Acá NO se convierte a fracción: eso pasa solo al crear el descuento. |
| `pct` ≤ `maxDiscountPct` | de cada escalón, no del promedio |
| `qty` entero ≥ 1 | |
| `qty` ascendente | `[1, 2, 3]`, nunca desordenado |
| sin `qty` repetidos | |
| primer escalón `pct: 0` | es el precio normal, la referencia |
| **exactamente un** `highlight: true` | ni cero ni dos |
| `len(tiers)` ≤ `maxTiers` | |

`ref` guarda el id del descuento de ese escalón. `code` va en `null` con esta estrategia (con
`codes` lleva el string del código). El escalón de 1 unidad no lleva `ref` ni `code`.

**Para sacar la oferta:** el mismo llamado con `"tiers":[]`. La lista vacía es válida y es lo que
apaga el widget. Igual necesita backup fresco.

---

## `desactivar`

**Entrada:** lista de `ref`. **Salida:** —

Una llamada por `ref`, para saber cuál falló si falla alguna.

```graphql
mutation ($id: ID!) {
  discountAutomaticDeactivate(id: $id) {
    automaticDiscountNode { id }
    userErrors { field message }
  }
}
```

```json
{ "id": "gid://shopify/DiscountAutomaticNode/111" }
```

- **Nunca `discountAutomaticDelete`** ni ninguna variante de borrado, ni en bulk. Están bloqueadas y
  con razón: desactivar es reversible desde el admin con un click, borrar no.
- **Nunca `discountAutomaticBasicUpdate` con `endsAt` = ahora** para "vencer" el descuento. Shopify
  rechaza `endsAt <= startsAt`, así que una oferta con fecha de arranque futura quedaría **imposible
  de apagar**: el update falla, borrar está bloqueado, y queda un descuento huérfano que entra en
  vigencia al día siguiente sin forma de frenarlo. Tampoco existe camino de update por otro motivo:
  sin él nadie puede estirar la fecha de fin ni cambiar el porcentaje después de creado.
- Desactivar **no exige backup** y se permite sobre cualquier id, incluso uno que no figura en
  ninguna oferta — que es exactamente el caso de los huérfanos y el de la compensación.
- Un pedido puede llevar varias desactivaciones, pero **no** puede llevar una desactivación y
  cualquier otra cosa.

---

## `verificar`

**Entrada:** lista de `ref`. **Salida:** el estado real leído del Admin API.

Solo lectura, con `Shopify:graphql_query`:

```graphql
query ($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on DiscountAutomaticNode {
      id
      automaticDiscount {
        ... on DiscountAutomaticBasic {
          title status startsAt endsAt
          customerGets { value { ... on DiscountPercentage { percentage } } }
        }
      }
    }
  }
}
```

Verificá después de crear y después de desactivar:

- **Después de crear:** que los tres estén `ACTIVE` (o `SCHEDULED` si la oferta arranca a futuro), que
  el `percentage` sea el que corresponde y que `endsAt` sea el que mostraste en el preview. Si algo no
  coincide, no publiques: desactivá lo creado y reportá.
- **Después de desactivar:** que hayan quedado en `EXPIRED`/inactivos. Si alguno sigue activo,
  reintentá; si el reintento falla, registralo en el worklog como pendiente y decíselo al cliente en
  lenguaje natural.

`percentage` vuelve en **fracción** (`0.1`). Para comparar contra el escalón, multiplicá por 100.

---

## Checklist antes de mandar cada operación

- [ ] El payload va en `variables`, no adentro del texto de la consulta.
- [ ] `productId` está entre las variables, con el gid del **producto** (creación).
- [ ] Una sola creación en el documento, y ningún otro asunto mezclado.
- [ ] `percentage` en fracción (creación) / `pct` entero (oferta del widget).
- [ ] `endsAt` presente y dentro de `maxDurationDays`.
- [ ] Ids de producto o variante explícitos; nada de `all` ni de colecciones.
- [ ] Backup de oferta guardado hace menos de 15 minutos (creación y publicación).
- [ ] Documento validado con `Shopify:validate_graphql_codeblocks`.
