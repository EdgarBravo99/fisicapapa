/* python-results-v4-compat.js
 * Bridge ligero para resultados generados por local_cruncher_v4_deep_stacking.py.
 * Convive con V3 y se activa cuando resultados.json declara model_version === "V4"
 * o v4_score_kind === "v4_deep_stacking_meta_score".
 */
(function () {
  'use strict';

  const V4_SCORE_KIND = 'v4_deep_stacking_meta_score';
  const EXPERT_LABELS = {
    physical: 'Física',
    transformer: 'Transformer',
    xgboost: 'XGBoost',
    fourier: 'Fourier',
    graph: 'Grafo',
    meta: 'Meta'
  };

  let cachedResults = null;

  function isV4(data) {
    return Boolean(data && (
      data.model_version === 'V4' ||
      data.v4_score_kind === V4_SCORE_KIND ||
      data.score_kind === V4_SCORE_KIND ||
      data.source === 'local_cruncher_v4_deep_stacking'
    ));
  }

  function pct(value, digits = 1) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '0.0%';
    return `${n.toFixed(digits)}%`;
  }

  function num(value, digits = 4) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : '0';
  }

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function comboNumbers(item) {
    return (item?.numbers || item?.nums || item?.combo || []).map(Number).filter(Number.isFinite);
  }

  function ball(n) {
    return `<span style="display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:#111927;border:1px solid rgba(88,166,255,.45);color:#e6edf3;font-weight:800;font-family:var(--mono);">${esc(n)}</span>`;
  }

  function topDrivers(item) {
    if (item?.plain_route) return esc(item.plain_route);
    if (Array.isArray(item?.number_explanations) && item.number_explanations.length) {
      return item.number_explanations
        .map(row => `${row.number}: ${row.main_driver_human || EXPERT_LABELS[row.main_driver] || row.main_driver || 'V4'}`)
        .join(' | ');
    }
    const drivers = item?.drivers || item?.expert_scores_v4 || {};
    const txt = Object.entries(drivers)
      .filter(([, value]) => Number.isFinite(Number(value)))
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 3)
      .map(([key, value]) => `${EXPERT_LABELS[key] || key}: ${num(value, 3)}`)
      .join(' | ');
    return esc(txt || item?.human_explanation || item?.procedure || 'Sin desglose V4 disponible');
  }

  async function loadV4Results(force = false) {
    if (cachedResults && !force) return cachedResults;
    try {
      const res = await fetch(`resultados.json?ts=${Date.now()}&v4=${Math.random().toString(36).slice(2)}`, {
        cache: 'no-store',
        headers: {
          'Cache-Control': 'no-cache, no-store, must-revalidate',
          Pragma: 'no-cache',
          Expires: '0'
        }
      });
      if (!res.ok) return null;
      const data = await res.json();
      cachedResults = isV4(data) ? data : null;
      window.MELATE_V4_RESULTS = cachedResults;
      if (cachedResults) {
        window.dispatchEvent(new CustomEvent('melate:v4-results-loaded', { detail: cachedResults }));
      }
      return cachedResults;
    } catch (error) {
      console.warn('No se pudieron cargar resultados V4:', error);
      return null;
    }
  }

  function ensurePanel() {
    const anchor = document.getElementById('combos-container');
    if (!anchor) return null;
    let panel = document.getElementById('v4-deep-stacking-panel');
    if (panel) return panel;
    panel = document.createElement('div');
    panel.id = 'v4-deep-stacking-panel';
    panel.className = 'card';
    panel.style.cssText = 'margin-bottom:16px;border-color:rgba(57,208,194,.45);';
    anchor.parentNode.insertBefore(panel, anchor);
    return panel;
  }

  function renderAuditPills(data) {
    const leak = data.leakage_audit || {};
    const stack = data.deep_stacking || {};
    const forget = data.historical_forgetting || {};
    const wf = data.walk_forward || {};
    const rows = Array.isArray(wf.rows) ? wf.rows.length : 0;
    const buffer = forget.recent_buffer_size || forget.buffer_size || '?';
    return [
      ['Buffer', `${buffer} sorteos`],
      ['OOS', `${rows} folds`],
      ['Leakage', leak.passed ? 'OK' : 'REVISAR'],
      ['Score', stack.score_kind || data.v4_score_kind || V4_SCORE_KIND],
      ['Meta', data.meta_model_audit?.trained ? 'MLP entrenado' : 'Fallback auditado']
    ].map(([label, value]) => (
      `<span style="display:inline-flex;gap:6px;align-items:center;padding:6px 9px;border-radius:6px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);font-size:12px;">
        <b style="color:var(--teal);">${esc(label)}</b><span style="color:var(--muted);">${esc(value)}</span>
      </span>`
    )).join('');
  }

  function renderV4Panel(data) {
    const panel = ensurePanel();
    if (!panel || !isV4(data)) return;
    const wf = data.walk_forward || {};
    const metrics = wf.metrics || {};
    const top = (data.model_portfolio?.top10 || data.top_combinations || data.generator_pool || []).slice(0, 3);
    panel.innerHTML = `
      <div class="card-header">
        <h2>V4 Deep Stacking Local</h2>
        <button class="btn btn-sm btn-teal" id="btn-load-v4-top">Cargar Top 10 V4</button>
      </div>
      <div class="card-body" style="display:grid;gap:12px;">
        <div style="display:flex;gap:8px;flex-wrap:wrap;">${renderAuditPills(data)}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:10px;">
          <div style="background:rgba(57,208,194,.08);border:1px solid rgba(57,208,194,.2);border-radius:8px;padding:10px;">
            <div style="font-size:12px;color:var(--muted);">Hit rate OOS</div>
            <div style="font-size:22px;font-weight:800;color:var(--teal);">${pct((metrics.hit_rate || 0) * 100)}</div>
          </div>
          <div style="background:rgba(240,180,41,.08);border:1px solid rgba(240,180,41,.2);border-radius:8px;padding:10px;">
            <div style="font-size:12px;color:var(--muted);">Meta loss</div>
            <div style="font-size:22px;font-weight:800;color:var(--gold);">${num(metrics.mean_meta_loss || 0, 5)}</div>
          </div>
          <div style="background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.2);border-radius:8px;padding:10px;">
            <div style="font-size:12px;color:var(--muted);">Varianza error ult. 3</div>
            <div style="font-size:22px;font-weight:800;color:var(--purple);">${num(metrics.last3_error_variance || 0, 5)}</div>
          </div>
        </div>
        <div style="display:grid;gap:8px;">
          ${top.map((item, idx) => {
            const nums = comboNumbers(item);
            return `<div style="display:flex;gap:8px;align-items:center;justify-content:space-between;border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:8px;">
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <b style="color:var(--teal);">#${idx + 1}</b>
                ${nums.map(ball).join('')}
              </div>
              <div style="font-size:12px;color:var(--muted);text-align:right;max-width:420px;">${topDrivers(item)}</div>
            </div>`;
          }).join('')}
        </div>
      </div>`;
    panel.querySelector('#btn-load-v4-top')?.addEventListener('click', () => renderTopCombinations(data));
  }

  function renderTopCombinations(data = cachedResults) {
    if (!isV4(data)) return false;
    const container = document.getElementById('combos-container');
    if (!container) return false;
    const items = (data.model_portfolio?.top10 || data.generator_pool || data.top_combinations || []).slice(0, 10);
    container.innerHTML = items.map((item, i) => {
      const nums = comboNumbers(item);
      const score = Number(item.score_percent ?? (Number(item.net_score || 0) * 100));
      return `<div class="combo-card" style="border-color:rgba(57,208,194,.42)">
        <div class="combo-card-header">
          <span style="color:var(--teal);font-weight:700">#${i + 1} | V4 Deep Stacking</span>
          <span style="background:rgba(57,208,194,.16);padding:4px 8px;border-radius:4px;color:var(--teal);font-family:var(--mono)">META: ${num(score, 2)}</span>
        </div>
        <div class="combo-balls">${nums.map(ball).join('')}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;">${topDrivers(item)}</div>
      </div>`;
    }).join('');
    const info = document.getElementById('combo-info');
    if (info) info.textContent = `${items.length} jugadas V4`;
    return true;
  }

  async function boot() {
    const data = await loadV4Results();
    if (data) renderV4Panel(data);
  }

  window.MelateV4Bridge = {
    load: loadV4Results,
    renderPanel: renderV4Panel,
    renderTopCombinations,
    labels: EXPERT_LABELS
  };

  document.addEventListener('DOMContentLoaded', boot);
  window.addEventListener('focus', () => loadV4Results(true).then(data => data && renderV4Panel(data)));
})();
