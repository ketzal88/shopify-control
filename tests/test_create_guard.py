import sys, json, time, importlib.util
from datetime import datetime
from pathlib import Path

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
_spec = importlib.util.spec_from_file_location("backup_guard", HOOKS / "backup_guard.py")
bg = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(bg)

REPO_ROOT = Path(__file__).resolve().parents[1]

# El repo root real: load_create_policy encuentra SOLO blunua (excluye _template),
# así que estos tests corren contra el techo real de create-policy.json de blunua.
root = str(REPO_ROOT)
now = time.time()

T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"


def _payload(query, variables=None):
    ti = {"query": query}
    if variables is not None:
        ti["variables"] = variables
    return {"tool_name": T_GQL, "tool_input": ti}


def _create_ti(product):
    """tool_input de un productSet cuyo input viaja por `variables` (patrón F2)."""
    return {"query": "mutation($p: ProductSetInput!){ productSet(input:$p, synchronous:true){ product{ id } userErrors{ message } } }",
            "variables": {"p": product}}


def _ok_product(**over):
    p = {"title": "Anillo X", "status": "DRAFT",
         "variants": [{"sku": "AX-1", "price": "120.00",
                       "optionValues": [{"optionName": "Color", "name": "Plata"}]}]}
    p.update(over)
    return p


def test_create_policy_exists_and_has_ceilings(tmp_path):
    # la política de blunua tiene las claves que el guard necesita
    pol = json.loads((REPO_ROOT / "clients" / "blunua" / "create-policy.json").read_text(encoding="utf-8"))
    for k in ("maxProductsPerBatch", "minPriceCents", "maxPriceCents", "allowPublish",
              "requireImage", "requireDescriptionMinWords", "createRecordWindowHours"):
        assert k in pol


# --- Task 2: _check_create (whitelist de campos + status DRAFT + techo precio) ---

def test_create_allows_valid_draft():
    decision, _ = bg._check_create(_create_ti(_ok_product()), root, now)
    assert decision == "allow"


def test_create_blocks_status_active():
    d, why = bg._check_create(_create_ti(_ok_product(status="ACTIVE")), root, now)
    assert d == "block" and "borrador" in why.lower()


def test_create_blocks_status_missing():
    prod = _ok_product(); prod.pop("status")
    assert bg._check_create(_create_ti(prod), root, now)[0] == "block"


def test_create_blocks_id_present():
    assert bg._check_create(_create_ti(_ok_product(id="gid://shopify/Product/1")), root, now)[0] == "block"


def test_create_blocks_collections():
    assert bg._check_create(_create_ti(_ok_product(collections=["gid://shopify/Collection/1"])), root, now)[0] == "block"


def test_create_blocks_product_metafields():
    assert bg._check_create(_create_ti(_ok_product(metafields=[{"namespace": "worker", "key": "deal", "value": "{}"}])), root, now)[0] == "block"


def test_create_blocks_variant_metafields_and_inventory():
    v = _ok_product(variants=[{"sku": "X", "price": "120.00", "optionValues": [],
                               "inventoryQuantities": [{"locationId": "gid://shopify/Location/1", "name": "available", "quantity": 10}]}])
    assert bg._check_create(_create_ti(v), root, now)[0] == "block"


def test_create_blocks_price_over_ceiling():
    assert bg._check_create(_create_ti(_ok_product(variants=[{"sku": "X", "price": "9999999999.00", "optionValues": []}])), root, now)[0] == "block"


def test_create_blocks_price_under_floor():
    assert bg._check_create(_create_ti(_ok_product(variants=[{"sku": "X", "price": "0.50", "optionValues": []}])), root, now)[0] == "block"


def test_create_blocks_inline_payload_no_variables():
    ti = {"query": "mutation{ productSet(input:{title:\"X\", status:DRAFT}){ product{id} } }"}
    assert bg._check_create(ti, root, now)[0] == "block"


def test_create_blocks_missing_policy(tmp_path):
    # backups_root sin create-policy.json => block fail-closed
    assert bg._check_create(_create_ti(_ok_product()), str(tmp_path), now)[0] == "block"


def test_load_create_policy_excludes_template():
    # REGRESIÓN issue-3: con blunua Y _template presentes, el loader devuelve UNA
    # política (no None). Contra el REPO ROOT real, no tmp_path.
    assert bg.load_create_policy(root) is not None


def test_create_blocks_inline_payload_with_decoy_variable():
    # bypass inline+señuelo: input inline ACTIVE/id + $p manso en variables => block
    ti = {"query": 'mutation($p: ProductSetInput!){ productSet(input: {status: ACTIVE, id: "gid://shopify/Product/1"}){ product{id} } }',
          "variables": {"p": _ok_product()}}
    assert bg._check_create(ti, root, now)[0] == "block"


# --- Task 3: router rutea productset/productchangestatus por nombre ---

def test_evaluate_routes_productset_create_allow():
    # productSet DRAFT válido, end-to-end por evaluate (el camino real del hook)
    d, _ = bg.evaluate(_payload(_create_ti(_ok_product())["query"], _create_ti(_ok_product())["variables"]), root, now)
    assert d == "allow"


def test_evaluate_blocks_two_product_mutations_one_doc():
    q = ("mutation($p:ProductSetInput!){ a: productSet(input:$p){product{id}} "
         "b: productChangeStatus(productId:\"gid://shopify/Product/1\", status:ACTIVE){product{id}} }")
    assert bg.evaluate(_payload(q, {"p": _ok_product()}), root, now)[0] == "block"   # len(product_roots)!=1


def test_evaluate_blocks_bare_productset_no_variables_not_fail_open():
    # el fail-open histórico: productSet sin id no lo ve GID_RE; el ruteo por nombre lo agarra
    assert bg.evaluate(_payload("mutation{ productSet(input:{title:\"x\"}){product{id}} }"), root, now)[0] == "block"


def test_evaluate_blocks_productset_mixed_with_discount():
    q = ("mutation($p:ProductSetInput!){ productSet(input:$p){product{id}} "
         "discountAutomaticDeactivate(id:\"gid://shopify/DiscountAutomaticNode/1\"){ automaticDiscountId } }")
    assert bg.evaluate(_payload(q, {"p": _ok_product()}), root, now)[0] == "block"   # asuntos mixtos
