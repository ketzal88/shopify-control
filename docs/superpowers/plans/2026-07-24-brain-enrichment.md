# Brain enrichment / `refrescar-estandares` (W4-2) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Un skill de operador `refrescar-estandares` que refresca la parte VIVA de `store-standards.md` (§4 keywords, §5 GEO) con evidencia del Worker Brain, con screen de vocabulario mecánico y gate del operador. NO toca Shopify ni el guard.

**Architecture:** Es **casi todo un SKILL.md** (procedimiento) — usa tools que ya existen: `Worker_Brain:get_client_brief/get_seo_gaps/get_creative_intelligence` (lectura), `description_lint.py` (CLI, screen de vocabulario), y `Edit` para escribir el markdown. Sin clase de guard, sin write de Shopify. La única pieza "de código" es reusar el `description_lint` existente como screen.

**Spec:** `docs/superpowers/specs/2026-07-24-brain-enrichment-design.md`. **Refinamientos del spec-review incorporados** (ver más abajo).

## Refinamientos del review, resueltos
- **(a) Screen de vocabulario mecánico:** el skill corre `description_lint.py` sobre el texto de las keywords propuestas ANTES del gate del operador → una keyword con material falso ("oro"/"plata"/chapado), lujo-vacío o claims médicos **se descarta** con nota. Convierte "no entra" de juicio a chequeo mecánico.
- **(b) §10:** el refresh escribe §4/§5 **y** agrega a §10 una nota datada ("última actualización: {fecha} — fuentes: seo-gaps, creative-intelligence") para trazabilidad. No escribe evidencia cruda.
- **(c) Regla afirmativa:** el skill escribe **únicamente §4/§5 y la nota de §10**; nunca ninguna sección ESTABLE (§1,2,3,6,7,8,9,11).
- **(d) Paso 0:** es el **Brain ID** (valor estático de `clients/{slug}/CLAUDE.md`), no `get-shop-info` — no hay riesgo de "repuntado en silencio" como con `switch-shop`, así que no lleva verify-back.

---

## File Structure
- **Create:** `.claude/skills/refrescar-estandares/SKILL.md` — el procedimiento (operador).
- **Create:** `clients/{slug}/backups/standards/` (implícito) — backups datados del `store-standards.md`.
- **Test:** `tests/test_vocab_screen.py` — que `description_lint` atrapa una keyword con material falso (la pieza mecánica).
- **No se toca:** `backup_guard.py`, `settings.json`, ningún archivo de Shopify.

---

## Task 1: Test del screen de vocabulario (la pieza mecánica)

**Files:**
- Create: `tests/test_vocab_screen.py`

- [ ] **Step 1: Test que falla/pasa** — confirmar que `description_lint.py` (por CLI, stdin) marca una keyword con material falso, para poder usarlo como screen. (Es un test del contrato que el skill va a usar, no código nuevo.)

```python
import subprocess, sys
from pathlib import Path
LINT = Path(__file__).resolve().parents[1] / ".claude" / "hooks" / "description_lint.py"

def _screen(text):
    # modo SOLO-VOCABULARIO: longitud relajada, sin GEO, SIN --keywords, así solo
    # disparan los chequeos de material falso / lujo / médico / voseo (NO "muy corta"
    # ni "falta GEO", que marcarían toda keyword corta). Confirmar los nombres exactos
    # de los flags contra el CLI real de description_lint.py.
    return subprocess.run([sys.executable, str(LINT), "--min", "1", "--max", "9999", "--no-geo"],
                          input=text, capture_output=True, text=True, encoding="utf-8")

def test_screen_flags_false_material_keyword():
    out = _screen("aretes de oro para regalar")            # "oro" = material que no es
    assert out.returncode == 1 and "oro" in (out.stdout + out.stderr).lower()

def test_screen_passes_clean_keyword():
    out = _screen("aretes de acero quirúrgico antialérgicos")   # keyword corta y limpia → exit 0
    assert out.returncode == 0
```

- [ ] **Step 2: Verificar** (con el `description_lint` actual ya debería pasar; si no, es señal de que el CLI necesita el flag/forma esperada — ajustar el uso en el skill, NO el linter).
- [ ] **Step 3: Commit** → `git add tests/test_vocab_screen.py && git commit -m "test(w4): screen de vocabulario reusa description_lint (W4-2)"`

---

## Task 2: SKILL.md `refrescar-estandares`

**Files:**
- Create: `.claude/skills/refrescar-estandares/SKILL.md`

- [ ] **Step 1:** Escribir el SKILL.md siguiendo el molde de los otros skills (frontmatter, reglas, paso 0). Contenido (spec §3):
  - **Frontmatter:** `name: refrescar-estandares`, `description:` (operador: refrescar los estándares vivos con datos del Brain; NO cliente-facing).
  - **Reglas:** solo escribe §4/§5 (+ nota §10); nunca ESTABLE; el Brain propone, el operador cura; frescura (dato viejo no es dato); no toca Shopify.
  - **Paso 0:** identificar cliente + Brain ID (`clients/{slug}/CLAUDE.md`). Sin Brain ID → avisar y caer al refresh manual (no abortar).
  - **Flujo:** leer §4/§5 → `get_client_brief` (contexto+frescura) → `get_seo_gaps` (keywords) + `get_creative_intelligence` (ángulos) → **screen mecánico (SOLO-VOCABULARIO):** por cada keyword, `echo "<keyword>" | python .claude/hooks/description_lint.py --min 1 --max 9999 --no-geo` (sin `--keywords`) y **descartar** las que salen con exit 1. NO usar los defaults (min 80 + GEO), que marcarían toda keyword corta como "muy corta / sin GEO". → proponer el diff en texto claro con evidencia por ítem → **gate del operador** (sí/no) → **backup: copia VERBATIM** del `store-standards.md` a `clients/{slug}/backups/standards/{fecha}.md` (undo real) → **Edit QUIRÚRGICO** (string-replacement del bloque §4/§5/§10 puntual, NUNCA un Write de todo el archivo — un rewrite completo arriesga pisar las secciones ESTABLE) + nota datada en §10 → worklog → confirmar.
  - **Frescura:** si un canal viene stale/missing en el brief, no usar ese dato y decirlo.
  - **Contraste con §2:** además del screen mecánico, contrastar cada sugerencia contra el vocabulario prohibido y las anti-referencias de §2 (juicio).
- [ ] **Step 2:** Verificar a mano: solo escribe §4/§5(+§10); paso 0 por Brain ID; corre el screen antes del gate; ningún tool de Shopify.
- [ ] **Step 3: Commit** → `git add .claude/skills/refrescar-estandares/SKILL.md && git commit -m "feat(w4): skill refrescar-estandares (Brain enrichment del refresh trimestral) (W4-2)"`

---

## Cierre
- [ ] Suite completa `python -m pytest -q` verde (W4-2 no toca código de guard; solo suma el test del screen).
- [ ] Confirmar: `backup_guard.py`/`settings.json` intactos; el skill no llama ningún tool de Shopify; escribe solo §4/§5(+§10) de store-standards.
- [ ] (Operador) Correr el refresh real contra el Brain de blunua cuando toque el trimestre.
