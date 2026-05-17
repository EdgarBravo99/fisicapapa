// v3-left-right-indicator.js
// Restaura el indicador Izquierda/Derecha en Estadísticas usando resultados V3/V4.
(function () {
  'use strict';

  const originalRenderStatsUI = window.renderStatsUI;

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getV3() {
    const data = typeof window.getV3Results === 'function'
      ? window.getV3Results()
      : (window.MELATE_V4_RESULTS || window.MELATE_V3_RESULTS);
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  function modelName(data) {
    return data?.model_version === 'V4' || data?.v4_score_kind ? 'V4' : 'V3';
  }

  function sideStatsFromCombos(combos) {
    let left = 0;
    let right = 0;
    let total = 0;
    (combos || []).forEach(combo => {
      const nums = Array.isArray(combo) ? combo : (combo?.numbers || combo?.nums || combo?.combo);
      if (!Array.isArray(nums)) return;
      nums.forEach(n => {
        const x = Number(n);
        if (!Number.isFinite(x)) return;
        if (x <= 28) left += 1;
        else right += 1;
        total += 1;
      });
    });
    const leftPct = total ? (left / total) * 100 : 50;
    const rightPct = total ? (right / total) * 100 : 50;
    const bias = total ? (left - right) / total : 0;
    const label = Math.abs(bias) < 0.06
      ? 'Equilibrio'
      : bias > 0
        ? 'Carga IZQUIERDA (1-28)'
        : 'Carga DERECHA (29-56)';
    const color = Math.abs(bias) < 0.06
      ? 'var(--teal)'
      : bias > 0
        ? 'var(--blue)'
        : 'var(--red)';
    return { left, right, total, leftPct, rightPct, bias, label, color };
  }

  function sideStatsFromRows(rows, field = 'actual') {
    const combos = (rows || [])
      .map(row => Array.isArray(row?.[field]) ? row[field] : null)
      .filter(Boolean);
    return sideStatsFromCombos(combos);
  }

  function barHtml(stats, label, sublabel) {
    return `<div style="margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px;gap:10px;">
        <span style="color:var(--muted)">${esc(label)}</span>
        <span style="color:${stats.color};font-weight:bold">${esc(stats.label)}</span>
      </div>
      <div style="display:flex;height:20px;border-radius:5px;overflow:hidden;border:1px solid var(--border);background:rgba(255,255,255,.03);">
        <div style="width:${Math.max(0, Math.min(100, stats.leftPct))}%;background:rgba(88,166,255,0.22);border-right:1px solid var(--blue);display:flex;align-items:center;padding-left:6px;font-size:10px;font-weight:bold;color:var(--blue);white-space:nowrap;">Izq ${Math.round(stats.leftPct)}%</div>
        <div style="width:${Math.max(0, Math.min(100, stats.rightPct))}%;background:rgba(248,81,73,0.22);display:flex;justify-content:flex-end;align-items:center;padding-right:6px;font-size:10px;font-weight:bold;color:var(--red);white-space:nowrap;">Der ${Math.round(stats.rightPct)}%</div>
      </div>
      <div style="font-size:11px;color:var(--dim);margin-top:4px;">${esc(sublabel)} · Izq=${stats.left} · Der=${stats.right} · Bias=${stats.bias.toFixed(3)}</div>
    </div>`;
  }

  function blockRowsFromPool(pool, size = 20, maxBlocks = 5) {
    const blocks = [];
    for (let i = 0; i < Math.min(pool.length, size * maxBlocks); i += size) {
      const chunk = pool.slice(i, i + size);
      if (!chunk.length) break;
      blocks.push({ index: i / size, chunk, stats: sideStatsFromCombos(chunk) });
    }
    return blocks;
  }

  function renderLeftRightIndicator() {
    const data = getV3();
    const trendEl = document.getElementById('trend-chart');
    if (!data || !trendEl) return false;
    const labelModel = modelName(data);

    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    const wfRows = Array.isArray(data.walk_forward?.rows) ? data.walk_forward.rows : [];
    const simulated = sideStatsFromCombos(pool.slice(0, 120));
    const realRecent = sideStatsFromRows(wfRows.slice(-20), 'actual');
    const predictedRecent = sideStatsFromRows(wfRows.slice(-20), 'predicted_top6');
    const blocks = blockRowsFromPool(pool, 20, 5);

    const headline = Math.abs(simulated.bias) < 0.06
      ? `El pool ${labelModel} está relativamente equilibrado entre izquierda y derecha.`
      : simulated.bias > 0
        ? `El pool ${labelModel} se está cargando hacia la izquierda: números 1-28.`
        : `El pool ${labelModel} se está cargando hacia la derecha: números 29-56.`;

    trendEl.innerHTML = `<div style="display:grid;gap:12px;">
      <div style="background:rgba(88,166,255,.07);border:1px solid ${simulated.color};border-radius:10px;padding:12px;">
        <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:center;margin-bottom:8px;">
          <div>
            <div style="font-family:var(--cond);font-size:17px;font-weight:800;color:${simulated.color};">🧭 Indicador Izquierda/Derecha ${labelModel}</div>
            <div style="font-size:12px;color:var(--muted);">${esc(headline)}</div>
          </div>
          <div style="font-family:var(--mono);font-weight:800;color:${simulated.color};font-size:18px;">${esc(simulated.label)}</div>
        </div>
        ${barHtml(simulated, `Futuro simulado · Top 120 ${labelModel}`, `Basado en ${Math.min(pool.length, 120)} combinaciones del generator_pool`)}
        ${wfRows.length ? barHtml(realRecent, 'Backtesting real reciente · Sorteos OOS', `Últimos ${Math.min(wfRows.length, 20)} sorteos reales evaluados`) : ''}
        ${wfRows.length ? barHtml(predictedRecent, `Predicción Walk-Forward reciente · Top6 ${labelModel}`, `Top6 propuesto en los últimos ${Math.min(wfRows.length, 20)} folds`) : ''}
      </div>
      <div style="background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Bloques de 20 combinaciones del pool ${labelModel}</div>
        ${blocks.map(block => barHtml(block.stats, `Bloque ${block.index + 1}`, `Combinaciones ${block.index * 20 + 1}-${block.index * 20 + block.chunk.length}`)).join('') || '<div style="color:var(--muted);font-size:12px;">Sin generator_pool suficiente para bloques.</div>'}
      </div>
    </div>`;
    return true;
  }

  window.renderV3LeftRightIndicator = renderLeftRightIndicator;

  window.renderStatsUI = function renderStatsUIWithLeftRight() {
    if (typeof originalRenderStatsUI === 'function') originalRenderStatsUI();
    renderLeftRightIndicator();
  };

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => {
      if (document.getElementById('tab-estadisticas')?.classList.contains('active')) renderLeftRightIndicator();
    }, 250);
  });

  document.addEventListener('melate:v3-results-loaded', () => {
    setTimeout(() => {
      if (document.getElementById('tab-estadisticas')?.classList.contains('active')) renderLeftRightIndicator();
    }, 80);
  });
  document.addEventListener('melate:v4-primary-loaded', () => {
    setTimeout(() => {
      if (document.getElementById('tab-estadisticas')?.classList.contains('active')) renderLeftRightIndicator();
    }, 80);
  });
})();

(function () {
  'use strict';
  if (window.__v3AuxLoader) return;
  window.__v3AuxLoader = true;

  function injectScript(src, flagName) {
    if (window[flagName]) return;
    const base = src.split('?')[0];
    if (document.querySelector(`script[src^="${base}"]`)) return;
    const s = document.createElement('script');
    s.src = `${base}?v=${Date.now()}`;
    s.onload = () => { window[flagName] = true; };
    s.onerror = () => console.warn(`No se pudo cargar ${base}`);
    document.body.appendChild(s);
  }

  function loadV3AuxPanels() {
    injectScript('pakin-remote-loader.js', '__pakinRemoteLoaderLoaded');
    injectScript('v3-generator-elite-rank.js', '__v3EliteGeneratorRankLoaded');
    injectScript('v3-model-portfolio-panel.js', '__v3ModelPortfolioPanelLoaded');
    injectScript('v3-results-live-refresh.js', '__v3ResultsLiveRefreshLoaded');
    injectScript('v4-primary-web.js', '__v4PrimaryWebLoaded');
    injectScript('v4-hit-aware-web.js', '__v4HitAwareWebLoaded');
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadV3AuxPanels);
  } else {
    loadV3AuxPanels();
  }
})();
