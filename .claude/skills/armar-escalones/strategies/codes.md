# Estrategia `codes` (fallback)

Un código de descuento por escalón, con la **misma** condición de cantidad mínima. El comprador no
lo tipea: el widget de la ficha lo aplica solo al hacer click, redirigiendo a
`/discount/{code}?redirect=/cart` con el código que trae la oferta.

**No la uses salvo que el operador la habilite.** Solo corre si `deal-policy.json` del cliente tiene
`"codes"` en `enabledStrategies`; si no está, toda creación se rechaza. Para blunua hoy la
estrategia habilitada es `automatic`.

Existe porque elimina dos incógnitas de la estrategia automática: acá el widget decide qué código
aplicar (no la tienda), y el límite de códigos por tienda es órdenes de magnitud mayor que el de
descuentos automáticos. Se documenta ahora y **se implementa solo si el test contra development
store lo exige**.

**Rige exactamente el mismo techo que `automatic`**: fecha de fin obligatoria, duración acotada,
porcentaje bajo `maxDiscountPct`, ids explícitos y backup fresco. Activar el fallback no puede
degradar la seguridad.

---

## Reglas que valen para las cuatro operaciones

Las mismas ocho de `automatic.md`, sin excepción. Las tres que más se rompen acá:

1. **El objeto del descuento va en `variables`, NUNCA inline en el texto de la consulta.** La
   validación lee `tool_input["variables"]` y nada más: un payload escrito adentro del string se
   rechaza **en el 100% de las llamadas** y el error no explica por qué.
2. **`productId` va siempre como variable**, aunque la mutación no lo consuma: es lo que se usa para
   encontrar el backup. Con alcance por variante no hay de dónde derivarlo.
3. **Una sola creación por llamada, un solo asunto por pedido.**

Y una propia de esta estrategia:

4. **El código se verifica antes de crearlo.** Los códigos son únicos por tienda: crear uno repetido
   falla, o peor, pisa una promo del cliente.

---

## El código

Formato: `{HANDLE_EN_MAYUSCULAS_SIN_GUIONES_MAX_12}-X{qty}`

`anillo-nexo-plateado` → `ANILLONEXOP-X2`, `ANILLONEXOP-X3`.

Antes de crear cada uno, consultá si ya existe (solo lectura, `Shopify:graphql_query`):

```graphql
query ($code: String!) { codeDiscountNodeByCode(code: $code) { id } }
```

Si devuelve algo, sufijá `-2`, `-3`, … (`ANILLONEXOP-X2-2`) y volvé a consultar hasta que dé `null`.

El código **tiene que quedar guardado en el campo `code` de su escalón** en la oferta del widget.
Sin eso la estrategia es inimplementable: desde el id del descuento el widget no puede derivar qué
código aplicar.

**El código nunca se le muestra al cliente en el preview.** Es un detalle de implementación: quien
compra hace click en un botón, no tipea nada.

---

## `crear`

**Entrada:** gid del producto, escalones (`qty` + `pct` entero), `startsAt`, `endsAt`.
**Salida:** por cada escalón con `pct > 0`, el `ref` (id del descuento) **y** el `code`.

Una llamada **por escalón con descuento**:

```graphql
mutation ($d: DiscountCodeBasicInput!) {
  discountCodeBasicCreate(basicCodeDiscount: $d) {
    codeDiscountNode { id }
    userErrors { field message }
  }
}
```

Variables (en `variables`, no en el texto de arriba). **`productId` va acá aunque el query NO lo
declare**: Shopify rechaza una variable declarada y no usada; como extra no declarada la ignora y
el guard la lee.

```json
{ "productId": "gid://shopify/Product/999",
  "d": { "title": "shopify-control · NEXO Plateado · 2+",
         "code": "ANILLONEXOP-X2",
         "startsAt": "2026-07-20T00:00:00Z",
         "endsAt":   "2026-10-18T00:00:00Z",
         "customerSelection": { "all": true },
         "minimumRequirement": { "quantity": { "greaterThanOrEqualToQuantity": "2" } },
         "customerGets": { "value": { "percentage": 0.10 },
                           "items": { "products": { "productsToAdd": ["gid://shopify/Product/999"] } } },
         "appliesOncePerCustomer": false,
         "combinesWith": { "productDiscounts": false, "orderDiscounts": true, "shippingDiscounts": true } } }
```

Diferencias con `automatic`, y solo estas:

