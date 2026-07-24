import sys, os, json, time, importlib.util
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


PID = "gid://shopify/Product/1"


def write_create_policy(dest, slug="blunua", **over):
    d = Path(dest) / "clients" / slug
    d.mkdir(parents=True, exist_ok=True)
    data = {"maxProductsPerBatch": 50, "minPriceCents": 100, "maxPriceCents": 100000000,
            "allowPublish": True, "requireImage": True, "requireDescriptionMinWords": 40,
            "createRecordWindowHours": 72}
    data.update(over)
    (d / "create-policy.json").write_text(json.dumps(data), encoding="utf-8")
    return d / "create-policy.json"


def write_create_record(dest, product_id=PID, slug="blunua", kind="create", age_hours=0):
    d = Path(dest) / "clients" / slug / "backups" / "create"
    d.mkdir(parents=True, exist_ok=True)
    tail = product_id.split("/")[-1]
    p = d / f"{tail}-20260724-120000.json"
    ts = datetime.fromtimestamp(time.time() - age_hours * 3600).isoformat()
    p.write_text(json.dumps({"kind": kind, "productId": product_id, "handle": "anillo-x",
                             "createdBy": "subir-productos", "ts": ts}), encoding="utf-8")
    if age_hours:
        old = time.time() - age_hours * 3600
        os.utime(p, (old, old))
    return p


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
    d, why = bg._check_create(_create_ti(prod), root, now)
    assert d == "block" and "borrador" in why, why


def test_create_blocks_id_present():
    d, why = bg._check_create(_create_ti(_ok_product(id="gid://shopify/Product/1")), root, now)
    assert d == "block" and "id" in why, why


def test_create_blocks_collections():
    d, why = bg._check_create(_create_ti(_ok_product(collections=["gid://shopify/Collection/1"])), root, now)
    assert d == "block" and "fuera de alcance" in why and "collections" in why, why


def test_create_blocks_product_metafields():
    d, why = bg._check_create(_create_ti(_ok_product(metafields=[{"namespace": "worker", "key": "deal", "value": "{}"}])), root, now)
    assert d == "block" and "fuera de alcance" in why and "metafields" in why, why


def test_create_blocks_variant_metafields_and_inventory():
    v = _ok_product(variants=[{"sku": "X", "price": "120.00", "optionValues": [],
                               "inventoryQuantities": [{"locationId": "gid://shopify/Location/1", "name": "available", "quantity": 10}]}])
    d, why = bg._check_create(_create_ti(v), root, now)
    assert d == "block" and "fuera de alcance" in why, why


def test_create_blocks_price_over_ceiling():
    d, why = bg._check_create(_create_ti(_ok_product(variants=[{"sku": "X", "price": "9999999999.00", "optionValues": []}])), root, now)
    assert d == "block" and "precio" in why, why


def test_create_blocks_price_under_floor():
    d, why = bg._check_create(_create_ti(_ok_product(variants=[{"sku": "X", "price": "0.50", "optionValues": []}])), root, now)
    assert d == "block" and "precio" in why, why


def test_create_blocks_inline_payload_no_variables():
    ti = {"query": "mutation{ productSet(input:{title:\"X\", status:DRAFT}){ product{id} } }"}
    d, why = bg._check_create(ti, root, now)
    assert d == "block" and "variables" in why, why


def test_create_blocks_missing_policy(tmp_path):
    # backups_root sin create-policy.json => block fail-closed
    d, why = bg._check_create(_create_ti(_ok_product()), str(tmp_path), now)
    assert d == "block" and "política" in why, why


# --- #4: bordes exactos del techo de precio (round, no truncar) ---
# create-policy de blunua: minPriceCents=100 ($1.00), maxPriceCents=100000000 ($1M).

def _price_product(price):
    return _ok_product(variants=[{"sku": "X", "price": price, "optionValues": []}])


def test_create_price_exactly_at_floor_allows():
    assert bg._check_create(_create_ti(_price_product("1.00")), root, now)[0] == "allow"


def test_create_price_exactly_at_ceiling_allows():
    assert bg._check_create(_create_ti(_price_product("1000000.00")), root, now)[0] == "allow"


def test_create_price_one_cent_under_floor_blocks():
    assert bg._check_create(_create_ti(_price_product("0.99")), root, now)[0] == "block"


def test_create_price_one_cent_over_ceiling_blocks():
    assert bg._check_create(_create_ti(_price_product("1000000.01")), root, now)[0] == "block"


