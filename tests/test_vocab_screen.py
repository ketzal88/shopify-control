"""Screen de vocabulario (W4-2): `refrescar-estandares` corre description_lint.py
en modo SOLO-VOCABULARIO sobre cada keyword propuesta por el Brain, para descartar
mecánicamente las que declaran un material falso ("oro"/"plata"/chapado), lujo-vacío,
claims médicos o voseo — ANTES del gate del operador.

Modo solo-vocabulario = `--min 1 --max 9999 --no-geo` y SIN `--keywords`: así las
comprobaciones de longitud ("muy corta") y de bloque GEO ("faltan preguntas") NO
disparan sobre una keyword corta; solo quedan los chequeos de §2 (material/lujo/
médico/voseo). Los flags coinciden con el CLI real de description_lint.py.
"""
import subprocess
import sys
from pathlib import Path

LINT = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "description_lint.py"


def _screen(text):
    return subprocess.run(
        [sys.executable, str(LINT), "--min", "1", "--max", "9999", "--no-geo"],
        input=text, capture_output=True, text=True, encoding="utf-8")


def test_screen_flags_false_material_keyword():
    # "oro" es un material que blunua NO usa (el material es acero quirúrgico) → exit 1
    out = _screen("aretes de oro para regalar")
    assert out.returncode == 1
    assert "oro" in (out.stdout + out.stderr).lower()


def test_screen_passes_clean_keyword():
    # una keyword corta y limpia pasa (longitud y GEO relajadas) → exit 0
    out = _screen("aretes de acero quirúrgico antialérgicos")
    assert out.returncode == 0


def test_screen_flags_hype_keyword():
    # lujo-vacío también se descarta mecánicamente
    out = _screen("aretes de lujo exclusivos")
    assert out.returncode == 1


def test_screen_flags_voseo_keyword():
    # el registro es español neutro: el voseo cae
    out = _screen("elegí tus aretes favoritos")
    assert out.returncode == 1
