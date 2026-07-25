"""Guard de la clase MEDIA (W4-3, spec 2026-07-24-imagenes-realce §5).

Adjuntar una foto REALZADA (de la foto real) a un producto existente es
`productCreateMedia` (solo IMAGE, un producto, backup, undo). El undo es
`productDeleteMedia` acotado a los media ids que la herramienta AGREGÓ (registro en
dos fases). Reusa los patrones del router W3 §7.0.1 y de `_covering_create_record`.
"""
import sys, os, json, time, importlib.util
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

REPO_ROOT = Path(__file__).resolve().parents[1]
root = str(REPO_ROOT)
now = time.time()

T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"
PID = "gid://shopify/Product/1"
MEDIA_ID = "gid://shopify/MediaImage/9"
OTHER_MEDIA = "gid://shopify/MediaImage/99"      # un id NO registrado (foto original)
IMG_URL = "https://cdn.example.com/realzada.jpg"


def _payload(query, variables=None):
    ti = {"query": query}
    if variables is not None:
        ti["variables"] = variables
    return {"tool_name": T_GQL, "tool_input": ti}


def write_media_policy(dest, slug="blunua", allow_media=True, max_images=6, window=72, **over):
    d = Path(dest) / "clients" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"allowMedia": allow_media, "maxImagesPerCall": max_images, "mediaRecordWindowHours": window}
    data.update(over)
    (d / "media-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d / "media-policy.json"


def write_media_record(dest, product_id=PID, slug="blunua", media_ids=None, age_hours=0):
    d = Path(dest) / "clients" / slug / "backups" / "media"
    d.mkdir(parents=True, exist_ok=True)
    tail = product_id.split("/")[-1]
    p = d / f"{tail}-20260724-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_hours * 3600).isoformat()
    rec = {"kind": "media", "productId": product_id, "ts": ts}
    if media_ids is not None:
        rec["mediaIds"] = media_ids
    p.write_text(json.dumps(rec), encoding="utf-8")
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(p, (old, old))
    return p


# --- Task 1: media-policy + _media_ceilings ---

def test_media_ceilings_present_and_valid():
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) == (6, 72)


