import json, time, os
from pathlib import Path
from datetime import datetime
import importlib.util

spec = importlib.util.spec_from_file_location("backup_guard", Path(__file__).parent.parent/".claude/hooks/backup_guard.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

def write_backup(root, product_id, fields, age_seconds=0):
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({"productId": product_id, "fields": fields, "ts": "x"}))
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

WRITE = {"tool_name": "shopify_product_update",
         "tool_input": {"productId": "gid://shopify/Product/1", "fields": {"body_html": "new"}}}

def test_non_shopify_tool_is_allowed(tmp_path):
    d, _ = bg.evaluate({"tool_name": "Read", "tool_input": {}}, tmp_path, time.time())
    assert d == "allow"

def test_write_without_backup_is_blocked(tmp_path):
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "block"

def test_write_with_covering_recent_backup_is_allowed(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"})
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "allow"

def test_backup_missing_a_field_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"})
    payload = {"tool_name": "shopify_product_update",
               "tool_input": {"productId": "gid://shopify/Product/1",
                              "fields": {"body_html": "new", "meta_title": "new"}}}
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block"

def test_stale_backup_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", "gid://shopify/Product/1", {"body_html": "old"}, age_seconds=100000)
    d, _ = bg.evaluate(WRITE, tmp_path, time.time())
    assert d == "block"
