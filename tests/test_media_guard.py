"""Guard de la clase MEDIA (W4-3, spec 2026-07-24-imagenes-realce §5).

Adjuntar una foto REALZADA (de la foto real) a un producto existente es
`productCreateMedia` (solo IMAGE, un producto, backup, undo). El undo es
`productDeleteMedia` acotado a los media ids que la herramienta AGREGÓ (registro en
dos fases). Reusa los patrones del router W3 §7.0.1 y de `_covering_create_record`.
"""
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
MEDIA_ID = "gid://shopify/MediaImage/9"
OTHER_MEDIA = "gid://shopify/MediaImage/99"      # un id NO registrado (foto original)
IMG_URL = "https://cdn.example.com/realzada.jpg"


def _payload(query, variables=None):
    ti = {"query": query}
    if variables is not None:
        ti["variables"] = variables
    return {"tool_name": T_GQL, "tool_input": ti}


def write_media_policy(dest, slug="blunua", allow_media=True, max_images=6, window=72, **over):
    d = Path(dest) / "clients" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"allowMedia": allow_media, "maxImagesPerCall": max_images, "mediaRecordWindowHours": window}
    data.update(over)
    (d / "media-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d / "media-policy.json"


def write_media_record(dest, product_id=PID, slug="blunua", media_ids=None, age_hours=0):
    d = Path(dest) / "clients" / slug / "backups" / "media"
    d.mkdir(parents=True, exist_ok=True)
    tail = product_id.split("/")[-1]
    p = d / f"{tail}-20260724-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_hours * 3600).isoformat()
    rec = {"kind": "media", "productId": product_id, "ts": ts}
    if media_ids is not None:
        rec["mediaIds"] = media_ids
    p.write_text(json.dumps(rec), encoding="utf-8")
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(p, (old, old))
    return p


# --- Task 1: media-policy + _media_ceilings ---

def test_media_ceilings_present_and_valid():
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) == (6, 72)


def test_media_ceilings_none_when_disabled_or_missing_or_malformed():
    assert bg._media_ceilings({"allowMedia": False, "maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) is None
    assert bg._media_ceilings({"maxImagesPerCall": 6, "mediaRecordWindowHours": 72}) is None    # allowMedia ausente
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": 6}) is None               # falta window
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": "6", "mediaRecordWindowHours": 72}) is None  # str
    assert bg._media_ceilings({"allowMedia": True, "maxImagesPerCall": True, "mediaRecordWindowHours": 72}) is None  # bool


def test_load_media_policy_excludes_template():
    # con blunua Y _template presentes, el loader devuelve UNA política (no None)
    assert bg.load_media_policy(root) is not None


def test_blunua_media_policy_exists():
    pol = json.loads((REPO_ROOT / "clients" / "blunua" / "media-policy.json").read_text(encoding="utf-8"))
    assert pol.get("allowMedia") is True
    assert isinstance(pol.get("maxImagesPerCall"), int) and not isinstance(pol.get("maxImagesPerCall"), bool)
    assert isinstance(pol.get("mediaRecordWindowHours"), int) and not isinstance(pol.get("mediaRecordWindowHours"), bool)
