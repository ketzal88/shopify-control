---
name: armar-regalo
description: Arma ofertas de "regalo gratis" en un producto de Shopify — mismo producto ("comprá 2 y el 3º es gratis") o cruzado ("comprá el anillo y llevate los aretes de regalo"). Muestra un preview en el chat, pide confirmación, guarda backup y permite sacarla. Usar cuando el cliente pide un regalo por compra, 2x1 / 3x2, "el siguiente gratis", o llevate algo de regalo.
---

# Armar regalo gratis (BXGY)

Skill de **escritura** sobre la tienda viva, y el segundo que toca **plata** (el primero es
`armar-escalones`). Todo lo que sigue existe por eso: el techo, el backup, el orden de escritura y el
gate no son ceremonia, son lo que separa "comprá 2 y el 3º gratis" de "regalá el catálogo entero".

`armar-combo` es el upstream natural: recomienda qué producto merece un regalo, y —para el cruzado—
qué producto conviene regalar con qué. Este skill lo ejecuta.

## Las dos formas

1. **Mismo producto** — "comprá 2 y el 3º es gratis" (o parcial: "el 3º a mitad de precio"). El que
   se compra y el que se regala son el **mismo** producto.
2. **Cruzado** — "comprá el anillo y llevate los aretes de regalo". El regalo es **otro** producto,
   y ese otro producto **tiene que estar en la lista de regalables del cliente**
   (`giftableProducts` del techo). Si no está, no se puede regalar: se lo explicás sin jerga y se lo
   proponés al operador para que lo agregue.

## Reglas duras (no negociables)

- **Alcance:** solo tres cosas. (1) crear **un** descuento de regalo sobre un producto,
  (2) escribir la oferta que lee el widget de la ficha, (3) **desactivar** descuentos.
  NUNCA precio, stock, status, tags, título, handle, colecciones ni regalos sobre todo el catálogo.
- **El regalo se limita a una vez por pedido.** No se multiplica solo en el carrito (comprá 4 no
  regala 2). Esto es parte del descuento que se crea, no opcional.
- **Nunca borrar un descuento.** La única forma de sacarlo es desactivarlo. Borrar está bloqueado por
  diseño y destruye el historial.
- **Nunca extender ni editar un descuento ya creado.** Si hay que cambiar algo, se crea uno nuevo y se
  desactiva el viejo. No existe camino de update.
- **El techo manda:** `clients/{slug}/deal-policy.json`. Cuánto regalo como máximo (`maxGiftPct`),
  cuántas unidades (`maxGetQty`), cuánto hay que comprar por cada unidad regalada (`minBuyGetRatio`),
  si el regalo cruzado está habilitado (`allowCrossProductGift`) y qué productos se pueden regalar
  (`giftableProducts`). Si lo que pide el cliente no entra, se le explica el límite **sin jerga** y se
  le propone la versión que sí entra. No se intenta igual.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de skill
  ni comandos. Tampoco expliques limitaciones técnicas ("no tengo permisos", "el guard lo bloquea"):
  eso también es jerga.
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN voseo).
  Los textos entre comillas de este archivo son **plantillas**, no literales universales. Para blunua,
  en Colombia se dice **aretes**, nunca "aros".
- **Humanizer obligatorio** antes de todo output cliente: leé `handsOn-Worker/skills/humanizer/SKILL.md`
  y aplicá sus reglas a mano (hoy no es invocable como skill desde este repo).
- **Nada se escribe sin:** (1) preview mostrado, (2) "sí" explícito del cliente, (3) backup guardado.
- **Un asunto por pedido.** Crear el descuento, escribir la oferta del widget y desactivar son
  **operaciones separadas**. Nunca las metas en la misma llamada: mezclarlas se rechaza entero.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)

Idéntico a `armar-escalones`. La sesión se abre en la RAÍZ del repo, así que el contexto del cliente
NO se carga solo. No asumas cuál es.

1. Determiná el cliente activo (el slug de `clients/`). Si hay más de uno posible, preguntá.
2. Leé `clients/{slug}/CLAUDE.md` + `clients/{slug}/store-standards.md` +
   **`clients/{slug}/deal-policy.json`**. Los tres. Sin el tercero no tenés techo y no podés proponer.
