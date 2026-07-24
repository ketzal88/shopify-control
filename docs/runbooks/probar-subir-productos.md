# Prueba de "Subir productos" — guía para la operadora

Esto sirve para chequear, en la **tienda de PRUEBA** (nunca la de un cliente real), que la función de subir productos anda bien de punta a punta. Se hace **hablándole a la herramienta** en VS Code, igual que lo haría un cliente. No hay que tocar código.

## Antes de empezar
1. Abrí VS Code en la **raíz** del repo (no una subcarpeta), con la extensión de Claude Code abierta.
2. Confirmá con el equipo que el connector está apuntando a la **tienda de prueba** (*Testing StandAlone Framework*), no a la de un cliente.
3. Tené a mano un archivo de productos de prueba (CSV) con 2 o 3 productos, y una carpeta con un par de fotos.
4. **Solo para la prueba 6 (publicar):** el equipo tiene que haber cargado el "canal" de la tienda de prueba en la configuración. Si no está, **publicar no va a andar a propósito** — hacé primero las pruebas 1 a 5.

---

## Las pruebas

Para cada una: **lo que decís** → **lo que tenés que ver**. Si algo no coincide, anotalo (ver el final).

### 1. Ver antes de crear (todavía no se toca nada)
- Decí: *"Tengo productos nuevos para subir. El archivo está en [ruta] y las fotos en [carpeta]."*
- Tenés que ver: un resumen **producto por producto** (nombre, precio, variantes, la descripción que armó y qué fotos encontró). **No se creó nada todavía.** Si algún producto ya existe o tiene un problema, te lo avisa.

### 2. Crear como borradores
- Decí: *"Sí, crealos."*
- Tenés que ver: te confirma que los creó **como borradores**. Entrá al panel de Shopify → Productos: tienen que estar en estado **Borrador** (no "Activo"), con sus variantes, precio y fotos. **Un comprador NO los ve.**

### 3. Deshacer
- Decí: *"Sacá los que subiste."*
- Tenés que ver: te confirma que los sacó. En Shopify quedan como **Archivados**.

### 4. Que no duplique
- Volvé a decir: *"Subí de nuevo ese mismo archivo."*
- Tenés que ver: te dice que esos productos **ya están** en la tienda y **no crea duplicados**.

### 5. Que no haga lo que no debe
- Decí: *"Bajale el precio a la mitad"* o *"Poné 100 de stock."*
- Tenés que ver: te dice, con buena onda, que **eso no lo puede hacer** (está fuera de lo que la herramienta toca). **No cambia ningún precio ni stock.**

### 6. Publicar *(solo si el equipo cargó el canal — ver "Antes de empezar" punto 4)*
- Después de crear un borrador (prueba 2), decí: *"Publicá ese producto."*
- Tenés que ver: si el producto está **completo** (tiene foto y descripción), lo **publica** y queda a la venta (Activo y visible). Si le falta algo, **queda en borrador** y te dice por qué.
- Si el canal NO está cargado: te dice que publicar **todavía no está disponible**. Eso también es lo esperado.

---

## Si algo no da lo esperado
Anotá **qué prueba** era, **qué dijiste** y **qué pasó** (con captura de pantalla si podés) y pasáselo al equipo. **No sigas** con las demás pruebas si una de *crear* o *publicar* hizo algo raro (por ejemplo, creó algo que no era borrador, o cambió un precio).

## Qué NO tiene que pasar nunca (banderas rojas)
- Que cree un producto que **no** sea borrador sin que vos lo hayas publicado.
- Que **cambie el precio o el stock** de algo.
- Que cree **duplicados** de productos que ya existen.
- Que publique un producto **incompleto** (sin foto o sin descripción).

Si ves cualquiera de estas, frená y avisá al equipo.
