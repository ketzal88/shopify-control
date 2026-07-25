---
name: armar-combo
description: Recomienda combos o bundles de productos en base a la co-compra real y al catálogo de la tienda, y —con el OK del cliente— crea el combo como un descuento "comprá A y llevate B con X% off" (dentro del techo del cliente). Muestra un preview, pide confirmación, guarda backup y permite sacarlo. Usar cuando el cliente pide ideas de combos, packs, sets, qué productos vender juntos, o armar/activar un combo.
---

# Armar combo (recomienda y, con OK del cliente, crea el combo)

Skill de dos partes. **Propone** combos como texto leyendo la co-compra real (lo que ya hacía), y **crea** el combo elegido como un descuento **"comprá A, llevate B con X% off"** (un BXGY nativo, se ve en carrito/checkout), dentro del techo del cliente y con todo el protocolo de write. El valor nuevo es que la oferta la **sugieren los datos de venta** (co-compra real), no el cliente a mano.

> **El combo es un descuento con % (nunca gratis).** "Gratis" es otra cosa (el regalo, otro skill). El combo lleva un porcentaje de descuento acotado por el techo del cliente. Si el cliente pide "regalá B", eso no es un combo.

## Reglas
- **La parte de proponer es solo lectura; la de crear es un write, y lleva el protocolo completo** (preview → gate explícito → backup → escribir → confirmar). El único write permitido es el combo: `discountAutomaticBxgyCreate` (con % < 100) + `metafieldsSet` de `worker.deal` `type:"combo"`. El undo es `discountAutomaticDeactivate`.
- **Techo y alcance los enforcea el guard.** El % no puede pasar `maxComboPct`, la cantidad que se lleva no puede pasar `maxComboGetQty`, nunca es gratis (100%), y el combo apunta a productos explícitos (comprá A → llevate B), una vez por pedido, con fecha de fin. No le pelees al guard: mandá exactamente eso.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca "BXGY", "descuento automático", nombres de campo, de skill ni comandos. Al cliente se le habla de "combo" y "llevándolos juntos ahorrás".
- Registro del cliente según `store-standards.md §2` (blunua: español neutro, sin voseo).
- El copy que proponés cumple el vocabulario de `store-standards §2` (ver "Chequeo del copy").
- Humanizer antes de todo texto que vea el cliente (preview y confirmación).

> **Sobre los textos entre comillas de este skill:** son **plantillas** escritas en el registro de blunua (español neutro, sin voseo), no literales universales. Este skill sirve a todos los clientes, así que antes de usarlas ajustá el registro al que indique `store-standards §2` del cliente activo.

## Skills que reusás (INTERNO: nunca los nombres frente al cliente)
- `ecommerce-marketing-manager`: lógica de cross-sell y bundling.
- `marketing-psychology`: por qué un combo convierte.
- `handsOn-Worker/skills/humanizer/SKILL.md`: obligatorio antes de todo output cliente. **Hoy NO es invocable como skill desde este repo:** abrí ese archivo con Read y aplicá sus reglas a mano sobre el texto final.

## Flujo

0. **CONFIRMAR CLIENTE Y TIENDA (obligatorio, antes de leer nada).**
   La sesión se abre en la **raíz del repo**, así que el contexto del cliente NO se carga solo. No asumas cuál es.
   1. Determiná el cliente activo (el slug de `clients/`). Si hay más de uno posible o no está claro, preguntá antes de seguir.
   2. Leé `clients/{slug}/CLAUDE.md` y `clients/{slug}/store-standards.md`. Sin eso no tenés registro, vocabulario prohibido ni taxonomía de colecciones.
   3. Verificá contra qué tienda está conectado el connector con `Shopify:get-shop-info` y compará con la tienda esperada del cliente (`clients/{slug}/connection.md`).
   4. **Si no coinciden: ABORTÁ.** No leas el catálogo ni las órdenes, no propongas nada. Avisá que la tienda conectada no es la del cliente. Cambiar de tienda (`Shopify:switch-shop`) es decisión del operador, no del cliente y no tuya por default.
      - Al cliente, en lenguaje natural: *"Ahora mismo no estoy viendo la tienda de {marca}, así que prefiero no proponerte combos con productos que podrían ser de otra tienda. Lo reviso con el equipo y te confirmo."*
   5. Si `connection.md` todavía no tiene la tienda cargada, tampoco sigas a ciegas: dejá constancia de qué tienda devolvió el connector y pedí confirmación al operador.