def test_media_ceilings_none_when_disabled_or_missing_or_malformed():
    assert bg._media_ceilings({"allowMedia": False, "maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) is None
    assert bg._media_ceilings({"maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) is None    # allowMedia ausente
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": 6}) is None               # falta window
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": "6", "mediaRecordWindowHours": 72}) is None  # str
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": True, "mediaRecordWindowHours": 72}) is None  # bool


def test_load_media_policy_excludes_template():
    # con blunua Y _template presentes, el loader devuelve UNA política (no None)
    assert bg.load_media_policy(root) is not None


def test_blunua_media_policy_exists():
    pol = json.loads((REPO_ROOT / "clients" / "blunua" / "media-policy.json").read_text(encoding="utf-8"))
    assert pol.get("allowMedia") is True
    assert isinstance(pol.get("maxImagesPerCall"), int) and not isinstance(pol.get("maxImagesPerCall"), bool)
    assert isinstance(pol.get("mediaRecordWindowHours"), int) and not isinstance(pol.get("mediaRecordWindowHours"), bool)


# --- Task 2: productdelete word-boundary (no atrapa productdeletemedia) ---

def test_productdelete_still_blocked():
    # productDelete solo SIGUE force-bloqueado por FORBIDDEN (el `(` es boundary)
    d, why = bg.evaluate(_payload('mutation{ productDelete(input:{id:"gid://shopify/Product/1"}){ deletedProductId } }'), root, now)
    assert d == "block" and "borra" in why.lower()


def test_productdeletemedia_no_longer_forbidden_matched():
    # productDeleteMedia YA NO lo agarra el scan de FORBIDDEN (word-boundary). Sigue
    # bloqueando (no está en ROOT_FIELD_ALLOWED hasta Task 3), pero por la ALLOWLIST,
    # NO por FORBIDDEN — se verifica que el motivo no sea el de FORBIDDEN.
    d, why = bg.evaluate(_payload('mutation{ productDeleteMedia(productId:"gid://shopify/Product/1", mediaIds:["gid://shopify/MediaImage/9"]){ deletedMediaIds } }'), root, now)
    assert d == "block" and ("publicación o borra" not in why.lower())


# --- helpers de media create/delete (para Tasks 3-6) ---

def media_create(product_id=PID, media=None, media_var="m", inline_media=None):
    """productCreateMedia con `media` por variable (o inline si inline_media)."""
    if inline_media is not None:
        q = (f'mutation{{ productCreateMedia(productId:"{product_id}", media:{inline_media}){{ '
             f'media {{ id }} mediaUserErrors {{ message }} }} }}')
        return _payload(q)
    media = media if media is not None else [{"mediaContentType": "IMAGE", "originalSource": IMG_URL, "alt": "foto"}]
    q = (f'mutation(${media_var}: [CreateMediaInput!]!){{ '
         f'productCreateMedia(productId:"{product_id}", media:${media_var}){{ media {{ id }} mediaUserErrors {{ message }} }} }}')
    return _payload(q, {media_var: media})


def media_delete(product_id=PID, media_ids=None):
    ids = media_ids if media_ids is not None else [MEDIA_ID]
    ids_str = ", ".join(f'"{i}"' for i in ids)
    q = f'mutation{{ productDeleteMedia(productId:"{product_id}", mediaIds:[{ids_str}]){{ deletedMediaIds }} }}'
    return _payload(q)


# --- Task 3: router — media por nombre, asunto propio, len(media_roots)==1 ---

def test_media_plus_productupdate_blocks(tmp_path):
    # productCreateMedia + productUpdate(desc) → block por asuntos (len 2): media NO
    # se cuenta como "cambios de producto", tiene su propio asunto.
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = (f'mutation($m: [CreateMediaInput!]!){{ '
         f'productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} '
         f'productUpdate(input:{{id:"{PID}", descriptionHtml:"<p>x</p>"}}){{ product {{ id }} }} }}')
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}), tmp_path, time.time())
    assert d == "block" and "mezcla" in why, why


def test_create_plus_delete_media_one_doc_blocks(tmp_path):
    # el fail-open DESTRUCTIVO: productCreateMedia + productDeleteMedia en un doc. La
    # delete apunta a un id RECORDED (MEDIA_ID), así que PASARÍA sola — el corte tiene
    # que venir de len(media_roots)!=1 (no de un id faltante). Se asserta el motivo de
    # la regla len para probar la atribución, igual que test_two_deletes_in_one_doc.
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    q = (f'mutation($m: [CreateMediaInput!]!){{ '
         f'productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} '
         f'productDeleteMedia(productId:"{PID}", mediaIds:["{MEDIA_ID}"]){{ deletedMediaIds }} }}')
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}), tmp_path, time.time())
    assert d == "block" and "por separado" in why, why


def test_lone_media_routes_not_double_count(tmp_path):
    # productCreateMedia solo → NO muere fail-closed por doble-conteo: rutea a su
    # check (que bloquea por falta de registro, NO por "mezcla").
    write_media_policy(tmp_path)   # sin registro media
    d, why = bg.evaluate(media_create(), tmp_path, time.time())
    assert d == "block" and "registro" in why and "mezcla" not in why, why


# --- Task 4: _check_media_create (solo IMAGE, source, tope, registro) ---

