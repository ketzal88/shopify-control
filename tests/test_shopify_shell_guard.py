"""El guard de shell tapa el camino que backup_guard no ve.

backup_guard filtra por NOMBRE DE TOOL, así que un `curl` contra la Admin API
esquiva backup, alcance de campos y gate de confirmación de una sola vez.
"""
import json, subprocess, sys
from pathlib import Path
import importlib.util

GUARD = Path(__file__).parent.parent / ".claude/hooks/shopify_shell_guard.py"
spec = importlib.util.spec_from_file_location("shopify_shell_guard", GUARD)
sg = importlib.util.module_from_spec(spec); spec.loader.exec_module(sg)

ADMIN_WRITE = ('curl -X POST https://blunua-jewelry.myshopify.com/admin/api/2024-10/graphql.json '
               '-H "X-Shopify-Access-Token: xxx" -d \'{"query":"mutation{productUpdate}"}\'')


def test_curl_contra_admin_api_se_detecta():
    assert sg.is_admin_api_call(ADMIN_WRITE)

def test_wget_y_powershell_tambien():
    assert sg.is_admin_api_call("wget https://tienda.myshopify.com/admin/api/2024-10/products.json")
    assert sg.is_admin_api_call("Invoke-RestMethod https://x.myshopify.com/admin/api/2024-10/x.json")

def test_lectura_por_shell_tambien_se_bloquea():
    # Una lectura por shell suele ser el paso previo a un write por shell.
    assert sg.is_admin_api_call("curl https://blunua-jewelry.myshopify.com/admin/api/2024-10/products.json")

def test_comandos_normales_no_se_tocan():
    for cmd in ["git status", "python -m pytest -q", "ls -la",
                "curl https://api.github.com/repos/x/y",
                "curl https://www.blunua.com"]:
        assert not sg.is_admin_api_call(cmd), cmd

def test_mencionar_la_url_sin_cliente_http_no_bloquea():
    # Hablar de la API en un echo o en un comentario no es llamarla.
    assert not sg.is_admin_api_call("echo 'la admin api vive en myshopify.com/admin'")

def test_comando_vacio_no_rompe():
    assert not sg.is_admin_api_call("")
    assert not sg.is_admin_api_call(None)


# --- contrato de exit codes -------------------------------------------------

def _run(payload):
    return subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                          capture_output=True, text=True, encoding="utf-8")

def test_main_bloquea_con_exit_2():
    r = _run({"tool_input": {"command": ADMIN_WRITE}})
    assert r.returncode == 2, f"debe ser 2 (block), fue {r.returncode}"
    assert "Admin API" in r.stderr

def test_main_permite_comando_normal_con_exit_0():
    r = _run({"tool_input": {"command": "git status"}})
    assert r.returncode == 0

def test_main_payload_ilegible_no_bloquea_todo():
    r = subprocess.run([sys.executable, str(GUARD)], input="no soy json",
                       capture_output=True, text=True)
    assert r.returncode == 0
