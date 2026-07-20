import json, time, os
from datetime import datetime
from pathlib import Path
import importlib.util
import pytest

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


T_GQL = "mcp__claude_ai_Shopify__graphql_mutation"

def policy(tmp_path, **over):
    from tests.test_deal_policy import write_policy
    return write_policy(tmp_path, **over)

def create_discount(pct=0.10, ends="2026-10-18T00:00:00Z",
                    starts="2026-07-20T00:00:00Z", items=None, product_id=PID):
    """`productId` va SIEMPRE como variable aparte.

    Razón: cuando el descuento apunta a variantes (`productVariantsToAdd`), el
    gid de variante no sirve para buscar el backup, que está indexado por
    producto. El guard exige este campo en vez de intentar derivarlo.
    """
    items = items or {"products": {"productsToAdd": [product_id]}}
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($d: DiscountAutomaticBasicInput!, $productId: ID!) { discountAutomaticBasicCreate(automaticBasicDiscount: $d) { automaticDiscountNode { id } } }",
        "variables": {"productId": product_id, "d": {
            "title": "shopify-control - test",
            "startsAt": starts, "endsAt": ends,
            "minimumRequirement": {"quantity": {"greaterThanOrEqualToQuantity": "2"}},
            "customerGets": {"value": {"percentage": pct}, "items": items},
        }}}}

def test_create_discount_happy_path(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "allow"

def test_create_discount_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "block"

def test_percentage_unit_trap(tmp_path):
    """0.7 es 70%, NO 0.7%. Comparar contra maxDiscountPct=30 sin convertir
    dejaría pasar 0.7 <= 30. Spec §9.4."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, why = bg.evaluate(create_discount(pct=0.7), tmp_path, time.time())
    assert d == "block", f"70% debe bloquear con techo 30%, dio: {why}"

def test_missing_endsAt_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(ends=None), tmp_path, time.time())
    assert d == "block"

def test_duration_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(ends="2031-01-01T00:00:00Z"), tmp_path, time.time())
    assert d == "block"

def test_items_all_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(items={"all": True}), tmp_path, time.time())
    assert d == "block"

def test_collection_scope_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(
        create_discount(items={"collections": {"add": ["gid://shopify/Collection/9"]}}),
        tmp_path, time.time())
    assert d == "block"

def test_product_variants_scope_is_allowed(tmp_path):
    """Mitigación de la incógnita C (spec §14): si el umbral resulta ser a nivel
    carrito, el escalón pasa a exigir N de la misma variante.

    El backup se busca por el `productId` de las variables, NO por el gid de
    variante: `"/Product/" in "gid://shopify/ProductVariant/5"` es False."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(
        create_discount(items={"products": {"productVariantsToAdd": ["gid://shopify/ProductVariant/5"]}}),
        tmp_path, time.time())
    assert d == "allow"

def test_discount_without_productId_variable_is_blocked(tmp_path):
    """Sin `productId` no hay forma de saber qué backup respalda este write."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    del p["tool_input"]["variables"]["productId"]
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_codes_strategy_blocked_unless_enabled(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    p["tool_input"]["query"] = p["tool_input"]["query"].replace(
        "discountAutomaticBasicCreate", "discountCodeBasicCreate")
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_no_policy_fails_closed(tmp_path):
    """Sin deal-policy.json no hay techo que aplicar => se bloquea."""
    write_deal_backup(tmp_path)
    d, _ = bg.evaluate(create_discount(), tmp_path, time.time())
    assert d == "block"

def test_deactivate_is_always_allowed(tmp_path):
    """Spec §9.8: la compensación no puede estar condicionada a un estado que
    la compensación misma modifica. Sin política y sin backup, igual pasa."""
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/7") { automaticDiscountNode { id } } }'}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow"

def test_update_mutation_is_blocked(tmp_path):
    """Spec §6.3: sin camino de update no hay forma de estirar endsAt ni
    cambiar el percentage después de creado."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { discountAutomaticBasicUpdate(id: "gid://shopify/DiscountAutomaticNode/7", automaticBasicDiscount: {endsAt: "2031-01-01T00:00:00Z"}) { automaticDiscountNode { id } } }'}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"

