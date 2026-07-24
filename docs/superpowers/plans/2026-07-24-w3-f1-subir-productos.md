# W3 · F1 — Parser + dedup + preview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leer un CSV nativo de export de Shopify, agruparlo en productos, validarlo y marcar cuáles crear / cuáles rechazar — sin escribir NADA en Shopify. Termina en un preview sin jerga.

**Architecture:** Un CLI Python (`.claude/hooks/product_csv.py`) hace el trabajo determinístico y testeable (leer con encoding robusto, agrupar filas multi-línea por `Handle`, extraer variantes/imágenes, validar, detectar duplicados DENTRO del lote) y emite JSON por stdout. La parte que necesita la tienda viva (dedup contra el catálogo real vía `search_products`) y la que necesita criterio (generar copy, armar el preview) las hace el skill `subir-productos` orquestando el CLI + el connector. F1 no toca `backup_guard` ni crea productos.

**Tech Stack:** Python 3 (stdlib `csv`, `argparse`, `json`, `re`), pytest. Mismo patrón que `description_lint.py` (CLI) y `tests/test_*.py`.

**Spec:** `docs/superpowers/specs/2026-07-24-subir-productos-w3-design.md` (§3 pasos 1-6, §4, §6, §8).

---

## File Structure

- **Create:** `.claude/hooks/product_csv.py` — el parser/validador. Funciones puras + un `main()` CLI. Sin dependencias fuera de la stdlib (igual que `description_lint.py`).
- **Create:** `tests/test_product_csv.py` — pytest de cada función pura + el CLI + un smoke test contra el export real.
- **Create:** `tests/fixtures/w3_mini.csv` — fixture chico y sintético (2-3 productos, multi-fila, con un byte no-UTF8 en un header) para los tests unitarios rápidos.
- **Create:** `.claude/skills/subir-productos/SKILL.md` — el procedimiento F1 (paso 0 → recibir → correr el CLI → dedup vivo → generar copy → preview). Crece en F2/F3.
- **Fixture real (solo lectura):** `clients/blunua/backups/upload/products_export_1 - productsUP.csv` (678 productos) para el smoke test de integración.

**Modelo interno** (contrato entre el CLI y el skill), un dict por producto:
```
{ "handle","title","productType","tags":[],
  "options":[{"name","values":[]}],
  "variants":[{"sku","priceCents"|null,"optionValues":[],"barcode","grams"}],
  "images":[{"url"|null,"position","alt","variantSku"|null}],
  "csvBody","csvSeoTitle","csvSeoDescription",
  "status":"crear"|"rechazado", "motivos":[] }
```

---

## Task 1: Lector de CSV robusto al encoding

**Files:**
- Create: `.claude/hooks/product_csv.py`
- Create: `tests/fixtures/w3_mini.csv`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Crear el fixture chico** (`tests/fixtures/w3_mini.csv`)

Header nativo mínimo (subconjunto de las 85 columnas) + 3 filas: un producto con 2 variantes en 2 filas, y otro producto de 1 fila. **La fila de continuación repite el `Handle`** (como hace el export real de Shopify) y deja `Title` vacío, para que el test ejercite el mismo camino de agrupado que el archivo de 678. Incluir en un valor un carácter no-ASCII (`Diseño`) guardado en **cp1252** para forzar el fallback. (El agente lo genera con un pequeño script que escribe bytes cp1252; o a mano si el editor lo permite.)

Columnas del fixture: `Handle,Title,Type,Tags,Option1 Name,Option1 Value,Variant SKU,Variant Price,Variant Barcode,Variant Grams,Image Src,Image Position,Image Alt Text,Variant Image,Body (HTML),SEO Title,SEO Description,Status`

- [ ] **Step 2: Escribir el test que falla**

```python
# tests/test_product_csv.py
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
```

- [ ] **Step 3: Ejecutar el test para verificar que falla**

Run: `python -m pytest tests/test_product_csv.py::test_read_rows_handles_cp1252_fallback -q`
Expected: FAIL (`AttributeError: module 'product_csv' has no attribute 'read_rows'` o ImportError).

- [ ] **Step 4: Implementar `read_rows`**

```python
# .claude/hooks/product_csv.py
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
```

- [ ] **Step 5: Ejecutar el test para verificar que pasa**

