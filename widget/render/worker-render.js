/* ==========================================================================
 * worker-render.js · render del widget de escalones (fuente única)
 * --------------------------------------------------------------------------
 * FUENTE ÚNICA del render. Lo usan dos lugares:
 *   - el widget (widget/worker-escalones.liquid) — lo inlinea y le suma el init
 *     de storefront (onBuy/preselectFromCart/setupCollapse), que NO viven acá;
 *   - el builder (widget/escalones-builder.template.html) — llama render() en
 *     cada cambio para el preview, y NUNCA toca el carrito.
 *
 * `render()` es PURO y builder-safe: solo construye/estila el DOM, sin fetch,
 * sin /cart, sin listeners de compra. Esa es la frontera del spec §4.
 *
 * DEFAULT_STYLE tiene que quedar SINCRONIZADO con los defaults del <style> del
 * .liquid y con los textos hardcodeados, o "sin worker.style = se ve como hoy"
 * deja de valer.
 * ========================================================================== */
(function (global) {
  'use strict';

  var DEFAULT_STYLE = {
    ink: '#4B4B4B', sage: '#9CB0B1', taupe: '#CEC4BA', cream: '#E9E6DD',
    label: 'Llevá más y ahorrá', badge: 'MÁS ELEGIDO'
  };

  // Fallback POR-KEY: cada clave ausente o vacía cae al default. Así un {} (el
  // "sacar el look" de §9.2) resetea TODO, no solo la ausencia del metafield.
  function resolveStyle(style) {
    style = style || {};
    var out = {};
    Object.keys(DEFAULT_STYLE).forEach(function (k) {
      var v = style[k];
      out[k] = (typeof v === 'string' && v.length) ? v : DEFAULT_STYLE[k];
    });
    return out;
  }

  // Dinero: formateador clásico de Shopify (respeta shop.money_format).
  function formatMoney(cents, format) {
    format = format || '${{amount}}';
    var m = format.match(/\{\{\s*(\w+)\s*\}\}/);
    if (!m) return format;
    function delim(number, precision, thousands, decimal) {
      thousands = thousands == null ? ',' : thousands;
      decimal = decimal == null ? '.' : decimal;
      if (isNaN(number) || number == null) number = 0;
      number = (number / 100.0).toFixed(precision);
      var parts = number.split('.');
      var whole = parts[0].replace(/(\d)(?=(\d\d\d)+(?!\d))/g, '$1' + thousands);
      return whole + (parts[1] ? decimal + parts[1] : '');
    }
    var value;
    switch (m[1]) {
      case 'amount': value = delim(cents, 2); break;
      case 'amount_no_decimals': value = delim(cents, 0); break;
      case 'amount_with_comma_separator': value = delim(cents, 2, '.', ','); break;
      case 'amount_no_decimals_with_comma_separator': value = delim(cents, 0, '.', ','); break;
      case 'amount_with_apostrophe_separator': value = delim(cents, 2, "'", '.'); break;
      case 'amount_no_decimals_with_space_separator': value = delim(cents, 0, ' ', ''); break;
      case 'amount_with_space_separator': value = delim(cents, 2, ' ', ','); break;
      default: value = delim(cents, 2);
    }
    return format.replace(/\{\{\s*\w+\s*\}\}/, value);
  }

  // LECCIÓN DEL CENTAVO (§14): Shopify redondea POR UNIDAD y después multiplica.
  function computeTierUnitCents(unit, pct) { return Math.round(unit * (100 - pct) / 100); }
  function computeTierTotalCents(unit, pct, qty) { return computeTierUnitCents(unit, pct) * qty; }

  // REGALO / BXGY: "pagás buyQty enteras + getQty al pct". Modelarlo como un %
  // único mentiría por redondeo contra el descuento nativo (que cobra las buyQty
  // completas + las getQty con su effect, sin promediar). El total honesto es
  // este, con el MISMO redondeo por unidad del centavo. pct=100 => el regalo sale
  // gratis. Fuente única del monto: la comparte el builder, el widget y el gate.
  function computeBxgyTotalCents(unit, buyQty, getQty, pct) {
    return buyQty * unit + getQty * computeTierUnitCents(unit, pct);
  }

  function el(tag, cls, text) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  }

  // Aplica el estilo resuelto como CSS vars + textos. Devuelve el estilo resuelto.
  function applyStyle(root, style) {
    var s = resolveStyle(style);
    root.style.setProperty('--we-ink', s.ink);
    root.style.setProperty('--we-sage', s.sage);
    root.style.setProperty('--we-taupe', s.taupe);
    root.style.setProperty('--we-cream', s.cream);
    var labelEl = root.querySelector('.we-label');
    if (labelEl) labelEl.textContent = s.label;
    return s;
  }

  function qtyLabel(q) { return q + ' ' + (q === 1 ? 'unidad' : 'unidades'); }

  /* render(root, data) — PURO / builder-safe. data = {deal, variants, cfg, style}.
   * Devuelve un controlador { tiers, select, selectedIndex, selectedTier,
   * chosenVariant, cta } para que el init de storefront (en el .liquid) enganche
   * preselect/compra/colapso SIN que el render sepa nada de eso. */
  function render(root, data) {
    var deal = data.deal || {};
    var cfg = data.cfg || {};
    var variants = data.variants || [];
    var tiers = (deal.tiers || []).slice().sort(function (a, b) { return a.qty - b.qty; });
    var unit = cfg.unitPriceCents;
    var s = applyStyle(root, data.style);

    var selectedIdx = 0;
    var chosenVariant = (variants.filter(function (v) { return v.available; })[0] || variants[0] || {}).id;

    function buildRows() {
      var box = root.querySelector('[data-we-tiers]');
      box.textContent = '';
      tiers.forEach(function (t, i) {
        var row = el('button', 'we-row' + (i === selectedIdx ? ' on' : ''));
        row.type = 'button';
        row.setAttribute('data-we-idx', i);
        if (t.highlight) row.appendChild(el('span', 'we-pop', s.badge));
        row.appendChild(el('span', 'we-radio'));
        if (cfg.imageUrl) {
          var img = el('img', 'we-thumb'); img.src = cfg.imageUrl; img.alt = ''; img.loading = 'lazy';
          row.appendChild(img);
        } else {
          row.appendChild(el('span', 'we-thumb'));
        }
        var mid = el('span', 'we-mid');
        mid.appendChild(el('span', 'we-qty', qtyLabel(t.qty)));
        if (t.pct > 0) mid.appendChild(el('span', 'we-save', 'AHORRÁS ' + t.pct + '%'));
        row.appendChild(mid);
        var prices = el('span', 'we-prices');
        prices.appendChild(el('span', 'we-total', formatMoney(computeTierTotalCents(unit, t.pct, t.qty), cfg.moneyFormat)));
        if (t.pct > 0) prices.appendChild(el('span', 'we-old', formatMoney(unit * t.qty, cfg.moneyFormat)));
        row.appendChild(prices);
        row.addEventListener('click', function () { select(i); });
        box.appendChild(row);
      });
    }

    function paintNudge() {
      var nudge = root.querySelector('[data-we-nudge]');
      var fill = root.querySelector('[data-we-fill]');
      var txt = root.querySelector('[data-we-nudge-txt]');
      nudge.hidden = false;
      txt.textContent = '';
      var last = tiers.length - 1;
      if (selectedIdx >= last) {
        nudge.classList.add('is-max');
        txt.appendChild(document.createTextNode('✓ Ahorro máximo'));
        return;
      }
      nudge.classList.remove('is-max');
      var next = tiers[selectedIdx + 1];
      var diff = next.qty - tiers[selectedIdx].qty;
      fill.style.width = Math.round(selectedIdx / last * 100) + '%';
      txt.appendChild(document.createTextNode('Sumá '));
      txt.appendChild(el('strong', null, diff + ' más'));
      txt.appendChild(document.createTextNode(' → '));
      txt.appendChild(el('strong', null, next.pct + '%'));
    }

    function paintCta() {
      var cta = root.querySelector('[data-we-cta]');
      var t = tiers[selectedIdx];
      cta.disabled = false;
      cta.textContent = 'Llevar ' + t.qty + ' · ' + formatMoney(computeTierTotalCents(unit, t.pct, t.qty), cfg.moneyFormat);
    }

    function select(i) {
      selectedIdx = i;
      root.querySelectorAll('.we-row').forEach(function (r, idx) { r.classList.toggle('on', idx === i); });
      paintNudge();
      paintCta();
    }

    buildRows();
    paintNudge();
    paintCta();
    root.hidden = false;

    return {
      tiers: tiers,
      select: select,
      selectedIndex: function () { return selectedIdx; },
      selectedTier: function () { return tiers[selectedIdx]; },
      chosenVariant: chosenVariant,
      cta: root.querySelector('[data-we-cta]')
    };
  }

  var api = {
    DEFAULT_STYLE: DEFAULT_STYLE,
    resolveStyle: resolveStyle,
    applyStyle: applyStyle,
    formatMoney: formatMoney,
    computeTierUnitCents: computeTierUnitCents,
    computeTierTotalCents: computeTierTotalCents,
    computeBxgyTotalCents: computeBxgyTotalCents,
    render: render
  };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (typeof window !== 'undefined') window.WorkerEscalones = api;
})(typeof globalThis !== 'undefined' ? globalThis : this);
