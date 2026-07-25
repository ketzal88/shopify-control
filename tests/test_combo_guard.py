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