3. Verificá con `Shopify:get-shop-info` **contra qué tienda** está conectado el connector.
4. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ.** No leas el catálogo, no
   propongas, no escribas. Avisá al operador. Crear un descuento en la tienda equivocada es plata real
   de otro.
   - Al cliente, en lenguaje natural: *"Ahora mismo no estoy viendo la tienda de {marca}, así que
     prefiero no tocar ninguna oferta. Lo reviso con el equipo y te confirmo."*
5. Si `connection.md` todavía no tiene la tienda cargada, tampoco sigas a ciegas: dejá constancia y
   pedí confirmación al operador.

## Estrategia

- `strategies/automatic.md` — **la única del v1**. Un descuento automático de regalo
  (`discountAutomaticBxgyCreate`). No hay estrategia de códigos para el regalo todavía.

*(INTERNO: nunca nombres la estrategia ni ningún archivo frente al cliente.)*

## Config del builder (`🎁 regalo-config`)

El cliente puede armar el regalo en el **builder visual** y pegarte el resultado. Llega como un bloque
con el marcador `🎁 regalo-config` seguido de un JSON:

```
🎁 regalo-config
{ "v": 1, "scope": "same",
  "buy":  { "product": { "id": "gid://shopify/Product/999", "title": "Anillo NEXO" }, "qty": 2 },
  "get":  { "product": { "id": "gid://shopify/Product/999", "title": "Anillo NEXO", "handle": "anillo-nexo" }, "qty": 1, "pct": 100 },
  "style": { "ink": "#4B4B4B", "label": "Comprá más y llevate un regalo", "badge": "GRATIS" } }
```

Reglas al recibirlo:

- **Es una request, no una orden.** NO saltea nada: corrés el flujo normal completo (paso 0, contexto,
  techo, preview, gate "¿la activo?", backup, write). El gate de plata **no se elimina**.
- **El builder NO es de confianza.** Revalidás `buy`/`get`/`scope` contra `deal-policy.json` (el techo)
  y `style` contra el set cerrado de claves, como si el texto viniera de cualquier lado. Si algo no
  entra, se lo explicás sin jerga y ofrecés el máximo que sí entra.
- **Mapeo:** `buy`/`get`/`scope` → la oferta (`automatic.md`, que le suma `strategy`, `startsAt`/
  `endsAt` y el `ref` del descuento); `style` → `worker.style`. El `v` es la versión del formato del
  builder, no del metafield. La config **no trae** fechas ni refs: los ponés vos al escribir.
- **Orden:** primero la oferta, después el estilo. **Dos writes separados**, cada uno con su backup
  (`backups/deals/` con `kind:"deal"`; `backups/style/` con `kind:"style"`). Nunca en el mismo
  documento.

