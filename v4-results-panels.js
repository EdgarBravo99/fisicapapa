// v4-results-panels.js
// Paneles finales Web V2: valida física, muestra top combinaciones, top 10 números y corrige panel físico.
(function () {
  'use strict';

  const MAX_NUMBER = 56;
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
      const explanation = combo?.plain_route || combo?.human_explanation || combo?.source || 'Sin ruta explicativa exportada.';
      return `<article class="rounded-2xl border border-amber-400/20 bg-slate-900/70 p-4">
        <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.22em] text-amber-300">#${idx + 1} · score ${fmt(score)}</p>
            <div class="mt-2 flex flex-wrap gap-2">${nums.map(n => `<span class="rounded-full border border-cyan-400/30 bg-cyan-400/10 px-3 py-1 text-sm font-black text-cyan-100">${n}</span>`).join('')}</div>
          </div>
          <button class="rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-bold text-cyan-100" data-fill-combo="${nums.join(',')}">Evaluar</button>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc(explanation).slice(0, 420)}</p>
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
      return `<article class="rounded-2xl border border-violet-400/20 bg-slate-900/70 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3"><span class="flex h-10 w-10 items-center justify-center rounded-full border border-violet-300/40 bg-violet-400/10 text-lg font-black text-violet-100">${item.number}</span><div><p class="text-xs text-slate-500">Rank #${idx + 1}</p><p class="text-sm font-black text-white">${fmt(item.score)} pts</p></div></div>
          <span class="text-xs font-bold text-cyan-200">${esc(driver)}</span>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc(reason).slice(0, 180)}</p>
        <p class="mt-2 text-xs text-slate-300">Peso real: <b>${real}</b> · efectivo: <b>${eff}</b> · salidas desde calibración: <b>${uses}</b> · desgaste: <b>${wear}</b></p>
      </article>`;
    }).join('');
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

    grid.innerHTML = rows.map(({ number, phys }) => {
      const real = phys.realWeight == null ? 'N/D' : `${fmt(phys.realWeight, 4)}g`;
      const eff = phys.effectiveWeight == null ? 'N/D' : `${fmt(phys.effectiveWeight, 4)}g`;
      const uses = phys.uses == null ? 'N/D' : phys.uses;
      const wear = phys.wearMg == null ? 'N/D' : `${fmt(phys.wearMg, 2)} mg`;
      const useWidth = phys.uses == null ? 0 : Math.min(100, (phys.uses / maxUses) * 100);
      const wearWidth = phys.wearMg == null ? 0 : Math.min(100, (phys.wearMg / maxWear) * 100);
      const tone = !phys.hasEffective ? 'border-red-500/30' : phys.effectiveWeight < phys.avgEffective ? 'border-emerald-400/30' : 'border-amber-400/30';
      const badge = phys.uses == null ? 'sin usos' : `${phys.uses} salidas`;
      return `<article class="rounded-2xl border ${tone} bg-slate-900/60 p-4">
        <div class="flex items-center justify-between gap-3">
          <span class="text-2xl font-black text-white">${number}</span>
          <span class="rounded-full border border-cyan-400/20 bg-cyan-400/10 px-2 py-1 text-xs font-bold text-cyan-100">${esc(badge)}</span>
        </div>
        <div class="mt-3 space-y-2">
          <div><div class="flex justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500"><span>Salidas reales</span><span>${uses}</span></div><div class="mt-1 h-2 overflow-hidden rounded-full bg-slate-800"><div class="h-full rounded-full bg-cyan-400" style="width:${useWidth}%"></div></div></div>
          <div><div class="flex justify-between text-[10px] uppercase tracking-[0.18em] text-slate-500"><span>Desgaste estimado</span><span>${wear}</span></div><div class="mt-1 h-2 overflow-hidden rounded-full bg-slate-800"><div class="h-full rounded-full bg-emerald-400" style="width:${wearWidth}%"></div></div></div>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-300">Bola ${number}: peso real <b>${real}</b>; desde el reset post-sorteo <b>${esc(resetAfter)}</b> ha salido <b>${uses}</b> veces y su peso efectivo actual es <b>${eff}</b>.</p>
      </article>`;
    }).join('');

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
