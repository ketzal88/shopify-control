"""Tests del guard para el metafield `worker.trust` (Pack LatAm F2/F3, spec §4.2/§5).

`worker.trust` es la 3ª familia cosmética: ítems tipados de confianza (badge,
message, whatsapp). Estrena el **owner SHOP** en el guard (spec §5.3): trust puede
vivir en PRODUCT o SHOP; style/faq siguen product-only. Cubre: validación por tipo,
backup propio `kind:"trust"`, cruce de discriminador vs plata y vs otras familias,
el owner-scope por-key, y el ruteo en `evaluate()`.
"""
import json, time, importlib.util
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "backup_guard.py"
_spec = importlib.util.spec_from_file_location("backup_guard", SPEC)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

GID = "gid://shopify/Product/9"
SHOP = "gid://shopify/Shop/1"
POLICY = {"maxDiscountPct": 30, "maxDurationDays": 90, "maxTiers": 4,
          "requireEndsAt": True, "allowCollectionScope": False,
          "enabledStrategies": ["automatic"]}

VALID_TRUST = {"version": 1, "items": [
    {"type": "badge", "icon": "cuotas", "text": "3 cuotas sin interés"},
    {"type": "badge", "icon": "transferencia", "text": "10% off por transferencia"},
    {"type": "message", "text": "Envío gratis desde $80.000"}]}
WA_ITEM = {"type": "whatsapp", "phone": "5491122334455", "text": "Hola, tengo una consulta"}


def _ts(now):
    return guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")


def _write_backup(root, gid, ts_iso, kind, sub):
    tail = gid.split("/")[-1]
    d = root / "clients" / "blunua" / "backups" / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tail}-x.json").write_text(json.dumps(
        {"kind": kind, "productId": gid, "previous": None, "ts": ts_iso}),
        encoding="utf-8")


def _write_policy(root):
    d = root / "clients" / "blunua"
    d.mkdir(parents=True, exist_ok=True)
    (d / "deal-policy.json").write_text(json.dumps(POLICY), encoding="utf-8")


def _trust_payload(data, owner=GID):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": "trust", "type": "json", "value": json.dumps(data)}]}}


# --- cobertura + cruce de discriminador --------------------------------------

def test_covering_trust_backup_accepts_fresh(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    ok, why = guard._covering_cosmetic_backup("trust", tmp_path, GID, now)
    assert ok is True, why


def test_trust_backup_does_not_enable_deal(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    ok, _ = guard._covering_deal_backup(tmp_path, GID, now)
    assert ok is False


def test_trust_backup_does_not_enable_style(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    ok, _ = guard._covering_style_backup(tmp_path, GID, now)
    assert ok is False


def test_deal_backup_does_not_enable_trust(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "deal", "deals")
    ok, _ = guard._covering_cosmetic_backup("trust", tmp_path, GID, now)
    assert ok is False


# --- validación de forma por tipo --------------------------------------------

def test_trust_accepts_valid_on_product(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    ok, why = guard._check_cosmetic("trust", _trust_payload(VALID_TRUST), tmp_path, now)
    assert ok == "allow", why


def test_trust_accepts_valid_on_shop(tmp_path):
    # NUEVO owner-scope: trust puede vivir en SHOP.
    now = time.time()
    _write_backup(tmp_path, SHOP, _ts(now), "trust", "trust")
    ok, why = guard._check_cosmetic("trust", _trust_payload(VALID_TRUST, owner=SHOP), tmp_path, now)
    assert ok == "allow", why


def test_trust_accepts_whatsapp(tmp_path):
    now = time.time()
    _write_backup(tmp_path, SHOP, _ts(now), "trust", "trust")
    data = {"version": 1, "items": [WA_ITEM]}
    ok, why = guard._check_cosmetic("trust", _trust_payload(data, owner=SHOP), tmp_path, now)
    assert ok == "allow", why


def test_trust_accepts_empty_items_removal(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    ok, why = guard._check_cosmetic("trust", _trust_payload({"version": 1, "items": []}), tmp_path, now)
    assert ok == "allow", why


def test_trust_blocks_unknown_top_key(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [], "evil": 1}), tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_unknown_item_type(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [{"type": "popup", "text": "x"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_bad_badge_icon(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [{"type": "badge", "icon": "evil", "text": "x"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_badge_extra_key(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [
            {"type": "badge", "icon": "cuotas", "text": "x", "url": "http://evil"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_angle_text(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [{"type": "message", "text": "<script>"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_too_long_message(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [{"type": "message", "text": "x" * 81}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_bad_phone(tmp_path):
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": [
            {"type": "whatsapp", "phone": "+54 911 boom", "text": "hola"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_too_many_items(tmp_path):
    items = [{"type": "message", "text": f"m{i}"} for i in range(9)]
    ok, _ = guard._check_cosmetic(
        "trust", _trust_payload({"version": 1, "items": items}), tmp_path, time.time())
    assert ok == "block"


def test_trust_blocks_missing_backup(tmp_path):
    ok, _ = guard._check_cosmetic("trust", _trust_payload(VALID_TRUST), tmp_path, time.time())
    assert ok == "block"


# --- owner-scope es POR KEY: faq/style siguen product-only -------------------

def test_faq_still_blocks_shop_owner(tmp_path):
    now = time.time()
    _write_backup(tmp_path, SHOP, _ts(now), "faq", "faq")
    p = {"variables": {"m": [{"ownerId": SHOP, "namespace": "worker", "key": "faq",
         "type": "json", "value": json.dumps({"version": 1, "items": [{"q": "a", "a": "b"}]})}]}}
    ok, _ = guard._check_cosmetic("faq", p, tmp_path, now)
    assert ok == "block"


# --- integración evaluate() --------------------------------------------------

TRUST_MUT = ("mutation ($m:[MetafieldsSetInput!]!){metafieldsSet(metafields:$m)"
             "{metafields{id} userErrors{field message}}}")


def _epayload(query, variables):
    return {"tool_name": "mcp__claude_ai_Shopify__graphql_mutation",
            "tool_input": {"query": query, "variables": variables}}


def test_evaluate_trust_shop_allow_happy_path(tmp_path):
    now = time.time()
    _write_backup(tmp_path, SHOP, _ts(now), "trust", "trust")
    payload = _epayload(TRUST_MUT, {"m": [{"ownerId": SHOP, "namespace": "worker",
              "key": "trust", "type": "json", "value": json.dumps(VALID_TRUST)}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "allow", why


def test_evaluate_trust_backup_does_not_enable_deal(tmp_path):
    now = time.time()
    _write_policy(tmp_path)
    _write_backup(tmp_path, GID, _ts(now), "trust", "trust")
    deal_value = json.dumps({"version": 1, "type": "quantity_breaks",
        "tiers": [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}]})
    payload = _epayload(TRUST_MUT, {"m": [{"ownerId": GID, "namespace": "worker",
              "key": "deal", "type": "json", "value": deal_value}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "block", why
