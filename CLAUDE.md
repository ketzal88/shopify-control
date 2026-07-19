# shopify-control

Herramienta native-Claude para que clientes de ecommerce **no técnicos** de Worker
controlen y mejoren su tienda Shopify hablándole a Claude.

## Cómo se usa
> **Se opera desde VS Code con la extensión de Claude Code abierta en este repo** (NO desde el
> app de Claude): así se cargan los skills, los hooks de seguridad, el worklog y la memoria por
> cliente. El app pelado no tiene ese "cerebro". El connector de Shopify tiene que estar
> disponible dentro de Claude Code.

- **Gabriel (operador/curador):** conecta la tienda, completa `clients/{slug}/store-standards.md`,
  corre el refresh trimestral. Arranca desde la raíz o desde `clients/{slug}/`.
- **Cliente (no técnico):** abre VS Code en `clients/{slug}/` y habla en lenguaje natural
  ("mejorá la descripción del anillo X", "¿cómo venden los aros esta semana?").

## Reglas duras (las respetan TODOS los skills)
1. **Sin jerga con el cliente:** nunca mostrar términos técnicos (nombres de campo, de skill,
   ni comandos). Entra en lenguaje natural, ve resultados en lenguaje natural.
2. **Humanizer obligatorio** antes de todo output cliente (reusa `handsOn/skills/humanizer`).
3. **Registro por cliente** según `store-standards.md` (blunua: español neutro, sin voseo).
4. **Todo write:** identificar → leer → generar → humanizer → checklist → preview → gate → backup → escribir → confirmar. Nunca escribir sin backup + confirmación explícita.
5. **Alcance de escritura v1:** solo descripción (`descriptionHtml`, vía `Shopify:update-product`)
   + SEO meta title/description (`seo.title`/`seo.description`, vía `Shopify:graphql_mutation`).
   NUNCA precio, stock, status ni handle/URL.

## Estructura
- `.claude/skills/` — procedimientos (sirven a todos los clientes)
- `.claude/hooks/` — guardrails (backup_guard, description_lint)
- `clients/{slug}/` — contexto + estándares + backups + worklog por cliente
- `docs/` — spec, plan, runbooks

Spec: `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