def test_create_price_rounds_not_truncates():
    # int(float("1.15")*100)==114 truncaría; round da 115. Ambos están dentro del
    # rango, así que el test asegura que el precio se lee sin perder el centavo.
    assert bg._check_create(_create_ti(_price_product("1.15")), root, now)[0] == "allow"


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


# --- Task 4: _check_status_change — rama ARCHIVED (undo) ---

def test_status_change_blocks_active_in_f2(tmp_path):
    write_create_policy(tmp_path)
    q = f'mutation{{ productChangeStatus(productId:"{PID}", status:ACTIVE){{ product{{id}} }} }}'
    d, why = bg.evaluate(_payload(q), tmp_path, time.time())
    assert d == "block" and "publicar" in why.lower()


def test_status_change_archive_needs_create_record(tmp_path):
    write_create_policy(tmp_path)
    q = f'mutation{{ productChangeStatus(productId:"{PID}", status:ARCHIVED){{ product{{id}} }} }}'
    # sin registro create => block
    assert bg.evaluate(_payload(q), tmp_path, time.time())[0] == "block"


def test_status_change_archive_allows_with_fresh_create_record(tmp_path):
    write_create_policy(tmp_path); write_create_record(tmp_path, PID)
    q = f'mutation{{ productChangeStatus(productId:"{PID}", status:ARCHIVED){{ product{{id}} }} }}'
    d, why = bg.evaluate(_payload(q), tmp_path, time.time())
    assert d == "allow", why


def test_status_change_archive_via_variable_ref_allows(tmp_path):
    # status: $s resuelto a ARCHIVED contra variables => allow (con registro fresco)
    write_create_policy(tmp_path); write_create_record(tmp_path, PID)
    q = f'mutation($s: ProductStatus!){{ productChangeStatus(productId:"{PID}", status:$s){{ product{{id}} }} }}'
    d, why = bg.evaluate(_payload(q, {"s": "ARCHIVED"}), tmp_path, time.time())
    assert d == "allow", why


def test_status_change_active_arg_with_archived_decoy_var_blocks(tmp_path):
    # bypass de señuelo: status:ACTIVE inline + $s="ARCHIVED" en variables => block
    # (lee el ARGUMENTO real, no la variable no referenciada)
    write_create_policy(tmp_path); write_create_record(tmp_path, PID)
    q = f'mutation($s: ProductStatus!){{ productChangeStatus(productId:"{PID}", status:ACTIVE){{ product{{id}} }} }}'
    assert bg.evaluate(_payload(q, {"s": "ARCHIVED"}), tmp_path, time.time())[0] == "block"


def test_status_change_string_decoy_arg_read_as_active_blocks(tmp_path):
    # #1: un string señuelo `note: "status: ARCHIVED"` NO puede hacer que el guard
    # lea ARCHIVED mientras el status ejecutado es ACTIVE. El parser string-aware
    # por clave lee el status REAL (ACTIVE) => block (publicar es F3).
    write_create_policy(tmp_path); write_create_record(tmp_path, PID)
    q = (f'mutation{{ productChangeStatus(note: "status: ARCHIVED", productId: "{PID}", '
         f'status: ACTIVE){{ product{{id}} }} }}')
    d, why = bg.evaluate(_payload(q), tmp_path, time.time())
    assert d == "block" and "publicar" in why, why


def test_status_change_stale_create_record_is_rejected(tmp_path):
    # registro de creación fuera de la ventana (createRecordWindowHours=72) => block
    write_create_policy(tmp_path); write_create_record(tmp_path, PID, age_hours=200)
    q = f'mutation{{ productChangeStatus(productId:"{PID}", status:ARCHIVED){{ product{{id}} }} }}'
    assert bg.evaluate(_payload(q), tmp_path, time.time())[0] == "block"


def test_covering_create_record_multi_client_is_ambiguous(tmp_path):
    # #3: dos clientes con un registro de creación para el MISMO id numérico
    # (los ids de Shopify son por tienda) => ambiguo => block, como _covering_backup.
    write_create_record(tmp_path, PID, slug="blunua")
    write_create_record(tmp_path, PID, slug="otra")
    ok, why = bg._covering_create_record(tmp_path, PID, time.time(), 72)
    assert ok is False and "por tienda" in why, why


# --- Task 5: anti-bypass de la clase create ---

def test_bypass_malicious_referenced_variable_blocks_despite_manso_decoy(tmp_path):
    """Señuelo: dos objetos ProductSetInput, uno manso y uno con status:ACTIVE.
    El que se valida es el REFERENCIADO por el query (`$p`); si el payload malo
    está ahí, bloquea aunque haya un decoy manso al lado. No se puede esconder el
    payload malo detrás del nombre de la variable ejecutada."""
    write_create_policy(tmp_path)
    q = "mutation($p: ProductSetInput!){ productSet(input:$p){product{id}} }"
    variables = {"p": _ok_product(status="ACTIVE", collections=["gid://shopify/Collection/1"]),
                 "manso": _ok_product()}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"


