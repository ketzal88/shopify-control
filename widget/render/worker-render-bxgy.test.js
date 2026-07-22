/* Matemática honesta del regalo (BXGY) — "pagás N", redondeo por unidad.
 * El total del regalo NO puede modelarse como un % único: divergiría del
 * descuento nativo por redondeo (§4.4 del spec del regalo). Este total es la
 * fuente única del monto que comparten builder, widget y el gate del skill. */
const assert = require('assert');
const { computeBxgyTotalCents, computeTierUnitCents } = require('./worker-render.js');

// Comprá 2 + 1 gratis (pct 100): pagás exactamente 2 unidades.
assert.strictEqual(computeBxgyTotalCents(62995, 2, 1, 100), 62995 * 2);
assert.strictEqual(computeBxgyTotalCents(160200, 2, 1, 100), 320400);

// Comprá 2 + 1 al 50%: 2 enteras + 1 media, redondeada POR UNIDAD.
// 62995 * 0.5 = 31497.5 -> 31498 (no 31497). El total no promedia.
assert.strictEqual(computeTierUnitCents(62995, 50), 31498);
assert.strictEqual(computeBxgyTotalCents(62995, 2, 1, 50), 62995 * 2 + 31498);

// Regalo cruzado: mismo cálculo con el precio del PRODUCTO regalado (Q).
// Comprá 1 de P + 1 de Q gratis: el total de esta línea de Q es 0.
assert.strictEqual(computeBxgyTotalCents(0, 0, 1, 100), 0);
// (el widget suma P por separado; acá se prueba el término del regalo)

// pct 0 = sin regalo real: paga todas las unidades enteras.
assert.strictEqual(computeBxgyTotalCents(1000, 2, 1, 0), 3000);

console.log('OK worker-render-bxgy');