def test_all_delete_variants_are_blocked(tmp_path):
    """Las cinco. Las tres Bulk faltaban en la primera redacción del spec."""
    policy(tmp_path); write_deal_backup(tmp_path)
    for mut in ["discountAutomaticDelete", "discountCodeDelete",
                "discountAutomaticBulkDelete", "discountCodeBulkDelete",
                "discountCodeRedeemCodeBulkDelete"]:
        p = {"tool_name": T_GQL, "tool_input": {
            "query": f'mutation {{ {mut}(id: "gid://shopify/DiscountAutomaticNode/7") {{ deletedId }} }}'}}
        d, _ = bg.evaluate(p, tmp_path, time.time())
        assert d == "block", f"{mut} no bloqueó"

def test_unlisted_discount_mutation_is_blocked(tmp_path):
    """Whitelist CERRADA (spec §9.0): lo no enumerado se bloquea."""
    policy(tmp_path); write_deal_backup(tmp_path)
    for mut in ["discountAutomaticBxgyCreate", "discountAutomaticFreeShippingCreate",
                "discountAutomaticAppCreate", "discountRedeemCodeBulkAdd"]:
        p = {"tool_name": T_GQL, "tool_input": {"query": f"mutation {{ {mut}(x: 1) {{ id }} }}"}}
        d, _ = bg.evaluate(p, tmp_path, time.time())
        assert d == "block", f"{mut} no bloqueó"


# --- Documentos con varios root fields (bypass del prefijo `Deactivate`) -----
# GraphQL admite varias mutaciones en un mismo documento. Un `Deactivate`
# adelante NO puede volver inocente a lo que viene atrás.

DEACTIVATE = 'discountAutomaticDeactivate(id: "gid://shopify/DiscountAutomaticNode/7") { automaticDiscountNode { id } }'

def test_deactivate_plus_delete_is_blocked(tmp_path):
    """El invariante central del milestone: se desactiva, NO se borra.
    Un `Deactivate` de prefijo no puede colar un `Delete` atrás."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {DEACTIVATE} discountAutomaticDelete(id: "gid://shopify/DiscountAutomaticNode/7") {{ deletedId }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el delete pasó escondido detrás del deactivate: {why}"

def test_deactivate_plus_bxgy_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f"mutation {{ {DEACTIVATE} discountAutomaticBxgyCreate(x: 1) {{ id }} }}"}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el BXGY pasó escondido detrás del deactivate: {why}"

def test_deactivate_plus_create_applies_full_conditions(tmp_path):
    """Un create NO queda exento por compartir documento con un deactivate:
    el 70% tiene que chocar contra el techo de 30% igual."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount(pct=0.7)
    p["tool_input"]["query"] = p["tool_input"]["query"].replace(
        "{ discountAutomaticBasicCreate", "{ " + DEACTIVATE + " discountAutomaticBasicCreate", 1)
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el create de 70% pasó detrás del deactivate: {why}"
    assert "70" in why, f"bloqueó, pero no por el techo: {why}"

def test_two_deactivates_are_allowed(tmp_path):
    """§9.8 sigue intacto: un documento de PURAS desactivaciones pasa sin
    política, sin backup y sin techo. Lo que se corrigió no fue el permiso,
    fue retornar antes de mirar el resto del documento."""
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {DEACTIVATE} discountCodeDeactivate(id: "gid://shopify/DiscountCodeNode/8") {{ codeDiscountNode {{ id }} }} }}'}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow"

def test_metafields_plus_discount_is_blocked(tmp_path):
    """Protege a la Task 4: sin esto, el dispatch del metafield que se agrega
    ahí queda tapado por el de ofertas apenas aterriza."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {DEACTIVATE} metafieldsSet(metafields: [{{ownerId: "gid://shopify/Product/1", namespace: "x", key: "y", value: "z", type: "single_line_text_field"}}]) {{ metafields {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el metafieldsSet pasó detrás del deactivate: {why}"

def test_metafields_plus_product_update_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { metafieldsSet(metafields: [{ownerId: "gid://shopify/Product/1", namespace: "x", key: "y", value: "z", type: "single_line_text_field"}]) { metafields { id } } productUpdate(input: {id: "gid://shopify/Product/1", descriptionHtml: "<p>x</p>"}) { product { id } } }'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"documento mixto metafields+producto no bloqueó: {why}"

def test_three_concerns_in_one_document_are_blocked(tmp_path):
    """Oferta + metafield + edición de producto, todo junto."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    p["tool_input"]["query"] = p["tool_input"]["query"].replace(
        "{ discountAutomaticBasicCreate",
        '{ metafieldsSet(metafields: [{ownerId: "gid://shopify/Product/1", namespace: "x", key: "y", value: "z", type: "single_line_text_field"}]) { metafields { id } } '
        'productUpdate(input: {id: "gid://shopify/Product/1", descriptionHtml: "<p>x</p>"}) { product { id } } '
        'discountAutomaticBasicCreate', 1)
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"documento con los tres asuntos no bloqueó: {why}"

