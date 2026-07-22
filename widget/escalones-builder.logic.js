/* ==========================================================================
 * escalones-builder.logic.js · lógica pura del builder (testeable en Node)
 * --------------------------------------------------------------------------
 * El techo (mismas reglas que _check_tiers_schema del guard) + emit/parse de la
 * config. NO toca el DOM ni Shopify. La inlinea el template; la testea Node.
 * ========================================================================== */
(function (global) {
  'use strict';

  var STYLE_KEYS = ['ink', 'sage', 'taupe', 'cream', 'label', 'badge'];
  var MARKER = '🧩 escalones-config';

  function isInt(n) { return typeof n === 'number' && isFinite(n) && Math.floor(n) === n; }

  // ¿este % entra en el techo? (entero, 0..maxDiscountPct)
  function tierPctValid(pct, ceiling) {
    return isInt(pct) && pct >= 0 && pct <= ceiling.maxDiscountPct;
  }

  // ¿se puede agregar otro escalón sin pasar maxTiers?
  function canAddTier(tiers, ceiling) {
    return (tiers ? tiers.length : 0) < ceiling.maxTiers;
  }

  // Mismas reglas que el guard: entero, orden asc, sin repetidos, primero 0%,
  // exactamente un destacado, <= maxTiers, cada pct <= maxDiscountPct.
  function tiersValid(tiers, ceiling) {
    if (!Array.isArray(tiers) || !tiers.length) return { ok: false, reason: 'sin escalones' };
    if (tiers.length > ceiling.maxTiers) return { ok: false, reason: 'demasiados escalones' };
    var qtys = [];
    for (var i = 0; i < tiers.length; i++) {
      var t = tiers[i];
      if (!isInt(t.qty) || t.qty < 1) return { ok: false, reason: 'cantidad inválida' };
      if (!isInt(t.pct) || t.pct < 0 || t.pct > 100) return { ok: false, reason: 'porcentaje inválido' };
      if (t.pct > ceiling.maxDiscountPct) return { ok: false, reason: 'un escalón supera el techo' };
      qtys.push(t.qty);
    }
    for (var j = 1; j < qtys.length; j++) {
      if (qtys[j] <= qtys[j - 1]) return { ok: false, reason: 'escalones desordenados o repetidos' };
    }
    if (tiers[0].pct !== 0) return { ok: false, reason: 'el primer escalón no puede tener descuento' };
    var hi = tiers.filter(function (t) { return t.highlight; }).length;
    if (hi !== 1) return { ok: false, reason: 'tiene que haber exactamente un destacado' };
    return { ok: true, reason: null };
  }

  function emitConfig(cfg) {
    var out = { v: 1, product: cfg.product, tiers: cfg.tiers };
    if (cfg.style && Object.keys(cfg.style).length) out.style = cfg.style;
    return MARKER + '\n' + JSON.stringify(out, null, 2);
  }

  function parseConfig(text) {
    var idx = text.indexOf(MARKER);
    var body = idx >= 0 ? text.slice(idx + MARKER.length) : text;
    var start = body.indexOf('{');
    if (start < 0) return null;
    var depth = 0, inStr = false, esc = false, end = -1;
    for (var i = start; i < body.length; i++) {
      var c = body[i];
      if (inStr) { if (esc) esc = false; else if (c === '\\') esc = true; else if (c === '"') inStr = false; continue; }
      if (c === '"') inStr = true;
      else if (c === '{') depth++;
      else if (c === '}') { depth--; if (depth === 0) { end = i + 1; break; } }
    }
    if (end < 0) return null;
    return JSON.parse(body.slice(start, end));
  }

  var api = { STYLE_KEYS: STYLE_KEYS, MARKER: MARKER, tierPctValid: tierPctValid,
              canAddTier: canAddTier, tiersValid: tiersValid,
              emitConfig: emitConfig, parseConfig: parseConfig };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.EscalonesBuilder = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
