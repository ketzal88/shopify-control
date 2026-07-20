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

## Lo que cambió en cómo está construido el guard

| Antes | Ahora |
|---|---|
| Blocklist de mutaciones prohibidas | **Whitelists cerradas** por familia: `discount*`, `product*`, `collection*` |
| `evaluate()` retornaba en el primer root field reconocido | Identifica **todos** los asuntos del documento y bloquea si mezcla |
| Parseo vacío = "nada fuera de alcance" | Parseo vacío = **desconocido → bloquea** |
| 3 entradas apuntando a mutaciones que ya no existen | Purgadas (`87e3436`) |

**65 → 146 tests.**

## Qué queda abierto

- **`metafieldsSet` en lote sobre varios productos verifica el backup solo del último.** El techo
  (`pct`, `maxTiers`, namespace) sí se aplica a todas las entradas, así que el riesgo de plata está
  acotado; lo que se relaja es la garantía de backup. El skill escribe un producto por vez.
- **El scoping multi-cliente sigue pendiente** (spec padre §12, spec de escalones §9.7): el guard
  no sabe cuál es el cliente activo. Con un cliente no hay ambigüedad; antes del segundo hay que
  cerrarlo.
- **La frescura del backup sigue siendo un proxy**: "existe un backup cubriente de menos de 15
  minutos", no "se respaldó exactamente el valor que se está por sobrescribir".
