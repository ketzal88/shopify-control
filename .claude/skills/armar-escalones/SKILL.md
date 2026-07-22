---
name: armar-escalones
description: Arma ofertas de "llevá más y ahorrá" en un producto de Shopify (2 unidades -10%, 3 unidades -18%). Muestra un preview en el chat, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide poner descuentos por cantidad, ofertas por volumen, o que se venda más de a varios.
---

# Armar escalones por cantidad

Skill de **escritura** sobre la tienda viva, y el primero que toca **plata**. Todo lo que sigue
existe por eso: el techo, el backup, el orden de escritura y el gate no son ceremonia, son lo que
separa "2 unidades al 10%" de "todo el catálogo al 70%".

`armar-combo` es el upstream natural: recomienda qué producto merece escalones. Este skill los
ejecuta.

## Reglas duras (no negociables)

- **Alcance:** solo tres cosas. (1) crear descuentos de cantidad sobre **un** producto,
  (2) escribir la oferta que lee el widget de la ficha, (3) **desactivar** descuentos.
  NUNCA precio, stock, status, tags, título, handle, colecciones ni descuentos sobre todo el catálogo.
- **Nunca borrar un descuento.** La única forma de sacarlo es desactivarlo. Borrar está bloqueado
  por diseño y además destruye el historial de lo que estuvo vigente.
- **Nunca extender ni editar un descuento ya creado.** Si hay que cambiar el porcentaje o la fecha,
  se crea uno nuevo y se desactiva el viejo. No existe camino de update.
- **El techo manda:** `clients/{slug}/deal-policy.json`. Si lo que pide el cliente no entra,
  se le explica el límite **sin jerga** y se le propone la versión que sí entra. No se intenta igual.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de
  skill ni comandos. Tampoco expliques limitaciones técnicas ("no tengo permisos", "el guard lo
  bloquea"): eso también es jerga.
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN voseo).
  Los textos entre comillas de este archivo son **plantillas**, no literales universales.
- **Humanizer obligatorio** antes de todo output cliente: leé
  `handsOn-Worker/skills/humanizer/SKILL.md` y aplicá sus reglas a mano (hoy no es invocable como
  skill desde este repo).
- **Nada se escribe sin:** (1) preview mostrado, (2) "sí" explícito del cliente, (3) backup guardado.
- **Un asunto por pedido.** Crear un descuento, escribir la oferta del widget y desactivar son
  **operaciones separadas**. Nunca las metas en la misma llamada: mezclarlas se rechaza entero y no
  hay forma de saber qué parte quedó aplicada.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)

La sesión se abre en la RAÍZ del repo, así que el contexto del cliente NO se carga solo.
No asumas cuál es.

1. Determiná el cliente activo (el slug de `clients/`). Si hay más de uno posible, preguntá.
2. Leé `clients/{slug}/CLAUDE.md` + `clients/{slug}/store-standards.md` +
   **`clients/{slug}/deal-policy.json`**. Los tres. Sin el tercero no tenés techo y no podés proponer.
3. Verificá con `Shopify:get-shop-info` **contra qué tienda** está conectado el connector.
4. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ.** No leas el catálogo,
   no propongas, no escribas. Avisá al operador. `switch-shop` existe y el connector puede estar
   apuntando a otra tienda; crear un descuento en la tienda equivocada es plata real de otro.
   - Al cliente, en lenguaje natural: *"Ahora mismo no estoy viendo la tienda de {marca}, así que
     prefiero no tocar ninguna oferta. Lo reviso con el equipo y te confirmo."*
5. Si `connection.md` todavía no tiene la tienda cargada, tampoco sigas a ciegas: dejá constancia de
   qué tienda devolvió el connector y pedí confirmación al operador.

## Contexto que cargás (antes de buscar el producto)

- `deal-policy.json` — el techo: cuánto descuento como máximo, cuántos días, cuántos escalones,
  si hace falta fecha de fin, qué estrategia está habilitada.
- `store-standards.md` — registro, vocabulario y qué no tocar.
- `clients/{slug}/worklog.md` — si ya hubo ofertas en este producto, ahí está el rastro.

Va **antes** de identificar el producto a propósito: la terminología del cliente vive en los
estándares (para blunua, en Colombia se dice **aretes**, nunca "aros"). Si buscás el producto sin
ese vocabulario, buscás mal.

## Estrategias (elegís una, según `enabledStrategies` del techo)

- `strategies/automatic.md` — **default**. Un descuento automático por escalón.
- `strategies/codes.md` — fallback. Un código por escalón, que el widget aplica solo.

