---
name: subir-productos
description: Prepara y revisa productos nuevos a partir de un archivo que entrega el cliente (más una carpeta de fotos), cumpliendo los estándares de la tienda. Muestra un preview producto por producto en el chat. Esta fase NO crea nada en Shopify: termina en el preview. Usar cuando el cliente quiere subir productos nuevos desde un archivo, cargar un catálogo, o dice que tiene una lista de productos para agregar.
---

# Subir productos nuevos (F1 — preparar y revisar)

Skill de **preparación** sobre datos que el cliente entrega. No escribe nada en Shopify: lee el
archivo, lo agrupa en productos, lo valida, chequea contra la tienda viva cuáles ya existen, genera
la descripción y el SEO de cada uno con el mismo craft que `mejorar-descripcion`, y arma un preview
sin jerga. Crear los productos como borradores (y publicarlos) es una fase futura, todavía no
construida.

## Reglas duras (no negociables)
- **Esta fase no escribe nada en Shopify.** Ningún tool de escritura se llama en este flujo. El
  resultado final es siempre un preview en el chat, nunca un producto creado.
- **Sin jerga con el cliente:** todo lo que ve es lenguaje natural. Nunca nombres de archivo
  técnico, de comando, de skill, ni la palabra "CSV", "JSON" o "CLI". Al cliente se le habla de "tu
  archivo" y "tu carpeta de fotos".
- **Registro:** el que diga `store-standards.md §2` del cliente (blunua: español neutro, SIN
  voseo). Los textos literales de este archivo son **plantillas**: si el cliente tiene otro
  registro, adaptalos.
- **El gate de crear todavía no existe.** Aunque el cliente diga "sí, creálos", esta fase no tiene
  forma de escribir en Shopify (no está construido y no hay que simularlo). Ver la sección "Si el
  cliente pide crear ya" más abajo.

## Paso 0 — Confirmar cliente y tienda (obligatorio, antes de todo)
La sesión se abre en la RAÍZ del repo, así que el contexto del cliente NO se carga solo.
1. Identificá el cliente y leé `clients/{slug}/CLAUDE.md` + `clients/{slug}/store-standards.md`.
2. Verificá con `Shopify:get-shop-info` **contra qué tienda** está conectado el connector.
3. Comparala con `clients/{slug}/connection.md`. **Si no coinciden, ABORTÁ** y avisá al operador.
   Nunca sigas sin confirmar la tienda: `switch-shop` existe y el connector puede estar apuntando a
   otra.

## Contexto que cargás (antes de generar copy)
- `clients/{slug}/store-standards.md` (molde canónico §3, registro §2, keywords por categoría §4,
  checklist §9).
- La marca en handsOn (link en el `CLAUDE.md` del cliente): brand-voice, vocabulario.

## Flujo F1 (siempre en este orden)

1. **RECIBIR.** Pedile al cliente, en lenguaje natural, dónde está el archivo con los productos
   nuevos y dónde está la carpeta con las fotos. Traducilo a dos rutas locales. No hace falta que
   el cliente sepa qué formato tiene el archivo: si viene de Shopify, ya sirve tal cual.

2. **PARSEAR.** Corré:

   ```
   python .claude/hooks/product_csv.py "<ruta del archivo>"
   ```

   Leé el resultado (JSON por salida estándar): trae, por cada producto, un estado —`crear` o
   `rechazado`— y, si fue rechazado, el motivo en texto. Esto es trabajo interno: nunca lo mencionés
   al cliente con esos nombres. Si el archivo no se pudo leer o el comando falla, decile al cliente
   en lenguaje natural que no se pudo abrir el archivo y avisá al operador; no sigas adivinando el
   contenido.

3. **DEDUP VIVO.** Por cada producto que quedó en `crear`, buscá si ya existe en la tienda real:
   - `Shopify:search_products` por `handle:<handle del producto>`.
   - `Shopify:search_products` por `sku:<sku>` de cada variante.

   Si cualquiera de las dos búsquedas encuentra un match, ese producto pasa a "ya existe" y no se
   procesa más (no se le genera copy). Guardá a qué producto de la tienda corresponde, para poder
   mencionarlo en el preview si hace falta.

4. **GENERAR COPY.** Por cada producto que sigue en `crear` (ni rechazado ni "ya existe"):
   - Escribí la descripción con el molde canónico de `store-standards §3`: título → hook → 3
     beneficios → material/garantía → bloque GEO (2-4 preguntas frecuentes). Tejé las keywords de
     `§4` en el texto, no en bloque aparte.
   - Generá también meta title (~60 caracteres) y meta description (~155 caracteres).
   - Pasá todo por el humanizer (obligatorio): `handsOn-Worker/skills/humanizer/SKILL.md`. Hoy no es
     invocable como skill desde este repo — leé ese archivo y aplicá sus reglas a mano. Sin
     em-dashes, sin voseo si el registro es neutro, sin lenguaje promocional vacío.
   - Corré el linter de verdad, sobre el **texto plano** (no el HTML). El texto va por entrada
     estándar (por eso el `echo` adelante, si no el comando se queda esperando):

     ```
     echo "<texto plano de la descripción>" | python .claude/hooks/description_lint.py --keywords "<keywords de la categoría>" --dialect neutro
     ```

     Sale 0 si está limpio; 1 y explica cada issue si no. Si algo falla, corregí antes de seguir.
     **No mostrés en el preview ninguna descripción que no pase el linter.**

5. **PREVIEW.** Armá el mensaje de chat (nunca dentro de un cuadro de confirmación: eso aplasta el
   formato) con:
   - Un índice arriba de todo: cuántos productos quedaron listos para crear, cuántos ya existen en
     la tienda, y cuántos tienen algún problema (y por qué, en lenguaje natural, no el motivo
     técnico crudo).
   - El detalle de cada producto que quedó listo para crear: nombre, precio, variantes (por
     ejemplo color o talla), la descripción generada, cómo se va a ver en Google (título y resumen),
     y el estado de las fotos (si el archivo trae fotos o no para ese producto).
   - Los productos con problemas o que ya existen: mencionalos con el motivo, sin entrar en detalle
     técnico ("ese ya está en tu tienda, lo salteo" / "a ese le falta el precio, revisalo y lo
     volvemos a intentar").
   - **Esta fase termina acá.** No hay gate de creación porque no hay nada que crear todavía.

## Si el cliente pide crear o publicar ya
Explicale que por ahora el archivo se revisa y se prepara, y que crearlos en la tienda es un paso
que todavía falta construir. No lo intentes ni simules un resultado.

Guion (neutro, adaptar por `store-standards §2`):
> "Por ahora puedo revisar tu archivo y mostrarte cómo quedarían los productos. Crearlos en tu
> tienda todavía no lo tengo disponible; en cuanto esté lo vemos."

Registralo en `clients/{slug}/worklog.md` como una preparación revisada (sin write), por ejemplo:
`## YYYY-MM-DD [preview] subir-productos — N para crear, X ya existen, Y con problemas`.

## Nota interna
Nunca nombres frente al cliente el comando, el archivo de resultado ni los nombres de campo
internos (`handle`, `sku`, `status`, `motivos`, etc.). Todo eso se traduce a lenguaje natural en el
preview.
