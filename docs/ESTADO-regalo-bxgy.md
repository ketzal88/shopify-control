# Estado de implementación — Regalo gratis / BXGY (rama `feat/regalo-bxgy-m1`)

- **Fecha:** 2026-07-22 (sesión autónoma nocturna; Gabriel pidió "terminá vos" tras cerrar el spec)
- **Spec:** `docs/superpowers/specs/2026-07-22-regalo-gratis-bxgy-design.md`
- **Rama:** `feat/regalo-bxgy-m1` (worktree aislado, **sin pushear** — el push es del operador)
- **Se construyó desde el HEAD local con toda la fundación del builder** (Tasks 1–5), no desde
  `origin/main` (que está muy atrás).

## Hecho y verificado OFFLINE en esta rama

| Commit | Qué | Verificación |
|---|---|---|
| `484c71b` | **Guard de plata** (`_check_bxgy`, metafield `type:"bxgy"`, techo propio) | **pytest: 209 passed** (26 tests nuevos de bxgy) |
| `91144c6` | **Matemática del regalo** (`computeBxgyTotalCents`, "pagás N", redondeo por unidad) | **node: OK** (gratis, parcial, borde) |
| `40c04fb` | **Skill `armar-regalo`** + `strategies/automatic.md` + fix de `armar-escalones` | procedimiento (markdown), cubierto por la verificación E2E pendiente |

**Guard — lo que enforcea** (`.claude/hooks/backup_guard.py`): `discountAutomaticBxgyCreate` entra a la
whitelist con **su propia función** (no reusa `_check_discount`); techo `maxGiftPct`/`maxGetQty`/
`minBuyGetRatio` (opcionales en la política → fail-closed si faltan) + allowlist `giftableProducts`
para el cruzado; `usesPerOrderLimit` forzado a 1; rechaza las formas no soportadas por BXGY
(`percentage`/`discountAmount` al tope); trampa de unidades y borde 100 cubiertos; `_check_metafield`
ramifica por `type`. `deal-policy.json` de blunua y `_template` backfilleados (cruzado nace apagado:
`giftableProducts: []`).

## HECHO en el follow-up ("terminar todo lo que se pueda para salir a producción")

- **Widget `worker-escalones.liquid` cableado para el regalo** (additivo; el camino de escalones NO se
  tocó). Gate Liquid abierto a `type:"bxgy"`, volcado de datos del regalo (incluido el cruzado vía
  `all_products[deal.get.handle]` + precio del regalado), rama `bxgy` en el JS con tarjeta de regalo,
  CTA "Llevar N · pagás M" (redondeo por unidad), y `onBuy` con la 2ª línea de carrito del cruzado.
  **Verificado offline:** JS `node --check` OK + tags Liquid balanceados. **NO verificado:** el render y
  el carrito reales (incógnitas D1/D2) — eso es dev-store.
- **Gobernanza:** `CLAUDE.md` regla 5 declara ya la clase "regalo/BXGY" y `worker.style`.

## PENDIENTE — para un único dueño, con dev-store (NO se puede hacer autónomo/offline)

1. **Verificación en vivo contra dev-store** — **el único gate real antes de producción.** El widget y
   el guard están escritos; falta probar que se comportan. Requiere paso 0 (confirmar que el connector
   NO apunta a blunua producción):
   - Mismo producto: comprá 2 → 3º gratis; el carrito paga lo que cantó el botón.
   - Cruzado: comprá P → Q a $0; que la línea de $0 renderice y checkoutee (D2).
   - `usesPerOrderLimit: 1`: comprá 4 en "buy 2 get 1" → **solo 1 gratis** (D3).
   - `all_products[handle]` resuelve el regalo cruzado (D1).
   - Ciclo crear → verificar en checkout → sacar → verificar que dejó de aplicar.

2. **Push y merge a `main`** — operator-only (`stack.json`). Solo lo hacés vos.

## Mejoras que NO bloquean producción (se pueden diferir)

- **Generalización del builder visual (§17 del spec).** El regalo funciona por lenguaje natural (skill
  `armar-regalo`); el builder visual es la capa opcional. Sumar: selector de tipo de oferta, marcador
  `🎁 regalo-config`, ingestión, y reconciliar con `§6/§7` del `2026-07-22-catalogo-widgets-design.md`.
- **`clients/blunua/store-standards.md`** — declarar la clase "regalo" en prosa (la regla dura ya está
  en `CLAUDE.md`; esto es documentación para humanos).

## Review adversarial del guard — RESUELTO (commit `9c5b1a7`)

Se corrió una review adversarial del `_check_bxgy` (código de plata; el M1 de escalones encontró 7
agujeros así). Ejecutó ~15 payloads reales contra el guard. **Tres hallazgos, los tres corregidos con
TDD (test que reproduce el bypass → fix → verde). 214 tests passed.**

- **HIGH — reabría escalones.** Un comentario (`#x\n`) o coma entre el nombre de la mutación y su `(`
  rompía el router de asuntos (`_discount_mutations`, regex sobre texto **crudo**) mientras el gate de
  allowlist (`_root_mutation_fields`, comment-stripped) lo dejaba pasar. El descuento caía al camino de
  producto pidiendo **solo un backup de descripción** → todo el techo evadido. **Afectaba
  `discountAutomaticBxgyCreate` Y `discountAutomaticBasicCreate`** (escalones). Fix: clasificar y
  despachar los asuntos desde `roots` (el parser que ya decidió la allowlist), no desde el regex crudo.
  Es exactamente la causa raíz de `docs/2026-07-20-hallazgos-de-seguridad-backup-guard.md`: dos formas
  de leer el mismo documento, y la decisión final confiaba en la débil.
- **MED — backup desacoplado.** El backup se buscaba por `variables.productId` sin compararlo con el
  producto realmente comprado; un backup de otro producto autorizaba el write. Fix: `productId == buy_gid`.
- **LOW — gid con espacio.** `"gid…/1 "` (espacio al final) se leía como falso "cruzado" y salteaba el
  ratio de mismo-producto. Fix: forma canónica `PRODUCT_GID_RE`.

Objetivos donde el review NO encontró bypass (confirmado): sin backup → bloquea; señuelo `aaa_decoy` →
cerrado; trampa fracción/entero y borde 100 → cubiertos; `all`/`collections`/variantes en buy o get →
cerrado; metafield `type:bxgy` sobre techo → cerrado.

> **Nota para el operador:** el HIGH **no lo introdujo BXGY** — estaba latente en el router de asuntos
> desde escalones. Este milestone lo encontró y lo cerró para las dos familias. Vale traerlo al `main`
> aunque se difiera el resto del regalo.
