import sys, json, subprocess, importlib.util
from pathlib import Path
import pytest

HOOKS = Path(__file__).resolve().parents[1] / ".claude" / "hooks"
FIX = Path(__file__).resolve().parent / "fixtures"

# Cargar el módulo por ruta (mismo patrón que test_description_lint / test_backup_guard,
# evita ensuciar sys.path en la sesión pytest compartida).
_spec = importlib.util.spec_from_file_location("product_csv", HOOKS / "product_csv.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)

def test_read_rows_handles_cp1252_fallback():
    rows, cols = pc.read_rows(FIX / "w3_mini.csv")
    assert "Handle" in cols
    # el valor con byte cp1252 se leyó sin romper y sin '�'
    joined = json.dumps(rows, ensure_ascii=False)
    assert "�" not in joined
    assert any("Diseño" in (r.get("Tags","") or "") or "Diseño" in (r.get("Type","") or "") for r in rows)


def test_group_products_multirow():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    # el producto de 2 variantes quedó en UN grupo con 2 filas
    assert len(groups) == 2
    sizes = sorted(len(g) for g in groups.values())
    assert sizes == [1, 2]


def test_group_products_drops_orphan_leading_row():
    # fila con Handle vacío y sin padre previo (nunca hubo un Handle no vacío antes): se ignora
    rows = [
        {"Handle": "", "Title": ""},
        {"Handle": "producto-x", "Title": "Producto X"},
    ]
    groups = pc.group_products(rows)
    assert list(groups.keys()) == ["producto-x"]
    assert len(groups["producto-x"]) == 1


def test_extract_variants_and_options():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    handle = next(h for h, g in groups.items() if len(g) == 2)
    options, variants = pc.extract_variants(groups[handle])
    assert options and options[0]["name"] == "Color"
    assert options[0]["values"] == ["Plateado", "Dorado"]   # los dos colores del fixture
    assert len(variants) == 2
    assert all("sku" in v and "optionValues" in v for v in variants)


def test_extract_images_url_and_variant():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    handle = next(h for h, g in groups.items() if len(g) == 2)
    images = pc.extract_images(groups[handle])
    assert isinstance(images, list)
    for img in images:
        assert set(img) >= {"url", "position", "alt", "variantSku"}
        assert img["url"]   # F1 solo reporta imágenes que el CSV trae (con URL)


def test_extract_images_variant_image_branch():
    # fila sintética que SOLO trae Variant Image (no Image Src): ejercita el branch
    # de imagen-por-variante, que el fixture w3_mini.csv no cubre por sí solo.
    group_rows = [{
        "Image Src": "", "Image Position": "", "Image Alt Text": "",
        "Variant Image": "https://cdn.shopify.com/s/files/1/0000/0001/products/v1.jpg",
        "Variant SKU": "SKU-V1",
    }]
    images = pc.extract_images(group_rows)
    assert len(images) == 1
    assert images[0]["url"] == "https://cdn.shopify.com/s/files/1/0000/0001/products/v1.jpg"
    assert images[0]["variantSku"] == "SKU-V1"


@pytest.mark.parametrize("raw,cents", [
    ("12.50", 1250), ("1000", 100000), ("1.234,56", None), ("", None),
    ("abc", None), ("0", 0), ("9.9", 990),
    # edge cases que F2 va a depender de que sigan devolviendo esto:
    (".", None), ("12.", 1200), ("-5", None), ("1.2.3", None), ("  12.50  ", 1250),
])
def test_price_to_cents(raw, cents):
    assert pc.price_to_cents(raw) == cents


def test_build_products_have_status_and_motivos():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    products = pc.build_products(pc.group_products(rows))
    assert all("status" in p and "motivos" in p for p in products)


def test_validate_flags_sku_already_seen():
    # unidad directa: un SKU que YA está en seen_skus (venga de donde venga) se rechaza.
    motivos = pc._validate(
        {"title": "T", "options": [], "variants": [{"sku": "X", "priceCents": 100, "optionValues": []}]},
        seen_skus={"X"},
    )
    assert any("repetido" in m.lower() for m in motivos)


def test_build_products_dedup_across_different_handles():
    # dedup real: DOS productos DISTINTOS (handles distintos) que comparten un SKU.
    # group_products los agrupa por Handle, así que quedan como dos productos separados
    # (a diferencia de duplicar las mismas filas, que solo repite el MISMO producto).
    rows = [
        {"Handle": "producto-a", "Title": "Producto A", "Variant SKU": "DUP-1", "Variant Price": "10.00"},
        {"Handle": "producto-b", "Title": "Producto B", "Variant SKU": "DUP-1", "Variant Price": "20.00"},
    ]
    products = pc.build_products(pc.group_products(rows))
    assert len(products) == 2
    by_handle = {p["handle"]: p for p in products}
    assert by_handle["producto-a"]["status"] == "crear"
    assert by_handle["producto-b"]["status"] == "rechazado"
    assert any("repetido" in m.lower() for m in by_handle["producto-b"]["motivos"])


def test_build_products_empty_input_gives_zero_counts():
    products = pc.build_products(pc.group_products([]))
    assert products == []
    summary = pc.summarize(products)
    assert summary["counts"] == {"total": 0, "crear": 0, "rechazado": 0}


def test_reject_missing_title_or_variant():
    p = pc._validate({"title": "", "variants": [{"sku": "X", "priceCents": 100, "optionValues": []}],
                      "options": []}, seen_skus=set())
    assert p and "título" in " ".join(p).lower()


def test_cli_outputs_json():
    out = subprocess.run(
        [sys.executable, str(HOOKS / "product_csv.py"), str(FIX / "w3_mini.csv")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["counts"]["total"] == 2
    assert data["products"]  # no vacío: el fixture trae 2 productos
    assert {p["status"] for p in data["products"]} <= {"crear", "rechazado"}


REAL = Path(__file__).resolve().parents[1] / "clients" / "blunua" / "backups" / "upload" / "products_export_1 - productsUP.csv"

@pytest.mark.skipif(not REAL.exists(), reason="export real no disponible")
def test_real_export_parses_to_678_products():
    rows, cols = pc.read_rows(REAL)
    assert len(cols) == 85
    products = pc.build_products(pc.group_products(rows))
    assert len(products) == 678
    # el archivo no rompe el parser y ningún grupo queda sin variantes
    assert all(p["variants"] for p in products if p["status"] == "crear")