def test_deactivate_only_still_allowed_after_restructure(tmp_path):
    """§9.8 intacto tras el restructure: puras desactivaciones pasan SIN
    política, SIN backup y SIN techo. Es la compensación; si depende de algo,
    deja de estar disponible justo cuando hace falta."""
    p = {"tool_name": T_GQL, "tool_input": {"query": f"mutation {{ {DEACTIVATE} }}"}}
    d, _ = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow"

def test_deactivate_plus_unnamed_product_write_is_blocked(tmp_path):
    """`productSet` no está en ninguna lista del guard: ni en la blocklist ni
    en `productUpdate`. El chequeo puntual anterior (solo `productupdate`) lo
    dejaba pasar detrás de un deactivate; la regla general lo agarra."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {DEACTIVATE} productSet(input: {{id: "gid://shopify/Product/1", status: DRAFT}}) {{ product {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el productSet pasó detrás del deactivate: {why}"

def test_deactivate_plus_product_update_is_blocked(tmp_path):
    """Documento mixto: el `_check_discount` retornaba y el control de campos
    de `productUpdate` no llegaba a correr, así que `status`/`handle` —lo que
    el v1 NUNCA toca— pasaban detrás de un deactivate."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {DEACTIVATE} productUpdate(input: {{id: "gid://shopify/Product/1", handle: "x", status: DRAFT}}) {{ product {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el productUpdate de status/handle pasó detrás del deactivate: {why}"

def test_two_creates_in_one_document_are_blocked(tmp_path):
    """Misma clase de agujero: el objeto validado sale de `variables` y es UNO
    SOLO (`_discount_input` devuelve el primero con `customerGets`). Con dos
    creates en el mismo documento el segundo —acá, 90%— nunca se validaría."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    p["tool_input"]["query"] = (
        "mutation ($d: DiscountAutomaticBasicInput!, $d2: DiscountAutomaticBasicInput!, $productId: ID!) "
        "{ discountAutomaticBasicCreate(automaticBasicDiscount: $d) { automaticDiscountNode { id } } "
        "discountAutomaticBasicCreate(automaticBasicDiscount: $d2) { automaticDiscountNode { id } } }")
    p["tool_input"]["variables"]["d2"] = {
        "title": "el que no se valida",
        "startsAt": "2026-07-20T00:00:00Z", "endsAt": "2026-10-18T00:00:00Z",
        "customerGets": {"value": {"percentage": 0.9},
                         "items": {"products": {"productsToAdd": [PID]}}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el segundo create (90%) nunca se validó: {why}"


# --- Familia de producto: whitelist cerrada ---------------------------------
# El control de campos solo mira el objeto `input: {...}`, así que toda mutación
# que reciba `productId:` + arrays no exponía ninguna key y quedaba gobernada
# solo por el backup: un backup de descripción fresco era una llave de 15
# minutos. Enumeradas contra el schema vivo del Admin API (26 en la familia).

FUERA_DE_ALCANCE = [
    "productBundleCreate", "productBundleUpdate", "productCreate",
    "productDuplicate", "productFeedCreate", "productFeedDelete",
    "productFullSync", "productJoinSellingPlanGroups",
    "productLeaveSellingPlanGroups", "productOptionUpdate",
    "productOptionsCreate", "productOptionsDelete", "productOptionsReorder",
    "productReorderMedia", "productSet", "productVariantAppendMedia",
    "productVariantDetachMedia", "productVariantJoinSellingPlanGroups",
    "productVariantLeaveSellingPlanGroups",
    "productVariantRelationshipBulkUpdate", "productVariantsBulkReorder",
]

@pytest.mark.parametrize("mut", FUERA_DE_ALCANCE)
def test_product_mutation_outside_v1_is_blocked(tmp_path, mut):
    """Con backup de descripción FRESCO, que es el estado normal mientras el
    skill edita una descripción. Sin la whitelist, las 21 pasaban."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {mut}(productId: "{PID}", items: [{{id: "gid://shopify/X/2"}}]) {{ userErrors {{ field }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"{mut} pasó con un backup de descripción fresco: {why}"

