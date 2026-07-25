# Imágenes: realce + adjuntar (W4-3) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Un skill cliente-facing que realza la foto REAL de un producto (fondo de marca vía Higgsfield) y la adjunta, extendiendo el guard con una clase `media` (`productCreateMedia` solo-IMAGE + `productDeleteMedia` acotado al undo por-id), fail-closed.

**Architecture:** En `backup_guard.py`: fix de la colisión de substring (`productdelete` word-boundary), router que rutea `productcreatemedia`/`productdeletemedia` por nombre con su propio asunto `media` y `len(media_roots)==1`, `_check_media_create`/`_check_media_delete`, `_covering_media_record` (dos fases). `media-policy.json` por cliente. El skill hace el realce (Higgsfield, no toca Shopify) + los writes gateados. Se define `store-standards §7` (plantilla de marca). Se actualizan `CLAUDE.md` regla 5 + `store-standards §8`.

**Tech Stack:** Python 3 (stdlib), pytest. GraphQL: `productCreateMedia`, `productDeleteMedia`, `stagedUploadsCreate` (ya permitido, F2). Higgsfield: `remove_background`/`outpaint_image`/`upscale_image`.

**Spec:** `docs/superpowers/specs/2026-07-24-imagenes-realce-design.md` §5. Reusa patrones de W3 F2/F3 (router §7.0.1, registro post-write kind:create, `_top_level_args`).

## Contexto del guard (leer antes de tocar)
- El scan de `FORBIDDEN_MUTATIONS` (líneas ~1992-1995): `for m in FORBIDDEN_MUTATIONS: if m in low` (substring). `productdelete` ⊂ `productdeletemedia`.
- El router de producto (W3 §7.0.1): `product_roots`, `create_or_status`, `len(product_roots)==1`, dispatch por nombre.
- `_top_level_args`/`_productid_arg` (string-aware, por clave). `_covering_create_record` (kind+ruta+ventana en horas, dos fases post-write). `load_create_policy` (excluye `_template`).

---

## Task 1: `media-policy.json` + `_media_ceilings`

**Files:** Modify: `clients/blunua/`, `clients/_template/` (nuevo `media-policy.json`); `.claude/hooks/backup_guard.py`. Test: `tests/test_media_guard.py`.

- [ ] **Tests:** `_media_ceilings({"allowMedia":True,"maxImagesPerCall":6,"mediaRecordWindowHours":72})==(6,72)`; None si `allowMedia:false`, si falta una clave, o si algún techo no es int (int-no-bool). `load_media_policy(<repo root>)` no None con `_template` presente (excluye `_template`).
- [ ] **Impl:** crear `media-policy.json` en ambos (`{"allowMedia":true,"maxImagesPerCall":6,"mediaRecordWindowHours":72}`); `load_media_policy` (mismo patrón que `load_create_policy`, excluye `_template`); `_media_ceilings` (espejo de `_gift_ceilings`/`_combo_ceilings`).
- [ ] **Commit** → `feat(w4): media-policy + _media_ceilings (W4-3)`

---

## Task 2: colisión `productdelete` ⊂ `productdeletemedia` — word-boundary (el cambio más sensible)

**Files:** Modify: `.claude/hooks/backup_guard.py`. Test: `tests/test_media_guard.py`.

⚠️ **Cambio en la línea más sensible del guard.** Hoy `productDeleteMedia` queda force-bloqueado por el substring `productdelete`. Fix mínimo: matchear `productdelete` con **word-boundary** (`\bproductdelete\b`), que matchea `productDelete(` (el `(` es boundary) pero NO `productdeletemedia` (`m` es word-char, sin boundary). Dejar los demás entries como están (substring), o —si es más limpio— pasar TODO el scan a `\b<entry>\b` (verificar que ningún test de FORBIDDEN se rompa: todos llaman `mutation(` así que el boundary existe).

- [ ] **Tests que fallan:**

```python
def test_productdelete_still_blocked():
    # productDelete solo sigue force-bloqueado por FORBIDDEN
    assert bg.evaluate(_payload('mutation{ productDelete(input:{id:"gid://shopify/Product/1"}){ deletedProductId } }'), root, now)[0] == "block"

def test_productdeletemedia_not_forcedblocked_by_forbidden():
    # productDeleteMedia YA NO lo agarra el scan de FORBIDDEN (pasa a la clase media;
    # sin registro va a bloquear igual, pero por _check_media_delete, no por FORBIDDEN)
    d, why = bg.evaluate(_payload('mutation{ productDeleteMedia(productId:"gid://shopify/Product/1", mediaIds:["gid://shopify/MediaImage/9"]){ deletedMediaIds } }'), root, now)
    assert d == "block" and "sacá" in why.lower() or "registr" in why.lower()   # bloquea por media, no por "fuera de alcance"
```

- [ ] **Impl:** word-boundary para `productdelete`. Correr TODA la suite de guard (los tests de FORBIDDEN deben seguir verdes).
- [ ] **Commit** → `feat(w4): productdelete match por word-boundary (no atrapa productdeletemedia) (W4-3)`

---

## Task 3: router — media por nombre, asunto propio, `len(media_roots)==1`

**Files:** Modify: `.claude/hooks/backup_guard.py`. Test: `tests/test_media_guard.py`.

Spec §5.2: agregar `productcreatemedia`/`productdeletemedia` a `ROOT_FIELD_ALLOWED`; **excluir** del bucket `product_roots`; darles el asunto `media` (append antes de `len(asuntos)>1`); **`len(media_roots)==1`** (block si hay >1 media en el doc); dispatch por nombre a `_check_media_create`/`_check_media_delete` ANTES de la rama `productupdate`.

- [ ] **Tests que fallan (los fail-opens del review):**

