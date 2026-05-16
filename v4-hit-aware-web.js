// v4-hit-aware-web.js
// Muestra métricas V4.1 hit-aware/calibración en todos los paneles relevantes.
(function () {
  'use strict';

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function fmt(value, digits = 3) {
    return num(value).toFixed(digits);
  }

  function getData() {
    const data = typeof window.getV4Results === 'function'
      ? window.getV4Results()
      : (window.MELATE_V4_RESULTS || window.MELATE_V3_RESULTS);
    if (!data || data.source !== 'local_cruncher_v4_deep_stacking') return null;
    return data;
  }

  function statusColor(ok) {
    return ok ? 'var(--green)' : 'var(--gold)';
  }

  function kpi(label, value, color = 'var(--teal)', sub = '') {
    return `<div class="stat-card"><div class="stat-val" style="font-size:20px;color:${color}">${esc(value)}</div><div class="stat-lbl">${esc(label)}</div>${sub ? `<div style="font-size:10px;color:var(--dim);margin-top:4px;">${esc(sub)}</div>` : ''}</div>`;
  }

  function renderHitAwareSummary() {
    const data = getData();
    if (!data) return false;
    const wf = data.walk_forward || {};
    const cal = data.calibration || {};
    const hit = data.hit_aware_training || {};
    const targets = hit.validation_targets || {};
    const passed = Boolean(targets.passed);
    const avg6 = num(wf.avg_hits_top6 ?? wf.avg_hits);
    const avg10 = num(wf.avg_hits_top10);
    const r2 = num(data.calibration_r2 ?? cal.calibration_r2);
    const hitWeight = num(hit.hit_weight ?? data.meta_model_audit?.hit_weight, NaN);

    const html = `<div id="v4-hit-aware-summary" style="margin:0 0 16px 0;background:linear-gradient(135deg, rgba(57,208,194,.14), rgba(240,180,41,.07));border:1px solid rgba(57,208,194,.45);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div>
          <div style="font-family:var(--cond);font-size:17px;font-weight:800;color:var(--teal);">🎯 V4.1 Hit-Aware activo</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:880px;">
            El ranking usa probabilidad calibrada de hit por número. Loss: BCE con positivos reales + MSE auxiliar; early stopping por hit-rate Top6/Top10.
          </div>
        </div>
        <div style="font-family:var(--mono);font-weight:800;color:${statusColor(passed)};">${passed ? 'OBJETIVOS OK' : 'EN CALIBRACIÓN'}</div>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        ${kpi('avg_hits_top6', fmt(avg6, 3), avg6 > 1 ? 'var(--green)' : 'var(--gold)', 'objetivo > 1.0')}
        ${kpi('avg_hits_top10', fmt(avg10, 3), avg10 > 1.5 ? 'var(--green)' : 'var(--gold)', 'objetivo > 1.5')}
        ${kpi('calibration_r2', fmt(r2, 5), r2 > 0.05 ? 'var(--green)' : 'var(--gold)', 'objetivo > 0.05')}
        ${kpi('hit_weight', Number.isFinite(hitWeight) ? fmt(hitWeight, 3) : 'N/A', 'var(--purple)', 'Optuna BCE/MSE')}
        ${kpi('brier', cal.brier_score ?? 'N/A', 'var(--blue)', 'calibración')}
      </div>
    </div>`;

    const genBody = document.querySelector('#tab-generador .card .card-body');
    if (genBody && !document.getElementById('v4-hit-aware-summary')) {
      const anchor = document.getElementById('v4-primary-panel') || document.getElementById('combos-container') || genBody.firstChild;
      const temp = document.createElement('div');
      temp.innerHTML = html;
      genBody.insertBefore(temp.firstElementChild, anchor);
    }

    const v4Root = document.getElementById('v4-dashboard-root');
    if (v4Root && !document.getElementById('v4-hit-aware-dashboard-block')) {
      const block = document.createElement('div');
      block.id = 'v4-hit-aware-dashboard-block';
      block.className = 'card';
      block.style.cssText = 'border-color:rgba(57,208,194,.45);margin-top:18px;';
      block.innerHTML = `<div class="card-header"><h2>🎯 Calibración Hit-Aware V4.1</h2></div><div class="card-body">${html}</div>`;
      v4Root.insertBefore(block, v4Root.firstChild);
    }

    const stats = document.getElementById('stats-summary');
    if (stats && !document.getElementById('v4-hit-aware-stats-strip')) {
      const strip = document.createElement('div');
      strip.id = 'v4-hit-aware-stats-strip';
      strip.style.gridColumn = '1 / -1';
      strip.innerHTML = html;
      stats.prepend(strip);
    }
    return true;
  }

  function refresh() {
    setTimeout(renderHitAwareSummary, 120);
  }

  document.addEventListener('DOMContentLoaded', refresh);
  document.addEventListener('melate:v4-primary-loaded', refresh);
  document.addEventListener('melate:v4-results-loaded', refresh);
  document.addEventListener('melate:v3-results-loaded', refresh);
  window.renderV4HitAwareSummary = renderHitAwareSummary;
})();
