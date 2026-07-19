# shopify-control

Herramienta para que el dueño de una tienda de ecommerce la controle y la mejore
hablándole a **Claude** en lenguaje normal: preguntar por ventas y stock, mejorar
descripciones con SEO/GEO, y pedir ideas de combos. Con **preview, confirmación y
"deshacer"** en cada cambio, para que nada se rompa.

- 🧑‍💼 **¿Sos el operador (Worker)?** Seguí la guía de instalación de abajo.
- 🛍️ **¿Sos el dueño de la tienda?** Tu guía simple está en **[docs/guia-cliente.md](docs/guia-cliente.md)** (esa es la que te pasan).

---

## ✅ Requisitos previos (se instalan una sola vez)

### Programas

| Qué | Para qué | Link | ¿Obligatorio? |
|-----|----------|------|:---:|
| **VS Code** 1.98+ | Es donde se trabaja. Todo el sistema asume que se abre la raíz del repo acá adentro. | [code.visualstudio.com](https://code.visualstudio.com/) | **Sí** |
| **Extensión "Claude Code"** | La herramienta en sí, dentro de VS Code | [claude.com/claude-code](https://claude.com/claude-code) | **Sí** |
| **git** | Versiona los cambios y, en Windows, **trae Git Bash** | [git-scm.com/downloads](https://git-scm.com/downloads) | **Sí** |
| **bash** | Lo necesitan los guardrails del framework (hay 4 scripts `.sh` y el secret-scan lo invoca). En Windows **viene con git**: al instalarlo dejá tildado "Git Bash". En Mac y Linux ya está. | (viene con git) | **Sí** |
| **Python 3.8+** | Corre los guardrails de seguridad y los tests | [python.org/downloads](https://www.python.org/downloads/) | **Sí** |
| **pytest** | Verifica que los guardrails funcionan. Se instala con `python -m pip install --user pytest` | (por pip) | **Sí** |
| **Node.js** | Dos casos: si instalás Claude Code por npm, y si vas a usar el **Shopify Dev MCP** (valida GraphQL, se baja con `npx`). Con la extensión de VS Code sola, no hace falta. | [nodejs.org](https://nodejs.org) | Opcional |

### Cuentas (no se instalan, se habilitan)

| Qué | Para qué | Dónde | ¿Obligatorio? |
|-----|----------|-------|:---:|
| **Claude Pro** (o mayor) | Claude Code **no** anda con el plan gratis. Pro (US$20) alcanza. | [claude.com/pricing](https://claude.com/pricing) | **Sí** |
| **Connector de Shopify** | Es por donde Claude lee y escribe en la tienda. Se habilita en la configuración de conectores de tu cuenta de claude.ai, **no** se instala en la máquina. Sin esto no funciona nada. | claude.ai → conectores | **Sí** |
| **Shopify Partners** | Crear una tienda de prueba gratis para practicar sin tocar la real | [partners.shopify.com](https://partners.shopify.com) | Recomendado |

> **Verificá todo de una vez.** Pegá esto en una terminal; lo que diga "no se reconoce", falta:
> ```powershell
> code --version; git --version; python --version; bash --version
> ```

> **¿Y el cliente qué instala?** Nada por su cuenta. El modelo es que **vos le dejás VS Code con
> la extensión andando y el repo abierto**, y él solo escribe en el panel. Por eso su guía
> ([docs/guia-cliente.md](docs/guia-cliente.md)) arranca en "abre VS Code" y no tiene sección de
> instalación.

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

- "¿Qué productos hay?" · "¿Qué está por agotarse?"
- "Mejora la descripción de [producto]" → te muestra antes/después y pide tu OK.
- "Dame ideas de combos."

---

## 🛠️ Las tres herramientas, en detalle

El cliente no las invoca por nombre: habla normal y Claude elige. Esta sección es para que
**vos** sepas qué hace cada una y dónde están sus límites.

### 📊 `reporte-tienda`: solo lectura

**Qué hace.** Responde cómo va la tienda leyendo en vivo: ventas del período, productos que más
venden, stock bajo o agotado, y de dónde llegan las visitas y las ventas.

**Le pide el cliente:** _"¿Cómo se vendieron los anillos esta semana?"_, _"¿Qué está por
agotarse?"_, _"¿De dónde vienen mis clientes?"_

**Devuelve** texto simple, sin métricas crudas: dice "ticket promedio", nunca "AOV"; compara
siempre contra un período anterior para que el número signifique algo.

**Límite real que conviene saber.** No puede escanear el catálogo entero buscando descripciones
pobres: la capa de datos no permite filtrar por largo de descripción ni por falta de foto. Revisa
una **muestra acotada** (los más vendidos, o una categoría) y está obligada a declarar el alcance
con número. Si te dice "revisé toda tu tienda", algo salió mal.

### ✍️ `mejorar-descripcion`: la única que escribe

**Qué toca.** Exactamente tres campos: descripción, título de Google y resumen de Google. Nada más.

**Le pide el cliente:** _"Mejora la descripción del anillo Cosmos."_

**El flujo, que nunca se saltea:** confirmar tienda → cargar los estándares del cliente →
identificar el producto (si hay varios parecidos, pregunta cuál) → leer los 3 campos actuales →
escribir la nueva versión con el molde de la marca → pasarla por el humanizer → **correr el
linter** → mostrar preview antes/después → **pedir sí o no** → guardar backup → escribir →
verificar → anotar en el worklog.

**Deshacer.** El cliente dice _"vuelve a la anterior"_. El undo también respalda antes de pisar,
así que se puede volver a aplicar la mejora después. Verificado con hashes: la reversión devuelve
los campos **idénticos carácter por carácter**.

**Límite conocido y no probado todavía:** el modo lote (varios productos con un solo OK) está
acotado a 5 y **no se probó con datos reales**. El backup vence a los 15 minutos, así que un lote
largo obliga a re-respaldar en el medio. Probá un lote de 2 o 3 antes de ofrecérselo al cliente.

### 🎁 `armar-combo`: solo lectura, solo propone

**Qué hace.** Sugiere combos basándose en la **co-compra real** (qué se llevó junto la gente en
las últimas órdenes), no en corazonadas de catálogo.

**Le pide el cliente:** _"Dame ideas de combos."_

**Devuelve** cada combo con qué lleva, por qué tiene sentido y una frase para comunicarlo (ese
copy pasa por el vocabulario prohibido de la marca).

**Lo que NO hace, a propósito:** no crea el combo, no crea descuentos, no arma colecciones y no
cambia precios. Si el cliente pide "ármalo con 15% off", responde con el guion de rechazo y lo
anota. Esas herramientas además están bloqueadas.

---

## 🧰 Herramientas del operador

**Correr los tests de seguridad:**

```powershell
python -m pytest tests/ -q
```

**Correr el linter a mano** sobre cualquier texto (útil para revisar algo antes de publicarlo):

```powershell
python .claude/hooks/description_lint.py --keywords "acero quirúrgico,hipoalergénico" --dialect neutro
```

El texto va por entrada estándar. Sale 0 si está limpio, 1 y explica qué encontró.

---

## 🗂️ Qué hay en este repo

| Carpeta                | Qué es                                                                     |
| ---------------------- | -------------------------------------------------------------------------- |
| `.claude/skills/`      | Los 3 skills: `mejorar-descripcion`, `reporte-tienda`, `armar-combo`       |
| `.claude/hooks/`       | Los guardrails: `backup_guard`, `shopify_shell_guard`, `description_lint`  |
| `clients/{slug}/`      | Cada cliente: estándares, conexión, backups y worklog                      |
| `core/` + `stack.json` | El claude-code-framework de Worker (secret-scan, pre-push, close-protocol) |
| `docs/`                | Guía del cliente, runbook de conexión, spec, plan y `HANDOFF.md`           |

**Para arrancar con un cliente nuevo:** copiá `clients/_template/` a `clients/{slug}/` y completá
`store-standards.md` (registro, vocabulario, keywords, taxonomía) y `connection.md`.

---

## 🔒 Cómo cuida la tienda

Antes de cualquier cambio muestra un **preview** y pide **confirmación**. Guarda una copia del
valor viejo, así el cliente puede deshacer diciendo _"vuelve a la anterior"_ (esa es la frase
exacta que se le enseña en la guía; va en neutro porque es el registro de blunua).

Lo importante: **el alcance no depende de que el modelo se porte bien.** Está bloqueado por
diseño, en cuatro capas:

| Capa                                  | Qué impide                                                                                                                     |
| ------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `permissions.deny` en `settings.json` | Que existan siquiera las herramientas de stock, descuentos, colecciones y alta de productos                                    |
| `backup_guard.py`                     | Escribir sin backup fresco, o tocar cualquier campo que no sea descripción y SEO (incluso si viene por `variables` de GraphQL) |
| `shopify_shell_guard.py`              | Pegarle a la API de Shopify desde la terminal, esquivando todo lo anterior                                                     |
| `description_lint.py`                 | Publicar un material falso ("oro" sobre acero), lujo vacío, un claim médico o voseo                                            |

Si querés comprobarlo, pedile a Claude que cambie un precio: no va a poder, y no porque se
niegue amablemente sino porque la herramienta no está.