1. **CO-COMPRA REAL (empezá por acá, no por el catálogo).** Mirá qué se está comprando junto de verdad, leyendo los productos de cada orden con `Shopify:graphql_query`:

   ```graphql
   query { orders(first: 40, sortKey: CREATED_AT, reverse: true) { edges { node { name lineItems(first: 10) { edges { node { title quantity } } } } } } }
   ```

   - Quedate con las órdenes de 2 o más productos y contá qué pares se repiten.
   - Ajustá `first` o paginá si querés una ventana más larga. Con 40 órdenes tenés la tendencia reciente, no el histórico completo: no presentes un par visto una sola vez como si fuera un patrón.
   - Si la tienda tiene poco volumen en esa ventana, decilo y pasá a la lógica de catálogo (paso 2), aclarando que la propuesta es por criterio y no por datos de venta.

   **Patrones ya observados en blunua (punto de partida, revalidalos con la consulta):**
   - Compran la **misma línea de diseño cruzando categorías**: Collar Sara + Candongas Sara, Choker Soul + Pulsera Soul. El nombre de la línea es el hilo, no la categoría.
   - Compran **dos pares de candongas juntos** (earstacking). El combo de "más de lo mismo" funciona acá.

2. **CATÁLOGO.** Leé productos, colecciones y tags vía el connector para completar y validar (que exista stock, que sea la misma línea, que los segmentos `Her`/`Him`/`Kids` cierren). Usá la taxonomía de `store-standards §6`, y ojo: Earstacking, Dorados, Cristales y similares son **colecciones curadas o de campaña, no categorías**.

3. **ARMAR COMBOS.** Priorizá en este orden:
   1. Pares que aparecieron de verdad en las órdenes.
   2. Misma línea de diseño cruzando categorías (el patrón fuerte de blunua).
   3. Repetición de la misma categoría cuando el uso lo justifica (earstacking).
   4. Lógica de colección (ej: NEXO, "funciona sola o en conjunto") y sets para regalo.

4. **COPY + CHEQUEO.** Escribí la frase de cómo comunicarlo, pasala por el humanizer y corré el chequeo de vocabulario de abajo antes de mostrar nada.

5. **PRESENTAR.** Cada combo en texto simple: qué lleva, por qué tiene sentido (y si sale de la co-compra real, decilo: *"esto ya lo compran junto"*), y una frase de cómo comunicarlo. Cerrá preguntando si quiere que arme (active) alguno.

## Crear el combo (write, solo con OK del cliente)

Esta parte corre **solo** si el cliente elige un combo concreto ("sí, armá el de collar + candongas al 15%"). Si solo pidió ideas, terminás en el paso 5.

### 6. Copy + humanizer + chequeo
La frase del combo pasa el humanizer y el "Chequeo del copy" de abajo, igual que cualquier texto de cliente.

### 7. Preview
Mostrá en el chat, sin jerga: qué combo, qué se lleva con qué descuento, sobre qué productos, y hasta cuándo. Ejemplo de registro (plantilla blunua): *"Combo: llevando el Collar Sara + las Candongas Sara, las candongas quedan con 15% off. Activo hasta el {fecha}."*

### 8. Gate
Preguntá explícito, sí/no: *"¿Lo activo?"*. Solo seguís con un sí.

### 9. Backup (antes de escribir)
Guardá el backup de oferta en `clients/{slug}/backups/deals/{idTail}-{YYYYMMDD-HHMMSS}.json` con `{"kind":"deal","productId":"gid://…","previous":…,"ts":"<ISO>"}` (el `productId` es el producto que se **compra**, A). Sin backup fresco el guard bloquea la escritura.

### 10. Escribir (dos writes, en pedidos separados)
Validá cada mutación con `Shopify:validate_graphql_codeblocks` antes.
1. `Shopify:graphql_mutation` con `discountAutomaticBxgyCreate`: `customerBuys` = producto A (comprado), `customerGets` = producto B con `discountOnQuantity.effect.percentage` **entre 0.01 y 0.99** (nunca 1.0 = gratis), `usesPerOrderLimit: 1`, `endsAt` puesto. El `productId` del producto A va en `variables` (el guard lo exige y tiene que coincidir con el producto comprado).
2. `Shopify:graphql_mutation` con `metafieldsSet` de `worker.deal` `type:"combo"` sobre el producto A, con la forma del combo (buy/get, %, cantidades). Las cantidades y el % tienen que coincidir con el descuento (el guard aplica el mismo techo en los dos, para que no diverjan).

Si algún `userErrors` vuelve con algo, no inventes: contáselo al cliente en natural y no des el combo por activado.

