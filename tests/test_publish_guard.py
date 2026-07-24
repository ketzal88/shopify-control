import sys, os, json, time, importlib.util
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

REPO_ROOT = Path(__file__).resolve().parents[1]
root = str(REPO_ROOT)
now = time.time()

T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"
PID = "gid://shopify/Product/1"
PUB_ONLINE = "gid://shopify/Publication/1"      # el canal permitido (Online Store)
PUB_EVIL = "gid://shopify/Publication/999"       # un canal fuera de la allowlist


def _payload(query, variables=None):
    ti = {"query": query}
    if variables is not None:
        ti["variables"] = variables
    return {"tool_name": T_GQL, "tool_input": ti}


def write_publish_policy(dest, slug="blunua", allowed=None, allow_publish=True, **over):
    """create-policy con el techo de F2 + allowedPublicationIds (F3). Por defecto
    trae el Online Store en la allowlist y allowPublish=true (camino feliz)."""
    d = Path(dest) / "clients" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"maxProductsPerBatch": 50, "minPriceCents": 100, "maxPriceCents": 100000000,
            "allowPublish": allow_publish, "requireImage": True,
            "requireDescriptionMinWords": 40, "createRecordWindowHours": 72,
            "allowedPublicationIds": [PUB_ONLINE] if allowed is None else allowed}
    data.update(over)
    (d / "create-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d / "create-policy.json"


def _write_record(dest, kind, product_id=PID, slug="blunua", age_hours=0):
    d = Path(dest) / "clients" / slug / "backups" / kind
    d.mkdir(parents=True, exist_ok=True)
    tail = product_id.split("/")[-1]
    p = d / f"{tail}-20260724-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_hours * 3600).isoformat()
    p.write_text(json.dumps({"kind": kind, "productId": product_id, "ts": ts}), encoding="utf-8")
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(p, (old, old))
    return p


def write_create_record(dest, product_id=PID, slug="blunua", age_hours=0):
    return _write_record(dest, "create", product_id, slug, age_hours)


def write_publish_record(dest, product_id=PID, slug="blunua", age_hours=0):
    return _write_record(dest, "publish", product_id, slug, age_hours)


# --- Task 1: create-policy gana allowedPublicationIds ---

def test_create_policy_has_allowed_publication_ids():
    pol = json.loads((REPO_ROOT / "clients" / "blunua" / "create-policy.json").read_text(encoding="utf-8"))
    assert isinstance(pol.get("allowedPublicationIds"), list)