Run: `python -m pytest tests/test_product_csv.py::test_read_rows_handles_cp1252_fallback -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add .claude/hooks/product_csv.py tests/test_product_csv.py tests/fixtures/w3_mini.csv
git commit -m "feat(w3): lector de CSV robusto al encoding (F1)"
```

---

## Task 2: Agrupar filas multi-línea por Handle

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
def test_group_products_multirow():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    # el producto de 2 variantes quedó en UN grupo con 2 filas
    assert len(groups) == 2
    sizes = sorted(len(g) for g in groups.values())
    assert sizes == [1, 2]
```

- [ ] **Step 2: Verificar que falla**

Run: `python -m pytest tests/test_product_csv.py::test_group_products_multirow -q` → FAIL.

- [ ] **Step 3: Implementar `group_products`**

```python
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
```

- [ ] **Step 4: Verificar que pasa** → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(w3): agrupar filas multi-línea por Handle (F1)"
```

---

## Task 3: Extraer opciones y variantes

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
def test_extract_variants_and_options():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    handle = next(h for h, g in groups.items() if len(g) == 2)
    options, variants = pc.extract_variants(groups[handle])
    assert options and options[0]["name"]              # ej. "Color"
    assert len(variants) == 2
    assert all("sku" in v and "optionValues" in v for v in variants)
```

- [ ] **Step 2: Verificar que falla** → FAIL.

- [ ] **Step 3: Implementar `extract_variants`**

```python
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
```

- [ ] **Step 4: Verificar que pasa** → PASS.

- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): extraer opciones y variantes (F1)"`

---

## Task 4: Extraer imágenes (URL o marca de local)

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
def test_extract_images_url_and_variant():
    rows, _ = pc.read_rows(FIX / "w3_mini.csv")
    groups = pc.group_products(rows)
    handle = next(h for h, g in groups.items() if len(g) == 2)
    images = pc.extract_images(groups[handle])
    assert isinstance(images, list)
    for img in images:
        assert set(img) >= {"url", "position", "alt", "variantSku"}
```

- [ ] **Step 2: Verificar que falla** → FAIL.

- [ ] **Step 3: Implementar `extract_images`**

```python
def extract_images(group_rows):
    """Imágenes del producto. Image Src → imagen de producto; Variant Image →
    imagen de la variante de esa fila (por su SKU). url=None marca 'buscar local
    por SKU' (lo resuelve F2). No sube nada."""
    images = []
    for row in group_rows:
        src = (row.get("Image Src") or "").strip()
        if src:
            images.append({
                "url": src,
                "position": (row.get("Image Position") or "").strip(),
                "alt": (row.get("Image Alt Text") or "").strip(),
                "variantSku": None,
            })
        vimg = (row.get("Variant Image") or "").strip()
        vsku = (row.get("Variant SKU") or "").strip()
        if vimg:
            images.append({"url": vimg, "position": "", "alt": "", "variantSku": vsku or None})
        elif vsku:
            # sin URL: F2 la buscará en la carpeta local por SKU
            images.append({"url": None, "position": "", "alt": "", "variantSku": vsku})
    return images
```

- [ ] **Step 4: Verificar que pasa** → PASS.

- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): extraer imágenes URL/local (F1)"`

---

## Task 5: Normalizar precio a centavos

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
import pytest

@pytest.mark.parametrize("raw,cents", [
    ("12.50", 1250), ("1000", 100000), ("1.234,56", None), ("", None),
    ("abc", None), ("0", 0), ("9.9", 990),
])
def test_price_to_cents(raw, cents):
    assert pc.price_to_cents(raw) == cents
```

- [ ] **Step 2: Verificar que falla** → FAIL.

- [ ] **Step 3: Implementar `price_to_cents`**

```python
def price_to_cents(raw):
    """'12.50' -> 1250. El export usa punto decimal (formato Shopify). Formatos
    ambiguos (coma decimal, miles) -> None: no adivinamos precio, se rechaza el
    producto y el cliente lo corrige. Vacío/no numérico -> None."""
    if not isinstance(raw, str):
        return None
    s = raw.strip()
    if not s:
        return None
    try:
        # solo dígitos y un punto decimal; nada de comas ni separadores de miles
        if not all(c.isdigit() or c == "." for c in s) or s.count(".") > 1:
            return None
        return round(float(s) * 100)
    except (TypeError, ValueError):
        return None