- La mutación es `discountCodeBasicCreate` y el argumento se llama `basicCodeDiscount`.
- Se agrega **`code`** (el string calculado arriba) y **`customerSelection: { all: true }`** —
  cualquiera puede usarlo, la condición que lo limita es la cantidad mínima, no quién es.
  Ojo: `customerSelection.all` es quién puede usarlo. **`customerGets.items.all` sería el catálogo
  entero y está prohibido**; son campos distintos con el mismo nombre.
- `appliesOncePerCustomer: false`: la oferta se puede aprovechar más de una vez mientras esté vigente.
- **Sin `usageLimit`.** Un tope de usos convertiría la oferta en una carrera silenciosa: la ficha
  seguiría anunciando el precio después de agotado el cupo.

Todo lo demás es idéntico, **incluido el `minimumRequirement` de cantidad**: el código no aplica
aunque alguien lo comparta sin cumplir la condición.

Y siguen valiendo igual: `title` con prefijo `shopify-control ·`, `percentage` en **fracción**
(`pct / 100`), ids explícitos, nada de `all` ni de colecciones, `endsAt` obligatorio.

---

## `publicar`

Idéntico a la sección `publicar` de `automatic.md` — es común a las dos estrategias — con dos
diferencias en el contenido:

- `"strategy": "codes"` en lugar de `"automatic"`.
- Cada escalón con descuento lleva su **`code`** en vez de `null`:

```json
{ "qty": 2, "pct": 10, "highlight": true,
  "ref": "gid://shopify/DiscountCodeNode/111", "code": "ANILLONEXOP-X2" }
```

La estrategia viaja en el dato y no solo en el skill: si mañana se migra, los productos viejos
siguen declarando cómo fueron creados y el flujo para sacarlos sabe qué hacer con cada uno.

Todas las reglas del contenido son las mismas y se verifican igual: `pct` **entero** 0–100 y bajo
`maxDiscountPct`, `qty` ascendente sin repetidos, primer escalón en `pct: 0`, **exactamente un**
`highlight: true`, `len(tiers)` ≤ `maxTiers`. Y el mismo backup fresco.

---

## `desactivar`

Una llamada por `ref`:

```graphql
mutation ($id: ID!) {
  discountCodeDeactivate(id: $id) {
    codeDiscountNode { id }
    userErrors { field message }
  }
}
```

```json
{ "id": "gid://shopify/DiscountCodeNode/111" }
```

- **Nunca `discountCodeDelete`**, ni `discountCodeBulkDelete`, ni
  `discountCodeRedeemCodeBulkDelete`. Están bloqueadas: desactivar es reversible desde el admin,
  borrar no.
- **Nunca `discountCodeBasicUpdate`** para "vencer" el descuento moviendo `endsAt`. Shopify rechaza
  `endsAt <= startsAt`, así que una oferta con arranque futuro quedaría imposible de apagar. Además,
  sin camino de update nadie puede estirar la fecha de fin ni cambiar el porcentaje después de creado.
- Desactivar **no exige backup** y se permite sobre cualquier id, incluidos los huérfanos.
- El código queda inutilizable, pero el objeto y su historial se conservan.

---

## `verificar`

Solo lectura:

```graphql
query ($ids: [ID!]!) {
  nodes(ids: $ids) {
    ... on DiscountCodeNode {
      id
      codeDiscount {
        ... on DiscountCodeBasic {
          title status startsAt endsAt
          codes(first: 1) { edges { node { code } } }
          customerGets { value { ... on DiscountPercentage { percentage } } }
        }
      }
    }
  }
}
```

Además de estado, fechas y porcentaje (que vuelve en **fracción**: multiplicá por 100), verificá que
el **`code` devuelto sea exactamente el que guardaste** en la oferta del widget. Si no coincide, el
botón de la ficha va a aplicar un código que no existe y el comprador va a pagar precio de lista
después de que se le prometió un descuento. Si no coincide: no publiques, desactivá lo creado y
reportá.

---

## Checklist antes de mandar cada operación

- [ ] `"codes"` está en `enabledStrategies` del cliente.
- [ ] El payload va en `variables`, no adentro del texto de la consulta.
- [ ] `productId` está entre las variables, con el gid del **producto**.
- [ ] El código se consultó antes y no existía.
- [ ] Una sola creación en el documento, y ningún otro asunto mezclado.
- [ ] `percentage` en fracción (creación) / `pct` entero (oferta del widget).
- [ ] `endsAt` presente y dentro de `maxDurationDays`.
- [ ] `customerGets.items` con ids explícitos; nada de `all` ni de colecciones.
- [ ] Cada `code` quedó guardado en su escalón de la oferta del widget.
- [ ] Backup de oferta guardado hace menos de 15 minutos (creación y publicación).
- [ ] Documento validado con `Shopify:validate_graphql_codeblocks`.
