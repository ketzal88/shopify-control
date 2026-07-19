"""Regresion del hook secret-scan (core/hooks/scripts).

Cubre dos cosas:
1. `secret-scan.sh`: el bug de CRLF (con core.autocrlf=true, Windows hace checkout
   del patterns file en CRLF; el \\r colgando rompia cada grep -> dejaba pasar TODO
   secreto). El script ahora hace strip del \\r; estos tests lo fijan.
2. `secret-scan-guard.py`: el wrapper que decide si correr el scanner (solo en
   `git commit`). Reemplaza el `python -c` inline que no disparaba en el runtime
   de Windows (ver docs/HANDOFF.md #1b).

Requiere `bash` y `git` en PATH (Git Bash en Windows). Si no estan, se skipea.
"""
import json, shutil, subprocess, sys
from pathlib import Path
import pytest

ROOT = Path(__file__).parent.parent
REAL_SCRIPT = ROOT / "core/hooks/scripts/secret-scan.sh"
PATTERNS = ROOT / "core/security/secret-patterns.txt"
GUARD = ROOT / "core/hooks/scripts/secret-scan-guard.py"

# key de EJEMPLO publica de AWS, construida por PARTES a proposito: asi el fuente
# de este test no matchea el propio patron del scanner (si fuera literal,
# commitear este archivo se auto-bloquearia una vez que el hook dispare).
FAKE_KEY = "AKIA" + "IOSFODNN7EXAMPLE"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="necesita bash y git en PATH",
)


def _git(args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _init_repo(path):
    _git(["init", "-q"], path)
    _git(["config", "user.email", "t@t.t"], path)
    _git(["config", "user.name", "t"], path)


def _stage_leak(path):
    (path / "leak.txt").write_text(f"clave: {FAKE_KEY}\n", encoding="utf-8")
    _git(["add", "leak.txt"], path)


def _run_scanner(script, cwd):
    return subprocess.run(["bash", str(script)], cwd=str(cwd),
                          capture_output=True, text=True)


# --- secret-scan.sh ---------------------------------------------------------

def test_bloquea_aws_key_staged(tmp_path):
    _init_repo(tmp_path)
    _stage_leak(tmp_path)
    r = _run_scanner(REAL_SCRIPT, tmp_path)
    assert r.returncode == 1, r.stderr
    assert "BLOCKED" in r.stderr


def test_deja_pasar_diff_limpio(tmp_path):
    _init_repo(tmp_path)
    (tmp_path / "notes.txt").write_text("hola mundo, sin secretos\n", encoding="utf-8")
    _git(["add", "notes.txt"], tmp_path)
    r = _run_scanner(REAL_SCRIPT, tmp_path)
    assert r.returncode == 0, r.stderr


def test_bloquea_aunque_el_patterns_file_tenga_crlf(tmp_path):
    """Regresion directa: patterns file en CRLF debe seguir bloqueando."""
    scripts_dir = tmp_path / "hooks" / "scripts"
    security_dir = tmp_path / "security"
    scripts_dir.mkdir(parents=True)
    security_dir.mkdir(parents=True)
    shutil.copy(REAL_SCRIPT, scripts_dir / "secret-scan.sh")
    (security_dir / "secret-patterns.txt").write_bytes(
        b"# comentario\r\nAKIA[0-9A-Z]{16}\r\n"
    )
    _init_repo(tmp_path)
    _stage_leak(tmp_path)
    r = _run_scanner(scripts_dir / "secret-scan.sh", tmp_path)
    assert r.returncode == 1, f"CRLF patterns file dejo pasar el secreto: {r.stderr}"
    assert "BLOCKED" in r.stderr


# --- secret-scan-guard.py (wrapper) -----------------------------------------

def _install_scanner(repo):
    """Instala el scanner + patterns dentro de un repo temporal autocontenido."""
    (repo / "core/hooks/scripts").mkdir(parents=True)
    (repo / "core/security").mkdir(parents=True)
    shutil.copy(REAL_SCRIPT, repo / "core/hooks/scripts/secret-scan.sh")
    shutil.copy(GUARD, repo / "core/hooks/scripts/secret-scan-guard.py")
    shutil.copy(PATTERNS, repo / "core/security/secret-patterns.txt")


def _run_guard(payload, project_dir):
    import os
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(project_dir))
    return subprocess.run(
        [sys.executable, str(project_dir / "core/hooks/scripts/secret-scan-guard.py")],
        input=json.dumps(payload), cwd=str(project_dir),
        capture_output=True, text=True, env=env,
    )


def test_guard_bloquea_en_git_commit_con_secreto(tmp_path):
    _install_scanner(tmp_path)
    _init_repo(tmp_path)
    _stage_leak(tmp_path)
    r = _run_guard({"tool_input": {"command": "git commit -m x"}}, tmp_path)
    assert r.returncode == 1, r.stderr


def test_guard_ignora_comando_que_no_es_commit(tmp_path):
    _install_scanner(tmp_path)
    _init_repo(tmp_path)
    _stage_leak(tmp_path)  # hay secreto staged, pero el comando no es `git commit`
    r = _run_guard({"tool_input": {"command": "git status"}}, tmp_path)
    assert r.returncode == 0, r.stderr
