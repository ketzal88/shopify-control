"""Guard de la caja COMBO (W4-1, spec 2026-07-24-combos-como-write §4).

El combo reusa la clase BXGY (`discountAutomaticBxgyCreate` + `worker.deal`), pero
con techo/scope PROPIOS: `_check_bxgy` acepta el discount si pasa la caja regalo
(intacta) O la caja combo (nueva, estricta-o-igual salvo el giftable relajado).
Cada caja se evalúa COMPLETA por sí sola (nunca se mezclan dimensiones).
"""
import json, time, os
from datetime import datetime
from pathlib import Path
import importlib.util

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"
PID = "gid://shopify/Product/1"      # producto comprado (A)
QID = "gid://shopify/Product/2"      # producto del combo (B), NO giftable

COMBO_KEYS = dict(allowCombo=True, maxComboPct=25, maxComboGetQty=2)


def write_deal_backup(root, product_id=PID):
    d = Path(root) / "clients/blunua/backups/deals"
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"{product_id.split('/')[-1]}-20260724-120000.json"
    p.write_text(json.dumps({"kind": "deal", "productId": product_id, "previous": None,
                             "ts": datetime.now().isoformat()}), encoding="utf-8")
    return p


def policy(tmp_path, **over):
    from tests.test_deal_policy import write_policy
    return write_policy(tmp_path, **over)


# --- Task 1: _combo_ceilings + claves opcionales en deal-policy ---

def test_combo_ceilings_present_and_valid():
    pol = {"allowCombo": True, "maxComboPct": 25, "maxComboGetQty": 2}
    assert bg._combo_ceilings(pol) == (25, 2)


def test_combo_ceilings_none_when_disabled_or_missing_or_malformed():
    assert bg._combo_ceilings({"allowCombo": False, "maxComboPct": 25, "maxComboGetQty": 2}) is None
    assert bg._combo_ceilings({"maxComboPct": 25, "maxComboGetQty": 2}) is None   # allowCombo ausente
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": 25}) is None    # falta getqty
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": "25", "maxComboGetQty": 2}) is None  # str
    assert bg._combo_ceilings({"allowCombo": True, "maxComboPct": True, "maxComboGetQty": 2}) is None  # bool no es int


def test_existing_deal_policy_still_loads():
    # las claves nuevas son OPCIONALES: deal-policy.json sigue cargando (no en REQUIRED_KEYS)
    root = Path(__file__).resolve().parents[1]
    dp_spec = importlib.util.spec_from_file_location("deal_policy", HOOKS / "deal_policy.py")
    dp = importlib.util.module_from_spec(dp_spec); dp_spec.loader.exec_module(dp)
    assert dp.load_policy(str(root)) is not None


def test_blunua_deal_policy_has_combo_keys():
    root = Path(__file__).resolve().parents[1]
    pol = json.loads((root / "clients" / "blunua" / "deal-policy.json").read_text(encoding="utf-8"))
    assert pol.get("allowCombo") is True
    assert isinstance(pol.get("maxComboPct"), int) and not isinstance(pol.get("maxComboPct"), bool)
    assert isinstance(pol.get("maxComboGetQty"), int) and not isinstance(pol.get("maxComboGetQty"), bool)


# --- Task 2: caja combo en _check_bxgy (el OR) ---

def combo_create(pct=0.20, buy_qty=1, get_qty=1, uses="1", buy_pid=PID, get_pid=QID,
                 ends="2026-10-18T00:00:00Z", starts="2026-07-20T00:00:00Z",
                 product_id=None, gets_value=None, buys_items=None, gets_items=None):
    """Un BXGY COMBO: por default cruzado, comprá 1 A → llevate 1 B al 20% off."""
    product_id = product_id if product_id is not None else buy_pid
    buys_items = buys_items if buys_items is not None else {"products": {"productsToAdd": [buy_pid]}}
    gets_items = gets_items if gets_items is not None else {"products": {"productsToAdd": [get_pid]}}
    gets_value = gets_value if gets_value is not None else {
        "discountOnQuantity": {"quantity": str(get_qty), "effect": {"percentage": pct}}}
    d = {"title": "shopify-control · Combo · test",
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


def test_combo_cross_to_non_giftable_allowed(tmp_path):
    # 20% cruzado a un NO-giftable (QID no está en giftableProducts), get_qty 1 → allow
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(), tmp_path, time.time())
    assert d == "allow", why


def test_combo_blocks_over_maxcombopct(tmp_path):
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(pct=0.30), tmp_path, time.time())      # 30% > 25
    assert d == "block", why


def test_combo_blocks_free(tmp_path):
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(pct=1.0), tmp_path, time.time())       # 100% no es combo
    assert d == "block", why


def test_combo_blocks_when_allowcombo_false(tmp_path):
    policy(tmp_path, allowCombo=False, maxComboPct=25, maxComboGetQty=2); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_get_qty_over_cap(tmp_path):
    # el hueco del OR: "comprá 1, llevate 1000 al 25%" → block por maxComboGetQty
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(pct=0.25, get_qty=1000), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_uses_per_order_not_one(tmp_path):
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(uses="5"), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_buy_qty_zero(tmp_path):
    # "llevate B sin comprar nada" = cupón → block
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(buy_qty=0), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_buy_collection(tmp_path):
    # "comprá cualquier cosa, llevate B" → block
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(buys_items={"collections": {"add": ["gid://shopify/Collection/9"]}}),
                         tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_buy_all(tmp_path):
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(buys_items={"all": True}), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_without_backup(tmp_path):
    # la caja combo tiene SU PROPIO chequeo de backup
    policy(tmp_path, **COMBO_KEYS)   # sin write_deal_backup
    d, why = bg.evaluate(combo_create(), tmp_path, time.time())
    assert d == "block", why


def test_combo_blocks_productid_mismatch(tmp_path):
    # productId != buy_gid → block (la caja combo hace su propio check, no se apoya en el regalo)
    policy(tmp_path, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(product_id=QID), tmp_path, time.time())  # buy=PID, productId=QID
    assert d == "block", why


def test_gift_box_still_intact(tmp_path):
    # regalo gratis a un giftable sigue allow (con combo encendido al lado)
    policy(tmp_path, giftableProducts=[QID], maxGiftPct=100, maxGetQty=1, **COMBO_KEYS)
    write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(pct=1.0, get_pid=QID, get_qty=1, buy_qty=1), tmp_path, time.time())
    assert d == "allow", why
    # y un cruzado NO-giftable al 100% sigue bloqueado (falla las dos cajas)
    policy(tmp_path, giftableProducts=[], maxGiftPct=100, **COMBO_KEYS)
    d2, why2 = bg.evaluate(combo_create(pct=1.0, get_pid=QID), tmp_path, time.time())
    assert d2 == "block", why2


def test_no_mix_and_match(tmp_path):
    # pct 100 + no-giftable: NO puede tomar "no-giftable OK" del combo y "pct<=maxGiftPct(100)"
    # del regalo. Cada caja se evalúa completa → block.
    policy(tmp_path, giftableProducts=[], maxGiftPct=100, **COMBO_KEYS); write_deal_backup(tmp_path)
    d, why = bg.evaluate(combo_create(pct=1.0, get_pid=QID), tmp_path, time.time())
    assert d == "block", why
