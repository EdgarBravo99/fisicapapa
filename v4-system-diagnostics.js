// v4-system-diagnostics.js
// Web V2 add-on: data-quality diagnostics and manual-evaluation explainability.
(function () {
  'use strict';

  const MAX_NUMBER = 56;
  const PICK_COUNT = 6;
  const REQUIRED_FEEDBACK_VERSION = 'V4.2';

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  const num = value => Number.isFinite(Number(value)) ? Number(value) : null;
  const fmt = (value, digits = 2) => {
    const n = num(value);
    return n == null ? '-' : n.toFixed(digits);
  };
  const pct = value => {
    const n = num(value);
    if (n == null) return 0;
    return n > 0 && n <= 1 ? n * 100 : n;
  };
  const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, Number.isFinite(Number(value)) ? Number(value) : 0));

  function feedbackLoop(data) {
    return data?.feedback_loop || data?.walk_forward?.feedback_loop || data?.deep_stacking?.feedback_loop || null;
  }

  function seedRows(data) {
    return Array.isArray(data?.manual_suggestion_seed) ? data.manual_suggestion_seed : [];
  }

  function seedMap(data) {
    const map = new Map();
    seedRows(data).forEach(row => {
      const n = Number(row?.number ?? row?.n ?? row?.ball);
      if (Number.isInteger(n) && n >= 1 && n <= MAX_NUMBER) map.set(n, row);
    });
    return map;
  }

  function realWeight(row) {
    return num(row?.real_weight ?? row?.raw_weight ?? row?.base_weight ?? row?.ball_weight ?? row?.weight ?? row?.measured_weight);
  }

  function effectiveWeight(row) {
    return num(row?.effective_weight ?? row?.effectiveWeight ?? row?.weight_effective ?? row?.sigmoid_weight ?? row?.w_eff);
  }

  function usesSinceCalibration(row) {
    return num(row?.uses_since_calibration ?? row?.uses_in_window ?? row?.uses ?? row?.hits_in_window);
  }

  function validateV42DataQuality(jsonData) {
    const errors = [];
    const warnings = [];
    const fb = feedbackLoop(jsonData);
    const map = seedMap(jsonData);
    const rows = Array.from(map.values());
    const physics = jsonData?.physics_summary || {};
    const counts = {
      manualSeed: map.size,
      realWeights: rows.filter(row => realWeight(row) != null).length,
      effectiveWeights: rows.filter(row => effectiveWeight(row) != null).length,
      usesSinceCalibration: rows.filter(row => usesSinceCalibration(row) != null).length,
      generatorPool: Array.isArray(jsonData?.generator_pool) ? jsonData.generator_pool.length : 0,
      topCombinations: Array.isArray(jsonData?.top_combinations) ? jsonData.top_combinations.length : 0,
      walkForwardRows: Array.isArray(jsonData?.walk_forward?.rows) ? jsonData.walk_forward.rows.length : 0,
    };

    if (!jsonData || typeof jsonData !== 'object') errors.push('resultados.json no es un objeto JSON.');
    if (fb?.version !== REQUIRED_FEEDBACK_VERSION) errors.push('feedback_loop.version no es V4.2.');
    if (!String(jsonData?.model_version || '').includes('V4.2')) warnings.push('model_version no declara V4.2 de forma explicita.');
    if (counts.manualSeed !== MAX_NUMBER) errors.push(`manual_suggestion_seed tiene ${counts.manualSeed}/56 entradas unicas.`);
    if (counts.realWeights !== MAX_NUMBER) errors.push(`Pesos reales incompletos: ${counts.realWeights}/56.`);
    if (counts.effectiveWeights !== MAX_NUMBER) errors.push(`Pesos efectivos incompletos: ${counts.effectiveWeights}/56.`);
    if (counts.usesSinceCalibration !== MAX_NUMBER) errors.push(`Usos desde calibracion incompletos: ${counts.usesSinceCalibration}/56.`);
    if (counts.generatorPool <= 0) errors.push('generator_pool no tiene combinaciones.');
    if (counts.topCombinations <= 0) warnings.push('top_combinations esta vacio; se usara generator_pool como respaldo.');
    if (counts.walkForwardRows <= 0) warnings.push('walk_forward.rows no tiene folds para auditoria humana.');
    if (num(physics.avg_effective_weight ?? physics.average_effective_weight ?? physics.mean_effective_weight) == null) errors.push('physics_summary.avg_effective_weight no existe.');
    if (!physics.weight_calibration_id && !rows.some(row => row.weight_calibration_id)) warnings.push('No hay weight_calibration_id global; se infiere desde filas por numero.');
    if (!physics.weight_lifecycle_reset_after_draw_id && !rows.some(row => row.weight_lifecycle_reset_after_draw_id)) warnings.push('No hay reset global de vida util; se espera reset despues del sorteo 4213.');

    return { ok: errors.length === 0, errors, warnings, counts };
  }

  function metricCard(label, value, ok, detail) {
    const tone = ok ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100' : 'border-red-400/40 bg-red-500/10 text-red-100';
    return `<article class="rounded-2xl border ${tone} p-4">
      <p class="text-[10px] uppercase tracking-[0.18em] opacity-75">${esc(label)}</p>
      <p class="mt-2 text-xl font-black">${esc(value)}</p>
      ${detail ? `<p class="mt-1 text-xs leading-5 opacity-80">${esc(detail)}</p>` : ''}
    </article>`;
  }

  function renderDiagnostics(jsonData) {
    const panel = $('system-diagnostics-panel');
    if (!panel || !jsonData) return;

    const quality = validateV42DataQuality(jsonData);
    const status = $('system-diagnostics-status');
    const fb = feedbackLoop(jsonData);
    const physics = jsonData.physics_summary || {};
    const rows = seedRows(jsonData);
    const calibrationDate = physics.weight_calibration_date || rows.find(row => row.weight_calibration_date)?.weight_calibration_date || '2026-05-17';
    const calibrationDraw = physics.weight_calibration_draw_id || rows.find(row => row.weight_calibration_context_draw_id)?.weight_calibration_context_draw_id || '4214';
    const resetAfter = physics.weight_lifecycle_reset_after_draw_id || rows.find(row => row.weight_lifecycle_reset_after_draw_id)?.weight_lifecycle_reset_after_draw_id || '4213';

    if (status) {
      status.textContent = quality.ok ? 'OK V4.2' : `${quality.errors.length} errores`;
      status.className = `rounded-2xl border px-4 py-2 text-sm font-bold ${quality.ok ? 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100' : 'border-red-400/40 bg-red-500/10 text-red-100'}`;
    }

    const messages = [...quality.errors.map(text => ({ tone: 'red', text })), ...quality.warnings.map(text => ({ tone: 'amber', text }))];
    panel.innerHTML = `
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        ${metricCard('Modelo', jsonData.model_version || jsonData.source || '-', Boolean(jsonData.model_version), jsonData.last_update || 'sin timestamp')}
        ${metricCard('Modo', jsonData.game_mode || jsonData.game_label || '-', Boolean(jsonData.game_mode || jsonData.game_label), `feedback ${fb?.version || '-'}`)}
        ${metricCard('Pool', `${quality.counts.generatorPool} combos`, quality.counts.generatorPool > 0, `${quality.counts.topCombinations} top_combinations`)}
        ${metricCard('Walk-forward', `${quality.counts.walkForwardRows} folds`, quality.counts.walkForwardRows > 0, 'rows disponibles para auditoria')}
        ${metricCard('manual_suggestion_seed', `${quality.counts.manualSeed}/56`, quality.counts.manualSeed === 56)}
        ${metricCard('Pesos reales', `${quality.counts.realWeights}/56`, quality.counts.realWeights === 56)}
        ${metricCard('Pesos efectivos', `${quality.counts.effectiveWeights}/56`, quality.counts.effectiveWeights === 56)}
        ${metricCard('Usos calibracion', `${quality.counts.usesSinceCalibration}/56`, quality.counts.usesSinceCalibration === 56)}
      </div>
      <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300">
        <p class="font-black text-white">Calibracion fisica</p>
        <p class="mt-2 leading-6">Fecha ${esc(calibrationDate)} / sorteo ${esc(calibrationDraw)}. Reset de vida util despues del sorteo ${esc(resetAfter)}. Promedio efectivo: ${fmt(physics.avg_effective_weight, 4)}g.</p>
      </div>
      ${messages.length ? `<div class="grid gap-2">${messages.map(item => `<p class="rounded-xl border ${item.tone === 'red' ? 'border-red-400/40 bg-red-500/10 text-red-100' : 'border-amber-400/40 bg-amber-500/10 text-amber-100'} px-3 py-2 text-sm">${esc(item.text)}</p>`).join('')}</div>` : '<p class="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-100">Contrato y conteos principales completos.</p>'}
    `;

    window.FISICAPAPA_LAST_DATA_QUALITY = quality;
  }

  function readManualNumbers() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => Number($(`manual-n${i}`)?.value));
    if (nums.length !== PICK_COUNT || nums.some(n => !Number.isInteger(n) || n < 1 || n > MAX_NUMBER) || new Set(nums).size !== PICK_COUNT) return null;
    return nums.slice().sort((a, b) => a - b);
  }

  function componentDelta(before, after, key) {
    return (after?.summary?.[key] ?? 0) - (before?.summary?.[key] ?? 0);
  }

  function under40Delta(beforeNums, afterNums) {
    return afterNums.filter(n => n < 40).length - beforeNums.filter(n => n < 40).length;
  }

  function weakestNumber(result) {
    const gravityRows = result?.components?.gravityPhysics?.physicalRows || [];
    const rows = (result?.components?.modelScore?.rows || []).map(row => {
      const phys = gravityRows.find(item => item.number === row.number) || {};
      const localScore = clamp((row.expertAverage || row.modelScore || 0) * 0.68 + (phys.effectiveWeight ? result.components.gravityPhysics.score * 0.16 : 0) + result.components.structuralBalance.score * 0.16);
      return { number: row.number, localScore, modelScore: row.modelScore ?? row.expertAverage ?? 0 };
    });
    return rows.sort((a, b) => a.localScore - b.localScore)[0] || null;
  }

  function replacementReasons(currentResult, evaluated, beforeNums, afterNums) {
    const reasons = [];
    const model = componentDelta(currentResult, evaluated, 'modelScore');
    const physics = componentDelta(currentResult, evaluated, 'gravityPhysics');
    const structure = componentDelta(currentResult, evaluated, 'structuralBalance');
    const pool = componentDelta(currentResult, evaluated, 'poolAlignment');
    const under = under40Delta(beforeNums, afterNums);
    if (model > 0.1) reasons.push(`modelo +${fmt(model)}`);
    if (physics > 0.1) reasons.push(`fisica +${fmt(physics)}`);
    if (structure > 0.1) reasons.push(`estructura +${fmt(structure)}`);
    if (pool > 0.1) reasons.push(`pool +${fmt(pool)}`);
    if (under !== 0) reasons.push(`<40 ${under > 0 ? '+' : ''}${under}`);
    return reasons.length ? reasons : ['mejora ranking compuesto sin cambiar formula oficial'];
  }

  function topReplacementSuggestions(numbers, jsonData, currentResult) {
    const weak = weakestNumber(currentResult);
    if (!weak || !window.evaluateManualComboV4) return [];
    const current = new Set(numbers);
    const rows = [];
    for (let candidate = 1; candidate <= MAX_NUMBER; candidate += 1) {
      if (current.has(candidate)) continue;
      const next = numbers.map(n => n === weak.number ? candidate : n).sort((a, b) => a - b);
      let evaluated;
      try {
        evaluated = window.evaluateManualComboV4(next, jsonData);
      } catch (_) {
        continue;
      }
      const gain = evaluated.netScoreV4 - currentResult.netScoreV4;
      const componentLift = Math.max(0, componentDelta(currentResult, evaluated, 'modelScore')) * 0.40
        + Math.max(0, componentDelta(currentResult, evaluated, 'structuralBalance')) * 0.24
        + Math.max(0, componentDelta(currentResult, evaluated, 'poolAlignment')) * 0.20
        + Math.max(0, componentDelta(currentResult, evaluated, 'gravityPhysics')) * 0.16;
      rows.push({
        remove: weak.number,
        add: candidate,
        next,
        gain,
        ranking: gain + componentLift,
        evaluated,
        reasons: replacementReasons(currentResult, evaluated, numbers, next),
      });
    }
    return rows.sort((a, b) => b.ranking - a.ranking).slice(0, 3);
  }

  function renderManualEnhancements() {
    const data = window.FISICAPAPA_WEB_V2?.jsonData;
    const resultBox = $('manual-result');
    if (!data || !resultBox || resultBox.classList.contains('hidden')) return;
    const previous = $('manual-enhancements-card');
    if (previous) previous.remove();

    const numbers = readManualNumbers();
    if (!numbers) return;

    let result;
    try {
      result = window.evaluateManualComboV4(numbers, data);
    } catch (_) {
      return;
    }

    const weak = weakestNumber(result);
    const suggestions = topReplacementSuggestions(numbers, data, result);
    const report = {
      numbers,
      netScoreV4: Number(result.netScoreV4.toFixed(4)),
      components: result.summary,
      weakestNumber: weak?.number ?? null,
      replacements: suggestions.map(item => ({ remove: item.remove, add: item.add, next: item.next, gain: Number(item.gain.toFixed(4)), reasons: item.reasons })),
      note: 'Auditoria visual Web V2; no representa probabilidad real garantizada.',
    };

    const rows = suggestions.map((item, idx) => `<article class="rounded-xl border border-violet-400/20 bg-violet-400/10 p-3">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p class="font-black text-violet-100">#${idx + 1}: ${item.remove} -&gt; ${item.add}</p>
        <p class="text-xs font-bold text-emerald-200">neto ${item.gain >= 0 ? '+' : ''}${fmt(item.gain)}</p>
      </div>
      <p class="mt-2 text-xs leading-5 text-slate-300">${esc(item.next.join(' | '))}</p>
      <p class="mt-2 text-xs leading-5 text-slate-400">${item.reasons.map(esc).join(' | ')}</p>
    </article>`).join('');

    resultBox.insertAdjacentHTML('beforeend', `<section id="manual-enhancements-card" class="rounded-2xl border border-cyan-400/30 bg-slate-900/70 p-4 text-sm text-slate-300">
      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.22em] text-cyan-300">Explicabilidad manual ampliada</p>
          <h3 class="mt-2 text-lg font-black text-white">Score neto ${fmt(result.netScoreV4)} | numero mas debil ${weak?.number ?? '-'}</h3>
          <p class="mt-2 leading-6">Modelo ${fmt(result.summary.modelScore)}, estructura ${fmt(result.summary.structuralBalance)}, fisica ${fmt(result.summary.gravityPhysics)}, pool ${fmt(result.summary.poolAlignment)}. La formula oficial no cambia.</p>
        </div>
        <button id="btn-copy-manual-report" class="min-h-[44px] rounded-xl border border-cyan-400/30 bg-cyan-400/10 px-3 py-2 text-xs font-bold text-cyan-100 transition hover:bg-cyan-400/20 focus:outline-none focus:ring-2 focus:ring-cyan-300">Copiar reporte</button>
      </div>
      <div class="mt-4 grid gap-3">${rows || '<p class="text-slate-400">No se encontraron reemplazos superiores.</p>'}</div>
    </section>`);

    $('btn-copy-manual-report')?.addEventListener('click', async event => {
      const text = JSON.stringify(report, null, 2);
      try {
        await navigator.clipboard.writeText(text);
        event.currentTarget.textContent = 'Reporte copiado';
      } catch (_) {
        const area = document.createElement('textarea');
        area.value = text;
        document.body.appendChild(area);
        area.select();
        document.execCommand('copy');
        area.remove();
        event.currentTarget.textContent = 'Reporte copiado';
      }
    });
  }

  function renderAll() {
    const data = window.FISICAPAPA_WEB_V2?.jsonData;
    if (data) renderDiagnostics(data);
  }

  function bind() {
    $('btn-evaluate-manual')?.addEventListener('click', () => setTimeout(renderManualEnhancements, 120));
    [1, 2, 3, 4, 5, 6].forEach(i => {
      $(`manual-n${i}`)?.addEventListener('keydown', event => {
        if (event.key === 'Enter') setTimeout(renderManualEnhancements, 150);
      });
    });
    $('btn-reload-json')?.addEventListener('click', () => setTimeout(renderAll, 500));
    const dashboard = $('dashboard');
    if (dashboard) {
      const observer = new MutationObserver(() => setTimeout(renderAll, 80));
      observer.observe(dashboard, { attributes: true, attributeFilter: ['class'] });
    }
    setTimeout(renderAll, 650);
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(bind, 300));
  window.validateV42DataQuality = validateV42DataQuality;
  window.renderV42SystemDiagnostics = renderAll;
  window.renderV42ManualEnhancements = renderManualEnhancements;
})();
