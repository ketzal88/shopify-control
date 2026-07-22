"""Guard del regalo gratis / BXGY (spec 2026-07-22-regalo-gratis-bxgy-design §9).

BXGY NO reusa `_check_discount`: esa función asume la forma Basic
(`customerGets.value.percentage` acotado por `maxDiscountPct`), y un regalo va
por `customerGets.value.discountOnQuantity.effect.percentage`, donde "gratis"
es 1.0 (=100%) y `maxDiscountPct` lo bloquearía siempre. Función propia
`_check_bxgy` con su propio techo (`maxGiftPct`/`maxGetQty`/`minBuyGetRatio` +
allowlist de regalables para el cruzado).
"""
import json, time, os
from datetime import datetime
from pathlib import Path
import importlib.util

GUARD = Path(__file__).parent.parent / ".claude/hooks/backup_guard.py"
spec = importlib.util.spec_from_file_location("backup_guard", GUARD)
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"
PID = "gid://shopify/Product/1"      # producto comprado (P)
QID = "gid://shopify/Product/2"      # producto regalado en el cruzado (Q)


def write_deal_backup(root, product_id=PID):
    d = Path(root) / "clients/blunua/backups/deals"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{product_id.split('/')[-1]}-20260722-120000.json"
    p.write_text(json.dumps({"kind": "deal", "productId": product_id,
                             "previous": None, "ts": datetime.now().isoformat()}),
                 encoding="utf-8")
    return p


def policy(tmp_path, **over):
    from tests.test_deal_policy import write_policy
    return write_policy(tmp_path, **over)


def bxgy_create(buy_qty=2, get_qty=1, gift_pct=1.0, buy_pid=PID, get_pid=PID,
                ends="2026-10-18T00:00:00Z", starts="2026-07-20T00:00:00Z",
                uses="1", product_id=None, gets_value=None, buys_items=None,
                gets_items=None):
    """Un BXGY nativo. Por default: mismo producto, comprá 2 → el 3º gratis."""
    product_id = product_id if product_id is not None else buy_pid
    buys_items = buys_items if buys_items is not None else {"products": {"productsToAdd": [buy_pid]}}
    gets_items = gets_items if gets_items is not None else {"products": {"productsToAdd": [get_pid]}}
    gets_value = gets_value if gets_value is not None else {
        "discountOnQuantity": {"quantity": str(get_qty), "effect": {"percentage": gift_pct}}}
    d = {"title": "shopify-control · Regalo · test",
         "startsAt": starts, "endsAt": ends, "usesPerOrderLimit": uses,
         "customerBuys": {"value": {"quantity": str(buy_qty)}, "items": buys_items},
         "customerGets": {"value": gets_value, "items": gets_items}}
    variables = {"d": d}
    if product_id is not None:
        variables["productId"] = product_id
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($d: DiscountAutomaticBxgyInput!, $productId: ID!) "
                 "{ discountAutomaticBxgyCreate(automaticBxgyDiscount: $d) { automaticDiscountNode { id } } }",
        "variables": variables}}


# --- create: camino feliz ---------------------------------------------------

def test_same_product_gift_happy_path(tmp_path):
    """Comprá 2 → el 3º gratis, mismo producto. Con backup fresco: pasa."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert d == "allow", why

def test_cross_product_gift_happy_path(tmp_path):
    """Comprá P → llevate Q de regalo, con Q en la allowlist."""
    policy(tmp_path, allowCrossProductGift=True, giftableProducts=[QID])
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=1, get_pid=QID), tmp_path, time.time())
    assert d == "allow", why

def test_bxgy_is_no_longer_blocked_unconditionally(tmp_path):
    """Antes caía en el catch-all de la whitelist. Ahora entra por _check_bxgy."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert d == "allow"


# --- create: techo de porcentaje del regalo ---------------------------------

def test_gift_pct_over_ceiling_is_blocked(tmp_path):
    """maxGiftPct=50; un regalo del 100% (gratis) tiene que chocar."""
    policy(tmp_path, maxGiftPct=50); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(gift_pct=1.0), tmp_path, time.time())
    assert d == "block", why

