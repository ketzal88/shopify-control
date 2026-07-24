# Editar un producto vacío — marca `originalEmpty` en el backup

**Fecha:** 2026-07-24
**Ámbito:** `backup_guard.py` (capa 2 del guard de writes) + `mejorar-descripcion`
**Relación:** refina §11 capa 2 de `2026-07-19-shopify-control-v1-design.md`

## Problema

`backup_guard._covering_backup` rechaza cualquier backup cuyos 3 campos
(`descriptionHtml`, `seo_title`, `seo_description`) estén vacíos. Esa regla existe
por seguridad: un backup de placeholders (todo vacío) satisfacía al guard viejo y
después el "undo" restauraba vacío en vez del contenido real, **borrándolo**.

El efecto colateral: un producto que **genuinamente** no tiene descripción ni SEO
(los 3 campos vacíos de verdad) no puede editarse. El único backup honesto de ese
estado es all-empty, y el guard lo descarta. Es el producto que más necesita una
descripción y el único que la herramienta no puede tocar. Verificado en vivo contra
la dev store con `The Multi-location Snowboard` (descripción `""`, SEO `null`).

## Decisión

El guard no puede ver la tienda (es síncrono, sin acceso al Admin API), así que no
puede distinguir por sí solo "producto vacío de verdad" de "backup mentiroso". Se
delega esa distinción al skill —que **sí** lee el estado en vivo antes de escribir—
mediante una **marca explícita**:

> Un backup all-empty es válido **si y solo si** trae `"originalEmpty": true` al tope
> del JSON. El skill la pone únicamente cuando leyó en vivo los 3 campos y los tres
> estaban vacíos.

Es el mismo patrón de discriminación por campo que el guard ya usa (`kind:"deal"`,
`kind:"<familia cosmética>"`), pero como el backup de descripción/SEO no usa `kind`,
se usa un booleano dedicado (`originalEmpty`) en vez de sobrecargar `kind`.

## El cambio en el guard (`_covering_backup`)

Se reordena para que la frescura (mtime + `ts`) se evalúe **antes** de la regla de
vacío, y la regla de vacío se condiciona a la marca:

1. `any(not isinstance(v, str))` → inválido. **Sin excepción** (los `null` siguen
   bloqueados; la marca solo salva strings vacíos `""`, no `None`).
2. mtime fuera de ventana → descartar.
3. `ts` no fresco → descartar.
4. `all(not v.strip())` (los 3 vacíos):
   - `data.get("originalEmpty") is True` → seed válido, cae como hit.
   - si no → se marca `saw_unmarked_empty` y se descarta.
5. Si no hubo hits y hubo un all-empty reciente sin marca, el motivo devuelto lo
   dice explícitamente (deja de mentir con el genérico "sin backup reciente").

### Invariantes que NO se aflojan

- **`null` sigue bloqueado.** La marca solo aplica a strings vacíos.
- **`is True` estricto.** Un `"true"` string o un `1` no cuentan; solo el booleano
  JSON `true`.
- **La marca es inerte si hay contenido.** Si algún campo trae texto, nunca se mira
  `originalEmpty`; es un backup normal.
- **La frescura sigue rigiendo** también para el seed.

## El cambio en el skill (`mejorar-descripcion`)

- **Paso 9 (backup):** si en el paso 3 leyó los 3 campos vacíos, guarda el backup con
  `"originalEmpty": true` y los 3 campos en `""`. Si no, backup normal sin marca.
- **Undo:** sin cambios. Para revertir lee el estado actual (ya con contenido → backup
  válido no-vacío) y reescribe los `""` viejos. Volver a vacío es correcto para un
  producto que nació vacío.

## Riesgo residual (aceptado explícitamente)

La marca la pone el modelo, así que un backup mal marcado (`originalEmpty:true` sobre
un producto que en realidad tenía contenido) reabriría —solo en el caso all-empty— el
escenario "undo borra contenido". Se acepta a cambio de la simplicidad, con estas
atenuaciones: la marca es explícita y auditable (queda en el archivo y en el worklog),
su efecto se limita al único caso all-empty, y el resto de los backups (con contenido,
el 99%) no cambian en nada.

## Caveat operativo

Los hooks se cargan al iniciar la sesión de Claude Code. El guard nuevo recién toma
efecto **tras reiniciar la sesión**; hasta entonces un write sobre un producto vacío
se sigue bloqueando.

## Tests (en `tests/test_backup_guard.py`)

- seed all-empty **con** marca → allow
- seed all-empty **sin** marca → block *(ya existe; se mantiene)*
- `null` **con** marca → sigue block
- marca `"true"` string / `1` → block (estrictez del booleano)
- seed con marca pero **stale** → block
- marca ignorada cuando hay contenido → allow
