# shopify-control

Herramienta native-Claude para que clientes de ecommerce **no técnicos** de Worker
controlen y mejoren su tienda Shopify hablándole a Claude.

## Cómo se usa
- **Gabriel (operador/curador):** conecta la tienda, completa `clients/{slug}/store-standards.md`,
  corre el refresh trimestral. Arranca desde la raíz o desde `clients/{slug}/`.
- **Cliente (no técnico):** arranca Claude desde `clients/{slug}/` y habla en lenguaje natural
  ("mejorá la descripción del anillo X", "¿cómo venden los aros esta semana?").

## Reglas duras (las respetan TODOS los skills)
1. **Sin jerga con el cliente:** nunca mostrar términos técnicos (nombres de campo, de skill,
   ni comandos). Entra en lenguaje natural, ve resultados en lenguaje natural.
2. **Humanizer obligatorio** antes de todo output cliente (reusa `handsOn/skills/humanizer`).
3. **Registro por cliente** según `store-standards.md` (blunua: español neutro, sin voseo).
4. **Todo write:** identificar → leer → generar → humanizer → checklist → preview → gate → backup → escribir → confirmar. Nunca escribir sin backup + confirmación explícita.
5. **Alcance de escritura v1:** solo descripción (`body_html`) + meta title + meta description.
   NUNCA precio, stock, status ni handle/URL.

## Estructura
- `.claude/skills/` — procedimientos (sirven a todos los clientes)
- `.claude/hooks/` — guardrails (backup_guard, description_lint)
- `clients/{slug}/` — contexto + estándares + backups + worklog por cliente
- `docs/` — spec, plan, runbooks

Spec: `docs/superpowers/specs/2026-07-19-shopify-control-v1-design.md`