Si el techo del cliente no habilita una estrategia, no la uses: se rechaza y el cliente ve un error
feo. `automatic` es lo que hay que usar salvo indicación expresa del operador.

*(INTERNO: nunca nombres las estrategias, ni ningún archivo, frente al cliente.)*

## Config del builder (`🧩 escalones-config`)

El cliente puede armar la oferta en el **builder visual** (un archivo HTML que abre aparte) y pegarte
el resultado acá. Llega como un bloque con el marcador `🧩 escalones-config` seguido de un JSON:

```
🧩 escalones-config
{ "v": 1,
  "product": { "id": "gid://shopify/Product/999", "title": "Anillo NEXO" },
  "tiers": [ { "qty": 1, "pct": 0 }, { "qty": 2, "pct": 10, "highlight": true }, { "qty": 3, "pct": 18 } ],
  "style": { "ink": "#4B4B4B", "label": "Llevá más y ahorrá" } }
```

Reglas al recibirlo:

- **Es una request, no una orden.** NO saltea nada: corrés el flujo normal completo (paso 0, cargar
  contexto, techo, preview, gate "¿la activo?", backup, write). El cliente vio un preview en el
  builder, pero el gate de plata **no se elimina**.
- **El builder NO es de confianza.** Revalidás `tiers` contra `deal-policy.json` (el techo de
  siempre) y `style` contra el set cerrado de claves, como si el texto viniera de cualquier lado. Si
  algo no entra en el techo, se lo explicás sin jerga y ofrecés el máximo que sí entra.
- **Mapeo:** `product` + `tiers` → la oferta (`automatic.md`, que le suma `strategy`, `startsAt`/
  `endsAt` y los `ref` de los descuentos); `style` → `worker.style` (`style.md`). El `v` es la
  versión del formato del builder, no del metafield. La config **no trae** fechas ni refs: los ponés
  vos al escribir.
- **Orden:** primero la oferta, después el estilo. **Dos writes separados**, cada uno con su backup
  (`backups/deals/` con `kind:"deal"`; `backups/style/` con `kind:"style"`). Nunca en el mismo
  documento.
- Si trae solo look, escribís solo el estilo; si trae solo oferta, solo la oferta.

