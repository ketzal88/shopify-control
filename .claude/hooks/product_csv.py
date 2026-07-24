"""Parser/validador del CSV nativo de export de Shopify para W3 (subir-productos).

NO escribe nada en Shopify. Lee un CSV, agrupa las filas multi-línea por Handle,
extrae variantes/imágenes, valida y marca cada producto como 'crear' o 'rechazado'.
El dedup contra la tienda VIVA lo hace el skill con search_products (esto solo
detecta duplicados DENTRO del lote). Emite JSON por stdout.

    python .claude/hooks/product_csv.py "ruta/al.csv"
"""
import argparse
import csv
import json
import sys
from pathlib import Path

# El export real no es UTF-8 limpio (headers con mojibake). Orden de intento:
_ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")


def read_rows(path):
    """(rows, fieldnames). Prueba encodings hasta que uno parsee sin UnicodeDecodeError.
    latin-1 nunca falla (mapea todo byte), así que es el piso y garantiza retorno."""
    last = None
    for enc in _ENCODINGS:
        try:
            with open(path, encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                return rows, (reader.fieldnames or [])
        except UnicodeDecodeError as e:
            last = e
            continue
    raise last  # solo si hasta latin-1 falló (no debería)


def group_products(rows):
    """dict ordenado {handle: [filas...]}. Las filas de continuación (mismo Handle,
    Title vacío) se pegan al grupo del último Handle no vacío. Un Handle vacío sin
    padre previo se descarta (fila corrupta)."""
    groups = {}
    current = None
    for row in rows:
        handle = (row.get("Handle") or "").strip()
        if handle:
            current = handle
            groups.setdefault(handle, []).append(row)
        elif current is not None:
            groups[current].append(row)
        # handle vacío sin current previo: se ignora
    return groups


def extract_variants(group_rows):
    """(options, variants). options = [{name, values[]}] de Option1/2/3 Name/Value.
    Una variante por fila que traiga Variant SKU o algún Option Value."""
    option_names = []
    for i in (1, 2, 3):
        name = (group_rows[0].get(f"Option{i} Name") or "").strip()
        if name:
            option_names.append((i, name))

    variants, values_by_opt = [], {i: [] for i, _ in option_names}
    for row in group_rows:
        opt_vals = []
        for i, _ in option_names:
            val = (row.get(f"Option{i} Value") or "").strip()
            opt_vals.append(val)
            if val and val not in values_by_opt[i]:
                values_by_opt[i].append(val)
        sku = (row.get("Variant SKU") or "").strip()
        if sku or any(opt_vals):
            variants.append({
                "sku": sku,
                "priceRaw": (row.get("Variant Price") or "").strip(),
                "optionValues": opt_vals,
                "barcode": (row.get("Variant Barcode") or "").strip(),
                "grams": (row.get("Variant Grams") or "").strip(),
            })
    options = [{"name": name, "values": values_by_opt[i]} for i, name in option_names]
    return options, variants
