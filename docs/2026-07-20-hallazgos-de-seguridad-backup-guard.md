# Hallazgos de seguridad en `backup_guard.py` (2026-07-20)

**Contexto:** encontrados mientras se implementaba el milestone de escalones por cantidad
(`docs/superpowers/plans/2026-07-19-escalones-m1-guard-politica-skill.md`). **Ninguno lo introdujo
ese milestone.** Los siete estaban en `main`, en producción, antes de empezar. Todos cerrados.

**Por qué este documento existe:** el spec padre §11 afirma que el alcance de escritura está
"enforced por código, no por prosa". Era cierto para el camino que se había probado, y falso para
varios que no. Dejar eso escrito importa más que el diff.

---

## La clase: "vacío" tratado como "limpio"

Seis de los siete son la misma falla. El guard parsea un payload, obtiene una estructura vacía, y
lo interpreta como **"no hay nada fuera de alcance"** en vez de **"no pude parsear esto"**.

> **Regla que sale de acá:** en un guard de seguridad, un parseo vacío es **desconocido**, nunca
> **limpio**. Si no pudiste leer qué toca un write, bloqueá.

---

## 1. El backup de descripción era una llave maestra de 15 minutos

**Severidad: alta.** El más grave de todos.

`_product_input_keys` busca `\b(?:product|input)\s*:\s*\{`. Las mutaciones que reciben
`productId:` como escalar más arrays (`options:`, `positions:`, `moves:`,
`sellingPlanGroupIds:`) **no tienen ningún objeto `input: {`**. El set de keys volvía vacío, `extra`
quedaba vacío, el control de alcance de campos pasaba **en el vacío**, y la ejecución caía en el
chequeo de backup — que estaba satisfecho, porque `mejorar-descripcion` acababa de escribir uno.

**Resultado:** durante los 15 minutos posteriores a cualquier mejora de descripción, **21 de las 26
mutaciones `product*` estaban habilitadas**, incluyendo duplicar el producto, reordenar variantes,
crear bundles y cambiar opciones.

Lo irónico: el docstring del propio guard dice que arregló *"un backup válido funcionaba como llave
de 15 minutos para cambiar precio o status"*. Ese arreglo solo cubrió las mutaciones con forma
`input: {...}`.

**Cerrado en `f1625bf`** — whitelist cerrada `PRODUCT_WRITE_ALLOWED = {"productupdate"}`, chequeada
por nombre **antes** del control de campos.

## 2. Un `Deactivate` inofensivo abría la puerta a todo lo demás

**Severidad: alta.**

GraphQL admite varios root fields en un mismo documento. `_discount_mutation` devolvía **solo el
primero**, y `discount*Deactivate` está permitido sin condiciones (§9.8 del spec: la compensación
tiene que funcionar siempre). Entonces:

```graphql
mutation {
  discountAutomaticDeactivate(id: "...") { id }   # matchea, se permite, RETORNA
  discountAutomaticDelete(id: "...") { deletedId } # nunca se evalúa
}
```

Eso destruía E5 —"desactivar, no borrar"— que todo el spec construye como enforced por código. La
misma forma servía con `productUpdate(status:)`, `productSet`, `productCreate` y `metafieldsSet`.

**Cerrado en `c9b2dea` + `5ba87bc`** — se inspeccionan **todas** las mutaciones del documento, y un
documento que mezcla asuntos (oferta + metafield + producto) se bloquea entero.

> El primer intento de arreglo fue parchear par por par. Cerró tres casos y dejó tres abiertos
> (`productSet`, `productCreate`, `metafieldsSet`), porque exigía enumerar correctamente un espacio
> combinatorio. **Cuando el arreglo depende de que hayas listado todos los casos, el arreglo está
> mal.**

## 3. `productCreate` por GraphQL nunca estuvo bloqueado

**Severidad: media.**

`permissions.deny` bloquea el **tool** `create-product` del connector. `FORBIDDEN_MUTATIONS` no
tenía `productcreate`. El camino GraphQL estaba abierto, contra lo que afirman la regla 5 del
`CLAUDE.md` y §11 capa 1 del spec.