def test_product_set_is_blocked_in_both_argument_shapes(tmp_path):
    """EL hallazgo: la misma mutación, el mismo efecto sobre la tienda, y el
    guard viejo bloqueaba una forma y dejaba pasar la otra.

    `input: {...}` exponía `status` y el control de campos lo agarraba;
    `productId:` + arrays no exponía NADA, el control pasaba en el vacío y
    mandaba el backup de descripción."""
    write_description_backup(tmp_path)
    formas = [
        f'productSet(input: {{id: "{PID}", status: DRAFT}}) {{ product {{ id }} }}',
        f'productSet(productId: "{PID}", positions: [{{id: "gid://shopify/ProductVariant/5"}}]) {{ product {{ id }} }}',
    ]
    for forma in formas:
        d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": "mutation { " + forma + " }"}},
                             tmp_path, time.time())
        assert d == "block", f"productSet pasó en esta forma: {forma} -> {why}"

def test_product_create_is_blocked(tmp_path):
    """Sin gid de producto no hay a qué agarrarse: caía en el `allow` final.
    CLAUDE.md regla 5 dice que la herramienta nunca crea productos, y el
    connector tenía cerrada la puerta del tool pero no la de GraphQL."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { productCreate(input: {title: "producto nuevo"}) { product { id } } }'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"productCreate pasó: {why}"

def test_product_duplicate_is_blocked(tmp_path):
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ productDuplicate(productId: "{PID}", newTitle: "copia") {{ newProduct {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"productDuplicate pasó: {why}"

def test_product_update_description_still_passes(tmp_path):
    """GUARDA DE REGRESIÓN: si la whitelist sobre-bloquea, el único camino
    legítimo del v1 deja de funcionar y este test cae."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ productUpdate(input: {{id: "{PID}", descriptionHtml: "<p>nueva</p>"}}) {{ product {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow", f"el camino legítimo de descripción se rompió: {why}"

def test_product_update_with_status_still_blocks_on_field_scope(tmp_path):
    """La whitelist por NOMBRE no puede haber cortocircuitado el control de
    CAMPOS de la única mutación que sigue necesitándolo."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ productUpdate(input: {{id: "{PID}", status: DRAFT}}) {{ product {{ id }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"productUpdate con status pasó: {why}"
    assert "status" in why, f"bloqueó, pero no por el control de campos: {why}"


# --- vacio es DESCONOCIDO, no limpio (raiz de la clase de agujeros) ---------

def test_product_update_without_id_in_variables_is_blocked(tmp_path):
    """`input` sin `id`: _variables_product_keys no cosecha nada, `extra` queda
    vacio, y el write pasaba con handle y status adentro. Hoy solo lo salvaba
    que Shopify exige input.id del lado del servidor."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($input: ProductInput!) { productUpdate(input:$input){product{id}} }",
        "variables": {"input": {"handle": "x", "status": "DRAFT"},
                      "ref": "gid://shopify/Product/1"}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why

def test_product_update_with_id_still_blocks_on_field_scope(tmp_path):
    """Control: el MISMO write con `id` presente bloquea, y bloquea por ALCANCE
    DE CAMPOS. Si el motivo cambiara, el chequeo nuevo estaria tapando al viejo."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($input: ProductInput!) { productUpdate(input:$input){product{id}} }",
        "variables": {"input": {"id": "gid://shopify/Product/1",
                                "handle": "x", "status": "DRAFT"}}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block"
    assert "status" in why, f"deberia bloquear por alcance de campos, dio: {why}"

def test_legit_description_write_still_passes(tmp_path):
    """Guardia de regresion: el unico camino legitimo del v1 sigue abierto."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { productUpdate(product:{id:"gid://shopify/Product/1", descriptionHtml:"<p>x</p>"}){product{id}} }'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow", why


# --- familia collection: whitelist cerrada y vacia --------------------------

