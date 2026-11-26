"""secret-scan-guard debe dispararse con cualquier forma de `git commit`, no solo si el comando empieza con eso."""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GUARD = os.path.join(ROOT, "core", "hooks", "scripts", "secret-scan-guard.py")


def _fires(cmd):
    """True si el guard intentó correr el scanner (con CLAUDE_PROJECT_DIR vacío no hay script: rc != 0 => exit 2)."""
    env = dict(os.environ, CLAUDE_PROJECT_DIR=os.path.join(ROOT, "no-existe"))
    p = subprocess.run([sys.executable, GUARD], input=json.dumps({"tool_input": {"command": cmd}}),
                       text=True, capture_output=True, env=env)
    return p.returncode == 2


def test_dispara_en_commit_directo_y_encadenado():
    for cmd in ("git commit -m x", "git add -A && git commit -m x", "cd x && git commit -m x",
                "git -C . commit -m x"):
        assert _fires(cmd), cmd


def test_no_dispara_en_otros_comandos():
    for cmd in ("git status", "git log --oneline", "echo commit", "ls"):
        assert not _fires(cmd), cmd
