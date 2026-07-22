"""Tests del guard para las 9 familias de "contenido" (uno por uno, estilo wigy).

Todas cosméticas del registro `COSMETIC_METAFIELDS`: sizechart, announce, lowstock,
beforeafter, gallery, video, compare, steps, benefits. Backup propio `kind`, sin
techo. Las que llevan URL usan `_ok_url` (https, sin inyección).
"""
import json, time, importlib.util
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "backup_guard.py"
_spec = importlib.util.spec_from_file_location("backup_guard", SPEC)
guard = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(guard)

GID = "gid://shopify/Product/9"
SHOP = "gid://shopify/Shop/1"
IMG = "https://cdn.shopify.com/s/files/1/foto.jpg"


def _ts(now):
    return guard.datetime.fromtimestamp(now).isoformat(timespec="seconds")


def _bk(root, gid, kind):
    tail = gid.split("/")[-1]
    d = root / "clients" / "blunua" / "backups" / kind
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tail}-x.json").write_text(json.dumps(
        {"kind": kind, "productId": gid, "previous": None, "ts": _ts(time.time())}), encoding="utf-8")


def _p(key, data, owner=GID):
    return {"variables": {"m": [{"ownerId": owner, "namespace": "worker",
            "key": key, "type": "json", "value": json.dumps(data)}]}}


def _ok(key, data, owner=GID):
    """Escribe backup y corre _check_cosmetic; devuelve la decisión."""
    return None  # placeholder replaced per-test


# ---- datos válidos por familia ----
VALID = {
    "sizechart": {"version": 1, "title": "Medidas", "rows": [["6", "16,5 mm"], ["7", "17,3 mm"]]},
    "announce": {"version": 1, "text": "Envío gratis +$80.000", "link": "https://tienda.com/envios"},
    "lowstock": {"version": 1, "threshold": 5, "text": "Quedan pocas"},
    "beforeafter": {"version": 1, "before": IMG, "after": IMG, "beforeLabel": "Antes"},
    "gallery": {"version": 1, "images": [IMG, IMG]},
    "video": {"version": 1, "url": "https://youtube.com/watch?v=abc", "label": "Ver video"},
    "compare": {"version": 1, "usLabel": "Nosotros", "themLabel": "Otros",
                "rows": [["Garantía", "Sí", "No"]]},
    "steps": {"version": 1, "items": ["Limpiá la superficie", "Aplicá el producto"]},
    "benefits": {"version": 1, "items": ["Hipoalergénico", "Ajuste gratis"]},
}

SHOP_SCOPED = {"announce", "video"}


def test_all_families_registered():
    for k in VALID:
        assert k in guard.COSMETIC_METAFIELDS, f"{k} no está en el registro"


def test_all_accept_valid_with_backup(tmp_path):
    for k, data in VALID.items():
        owner = SHOP if k in SHOP_SCOPED else GID
        _bk(tmp_path, owner, k)
        ok, why = guard._check_cosmetic(k, _p(k, data, owner), tmp_path, time.time())
        assert ok == "allow", f"{k}: {why}"


def test_all_block_missing_backup(tmp_path):
    for k, data in VALID.items():
        owner = SHOP if k in SHOP_SCOPED else GID
        ok, _ = guard._check_cosmetic(k, _p(k, data, owner), tmp_path, time.time())
        assert ok == "block", f"{k} pasó sin backup"


def test_all_block_unknown_key(tmp_path):
    for k, data in VALID.items():
        owner = SHOP if k in SHOP_SCOPED else GID
        _bk(tmp_path, owner, k)
        bad = dict(data); bad["evil"] = 1
        ok, _ = guard._check_cosmetic(k, _p(k, bad, owner), tmp_path, time.time())
        assert ok == "block", f"{k} no bloqueó una clave desconocida"


def test_url_families_block_non_https(tmp_path):
    # gallery / video / beforeafter rechazan URLs no-https (anti inyección).
    _bk(tmp_path, GID, "gallery")
    ok, _ = guard._check_cosmetic("gallery", _p("gallery",
        {"version": 1, "images": ["javascript:alert(1)"]}), tmp_path, time.time())
    assert ok == "block"
    _bk(tmp_path, SHOP, "video")
    ok2, _ = guard._check_cosmetic("video", _p("video",
        {"version": 1, "url": "http://insecuro.com/v"}, owner=SHOP), tmp_path, time.time())
    assert ok2 == "block"


def test_text_families_block_angle(tmp_path):
    _bk(tmp_path, GID, "benefits")
    ok, _ = guard._check_cosmetic("benefits", _p("benefits",
        {"version": 1, "items": ["<script>x</script>"]}), tmp_path, time.time())
    assert ok == "block"


def test_lowstock_blocks_bad_threshold(tmp_path):
    _bk(tmp_path, GID, "lowstock")
    ok, _ = guard._check_cosmetic("lowstock", _p("lowstock",
        {"version": 1, "threshold": 0, "text": "x"}), tmp_path, time.time())
    assert ok == "block"


def test_cross_discriminator(tmp_path):
    # un backup de 'steps' no habilita un write de plata ni de otra familia
    _bk(tmp_path, GID, "steps")
    ok, _ = guard._covering_deal_backup(tmp_path, GID, time.time())
    assert ok is False
    ok2, _ = guard._covering_cosmetic_backup("benefits", tmp_path, GID, time.time())
    assert ok2 is False