def test_bypass_two_productset_roots_block_by_router(tmp_path):
    """Un productSet DRAFT válido adelante y un productSet con metafields atrás:
    dos product roots => block por Task 3 (una operación de producto por pedido),
    antes de que ninguno llegue a _check_create."""
    write_create_policy(tmp_path)
    q = ("mutation($p: ProductSetInput!, $q: ProductSetInput!){ "
         "productSet(input:$p){product{id}} productSet(input:$q){product{id}} }")
    variables = {"p": _ok_product(),
                 "q": _ok_product(metafields=[{"namespace": "worker", "key": "deal", "value": "{}"}])}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"


def test_bypass_productset_with_id_disguised_as_create_blocks(tmp_path):
    """productSet con `id` presente es un UPDATE disfrazado de alta => block."""
    write_create_policy(tmp_path)
    q = "mutation($p: ProductSetInput!){ productSet(input:$p){product{id}} }"
    assert bg.evaluate(_payload(q, {"p": _ok_product(id=PID)}), tmp_path, time.time())[0] == "block"


def test_bypass_productchangestatus_to_draft_blocks(tmp_path):
    """Bajar de estado (destino DRAFT) no está permitido: solo ARCHIVED (undo)."""
    write_create_policy(tmp_path); write_create_record(tmp_path, PID)
    q = f'mutation{{ productChangeStatus(productId:"{PID}", status:DRAFT){{ product{{id}} }} }}'
    assert bg.evaluate(_payload(q), tmp_path, time.time())[0] == "block"


def test_bypass_create_still_forbidden_mutation_wins(tmp_path):
    """Defensa en profundidad: un productSet manso adelante NO puede vehiculizar
    una mutación de la blocklist (productDelete) en el mismo documento."""
    write_create_policy(tmp_path)
    q = ("mutation($p: ProductSetInput!){ productSet(input:$p){product{id}} "
         'productDelete(input:{id:"' + PID + '"}){deletedProductId} }')
    assert bg.evaluate(_payload(q, {"p": _ok_product()}), tmp_path, time.time())[0] == "block"


# --- stagedUploadsCreate: subir bytes de una foto local (INERTE) ---
# Solo devuelve un destino temporal de subida; NO toca producto/stock/colección.
# El attach real pasa por productSet.files, que _check_create ya controla.

STAGED_Q = ("mutation($i:[StagedUploadInput!]!){ stagedUploadsCreate(input:$i){ "
            "stagedTargets{ url resourceUrl parameters{ name value } } userErrors{ message } } }")
STAGED_VARS = {"i": [{"filename": "a.jpg", "mimeType": "image/jpeg",
                      "resource": "IMAGE", "httpMethod": "POST"}]}


def test_staged_upload_alone_is_allowed():
    d, why = bg.evaluate(_payload(STAGED_Q, STAGED_VARS), root, now)
    assert d == "allow", why


def test_staged_upload_mixed_with_productset_blocks_by_asuntos(tmp_path):
    # NO puede viajar junto a un productSet: el contador de asuntos lo separa.
    write_create_policy(tmp_path)
    q = ("mutation($i:[StagedUploadInput!]!, $p:ProductSetInput!){ "
         "stagedUploadsCreate(input:$i){ stagedTargets{ url } } "
         "productSet(input:$p){ product{ id } } }")
    variables = {"i": STAGED_VARS["i"], "p": _ok_product()}
    d, why = bg.evaluate(_payload(q, variables), tmp_path, time.time())
    assert d == "block"
    # bloquea por MEZCLA DE ASUNTOS, no por un error incidental
    assert "mezcla" in why and "staged-upload" in why, why


def test_staged_upload_mixed_with_discount_deactivate_blocks_by_asuntos(tmp_path):
    q = ("mutation($i:[StagedUploadInput!]!){ "
         "stagedUploadsCreate(input:$i){ stagedTargets{ url } } "
         'discountAutomaticDeactivate(id:"gid://shopify/DiscountAutomaticNode/1"){ automaticDiscountId } }')
    d, why = bg.evaluate(_payload(q, {"i": STAGED_VARS["i"]}), tmp_path, time.time())
    assert d == "block"
    assert "mezcla" in why and "staged-upload" in why, why