def test_media_create_allows_image_with_record(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    d, why = bg.evaluate(media_create(), tmp_path, time.time())
    assert d == "allow", why


def test_media_create_blocks_video(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    d, why = bg.evaluate(media_create(media=[{"mediaContentType": "VIDEO", "originalSource": IMG_URL}]), tmp_path, time.time())
    assert d == "block" and "video" in why.lower(), why


def test_media_create_blocks_3d(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    d, why = bg.evaluate(media_create(media=[{"mediaContentType": "MODEL_3D", "originalSource": IMG_URL}]), tmp_path, time.time())
    assert d == "block", why


def test_media_create_blocks_inline(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    inline = f'[{{mediaContentType: IMAGE, originalSource: "{IMG_URL}"}}]'
    d, why = bg.evaluate(media_create(inline_media=inline), tmp_path, time.time())
    assert d == "block" and "variables" in why, why


def test_media_create_blocks_when_allowmedia_false(tmp_path):
    write_media_policy(tmp_path, allow_media=False); write_media_record(tmp_path)
    assert bg.evaluate(media_create(), tmp_path, time.time())[0] == "block"


def test_media_create_blocks_without_policy(tmp_path):
    write_media_record(tmp_path)   # sin media-policy
    assert bg.evaluate(media_create(), tmp_path, time.time())[0] == "block"


def test_media_create_blocks_over_max_images(tmp_path):
    write_media_policy(tmp_path, max_images=2); write_media_record(tmp_path)
    media = [{"mediaContentType": "IMAGE", "originalSource": IMG_URL} for _ in range(3)]
    d, why = bg.evaluate(media_create(media=media), tmp_path, time.time())
    assert d == "block" and "hasta 2" in why, why


def test_media_create_blocks_non_https_source(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    d, why = bg.evaluate(media_create(media=[{"mediaContentType": "IMAGE", "originalSource": "http://insecure.example/x.jpg"}]),
                         tmp_path, time.time())
    assert d == "block" and "https" in why, why


def test_media_create_blocks_without_media_record(tmp_path):
    write_media_policy(tmp_path)   # policy pero SIN registro media
    d, why = bg.evaluate(media_create(), tmp_path, time.time())
    assert d == "block" and "registro" in why, why


def test_media_create_blocks_missing_productid(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = 'mutation($m: [CreateMediaInput!]!){ productCreateMedia(media:$m){ media { id } } }'
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}), tmp_path, time.time())
    assert d == "block", why


def test_media_create_blocks_stale_record(tmp_path):
    # registro fuera de la ventana (mediaRecordWindowHours=72) → block
    write_media_policy(tmp_path); write_media_record(tmp_path, age_hours=200)
    assert bg.evaluate(media_create(), tmp_path, time.time())[0] == "block"


# --- Task 5: _check_media_delete (por-id, iterar todos) — la parte destructiva ---

def test_media_delete_allows_recorded_id(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    d, why = bg.evaluate(media_delete(media_ids=[MEDIA_ID]), tmp_path, time.time())
    assert d == "allow", why


def test_media_delete_blocks_unrecorded_id(tmp_path):
    # borrar un id que NO está en el registro = borrar una foto ORIGINAL del cliente → block
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    d, why = bg.evaluate(media_delete(media_ids=[OTHER_MEDIA]), tmp_path, time.time())
    assert d == "block" and "registro" in why, why


def test_media_delete_blocks_if_any_id_unrecorded(tmp_path):
    # iterar TODOS: uno registrado + uno original NO registrado → block
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    d, why = bg.evaluate(media_delete(media_ids=[MEDIA_ID, OTHER_MEDIA]), tmp_path, time.time())
    assert d == "block", why


def test_media_delete_blocks_without_record(tmp_path):
    # sin registro media propio → block (motivo media-específico "registro")
    write_media_policy(tmp_path)
    d, why = bg.evaluate(media_delete(media_ids=[MEDIA_ID]), tmp_path, time.time())
    assert d == "block" and "registro" in why, why


def test_media_delete_blocks_productid_mismatch(tmp_path):
    # registro de PID, delete sobre OTRO producto → no hay registro para ese → block
    write_media_policy(tmp_path); write_media_record(tmp_path, product_id=PID, media_ids=[MEDIA_ID])
    d, why = bg.evaluate(media_delete(product_id="gid://shopify/Product/2", media_ids=[MEDIA_ID]), tmp_path, time.time())
    assert d == "block", why


def test_media_delete_via_variable_ids_allows(tmp_path):
    # mediaIds por $var resuelto → allow si todos están registrados
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    q = f'mutation($ids: [ID!]!){{ productDeleteMedia(productId:"{PID}", mediaIds:$ids){{ deletedMediaIds }} }}'
    d, why = bg.evaluate(_payload(q, {"ids": [MEDIA_ID]}), tmp_path, time.time())
    assert d == "allow", why


# --- Task 6: anti-bypass + regresión ---

def test_media_create_decoy_variable_validates_referenced(tmp_path):
    # el query referencia $m; un decoy manso (IMAGE) NO cambia que se valide $m (VIDEO)
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = f'mutation($m: [CreateMediaInput!]!){{ productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} }}'
    variables = {"m": [{"mediaContentType": "VIDEO", "originalSource": IMG_URL}],
                 "decoy": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"


def test_media_mixed_with_metafield_blocks(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = (f'mutation($m: [CreateMediaInput!]!){{ '
         f'productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} '
         f'metafieldsSet(metafields: [{{ownerId:"{PID}", namespace:"worker", key:"deal", value:"{{}}", type:"json"}}]){{ metafields {{ id }} }} }}')
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}), tmp_path, time.time())
    assert d == "block" and "mezcla" in why, why


def test_media_mixed_with_discount_deactivate_blocks(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = (f'mutation($m: [CreateMediaInput!]!){{ '
         f'productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} '
         f'discountAutomaticDeactivate(id:"gid://shopify/DiscountAutomaticNode/1"){{ automaticDiscountId }} }}')
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}]}), tmp_path, time.time())
    assert d == "block" and "mezcla" in why, why