```

- [ ] **Step 4: Verificar que pasa** → PASS.

- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): normalizar precio a centavos (F1)"`

---

## Task 6: Construir el producto + validar + dedup intra-lote

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
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
```

- [ ] **Step 2: Verificar que falla** → FAIL.

- [ ] **Step 3: Implementar `build_products` + `_validate`**

```python
def _validate(prod, seen_skus):
    """Lista de motivos de rechazo (vacía = ok). Estructural + dedup intra-lote.
    Piso/techo de precio y dedup contra la tienda VIVA NO van acá (el guard y el
    skill respectivamente); acá solo lo que se ve desde el CSV."""
    motivos = []
    if not (prod.get("title") or "").strip():
        motivos.append("le falta el título")
    variants = prod.get("variants") or []
    if not variants:
        motivos.append("no tiene ninguna variante")
    n_opts = len(prod.get("options") or [])
    for v in variants:
        if v.get("priceCents") is None:
            motivos.append(f"precio inválido o vacío (SKU {v.get('sku') or '—'})")
        if not v.get("sku"):
            motivos.append("hay una variante sin código (SKU)")
        elif v["sku"] in seen_skus:
            motivos.append(f"el código {v['sku']} está repetido en el archivo")
        # consistencia de opciones: cada variante con un valor por opción declarada
        if n_opts and len([x for x in v.get("optionValues", []) if x]) < n_opts:
            motivos.append(f"a la variante {v.get('sku') or '—'} le falta una opción")
    return motivos


def build_products(groups):
    """Lista de productos del modelo interno, ya validados y con status."""
    products, seen_skus = [], set()
    for handle, group_rows in groups.items():
        options, variants = extract_variants(group_rows)
        for v in variants:
            v["priceCents"] = price_to_cents(v.pop("priceRaw", ""))
        head = group_rows[0]
        prod = {
            "handle": handle,
            "title": (head.get("Title") or "").strip(),
            "productType": (head.get("Type") or "").strip(),
            "tags": [t.strip() for t in (head.get("Tags") or "").split(",") if t.strip()],
            "options": options,
            "variants": variants,
            "images": extract_images(group_rows),
            "csvBody": (head.get("Body (HTML)") or "").strip(),
            "csvSeoTitle": (head.get("SEO Title") or "").strip(),
            "csvSeoDescription": (head.get("SEO Description") or "").strip(),
        }
        motivos = _validate(prod, seen_skus)
        for v in variants:
            if v.get("sku"):
                seen_skus.add(v["sku"])
        prod["status"] = "rechazado" if motivos else "crear"
        prod["motivos"] = motivos
        products.append(prod)
    return products
```

- [ ] **Step 4: Verificar que pasa** → PASS.

- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): construir producto, validar y dedup intra-lote (F1)"`

---

## Task 7: CLI `main` (JSON por stdout)

**Files:**
- Modify: `.claude/hooks/product_csv.py`
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla** (corre el CLI como subproceso)

```python
def test_cli_outputs_json():
    out = subprocess.run(
        [sys.executable, str(HOOKS / "product_csv.py"), str(FIX / "w3_mini.csv")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert out.returncode == 0
    data = json.loads(out.stdout)
    assert data["counts"]["total"] == 2
    assert {"crear", "rechazado"} >= {p["status"] for p in data["products"]} or data["products"]
```

- [ ] **Step 2: Verificar que falla** → FAIL.

- [ ] **Step 3: Implementar `main`**

```python
def summarize(products):
    counts = {"total": len(products),
              "crear": sum(1 for p in products if p["status"] == "crear"),
              "rechazado": sum(1 for p in products if p["status"] == "rechazado")}
    return {"counts": counts, "products": products}


def main(argv=None):
    ap = argparse.ArgumentParser(description="Parser del CSV nativo de Shopify (W3 F1, no escribe nada).")
    ap.add_argument("csv_path")
    args = ap.parse_args(argv)
    rows, _cols = read_rows(Path(args.csv_path))
    products = build_products(group_products(rows))
    print(json.dumps(summarize(products), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Verificar que pasa** → PASS. Correr toda la suite: `python -m pytest tests/test_product_csv.py -q`.

- [ ] **Step 5: Commit** → `git add -A && git commit -m "feat(w3): CLI del parser con salida JSON (F1)"`

---

## Task 8: Smoke test contra el export real (678 productos)

**Files:**
- Test: `tests/test_product_csv.py`

- [ ] **Step 1: Test que falla**

```python
REAL = Path(__file__).resolve().parents[1] / "clients" / "blunua" / "backups" / "upload" / "products_export_1 - productsUP.csv"

