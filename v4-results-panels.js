// v4-results-panels.js
// Paneles finales Web V2: valida física, muestra top combinaciones y top 10 números.
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
    const uses = Number(row?.uses_in_window ?? row?.uses ?? row?.hits_in_window);
    const avgEffective = Number(physics.avg_effective_weight ?? physics.average_effective_weight ?? physics.mean_effective_weight ?? physics.avgEffectiveWeight);
    return {
      realWeight: Number.isFinite(realWeight) ? realWeight : null,
      effectiveWeight: Number.isFinite(effectiveWeight) ? effectiveWeight : null,
      uses: Number.isFinite(uses) ? uses : null,
      avgEffective: Number.isFinite(avgEffective) ? avgEffective : null,
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
      return `<article class="rounded-2xl border border-violet-400/20 bg-slate-900/70 p-4">
        <div class="flex items-center justify-between gap-3">
          <div class="flex items-center gap-3"><span class="flex h-10 w-10 items-center justify-center rounded-full border border-violet-300/40 bg-violet-400/10 text-lg font-black text-violet-100">${item.number}</span><div><p class="text-xs text-slate-500">Rank #${idx + 1}</p><p class="text-sm font-black text-white">${fmt(item.score)} pts</p></div></div>
          <span class="text-xs font-bold text-cyan-200">${esc(driver)}</span>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc(reason).slice(0, 180)}</p>
        <p class="mt-2 text-xs text-slate-300">Peso real: <b>${real}</b> · efectivo: <b>${eff}</b> · usos: <b>${uses}</b></p>
      </article>`;
    }).join('');
  }

  function validatePhysicsPresence(data) {
    const rows = Array.from(seedMap(data).values());
    const effectiveCount = rows.filter(row => physicalOf(row, data).hasEffective).length;
    const realCount = rows.filter(row => physicalOf(row, data).hasReal).length;
    const label = $('physics-summary-label');
    if (label) {
      const avg = data?.physics_summary?.avg_effective_weight;
      label.textContent = `Física: ${effectiveCount}/56 efectivos · ${realCount}/56 reales · prom ${fmt(avg, 4)}g`;
    }
    if (effectiveCount < 56) console.warn(`[V4.2] Faltan effective_weight en ${56 - effectiveCount} números.`);
    if (realCount < 56) console.warn(`[V4.2] Faltan real_weight/base_weight en ${56 - realCount} números. El cruncher debe exportarlo.`);
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
      renderTopCombinations(data);
      renderTopNumbers(data);
    } catch (err) {
      console.warn('[V4.2 panels] No se pudieron renderizar paneles:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(render, 250));
  window.addEventListener('focus', () => setTimeout(render, 150));
  window.renderV42ResultPanels = render;
})();
