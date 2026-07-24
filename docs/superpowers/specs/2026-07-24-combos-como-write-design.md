# Combos como write (W4-1) — Design Spec

- **Fecha:** 2026-07-24
- **Autor:** Gabriel (Worker) + Claude
- **Estado:** Diseño aprobado en brainstorm. No implementado.
- **Cliente piloto:** blunua (COP/Colombia)
- **Es:** el primero de los tres features de W4 (los otros: W4-2 datos del Brain, W4-3 imágenes), cada uno su propio ciclo.
- **Depende de:** `2026-07-22-regalo-gratis-bxgy-design.md` (la clase BXGY que se reusa), `2026-07-19-quantity-breaks-design.md` y `2026-07-19-shopify-control-v1-design.md` §11 (modelo de seguridad).

---

## 1. Contexto y objetivo

Hoy `armar-combo` (R2) **solo propone** combos como texto, leyendo la co-compra real de las órdenes; no escribe nada. Este feature le agrega un **camino de escritura**: cuando el cliente aprueba un combo propuesto, se crea un **descuento BXGY** — *"comprá el collar, llevate las candongas con 15% off"* — reusando la maquinaria BXGY ya construida, con framing e invariantes propios de "combo".

**El valor nuevo** es que la oferta la **sugieren los datos de venta** (co-compra real), no el cliente a mano — eso distingue a combo de `armar-regalo` (que el cliente especifica).

### 1.1 Decisiones del brainstorm (2026-07-24)

| # | Decisión | Elección |
|---|---|---|
| C-D1 | Qué es un "combo" | **Descuento** (no producto-bundle, no widget). |
| C-D2 | Forma del descuento | **BXGY** *"comprá A, llevate B con X% off"*. El "set exacto → % off orden" NO existe nativo en Shopify (necesitaría un Shopify Function/app; verificado contra `DiscountAutomaticBasicInput`: `minimumRequirement` solo admite cantidad/subtotal, no "uno de cada"). |
| C-D3 | Guard nuevo vs reuso | **Reuso** de la clase BXGY (`discountAutomaticBxgyCreate` + `worker.deal`), con una **rama combo** de techo/scope propios. NO una clase nueva desde cero. |
| C-D4 | Techo y scope | **Propios:** `maxComboPct` (propuesto 25%) + `allowCombo`, y el "get" = el producto de la co-compra (explícito, existe, **sin** la lista de regalables), con `%` en **(0, 100)** — nunca gratis. |
| C-D5 | Skill | **`armar-combo` gana el camino de escritura** (propone → el cliente elige → crea), como `mejorar-descripcion` (lee y luego escribe). |

---

## 2. Alcance

**Dentro:**
- `armar-combo`: del "solo propone" al "propone y, con OK del cliente, crea el combo".
- Rama **combo** en el guard de ofertas (`backup_guard.py`): techo/scope propios, distinta del regalo.
- `deal-policy.json` suma `maxComboPct` y `allowCombo`.
- Metafield `worker.deal` con `type:"combo"` (para el registro y un widget futuro).
- Combo **cruzado** (comprá A, llevate B) como caso principal.

**Fuera (YAGNI):**
- Widget nuevo. El combo es el descuento nativo (se ve en carrito/checkout). Un bloque visual, si se justifica, es otro ciclo.
- Combos de mismo-producto (earstacking de 2 iguales): lo cubre mejor **escalones** (quantity breaks), ya construido. No se duplica.
- El "set exacto → % off orden" (necesita Shopify Function/app): fuera del modelo de la herramienta.
- Combos por código (solo automáticos, como el resto).

---

## 3. Modelo de datos y mecanismo

- **Descuento:** `discountAutomaticBxgyCreate` con `customerBuys` = producto A (comprado), `customerGets` = producto B con `discountOnQuantity.effect.percentage` en (0, 1) (o sea 1%–99%, nunca 100% = gratis).
- **Metafield:** `worker.deal` sobre el producto A (el comprado), `type:"combo"`, con la forma del combo (buy/get, %, cantidades) — espejo del `type:"bxgy"` del regalo, para el registro y un widget futuro.
- **Política** (`deal-policy.json`), claves nuevas y **OPCIONALES** (⚠️ NO agregarlas a `deal_policy.REQUIRED_KEYS`: si no, todo `deal-policy.json` existente —el de blunua incluido— fallaría el `issubset` de `load_policy` y se caerían escalones y regalos):
  ```json
  { "allowCombo": true, "maxComboPct": 25, "maxComboGetQty": 2 }
  ```
  El guard gatea vía un helper **`_combo_ceilings(policy)`** (espejo de `_gift_ceilings`) que devuelve `(maxComboPct, maxComboGetQty)` **solo si** `allowCombo is True` y los dos techos son `int` reales; si no → `None` → **no se crean combos** (fail-closed, sin caer en `pct <= None`). `allowCombo:false`, o cualquier techo ausente/malformado ⇒ combos apagados.

---