def test_collection_mutations_are_blocked(tmp_path):
    write_description_backup(tmp_path)
    for m in ['collectionDelete(input:{id:"gid://shopify/Collection/1"}){deletedCollectionId}',
              'collectionDuplicate(id:"gid://shopify/Collection/1"){newCollection{id}}',
              'collectionReorderProducts(id:"gid://shopify/Collection/1", moves:[]){job{id}}',
              'collectionAddProductsV2(id:"gid://shopify/Collection/1", productIds:[]){job{id}}',
              'collectionRemoveProducts(id:"gid://shopify/Collection/1", productIds:[]){job{id}}']:
        d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": "mutation { %s }" % m}},
                             tmp_path, time.time())
        assert d == "block", f"{m.split('(')[0]} no bloqueo"


def test_detectors_are_not_blind_to_digits_in_mutation_names(tmp_path):
    r"""Los tres detectores usaban `[A-Za-z]*`, que se corta en el primer digito.

    `collectionAddProductsV2` no matcheaba: [A-Za-z]* paraba en la V, el `2` no
    es letra y el `\(` no llegaba. Shopify usa sufijos V2/V3 de forma habitual,
    asi que la whitelist "cerrada" tenia un agujero con forma de numero. Este
    test lo fija para las tres familias.
    """
    write_description_backup(tmp_path)
    for q in ['collectionAddProductsV2(id:"gid://shopify/Collection/1", productIds:[]){job{id}}',
              'productVariantsBulkUpdate2(productId:"gid://shopify/Product/1"){userErrors{field}}',
              'discountAutomaticBxgyCreate2(x:1){id}']:
        d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": "mutation { %s }" % q}},
                             tmp_path, time.time())
        assert d == "block", f"{q.split('(')[0]} paso: {why}"

    # Y el detector devuelve el nombre COMPLETO, con digito incluido.
    assert bg._collection_mutations("collectionAddProductsV2(") == ["collectionaddproductsv2"]


# --- metafield worker.deal (spec §9.1, §9.3) --------------------------------

def metafield_set(tiers, namespace="worker", key="deal"):
    value = json.dumps({"version": 1, "type": "quantity_breaks", "tiers": tiers,
                        "strategy": "automatic", "startsAt": "2026-07-20T00:00:00Z",
                        "endsAt": "2026-10-18T00:00:00Z"})
    return {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [{"ownerId": PID, "namespace": namespace, "key": key,
                             "type": "json", "value": value}]}}}

TIERS_OK = [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}]

def test_metafield_happy_path(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK), tmp_path, time.time())
    assert d == "allow"

def test_metafield_pct_over_ceiling_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set([{"qty": 1, "pct": 0}, {"qty": 2, "pct": 90}]),
                       tmp_path, time.time())
    assert d == "block"

def test_metafield_too_many_tiers_is_blocked(tmp_path):
    policy(tmp_path, maxTiers=2); write_deal_backup(tmp_path)
    tiers = [{"qty": n, "pct": n} for n in range(1, 6)]
    d, _ = bg.evaluate(metafield_set(tiers), tmp_path, time.time())
    assert d == "block"

def test_metafield_other_namespace_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK, namespace="otro"), tmp_path, time.time())
    assert d == "block"

def test_metafield_without_backup_is_blocked(tmp_path):
    policy(tmp_path)
    d, _ = bg.evaluate(metafield_set(TIERS_OK), tmp_path, time.time())
    assert d == "block"

def test_metafield_empty_tiers_is_allowed(tmp_path):
    """`sacar escalones` escribe tiers: [] — tiene que poder."""
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set([]), tmp_path, time.time())
    assert d == "allow"

# --- schema de §5, que el spec afirma "verificado por el guard" -------------

def test_metafield_unordered_tiers_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 0}, {"qty": 5, "pct": 20, "highlight": True}, {"qty": 3, "pct": 10}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_duplicate_qty_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True}, {"qty": 2, "pct": 15}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_first_tier_with_discount_is_blocked(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    d, _ = bg.evaluate(metafield_set(
        [{"qty": 1, "pct": 5}, {"qty": 2, "pct": 10, "highlight": True}]),
        tmp_path, time.time())
    assert d == "block"

def test_metafield_needs_exactly_one_highlight(tmp_path):
    policy(tmp_path); write_deal_backup(tmp_path)
    for tiers in (
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10}],                                    # ninguno
        [{"qty": 1, "pct": 0}, {"qty": 2, "pct": 10, "highlight": True},
         {"qty": 3, "pct": 15, "highlight": True}],                                       # dos
    ):
        d, _ = bg.evaluate(metafield_set(tiers), tmp_path, time.time())
        assert d == "block"


