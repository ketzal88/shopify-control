// Tests Node de la lógica del builder: el techo no deja construir inválido + round-trip.
const assert = require('assert');
const B = require('./escalones-builder.logic.js');
const ceiling = { maxDiscountPct: 30, maxDurationDays: 90, maxTiers: 4 };

// --- techo ---
assert.strictEqual(B.tierPctValid(31, ceiling), false, '31% supera el techo');
assert.strictEqual(B.tierPctValid(30, ceiling), true, '30% entra');
assert.strictEqual(B.canAddTier([{ qty: 1, pct: 0 }, { qty: 2, pct: 10 }], ceiling), true);
assert.strictEqual(B.canAddTier([{}, {}, {}, {}], ceiling), false, 'no más de maxTiers');

// --- tiersValid ---
assert.strictEqual(B.tiersValid([{ qty: 1, pct: 0 }, { qty: 2, pct: 10, highlight: true }], ceiling).ok, true);
assert.strictEqual(B.tiersValid([{ qty: 2, pct: 10 }, { qty: 1, pct: 0 }], ceiling).ok, false, 'desordenado');
assert.strictEqual(B.tiersValid([{ qty: 1, pct: 5 }], ceiling).ok, false, 'primero != 0');
assert.strictEqual(B.tiersValid([{ qty: 1, pct: 0 }, { qty: 2, pct: 10 }], ceiling).ok, false, 'sin highlight');
assert.strictEqual(B.tiersValid([{ qty: 1, pct: 0 }, { qty: 1, pct: 10, highlight: true }], ceiling).ok, false, 'qty repetida');
assert.strictEqual(B.tiersValid([{ qty: 1, pct: 0 }, { qty: 2, pct: 40, highlight: true }], ceiling).ok, false, 'pct > techo');

// --- round-trip: emit -> parse -> mismos datos ---
const cfg = {
  product: { id: 'gid://shopify/Product/9', title: 'X' },
  tiers: [{ qty: 1, pct: 0 }, { qty: 2, pct: 10, highlight: true }],
  style: { ink: '#000000' }
};
const text = B.emitConfig(cfg);
assert.ok(text.includes('🧩 escalones-config'), 'lleva el marcador');
assert.deepStrictEqual(B.parseConfig(text), { v: 1, product: cfg.product, tiers: cfg.tiers, style: cfg.style });

// --- smoke del template: los 5 slots existen ---
const fs = require('fs'), path = require('path');
const tpl = fs.readFileSync(path.join(__dirname, 'escalones-builder.template.html'), 'utf8');
['__PRODUCTS_JSON__', '__CEILING_JSON__', '__RENDER_JS__', '__RENDER_CSS__', '__BUILDER_LOGIC__']
  .forEach(function (slot) { assert.ok(tpl.indexOf(slot) >= 0, 'falta el slot ' + slot); });

console.log('OK builder logic + template slots');
