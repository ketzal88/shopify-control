import json, time, os, subprocess, sys
from pathlib import Path
import importlib.util

GUARD = Path(__file__).parent.parent / ".claude/hooks/backup_guard.py"
spec = importlib.util.spec_from_file_location("backup_guard", GUARD)
bg = importlib.util.module_from_spec(spec); spec.loader.exec_module(bg)

PID = "gid://shopify/Product/1"
FULL_FIELDS = {"descriptionHtml": "old", "seo_title": "old", "seo_description": "old"}

# Nombres REALES que recibe el hook (formato MCP: mcp__server__tool):
T_UPDATE = "mcp__claude_ai_Shopify__update-product"
T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"
T_GET = "mcp__claude_ai_Shopify__get-product"
T_INVENTORY = "mcp__claude_ai_Shopify__set-inventory"
T_DISCOUNT = "mcp__claude_ai_Shopify__create-discount"
T_BULK_STATUS = "mcp__claude_ai_Shopify__bulk-update-product-status"

def write_backup(root, product_id=PID, fields=None, age_seconds=0):
    fields = FULL_FIELDS if fields is None else fields
    d = Path(root); d.mkdir(parents=True, exist_ok=True)
    p = d/f"{product_id.split('/')[-1]}-x.json"
    p.write_text(json.dumps({"productId": product_id, "fields": fields, "ts": "x"}), encoding="utf-8")
    if age_seconds:
        old = time.time() - age_seconds
        os.utime(p, (old, old))
    return p

UPDATE = {"tool_name": T_UPDATE, "tool_input": {"id": PID, "descriptionHtml": "new"}}
GQL_SEO = {"tool_name": T_GQL,
           "tool_input": {"query": 'mutation { productUpdate(input:{id:"gid://shopify/Product/1", seo:{title:"t",description:"d"}}){ product{id} userErrors{message} } }'}}


# --- camino feliz y bloqueo por backup -------------------------------------

def test_read_tool_is_allowed(tmp_path):
    d, _ = bg.evaluate({"tool_name": T_GET, "tool_input": {"id": PID}}, tmp_path, time.time())
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
    write_backup(tmp_path/"blunua/backups", fields={"descriptionHtml": "old"})
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_stale_backup_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups", age_seconds=100000)
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_non_dict_tool_input_on_write_is_blocked(tmp_path):
    d, _ = bg.evaluate({"tool_name": T_UPDATE, "tool_input": "oops"}, tmp_path, time.time())
    assert d == "block"

def test_display_name_form_also_matches(tmp_path):
    # El guard reconoce también el formato de display ("Shopify:update-product").
    write_backup(tmp_path/"blunua/backups")
    payload = {"tool_name": "Shopify:update-product", "tool_input": {"id": PID, "descriptionHtml": "new"}}
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "allow"


# --- ALCANCE DE CAMPOS: un backup válido NO habilita otros campos -----------
# Antes, un backup legítimo de descripción era una llave de 15 min para cambiar
# precio o status del mismo producto.

