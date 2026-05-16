// v4-hit-aware-web.js
// Muestra métricas V4.1 hit-aware/calibración y simulador web-side de hits.
(function () {
  'use strict';

  const PICK_COUNT = 6;

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

  function pct(value, digits = 1) {
    return `${fmt(value, digits)}%`;
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

  function walkForwardRows(data) {
    return Array.isArray(data?.walk_forward?.rows) ? data.walk_forward.rows : [];
  }

  function hitDistributionFromRows(rows, field = 'hits') {
    const counts = Array(7).fill(0);
    rows.forEach(row => {
      const h = Math.max(0, Math.min(6, Math.round(num(row?.[field], 0))));
      counts[h] += 1;
    });
    const total = counts.reduce((a, b) => a + b, 0) || 1;
    return counts.map(c => c / total);
  }

  function distributionBars(dist, color = 'var(--teal)') {
    return dist.map((p, hits) => `<div style="display:grid;grid-template-columns:34px 1fr 52px;gap:8px;align-items:center;font-size:11px;">
      <b style="color:${color}">${hits} hit${hits === 1 ? '' : 's'}</b>
      <div style="height:8px;border-radius:999px;background:rgba(255,255,255,.08);overflow:hidden;"><div style="width:${Math.min(100, p * 100)}%;height:100%;background:${color};"></div></div>
      <span style="font-family:var(--mono);color:var(--muted);text-align:right;">${pct(p * 100, 1)}</span>
    </div>`).join('');
  }

  function getNumberProbability(data, n) {
    const calibrated = data?.calibrated_hit_probabilities || {};
    if (Number.isFinite(Number(calibrated[String(n)]))) return Math.max(0, Math.min(1, Number(calibrated[String(n)])));
    const scores = data?.number_scores || {};
    if (Number.isFinite(Number(scores[String(n)]))) return Math.max(0, Math.min(1, Number(scores[String(n)]) / 100));
    const row = data?.numberMap?.get?.(Number(n));
    if (row && Number.isFinite(Number(row.score))) return Math.max(0, Math.min(1, Number(row.score) / 100));
    return 6 / 56;
  }

  function poissonBinomial(probs) {
    const dp = Array(PICK_COUNT + 1).fill(0);
    dp[0] = 1;
    probs.forEach(pRaw => {
      const p = Math.max(0, Math.min(1, Number(pRaw) || 0));
      for (let k = PICK_COUNT; k >= 0; k--) {
        dp[k] = dp[k] * (1 - p) + (k > 0 ? dp[k - 1] * p : 0);
      }
    });
    const sum = dp.reduce((a, b) => a + b, 0) || 1;
    return dp.map(x => x / sum);
  }

  function readManualNumbers() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`)?.value, 10));
    if (nums.some(n => Number.isNaN(n) || n < 1 || n > 56)) return null;
    if (new Set(nums).size !== 6) return null;
    return nums.sort((a, b) => a - b);
  }

  function comboNumbers(item) {
    return (item?.numbers || item?.nums || item?.combo || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  }

  function poolSupport(data, nums) {
    const pool = Array.isArray(data?.generator_pool) ? data.generator_pool.slice(0, 250) : [];
    const support = new Map(nums.map(n => [n, 0]));
    const overlapCounts = Array(7).fill(0);
    pool.forEach(item => {
      const combo = comboNumbers(item);
      const overlap = combo.filter(n => support.has(n)).length;
      overlapCounts[overlap] += 1;
      combo.forEach(n => {
        if (support.has(n)) support.set(n, support.get(n) + 1);
      });
    });
    const total = pool.length || 1;
    return {
      total,
      support: nums.map(n => ({ number: n, count: support.get(n) || 0, pct: ((support.get(n) || 0) / total) * 100 })),
      overlapDist: overlapCounts.map(c => c / total),
      avgOverlap: overlapCounts.reduce((acc, c, h) => acc + c * h, 0) / total
    };
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
    const success6 = (avg6 / PICK_COUNT) * 100;
    const success10 = (avg10 / PICK_COUNT) * 100;
    const r2 = num(data.calibration_r2 ?? cal.calibration_r2);
    const hitWeight = num(hit.hit_weight ?? data.meta_model_audit?.hit_weight, NaN);
    const rows = walkForwardRows(data);
    const distTop6 = hitDistributionFromRows(rows, 'hits_top6');
    const distTop10 = hitDistributionFromRows(rows, 'hits_top10');

    const html = `<div id="v4-hit-aware-summary" style="margin:0 0 16px 0;background:linear-gradient(135deg, rgba(57,208,194,.14), rgba(240,180,41,.07));border:1px solid rgba(57,208,194,.45);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div>
          <div style="font-family:var(--cond);font-size:17px;font-weight:800;color:var(--teal);">🎯 V4.1 Hit-Aware activo</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:900px;">
            Métricas expresadas en hits reales OOS: avg_hits_top6/top10 y porcentaje de cobertura sobre los 6 números ganadores. El simulador manual usa probabilidades calibradas de hit y el pool generado por búsqueda exhaustiva.
          </div>
        </div>
        <div style="font-family:var(--mono);font-weight:800;color:${statusColor(passed)};">${passed ? 'OBJETIVOS OK' : 'EN CALIBRACIÓN'}</div>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        ${kpi('avg_hits_top6', fmt(avg6, 3), avg6 > 1 ? 'var(--green)' : 'var(--gold)', 'hits promedio en Top6')}
        ${kpi('éxito Top6', pct(success6, 1), success6 > 16.67 ? 'var(--green)' : 'var(--gold)', 'avg_hits_top6 / 6')}
        ${kpi('avg_hits_top10', fmt(avg10, 3), avg10 > 1.5 ? 'var(--green)' : 'var(--gold)', 'hits promedio en Top10')}
        ${kpi('éxito Top10', pct(success10, 1), success10 > 25 ? 'var(--green)' : 'var(--gold)', 'avg_hits_top10 / 6')}
        ${kpi('calibration_r2', fmt(r2, 5), r2 > 0.05 ? 'var(--green)' : 'var(--gold)', 'objetivo > 0.05')}
        ${kpi('hit_weight', Number.isFinite(hitWeight) ? fmt(hitWeight, 3) : 'N/A', 'var(--purple)', 'Optuna BCE/MSE')}
      </div>
      <details style="margin-top:12px;">
        <summary style="cursor:pointer;color:var(--teal);font-weight:700;font-size:12px;">Distribución histórica OOS de hits</summary>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin-top:10px;">
          <div><div style="font-size:12px;color:var(--muted);margin-bottom:6px;">Top6 histórico</div>${distributionBars(distTop6, 'var(--teal)')}</div>
          <div><div style="font-size:12px;color:var(--muted);margin-bottom:6px;">Top10 histórico</div>${distributionBars(distTop10, 'var(--gold)')}</div>
        </div>
      </details>
    </div>`;

    const genBody = document.querySelector('#tab-generador .card .card-body');
    const oldGen = document.getElementById('v4-hit-aware-summary');
    if (oldGen) oldGen.remove();
    if (genBody) {
      const anchor = document.getElementById('v4-primary-panel') || document.getElementById('combos-container') || genBody.firstChild;
      const temp = document.createElement('div');
      temp.innerHTML = html;
      genBody.insertBefore(temp.firstElementChild, anchor);
    }

    const v4Root = document.getElementById('v4-dashboard-root');
    const oldDash = document.getElementById('v4-hit-aware-dashboard-block');
    if (oldDash) oldDash.remove();
    if (v4Root) {
      const block = document.createElement('div');
      block.id = 'v4-hit-aware-dashboard-block';
      block.className = 'card';
      block.style.cssText = 'border-color:rgba(57,208,194,.45);margin-top:18px;';
      block.innerHTML = `<div class="card-header"><h2>🎯 Calibración y éxito OOS V4.1</h2></div><div class="card-body">${html}</div>`;
      v4Root.insertBefore(block, v4Root.firstChild);
    }

    const stats = document.getElementById('stats-summary');
    const oldStats = document.getElementById('v4-hit-aware-stats-strip');
    if (oldStats) oldStats.remove();
    if (stats) {
      const strip = document.createElement('div');
      strip.id = 'v4-hit-aware-stats-strip';
      strip.style.gridColumn = '1 / -1';
      strip.innerHTML = html;
      stats.prepend(strip);
    }
    return true;
  }

  function simulateManualHits(data, nums) {
    const probs = nums.map(n => getNumberProbability(data, n));
    const dist = poissonBinomial(probs);
    const expected = probs.reduce((a, b) => a + b, 0);
    const atLeast1 = dist.slice(1).reduce((a, b) => a + b, 0);
    const atLeast2 = dist.slice(2).reduce((a, b) => a + b, 0);
    const atLeast3 = dist.slice(3).reduce((a, b) => a + b, 0);
    const modeHits = dist.reduce((best, p, i) => p > dist[best] ? i : best, 0);
    const support = poolSupport(data, nums);
    const wf = data.walk_forward || {};
    const avg6 = num(wf.avg_hits_top6 ?? wf.avg_hits);
    const avg10 = num(wf.avg_hits_top10);
    return { probs, dist, expected, atLeast1, atLeast2, atLeast3, modeHits, support, avg6, avg10 };
  }

  function renderManualSimulator() {
    const data = getData();
    const target = document.getElementById('user-result');
    const nums = readManualNumbers();
    if (!data || !target || !nums) return false;
    const old = document.getElementById('v4-manual-hit-simulator');
    if (old) old.remove();
    const sim = simulateManualHits(data, nums);
    const probRows = nums.map((n, i) => `<tr><td><b>${n}</b></td><td>${pct(sim.probs[i] * 100, 2)}</td><td>${pct(sim.support.support[i]?.pct || 0, 1)}</td></tr>`).join('');
    const riskColor = sim.atLeast3 >= 0.12 ? 'var(--green)' : sim.atLeast2 >= 0.25 ? 'var(--gold)' : 'var(--teal)';
    const html = `<div id="v4-manual-hit-simulator" style="margin-top:14px;border:1px solid ${riskColor};border-radius:10px;padding:14px;background:rgba(255,255,255,.035);">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;">
        <div>
          <div style="font-family:var(--cond);font-size:16px;font-weight:800;color:${riskColor};">🧪 Simulador web-side de hits posibles</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:850px;">
            Estimación informativa usando probabilidades calibradas de V4.1 por número y soporte en el generator_pool. No altera el cruncher ni recalcula Python.
          </div>
        </div>
        <div style="font-family:var(--mono);font-size:22px;font-weight:800;color:${riskColor};">E[hits] ${fmt(sim.expected, 3)}</div>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        ${kpi('hit más probable', `${sim.modeHits}`, riskColor, 'modo de distribución')}
        ${kpi('P(≥1 hit)', pct(sim.atLeast1 * 100, 1), 'var(--teal)')}
        ${kpi('P(≥2 hits)', pct(sim.atLeast2 * 100, 1), 'var(--gold)')}
        ${kpi('P(≥3 hits)', pct(sim.atLeast3 * 100, 1), 'var(--green)')}
        ${kpi('overlap pool', fmt(sim.support.avgOverlap, 2), 'var(--purple)', 'vs Top 250')}
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px;margin-top:12px;">
        <div style="background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:8px;padding:10px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">Distribución estimada para tu combinación</div>
          ${distributionBars(sim.dist, riskColor)}
        </div>
        <div style="background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:8px;padding:10px;">
          <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">Probabilidad calibrada y soporte por número</div>
          <div class="tbl-wrap"><table><thead><tr><th>#</th><th>P(hit)</th><th>Pool</th></tr></thead><tbody>${probRows}</tbody></table></div>
        </div>
      </div>
      <div style="font-size:11px;color:var(--dim);margin-top:10px;line-height:1.5;">
        Referencia OOS del modelo: avg_hits_top6=${fmt(sim.avg6, 3)} (${pct((sim.avg6 / PICK_COUNT) * 100, 1)} de cobertura sobre 6), avg_hits_top10=${fmt(sim.avg10, 3)} (${pct((sim.avg10 / PICK_COUNT) * 100, 1)}). Esta simulación no predice certeza; traduce los scores V4.1 a una distribución humana de hits posibles.
      </div>
    </div>`;
    target.insertAdjacentHTML('beforeend', html);
    return true;
  }

  function wrapManualEvaluator() {
    if (window.__v4ManualSimulatorWrapped) return;
    const previous = window.evalUserComboUI;
    if (typeof previous !== 'function') return;
    window.__v4ManualSimulatorWrapped = true;
    window.evalUserComboUI = async function evalUserComboUIWithSimulator() {
      const result = await previous.apply(this, arguments);
      setTimeout(renderManualSimulator, 80);
      return result;
    };
  }

  function refresh() {
    setTimeout(() => {
      renderHitAwareSummary();
      wrapManualEvaluator();
      renderManualSimulator();
    }, 150);
  }

  document.addEventListener('DOMContentLoaded', refresh);
  document.addEventListener('melate:v4-primary-loaded', refresh);
  document.addEventListener('melate:v4-results-loaded', refresh);
  document.addEventListener('melate:v3-results-loaded', refresh);
  window.renderV4HitAwareSummary = renderHitAwareSummary;
  window.renderV4ManualHitSimulator = renderManualSimulator;
})();
