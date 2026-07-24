import sys, json, time, importlib.util
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_create_policy_exists_and_has_ceilings(tmp_path):
    # la política de blunua tiene las claves que el guard necesita
    pol = json.loads((REPO_ROOT / "clients" / "blunua" / "create-policy.json").read_text(encoding="utf-8"))
    for k in ("maxProductsPerBatch", "minPriceCents", "maxPriceCents", "allowPublish",
              "requireImage", "requireDescriptionMinWords", "createRecordWindowHours"):
        assert k in pol