```python
def test_media_plus_productupdate_blocks():          # productCreateMedia + productUpdate(desc) → block (asuntos len 2)
def test_create_plus_delete_media_one_doc_blocks():  # productCreateMedia + productDeleteMedia → block (len(media_roots)!=1) — cierra el fail-open destructivo
def test_lone_media_routes_not_double_count():        # productCreateMedia solo → NO muere fail-closed por doble-conteo
```

- [ ] **Impl** la restructura. Suite completa verde (productos/ofertas/combos/descripción intactos).
- [ ] **Commit** → `feat(w4): router rutea media por nombre, asunto propio, una media por doc (W4-3)`

---

## Task 4: `_check_media_create` + `_covering_media_record` (fase pre-write)

**Files:** Modify: `.claude/hooks/backup_guard.py`. Test: `tests/test_media_guard.py`.

`_check_media_create` (spec §5.3): `_media_ceilings` no None; un solo `productCreateMedia` (garantizado por Task 3); `media` = referencia a variable (inline `[` → block); cada item `mediaContentType == IMAGE` (VIDEO/EXTERNAL_VIDEO/MODEL_3D → block); `productId` por clave string-aware, único; `originalSource` `_ok_url` https o staged `resourceUrl`; `len(media) ≤ maxImagesPerCall`; **registro `kind:"media"` pre-write** (`_covering_media_record`, ruta `backups/media/`, ventana `mediaRecordWindowHours`, cross-client guard). `CreateMediaInput` confirmado `{alt, mediaContentType, originalSource}`.

- [ ] **Tests:** allow IMAGE válido con registro+policy; block VIDEO/3D; block inline; block `allowMedia:false`/policy ausente; block > maxImagesPerCall; block productId ausente/múltiple; block sin registro `media`; block source no-https.
- [ ] **Impl** `_check_media_create` + `_covering_media_record` (espejo de `_covering_create_record`).
- [ ] **Commit** → `feat(w4): _check_media_create solo-IMAGE + registro media (W4-3)`

---

## Task 5: `_check_media_delete` (por-id, iterar todos) — la parte destructiva

**Files:** Modify: `.claude/hooks/backup_guard.py`. Test: `tests/test_media_guard.py`.

Spec §5.4/§5.5: `productDeleteMedia(productId, mediaIds:[ID!])`. `productId` por clave string-aware; **cada `mediaId`** de la lista tiene que estar en los ids que la herramienta creó para ese producto (registro `media` post-write, §5.5); **iterar TODOS** — si alguno no está registrado → block. Sin registro → block. Es lo que impide borrar las fotos originales del cliente.

- [ ] **Tests:** allow borrar un id registrado; **block si algún id de la lista NO está registrado** (borrar original montado en uno propio); block sin registro; block productId mismatch.
- [ ] **Impl** `_check_media_delete` (matchea contra los ids del registro post-write).
- [ ] **Commit** → `feat(w4): _check_media_delete acotado a ids registrados (undo), iterando todos (W4-3)`

---

## Task 6: anti-bypass + regresión

**Files:** Test: `tests/test_media_guard.py`.

- [ ] Señuelo en variables del `media`; media mezclado con oferta/metafield → block; el `len(media_roots)==1` con dos deletes → block. Correr `python -m pytest tests/test_backup_guard*.py tests/test_create_guard.py tests/test_combo_guard.py tests/test_publish_guard.py tests/test_media_guard.py -q` — todo verde.
- [ ] **Commit** → `test(w4): anti-bypass y regresión de la clase media (W4-3)`

---

## Task 7: skill + `store-standards §7` (plantilla de marca)

**Files:** Create: `.claude/skills/mejorar-fotos/SKILL.md`. Modify: `clients/blunua/store-standards.md` §7.

- [ ] **§7 (deliverable del review):** definir la plantilla de imagen de marca de blunua — fondo (limpio, uno de los 4 colores §7), encuadre (producto centrado, aire), cómo aplican los colores, qué Higgsfield tool para cada paso. Sacarla de placeholder.
- [ ] **SKILL.md `mejorar-fotos`** (spec §6): paso 0 → identificar producto → leer foto actual (`graphql_query`) → **realce Higgsfield sobre la foto real** (transformaciones acotadas, regla de integridad §4) → preview antes/después → gate → registro `media` pre-write → `productCreateMedia` (IMAGE) → capturar los media ids devueltos al registro (post-write) → worklog → undo (`productDeleteMedia` del id registrado). Sin jerga; para productos nuevos, el realce se suma en el `productSet.files` de F2 (no `productCreateMedia`).
- [ ] **Commit** → `feat(w4): skill mejorar-fotos (realce Higgsfield + adjuntar gateado) + §7 de marca (W4-3)`

---

## Task 8: actualizar docs de alcance (lockstep)

**Files:** Modify: `CLAUDE.md` (regla 5), `clients/blunua/store-standards.md` (§8).

- [ ] Sumar la clase de write `media` (adjuntar imágenes realzadas de la foto real, con su guard) a la enumeración de alcance de `CLAUDE.md` regla 5 y `store-standards §8`, para que el "NUNCA lo demás" siga siendo cierto y coherente con el guard.
- [ ] **Commit** → `docs(w4): media como clase de write en el alcance (CLAUDE.md, store-standards §8) (W4-3)`

---

## Cierre
- [ ] Suite completa `python -m pytest -q` verde.
- [ ] Confirmar: `permissions.deny` intacto; `FORBIDDEN_MUTATIONS` = solo se ajustó el match de `productdelete` (sigue bloqueando `productDelete`), el resto intacto; `productDeleteMedia` solo pasa por su check.
- [ ] e2e manual (operador, dev store): realzar una foto real, adjuntar, verificar en admin, sacar (undo). Higgsfield real.