def test_gift_pct_exactly_100_is_allowed_when_ceiling_100(tmp_path):
    """El borde: 1.0 → 100 tiene que pasar con maxGiftPct=100, sin off-by-one."""
    policy(tmp_path, maxGiftPct=100); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(gift_pct=1.0), tmp_path, time.time())
    assert d == "allow", why

def test_gift_pct_unit_trap(tmp_path):
    """0.7 es 70%, no 0.7%. Con maxGiftPct=50 tiene que bloquear."""
    policy(tmp_path, maxGiftPct=50); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(gift_pct=0.7), tmp_path, time.time())
    assert d == "block", why


# --- create: formas que BXGY no soporta -------------------------------------

def test_top_level_percentage_form_is_blocked(tmp_path):
    """BXGY no soporta customerGets.value.percentage; solo discountOnQuantity."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(gets_value={"percentage": 1.0}), tmp_path, time.time())
    assert d == "block", why

def test_top_level_discount_amount_form_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(
        gets_value={"discountAmount": {"amount": "10.0", "appliesOnEachItem": True}}),
        tmp_path, time.time())
    assert d == "block", why


# --- create: cantidad regalada y ratio --------------------------------------

def test_get_qty_over_ceiling_is_blocked(tmp_path):
    """maxGetQty=1; regalar 2 unidades tiene que bloquear."""
    policy(tmp_path, maxGetQty=1); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=4, get_qty=2), tmp_path, time.time())
    assert d == "block", why

def test_same_product_insufficient_ratio_is_blocked(tmp_path):
    """minBuyGetRatio=2; 'comprá 1 llevá 1' (50% off encubierto) tiene que bloquear."""
    policy(tmp_path, minBuyGetRatio=2); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=1, get_qty=1), tmp_path, time.time())
    assert d == "block", why

def test_same_product_meets_ratio_is_allowed(tmp_path):
    policy(tmp_path, minBuyGetRatio=2); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=2, get_qty=1), tmp_path, time.time())
    assert d == "allow", why


# --- create: usesPerOrderLimit forzado --------------------------------------

def test_uses_per_order_limit_must_be_one(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(uses="5"), tmp_path, time.time())
    assert d == "block", why

def test_uses_per_order_limit_absent_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(uses=None), tmp_path, time.time())
    assert d == "block", why


# --- create: cruzado y allowlist --------------------------------------------

def test_cross_not_in_allowlist_is_blocked(tmp_path):
    policy(tmp_path, allowCrossProductGift=True, giftableProducts=[])
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=1, get_pid=QID), tmp_path, time.time())
    assert d == "block", why

def test_cross_disabled_is_blocked(tmp_path):
    policy(tmp_path, allowCrossProductGift=False, giftableProducts=[QID])
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(buy_qty=1, get_pid=QID), tmp_path, time.time())
    assert d == "block", why


# --- create: scope, all, colección ------------------------------------------

def test_gift_over_all_catalog_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(gets_items={"all": True}), tmp_path, time.time())
    assert d == "block", why

def test_gift_over_collection_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(
        gets_items={"collections": {"add": ["gid://shopify/Collection/9"]}}),
        tmp_path, time.time())
    assert d == "block", why

def test_buy_over_collection_is_blocked(tmp_path):
    """El scope se valida en LOS DOS lados: la compra tampoco puede ser colección."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(
        buys_items={"collections": {"add": ["gid://shopify/Collection/9"]}}),
        tmp_path, time.time())
    assert d == "block", why


# --- create: fechas, backup, política ---------------------------------------

def test_missing_endsAt_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(ends=None), tmp_path, time.time())
    assert d == "block", why

def test_duration_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(ends="2031-01-01T00:00:00Z"), tmp_path, time.time())
    assert d == "block", why

def test_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, why = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert d == "block", why

def test_without_productId_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    p = bxgy_create()
    del p["tool_input"]["variables"]["productId"]
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why

def test_no_policy_fails_closed(tmp_path):
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert d == "block", why