# --- vacio es DESCONOCIDO, no limpio, tambien en el metafield ---------------
# Misma clase de agujero que cerro la Task 3 en la rama de producto: un parse
# que sale vacio significa "no pude leerlo", NUNCA "no hay nada fuera de
# alcance". Si un parse vacio satisficiera el chequeo de namespace en el vacio,
# el techo del metafield no existiria.

def test_metafield_with_empty_list_is_blocked(tmp_path):
    """`metafields: []` no deja nada que verificar: no hay namespace, no hay
    tiers y no hay ownerId con el que buscar el backup."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": []}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why

def test_metafield_entry_without_namespace_is_blocked(tmp_path):
    """Una entrada sin `namespace`/`key` legibles no puede pasar el chequeo de
    namespace por ausencia: `None != "worker"` tiene que bloquear."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [{"ownerId": PID, "type": "json", "value": "{}"}]}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why

def test_metafield_inline_in_the_query_is_blocked(tmp_path):
    """El parse estructural lee `variables`, no el texto del query. Un
    metafieldsSet con las entradas inline sale VACIO del parse, y vacio es
    desconocido: bloquea. Falla cerrado, que es el lado correcto."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { metafieldsSet(metafields: [{ownerId: "%s", namespace: "worker", '
                 'key: "deal", value: "{}", type: "json"}]) { metafields { id } } }' % PID}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why


def test_metafield_without_ownerId_is_blocked_even_with_a_dash_named_backup(tmp_path):
    """Sin `ownerId`, `owner` quedaba vacio y el glob pasaba a ser
    `**/backups/deals/-*.json`. Un archivo llamado `-trampa.json` lo satisfacia:
    bloqueaba de casualidad, no por diseno. Fail-open verificado antes del fix.
    """
    policy(tmp_path)
    d = tmp_path/"clients/blunua/backups/deals"
    d.mkdir(parents=True, exist_ok=True)
    (d/"-trampa.json").write_text(json.dumps({
        "kind": "deal", "productId": "", "previous": None,
        "ts": datetime.now().isoformat()}), encoding="utf-8")

    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields:$m){metafields{id}} }",
        "variables": {"m": [{"namespace": "worker", "key": "deal", "type": "json",
                             "value": json.dumps({"tiers": []})}]}}}
    d_, why = bg.evaluate(p, tmp_path, time.time())
    assert d_ == "block", why
    assert "producto" in why


def test_variable_senuelo_no_derrota_el_techo(tmp_path):
    """F2. El query nombra la variable que usa; el guard miraba la PRIMERA de
    `variables` que tuviera `customerGets` y nunca correlacionaba las dos cosas.
    Las variables no declaradas el servidor las ignora, asi que un senuelo manso
    ordenado alfabeticamente adelante (`aaa_decoy`) se llevaba puestos los tres
    techos: 100% de descuento, sobre una coleccion entera, por diez anos."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($real: DiscountAutomaticBasicInput!) { discountAutomaticBasicCreate(automaticBasicDiscount: $real) { automaticDiscountNode { id } } }",
        "variables": {
            "aaa_decoy": {"startsAt": "2026-07-20T00:00:00Z", "endsAt": "2026-08-01T00:00:00Z",
                          "customerGets": {"value": {"percentage": 0.05},
                                           "items": {"products": {"productsToAdd": ["gid://shopify/Product/1"]}}}},
            "real": {"startsAt": "2026-07-20T00:00:00Z", "endsAt": "2036-01-01T00:00:00Z",
                     "customerGets": {"value": {"percentage": 1.0},
                                      "items": {"collections": {"add": ["gid://shopify/Collection/1"]}}}},
            "productId": "gid://shopify/Product/1"}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el senuelo tapo un descuento de 100% a diez anos: {why}"


def test_un_solo_descuento_por_pedido_sigue_pasando(tmp_path):
    """Control de sobre-bloqueo: variables con UN descuento y ruido alrededor
    (el `productId`, un titulo suelto) siguen siendo un pedido valido."""
    policy(tmp_path); write_deal_backup(tmp_path)
    p = create_discount()
    p["tool_input"]["variables"]["nota"] = "esto no es un descuento"
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow", why


