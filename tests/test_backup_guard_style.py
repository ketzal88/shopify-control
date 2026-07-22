"""Tests del guard para el metafield de estilo `worker.style` (spec §9 + §9.1).

Cubren: la cobertura del backup de estilo (`kind:"style"` + ruta propia), el
CRUCE de discriminador (un backup de estilo no habilita un write de plata y
viceversa), la validación cosmética de `_check_style`, y el ruteo a nivel
`evaluate()`.
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


def _ts(now):
    return guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")


def _write_policy(root):
    d = root / "clients" / "blunua"
    d.mkdir(parents=True, exist_ok=True)
    (d / "deal-policy.json").write_text(json.dumps(POLICY), encoding="utf-8")


def _write_backup(root, gid, ts_iso, kind, sub):
    tail = gid.split("/")[-1]
    d = root / "clients" / "blunua" / "backups" / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tail}-x.json").write_text(json.dumps(
        {"kind": kind, "productId": gid, "previous": None, "ts": ts_iso}),
        encoding="utf-8")


def _style_payload(value_dict, owner=GID):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": "style", "type": "json", "value": json.dumps(value_dict)}]}}


# --- _covering_style_backup + cruce de discriminador (crítico) ---------------

def test_covering_style_backup_accepts_fresh_style_kind(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "style", "style")
    ok, why = guard._covering_style_backup(tmp_path, GID, now)
    assert ok is True, why


def test_style_backup_does_not_enable_deal_write(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "style", "style")
    ok, _ = guard._covering_deal_backup(tmp_path, GID, now)
    assert ok is False


def test_deal_backup_does_not_enable_style_write(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "deal", "deals")
    ok, _ = guard._covering_style_backup(tmp_path, GID, now)
    assert ok is False


# --- _check_style: validación cosmética cerrada ------------------------------

def test_style_accepts_valid(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "style", "style")
    ok, why = guard._check_style(
        _style_payload({"ink": "#4B4B4B", "label": "Llevá más y ahorrá"}), tmp_path, now)
    assert ok == "allow", why


def test_style_blocks_non_hex_color(tmp_path):
    ok, _ = guard._check_style(_style_payload({"ink": "red; }"}), tmp_path, time.time())
    assert ok == "block"


def test_style_blocks_unknown_key(tmp_path):
    ok, _ = guard._check_style(_style_payload({"evil": "#000000"}), tmp_path, time.time())
    assert ok == "block"


def test_style_blocks_angle_text(tmp_path):
    ok, _ = guard._check_style(_style_payload({"label": "<script>"}), tmp_path, time.time())
    assert ok == "block"


def test_style_blocks_long_text(tmp_path):
    ok, _ = guard._check_style(_style_payload({"label": "x" * 41}), tmp_path, time.time())
    assert ok == "block"


def test_style_blocks_missing_backup(tmp_path):
    ok, _ = guard._check_style(_style_payload({"ink": "#000000"}), tmp_path, time.time())
    assert ok == "block"


# --- Integración a nivel evaluate() (Step 10b del plan) ----------------------

STYLE_MUT = ("mutation ($m:[MetafieldsSetInput!]!){metafieldsSet(metafields:$m)"
             "{metafields{id} userErrors{field message}}}")


def _payload(query, variables):
    return {"tool_name": "mcp__claude_ai_Shopify__graphql_mutation",
            "tool_input": {"query": query, "variables": variables}}


def test_evaluate_style_allow_happy_path(tmp_path):
    now = time.time()
    _write_backup(tmp_path, GID, _ts(now), "style", "style")
    payload = _payload(STYLE_MUT, {"m": [{"ownerId": GID, "namespace": "worker",
              "key": "style", "type": "json", "value": json.dumps({"ink": "#000000"})}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "allow", why


def test_evaluate_style_backup_does_not_enable_deal_metafield(tmp_path):
    # Solo hay backup de estilo; se intenta escribir worker.deal -> block.
    now = time.time()
    _write_policy(tmp_path)
    _write_backup(tmp_path, GID, _ts(now), "style", "style")
    deal_value = json.dumps({"version": 1, "type": "quantity_breaks",
        "tiers": [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}]})
    payload = _payload(STYLE_MUT, {"m": [{"ownerId": GID, "namespace": "worker",
              "key": "deal", "type": "json", "value": deal_value}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "block", why