@pytest.mark.skipif(not REAL.exists(), reason="export real no disponible")
def test_real_export_parses_to_678_products():
    rows, cols = pc.read_rows(REAL)
    assert len(cols) == 85
    products = pc.build_products(pc.group_products(rows))
    assert len(products) == 678
    # el archivo no rompe el parser y ningún grupo queda sin variantes
    assert all(p["variants"] for p in products if p["status"] == "crear")
```

- [ ] **Step 2: Verificar** — con el archivo presente debe PASAR ya (el código de Tasks 1-7 lo cubre). Si falla, es señal de un caso real no contemplado (encoding, columnas): arreglar el parser, no el test.

Run: `python -m pytest tests/test_product_csv.py -q`
Expected: todos PASS (o el smoke se SKIPea si el archivo no está).

- [ ] **Step 3: Commit** → `git add -A && git commit -m "test(w3): smoke test del parser contra el export real de 678 (F1)"`

---

## Task 9: SKILL.md de `subir-productos` (procedimiento F1)

**Files:**
- Create: `.claude/skills/subir-productos/SKILL.md`

- [ ] **Step 1: Escribir el SKILL.md** siguiendo el molde de `mejorar-descripcion/SKILL.md` (mismo tono, paso 0 idéntico, reglas duras, sin jerga). Secciones:
  - **Frontmatter** `name: subir-productos` + `description:` (cuándo usarlo: "el cliente quiere subir productos nuevos desde un archivo").
  - **Reglas duras:** F1 NO escribe nada en Shopify (termina en el preview); sin jerga; registro del cliente; el gate de crear recién llega en F2.
  - **Paso 0** (idéntico a los demás: confirmar cliente + `get-shop-info` vs `connection.md`, abortar si no coincide).
  - **Flujo F1:**
    1. RECIBIR: pedir el archivo y la carpeta de fotos en lenguaje natural → dos paths.
    2. PARSEAR: correr `python .claude/hooks/product_csv.py "<path>"`, leer el JSON.
    3. DEDUP VIVO: para cada producto `status:crear`, `Shopify:search_products` por `handle:<h>` y por cada `sku:<s>`; si hay match, pasar a "ya existe".
    4. GENERAR COPY: por cada producto que sigue en `crear`, generar descripción + SEO con el molde de `store-standards §3`, keywords `§4`, **humanizer**, y correr `description_lint.py`. No mostrar nada que no pase el linter.
    5. PREVIEW: índice ("N para crear, X ya existen, Y con problemas") + detalle por producto (nombre, precio, variantes, descripción generada, cómo se ve en Google, estado de fotos). Sin jerga. **Termina acá** — F1 no crea.
  - **Si el cliente pide crear/publicar ya:** decir que en F1 solo se prepara y revisa; crear llega en la próxima fase. Registrar en worklog. (Guion neutro, adaptar por `store-standards §2`.)
  - **Nota interna:** nunca nombrar el CLI, el JSON ni los campos frente al cliente.

- [ ] **Step 2: Verificar el skill a mano** — que el paso 0 y el "no escribe nada" estén explícitos y que ninguna instrucción invoque un write de Shopify.

- [ ] **Step 3: Commit** → `git add .claude/skills/subir-productos/SKILL.md && git commit -m "feat(w3): skill subir-productos, procedimiento F1 (parser+dedup+preview)"`

---

## Cierre de F1

- [ ] Correr toda la suite del repo: `python -m pytest -q` (F1 no debe romper ningún test existente).
- [ ] Confirmar que F1 no tocó `backup_guard.py`, `settings.json` ni creó ningún producto: es 100% lectura + preview.
- [ ] F2 (clase `create` + imágenes + `backup_guard`) y F3 (clase `publish`) son planes separados, cada uno con su spec-section (§7) como referencia.