### 11. Worklog + confirmar
Anotá en `clients/{slug}/worklog.md`: `## YYYY-MM-DD [write] armar-combo — combo A+B al X% hasta {fecha}`. Al cliente, en natural: *"Listo, el combo está activo hasta el {fecha}."*

### 12. Undo ("sacá ese combo")
Su propio gate, y después `Shopify:graphql_mutation` con `discountAutomaticDeactivate` del descuento del combo. Anotalo en el worklog. Desactivar está siempre permitido (es la compensación).

### Si armar el combo todavía no está disponible
Si el cliente no tiene el techo de combo configurado (`allowCombo:false` o sin `maxComboPct`/`maxComboGetQty`), armar el combo todavía no está disponible: el guard igual lo bloquearía. Decíselo en natural (*"El combo te lo dejo pensado y con la frase; activarlo todavía no lo puedo hacer yo, lo anoto y lo vemos con el equipo."*) y anotalo en el worklog. No intentes el write.

## Chequeo del copy (obligatorio antes de mostrar)

La frase de comunicación es copy de marketing y cumple `store-standards §2` igual que una descripción de producto. Antes de mostrarla, verificá que NO tenga:

- **Materiales que no son:** oro, plata, oro laminado, chapado, enchapado, bañado en oro. El material es **acero quirúrgico**. Se puede describir el *acabado* ("tono dorado", "tono plateado"), nunca como material.
- **Lujo vacío y superlativos:** lujo, de lujo, exclusivo, glamour, deslumbrante, el mejor, único en el mundo, espectacular, increíble, de ensueño.
- **Claims médicos:** cura, curativo, propiedades medicinales, mágico. Sí permitido: "no irrita", "apto para pieles sensibles".
- **Registro equivocado:** sin voseo ni argentinismos (blunua es Colombia, español neutro).
- **Em-dashes** ni otros AI tells (los saca el humanizer).

Si algo falla, corregilo antes del preview. No muestres copy que no pase el chequeo.

## Si el cliente pide algo fuera de alcance

Crear el **combo** (el descuento "comprá A, llevate B con % off") **sí** está en alcance, con el protocolo de arriba. Lo que sigue fuera de alcance: crear **otros** descuentos (códigos, campañas), armar o modificar **colecciones**, cambiar **precios**, **stock** o **status**.

**Qué hacés con un pedido fuera de alcance:**
1. **No lo ejecutás.** Ni siquiera parcialmente, ni "para probar", ni buscando un camino alternativo. Igual seguís con lo que sí podés (proponer, o armar el combo si es eso lo que pidió).
2. Respondés con el guion, sin nombrar campos, herramientas ni skills, y sin explicar limitaciones técnicas.
3. Lo anotás en `clients/{slug}/worklog.md` como pedido fuera de alcance, con fecha y qué pidió.

**Guion (plantilla en registro blunua: español neutro, sin voseo; ajustar según `store-standards §2` del cliente activo):**

> "Eso todavía no lo puedo cambiar yo. Lo anoto y lo vemos con el equipo."

**Ejemplos que disparan el guion:** "créame el código de descuento", "haz una colección con estos", "agrégalos a la colección de regalos", "baja el precio del combo", "pon 20 unidades", "regalá B" (un combo lleva %, no es gratis).

**Nunca digas:** que no tenés permisos, que el connector no lo soporta, que falta un scope, ni nombres de campos o herramientas. Eso es jerga.

## Qué NO hace (prohibiciones duras)
- **Solo el combo BXGY:** no crea **otros** descuentos (ni códigos, ni básicos de campaña) fuera del combo "comprá A, llevate B con % off".
- Un combo **nunca es gratis** (100%): eso es un regalo, otro camino.
- **No crea ni modifica colecciones.**
- **No agrega productos a colecciones** existentes.
- No cambia precios, stock, status ni ningún otro campo.
- No propone ni escribe nada sin haber verificado antes contra qué tienda está conectado, y no escribe sin backup + confirmación explícita del cliente.

> Estos tools existen en el connector y están al alcance de la mano. La prohibición es explícita justamente por eso: que el tool esté disponible no lo habilita.

## Nota para quien edite este skill

Acá había un placeholder que mandaba a usar `customer-intelligence` del Brain para la co-compra. **Se verificó que ese tool no devuelve co-compra:** devuelve valor de vida del cliente, tasa de recompra y fuentes de adquisición. La co-compra real se saca de los productos de las órdenes (paso 1). No vuelvas a poner el placeholder.