**Cerrado en `f1625bf`** (mismo whitelist que #1).

## 4. La familia `collection*` estaba como estaba `product*`

**Severidad: media.**

La blocklist nombraba `collectionCreate` y `collectionUpdate`. Pasaban `collectionDelete`,
`collectionDuplicate` y `collectionReorderProducts`.

**Cerrado en `d3ab916`** — `COLLECTION_WRITE_ALLOWED = set()`, whitelist cerrada y vacía.

## 5. Los detectores eran ciegos a los dígitos

**Severidad: media.** El más barato de encontrar y el más fácil de repetir.

Los tres detectores usaban `\b(familia[A-Za-z]*)\s*\(`. Con `collectionAddProductsV2`, `[A-Za-z]*`
se detiene en la `V`, el `2` no es letra, y el `\(` nunca llega. **Cualquier mutación con un dígito
en el nombre era invisible** — y Shopify usa sufijos `V2`/`V3` de forma habitual.

O sea: la whitelist "cerrada" que se acababa de construir para tapar 21 bypasses tenía un agujero
con forma de número, en las tres familias a la vez.

No lo encontró ningún razonamiento. Lo encontró haber elegido, sin pensarlo, un ejemplo con un `2`.

**Cerrado en `d3ab916`** — `[A-Za-z0-9]*` en `discount*`, `product*` y `collection*`.

## 6. `productUpdate` sin `id` en las variables

**Severidad: baja hoy, alta si Shopify cambia.**

`_variables_product_keys` solo cosecha keys de los dicts de `variables` que contienen `id`. Un
`productUpdate(input: $input)` cuyo `input` **no** trae `id` no aportaba ninguna key → `extra`
vacío → pasaba con `handle` y `status` adentro.

El control lo dice todo: **el mismo write con `id` presente bloquea**. Hoy al guard lo salva que
Shopify exige `input.id` del lado del servidor — o sea, **la validación de la API, no la lógica del
guard**.

**Cerrado en `d3ab916`** — un set de keys sin `id` bloquea.

## 7. `metafieldsSet` sin `ownerId` bloqueaba de casualidad

**Severidad: baja.** Introducido y cerrado dentro del mismo milestone.

Sin `ownerId`, `owner` quedaba en `""` y el glob del backup pasaba a ser
`**/backups/deals/-*.json`. Un archivo llamado `-loquesea.json` lo satisface. Bloqueaba **solo
porque ese nombre no suele existir**, que no es una defensa.

**Cerrado en `7e16a56`** — se exige un gid de producto reconocible antes de buscar el backup.

---

## Bonus: el guard mentía en un mensaje de error

No es un agujero, pero cuesta lo mismo. `_discount_input` solo lee `variables`; con el payload
escrito inline en el query devolvía `{}` — que es un dict, así que el `isinstance` pasaba y la
ejecución caía en el chequeo de `endsAt`, respondiendo **"toda oferta necesita fecha de fin"** sobre
un documento que tiene el `endsAt` a la vista.

Quien lo leyera agregaría un `endsAt` que ya estaba, seguiría fallando, y terminaría sospechando
del guard. **Un guard que bloquea bien pero explica mal es un guard que alguien va a terminar
deshabilitando.** Eso es una falla de seguridad con otro nombre.

**Cerrado en `9053426`.**

---

## Ronda 2: lo que encontró el review adversarial final

Los siete de arriba salieron de **implementar**. Estos cuatro salieron de **atacar** — un review
final que escribió ~60 payloads y los ejecutó. **Dos los introdujo este milestone.**

### 8. El señuelo que anulaba todo el techo de una sola vez

**Severidad: alta. Introducido por este milestone.** El peor hallazgo de todos.

`_discount_input` devolvía **el primer** dict de `variables` que tuviera `customerGets`. El query
declara cuál variable usa realmente, y el guard **nunca los correlacionaba**. Las variables
sobrantes las ignora el servidor.

```json
query: "mutation ($real: DiscountAutomaticBasicInput!) { discountAutomaticBasicCreate(automaticBasicDiscount: $real) {...} }"
variables: {
  "aaa_decoy": { 5%, 12 días, un producto },        ← el guard validaba ESTE
  "real":      { 100%, 10 años, colección entera }  ← Shopify ejecutaba ESTE
}
```

En una sola llamada se salteaban `maxDiscountPct`, `maxDurationDays`, `allowCollectionScope` **y**
el bloqueo de `items.all`. Construimos un techo y era evitable poniendo un decorado adelante.

**Cerrado en `eeca31c`** — se validan **todos** los candidatos; más de uno se rechaza. No se intenta
correlacionar cuál nombra el query: ese parseo falla abierto, rechazar la ambigüedad falla cerrado.

### 9. En `metafieldsSet` en lote, el último backup autorizaba al primero

**Severidad: alta. Introducido por este milestone.** Peor de lo que decía el review.

El loop **sí** validaba todas las entradas, pero `owner = e.get("ownerId") or owner` se
reasignaba en cada vuelta. Dos entradas impecables sobre productos distintos pasaban con **un solo
backup**: el del segundo autorizaba la escritura del primero, que quedaba **sin undo**.

Estaba documentado en "Qué queda abierto" como una relajación acotada. Era un fail-open.

**Cerrado en `eeca31c`** — más de una entrada se rechaza.

### 10. El `re.search` que sobrevivió a su propio arreglo

**Severidad: alta.** Preexistente.

`_product_input_keys` usaba `re.search`: **solo el primer objeto de input**. Un documento con dos
`productUpdate` colaba el segundo entero:

```graphql
mutation { productUpdate(input: {id: "…", descriptionHtml: "<p>ok</p>"}) { product { id } }
           b: productUpdate(input: {id: "…", status: DRAFT, handle: "robado"}) { product { id } } }
```

El commit `c9b2dea` se llama *"inspeccionar TODAS las mutaciones del documento, no la primera"*.
Cerró esa clase para los **nombres** y dejó el `re.search` idéntico dos funciones más abajo, en el
control de **campos**. **Se arregló la instancia y se declaró cerrada la clase.**

**Cerrado en `eeca31c`** — `finditer` + unión de todos los objetos.

### 11. Todo lo que nadie enumeró estaba permitido

**Severidad: alta.** Preexistente.

La detección de asuntos conocía tres familias: `discount*`, `metafieldsSet`, `product*`. Cualquier
otra caía en el `allow` final. **16 mutaciones pasaban solas**, incluidas
`inventorySetOnHandQuantities` y `inventoryMoveQuantities` (stock), `themeFilesUpsert` (inyectar
`<script>` en el tema), `customerUpdate`, `orderUpdate`, `webhookSubscriptionCreate`,
`giftCardCreate`, `publicationUpdate`.

Y pasaban **montadas sobre una operación legítima**:
- `productUpdate` con una descripción real + `inventorySetOnHandQuantities(quantity: 0)` → allow
- `discountAutomaticDeactivate` + `inventorySetOnHandQuantities` → allow, **sin backup y sin
  `deal-policy.json`**, porque §9.8 le da paso libre al deactivate

Detalle amargo: `inventorySetQuantities` **sí** estaba en la blocklist, pero el chequeo es por
substring y `inventorySetOnHandQuantities` no la contiene. La entrada que existía para frenar
escrituras de stock no frenaba la que se usa.

**Cerrado en `eeca31c`** — allowlist sobre los root fields del documento:
`{productUpdate} ∪ whitelist de descuentos ∪ {metafieldsSet}`. Lo que nadie enumeró **bloquea**.

---

## Lo que costó invertir ese default

El *conjunto* permitido son tres nombres. Todo el costo estuvo en extraer los root fields de un
documento GraphQL sin un parser: aliases (`b: productUpdate(...)` pone el alias exactamente donde
va un root field), objetos literales dentro de los argumentos que suben la profundidad de llaves,
strings con `{` adentro que desincronizan el contador, la cabecera de la operación
(`mutation ($input: ProductInput!)`), y las directivas.

**Es un scanner hecho a mano en el camino de la plata.** Yerra cerrado por construcción, pero eso
significa que su modo de falla son los bloqueos falsos. Si aparecen, la decisión a tomar es
vendorizar un parser de verdad, no aflojar el scanner.

---

## Cómo apareció cada cosa

| Ronda | Qué la encontró | Hallazgos |
|---|---|---|
| — | Los **3 reviews del plan** (19 correcciones al documento) | **0** |
| 1 | **Implementar** el código | 7 |
| 2 | **Atacar** el código con ~60 payloads ejecutados | 4 |

Cero de los once salió de leer. Los tres reviews del plan mejoraron mucho el documento y no
encontraron un solo agujero.

---

## Lo que cambió en cómo está construido el guard

| Antes | Ahora |
|---|---|
| Blocklist de mutaciones prohibidas | **Whitelists cerradas** por familia: `discount*`, `product*`, `collection*` |
| `evaluate()` retornaba en el primer root field reconocido | Identifica **todos** los asuntos del documento y bloquea si mezcla |
| Parseo vacío = "nada fuera de alcance" | Parseo vacío = **desconocido → bloquea** |
| 3 entradas apuntando a mutaciones que ya no existen | Purgadas (`87e3436`) |

**65 → 164 tests.**

## Qué queda abierto

- ~~`metafieldsSet` en lote verifica el backup solo del último~~ — **era un fail-open, no una
  relajación acotada.** Ver hallazgo #9. Cerrado.
- **El scoping multi-cliente sigue pendiente** (spec padre §12, spec de escalones §9.7): el guard
  no sabe cuál es el cliente activo. Con un cliente no hay ambigüedad; antes del segundo hay que
  cerrarlo.
- **La frescura del backup sigue siendo un proxy**: "existe un backup cubriente de menos de 15
  minutos", no "se respaldó exactamente el valor que se está por sobrescribir".
