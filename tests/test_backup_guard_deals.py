import json, time, os
from datetime import datetime
from pathlib import Path
import importlib.util

GUARD = Path(__file__).parent.parent / ".claude/hooks/backup_guard.py"
spec = importlib.util.spec_from_file_location("backup_guard", GUARD)
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

PID = "gid://shopify/Product/1"

def write_deal_backup(root, product_id=PID, kind="deal", age_seconds=0, previous=None):
    d = Path(root)/"clients/blunua/backups/deals"
    d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-20260719-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_seconds).isoformat()
    p.write_text(json.dumps({"kind": kind, "productId": product_id,
                             "previous": previous, "ts": ts}), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

def write_description_backup(root, product_id=PID):
    """El backup del OTRO tipo. No debe habilitar un write de deal."""
    d = Path(root)/"clients/blunua/backups"
    d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({
        "productId": product_id,
        "fields": {"descriptionHtml": "old", "seo_title": "o", "seo_description": "o"},
        "ts": datetime.now().isoformat()}), encoding="utf-8")
    return p


def test_fresh_deal_backup_is_accepted(tmp_path):
    write_deal_backup(tmp_path)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is True

def test_deal_backup_without_kind_is_rejected(tmp_path):
    write_deal_backup(tmp_path, kind="otra-cosa")
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_stale_deal_backup_is_rejected(tmp_path):
    write_deal_backup(tmp_path, age_seconds=100000)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_description_backup_does_not_enable_a_deal_write(tmp_path):
    write_description_backup(tmp_path)
    assert bg._covering_deal_backup(tmp_path, PID, time.time())[0] is False

def test_deal_backup_does_not_enable_a_description_write(tmp_path):
    """El glob de descripciones exige el archivo directo bajo backups/,
    y el de deals vive un nivel más abajo. Cruce cerrado en las dos direcciones."""
    write_deal_backup(tmp_path)
    ok, _ = bg._covering_backup(tmp_path, PID, time.time())
    assert ok is False
