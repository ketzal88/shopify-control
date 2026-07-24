import sys, json, subprocess, importlib.util
from pathlib import Path

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
