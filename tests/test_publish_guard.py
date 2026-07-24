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


def _status_q(status, product_id=PID):
    return f'mutation{{ productChangeStatus(productId:"{product_id}", status:{status}){{ product{{id}} }} }}'


# --- Task 2: rama ACTIVE de _check_status_change (habilitada en F3) ---

def test_active_blocked_without_allow_publish(tmp_path):
    # allowPublish:false => block, aun con create + publish records frescos
    write_publish_policy(tmp_path, allow_publish=False)
    write_create_record(tmp_path); write_publish_record(tmp_path)
    d, why = bg.evaluate(_payload(_status_q("ACTIVE")), tmp_path, time.time())
    assert d == "block" and "publicar" in why, why


def test_active_blocked_without_publish_record(tmp_path):
    # create record presente, publish record ausente => block ("revisar que esté completo")
    write_publish_policy(tmp_path); write_create_record(tmp_path)
    d, why = bg.evaluate(_payload(_status_q("ACTIVE")), tmp_path, time.time())
    assert d == "block" and "publicar" in why, why


def test_active_blocked_without_create_record(tmp_path):
    # publish record presente pero NO create record (no lo subió W3) => block
    write_publish_policy(tmp_path); write_publish_record(tmp_path)
    d, why = bg.evaluate(_payload(_status_q("ACTIVE")), tmp_path, time.time())
    assert d == "block" and "publicar" in why, why


def test_active_allowed_with_create_and_publish_records(tmp_path):
    # allowPublish:true + create + publish records frescos => allow
    write_publish_policy(tmp_path); write_create_record(tmp_path); write_publish_record(tmp_path)
    d, why = bg.evaluate(_payload(_status_q("ACTIVE")), tmp_path, time.time())
    assert d == "allow", why


def test_archived_still_works_from_f2(tmp_path):
    # regresión F2: ARCHIVED sigue funcionando con SOLO el create record (sin publish)
    write_publish_policy(tmp_path); write_create_record(tmp_path)
    d, why = bg.evaluate(_payload(_status_q("ARCHIVED")), tmp_path, time.time())
    assert d == "allow", why


def test_active_stale_publish_record_is_rejected(tmp_path):
    # publish record fuera de ventana => block (frescura doble, espejo de create)
    write_publish_policy(tmp_path); write_create_record(tmp_path)
    write_publish_record(tmp_path, age_hours=200)
    assert bg.evaluate(_payload(_status_q("ACTIVE")), tmp_path, time.time())[0] == "block"


def test_covering_publish_record_multi_client_is_ambiguous(tmp_path):
    # ids de Shopify son por tienda: dos clientes con publish record del mismo id => ambiguo
    write_publish_record(tmp_path, slug="blunua")
    write_publish_record(tmp_path, slug="otra")
    ok, why = bg._covering_publish_record(tmp_path, PID, time.time(), 72)
    assert ok is False and "por tienda" in why, why


# --- Task 3: reabrir publishablePublish con _check_publish ---

def _publish_payload(pubs, product_id=PID, var="p"):
    q = (f'mutation(${var}:[PublicationInput!]!){{ publishablePublish(id:"{product_id}", '
         f'input:${var}){{ publishable {{ availablePublicationsCount {{ count }} }} userErrors {{ message }} }} }}')
    return _payload(q, {var: pubs})


def _records(tmp_path):
    write_publish_policy(tmp_path); write_create_record(tmp_path); write_publish_record(tmp_path)


def test_publish_allows_online_store_with_records(tmp_path):
    _records(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}]), tmp_path, time.time())
    assert d == "allow", why


def test_publish_blocks_channel_not_in_allowlist(tmp_path):
    _records(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_EVIL}]), tmp_path, time.time())
    assert d == "block" and "canal" in why, why


def test_publish_blocks_when_allowlist_empty(tmp_path):
    write_publish_policy(tmp_path, allowed=[]); write_create_record(tmp_path); write_publish_record(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}]), tmp_path, time.time())
    assert d == "block", why


def test_publish_blocks_without_allow_publish(tmp_path):
    write_publish_policy(tmp_path, allow_publish=False); write_create_record(tmp_path); write_publish_record(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}]), tmp_path, time.time())
    assert d == "block", why


def test_publish_blocks_scheduled_publishdate(tmp_path):
    _records(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE, "publishDate": "2027-01-01T00:00:00Z"}]),
                         tmp_path, time.time())
    assert d == "block", why


def test_publish_blocks_without_create_or_publish_record(tmp_path):
    # allowlist ok pero SIN records => block
    write_publish_policy(tmp_path)
    assert bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}]), tmp_path, time.time())[0] == "block"
    # con create pero sin publish record => block
    write_create_record(tmp_path)
    assert bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}]), tmp_path, time.time())[0] == "block"


def test_publish_blocks_if_any_channel_not_allowed(tmp_path):
    # input:[{ALLOWED},{EVIL}] => block: valida TODOS los publicationId, no el primero
    _records(tmp_path)
    d, why = bg.evaluate(_publish_payload([{"publicationId": PUB_ONLINE}, {"publicationId": PUB_EVIL}]),
                         tmp_path, time.time())
    assert d == "block", why