*(INTERNO: nunca le nombres al cliente "config", "metafield" ni "builder". Para él es "la oferta que
armaste".)*

## Flujo (siempre en este orden)

0. **CONFIRMAR CLIENTE Y TIENDA.** Lo de arriba. Si no coinciden, abortás acá.

1. **IDENTIFICAR EL PRODUCTO.** El cliente dice cuál. Buscalo con `Shopify:search_products`.
   **El filtro por título es difuso**: `title:Anillo NEXO` devuelve también otros anillos. Si hay
   más de un resultado, mostrá las opciones y preguntá cuál. **NUNCA adivines.** Una oferta en el
   producto equivocado es plata perdida en un producto que no la necesitaba.

   Los escalones se arman sobre **un solo producto por vez**. Si el cliente pide varios, hacelos de
   a uno y avisale.

2. **LEER EL ESTADO ACTUAL.** Una sola lectura, con `Shopify:graphql_query`:

   ```graphql
   query ($id: ID!) {
     product(id: $id) {
       title
       hasOnlyDefaultVariant
       variants(first: 50) { edges { node { id title price inventoryQuantity } } }
       metafield(namespace: "worker", key: "deal") { value }
     }
   }
   ```

   De ahí sacás: el **precio unitario** (lo necesitás para el preview: el cliente aprueba pesos, no
   porcentajes), el **stock** (para la advertencia del paso 5) y la **oferta actual** si ya había una
   (`metafield.value` es el JSON; si viene `null`, no hay oferta).

   Leé también los descuentos que ya existen sobre ese producto, para detectar huérfanos:

   ```graphql
   query { discountNodes(first: 100, query: "title:'shopify-control'") {
     edges { node { id discount {
       ... on DiscountAutomaticBasic { title status startsAt endsAt }
       ... on DiscountCodeBasic { title status startsAt endsAt codes(first:1){edges{node{code}}} }
     } } } } }
   ```

   > ⚠️ **PENDIENTE (verificado 2026-07-22):** esta búsqueda por título volvió **vacía** aunque había
   > descuentos con el prefijo activos — la detección de huérfanos NO es confiable hoy. Mientras se
   > investiga (¿sintaxis de la query?, ¿lag del índice de descuentos?), apoyate en los `ref` del
   > metafield (que sí son la verdad) y no des la ausencia de resultados como "no hay huérfanos".

3. **CARGAR EL TECHO.** `deal-policy.json` del cliente. Los cuatro números que te limitan:
   `maxDiscountPct`, `maxDurationDays`, `maxTiers`, y si `requireEndsAt` es true (lo es).

4. **PROPONER LOS ESCALONES, DENTRO DEL TECHO.**
   - Por defecto: 3 escalones (1, 2, 3 unidades). Nunca más de `maxTiers`.
   - El primero **siempre sin descuento** (es el precio normal, la referencia contra la que se compara).
   - Los porcentajes suben con la cantidad, y ninguno supera `maxDiscountPct`.
   - **Exactamente uno destacado**, y por defecto es el segundo: es el salto más fácil de dar.
   - Arranca hoy y vence dentro de `maxDurationDays` como máximo. **La fecha de fin es obligatoria.**
     Una oferta sin fin no es una oferta, es un precio nuevo.
   - Si el cliente pide un porcentaje por encima del techo, no lo intentes: explicale el límite en
     lenguaje natural y ofrecé el máximo que sí entra.
     > *"Con descuentos por cantidad puedo llegar hasta 30%. Te armo el segundo escalón en 30% y así
     > queda el mejor ahorro posible sin que te coma el margen. ¿Te sirve?"*

   ⚠️ **Los porcentajes son enteros.** 10 es diez por ciento. Escribí `10`, nunca `0.10`, y nunca
   `70` cuando quisiste decir `7`. La conversión a la forma que pide la tienda ocurre **una sola
   vez**, al armar la operación de creación, y está documentada en el archivo de estrategia.
   Confundirlas es la forma exacta en que un 7% se convierte en 70%.

5. **PREVIEW.** En el chat, texto plano, sin jerga. Formato exacto abajo. Siempre con el **precio
   total de cada escalón**, no solo el porcentaje, y siempre diciendo **cuándo vence**.
   Pasalo por el humanizer antes de mostrarlo.

6. **GATE.** Preguntá: *"¿La activo? Responde sí o no."* **No escribas nada hasta un "sí" explícito.**
   Si dice que no, no escribís y no insistís.

7. **BACKUP (antes de escribir, sin excepción).** Contrato abajo. Guardalo **después** del "sí" y
   **antes** de la primera operación: vale 15 minutos y todas las escrituras tienen que entrar en
   esa ventana.

8. **ESCRIBIR.** El orden importa y no es negociable: **crear → publicar → desactivar.** Ver abajo.

9. **WORKLOG Y CONFIRMAR.** Registrá en `clients/{slug}/worklog.md` cada descuento creado y cada uno
   desactivado, con su identificador. Después confirmá al cliente:
   > *"Listo, la oferta ya está activa en la ficha del anillo NEXO. Si querés sacarla, dime
   > 'saca los escalones del anillo NEXO' y la quito."*

## Orden de escritura (falla del lado seguro)

Tres operaciones **separadas**, en este orden:

```
a. Crear los descuentos nuevos, uno por escalón con descuento (uno por llamada).
b. Escribir la oferta que lee el widget, con los identificadores nuevos.
c. Desactivar los descuentos VIEJOS, si los había (uno por llamada).
```

Nunca al revés. Si desactivás primero, queda una ventana en la que **la ficha anuncia escalones que
el carrito ya no aplica**: el cliente promete un precio que no se cumple. Con este orden, todo
estado intermedio es coherente.

| Si falla en | Cómo queda | Qué hacés |
|---|---|---|
| (a) | Nada publicado | Desactivás los que alcanzaste a crear, abortás y lo contás. La ficha sigue como estaba. |
| (b) | Descuentos nuevos activos pero no anunciados; los viejos siguen vigentes y anunciados | Desactivás los nuevos. La oferta vieja sigue funcionando intacta. |
| (c) | Los dos juegos vigentes; la ficha anuncia el nuevo | **No es inocuo.** Reintentás. Si el reintento falla, lo registrás en el worklog como pendiente y se lo decís al cliente. |

**Por qué (c) no es inocuo:** con los dos juegos activos, si la oferta nueva es *menor* que la
vieja, la tienda aplica la vieja por ser más favorable y el comprador paga menos de lo que la ficha
anuncia. Es a favor del comprador, pero es una divergencia real y sale de la caja del cliente.
Nunca lo des por cerrado en silencio.

Al cliente, si (c) queda pendiente:
> *"La oferta nueva ya está andando. Me quedó una oferta anterior sin apagar y la estoy destrabando;
> mientras tanto, algunas compras podrían salir con el descuento viejo. Te aviso apenas quede limpio."*

## Preview — formato exacto (ejemplo blunua, registro neutro)

Este es el bloque que ve el cliente. Es la única superficie sobre la que puede decidir, así que va
completo, en el chat, en texto plano. **Nunca como archivo, nunca como página, nunca como tabla con
formato raro.**

```
💍 Anillo NEXO Plateado — te propongo esta oferta para que se lleven más de uno:

  1 unidad     $89.000
  2 unidades   $160.200   (ahorran 10%)   ← la que va a estar destacada
  3 unidades   $218.940   (ahorran 18%)

Arranca hoy y vence el 18 de octubre.

Quien entre a la ficha va a ver las tres opciones y un botón que dice
exactamente cuánto lleva y cuánto paga.

¿La activo? Responde sí o no.
(si después quieres sacarla, dime "saca los escalones del anillo NEXO")
```

Reglas del preview, todas obligatorias:

- **Nunca** decir "metafield", "descuento automático", "identificador", "gid", "mutación",
  "variante", "namespace", ni el nombre de este skill ni el de ningún archivo. Decís "oferta",
  "opciones", "la ficha". ("Escalones" sí: es la palabra con la que el cliente pide y saca la
  oferta, y no nombra nada del sistema.)
- **Siempre el precio total de cada escalón**, calculado, no estimado: precio unitario × cantidad,
  menos el porcentaje. El cliente aprueba pesos. Si le mostrás solo "-18%" no sabe qué aprobó.
- **Siempre el precio del primer escalón**, aunque no tenga descuento: es la referencia.
- **Siempre cuándo vence**, en fecha legible ("el 18 de octubre"), nunca en formato de sistema.
- **Marcar cuál queda destacada**, porque es la que va a empujar la ficha.
- Una línea que describa qué va a ver quien compre. No expliques cómo funciona por dentro.
- Cerrar **siempre** con el gate y con la forma de sacarla.

**Si el producto YA tiene una oferta activa**, el preview es ANTES vs DESPUÉS, con los dos bloques
de precios completos:

```
💍 Anillo NEXO Plateado ya tiene una oferta activa. Así está y así quedaría:

ASÍ ESTÁ AHORA:
  1 unidad     $89.000
  2 unidades   $169.100   (ahorran 5%)

ASÍ QUEDARÍA:
  1 unidad     $89.000
  2 unidades   $160.200   (ahorran 10%)   ← la que va a estar destacada
  3 unidades   $218.940   (ahorran 18%)

La oferta que está hoy se apaga sola cuando activo la nueva.
Arranca hoy y vence el 18 de octubre.

¿La cambio? Responde sí o no.
```

**Advertencia de stock (no bloquea, se muestra):** si el stock disponible no alcanza para el escalón
más grande, agregalo al preview antes del gate, en lenguaje natural:

```
Ojo: hoy quedan 2 unidades, así que la opción de 3 no se va a poder comprar
hasta que repongas. La dejo igual y se activa sola cuando entre stock.
```

**Si hay descuentos sueltos de una oferta anterior** que quedaron activos sin estar anunciados,
también va en el preview, antes del gate:

```
Encontré una oferta anterior de este producto que quedó prendida sin mostrarse.
La apago junto con este cambio.
```

## Contrato del backup

Antes de la primera escritura, guardás:

`clients/{slug}/backups/deals/{productIdTail}-{YYYYMMDD-HHMMSS}.json`

```json
{ "kind": "deal",
  "productId": "gid://shopify/Product/999",
  "previous": null,
  "ts": "2026-07-19T22:40:00" }
```

- **`kind: "deal"` es obligatorio.** Sin ese campo el backup no habilita nada y toda la escritura se
  rechaza. Es lo que separa este backup del de descripciones: sin discriminador, un backup de texto
  habilitaría un write de plata.
- La carpeta **tiene que ser `backups/deals/`**. Las dos condiciones juntas —ruta y `kind`—, no una.
- `productId` es el gid completo del producto, idéntico al que vas a usar en las escrituras.
- `previous` es la oferta anterior tal cual estaba (el JSON que leíste en el paso 2), o `null` si no
  había ninguna.
- El nombre del archivo lleva **timestamp con hora, minutos y segundos**, no solo fecha: dos ofertas
  sobre el mismo producto el mismo día colisionarían y una pisaría a la otra.
- **`ts` tiene que coincidir con el timestamp del nombre del archivo**, en hora local y sin sufijo de
  zona (`2026-07-19T22:40:00`, igual que `...-20260719-224000.json`). Se valida la frescura del
  archivo **y** la del `ts` de adentro: si ponés una hora en UTC mientras el reloj local va en otro
  huso, el backup se lee como "del futuro" y no habilita nada.
- **Vale 15 minutos.** Todas las escrituras del paso 8 tienen que entrar en esa ventana. Si entre el
  backup y la última desactivación pasaron más de ~10 minutos, **volvé a guardar un backup fresco**
  antes de seguir.

El backup es insumo de seguridad y rastro de auditoría. **No es una fuente de restore:** no existe
"volver a la oferta anterior" (ver abajo).

## Sacar los escalones

"Saca los escalones del anillo NEXO" es un write como cualquier otro: lleva preview, gate y backup.

1. **Leé la oferta actual** del producto: qué escalones tiene y qué descuentos la sostienen.
2. **Preview + gate:**

   ```
   💍 Anillo NEXO Plateado — hoy tiene esta oferta:

     2 unidades   $160.200   (ahorran 10%)
     3 unidades   $218.940   (ahorran 18%)

   Si la saco, la ficha vuelve a mostrar solo el precio de una unidad: $89.000.
   Las compras que ya se hicieron no cambian.

   ¿La saco? Responde sí o no.
   ```

   Decile también, en la misma línea, que **no hay vuelta atrás automática**: si después la quiere de
   nuevo, se la vuelve a armar.
   > *"Si más adelante la quieres otra vez, me dices y te la armo igual en un minuto."*

3. **BACKUP** (mismo contrato de arriba, con `previous` = la oferta que estás sacando).
   **No es opcional:** sin él, el propio paso 4 se rechaza.
4. **Publicá la oferta vacía** (escalones vacíos): la ficha deja de anunciar. Va primero, siempre.
5. **Desactivá cada descuento** de la oferta, uno por llamada. **NUNCA borres.**
6. **Worklog** con cada identificador desactivado, y confirmá:
   > *"Listo, saqué la oferta. La ficha ya muestra el precio normal."*

**No existe un flujo "revertir" para ofertas.** Si el cliente quiere volver a una anterior, se
vuelve a armar. Reactivar descuentos ya apagados reintroduce ambigüedad sobre qué estuvo vigente
cuándo, y las órdenes ya cobradas no se recalculan.

## Descuentos huérfanos

Un huérfano es un descuento con el prefijo de la herramienta sobre ese producto que **no está
referenciado por la oferta actual**. Los detectás con la consulta del paso 2.

La condición es esa, y **no** "si la oferta está vacía": en el estado (c) del orden de escritura la
oferta *no* está vacía —anuncia la nueva— y los huérfanos son justamente los viejos que quedaron
prendidos. Una condición basada en "oferta vacía" no dispararía en el único caso donde hace falta.

Cuando encontrás huérfanos: mencionalos en el preview (texto de arriba) y desactivalos junto con la
operación en curso. Nunca los borres. Si no hay ninguna operación en curso, ofrecé apagarlos y esperá
el "sí".

## Worklog

Append a `clients/{slug}/worklog.md` después de escribir:

```
## 2026-07-19 [oferta] Anillo NEXO Plateado — escalones 2/-10%, 3/-18%
Backup: clients/blunua/backups/deals/999-20260719-224000.json
Creados:      gid://shopify/DiscountAutomaticNode/111 (2+), gid://shopify/DiscountAutomaticNode/222 (3+)
Desactivados: gid://shopify/DiscountAutomaticNode/090 (oferta anterior)
```

Es **auditoría, no permiso**: sirve para reconstruir qué pasó y para detectar huérfanos.
Si el worklog fallara, la desactivación tiene que seguir estando disponible igual — nunca frenes una
limpieza porque no pudiste registrarla.

## Si el cliente pide algo fuera de alcance

Bajar el precio de lista, poner un descuento a toda la tienda o a una colección entera, envío gratis,
cupones sueltos, pausar o publicar productos: **no se hace y no se intenta.** Esos caminos están
bloqueados por diseño, así que intentarlo solo genera un error feo.

El **regalo por compra** ("comprá 2 y el 3º gratis", "llevate algo de regalo") sí se puede, pero es
**otro skill** (`armar-regalo`), no este. Si el cliente lo pide, no lo armes acá: es una oferta
distinta, con otro techo y otra forma de escritura.

Guion (neutro, adaptar según `store-standards §2`):
> *"Eso todavía no lo puedo hacer yo. Lo anoto y lo vemos con el equipo."*

Registralo en el worklog y seguí con lo que sí podés hacer. No expliques por qué no podés en
términos técnicos.
