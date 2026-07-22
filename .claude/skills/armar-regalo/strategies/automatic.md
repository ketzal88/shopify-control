# Estrategia `automatic` — regalo con descuento automático (BXGY)

La única estrategia del regalo en el v1. Un **`DiscountAutomaticBxgyNode`** por oferta (uno solo, no
uno por escalón: el regalo es una regla única). Tres operaciones, misma forma de entrada/salida que
`armar-escalones`.

Verificado contra el connector real (introspección + `validate_graphql_codeblocks`): el regalo va
**siempre** por `customerGets.value.discountOnQuantity.effect.percentage`. La API rechaza
`customerGets.value.percentage` y `customerGets.value.discountAmount` en un BXGY, y el guard también
los bloquea. No los uses.

## `crear`

**Entrada:** product gid comprado (P), product gid regalado (Q; = P si es mismo-producto), `buy.qty`,
`get.qty`, `pct` entero 0–100, `startsAt`, `endsAt`.
**Salida:** el `ref` (gid del `DiscountAutomaticNode`).

```graphql
mutation ($d: DiscountAutomaticBxgyInput!, $productId: ID!) {
  discountAutomaticBxgyCreate(automaticBxgyDiscount: $d) {
    automaticDiscountNode { id }
    userErrors { field code message }
  }
}
```

```json
{ "productId": "gid://shopify/Product/P",
  "d": {
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

Reglas que el guard enforcea (y que no podés saltear):

- **`productId` va como variable EXTRA, NO en la firma.** Shopify rechaza una variable declarada y no
  usada (*"Variable $productId is declared by anonymous mutation but not used"*). El guard la lee de
  `variables.productId` para encontrar el backup; el servidor la ignora. Es el gid de **P** (el
  comprado), aunque el regalo sea cruzado.
- **`effect.percentage` es fracción `0.0–1.0`.** `pct` del metafield es entero: `1.0` = gratis = 100,
  `0.5` = mitad = 50. La conversión `pct/100` ocurre **acá y solo acá**.
- **`usesPerOrderLimit: "1"`** obligatorio: el regalo aplica una vez por pedido, no se multiplica.
- **Mismo producto:** el mismo gid en `customerBuys.items` y `customerGets.items`.
  **Cruzado:** gid de P en buys, gid de Q en gets. Q tiene que estar en `giftableProducts` del techo.
- **`productDiscounts: false`** para que el regalo no se apile con otros descuentos de producto.
- **Sin `all`, sin `collections`, sin variantes** en ninguno de los dos lados. Producto explícito.
- **`title` con prefijo `shopify-control ·`**: permite auditar en el admin qué creó la herramienta y
  detectar huérfanos.

## `desactivar`

`discountAutomaticDeactivate` (la misma primitiva que escalones — es genérica, sirve para cualquier
descuento automático). **Nunca** `Delete`. **Nunca** `Update` con `endsAt` en el pasado (Shopify
rechaza `endsAt <= startsAt`, y un regalo con `startsAt` futuro quedaría imposible de neutralizar).

```graphql
mutation { discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/333") {
  automaticDiscountNode { id } userErrors { field message } } }
```

Va **sin condiciones** para el guard (no exige techo ni backup): la compensación no puede depender de
un estado que ella misma modifica.

## `verificar`

Lee el estado real del Admin API para confirmar que quedó `ACTIVE` (o `EXPIRED` tras desactivar):

```graphql
query ($id: ID!) { discountNode(id: $id) { discount {
  ... on DiscountAutomaticBxgy { title status startsAt endsAt } } } }
```
