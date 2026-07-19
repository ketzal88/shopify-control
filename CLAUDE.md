# shopify-control

Herramienta native-Claude para que clientes de ecommerce **no técnicos** de Worker
controlen y mejoren su tienda Shopify hablándole a Claude.

## Cómo se usa
> **Se opera desde VS Code con la extensión de Claude Code abierta en este repo** (NO desde el
> app de Claude): así se cargan los skills, los hooks de seguridad, el worklog y la memoria por
> cliente. El app pelado no tiene ese "cerebro". El connector de Shopify tiene que estar
> disponible dentro de Claude Code.

> **Siempre se abre la RAÍZ del repo**, nunca una subcarpeta. Claude Code busca `.claude/` en la
> carpeta que abrís: si abrís `clients/{slug}/` no hay hooks ni skills, pero el connector de
> Shopify **igual puede escribir**. Abrir la raíz no es preferencia, es lo que enciende los
> guardrails.

- **Gabriel (operador/curador):** conecta la tienda, completa `clients/{slug}/store-standards.md`,
  corre el refresh trimestral.
- **Cliente (no técnico):** abre VS Code en la raíz de este repo y habla en lenguaje natural
  ("mejora la descripción del anillo X", "¿cómo se venden los aretes esta semana?").

Como desde la raíz no se auto-carga el contexto del cliente, **todo skill arranca por el paso 0:
confirmar el cliente activo y contra qué tienda está conectado el connector** (`get-shop-info`
contra `clients/{slug}/connection.md`). Si no coinciden, se aborta.

## Reglas duras (las respetan TODOS los skills)
1. **Sin jerga con el cliente:** nunca mostrar términos técnicos (nombres de campo, de skill,
   ni comandos). Entra en lenguaje natural, ve resultados en lenguaje natural.
2. **Humanizer obligatorio** antes de todo output cliente. Path único:
   `handsOn-Worker/skills/humanizer/SKILL.md`. Hoy NO es invocable como skill desde este repo:
   hay que leer ese archivo y aplicarlo a mano.
3. **Registro por cliente** según `store-standards.md` (blunua: español neutro, sin voseo).
   Los textos literales de los skills son plantillas, no literales universales.
4. **Todo write:** confirmar tienda → cargar contexto → identificar → leer → generar → humanizer →
   checklist → preview → gate → backup → escribir → confirmar. Nunca escribir sin backup +
   confirmación explícita. **El undo también es un write** y lleva el mismo protocolo.
5. **Alcance de escritura v1:** solo descripción (`descriptionHtml`, vía `Shopify:update-product`)
   + SEO meta title/description (`seo.title`/`seo.description`, vía `Shopify:graphql_mutation`).
   NUNCA precio, stock, status, tags, título ni handle/URL.
   **Esto está enforced por diseño, no por prosa:** `permissions.deny` en `settings.json` bloquea
   los tools fuera de alcance (stock, descuentos, colecciones, alta de productos), y
   `backup_guard` bloquea cualquier write que toque un campo fuera de `{descripción, seo}`.

## Estructura
- `.claude/skills/` — procedimientos (sirven a todos los clientes)
- `.claude/hooks/` — guardrails propios (backup_guard, description_lint)
- `clients/{slug}/` — contexto + estándares + backups + worklog por cliente
- `core/` + `stack.json` — el claude-code-framework de Worker (gates de calidad/seguridad)
- `docs/` — spec, plan, runbooks

## Gates de calidad y seguridad (framework)
Este repo adopta el **claude-code-framework** de Worker (config-driven vía `stack.json`):
- `stack.json` — manifest: `test = python -m pytest -q`, secret-scan en cada commit, pre-push corre los tests, `push: operator-only`, close-protocol.
- Los hooks **conviven** con los nuestros: `backup_guard` (matcher `.*`) cuida los writes de Shopify; los del framework (matcher `Bash`) cuidan commits/pushes/secretos.
- Reglas de referencia en `core/rules/` (close-protocol, operating-procedure, subagent-economics, learning-loop — esta última tiene la regla de **verificar automatizaciones headless**, aplica al chequeo del hook).
> Los hooks se arman al INICIAR la sesión de Claude Code. Si editás `settings.json`/`stack.json`, reiniciá la sesión para que tomen efecto.

Spec: `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