def test_dos_entradas_de_metafield_esconden_una(tmp_path):
    """F2, misma clase, rama del metafield. El loop valida TODAS las entradas,
    pero `owner = e.get("ownerId") or owner` se pisa en cada vuelta y gana la
    ULTIMA. Dos worker.deal impecables sobre productos distintos pasaban enteras:
    el backup del segundo habilitaba la escritura sobre el primero, que quedaba
    sin undo. Verificado en ALLOW antes del fix."""
    policy(tmp_path); write_deal_backup(tmp_path)          # backup solo del Product/1
    victima = json.dumps({"tiers": [{"qty": 1, "pct": 0},
                                    {"qty": 2, "pct": 25, "highlight": True}]})
    tapadera = json.dumps({"tiers": [{"qty": 1, "pct": 0},
                                     {"qty": 2, "pct": 10, "highlight": True}]})
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation ($m: [MetafieldsSetInput!]!) { metafieldsSet(metafields: $m) { metafields { id } } }",
        "variables": {"m": [
            {"ownerId": "gid://shopify/Product/999", "namespace": "worker", "key": "deal",
             "type": "json", "value": victima},
            {"ownerId": PID, "namespace": "worker", "key": "deal",
             "type": "json", "value": tapadera}]}}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"la oferta sobre Product/999 viajo sin backup propio: {why}"


# --- F1: el control de campos miraba solo el PRIMER objeto input ------------
# El commit c9b2dea cerro esta clase para los NOMBRES de las mutaciones y dejo
# el mismo `re.search` dos funciones mas abajo, en el control de CAMPOS.

F1_BUENO = 'productUpdate(input: {id: "gid://shopify/Product/1", descriptionHtml: "<p>ok</p>"}) { product { id } }'
F1_MALO = 'b: productUpdate(input: {id: "gid://shopify/Product/1", status: DRAFT, handle: "robado"}) { product { id } }'

def test_segundo_product_update_no_escapa_al_control_de_campos(tmp_path):
    """El documento entero pasaba con un backup de descripcion fresco: el primer
    objeto daba {id, descriptionHtml}, `extra` quedaba vacio y `status`/`handle`
    del segundo nunca se miraban."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation { %s %s }" % (F1_BUENO, F1_MALO)}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el segundo productUpdate paso escondido detras del primero: {why}"
    assert "status" in why and "handle" in why, \
        f"tiene que bloquear por ALCANCE DE CAMPOS, no de casualidad: {why}"

def test_el_orden_de_los_objetos_no_cambia_la_decision(tmp_path):
    """EL TELL del hallazgo: el MISMO documento, el MISMO efecto sobre la tienda,
    y el guard viejo decidia distinto segun cual objeto viniera primero. Este
    control existe para que el test de arriba no pueda pasar por el motivo viejo."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation { %s %s }" % (F1_MALO, F1_BUENO)}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", why
    assert "status" in why and "handle" in why, why


# --- F3: el default invertido -----------------------------------------------
# `asuntos` solo conocia discount*, metafieldsSet y product*. Todo lo demas
# llegaba al `return allow` final. Ojo: `inventorySetQuantities` SI estaba en la
# blocklist, pero el chequeo es por substring y `inventorySetOnHandQuantities`
# no la contiene.

F3_NO_ENUMERADAS = [
    "inventorySetOnHandQuantities", "inventoryMoveQuantities", "themeFilesUpsert",
    "customerUpdate", "orderUpdate", "webhookSubscriptionCreate",
    "giftCardCreate", "publicationUpdate",
]

