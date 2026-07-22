// Tests Node de la lógica pura de worker-render.js (redondeo por unidad + estilo)
const assert = require('assert');
const { computeTierTotalCents, resolveStyle, DEFAULT_STYLE, formatMoney } = require('./worker-render.js');

// --- lección del centavo: redondeo POR UNIDAD como Shopify ---
assert.strictEqual(computeTierTotalCents(62995, 10, 2), 113392, '2u@10% = $1,133.92');
assert.strictEqual(computeTierTotalCents(62995, 20, 3), 151188, '3u@20% = $1,511.88');
assert.strictEqual(computeTierTotalCents(62995, 0, 1), 62995, '1u = precio');

// --- formato: USD y COP ---
assert.strictEqual(formatMoney(113392, '${{amount}}'), '$1,133.92');
assert.strictEqual(formatMoney(16020000, '${{amount_no_decimals_with_comma_separator}}'), '$160.200');

// --- fallback POR-KEY ---
assert.deepStrictEqual(resolveStyle({}), DEFAULT_STYLE, '{} => todo default');
assert.strictEqual(resolveStyle({ ink: '' }).ink, DEFAULT_STYLE.ink, 'vacío => default');
assert.strictEqual(resolveStyle({ ink: '#000000' }).ink, '#000000', 'presente => override');
assert.strictEqual(resolveStyle({ ink: '#000000' }).sage, DEFAULT_STYLE.sage, 'las otras keys => default');
assert.strictEqual(resolveStyle({ label: 'Comprá más' }).label, 'Comprá más', 'texto override');

console.log('OK worker-render');
