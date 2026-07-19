---
name: armar-combo
description: Recomienda combos o bundles de productos en base a la co-compra real y al catálogo de la tienda. Devuelve las propuestas como texto; no crea el combo en Shopify. Usar cuando el cliente pide ideas de combos, packs, sets o qué productos vender juntos.
---

# Armar combo (recomendación, solo lectura)

Skill de **lectura + razonamiento**. Propone combos como texto. NO crea nada en la tienda (eso sería un write, va a una versión futura).

## Reglas
- Solo propone. No escribe absolutamente nada en la tienda.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de campo, de skill ni comandos.
- Registro del cliente según `store-standards.md §2` (blunua: español neutro, sin voseo).
- El copy que proponés cumple el vocabulario de `store-standards §2` (ver "Chequeo del copy").
- Humanizer antes de entregar.

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

5. **PRESENTAR.** Cada combo en texto simple: qué lleva, por qué tiene sentido (y si sale de la co-compra real, decilo: *"esto ya lo compran junto"*), y una frase de cómo comunicarlo.

## Chequeo del copy (obligatorio antes de mostrar)

La frase de comunicación es copy de marketing y cumple `store-standards §2` igual que una descripción de producto. Antes de mostrarla, verificá que NO tenga:

- **Materiales que no son:** oro, plata, oro laminado, chapado, enchapado, bañado en oro. El material es **acero quirúrgico**. Se puede describir el *acabado* ("tono dorado", "tono plateado"), nunca como material.
- **Lujo vacío y superlativos:** lujo, de lujo, exclusivo, glamour, deslumbrante, el mejor, único en el mundo, espectacular, increíble, de ensueño.
- **Claims médicos:** cura, curativo, propiedades medicinales, mágico. Sí permitido: "no irrita", "apto para pieles sensibles".
- **Registro equivocado:** sin voseo ni argentinismos (blunua es Colombia, español neutro).
- **Em-dashes** ni otros AI tells (los saca el humanizer).

Si algo falla, corregilo antes del preview. No muestres copy que no pase el chequeo.

## Si el cliente pide algo fuera de alcance

Este skill solo propone. Todo pedido de ejecutar el combo (crear el descuento, armar la colección, cambiar precios, ponerlo en la tienda) está fuera de alcance.

**Qué hacés:**
1. **No lo ejecutás.** Ni siquiera parcialmente, ni "para probar", ni buscando un camino alternativo. Igual seguís entregando la propuesta en texto, que es lo que sí podés hacer.
2. Respondés con el guion, sin nombrar campos, herramientas ni skills, y sin explicar limitaciones técnicas.
3. Lo anotás en `clients/{slug}/worklog.md` como pedido fuera de alcance, con fecha y qué pidió.

**Guion (plantilla en registro blunua: español neutro, sin voseo; ajustar según `store-standards §2` del cliente activo):**

> "Eso todavía no lo puedo cambiar yo. Lo anoto y lo vemos con el equipo."

Aplicado al caso típico del descuento:

> "El combo te lo dejo armado y con la frase para comunicarlo. Ponerle el descuento todavía no lo puedo hacer yo: lo anoto y lo vemos con el equipo."

**Ejemplos que disparan el guion:** "arma el combo con 15% off", "créame el código de descuento", "haz una colección con estos", "agrégalos a la colección de regalos", "baja el precio del combo", "pon 20 unidades".

**Nunca digas:** que no tenés permisos, que el connector no lo soporta, que falta un scope, ni nombres de campos o herramientas. Eso es jerga.

## Qué NO hace (prohibiciones duras)
- No crea el combo o bundle en Shopify.
- **No crea descuentos** de ningún tipo (ni códigos, ni automáticos, ni de campaña).
- **No crea ni modifica colecciones.**
- **No agrega productos a colecciones** existentes.
- No cambia precios, stock, status ni ningún otro campo.
- No propone nada sin haber verificado antes contra qué tienda está conectado.

> Estos tools existen en el connector y están al alcance de la mano. La prohibición es explícita justamente por eso: que el tool esté disponible no lo habilita.

## Nota para quien edite este skill

Acá había un placeholder que mandaba a usar `customer-intelligence` del Brain para la co-compra. **Se verificó que ese tool no devuelve co-compra:** devuelve valor de vida del cliente, tasa de recompra y fuentes de adquisición. La co-compra real se saca de los productos de las órdenes (paso 1). No vuelvas a poner el placeholder.
