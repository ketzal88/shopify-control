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