def test_media_create_plus_productset_blocks(tmp_path):
    write_media_policy(tmp_path); write_media_record(tmp_path)
    q = (f'mutation($m: [CreateMediaInput!]!, $p: ProductSetInput!){{ '
         f'productCreateMedia(productId:"{PID}", media:$m){{ media {{ id }} }} '
         f'productSet(input:$p){{ product {{ id }} }} }}')
    d, why = bg.evaluate(_payload(q, {"m": [{"mediaContentType": "IMAGE", "originalSource": IMG_URL}],
                                      "p": {"title": "x", "status": "DRAFT"}}), tmp_path, time.time())
    assert d == "block" and "mezcla" in why, why


def test_two_deletes_in_one_doc_blocks(tmp_path):
    # dos productDeleteMedia en un doc → len(media_roots)!=1 → block (con registro
    # válido para AMBOS ids, para probar que el corte viene de len==1, no de records)
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID, OTHER_MEDIA])
    q = (f'mutation{{ productDeleteMedia(productId:"{PID}", mediaIds:["{MEDIA_ID}"]){{ deletedMediaIds }} '
         f'b: productDeleteMedia(productId:"{PID}", mediaIds:["{OTHER_MEDIA}"]){{ deletedMediaIds }} }}')
    d, why = bg.evaluate(_payload(q), tmp_path, time.time())
    assert d == "block" and "por separado" in why, why


def test_media_delete_decoy_variable_validates_executed_ids(tmp_path):
    # simétrico a test_media_create_decoy_...: mediaIds:$ids referenciado; un decoy
    # manso (id registrado) NO cambia que se validen los ids EJECUTADOS. Con $ids = un
    # id NO registrado, bloquea aunque el decoy sea válido.
    write_media_policy(tmp_path); write_media_record(tmp_path, media_ids=[MEDIA_ID])
    q = f'mutation($ids: [ID!]!){{ productDeleteMedia(productId:"{PID}", mediaIds:$ids){{ deletedMediaIds }} }}'
    variables = {"ids": [OTHER_MEDIA], "decoy": [MEDIA_ID]}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"


# --- M-2(b): invariante de la blocklist vs allowlist ---

def test_forbidden_not_substring_of_allowed_unless_word_boundary():
    """Invariante del guard: ninguna entrada de FORBIDDEN_MUTATIONS puede ser
    substring de un root de ROOT_FIELD_ALLOWED (over-block silencioso / shadow de un
    root nuevo), SALVO que esté word-boundary-special-cased (hoy productdelete vs
    productdeletemedia). Convierte la corrección de hoy en un invariante enforced:
    si mañana una forbidden nueva es substring de un root permitido nuevo sin su
    boundary, este test cae."""
    for f in bg.FORBIDDEN_MUTATIONS:
        for a in bg.ROOT_FIELD_ALLOWED:
            if f in a and f != a:
                assert f in bg.WORD_BOUNDARY_FORBIDDEN, (
                    f"'{f}' es substring de '{a}' pero no está en WORD_BOUNDARY_FORBIDDEN")
