"""Tests del guard para `worker.countdown` y `worker.freeship` (widgets nuevos).

Ambos son familias cosméticas del registro `COSMETIC_METAFIELDS` (sin techo, backup
propio `kind`, aislamiento por ruta+kind). countdown: fecha de fin real (honesto, no
resetea). freeship: monto umbral en centavos. Los dos aceptan owner PRODUCT o SHOP.
"""
import json, time, importlib.util
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "backup_guard.py"
_spec = importlib.util.spec_from_file_location("backup_guard", SPEC)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

GID = "gid://shopify/Product/9"
SHOP = "gid://shopify/Shop/1"


def _ts(now):
    return guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")


def _write_backup(root, gid, ts_iso, kind, sub):
    tail = gid.split("/")[-1]
    d = root / "clients" / "blunua" / "backups" / sub
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tail}-x.json").write_text(json.dumps(
        {"kind": kind, "productId": gid, "previous": None, "ts": ts_iso}), encoding="utf-8")


def _payload(key, data, owner=GID):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": key, "type": "json", "value": json.dumps(data)}]}}


# =========================== worker.countdown ===============================

VALID_COUNT = {"version": 1, "endsAt": "2026-12-31T00:00:00Z", "label": "La oferta termina en"}


def test_countdown_accepts_valid_on_product(tmp_path):
    now = time.time(); _write_backup(tmp_path, GID, _ts(now), "countdown", "countdown")
    ok, why = guard._check_cosmetic("countdown", _payload("countdown", VALID_COUNT), tmp_path, now)
    assert ok == "allow", why


def test_countdown_accepts_valid_on_shop(tmp_path):
    now = time.time(); _write_backup(tmp_path, SHOP, _ts(now), "countdown", "countdown")
    ok, why = guard._check_cosmetic("countdown", _payload("countdown", VALID_COUNT, owner=SHOP), tmp_path, now)
    assert ok == "allow", why


def test_countdown_blocks_bad_date(tmp_path):
    ok, _ = guard._check_cosmetic("countdown", _payload("countdown",
        {"version": 1, "endsAt": "no-soy-fecha"}), tmp_path, time.time())
    assert ok == "block"


def test_countdown_blocks_missing_date(tmp_path):
    ok, _ = guard._check_cosmetic("countdown", _payload("countdown",
        {"version": 1, "label": "x"}), tmp_path, time.time())
    assert ok == "block"


def test_countdown_blocks_unknown_key(tmp_path):
    ok, _ = guard._check_cosmetic("countdown", _payload("countdown",
        {"version": 1, "endsAt": "2026-12-31T00:00:00Z", "evil": 1}), tmp_path, time.time())
    assert ok == "block"


def test_countdown_blocks_angle_text(tmp_path):
    ok, _ = guard._check_cosmetic("countdown", _payload("countdown",
        {"version": 1, "endsAt": "2026-12-31T00:00:00Z", "label": "<b>x</b>"}), tmp_path, time.time())
    assert ok == "block"


def test_countdown_blocks_missing_backup(tmp_path):
    ok, _ = guard._check_cosmetic("countdown", _payload("countdown", VALID_COUNT), tmp_path, time.time())
    assert ok == "block"


def test_countdown_backup_does_not_enable_deal(tmp_path):
    now = time.time(); _write_backup(tmp_path, GID, _ts(now), "countdown", "countdown")
    ok, _ = guard._covering_deal_backup(tmp_path, GID, now)
    assert ok is False


# =========================== worker.freeship ================================

VALID_SHIP = {"version": 1, "threshold": 8000000, "label": "Te faltan {falta} para el envío gratis"}


def test_freeship_accepts_valid_on_shop(tmp_path):
    now = time.time(); _write_backup(tmp_path, SHOP, _ts(now), "freeship", "freeship")
    ok, why = guard._check_cosmetic("freeship", _payload("freeship", VALID_SHIP, owner=SHOP), tmp_path, now)
    assert ok == "allow", why


def test_freeship_blocks_zero_threshold(tmp_path):
    ok, _ = guard._check_cosmetic("freeship", _payload("freeship",
        {"version": 1, "threshold": 0}, owner=SHOP), tmp_path, time.time())
    assert ok == "block"


def test_freeship_blocks_non_int_threshold(tmp_path):
    ok, _ = guard._check_cosmetic("freeship", _payload("freeship",
        {"version": 1, "threshold": "80000"}, owner=SHOP), tmp_path, time.time())
    assert ok == "block"


def test_freeship_blocks_unknown_key(tmp_path):
    ok, _ = guard._check_cosmetic("freeship", _payload("freeship",
        {"version": 1, "threshold": 8000000, "evil": 1}, owner=SHOP), tmp_path, time.time())
    assert ok == "block"


def test_freeship_blocks_angle_text(tmp_path):
    ok, _ = guard._check_cosmetic("freeship", _payload("freeship",
        {"version": 1, "threshold": 8000000, "successText": "<x>"}, owner=SHOP), tmp_path, time.time())
    assert ok == "block"


def test_freeship_blocks_missing_backup(tmp_path):
    ok, _ = guard._check_cosmetic("freeship", _payload("freeship", VALID_SHIP, owner=SHOP), tmp_path, time.time())
    assert ok == "block"


def test_freeship_backup_does_not_enable_style(tmp_path):
    now = time.time(); _write_backup(tmp_path, SHOP, _ts(now), "freeship", "freeship")
    ok, _ = guard._covering_style_backup(tmp_path, SHOP, now)
    assert ok is False


# =========================== evaluate() routing =============================

MUT = ("mutation ($m:[MetafieldsSetInput!]!){metafieldsSet(metafields:$m)"
       "{metafields{id} userErrors{field message}}}")


def _epayload(variables):
    return {"tool_name": "mcp__claude_ai_Shopify__graphql_mutation",
            "tool_input": {"query": MUT, "variables": variables}}


def test_evaluate_countdown_allow(tmp_path):
    now = time.time(); _write_backup(tmp_path, GID, _ts(now), "countdown", "countdown")
    payload = _epayload({"m": [{"ownerId": GID, "namespace": "worker", "key": "countdown",
              "type": "json", "value": json.dumps(VALID_COUNT)}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "allow", why


def test_evaluate_freeship_allow(tmp_path):
    now = time.time(); _write_backup(tmp_path, SHOP, _ts(now), "freeship", "freeship")
    payload = _epayload({"m": [{"ownerId": SHOP, "namespace": "worker", "key": "freeship",
              "type": "json", "value": json.dumps(VALID_SHIP)}]})
    decision, why = guard.evaluate(payload, tmp_path, now)
    assert decision == "allow", why