@pytest.mark.parametrize("mut", F3_NO_ENUMERADAS)
def test_mutacion_no_enumerada_bloquea(tmp_path, mut):
    """Con backup de descripcion fresco, que es el estado normal mientras el
    skill trabaja. Las ocho pasaban sueltas."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": f'mutation {{ {mut}(input: {{id: "gid://shopify/Foo/1"}}) {{ userErrors {{ field }} }} }}'}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"{mut} paso suelta: {why}"
    assert mut.lower() in why.lower(), f"tiene que nombrar al infractor: {why}"


INVENTARIO_A_CERO = ('inventorySetOnHandQuantities(input: {reason: "correction", setQuantities: '
                     '[{inventoryItemId: "gid://shopify/InventoryItem/1", '
                     'locationId: "gid://shopify/Location/1", quantity: 0}]}) { userErrors { field } }')

def test_inventario_montado_sobre_una_descripcion_legitima_bloquea(tmp_path):
    """La descripcion de adelante es real y su backup tambien. El vehiculo era
    justamente eso: la operacion legitima que abre la puerta."""
    write_description_backup(tmp_path)
    p = {"tool_name": T_GQL, "tool_input": {
        "query": 'mutation { productUpdate(input: {id: "gid://shopify/Product/1", '
                 'descriptionHtml: "<p>nueva</p>"}) { product { id } } %s }' % INVENTARIO_A_CERO}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el stock a cero viajo con la descripcion: {why}"
    assert "inventorysetonhandquantities" in why.lower(), why

def test_inventario_montado_sobre_un_deactivate_bloquea(tmp_path):
    """El peor de los dos: el deactivate no exige NI politica NI backup (§9.8),
    asi que el stock a cero pasaba sin ningun archivo en el repo."""
    p = {"tool_name": T_GQL, "tool_input": {
        "query": "mutation { %s %s }" % (DEACTIVATE, INVENTARIO_A_CERO)}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "block", f"el stock a cero paso sin politica y sin backup: {why}"
    assert "inventorysetonhandquantities" in why.lower(), why

def test_deactivate_solo_sigue_pasando_sin_politica_ni_backup(tmp_path):
    """§9.8 despues de invertir el default. Propiedad PORTANTE del camino de
    compensacion: si sacar una oferta dependiera de una politica o de un backup,
    dejaria de estar disponible justo en el momento en que hace falta."""
    assert not list(tmp_path.glob("**/*.json")), "el escenario tiene que estar vacio"
    p = {"tool_name": T_GQL, "tool_input": {"query": "mutation { %s }" % DEACTIVATE}}
    d, why = bg.evaluate(p, tmp_path, time.time())
    assert d == "allow", why

def test_documento_sin_query_legible_bloquea(tmp_path):
    """Vacio es DESCONOCIDO: sin documento no se sabe que se ejecuta."""
    write_description_backup(tmp_path)
    for ti in ({"variables": {"input": {"id": PID, "descriptionHtml": "x"}}}, {}, "oops"):
        d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": ti}, tmp_path, time.time())
        assert d == "block", f"{ti} paso: {why}"


def test_root_fields_ignora_los_campos_anidados(tmp_path):
    """El extractor tiene que ver el root field y NO los campos de la seleccion
    ni las keys de los argumentos; si contara de mas, sobre-bloquearia el unico
    camino legitimo del v1."""
    q = ('mutation ($input: ProductInput!) { b: productUpdate(input: $input) '
         '{ product { id seo { title } } userErrors { field message } } }')
    assert bg._root_mutation_fields(q) == ["productupdate"]
    assert bg._root_mutation_fields(
        'mutation { productUpdate(input: {id: "x", descriptionHtml: "{ status: DRAFT }"}) { product { id } } }'
    ) == ["productupdate"]


def test_inline_payload_blocks_with_the_RIGHT_reason(tmp_path):
    """Bloquear no alcanza: tiene que bloquear diciendo la verdad.

    `_discount_input` solo lee `variables`. Con el payload inline devuelve {},
    que es un dict, asi que el isinstance pasaba y caia en el chequeo de endsAt:
    respondia "toda oferta necesita fecha de fin" sobre un documento que tiene
    el endsAt a la vista. Quien lo leyera agregaria un endsAt que ya estaba.
    """
    policy(tmp_path); write_deal_backup(tmp_path)
    q = ('mutation { discountAutomaticBasicCreate(automaticBasicDiscount:{'
         'title:"x", startsAt:"2026-07-20T00:00:00Z", endsAt:"2026-08-20T00:00:00Z", '
         'customerGets:{value:{percentage:0.10}, '
         'items:{products:{productsToAdd:["gid://shopify/Product/1"]}}}'
         '}){automaticDiscountNode{id}} }')
    d, why = bg.evaluate({"tool_name": T_GQL, "tool_input": {"query": q}}, tmp_path, time.time())
    assert d == "block"
    assert "variables" in why, f"el motivo tiene que senalar las variables, dio: {why}"
    assert "fecha de fin" not in why, f"motivo enganoso: {why}"