## 4. Guard — la rama "combo" (§11 del v1)

El combo reusa `discountAutomaticBxgyCreate`, así que pasa por `_check_bxgy` (discount create) y por `_check_bxgy_metafield` (el metafield). Hoy `_bxgy_scope_ok` **bloquea** un BXGY cruzado a un producto que no esté en `giftableProducts` — por eso el combo necesita su propia rama (un combo cruzado apunta a un producto de co-compra, no a un regalable curado).

### 4.1 Discount create (`_check_bxgy`) — aceptar si cae en la caja REGALO **o** en la caja COMBO

En vez de un marcador frágil (que el server ignoraría), el guard acepta el `discountAutomaticBxgyCreate` si satisface **una de las dos cajas**, cada una completa por sí sola:

- **Caja regalo** (la actual, sin cambios): `pct ≤ maxGiftPct`, y si es cruzado, `allowCrossProductGift` + `get ∈ giftableProducts`, `get_qty ≤ maxGetQty`, ratio de mismo-producto, `usesPerOrderLimit:1`, `endsAt`, backup, `productId == buy_gid`.
- **Caja combo** (nueva): `_combo_ceilings(policy)` no es `None` **y** `0 < pct ≤ maxComboPct` **y** `pct < 100` (nunca gratis) **y** el **buy** es un producto explícito único (`_bxgy_single_product`: no `all`, no colección, no variante) **y** `buy_qty ≥ 1` (si no, es "llevate B sin comprar nada" = un cupón) **y** el **get** es un producto explícito único **sin** exigir `giftableProducts` **y** `1 ≤ get_qty ≤ maxComboGetQty` **y** `usesPerOrderLimit == 1` **y** `endsAt` **y** backup **y** `productId == buy_gid`.

> **INVARIANTE DE SEGURIDAD (el review lo pidió explícito):** la caja combo tiene que ser **estricta-o-igual que la caja regalo en TODA dimensión que no relaje conscientemente.** La única relajación deliberada es **el giftable** (un combo apunta a un producto de co-compra, no a un regalable curado). Todo lo demás se mantiene acotado: `get_qty` (por `maxComboGetQty`), `usesPerOrderLimit == 1`, buy/get explícitos, `endsAt`, backup, `productId == buy_gid`. El % es MÁS bajo, no más alto.

Aceptar por OR es seguro **solo con ese invariante**: cada caja se evalúa **COMPLETA por sí sola** (nunca se mezclan dimensiones de una y otra). "Hacerse pasar por combo" solo consigue MENOS: menor %, cantidad acotada, una vez por orden. Para un gratis (100%) hay que pasar por la caja regalo (giftable). Un cruzado a un no-regalable al 25%, get_qty ≤ tope, una vez por orden → **falla regalo** (no giftable) pero **pasa combo** → permitido (deseado). Un "comprá 1, llevate 1000 al 25%" → falla regalo (get_qty > tope) **y** falla combo (get_qty > `maxComboGetQty`) → bloqueado. Un 100% a un no-regalable → falla las dos → bloqueado.

### 4.2 Metafield (`_check_metafield`) — ruteo por `type`

`_check_metafield` ya ramifica por `data.get("type")`. Se agrega `type:"combo"` → un **`_check_combo_metafield` PROPIO** (⚠️ NO se puede reusar `_check_bxgy_metafield`: ese termina en `_bxgy_scope_ok`, que exige `giftableProducts` para el cruzado y usa `_gift_ceilings` para el techo). `_check_combo_metafield` aplica las **mismas caps que la caja combo del discount** (§4.1): pct en (0,100) ≤ `maxComboPct`, **`get_qty ≤ maxComboGetQty`**, buy y get explícitos, sin giftable. Que las caps del metafield y del discount sean **idénticas** es lo que evita la divergencia widget↔carrito — el motivo por el que existe el check de metafield de BXGY. `type:"bxgy"` sigue yendo al del regalo, `tiers` a escalones; el fallthrough de `type` desconocido sigue fallando cerrado.

### 4.3 Lo que NO cambia
- La whitelist de mutaciones de descuento, el "un asunto por documento", el "un solo create/metafield por doc", `endsAt` obligatorio, el backup de oferta (`_covering_deal_backup`), y `_percentage_int`/unidades — todo se reusa igual.
- `permissions.deny` y `FORBIDDEN_MUTATIONS` **no se tocan**.

---

## 5. Flujo del skill `armar-combo` (write)

Mismo protocolo que todo write (spec v1 §6, §9):