def test_policy_without_gift_keys_fails_closed(tmp_path):
    """Un cliente sin techo de regalos configurado no puede crear regalos."""
    from tests.test_deal_policy import DEFAULTS
    d = Path(tmp_path) / "clients/blunua"
    d.mkdir(parents=True, exist_ok=True)
    (d / "deal-policy.json").write_text(json.dumps(DEFAULTS), encoding="utf-8")  # solo claves escalones
    write_deal_backup(tmp_path)
    dec, why = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert dec == "block", why


# --- create: bxgy escondido detrás de un deactivate -------------------------

def test_deactivate_plus_bxgy_applies_full_conditions(tmp_path):
    """Un deactivate adelante no exime al bxgy de atrás: sin datos válidos, bloquea."""
    policy(tmp_path); write_deal_backup(tmp_path)
    deact = 'discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/7") { automaticDiscountNode { id } }'
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f"mutation {{ {deact} discountAutomaticBxgyCreate(x: 1) {{ id }} }}"}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why

def test_bxgy_plus_basic_create_is_blocked(tmp_path):
    """Dos familias de create en un documento: no se validan dos techos juntos."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = bxgy_create()
    p["tool_input"]["query"] = p["tool_input"]["query"].replace(
        "{ discountAutomaticBxgyCreate",
        "{ discountAutomaticBasicCreate(automaticBasicDiscount: $d) { automaticDiscountNode { id } } "
        "discountAutomaticBxgyCreate", 1)
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why


# --- metafield worker.deal type:"bxgy" --------------------------------------

def bxgy_metafield(scope="same", buy_qty=2, get_qty=1, gift_pct=100,
                   buy_pid=PID, get_pid=PID, owner=PID):
    value = json.dumps({
        "version": 1, "type": "bxgy", "scope": scope,
        "buy": {"qty": buy_qty, "product": buy_pid},
        "get": {"qty": get_qty, "product": get_pid, "handle": "x", "pct": gift_pct},
        "strategy": "automatic", "usesPerOrderLimit": 1,
        "startsAt": "2026-07-20T00:00:00Z", "endsAt": "2026-10-18T00:00:00Z"})
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [{"ownerId": owner, "namespace": "worker", "key": "deal",
                             "type": "json", "value": value}]}}}

def test_bxgy_metafield_happy_path(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(), tmp_path, time.time())
    assert d == "allow", why

def test_bxgy_metafield_pct_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path, maxGiftPct=50); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(gift_pct=100), tmp_path, time.time())
    assert d == "block", why

def test_bxgy_metafield_get_qty_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path, maxGetQty=1); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(buy_qty=4, get_qty=2), tmp_path, time.time())
    assert d == "block", why

def test_bxgy_metafield_same_product_ratio_is_enforced(tmp_path):
    policy(tmp_path, minBuyGetRatio=2); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(buy_qty=1, get_qty=1), tmp_path, time.time())
    assert d == "block", why

def test_bxgy_metafield_cross_not_in_allowlist_is_blocked(tmp_path):
    policy(tmp_path, allowCrossProductGift=True, giftableProducts=[])
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(scope="cross", buy_qty=1, get_pid=QID),
                         tmp_path, time.time())
    assert d == "block", why

def test_bxgy_metafield_cross_in_allowlist_is_allowed(tmp_path):
    policy(tmp_path, allowCrossProductGift=True, giftableProducts=[QID])
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(scope="cross", buy_qty=1, get_pid=QID),
                         tmp_path, time.time())
    assert d == "allow", why

def test_bxgy_metafield_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, why = bg.evaluate(bxgy_metafield(), tmp_path, time.time())
    assert d == "block", why

def test_escalones_metafield_still_works(tmp_path):
    """Regresión: un metafield de escalones (type quantity_breaks) sigue validando
    por el camino de tiers, no por el de bxgy."""
    policy(tmp_path); write_deal_backup(tmp_path)
    value = json.dumps({"version": 1, "type": "quantity_breaks",
                        "tiers": [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}],
                        "strategy": "automatic"})
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [{"ownerId": PID, "namespace": "worker", "key": "deal",
                             "type": "json", "value": value}]}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow", why


# --- Review adversarial (2026-07-22): los tres hallazgos y sus fixes ---------

def write_description_backup(root, product_id=PID):
    """Backup de DESCRIPCIÓN (no de oferta). Es el estado normal tras
    mejorar-descripcion, y el que el bypass del comentario usaba como llave."""
    d = Path(root) / "clients/blunua/backups"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{product_id.split('/')[-1]}-desc.json"
    p.write_text(json.dumps({"productId": product_id,
        "fields": {"descriptionHtml": "old", "seo_title": "o", "seo_description": "o"},
        "ts": datetime.now().isoformat()}), encoding="utf-8")
    return p

def test_comment_between_name_and_paren_does_not_bypass_bxgy(tmp_path):
    """HALLAZGO 1 (HIGH). Un comentario entre el nombre de la mutación y su '('
    rompía el router de asuntos (regex `name\\s*\\(` sobre texto CRUDO) mientras el
    gate de allowlist (que borra comentarios) lo dejaba pasar. El regalo caía al
    camino de producto pidiendo SOLO un backup de descripción → todo el techo
    evadido. Fix: clasificar los asuntos desde `roots`, no desde el regex crudo."""
    policy(tmp_path, maxGiftPct=50, maxGetQty=1, minBuyGetRatio=2, giftableProducts=[])
    write_description_backup(tmp_path)   # NO hay backup de oferta, solo de descripción
    d_input = {
        "title": "x", "startsAt": "2026-07-20T00:00:00Z", "endsAt": "2026-10-18T00:00:00Z",
        "usesPerOrderLimit": "99",
        "customerBuys": {"value": {"quantity": "1"},
                         "items": {"products": {"productsToAdd": [PID]}}},
        "customerGets": {"value": {"discountOnQuantity": {"quantity": "10",
                                    "effect": {"percentage": 1.0}}},
                         "items": {"products": {"productsToAdd": [QID]}}}}
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($d: DiscountAutomaticBxgyInput!) { discountAutomaticBxgyCreate #x\n"
                 " (automaticBxgyDiscount: $d) { automaticDiscountNode { id } } }",
        # el señuelo {"id": ...} hace que _variables_product_keys coseche "id", que
        # es lo que el bypass necesitaba para pasar el chequeo de campos de producto.
        "variables": {"d": d_input, "decoy": {"id": PID}}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el comentario evadió el techo del regalo entero: {why}"

def test_backup_productId_must_match_buy_product(tmp_path):
    """HALLAZGO 2 (MED). El backup se buscaba por variables.productId sin
    compararlo con el producto REALMENTE comprado. Un backup de otro producto
    autorizaba el write. Fix: productId == buy_gid."""
    policy(tmp_path)
    write_deal_backup(tmp_path, product_id="gid://shopify/Product/999")  # backup de 999, no de P
    p = bxgy_create(buy_qty=2, get_qty=1, gift_pct=0.5, product_id="gid://shopify/Product/999")
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"un backup de otro producto autorizó el regalo sobre P: {why}"

def test_backup_productId_matching_buy_product_is_allowed(tmp_path):
    """Control de sobre-bloqueo: con productId == el producto comprado y su backup, pasa."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(bxgy_create(), tmp_path, time.time())
    assert d == "allow", why

def test_gid_with_trailing_space_is_rejected(tmp_path):
    """HALLAZGO 3 (LOW). 'gid P' vs 'gid P ' (espacio al final) se tomaba como
    cruzado y saltaba el ratio de mismo-producto. Fix: forma canónica del gid."""
    policy(tmp_path, allowCrossProductGift=True, giftableProducts=["gid://shopify/Product/1 "])
    write_deal_backup(tmp_path)
    p = bxgy_create(buy_qty=1, get_qty=1, buy_pid=PID, get_pid="gid://shopify/Product/1 ")
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"un gid con espacio evadió el ratio como falso cruzado: {why}"
