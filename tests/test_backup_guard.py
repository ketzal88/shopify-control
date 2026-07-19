import json, time, os
from pathlib import Path
import importlib.util

spec = importlib.util.spec_from_file_location("backup_guard", Path(__file__).parent.parent/".claude/hooks/backup_guard.py")
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

PID = "gid://shopify/Product/1"
FULL_FIELDS = {"descriptionHtml": "old", "seo_title": "old", "seo_description": "old"}

def write_backup(root, product_id=PID, fields=None, age_seconds=0):
    fields = FULL_FIELDS if fields is None else fields
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({"productId": product_id, "fields": fields, "ts": "x"}), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

# Write real: la descripción va por update-product.
UPDATE = {"tool_name": "Shopify:update-product",
          "tool_input": {"id": PID, "descriptionHtml": "new"}}
# Write real: el SEO va por graphql_mutation (productUpdate { seo }).
GQL_SEO = {"tool_name": "Shopify:graphql_mutation",
           "tool_input": {"query": 'mutation { productUpdate(input:{id:"gid://shopify/Product/1", seo:{title:"t",description:"d"}}){ product{id} userErrors{message} } }'}}

def test_read_tool_is_allowed(tmp_path):
    d, _ = bg.evaluate({"tool_name": "Shopify:get-product", "tool_input": {"id": PID}}, tmp_path, time.time())
    assert d == "allow"

def test_update_product_without_backup_is_blocked(tmp_path):
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_update_product_with_covering_backup_is_allowed(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "allow"

def test_graphql_seo_mutation_without_backup_is_blocked(tmp_path):
    d, _ = bg.evaluate(GQL_SEO, tmp_path, time.time())
    assert d == "block"

def test_graphql_seo_mutation_with_covering_backup_is_allowed(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    d, _ = bg.evaluate(GQL_SEO, tmp_path, time.time())
    assert d == "allow"

def test_backup_missing_seo_fields_is_blocked(tmp_path):
    # Un backup que solo respaldó la descripción no cubre el set completo.
    write_backup(tmp_path/"blunua/backups", fields={"descriptionHtml": "old"})
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_stale_backup_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", age_seconds=100000)
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_non_dict_tool_input_on_write_is_blocked(tmp_path):
    d, _ = bg.evaluate({"tool_name": "Shopify:update-product", "tool_input": "oops"}, tmp_path, time.time())
    assert d == "block"

def test_unguarded_shopify_write_is_allowed(tmp_path):
    # set-inventory está fuera del flujo del skill: el hook v1 no lo vigila.
    d, _ = bg.evaluate({"tool_name": "Shopify:set-inventory", "tool_input": {"id": PID, "available": 5}}, tmp_path, time.time())
    assert d == "allow"