*(INTERNO: nunca le nombres al cliente "config", "metafield" ni "builder". Para él es "el regalo que
armaste".)*

## Flujo (siempre en este orden)

0. **CONFIRMAR CLIENTE Y TIENDA.** Lo de arriba. Si no coinciden, abortás acá.

1. **IDENTIFICAR EL/LOS PRODUCTO(S).** El producto que se **compra** (P). Si es cruzado, también el
   que se **regala** (Q). Buscalos con `Shopify:search_products`. El filtro por título es difuso: si
   hay más de un resultado, mostrá opciones y preguntá. **NUNCA adivines.** Para el cruzado, verificá
   que Q esté en `giftableProducts` **antes** de proponer nada; si no está, decilo sin jerga (abajo).

2. **LEER EL ESTADO ACTUAL.** Con `Shopify:graphql_query`: título, `hasOnlyDefaultVariant`, variantes
   (id/title/price/inventoryQuantity) y `metafield(namespace:"worker", key:"deal")` de P. Para el
   cruzado, también el **precio y una variante disponible de Q** (lo necesitás para el preview y para
   la línea de carrito del regalo). Sacás: precio unitario (el cliente aprueba pesos, no porcentajes),
   stock (para la advertencia del paso 5) y la oferta actual si había. Leé también los descuentos con
   prefijo `shopify-control` sobre P, para detectar huérfanos (misma query que `armar-escalones`).

3. **CARGAR EL TECHO.** `deal-policy.json`: `maxGiftPct`, `maxGetQty`, `minBuyGetRatio`,
   `allowCrossProductGift`, `giftableProducts`, `maxDurationDays`, `requireEndsAt`.

4. **PROPONER EL REGALO, DENTRO DEL TECHO.**
   - Mismo producto por defecto: "comprá 2, el 3º gratis" (`buy.qty=2`, `get.qty=1`, `pct=100`).
     Respetá `minBuyGetRatio`: hay que comprar al menos ese número por cada unidad regalada (no
     "comprá 1 llevá 1", que sería medio precio encubierto).
   - `get.qty` nunca supera `maxGetQty`. `pct` nunca supera `maxGiftPct` (100 = gratis).
   - **La fecha de fin es obligatoria** y la oferta vence dentro de `maxDurationDays`. Un regalo sin
     fin no es un regalo, es un precio nuevo.
   - Cruzado: Q tiene que estar en `giftableProducts`. Si el cliente pide regalar algo que no está:
     > *"Ese producto todavía no está entre los que puedo regalar. Lo anoto para sumarlo con el
     > equipo y te aviso; mientras, ¿querés que te arme el regalo con otro?"*
   - Si pide un regalo por encima del techo (más unidades, o gratis cuando el cliente solo permite
     parcial), no lo intentes: explicá el límite en lenguaje natural y ofrecé lo que sí entra.

   ⚠️ **El porcentaje del regalo es entero.** 100 es gratis, 50 es mitad de precio. Escribí `100`,
   nunca `1.0`, en la oferta que lee el widget. La conversión a la fracción que pide la tienda
   (`1.0`) ocurre **una sola vez**, al armar la operación de creación, y está en el archivo de
   estrategia. Confundirlas es cómo un 7% se vuelve 70%.

5. **PREVIEW.** En el chat, texto plano, sin jerga. Formato exacto abajo. Siempre con el **precio
   total que paga** ("pagás 2"), no solo "gratis", y siempre diciendo **cuándo vence**. Pasalo por el
   humanizer antes de mostrarlo.

6. **GATE.** Preguntá: *"¿La activo? Responde sí o no."* **No escribas nada hasta un "sí" explícito.**

7. **BACKUP (antes de escribir, sin excepción).** Mismo contrato que `armar-escalones`
   (`backups/deals/`, `kind:"deal"`, doble frescura). El backup se guarda por el producto **comprado**
   (P) — es sobre P que se escribe la oferta. Vale 15 minutos.

8. **ESCRIBIR.** Orden: **crear → publicar → desactivar.** Ver abajo.

9. **WORKLOG Y CONFIRMAR.** Registrá el descuento creado y los desactivados, con su identificador.
   Después confirmá al cliente:
   > *"Listo, el regalo ya está activo en la ficha del anillo NEXO. Si querés sacarlo, dime
   > 'saca el regalo del anillo NEXO' y lo quito."*

## Orden de escritura (falla del lado seguro)

Igual que `armar-escalones`, tres operaciones **separadas** y en este orden:

```
a. Crear el descuento de regalo nuevo (una llamada).
b. Escribir la oferta que lee el widget, con el identificador nuevo.
c. Desactivar el/los descuento(s) VIEJO(S), si los había (uno por llamada).
```

Nunca al revés: desactivar primero deja una ventana donde **la ficha anuncia un regalo que el carrito
ya no aplica**. La tabla de recuperación por punto de falla y el porqué del estado (c) no-inocuo son
idénticos a `armar-escalones` (§ "Orden de escritura"): reintentás (c), y si falla lo registrás en el
worklog y se lo decís al cliente.

## Preview — formato exacto (ejemplo blunua, registro neutro)

**Mismo producto:**

```
💍 Anillo NEXO Plateado — te propongo este regalo para que se lleven más de uno:

  Comprá 2 y el 3º va de regalo.
  Pagás 2 ($178.000) y te llevás 3.

Arranca hoy y vence el 20 de octubre.

Quien entre a la ficha lo va a ver arriba del botón de comprar, con un botón que
dice exactamente cuánto lleva y cuánto paga.

¿Lo activo? Responde sí o no.
(si después quieres sacarlo, dime "saca el regalo del anillo NEXO")
```

**Cruzado:**

```
💍 Anillo NEXO Plateado — te propongo este regalo:

  Quien compre el anillo NEXO se lleva de regalo unos aretes LUNA.
  Paga $89.000 por el anillo y los aretes van sin costo.

Arranca hoy y vence el 20 de octubre.

¿Lo activo? Responde sí o no.
(si después quieres sacarlo, dime "saca el regalo del anillo NEXO")
```

Reglas del preview, todas obligatorias:

- **Nunca** decir "metafield", "descuento automático", "identificador", "gid", "mutación", "variante",
  "namespace", "BXGY", ni el nombre de este skill ni de ningún archivo. Decís "regalo", "la ficha".
  ("Regalo" sí: es la palabra con la que el cliente pide y saca la oferta.)
- **Siempre el precio total que paga**, calculado (precio unitario × unidades que paga), no "gratis" a
  secas. El cliente aprueba pesos.
- **Siempre cuándo vence**, en fecha legible ("el 20 de octubre"), nunca en formato de sistema.
- Una línea que describa qué va a ver quien compre. No expliques cómo funciona por dentro.
- Cerrar **siempre** con el gate y con la forma de sacarlo.
- Si el producto YA tiene una oferta activa (escalones o regalo), el preview es **ANTES vs DESPUÉS**,
  con los dos bloques completos, y aclarás: *"La oferta que está hoy se apaga sola cuando activo esta."*
  (Recordá: un producto tiene **una** oferta por vez — un regalo reemplaza unos escalones y viceversa.)
- **Advertencia de stock** (no bloquea): si no alcanza para comprar las unidades requeridas + el
  regalo, agregala antes del gate, en lenguaje natural.
- **Huérfanos:** si hay descuentos sueltos de una oferta anterior, van en el preview antes del gate.

## Contrato del backup

Idéntico a `armar-escalones`: `clients/{slug}/backups/deals/{productIdTail}-{YYYYMMDD-HHMMSS}.json`
con `{ "kind": "deal", "productId": "<gid de P>", "previous": <la oferta anterior o null>,
"ts": "<local, sin zona, = el del nombre>" }`. `kind:"deal"` y la ruta `backups/deals/`, las dos
juntas. Vale 15 minutos. El `productId` es el del producto **comprado** (P). Es insumo de seguridad y
rastro de auditoría, **no** fuente de restore.

## Sacar el regalo

"Saca el regalo del anillo NEXO" es un write como cualquier otro: lleva preview, gate y backup.

1. **Leé la oferta actual** de P: qué regalo tiene y qué descuento lo sostiene.
2. **Preview + gate**, aclarando que **no hay vuelta atrás automática** (si lo quiere de nuevo, se
   vuelve a armar) y que las compras ya hechas no cambian.
3. **BACKUP** (mismo contrato, `previous` = la oferta que sacás). No es opcional.
4. **Publicá la oferta vacía** (escribí la oferta sin regalo — el mismo "vaciar" que usa
   `armar-escalones`, `tiers: []`): la ficha deja de anunciar. Va primero, siempre.
5. **Desactivá el descuento** del regalo, una llamada. **NUNCA borres.**
6. **Worklog** con el identificador desactivado, y confirmá:
   > *"Listo, saqué el regalo. La ficha ya muestra el producto normal."*

**No existe un flujo "revertir".** Si el cliente quiere volver a un regalo anterior, se vuelve a armar.

## Descuentos huérfanos

Mismo criterio que `armar-escalones`: un huérfano es un descuento con el prefijo `shopify-control`
sobre P que **no está referenciado por la oferta actual** (no "si la oferta está vacía"). Los
mencionás en el preview y los desactivás junto con la operación en curso. Nunca los borres.

## Worklog

Append a `clients/{slug}/worklog.md` después de escribir:

```
## 2026-07-22 [regalo] Anillo NEXO Plateado — comprá 2, el 3º gratis
Backup: clients/blunua/backups/deals/999-20260722-224000.json
Creados:      gid://shopify/DiscountAutomaticNode/333 (regalo 2+1)
Desactivados: gid://shopify/DiscountAutomaticNode/090 (oferta anterior)
```

Es **auditoría, no permiso**: si el worklog fallara, la desactivación tiene que seguir disponible
igual — nunca frenes una limpieza porque no pudiste registrarla.

## Si el cliente pide algo fuera de alcance

Bajar el precio de lista, un descuento a toda la tienda o a una colección entera, envío gratis,
cupones sueltos, pausar o publicar productos, o regalar un producto que no está entre los regalables:
**no se hace y no se intenta.** Esos caminos están bloqueados por diseño; intentarlo solo genera un
error feo.

Guion (neutro, adaptar según `store-standards §2`):
> *"Eso todavía no lo puedo hacer yo. Lo anoto y lo vemos con el equipo."*

Registralo en el worklog y seguí con lo que sí podés hacer.
