import json
from pathlib import Path
import importlib.util

MOD = Path(__file__).parent.parent / ".claude/hooks/deal_policy.py"
spec = importlib.util.spec_from_file_location("deal_policy", MOD)
dp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dp)

# Claves de escalones (las requeridas por load_policy). Se deja SOLO estas a
# propósito: hay un test que escribe un cliente con estas y sin las de regalo,
# para verificar que un cliente sin techo de regalos no puede crear regalos.
DEFAULTS = {"maxDiscountPct": 30, "maxDurationDays": 90, "maxTiers": 4,
            "requireEndsAt": True, "allowCollectionScope": False,
            "enabledStrategies": ["automatic"]}

# Claves del regalo (BXGY). Opcionales en la política; si faltan, el guard falla
# cerrado (no se crean regalos). write_policy las incluye para que el camino feliz
# del regalo tenga un techo con el que trabajar.
GIFT_DEFAULTS = {"maxGiftPct": 100, "maxGetQty": 1, "minBuyGetRatio": 2,
                 "allowCrossProductGift": True, "giftableProducts": []}

def write_policy(root, slug="blunua", **over):
    d = Path(root)/"clients"/slug
    d.mkdir(parents=True, exist_ok=True)
    data = {**DEFAULTS, **GIFT_DEFAULTS, **over}
    (d/"deal-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d/"deal-policy.json"

def test_loads_the_only_policy_in_the_repo(tmp_path):
    write_policy(tmp_path)
    pol = dp.load_policy(tmp_path)
    assert pol["maxDiscountPct"] == 30

def test_missing_policy_returns_none(tmp_path):
    assert dp.load_policy(tmp_path) is None

def test_two_clients_is_ambiguous_and_returns_none(tmp_path):
    write_policy(tmp_path, slug="blunua")
    write_policy(tmp_path, slug="otra")
    # Con 2+ clientes el guard no puede saber cuál aplica (spec §9.7).
    assert dp.load_policy(tmp_path) is None

def test_template_does_not_count_as_a_client(tmp_path):
    """`_template/` es el scaffold del próximo cliente, no un cliente.
    Si contara, un repo con blunua + template sería 'ambiguo' y bloquearía todo."""
    write_policy(tmp_path, slug="blunua")
    write_policy(tmp_path, slug="_template")
    assert dp.load_policy(tmp_path) is not None
