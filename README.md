# shopify-control

Herramienta para que el dueño de una tienda de ecommerce la controle y la mejore
hablándole a **Claude** en lenguaje normal: preguntar por ventas y stock, mejorar
descripciones con SEO/GEO, y pedir ideas de combos. Con **preview, confirmación y
"deshacer"** en cada cambio, para que nada se rompa.

- 🧑‍💼 **¿Sos el operador (Worker)?** Seguí la guía de instalación de abajo.
- 🛍️ **¿Sos el dueño de la tienda?** Tu guía simple está en **[docs/guia-cliente.md](docs/guia-cliente.md)** (esa es la que te pasan).

---

## ✅ Requisitos previos (se instalan una sola vez)

| Qué | Para qué | Link | ¿Obligatorio? |
|-----|----------|------|:---:|
| **Claude Code** | La herramienta en sí (app / extensión de VSCode / CLI) | [claude.com/claude-code](https://claude.com/claude-code) | Sí |
| **Cuenta Claude Pro** (o mayor) | Claude Code **no** anda con el plan gratis. Pro (US$20) alcanza. | [claude.com/pricing](https://claude.com/pricing) | Sí |
| **git** | Guardar y versionar los cambios | [git-scm.com/downloads](https://git-scm.com/downloads) | Sí |
| **Python 3** | Corre los guardrails de seguridad (hooks) y los tests | [python.org/downloads](https://www.python.org/downloads/) | Sí |
| **Node.js** | **Casi nunca.** Solo si instalás Claude Code por npm. Con el instalador nativo o la extensión de VSCode **NO** hace falta. | [nodejs.org](https://nodejs.org) | Opcional |
| **Cuenta Shopify Partners** | Crear una tienda de prueba gratis | [partners.shopify.com](https://partners.shopify.com) | Sí (para probar) |

> Si ya usás Claude Code, seguramente ya tenés git y probablemente Python. Verificá con los comandos del paso 1.

### Instalar Claude Code (Windows)
- **Opción fácil:** instalá la extensión **"Claude Code"** en VSCode (necesita VSCode 1.98+). Trae todo incluido, sin Node.
- **O por terminal (PowerShell), instalador nativo sin Node:**
  ```powershell
  irm https://claude.ai/install.ps1 | iex
  ```

---

## 🚀 Puesta en marcha (paso a paso)

### 1. Verificá lo básico
Abrí una terminal y probá:
```powershell
git --version
python --version
```
Si alguno dice "no se reconoce", instalalo del link de arriba.

### 2. Instalá pytest (corre los tests de seguridad)
```powershell
python -m pip install --user pytest
```

### 3. Abrí este repo con Claude Code
Abrí la carpeta `shopify-control` en Claude Code (o en VSCode con la extensión).

### 4. Verificá que todo anda
```powershell
python -m pytest tests/ -q
```
Tenés que ver **todos los tests en verde** (0 failed). Eso confirma que los guardrails de
seguridad funcionan. La cantidad de tests crece con el repo, así que no mires el número:
mirá que no falle ninguno.

### 5. Conectá una tienda
Seguí la guía dummy paso a paso: **[docs/runbooks/conectar-tienda.md](docs/runbooks/conectar-tienda.md)**.
Recomendado: empezá con una **tienda de prueba** (development store) gratis, no la real.

### 6. Usalo
Abrí **siempre la RAÍZ del repo** (`shopify-control/`) en VS Code con la extensión de Claude
Code. Nunca abras `clients/{slug}/`: Claude Code busca la carpeta `.claude/` en la carpeta que
abrís, y ahí no hay ninguna, así que la sesión arranca **sin hooks y sin skills** mientras el
connector de Shopify igual puede escribir en la tienda. Además `core/` y `stack.json` viven
en la raíz.

**Paso 0 (obligatorio):** como desde la raíz no se auto-carga el `CLAUDE.md` del cliente,
antes de operar confirmá **con qué cliente vas a trabajar** y **qué tienda está conectada**
(preguntale a Claude "¿qué tienda está conectada?"; si hay más de una, ver el runbook de
conexión). Recién ahí hablá normal:
- "¿Qué productos hay?" · "¿Qué se está por agotar?"
- "Mejorá la descripción de [producto]" → te muestra antes/después y pide tu OK.
- "Dame ideas de combos."

---

## 🗂️ Qué hay en este repo

| Carpeta | Qué es |
|---------|--------|
| `.claude/skills/` | Los 3 skills: `mejorar-descripcion`, `reporte-tienda`, `armar-combo` |
| `.claude/hooks/` | Los guardrails de seguridad (backup + linter) |
| `clients/{slug}/` | Cada cliente: sus estándares, conexión, backups y worklog |
| `docs/` | Esta guía, el runbook de conexión, el spec y el plan |

---

## 🔒 Cómo cuida tu tienda
- Antes de cualquier cambio te muestra un **preview** y pide **confirmación** (sí / no).
- Guarda una **copia** del valor viejo: podés **deshacer** diciendo *"volvé a la anterior"*.
- Solo toca **descripciones y textos de SEO**. Nunca precios, stock ni nada más.
