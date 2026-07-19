import subprocess, sys
from pathlib import Path
import importlib.util

LINT = Path(__file__).parent.parent / ".claude/hooks/description_lint.py"
spec = importlib.util.spec_from_file_location("description_lint", LINT)
dl = importlib.util.module_from_spec(spec); spec.loader.exec_module(dl)

KW = ["acero quirúrgico", "hipoalergénico"]


# --- chequeos originales ----------------------------------------------------

def test_clean_text_has_no_issues():
    txt = "Anillo minimalista en acero quirúrgico, hipoalergénico y resistente al agua. " * 3
    assert dl.lint(txt, KW, 10, 200) == []

def test_em_dash_is_flagged():
    txt = "Anillo en acero quirúrgico — hipoalergénico y duradero para uso diario todos los dias."
    assert any("em-dash" in i for i in dl.lint(txt, KW, 3, 200))

def test_too_short_is_flagged():
    assert any("corto" in i.lower() for i in dl.lint("acero quirúrgico hipoalergénico", KW, 50, 200))

def test_missing_keyword_is_flagged():
    txt = "Un anillo lindo y bonito para todos los dias, elegante y sencillo, ideal para regalar."
    assert any("keyword" in i.lower() for i in dl.lint(txt, KW, 3, 200))

def test_too_long_is_flagged():
    txt = "acero quirúrgico hipoalergénico " * 100
    assert any("largo" in i.lower() for i in dl.lint(txt, KW, 3, 50))


# --- §2 palabras prohibidas: materiales falsos ------------------------------
# Es el ítem de mayor riesgo comercial: publicar "oro" sobre acero quirúrgico
# es un claim de material falso en la tienda viva.

def test_material_falso_es_flagged():
    for palabra in ["Anillo de oro para uso diario.", "Collar de plata resistente.",
                    "Pieza chapada en acero.", "Cadena bañado en oro duradera."]:
        assert any("material prohibido" in i for i in dl.lint(palabra, None, 3, 200)), palabra

def test_acabado_dorado_o_plateado_NO_es_flagged():
    # "dorado"/"plateado" describen el acabado y son válidos; el linter no debe
    # confundirlos con un claim de material.
    txt = "Anillo en acero quirúrgico con acabado dorado y version plateado, hipoalergénico."
    assert [i for i in dl.lint(txt, KW, 3, 200) if "material" in i] == []

def test_palabra_que_contiene_oro_no_dispara():
    txt = "Una pieza que es un tesoro para uso diario en acero quirúrgico hipoalergénico."
    assert [i for i in dl.lint(txt, KW, 3, 200) if "material" in i] == []


# --- §2 lujo-vacío y claims médicos -----------------------------------------

def test_lujo_vacio_es_flagged():
    for txt in ["Un anillo de lujo para vos.", "Pieza exclusiva y deslumbrante.",
                "El mejor anillo del catalogo."]:
        assert any("lujo-vacío" in i for i in dl.lint(txt, None, 3, 200)), txt

def test_claim_medico_es_flagged():
    txt = "El acero tiene propiedades curativas y medicinales para la piel."
    assert any("claim médico" in i for i in dl.lint(txt, None, 3, 200))

def test_no_irrita_es_permitido():
    txt = "Acero quirúrgico hipoalergénico que no irrita, apto para pieles sensibles."
    assert [i for i in dl.lint(txt, KW, 3, 200) if "médico" in i] == []

def test_magico_NO_dispara_porque_la_marca_lo_usa():
    # Decisión deliberada: la tienda tiene colecciones "Brillo mágico".
    txt = "Un brillo mágico en acero quirúrgico hipoalergénico para uso diario."
    assert [i for i in dl.lint(txt, KW, 3, 200) if "médico" in i] == []


# --- §2 registro: voseo -----------------------------------------------------

def test_voseo_es_flagged_en_neutro():
    txt = "Si querés, podés combinarlo con otros anillos de acero quirúrgico hipoalergénico."
    assert any("voseo" in i for i in dl.lint(txt, KW, 3, 200))

def test_voseo_no_es_flagged_en_rioplatense():
    txt = "Si querés, podés combinarlo con otros anillos de acero quirúrgico hipoalergénico."
    assert [i for i in dl.lint(txt, KW, 3, 200, dialect="rioplatense") if "voseo" in i] == []

def test_texto_neutro_no_dispara_voseo():
    txt = "Si quieres, puedes combinarlo con otros anillos de acero quirúrgico hipoalergénico."
    assert [i for i in dl.lint(txt, KW, 3, 200) if "voseo" in i] == []


# --- §5 bloque GEO ----------------------------------------------------------

def test_falta_bloque_geo_es_flagged():
    txt = "Anillo en acero quirúrgico hipoalergénico, resistente al agua y para uso diario."
    assert any("GEO" in i for i in dl.lint(txt, KW, 3, 200, check_geo=True))

def test_con_preguntas_frecuentes_pasa_geo():
    txt = "Anillo en acero quirúrgico hipoalergénico. ¿Se puede mojar? Si, resiste el agua."
    assert [i for i in dl.lint(txt, KW, 3, 200, check_geo=True) if "GEO" in i] == []


# --- HTML -------------------------------------------------------------------

def test_los_tags_html_no_se_cuentan_como_palabras():
    plano = "acero quirúrgico hipoalergénico resistente"
    html = "<p><strong>acero quirúrgico</strong> <em>hipoalergénico</em> <br> resistente</p>"
    assert len(dl.strip_html(html).split()) == len(plano.split())

def test_em_dash_dentro_de_html_se_detecta():
    html = "<p>Anillo en acero quirúrgico — hipoalergénico y duradero para el uso diario.</p>"
    assert any("em-dash" in i for i in dl.lint(html, KW, 3, 200))


# --- CLI --------------------------------------------------------------------
# Antes no era ejecutable (sin __main__), así que "corré el lint" era autorreportado.

def _run_cli(text, *args):
    return subprocess.run([sys.executable, str(LINT), *args], input=text,
                          capture_output=True, text=True, encoding="utf-8")

def test_cli_texto_limpio_sale_0():
    txt = ("Anillo Cosmos en acero quirúrgico con cristales, no irrita la piel. " * 12 +
           "¿Se puede mojar? Si, resiste el agua.")
    r = _run_cli(txt, "--keywords", "acero quirúrgico", "--min", "10", "--max", "400")
    assert r.returncode == 0, r.stderr

def test_cli_texto_con_issue_sale_1_y_explica():
    txt = "Anillo de oro para uso diario."
    r = _run_cli(txt, "--min", "3", "--max", "200", "--no-geo")
    assert r.returncode == 1
    assert "material prohibido" in r.stderr