def test_update_product_with_status_is_blocked_even_with_backup(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    payload = {"tool_name": T_UPDATE, "tool_input": {"id": PID, "descriptionHtml": "new", "status": "DRAFT"}}
    d, why = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block" and "status" in why

def test_update_product_with_variant_price_is_blocked_even_with_backup(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    payload = {"tool_name": T_UPDATE,
               "tool_input": {"id": PID, "variants": [{"id": "x", "price": "50000"}]}}
    d, why = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block" and "variants" in why

def test_update_product_with_title_is_blocked_even_with_backup(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    payload = {"tool_name": T_UPDATE, "tool_input": {"id": PID, "title": "otro nombre"}}
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block"

def test_graphql_handle_change_is_blocked_even_with_backup(tmp_path):
    # handle rompe la URL del producto (404s). Nunca en v1.
    write_backup(tmp_path/"blunua/backups")
    q = 'mutation { productUpdate(product:{id:"gid://shopify/Product/1", handle:"nuevo"}){ product{id} } }'
    d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": q}}, tmp_path, time.time())
    assert d == "block" and "handle" in why

def test_graphql_seo_nested_title_is_not_confused_with_top_level_title(tmp_path):
    # seo:{title:...} es legítimo; no debe leerse como un cambio de título.
    write_backup(tmp_path/"blunua/backups")
    q = 'mutation { productUpdate(product:{id:"gid://shopify/Product/1", seo:{title:"t",description:"d"}}){ product{id} } }'
    d, _ = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": q}}, tmp_path, time.time())
    assert d == "allow"


# --- BYPASS por variables ---------------------------------------------------
# La forma idiomática de GraphQL pasa el id por variables; el guard viejo solo
# miraba el string del query y por eso no veía ni el gid ni los campos.

def test_graphql_variables_bypass_is_blocked(tmp_path):
    q = 'mutation ($product: ProductUpdateInput!) { productUpdate(product:$product){ product{id} } }'
    payload = {"tool_name": T_GQL, "tool_input": {
        "query": q,
        "variables": {"product": {"id": PID, "handle": "nuevo-handle", "status": "DRAFT"}}}}
    d, why = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block" and ("handle" in why or "status" in why)

def test_graphql_variables_legit_seo_needs_backup(tmp_path):
    q = 'mutation ($product: ProductUpdateInput!) { productUpdate(product:$product){ product{id} } }'
    payload = {"tool_name": T_GQL, "tool_input": {
        "query": q, "variables": {"product": {"id": PID, "seo": {"title": "t", "description": "d"}}}}}
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "block"          # sin backup
    write_backup(tmp_path/"blunua/backups")
    d, _ = bg.evaluate(payload, tmp_path, time.time())
    assert d == "allow"          # con backup


# --- MUTACIONES Y TOOLS PROHIBIDOS -----------------------------------------

def test_forbidden_mutations_are_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups")   # ni con backup
    for mutation in ["productDelete", "productVariantsBulkUpdate", "productChangeStatus",
                     "inventorySetQuantities"]:
        q = f'mutation {{ {mutation}(input:{{id:"gid://shopify/Product/1"}}){{ userErrors{{message}} }} }}'
        d, _ = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": q}}, tmp_path, time.time())
        assert d == "block", f"{mutation} debería bloquearse"

def test_forbidden_write_tools_are_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups")   # ni con backup
    for tool in [T_INVENTORY, T_DISCOUNT, T_BULK_STATUS]:
        d, _ = bg.evaluate({"tool_name": tool, "tool_input": {"id": PID}}, tmp_path, time.time())
        assert d == "block", f"{tool} debería bloquearse en v1"


# --- CALIDAD DEL BACKUP -----------------------------------------------------
# Un backup de placeholders satisfacía el guard, y después el "undo" restauraba
# vacío en vez de restaurar el valor original.

def test_backup_with_all_empty_values_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups",
                 fields={"descriptionHtml": "", "seo_title": "", "seo_description": ""})
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_backup_with_null_values_is_blocked(tmp_path):
    write_backup(tmp_path/"blunua/backups",
                 fields={"descriptionHtml": None, "seo_title": None, "seo_description": None})
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "block"

def test_backup_with_seo_vacio_pero_descripcion_real_es_valido(tmp_path):
    # Un producto puede tener SEO vacío de verdad; eso no invalida el backup.
    write_backup(tmp_path/"blunua/backups",
                 fields={"descriptionHtml": "texto viejo real", "seo_title": "", "seo_description": ""})
    d, _ = bg.evaluate(UPDATE, tmp_path, time.time())
    assert d == "allow"


# --- CONTRATO DE EXIT CODES (main) -----------------------------------------
# Claude Code bloquea SOLO con exit 2. Este contrato no estaba testeado, y es
# exactamente el bug que ya ocurrió con secret-scan (ver test_secret_scan.py).

def _run_main(payload):
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                          capture_output=True, text=True)

def test_main_bloquea_con_exit_2(tmp_path):
    payload = dict(UPDATE, cwd=str(tmp_path))      # sin backup
    r = _run_main(payload)
    assert r.returncode == 2, f"debe ser 2 (block), fue {r.returncode}: {r.stderr}"
    assert "backup" in r.stderr.lower()

def test_main_permite_con_exit_0(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    r = _run_main(dict(UPDATE, cwd=str(tmp_path)))
    assert r.returncode == 0, r.stderr

def test_main_bloquea_write_fuera_de_alcance_con_exit_2(tmp_path):
    write_backup(tmp_path/"blunua/backups")
    payload = {"tool_name": T_UPDATE, "tool_input": {"id": PID, "status": "DRAFT"}, "cwd": str(tmp_path)}
    r = _run_main(payload)
    assert r.returncode == 2, f"debe ser 2, fue {r.returncode}: {r.stderr}"

def test_main_payload_ilegible_no_bloquea_todo(tmp_path):
    r = subprocess.run([sys.executable, str(GUARD)], input="no soy json",
                       capture_output=True, text=True)
    assert r.returncode == 0
