/* python-results-v4-compat.js
 * Bridge ligero para resultados generados por local_cruncher_v4_deep_stacking.py.
 * Convive con V3: solo se activa cuando resultados.json declara
 * score_kind === "v4_deep_stacking_meta_score".
 */
(function () {
  'use strict';

  const V4_SCORE_KIND = 'v4_deep_stacking_meta_score';
  const EXPERT_LABELS = {
    physical: 'Fisica',
    transformer: 'Transformer',
    xgboost: 'XGBoost',
    fourier: 'Fourier',
    graph: 'Grafo',
    meta: 'Meta'
  };

  let cachedResults = null;

  function isV4(data) {
    return !!data && data.score_kind === V4_SCORE_KIND;
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

  function ball(n) {
    return `<span style="display:inline-grid;place-items:center;width:34px;height:34px;border-radius:50%;background:#111927;border:1px solid rgba(88,166,255,.45);color:#e6edf3;font-weight:800;font-family:var(--mono);">${n}</span>`;
  }

  function topDrivers(item) {
    const drivers = item?.drivers || item?.expert_scores_v4 || {};
    return Object.entries(drivers)
      .filter(([, value]) => Number.isFinite(Number(value)))
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 3)
      .map(([key, value]) => `${EXPERT_LABELS[key] || key}: ${num(value, 3)}`)
      .join(' | ');
  }

  async function loadV4Results(force = false) {
    if (cachedResults && !force) return cachedResults;
    try {
      const res = await fetch(`resultados.json?ts=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) return null;
      const data = await res.json();
      cachedResults = isV4(data) ? data : null;
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
    return [
      ['Buffer', `${forget.buffer_size || '?'} sorteos`],
      ['OOS', `${rows} folds`],
      ['Leakage', leak.passed ? 'OK' : 'REVISAR'],
      ['Score', stack.score_kind || V4_SCORE_KIND],
      ['Meta', data.meta_model_audit?.trained ? 'MLP entrenado' : 'Fallback auditado']
    ].map(([label, value]) => (
      `<span style="display:inline-flex;gap:6px;align-items:center;padding:6px 9px;border-radius:6px;border:1px solid rgba(255,255,255,.12);background:rgba(255,255,255,.04);font-size:12px;">
        <b style="color:var(--teal);">${label}</b><span style="color:var(--muted);">${value}</span>
      </span>`
    )).join('');
  }

  function renderV4Panel(data) {
    const panel = ensurePanel();
    if (!panel || !isV4(data)) return;
    const wf = data.walk_forward || {};
    const metrics = wf.metrics || {};
    const top = (data.top_combinations || data.generator_pool || []).slice(0, 3);
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
          ${top.map((item, idx) => `
            <div style="display:flex;gap:8px;align-items:center;justify-content:space-between;border:1px solid rgba(255,255,255,.08);border-radius:8px;padding:8px;">
              <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
                <b style="color:var(--teal);">#${idx + 1}</b>
                ${(item.nums || item.combo || []).map(ball).join('')}
              </div>
              <div style="font-size:12px;color:var(--muted);text-align:right;">${topDrivers(item)}</div>
            </div>
          `).join('')}
        </div>
      </div>`;
    panel.querySelector('#btn-load-v4-top')?.addEventListener('click', () => renderTopCombinations(data));
  }

  function renderTopCombinations(data = cachedResults) {
    if (!isV4(data)) return false;
    const container = document.getElementById('combos-container');
    if (!container) return false;
    const items = (data.generator_pool || data.top_combinations || []).slice(0, 10);
    container.innerHTML = items.map((item, i) => {
      const nums = item.nums || item.combo || [];
      const score = Number(item.score_percent ?? item.net_score * 100 ?? 0);
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
})();
