# Runbook — Usar el builder visual de escalones

Cómo el cliente arma su oferta de escalones en una pantalla visual y Claude la aplica, manteniendo la
plata pasando por el guard.

## El flujo, de punta a punta

1. **El cliente pide armarla visualmente** ("quiero armar la oferta a ojo", "una pantalla para
   configurarla"). Claude corre la skill `generar-builder-escalones`: paso 0 (confirma tienda), lee
   los productos + el techo, y **genera** `clients/{slug}/escalones-builder.html`.
2. **El cliente abre el archivo** (doble click; se abre en el navegador). Elige el producto, arma los
   escalones (la pantalla **no lo deja** pasar el techo), elige colores y textos, y ve el **preview en
   vivo** con el mismo diseño que la ficha real.
3. **Copia el texto** que la pantalla genera abajo (arranca con `🧩 escalones-config`) y lo **pega en
   el chat**.
4. **Claude lo recibe** y corre `armar-escalones`: **revalida** contra el techo (el builder no es de
   confianza), muestra el preview en texto, pide el "sí", guarda backup y escribe — **primero la
   oferta, después el estilo**, cada uno con su backup (`backups/deals/`, `backups/style/`).
5. La ficha ya instalada (widget de M2) toma la oferta y el look nuevos.

> **El builder no escribe nada en la tienda.** Es una pantalla que produce texto. El único que toca
> plata sigue siendo Claude a través del guard.

## Prerrequisito para que se vea el look

Para que los **colores/textos** que el cliente elige se reflejen en la ficha, el tema tiene que tener
la versión del widget que lee `worker.style` (la de este milestone). Si el widget se instaló antes,
**re-pegá** el bloque actualizado (`widget/worker-escalones.liquid`) en el Custom Liquid del tema —
ver `instalar-widget-escalones.md`. El widget viejo ignora `worker.style` y el color no aparece
(aunque la oferta sí funciona).

## Verificación end-to-end (contra development store, §13.3 del spec padre)

Antes de habilitarlo para un cliente real, correr una vez contra la dev store:

- [ ] **Re-pegar** el widget actualizado en el tema de la dev store (prerequisito de arriba).
- [ ] Generar el builder, abrirlo, armar `2u -10%` / `3u -20%` y cambiar un color.
- [ ] El **preview del builder** coincide **al centavo** con: el preview del chat, el widget en la
      ficha, y el total del carrito. (Redondeo por unidad — lección del centavo §14.)
- [ ] El color elegido viaja a `worker.style` y **el widget lo aplica** en la ficha.
- [ ] Pegar una config con `40%` → Claude la **rechaza** por el techo y ofrece el máximo (30%).
- [ ] Se crean **dos backups**: `backups/deals/…` (`kind:"deal"`) y `backups/style/…` (`kind:"style"`).
- [ ] Registrar en el worklog. Limpiar: desactivar descuentos, `worker.style` a `{}`, borrar backups
      de prueba.

## Límites conocidos (v1)

- Un producto por oferta.
- El look es acotado: cuatro colores + dos textos (título y etiqueta del destacado). No es un editor
  de CSS libre.
- Variantes: el widget v1 usa una sola variante para las N unidades (los N selectores mezclables de
  §4.6 quedan para después).
