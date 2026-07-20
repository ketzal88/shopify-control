import json
from pathlib import Path
import importlib.util

MOD = Path(__file__).parent.parent / ".claude/hooks/deal_policy.py"
spec = importlib.util.spec_from_file_location("deal_policy", MOD)
dp = importlib.util.module_from_spec(spec); spec.loader.exec_module(dp)

DEFAULTS = {"maxDiscountPct": 30, "maxDurationDays": 90, "maxTiers": 4,
            "requireEndsAt": True, "allowCollectionScope": False,
            "enabledStrategies": ["automatic"]}

def write_policy(root, slug="blunua", **over):
    d = Path(root)/"clients"/slug
    d.mkdir(parents=True, exist_ok=True)
    data = {**DEFAULTS, **over}
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
