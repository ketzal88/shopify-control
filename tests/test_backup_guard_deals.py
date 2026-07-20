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
