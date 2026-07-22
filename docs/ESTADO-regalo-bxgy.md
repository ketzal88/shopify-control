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

## PENDIENTE — para un único dueño, con dev-store (NO se hizo autónomo de noche)

1. **Cableado del widget storefront (`widget/worker-escalones.liquid`).** El `.liquid` NO renderiza un
   regalo todavía: su gate Liquid es `deal.tiers.size > 0` (línea 19) y su JS asume `tiers`. Falta:
   - Gate Liquid: `if deal and (deal.tiers.size > 0 or deal.type == 'bxgy')`.
   - Rama `bxgy` en el JS: una tarjeta de regalo (badge "GRATIS"/"−X%"), CTA que canta "Llevar N ·
     pagás M" usando `computeBxgyTotalCents` (ya está en `worker-render.js`).
   - **Cruzado:** volcar el producto regalado vía `all_products[deal.get.handle]` (incógnita D1) y una
     **2ª línea de carrito** en `onBuy` (la variante de Q en `get.qty`, además de P) — el descuento
     nativo la deja en $0 (incógnita D2).
   - **Ojo divergencia:** hoy el `.liquid` tiene render inline y NO consume `worker-render.js`
     (el carril builder no completó la extracción). Decidir: extraer de una (mejor) o duplicar la
     rama bxgy. La matemática ya está centralizada en `computeBxgyTotalCents` — usar esa, no reescribir.
2. **Generalización del builder (§17 del spec).** `worker-render.js` tiene la matemática pero no la
   rama de render DOM del regalo; el template/lógica del builder y `generar-builder-escalones` siguen
   solo-escalones. Sumar: selector de tipo de oferta, sección de regalo con techo horneado, marcador
   `🎁 regalo-config`, e ingestión en `armar-regalo`. Reconciliar con `§6/§7` del
   `2026-07-22-catalogo-widgets-design.md` (mismo movimiento, dos vistas).
3. **Gobernanza (§10 del spec).** Actualizar `CLAUDE.md` regla 5 y `clients/blunua/store-standards.md`
   para declarar la clase "regalo" con su techo. (No se tocó para no colisionar con otros carriles.)
4. **Verificación en vivo contra dev-store** (§13.2 + incógnitas §14, requiere paso 0 confirmando que
   NO es blunua producción):
   - Mismo producto: comprá 2 → 3º gratis; el carrito paga lo que cantó el botón.
   - Cruzado: comprá P → Q a $0; que la línea de $0 renderice y checkoutee (D2).
   - `usesPerOrderLimit: 1`: comprá 4 en "buy 2 get 1" → **solo 1 gratis** (D3).
   - `all_products[handle]` resuelve el regalo cruzado (D1).
   - Ciclo crear → verificar en checkout → sacar → verificar que dejó de aplicar.

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
