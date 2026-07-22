"""Tests del guard para el metafield `worker.faq` (Pack LatAm F1, spec §4.1/§5).

`worker.faq` es la 2ª familia cosmética. Estrena el registro `COSMETIC_METAFIELDS`:
la validación se hace por `_check_cosmetic(key, ...)` y la cobertura del backup por
`_covering_cosmetic_backup(key, ...)`, generalizando lo que `worker.style` hacía
bespoke. Cubre: validación de forma (Q/A cerrada), backup propio `kind:"faq"`, el
CRUCE de discriminador en las 4 direcciones (faq↔style↔deal), y el ruteo en
`evaluate()`. Product-scope (owner SHOP entra en F2).
"""
import json, time, importlib.util
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "backup_guard.py"
_spec = importlib.util.spec_from_file_location("backup_guard", SPEC)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

GID = "gid://shopify/Product/9"
POLICY = {"maxDiscountPct": 30, "maxDurationDays": 90, "maxTiers": 4,
          "requireEndsAt": True, "allowCollectionScope": False,
          "enabledStrategies": ["automatic"]}

VALID_FAQ = {"version": 1, "items": [
    {"q": "¿El anillo es ajustable?", "a": "Sí, con ajuste gratis en tu primer pedido."},
    {"q": "¿Cuánto tarda el envío?", "a": "Entre 3 y 5 días hábiles a todo el país."}]}


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


def _faq_payload(data, owner=GID):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": "faq", "type": "json", "value": json.dumps(data)}]}}


# --- _covering_cosmetic_backup + cruce de discriminador (crítico) -------------

def test_covering_faq_backup_accepts_fresh(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, why = guard._covering_cosmetic_backup("faq", tmp_path, GID, now)
    assert ok is True, why


def test_faq_backup_does_not_enable_deal(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, _ = guard._covering_deal_backup(tmp_path, GID, now)
    assert ok is False


def test_faq_backup_does_not_enable_style(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, _ = guard._covering_style_backup(tmp_path, GID, now)
    assert ok is False


def test_deal_backup_does_not_enable_faq(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "deal", "deals")
    ok, _ = guard._covering_cosmetic_backup("faq", tmp_path, GID, now)
    assert ok is False


# --- _check_cosmetic('faq', ...): validación de forma cerrada -----------------

def test_faq_accepts_valid(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, why = guard._check_cosmetic("faq", _faq_payload(VALID_FAQ), tmp_path, now)
    assert ok == "allow", why


def test_faq_blocks_unknown_top_key(tmp_path):
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": [{"q": "a", "a": "b"}], "evil": 1}),
        tmp_path, time.time())
    assert ok == "block"


def test_faq_accepts_empty_items_removal(tmp_path):
    # "Sacar la FAQ" = escribir items:[] (el widget deja de mostrarse), espejo de
    # "sacar el look" = {} en estilo. Es un write válido, con su backup.
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, why = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": []}), tmp_path, now)
    assert ok == "allow", why


def test_faq_blocks_item_missing_answer(tmp_path):
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": [{"q": "hola"}]}), tmp_path, time.time())
    assert ok == "block"


def test_faq_blocks_angle_text(tmp_path):
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": [{"q": "<script>", "a": "x"}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_faq_blocks_too_long_answer(tmp_path):
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": [{"q": "q", "a": "x" * 601}]}),
        tmp_path, time.time())
    assert ok == "block"


def test_faq_blocks_too_many_items(tmp_path):
    items = [{"q": f"q{i}", "a": "a"} for i in range(13)]
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload({"version": 1, "items": items}), tmp_path, time.time())
    assert ok == "block"


def test_faq_blocks_missing_backup(tmp_path):
    ok, _ = guard._check_cosmetic("faq", _faq_payload(VALID_FAQ), tmp_path, time.time())
    assert ok == "block"


def test_faq_blocks_wrong_namespace(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    p = {"variables": {"m": [{"ownerId": GID, "namespace": "evil", "key": "faq",
         "type": "json", "value": json.dumps(VALID_FAQ)}]}}
    ok, _ = guard._check_cosmetic("faq", p, tmp_path, now)
    assert ok == "block"


def test_faq_blocks_non_product_owner(tmp_path):
    # F1: faq es product-scope. Un owner de Shop bloquea (owner SHOP entra en F2).
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    ok, _ = guard._check_cosmetic(
        "faq", _faq_payload(VALID_FAQ, owner="gid://shopify/Shop/1"), tmp_path, now)
    assert ok == "block"


# --- Integración a nivel evaluate() ------------------------------------------

FAQ_MUT = ("mutation ($m:[MetafieldsSetInput!]!){metafieldsSet(metafields:$m)"
           "{metafields{id} userErrors{field message}}}")


def _epayload(query, variables):
    return {"tool_name": "mcp__claude_ai_Shopify__graphql_mutation",
            "tool_input": {"query": query, "variables": variables}}


def test_evaluate_faq_allow_happy_path(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    payload = _epayload(FAQ_MUT, {"m": [{"ownerId": GID, "namespace": "worker",
              "key": "faq", "type": "json", "value": json.dumps(VALID_FAQ)}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "allow", why


def test_evaluate_faq_backup_does_not_enable_deal(tmp_path):
    # Solo hay backup de faq; se intenta escribir worker.deal -> block.
    now = time.time()
    _write_policy(tmp_path)
    _write_backup(tmp_path, GID, _ts(now), "faq", "faq")
    deal_value = json.dumps({"version": 1, "type": "quantity_breaks",
        "tiers": [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}]})
    payload = _epayload(FAQ_MUT, {"m": [{"ownerId": GID, "namespace": "worker",
              "key": "deal", "type": "json", "value": deal_value}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "block", why