```
0. PASO 0 — confirmar cliente + tienda (idéntico; hoy ya lo tiene).
1. CO-COMPRA — leer órdenes, contar pares (lo que ya hace).
2. CATÁLOGO — validar (stock, misma línea, segmentos).
3. PROPONER — combos en texto, priorizando la co-compra real (lo que ya hace).
4. EL CLIENTE ELIGE — "sí, armá el de collar + candongas al 15%".
   (Si no elige o pide solo ideas, termina acá, como hoy — el write es opcional.)
5. COPY DE COMBO + HUMANIZER + CHECKLIST — la frase del combo pasa el chequeo de §2 de standards.
6. PREVIEW — qué combo, qué descuento, sobre qué productos, hasta cuándo. Sin jerga.
7. GATE — "¿lo activo? sí/no" explícito.
8. BACKUP — backup de oferta (kind:"deal") antes de escribir.
9. ESCRIBIR — discountAutomaticBxgyCreate (pct<100) + metafieldsSet worker.deal type:"combo".
   Validar antes con validate_graphql_codeblocks.
10. WORKLOG + CONFIRMAR — "listo, el combo está activo hasta {fecha}".
11. UNDO — "sacá ese combo" → discountAutomaticDeactivate, como toda oferta.
```

- **Sin jerga:** el cliente escucha "combo", "llevándolos juntos ahorrás", nunca "BXGY" ni nombres de campo.
- **Registro** por `store-standards §2`; **humanizer** obligatorio.
- **`allowCombo:false` / sin `maxComboPct`:** el skill dice en natural que armar el combo todavía no está disponible y lo anota; no intenta el write (el guard igual lo bloquearía).

---

## 6. Testing

- **pytest de la caja combo** (`_check_bxgy`): permite un BXGY cruzado a un producto **no** regalable al ≤`maxComboPct`, `get_qty ≤ maxComboGetQty`, `usesPerOrderLimit:1`, con `endsAt`+backup; bloquea `> maxComboPct`; bloquea `pct == 100` (gratis); bloquea `allowCombo:false` y `maxComboPct`/`maxComboGetQty` ausente (fail-closed vía `_combo_ceilings`); **bloquea `get_qty > maxComboGetQty`** (el hueco del OR: "comprá 1, llevate 1000 al 25%"); **bloquea `usesPerOrderLimit != 1`**; **bloquea el buy como colección / `all` / variante** ("comprá cualquier cosa, llevate B"); **bloquea `buy_qty < 1`** ("llevate B sin comprar nada" = cupón); bloquea sin backup; bloquea `productId != buy_gid`.
- **pytest de regresión de la caja regalo:** un regalo gratis a un giftable sigue pasando; un cruzado no-giftable al 100% sigue bloqueado; un cruzado no-giftable al 25% con get_qty alto se bloquea por `maxComboGetQty`.
- **pytest anti mix-and-match** (invariante de §4.1): un documento que NO satisface **ninguna caja COMPLETA** bloquea, aunque cada dimensión suelta la cubra alguna caja — ej: `pct 100` + no-giftable no puede tomar "no-giftable OK" de la caja combo y "pct ≤ maxGiftPct(=100)" de la caja regalo. Las cajas se evalúan completas, en secuencia.
- **pytest del metafield combo** (`_check_bxgy_metafield`/`_check_combo_metafield`): `type:"combo"` con pct (0,100) ≤ techo pasa; pct 100 o > techo bloquea; get sin producto explícito bloquea.
- **Anti-bypass:** combo mezclado con otra mutación → block (un asunto por doc, ya existe); señuelo en variables; un combo que intenta 100% para colar un gratis a un no-giftable → block por las dos cajas.
- **Regresión:** toda la suite de ofertas (escalones, BXGY/regalo) verde.
- **e2e manual (operador, dev store):** crear un combo real, verificar el descuento en checkout, desactivarlo (undo).

---

## 7. Riesgos y límites

- **La aproximación BXGY no es "el set exacto":** un combo "comprá A, llevate B al 15%" descuenta solo B, y dispara con A+B en el carrito (no exige nada más). Es la forma nativa más cercana; el set exacto necesitaría un Function (§2, fuera de alcance). Aceptado.
- **Solapamiento con `armar-regalo`:** los dos usan BXGY. La diferencia es de framing (combo con % vs regalo gratis) y de origen (combo = datos de co-compra; regalo = elección del cliente) y de techo/scope (§4). El guard los separa por `type` en el metafield y por la caja que satisfacen en el discount.
- **Techo `maxComboPct` = 25% es un default** a calibrar con el cliente, igual que los otros techos.
- **Autoatestación del registro:** como toda oferta, el skill escribe su backup; el guard valida la forma/techo/scope, no la intención (modelo de amenaza del v1: el operador/cliente se equivocan, no un actor hostil con shell).

---

## 8. Preguntas abiertas para el plan
- La forma exacta del `worker.deal` `type:"combo"` (¿reusa el schema del `type:"bxgy"` con otro `type`, o agrega campos?). Se decide leyendo `_check_bxgy_metafield` y el spec de BXGY.
- **Resuelto por el review:** `_check_combo_metafield` es función **propia** (no reusa `_check_bxgy_metafield`, que exige giftable y usa `_gift_ceilings`).
- **`maxComboGetQty` default = 2** (un combo suele ser "llevate 1 B"; puede ser MÁS chico que `maxGetQty`). A calibrar con el cliente.
