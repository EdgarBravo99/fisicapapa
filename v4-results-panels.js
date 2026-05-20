// v4-results-panels.js
// Paneles finales Web V2: valida física, muestra top combinaciones, top 10 números y corrige panel físico.
(function () {
  'use strict';

  const MAX_NUMBER = 56;
  let physicsExpanded = false;
  let physicsMode = 'review';
  const $ = id => document.getElementById(id);
  const num = (v, f = 0) => Number.isFinite(Number(v)) ? Number(v) : f;
  const pct = v => { const x = num(v, 0); return x > 0 && x <= 1 ? x * 100 : x; };
  const fmt = (v, d = 2) => Number.isFinite(Number(v)) ? Number(v).toFixed(d) : '—';
  const esc = v => String(v ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));

  function validV42(data) {
    const fb = data?.feedback_loop || data?.walk_forward?.feedback_loop || data?.deep_stacking?.feedback_loop;
    return fb?.version === 'V4.2';
  }

  function seedMap(data) {
    const map = new Map();
    (Array.isArray(data?.manual_suggestion_seed) ? data.manual_suggestion_seed : []).forEach(row => {
      const n = Number(row?.number ?? row?.n ?? row?.ball);
      if (Number.isInteger(n) && n >= 1 && n <= MAX_NUMBER) map.set(n, row);
    });
    return map;
  }

  function physicalOf(row, data) {
    const physics = data?.physics_summary || {};
    const realWeight = Number(row?.real_weight ?? row?.raw_weight ?? row?.base_weight ?? row?.ball_weight ?? row?.weight ?? row?.measured_weight);
    const effectiveWeight = Number(row?.effective_weight ?? row?.effectiveWeight ?? row?.weight_effective ?? row?.sigmoid_weight ?? row?.w_eff);
    const uses = Number(row?.uses_since_calibration ?? row?.uses_in_window ?? row?.uses ?? row?.hits_in_window);
    const avgEffective = Number(physics.avg_effective_weight ?? physics.average_effective_weight ?? physics.mean_effective_weight ?? physics.avgEffectiveWeight);
    const resetAfter = row?.weight_lifecycle_reset_after_draw_id ?? row?.lifecycle_reset_after_draw_id ?? physics.weight_lifecycle_reset_after_draw_id ?? physics.lifecycle_reset_after_draw_id ?? '4213';
    const calibrationId = row?.weight_calibration_id ?? physics.weight_calibration_id ?? physics.calibration_id ?? 'V4.2';
    const calibrationDate = row?.weight_calibration_date ?? physics.weight_calibration_date ?? physics.calibration_date ?? null;
    const wearMg = Number.isFinite(realWeight) && Number.isFinite(effectiveWeight)
      ? Math.max(0, (realWeight - effectiveWeight) * 1000)
      : null;
    return {
      realWeight: Number.isFinite(realWeight) ? realWeight : null,
      effectiveWeight: Number.isFinite(effectiveWeight) ? effectiveWeight : null,
      uses: Number.isFinite(uses) ? uses : null,
      avgEffective: Number.isFinite(avgEffective) ? avgEffective : null,
      resetAfter,
      calibrationId,
      calibrationDate,
      wearMg: Number.isFinite(wearMg) ? wearMg : null,
      hasEffective: Number.isFinite(effectiveWeight),
      hasReal: Number.isFinite(realWeight),
    };
  }

  function comboNumbers(combo) {
    return (combo?.numbers || combo?.nums || combo?.combo || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  }

  function comboScore(combo) {
    return pct(combo?.score_percent ?? combo?.net_score ?? combo?.confidence ?? combo?.score ?? 0);
  }

  function compareScores(nums, combo, data) {
    if (typeof window.compareCruncherVsWebScore === 'function') {
      return window.compareCruncherVsWebScore(nums, data);
    }
    return {
      cruncherScore: comboScore(combo),
      webScore: null,
      delta: null,
      scaleDetected: 'unknown',
      interpretation: 'Score web disponible despues de cargar diagnosticos V4.2.'
    };
  }

  function badgeHtml(label, tone) {
    const cls = {
      emerald: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100',
      cyan: 'border-cyan-400/30 bg-cyan-400/10 text-cyan-100',
      violet: 'border-violet-400/30 bg-violet-400/10 text-violet-100',
      amber: 'border-amber-400/30 bg-amber-400/10 text-amber-100',
      red: 'border-red-400/40 bg-red-500/10 text-red-100',
    }[tone] || 'border-slate-700 bg-slate-900 text-slate-200';
    return `<span class="taste-chip quant-pill rounded-full border ${cls} px-2 py-1 text-[10px] font-bold uppercase tracking-[0.14em]">${esc(label)}</span>`;
  }

  function comboBadges(combo, nums, data) {
    const score = comboScore(combo);
    const parity = nums.filter(n => n % 2 === 0).length;
    const left = nums.filter(n => n <= 28).length;
    const decades = new Set(nums.map(n => Math.floor((n - 1) / 10))).size;
    const map = seedMap(data);
    const weights = nums.map(n => physicalOf(map.get(n) || { number: n }, data).effectiveWeight).filter(Number.isFinite);
    const avg = weights.length ? weights.reduce((a, b) => a + b, 0) / weights.length : null;
    const systemAvg = Number(data?.physics_summary?.avg_effective_weight);
    const badges = [];
    if (Math.abs(parity - 3) <= 1 && Math.abs(left - 3) <= 1 && decades >= 4) badges.push(['balanceada', 'emerald']);
    else badges.push(['revisar estructura', 'amber']);
    if (score >= 70) badges.push(['fuerte por modelo', 'cyan']);
    if (Number(combo?.portfolio_rank ?? combo?.rank ?? 1) <= 10) badges.push(['fuerte por pool', 'violet']);
    if (avg != null && Number.isFinite(systemAvg)) {
      const delta = avg - systemAvg;
      if (Math.abs(delta) <= 0.025) badges.push(['fuerte por fisica', 'emerald']);
      if (Math.abs(delta) >= 0.06) badges.push(['extrema en peso', 'red']);
    }
    return badges.map(([label, tone]) => badgeHtml(label, tone)).join('');
  }

  function renderTopCombinations(data) {
    const panel = $('top-combinations-panel');
    if (!panel) return;
    const pool = Array.isArray(data?.top_combinations) && data.top_combinations.length
      ? data.top_combinations
      : Array.isArray(data?.generator_pool) ? data.generator_pool.slice(0, 10) : [];

    const label = $('top-combos-label');
    if (label) label.textContent = `${pool.length} combos top`;

    if (!pool.length) {
      panel.innerHTML = '<div class="rounded-2xl border border-red-500/40 bg-red-500/10 p-4 text-sm text-red-100">No hay top_combinations ni generator_pool en resultados.json.</div>';
      return;
    }

    panel.innerHTML = pool.slice(0, 10).map((combo, idx) => {
      const nums = comboNumbers(combo);
      const score = comboScore(combo);
      const scoreCompare = compareScores(nums, combo, data);
      const webScore = Number.isFinite(Number(scoreCompare.webScore)) ? fmt(scoreCompare.webScore) : 'N/D';
      const cruncherScore = Number.isFinite(Number(scoreCompare.cruncherScore)) ? fmt(scoreCompare.cruncherScore) : fmt(score);
      const delta = Number.isFinite(Number(scoreCompare.delta)) ? fmt(scoreCompare.delta) : 'N/D';
      const explanation = combo?.plain_route || combo?.human_explanation || combo?.source || 'Sin ruta explicativa exportada.';
      const comparatorReady = Boolean(window.FISICAPAPA_COMPARATOR?.saveCombo);
      const saveAttrs = comparatorReady
        ? `data-save-combo="${nums.join(',')}" data-save-label="Top #${idx + 1}"`
        : 'disabled aria-disabled="true" title="Comparador cargando"';
      return `<article class="combo-ticket taste-motion-in" style="animation-delay:${idx * 55}ms">
        <div class="combo-ticket-rank" aria-label="Ranking ${idx + 1}">#${idx + 1}</div>
        <div class="combo-ticket-body">
          <div class="combo-ticket-main">
            <p class="text-xs uppercase tracking-[0.22em] text-amber-300">#${idx + 1} · score ${fmt(score)}</p>
            <div class="combo-ball-row mt-3">${nums.map(n => `<span class="taste-ball quant-number-ball rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-sm font-black text-cyan-100">${n}</span>`).join('')}</div>
            <div class="mt-3 flex flex-wrap gap-2">${comboBadges(combo, nums, data)}</div>
            <div class="metric-strip mt-3">
              <div class="quant-metric"><p>Score web</p><b>${webScore}</b></div>
              <div class="quant-metric"><p>Cruncher</p><b>${cruncherScore}</b></div>
              <div class="quant-metric"><p>Delta</p><b>${delta}</b></div>
            </div>
          </div>
          <div class="combo-ticket-actions">
            <button class="taste-ghost quant-ghost-button" data-fill-combo="${nums.join(',')}">Evaluar</button>
            <button class="taste-ghost quant-ghost-button" ${saveAttrs}>Guardar</button>
            <button class="taste-ghost quant-ghost-button" data-copy-combo="${nums.join(' ')}">Copiar</button>
          </div>
        </div>
        <p class="combo-ticket-score mt-3 text-xs leading-5 text-slate-400">${esc(explanation).slice(0, 420)}</p>
      </article>`;
    }).join('');

    panel.querySelectorAll('[data-fill-combo]').forEach(btn => {
      btn.addEventListener('click', () => {
        const nums = btn.getAttribute('data-fill-combo').split(',').map(Number);
        nums.forEach((n, idx) => {
          const input = document.getElementById(`manual-n${idx + 1}`);
          if (input) input.value = n;
        });
        document.getElementById('btn-evaluate-manual')?.click();
        document.getElementById('manual-result')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });

    panel.querySelectorAll('[data-copy-combo]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const value = btn.getAttribute('data-copy-combo');
        try { await navigator.clipboard.writeText(value); } catch (_) {
          const area = document.createElement('textarea');
          area.value = value;
          document.body.appendChild(area);
          area.select();
          document.execCommand('copy');
          area.remove();
        }
        btn.textContent = 'Copiada';
      });
    });

    panel.querySelectorAll('[data-save-combo]').forEach(btn => {
      btn.addEventListener('click', () => {
        const nums = btn.getAttribute('data-save-combo').split(',').map(Number);
        const label = btn.getAttribute('data-save-label') || 'Top combination';
        if (window.FISICAPAPA_COMPARATOR?.saveCombo) {
          window.FISICAPAPA_COMPARATOR.saveCombo(nums, label);
          btn.textContent = 'Guardada';
          return;
        }
        btn.textContent = 'Comparador no listo';
        btn.setAttribute('disabled', 'disabled');
      });
    });
  }

  function renderTopNumbers(data) {
    const panel = $('top-numbers-panel');
    if (!panel) return;
    const map = seedMap(data);
    const rows = [];
    for (let n = 1; n <= MAX_NUMBER; n += 1) {
      const row = map.get(n) || {};
      const score = pct(row.score ?? row.meta_score ?? row.score_percent ?? row.net_score ?? data?.number_scores?.[String(n)] ?? 0);
      const phys = physicalOf(row, data);
      rows.push({ number: n, row, score, phys });
    }
    rows.sort((a, b) => b.score - a.score);

    panel.innerHTML = rows.slice(0, 10).map((item, idx) => {
      const driver = item.row.winner_component_human || item.row.main_driver_human || item.row.driver_human || item.row.main_driver || item.row.winner_component || 'modelo V4.2';
      const reason = item.row.reason || item.row.explanation || 'Ranking por score del modelo V4.2.';
      const real = item.phys.realWeight == null ? 'N/D' : `${fmt(item.phys.realWeight, 4)}g`;
      const eff = item.phys.effectiveWeight == null ? 'N/D' : `${fmt(item.phys.effectiveWeight, 4)}g`;
      const uses = item.phys.uses == null ? 'N/D' : item.phys.uses;
      const wear = item.phys.wearMg == null ? 'N/D' : `${fmt(item.phys.wearMg, 2)} mg`;
      const raw = item.row?.expert_raw || item.row?.expert_scores || item.row?.experts || {};
      const transformer = pct(raw.transformer);
      const xgboost = pct(raw.xgboost);
      const graph = pct(raw.graph);
      const physicsBadge = !item.phys.hasEffective ? badgeHtml('sin datos fisicos', 'red') : item.phys.effectiveWeight < item.phys.avgEffective ? badgeHtml('fisica ligera', 'emerald') : badgeHtml('fisica pesada', 'amber');
      return `<article class="number-rank-card taste-motion-in rounded-2xl border border-violet-400/20 bg-slate-900/70 p-4" style="animation-delay:${idx * 45}ms">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3"><span class="taste-ball quant-number-ball flex h-10 w-10 items-center justify-center rounded-full border border-violet-300/40 bg-violet-400/10 text-lg font-black text-violet-100">${item.number}</span><div><p class="text-xs text-slate-500">Rank #${idx + 1}</p><p class="text-sm font-black text-white">${fmt(item.score)} pts</p></div></div>
          <span class="driver-chip text-xs font-bold text-cyan-200">${esc(driver)}</span>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc(reason).slice(0, 180)}</p>
        <div class="mt-3 flex flex-wrap gap-2">${physicsBadge}</div>
        <div class="metric-strip mt-3">
          <div class="quant-metric"><p>Transformer</p><b>${fmt(transformer)}</b></div>
          <div class="quant-metric"><p>XGBoost</p><b>${fmt(xgboost)}</b></div>
          <div class="quant-metric"><p>Graph</p><b>${fmt(graph)}</b></div>
        </div>
        <p class="mt-2 text-xs text-slate-300">Peso real: <b>${real}</b> · efectivo: <b>${eff}</b> · salidas desde calibración: <b>${uses}</b> · desgaste: <b>${wear}</b></p>
      </article>`;
    }).join('');
  }

  function physicsAlerts(phys, maxUses) {
    const alerts = [];
    if (!phys.hasEffective || !phys.hasReal) alerts.push(['esfera sin datos', 'red']);
    if (phys.avgEffective != null && phys.effectiveWeight != null && phys.effectiveWeight - phys.avgEffective >= 0.055) alerts.push(['extremadamente pesada', 'amber']);
    if (phys.avgEffective != null && phys.effectiveWeight != null && phys.avgEffective - phys.effectiveWeight >= 0.055) alerts.push(['extremadamente ligera', 'cyan']);
    if (phys.uses != null && phys.uses >= Math.max(3, Math.ceil(maxUses * 0.8))) alerts.push(['muy usada', 'violet']);
    return alerts;
  }

  function renderPhysicsGrid(data) {
    const grid = $('physics-grid');
    if (!grid) return;
    const map = seedMap(data);
    const rows = [];
    for (let n = 1; n <= MAX_NUMBER; n += 1) {
      const row = map.get(n) || { number: n };
      rows.push({ number: n, row, phys: physicalOf(row, data) });
    }
    const maxUses = Math.max(1, ...rows.map(r => r.phys.uses ?? 0));
    const maxWear = Math.max(0.0001, ...rows.map(r => r.phys.wearMg ?? 0));
    const resetAfter = rows.find(r => r.phys.resetAfter)?.phys.resetAfter ?? '4213';
    const calibrationDate = rows.find(r => r.phys.calibrationDate)?.phys.calibrationDate ?? '2026-05-17';
    const rowsWithAlerts = rows.map(row => ({ ...row, alerts: physicsAlerts(row.phys, maxUses) }));
    const reviewRows = rowsWithAlerts
      .filter(row => row.alerts.length)
      .concat(rowsWithAlerts.slice().sort((a, b) => (b.phys.uses ?? 0) - (a.phys.uses ?? 0)).slice(0, 10))
      .filter((row, index, list) => list.findIndex(item => item.number === row.number) === index);
    const selectedRows = physicsExpanded
      ? rowsWithAlerts
      : physicsMode === 'alerts'
        ? rowsWithAlerts.filter(row => row.alerts.length).slice(0, 24)
        : reviewRows.slice(0, 18);
    const controls = `<div class="taste-panel-muted physics-lab-control">
      <div>
        <p class="taste-eyebrow">Vista fisica</p>
        <p>${selectedRows.length}/56 esferas visibles. Usa filtros para no saturar movil.</p>
      </div>
      <div class="taste-action-row">
        <button class="taste-ghost" data-physics-mode="review">Revisar primero</button>
        <button class="taste-ghost" data-physics-mode="alerts">Solo alertas</button>
        <button class="taste-ghost" data-physics-expanded="${physicsExpanded ? '0' : '1'}">${physicsExpanded ? 'Compactar' : 'Mostrar 56'}</button>
      </div>
    </div>`;

    grid.innerHTML = controls + selectedRows.map(({ number, phys, alerts }, idx) => {
      const real = phys.realWeight == null ? 'N/D' : `${fmt(phys.realWeight, 4)}g`;
      const eff = phys.effectiveWeight == null ? 'N/D' : `${fmt(phys.effectiveWeight, 4)}g`;
      const uses = phys.uses == null ? 'N/D' : phys.uses;
      const wear = phys.wearMg == null ? 'N/D' : `${fmt(phys.wearMg, 2)} mg`;
      const useWidth = phys.uses == null ? 0 : Math.min(100, (phys.uses / maxUses) * 100);
      const wearWidth = phys.wearMg == null ? 0 : Math.min(100, (phys.wearMg / maxWear) * 100);
      const tone = !phys.hasEffective ? 'border-red-500/30' : phys.effectiveWeight < phys.avgEffective ? 'border-emerald-400/30' : 'border-amber-400/30';
      const badge = phys.uses == null ? 'sin usos' : `${phys.uses} salidas`;
      return `<article class="physics-lab-card taste-motion-in rounded-2xl border ${tone} bg-slate-900/60 p-4" style="animation-delay:${idx * 24}ms">
        <div class="flex items-center justify-between gap-3">
          <span class="taste-ball quant-number-ball">${number}</span>
          <span class="taste-chip quant-pill rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-1 text-xs font-bold text-cyan-100">${esc(badge)}</span>
        </div>
        <div class="mt-3 flex flex-wrap gap-2">${alerts.map(([label, alertTone]) => badgeHtml(label, alertTone)).join('') || badgeHtml('fisica nominal', 'emerald')}</div>
        <div class="mt-3 space-y-2">
          <div class="component-meter"><div class="flex justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500"><span>Salidas reales</span><span>${uses}</span></div><div class="quant-progress mt-1"><div style="width:${useWidth}%"></div></div></div>
          <div class="component-meter"><div class="flex justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500"><span>Desgaste estimado</span><span>${wear}</span></div><div class="quant-progress mt-1"><div style="width:${wearWidth}%"></div></div></div>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-300">Bola ${number}: peso real <b>${real}</b>; desde el reset post-sorteo <b>${esc(resetAfter)}</b> ha salido <b>${uses}</b> veces y su peso efectivo actual es <b>${eff}</b>.</p>
      </article>`;
    }).join('');

    grid.querySelectorAll('[data-physics-mode]').forEach(button => {
      button.addEventListener('click', () => {
        physicsMode = button.getAttribute('data-physics-mode');
        physicsExpanded = false;
        renderPhysicsGrid(data);
      });
    });
    grid.querySelector('[data-physics-expanded]')?.addEventListener('click', event => {
      physicsExpanded = event.currentTarget.getAttribute('data-physics-expanded') === '1';
      renderPhysicsGrid(data);
    });

    const label = $('physics-summary-label');
    if (label) {
      const avg = data?.physics_summary?.avg_effective_weight;
      label.textContent = `Reset vida útil > ${resetAfter} · calibración ${calibrationDate} · prom ${fmt(avg, 4)}g`;
    }
  }

  function validatePhysicsPresence(data) {
    const rows = Array.from(seedMap(data).values());
    const effectiveCount = rows.filter(row => physicalOf(row, data).hasEffective).length;
    const realCount = rows.filter(row => physicalOf(row, data).hasReal).length;
    const usesCount = rows.filter(row => physicalOf(row, data).uses !== null).length;
    const label = $('physics-summary-label');
    if (label) {
      const avg = data?.physics_summary?.avg_effective_weight;
      label.textContent = `Física: ${effectiveCount}/56 efectivos · ${realCount}/56 reales · ${usesCount}/56 usos · prom ${fmt(avg, 4)}g`;
    }
    if (effectiveCount < 56) console.warn(`[V4.2] Faltan effective_weight en ${56 - effectiveCount} números.`);
    if (realCount < 56) console.warn(`[V4.2] Faltan real_weight/base_weight en ${56 - realCount} números. El cruncher debe exportarlo.`);
    if (usesCount < 56) console.warn(`[V4.2] Faltan uses_since_calibration/uses_in_window en ${56 - usesCount} números.`);
  }

  async function loadResults() {
    if (window.FISICAPAPA_WEB_V2?.jsonData) return window.FISICAPAPA_WEB_V2.jsonData;
    const r = await fetch(`resultados.json?v42panels=${Date.now()}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return r.json();
  }

  async function render() {
    try {
      const data = await loadResults();
      if (!validV42(data)) return;
      validatePhysicsPresence(data);
      renderPhysicsGrid(data);
      renderTopCombinations(data);
      renderTopNumbers(data);
    } catch (err) {
      console.warn('[V4.2 panels] No se pudieron renderizar paneles:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(render, 350));
  window.addEventListener('focus', () => setTimeout(render, 150));
  window.renderV42ResultPanels = render;
})();
