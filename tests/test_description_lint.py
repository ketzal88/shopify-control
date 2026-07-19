from pathlib import Path
import importlib.util
spec = importlib.util.spec_from_file_location("description_lint", Path(__file__).parent.parent/".claude/hooks/description_lint.py")
dl = importlib.util.module_from_spec(spec); spec.loader.exec_module(dl)

KW = ["acero quirúrgico", "hipoalergénico"]

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