def test_publish_blocks_empty_input_or_missing_publication_id(tmp_path):
    _records(tmp_path)
    assert bg.evaluate(_publish_payload([]), tmp_path, time.time())[0] == "block"                 # lista vacía
    assert bg.evaluate(_publish_payload([{"foo": "bar"}]), tmp_path, time.time())[0] == "block"    # sin publicationId


def test_publish_inline_decoy_blocked(tmp_path):
    # input inline [{EVIL}] + variable señuelo mansa => block (el input tiene que ir por variable)
    _records(tmp_path)
    q = (f'mutation($p:[PublicationInput!]!){{ publishablePublish(id:"{PID}", '
         f'input:[{{publicationId:"{PUB_EVIL}"}}]){{ userErrors {{ message }} }} }}')
    d, why = bg.evaluate(_payload(q, {"p": [{"publicationId": PUB_ONLINE}]}), tmp_path, time.time())
    assert d == "block", why


def test_publishableunpublish_still_forbidden():
    q = ('mutation{ publishableUnpublish(id:"gid://shopify/Product/1", '
         'input:[{publicationId:"gid://shopify/Publication/1"}]){ shop{id} } }')
    assert bg.evaluate(_payload(q), root, now)[0] == "block"


# --- Task 4: anti-bypass de la clase publish ---

def test_bypass_publish_mixed_with_active_status_blocks_by_asuntos(tmp_path):
    """EL bypass de canal arbitrario. Setup REAL: create+publish records frescos,
    allowPublish:true, y el Online Store en la allowlist — así la mitad benigna
    (productChangeStatus ACTIVE) pasaría SOLA. El publishablePublish apunta a
    CANAL_MALO. Que bloquee por 'mezcla...publicación' prueba que el corte viene
    del contador `asuntos` (has_publish), no de un record faltante que bloquearía
    por otro motivo. Sin el fix, el status-change se aprobaría y el
    publishablePublish(CANAL_MALO) se ejecutaría sin pasar por _check_publish."""
    _records(tmp_path)
    q = (f'mutation($p:[PublicationInput!]!){{ '
         f'productChangeStatus(productId:"{PID}", status:ACTIVE){{ product{{id}} }} '
         f'publishablePublish(id:"{PID}", input:$p){{ userErrors{{ message }} }} }}')
    d, why = bg.evaluate(_payload(q, {"p": [{"publicationId": PUB_EVIL}]}), tmp_path, time.time())
    assert d == "block" and "mezcla" in why and "publicación" in why, why


def test_bypass_publish_plus_staged_upload_blocks_by_asuntos(tmp_path):
    """publishablePublish + stagedUploadsCreate en un doc => block por asuntos."""
    _records(tmp_path)
    q = (f'mutation($p:[PublicationInput!]!, $i:[StagedUploadInput!]!){{ '
         f'publishablePublish(id:"{PID}", input:$p){{ userErrors{{ message }} }} '
         f'stagedUploadsCreate(input:$i){{ stagedTargets{{ url }} }} }}')
    d, why = bg.evaluate(_payload(q, {"p": [{"publicationId": PUB_ONLINE}], "i": [{"resource": "IMAGE"}]}),
                         tmp_path, time.time())
    assert d == "block" and "mezcla" in why, why


def test_publish_variable_decoy_validates_referenced_input(tmp_path):
    """El query referencia `$p`; un `$decoy` manso NO cambia que se valide `$p` (lo
    que el server ejecuta). Con `$p` = CANAL_MALO bloquea, aunque el decoy traiga
    el canal permitido."""
    _records(tmp_path)
    q = (f'mutation($p:[PublicationInput!]!){{ publishablePublish(id:"{PID}", input:$p)'
         '{ userErrors{ message } } }')
    variables = {"p": [{"publicationId": PUB_EVIL}], "decoy": [{"publicationId": PUB_ONLINE}]}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"


def test_status_change_to_draft_or_unlisted_blocks(tmp_path):
    """Destinos no permitidos: solo ARCHIVED (undo) y ACTIVE (publicar)."""
    write_publish_policy(tmp_path); write_create_record(tmp_path); write_publish_record(tmp_path)
    for st in ("DRAFT", "UNLISTED"):
        assert bg.evaluate(_payload(_status_q(st)), tmp_path, time.time())[0] == "block", st


def test_two_publishablepublish_in_one_doc_blocks(tmp_path):
    """Dos publishablePublish en un doc: el input validado sale de la variable del
    PRIMERO; el segundo viajaría sin control => block ('una publicación por pedido')."""
    _records(tmp_path)
    q = (f'mutation($p:[PublicationInput!]!, $q:[PublicationInput!]!){{ '
         f'publishablePublish(id:"{PID}", input:$p){{ userErrors{{ message }} }} '
         f'b: publishablePublish(id:"{PID}", input:$q){{ userErrors{{ message }} }} }}')
    variables = {"p": [{"publicationId": PUB_ONLINE}], "q": [{"publicationId": PUB_EVIL}]}
    assert bg.evaluate(_payload(q, variables), tmp_path, time.time())[0] == "block"
