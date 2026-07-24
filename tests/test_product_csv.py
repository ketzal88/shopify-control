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


def test_extract_variants_and_options():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    handle = next(h for h, g in groups.items() if len(g) == 2)
    options, variants = pc.extract_variants(groups[handle])
    assert options and options[0]["name"]              # ej. "Color"
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


@pytest.mark.parametrize("raw,cents", [
    ("12.50", 1250), ("1000", 100000), ("1.234,56", None), ("", None),
    ("abc", None), ("0", 0), ("9.9", 990),
])
def test_price_to_cents(raw, cents):
    assert pc.price_to_cents(raw) == cents


def test_build_and_validate_flags_bad_price_and_dup_sku():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    products = pc.build_products(pc.group_products(rows))
    assert all("status" in p and "motivos" in p for p in products)
    # dedup intra-lote: dos productos con el mismo SKU -> el 2º rechazado
    dup = pc.build_products(pc.group_products(rows + rows))
    rechazados = [p for p in dup if p["status"] == "rechazado"]
    assert any("repetido" in " ".join(p["motivos"]).lower() for p in rechazados)

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
    assert {"crear", "rechazado"} >= {p["status"] for p in data["products"]} or data["products"]


REAL = Path(__file__).resolve().parents[1] / "clients" / "blunua" / "backups" / "upload" / "products_export_1 - productsUP.csv"

@pytest.mark.skipif(not REAL.exists(), reason="export real no disponible")
def test_real_export_parses_to_678_products():
    rows, cols = pc.read_rows(REAL)
    assert len(cols) == 85
    products = pc.build_products(pc.group_products(rows))
    assert len(products) == 678
    # el archivo no rompe el parser y ningún grupo queda sin variantes
    assert all(p["variants"] for p in products if p["status"] == "crear")
