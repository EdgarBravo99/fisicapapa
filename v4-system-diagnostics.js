// v4-system-diagnostics.js
// Personal V4.2 decision center, data-quality audit, score source comparison, and combo profiles.
(function () {
  'use strict';

  const MAX_NUMBER = 56;
  const PICK_COUNT = 6;
  const $ = id => document.getElementById(id);
  const number = value => Number(value);
  const finite = value => Number.isFinite(number(value));
  const fmt = (value, digits = 2) => finite(value) ? number(value).toFixed(digits) : 'N/D';
  const esc = value => String(value ?? 'N/D').replace(/[&<>"']/g, mark => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[mark]));
  const clamp = (value, min = 0, max = 100) => Math.max(min, Math.min(max, finite(value) ? number(value) : 0));
  const pct = value => {
    const n = number(value);
    if (!Number.isFinite(n)) return null;
    return n > 0 && n <= 1 ? n * 100 : n;
  };
  const displayJson = value => JSON.stringify(value, (_key, raw) => raw === null ? 'N/D' : raw, 2);

  function comboNumbers(combo) {
    const raw = Array.isArray(combo) ? combo : combo?.numbers || combo?.nums || combo?.combo || [];
    return raw.map(Number).filter(n => Number.isInteger(n) && n >= 1 && n <= MAX_NUMBER).sort((a, b) => a - b);
  }

  function comboKey(input) {
    return comboNumbers(input).join('-');
  }

  function getFeedbackLoop(jsonData) {
    return jsonData?.feedback_loop || jsonData?.walk_forward?.feedback_loop || jsonData?.deep_stacking?.feedback_loop || {};
  }

  function rows(jsonData) {
    return Array.isArray(jsonData?.manual_suggestion_seed) ? jsonData.manual_suggestion_seed : [];
  }

  function countRows(jsonData, predicate) {
    return rows(jsonData).filter(predicate).length;
  }

  function hasRealWeight(row) {
    return finite(row?.real_weight ?? row?.raw_weight ?? row?.base_weight ?? row?.ball_weight ?? row?.weight ?? row?.measured_weight);
  }

  function hasEffectiveWeight(row) {
    return finite(row?.effective_weight ?? row?.effectiveWeight ?? row?.weight_effective ?? row?.sigmoid_weight ?? row?.w_eff);
  }

  function hasUsesSinceCalibration(row) {
    return finite(row?.uses_since_calibration ?? row?.uses_in_window ?? row?.uses ?? row?.hits_in_window);
  }

  function validateV42DataQuality(jsonData) {
    const manualSeed = rows(jsonData).length;
    const topCombinations = Array.isArray(jsonData?.top_combinations) ? jsonData.top_combinations.length : 0;
    const generatorPool = Array.isArray(jsonData?.generator_pool) ? jsonData.generator_pool.length : 0;
    const walkForwardRows = Array.isArray(jsonData?.walk_forward?.rows) ? jsonData.walk_forward.rows.length : Number(jsonData?.walk_forward?.rows ?? 0) || 0;
    const counts = {
      manualSeed,
      realWeights: countRows(jsonData, hasRealWeight),
      effectiveWeights: countRows(jsonData, hasEffectiveWeight),
      usesSinceCalibration: countRows(jsonData, hasUsesSinceCalibration),
      generatorPool,
      topCombinations,
      walkForwardRows,
    };
    const errors = [];
    const warnings = [];
    const feedback = getFeedbackLoop(jsonData);
    if (feedback.version !== 'V4.2') errors.push('feedback_loop.version no es V4.2.');
    if (manualSeed !== MAX_NUMBER) errors.push(`manual_suggestion_seed trae ${manualSeed}/56 entradas.`);
    if (counts.effectiveWeights !== MAX_NUMBER) errors.push(`effective_weight trae ${counts.effectiveWeights}/56 entradas.`);
    if (counts.realWeights !== MAX_NUMBER) warnings.push(`peso real trae ${counts.realWeights}/56 entradas.`);
    if (counts.usesSinceCalibration !== MAX_NUMBER) warnings.push(`usos desde calibracion trae ${counts.usesSinceCalibration}/56 entradas.`);
    if (!finite(jsonData?.physics_summary?.avg_effective_weight)) warnings.push('physics_summary.avg_effective_weight no esta disponible.');
    if (!topCombinations) warnings.push('top_combinations esta vacio; se usara generator_pool cuando exista.');
    if (!generatorPool) errors.push('generator_pool no esta disponible.');
    if (!walkForwardRows) warnings.push('walk_forward.rows no esta disponible o no trae filas.');
    return { ok: errors.length === 0, errors, warnings, counts };
  }

  function detectScale(value) {
    if (!finite(value)) return 'unknown';
    const n = number(value);
    if (n >= 0 && n <= 1) return '0-1';
    if (n > 1 && n <= 100) return '0-100';
    return 'unknown';
  }

  function firstCruncherScore(combo) {
    const candidates = [
      ['score_percent', combo?.score_percent],
      ['net_score', combo?.net_score],
      ['confidence', combo?.confidence],
      ['score', combo?.score],
    ];
    const hit = candidates.find(([, value]) => finite(value));
    if (!hit) return { raw: null, normalized: null, scaleDetected: 'unknown', field: null };
    return { raw: number(hit[1]), normalized: pct(hit[1]), scaleDetected: detectScale(hit[1]), field: hit[0] };
  }

  function findCombo(combo, jsonData) {
    const target = comboKey(combo);
    const top = Array.isArray(jsonData?.top_combinations) ? jsonData.top_combinations : [];
    const pool = Array.isArray(jsonData?.generator_pool) ? jsonData.generator_pool : [];
    const all = top.map((item, index) => ({ item, source: 'top_combinations', rank: index + 1 }))
      .concat(pool.map((item, index) => ({ item, source: 'generator_pool', rank: index + 1 })));
    return all.find(entry => comboKey(entry.item) === target) || null;
  }

  function compareCruncherVsWebScore(combo, jsonData) {
    const numbers = comboNumbers(combo);
    let webScore = 0;
    try {
      webScore = window.evaluateManualComboV4(numbers, jsonData).netScoreV4;
    } catch (_) {
      webScore = null;
    }
    const found = findCombo(numbers, jsonData);
    const cruncher = firstCruncherScore(found?.item);
    const delta = finite(cruncher.normalized) && finite(webScore) ? number(webScore) - number(cruncher.normalized) : null;
    let interpretation = 'No se encontro esta combinacion en top_combinations ni generator_pool.';
    if (found && delta !== null) {
      const abs = Math.abs(delta);
      if (abs <= 5) interpretation = 'Coincide bien con el cruncher.';
      else if (delta < 0) interpretation = 'La web penaliza por estructura, fisica o pool.';
      else interpretation = 'La web la favorece mas que el score exportado; revisar componentes.';
      if (abs > 18) interpretation = 'Hay diferencia alta; revisar escalas o componentes.';
    }
    return {
      foundInPool: Boolean(found),
      cruncherScore: finite(cruncher.normalized) ? cruncher.normalized : null,
      webScore: finite(webScore) ? webScore : null,
      delta,
      scaleDetected: cruncher.scaleDetected,
      interpretation,
      source: found?.source || null,
      rank: found?.rank || null,
      scoreField: cruncher.field,
    };
  }

  function under40Profile(numbers, jsonData) {
    if (typeof window.computeUnder40Pressure !== 'function') return null;
    try {
      return window.computeUnder40Pressure(jsonData, numbers);
    } catch (_) {
      return null;
    }
  }

  function getComboProfileV4(evaluation, jsonData) {
    const summary = evaluation?.summary || {};
    const badges = [];
    const add = (label, tone = 'slate', reason = '') => badges.push({ label, tone, reason });
    if (summary.modelScore >= 80) add('Fuerte por modelo', 'cyan', 'El componente modelo domina positivamente.');
    if (summary.gravityPhysics >= 78) add('Fuerte por fisica', 'emerald', 'La fisica efectiva no castiga la combinacion.');
    if (summary.structuralBalance >= 78) add('Buena estructura', 'violet', 'Paridad, lados, decadas y suma estan sanos.');
    if (summary.poolAlignment < 45) add('Debil en pool', 'amber', 'Tiene poca cercania con generator_pool.');
    if (summary.modelScore >= 68 && summary.structuralBalance >= 68 && summary.gravityPhysics >= 68 && summary.poolAlignment >= 45) add('Balanceada', 'emerald', 'No depende de un solo componente.');
    const gravity = evaluation?.components?.gravityPhysics;
    const extreme = Math.abs(Number(gravity?.meanDeviation ?? 0)) > 0.055 || Math.abs(Number(gravity?.avgAbsDeviation ?? 0)) > 0.065;
    if (extreme || ['Muy Pesado', 'Muy Ligero'].includes(evaluation?.gravityProfile)) add('Riesgo fisico extremo', 'red', 'El perfil de peso se aleja del promedio efectivo.');
    const macro = under40Profile(evaluation?.numbers || [], jsonData);
    if (macro?.available) {
      if (macro.status === 'alineado') add('Macro <40 alineada', 'emerald', 'El auditor visual <40 no marca alerta fuerte.');
      else add('Macro <40 desalineada', 'amber', 'El auditor visual <40 sugiere revisar macroestructura.');
    }
    if (summary.modelScore >= 82 && (summary.structuralBalance < 58 || summary.gravityPhysics < 58)) add('Experimental agresiva', 'amber', 'Modelo alto con trade-off estructural o fisico.');
    if (summary.modelScore < 72 && summary.structuralBalance >= 76 && summary.gravityPhysics >= 76) add('Conservadora', 'slate', 'Menos empuje de modelo, mas estabilidad.');
    if (badges.length === 0 || summary.structuralBalance < 50 || summary.gravityPhysics < 50) add('Requiere revision', 'red', 'Hay componentes flojos para revisar antes de usarla.');
    return badges;
  }

  function badgeHtml(badge) {
    const tones = {
      cyan: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
      emerald: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
      violet: 'border-violet-300/30 bg-violet-400/10 text-violet-100',
      amber: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
      red: 'border-red-300/30 bg-red-500/10 text-red-100',
      slate: 'border-slate-600 bg-slate-800/80 text-slate-100',
    };
    return `<span class="rounded-full border ${tones[badge.tone] || tones.slate} px-3 py-1 text-xs font-bold">${esc(badge.label)}</span>`;
  }

  function card(label, value, status = 'OK', detail = '') {
    const tone = status === 'Critico'
      ? 'border-red-400/40 bg-red-500/10 text-red-100'
      : status === 'Revisar'
        ? 'border-amber-400/40 bg-amber-400/10 text-amber-100'
        : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-100';
    return `<article class="rounded-2xl border ${tone} p-4">
      <p class="text-[10px] uppercase tracking-[0.22em] opacity-75">${esc(label)}</p>
      <p class="mt-2 text-lg font-black">${esc(value)}</p>
      ${detail ? `<p class="mt-1 text-xs opacity-80">${esc(detail)}</p>` : ''}
    </article>`;
  }

  function renderPersonalCenter(jsonData) {
    const panel = $('personal-center-panel');
    if (!panel) return;
    const quality = validateV42DataQuality(jsonData);
    const feedback = getFeedbackLoop(jsonData);
    const top = Array.isArray(jsonData?.top_combinations) && jsonData.top_combinations.length ? jsonData.top_combinations[0] : (jsonData?.generator_pool || [])[0];
    const bestCombo = comboNumbers(top);
    const bestNumber = rows(jsonData).slice().sort((a, b) => (pct(b.score ?? b.meta_score ?? b.score_percent ?? b.net_score) || 0) - (pct(a.score ?? a.meta_score ?? a.score_percent ?? a.net_score) || 0))[0];
    const hasCritical = quality.errors.length > 0;
    const hasReview = quality.warnings.length > 0;
    const status = hasCritical ? 'Critico' : hasReview ? 'Revisar' : 'OK';
    const statusEl = $('personal-center-status');
    if (statusEl) {
      statusEl.textContent = status;
      statusEl.className = `rounded-2xl border px-4 py-2 text-sm font-bold ${status === 'Critico' ? 'border-red-400/40 bg-red-500/10 text-red-100' : status === 'Revisar' ? 'border-amber-400/40 bg-amber-400/10 text-amber-100' : 'border-emerald-400/40 bg-emerald-400/10 text-emerald-100'}`;
    }
    const firstAction = hasCritical
      ? 'Actualizar resultados.json'
      : hasReview
        ? 'Revisar fisica y auditor'
        : 'Evaluar y comparar manual';
    panel.innerHTML = `
      <div class="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        ${card('JSON', jsonData?.last_update || 'Sin timestamp', hasCritical ? 'Critico' : 'OK', 'Cache: fetch no-store + parametro temporal.')}
        ${card('Modo / modelo', `${jsonData?.game_mode || 'N/D'} / ${feedback.version || 'N/D'}`, feedback.version === 'V4.2' ? 'OK' : 'Critico', jsonData?.model_version || jsonData?.source || 'V4.2')}
        ${card('Fisica', `${quality.counts.realWeights}/56 reales, ${quality.counts.effectiveWeights}/56 efectivos`, quality.counts.effectiveWeights === 56 ? (quality.counts.realWeights === 56 ? 'OK' : 'Revisar') : 'Critico', `${quality.counts.usesSinceCalibration}/56 usos desde calibracion`)}
        ${card('Combinaciones', `${quality.counts.topCombinations} top, ${quality.counts.generatorPool} pool`, quality.counts.generatorPool ? 'OK' : 'Critico', `Walk-forward rows: ${quality.counts.walkForwardRows}`)}
      </div>
      <div class="grid gap-3 lg:grid-cols-3">
        <article class="rounded-2xl border border-cyan-400/20 bg-slate-900/70 p-4">
          <p class="text-xs uppercase tracking-[0.22em] text-cyan-300">Mejor combinacion actual</p>
          <p class="mt-2 text-xl font-black text-white">${bestCombo.length ? bestCombo.join(' - ') : 'N/D'}</p>
          <button class="mt-3 min-h-[44px] rounded-xl border border-cyan-300/40 bg-cyan-400/10 px-3 py-2 text-sm font-bold text-cyan-100" data-fill-combo="${bestCombo.join(',')}">Evaluar esta combinacion</button>
        </article>
        <article class="rounded-2xl border border-violet-400/20 bg-slate-900/70 p-4">
          <p class="text-xs uppercase tracking-[0.22em] text-violet-300">Mejor numero actual</p>
          <p class="mt-2 text-xl font-black text-white">${esc(bestNumber?.number ?? bestNumber?.n ?? bestNumber?.ball)}</p>
          <p class="mt-1 text-xs text-slate-400">Score interno: ${fmt(pct(bestNumber?.score ?? bestNumber?.meta_score ?? bestNumber?.score_percent ?? bestNumber?.net_score))}</p>
        </article>
        <article class="rounded-2xl border border-amber-400/20 bg-slate-900/70 p-4">
          <p class="text-xs uppercase tracking-[0.22em] text-amber-300">Revisar primero</p>
          <p class="mt-2 text-xl font-black text-white">${esc(firstAction)}</p>
          <p class="mt-1 text-xs text-slate-400">Los scores son indices internos de decision, no probabilidades garantizadas.</p>
        </article>
      </div>
      <div class="flex flex-wrap gap-2">
        <a class="min-h-[44px] rounded-xl border border-cyan-300/40 bg-cyan-400/10 px-3 py-3 text-sm font-bold text-cyan-100" href="#manual-evaluator-section">Evaluar manual</a>
        <a class="min-h-[44px] rounded-xl border border-amber-300/40 bg-amber-400/10 px-3 py-3 text-sm font-bold text-amber-100" href="#top-combinations-section">Ver top combos</a>
        <a class="min-h-[44px] rounded-xl border border-emerald-300/40 bg-emerald-400/10 px-3 py-3 text-sm font-bold text-emerald-100" href="#physics-section">Revisar fisica</a>
        <a class="min-h-[44px] rounded-xl border border-violet-300/40 bg-violet-400/10 px-3 py-3 text-sm font-bold text-violet-100" href="#combo-comparator-section">Comparar</a>
      </div>`;
    panel.querySelector('[data-fill-combo]')?.addEventListener('click', event => {
      const nums = event.currentTarget.getAttribute('data-fill-combo').split(',').map(Number);
      nums.forEach((n, index) => {
        const input = $(`manual-n${index + 1}`);
        if (input) input.value = n;
      });
      $('btn-evaluate-manual')?.click();
      $('manual-evaluator-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function renderAuditor(jsonData) {
    const panel = $('auditor-panel');
    if (!panel) return;
    const quality = validateV42DataQuality(jsonData);
    const top = Array.isArray(jsonData?.top_combinations) ? jsonData.top_combinations[0] : null;
    const numberTop = rows(jsonData).slice().sort((a, b) => (pct(b.score ?? b.meta_score ?? b.score_percent ?? b.net_score) || 0) - (pct(a.score ?? a.meta_score ?? a.score_percent ?? a.net_score) || 0))[0] || null;
    const scales = (jsonData?.top_combinations || []).slice(0, 10).map(firstCruncherScore).map(score => score.scaleDetected);
    panel.innerHTML = `
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        ${Object.entries(quality.counts).map(([key, value]) => card(key, value, value ? 'OK' : 'Revisar')).join('')}
      </div>
      <div class="grid gap-3 lg:grid-cols-2">
        <article class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
          <p class="font-black text-white">Advertencias</p>
          <ul class="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-300">${quality.errors.concat(quality.warnings).map(item => `<li>${esc(item)}</li>`).join('') || '<li>Sin advertencias de contrato.</li>'}</ul>
          <p class="mt-3 text-xs text-slate-400">Escalas top detectadas: ${esc([...new Set(scales)].join(', ') || 'N/D')}</p>
        </article>
        <article class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
          <p class="font-black text-white">Calidad fisica / walk-forward</p>
          <p class="mt-2 text-xs text-slate-300">avg_effective_weight: ${fmt(jsonData?.physics_summary?.avg_effective_weight, 4)}g</p>
          <p class="mt-1 text-xs text-slate-300">walk_forward.rows: ${quality.counts.walkForwardRows}</p>
          <p class="mt-1 text-xs text-slate-300">Calibracion esperada: 2026-05-17 / sorteo 4214 / reset posterior a 4213.</p>
        </article>
      </div>
      <details class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <summary class="cursor-pointer font-black text-white">Raw top combination</summary>
        <pre class="mt-3 max-h-72 overflow-auto text-xs text-slate-300">${esc(displayJson(top))}</pre>
      </details>
      <details class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
        <summary class="cursor-pointer font-black text-white">Raw top number</summary>
        <pre class="mt-3 max-h-72 overflow-auto text-xs text-slate-300">${esc(displayJson(numberTop))}</pre>
      </details>`;
  }

  function renderSystemDiagnostics(jsonData) {
    const panel = $('system-diagnostics-panel');
    if (!panel) return;
    const quality = validateV42DataQuality(jsonData);
    const feedback = getFeedbackLoop(jsonData);
    const physics = jsonData?.physics_summary || {};
    const status = $('system-diagnostics-status');
    const state = quality.ok ? (quality.warnings.length ? 'Revisar' : 'OK V4.2') : `${quality.errors.length} errores`;
    if (status) {
      status.textContent = state;
      status.className = `rounded-2xl border px-4 py-2 text-sm font-bold ${quality.ok ? (quality.warnings.length ? 'border-amber-400/40 bg-amber-400/10 text-amber-100' : 'border-emerald-400/30 bg-emerald-400/10 text-emerald-100') : 'border-red-400/40 bg-red-500/10 text-red-100'}`;
    }
    const messages = quality.errors.concat(quality.warnings);
    panel.innerHTML = `
      <div class="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        ${card('Modelo', jsonData?.model_version || jsonData?.source || 'N/D', feedback.version === 'V4.2' ? 'OK' : 'Critico', jsonData?.last_update || 'Sin timestamp')}
        ${card('Modo', jsonData?.game_mode || jsonData?.game_label || 'N/D', jsonData?.game_mode || jsonData?.game_label ? 'OK' : 'Revisar', `feedback ${feedback.version || 'N/D'}`)}
        ${card('Pool', `${quality.counts.generatorPool} combos`, quality.counts.generatorPool ? 'OK' : 'Critico', `${quality.counts.topCombinations} top_combinations`)}
        ${card('Walk-forward', `${quality.counts.walkForwardRows} folds`, quality.counts.walkForwardRows ? 'OK' : 'Revisar', 'rows disponibles para auditoria')}
        ${card('manual_suggestion_seed', `${quality.counts.manualSeed}/56`, quality.counts.manualSeed === 56 ? 'OK' : 'Critico')}
        ${card('Pesos reales', `${quality.counts.realWeights}/56`, quality.counts.realWeights === 56 ? 'OK' : 'Revisar')}
        ${card('Pesos efectivos', `${quality.counts.effectiveWeights}/56`, quality.counts.effectiveWeights === 56 ? 'OK' : 'Critico')}
        ${card('Usos calibracion', `${quality.counts.usesSinceCalibration}/56`, quality.counts.usesSinceCalibration === 56 ? 'OK' : 'Revisar')}
      </div>
      <div class="rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300">
        <p class="font-black text-white">Calibracion fisica</p>
        <p class="mt-2 leading-6">Fecha 2026-05-17 / sorteo 4214. Reset de vida util despues del sorteo 4213. Promedio efectivo: ${fmt(physics.avg_effective_weight, 4)}g.</p>
      </div>
      ${messages.length ? `<div class="grid gap-2">${messages.map(item => `<p class="rounded-xl border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-sm text-amber-100">${esc(item)}</p>`).join('')}</div>` : '<p class="rounded-xl border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 text-sm font-bold text-emerald-100">Contrato y conteos principales completos.</p>'}`;
  }

  function enhanceTopCombinationCards(jsonData) {
    const panel = $('top-combinations-panel');
    if (!panel) return;
    panel.querySelectorAll('article').forEach((article, index) => {
      if (article.dataset.v42Enhanced === '1') return;
      const fillButton = article.querySelector('[data-fill-combo]');
      const nums = fillButton?.getAttribute('data-fill-combo')?.split(',').map(Number).filter(Number.isInteger) || [];
      if (nums.length !== PICK_COUNT) return;
      let evaluation = null;
      try {
        evaluation = window.evaluateManualComboV4(nums, jsonData);
      } catch (_) {
        return;
      }
      const compare = compareCruncherVsWebScore(nums, jsonData);
      const badges = getComboProfileV4(evaluation, jsonData);
      const actions = document.createElement('div');
      actions.className = 'mt-3 grid gap-2';
      actions.innerHTML = `
        <div class="flex flex-wrap gap-2">${badges.map(badgeHtml).join('')}</div>
        <p class="text-xs text-slate-500">Score web ${fmt(compare.webScore)} | score cruncher ${fmt(compare.cruncherScore)} | ${esc(compare.interpretation)}</p>
        <div class="flex flex-wrap gap-2">
          <button class="min-h-[44px] rounded-xl border border-violet-300/40 bg-violet-400/10 px-3 py-2 text-xs font-bold text-violet-100" data-save-top-combo="${nums.join(',')}" data-save-label="Top #${index + 1}">Guardar al comparador</button>
          <button class="min-h-[44px] rounded-xl border border-slate-600 bg-slate-800 px-3 py-2 text-xs font-bold text-slate-100" data-copy-top-combo="${nums.join(' ')}">Copiar</button>
        </div>`;
      article.appendChild(actions);
      article.dataset.v42Enhanced = '1';
    });
    panel.querySelectorAll('[data-save-top-combo]').forEach(button => {
      if (button.dataset.bound === '1') return;
      button.dataset.bound = '1';
      button.addEventListener('click', () => {
        const nums = button.getAttribute('data-save-top-combo').split(',').map(Number);
        window.FISICAPAPA_COMPARATOR?.saveCombo(nums, button.getAttribute('data-save-label'));
        $('combo-comparator-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
    });
    panel.querySelectorAll('[data-copy-top-combo]').forEach(button => {
      if (button.dataset.bound === '1') return;
      button.dataset.bound = '1';
      button.addEventListener('click', () => {
        navigator.clipboard?.writeText(button.getAttribute('data-copy-top-combo')).catch(() => {});
      });
    });
  }

  function seedByNumber(jsonData) {
    const map = new Map();
    rows(jsonData).forEach(row => {
      const n = Number(row?.number ?? row?.n ?? row?.ball);
      if (Number.isInteger(n)) map.set(n, row);
    });
    return map;
  }

  function enhanceTopNumberCards(jsonData) {
    const panel = $('top-numbers-panel');
    if (!panel) return;
    const map = seedByNumber(jsonData);
    const avg = Number(jsonData?.physics_summary?.avg_effective_weight);
    panel.querySelectorAll('article').forEach(article => {
      if (article.dataset.v42Enhanced === '1') return;
      const numberText = article.querySelector('span')?.textContent;
      const n = Number(numberText);
      const row = map.get(n);
      if (!row) return;
      const experts = row.expert_raw || row.expert_scores || row.experts || {};
      const transformer = pct(experts.transformer ?? row.transformer_score);
      const xgboost = pct(experts.xgboost ?? row.xgboost_score);
      const graph = pct(experts.graph ?? row.graph_score);
      const effective = Number(row.effective_weight ?? row.effectiveWeight ?? row.weight_effective ?? row.sigmoid_weight ?? row.w_eff);
      const physicsBadge = !Number.isFinite(effective) || !Number.isFinite(avg)
        ? 'sin fisica'
        : effective > avg
          ? 'fisica pesada'
          : 'fisica ligera';
      const line = document.createElement('p');
      line.className = 'mt-2 text-xs text-slate-300';
      line.innerHTML = `Transformer: <b>${fmt(transformer)}</b> | XGBoost: <b>${fmt(xgboost)}</b> | Graph: <b>${fmt(graph)}</b> | badge: <b>${esc(physicsBadge)}</b>`;
      article.appendChild(line);
      article.dataset.v42Enhanced = '1';
    });
  }

  function componentDelta(before, after, key) {
    return Number(after?.summary?.[key] ?? 0) - Number(before?.summary?.[key] ?? 0);
  }

  function weakestNumber(evaluation) {
    const gravityRows = evaluation?.components?.gravityPhysics?.physicalRows || [];
    const rows = (evaluation?.components?.modelScore?.rows || []).map(row => {
      const phys = gravityRows.find(item => item.number === row.number) || {};
      const physicsScore = Number.isFinite(Number(phys.effectiveWeight)) ? Number(evaluation?.components?.gravityPhysics?.score || 0) : 0;
      const localScore = clamp((row.expertAverage || row.modelScore || 0) * 0.68 + physicsScore * 0.16 + Number(evaluation?.components?.structuralBalance?.score || 0) * 0.16);
      return { number: row.number, localScore };
    });
    return rows.sort((a, b) => a.localScore - b.localScore)[0] || null;
  }

  function replacementReasons(current, evaluated, beforeNums, afterNums) {
    const reasons = [];
    const model = componentDelta(current, evaluated, 'modelScore');
    const physics = componentDelta(current, evaluated, 'gravityPhysics');
    const structure = componentDelta(current, evaluated, 'structuralBalance');
    const pool = componentDelta(current, evaluated, 'poolAlignment');
    const under = afterNums.filter(n => n < 40).length - beforeNums.filter(n => n < 40).length;
    if (model > 0.1) reasons.push(`modelo +${fmt(model)}`);
    if (physics > 0.1) reasons.push(`fisica +${fmt(physics)}`);
    if (structure > 0.1) reasons.push(`estructura +${fmt(structure)}`);
    if (pool > 0.1) reasons.push(`pool +${fmt(pool)}`);
    if (under !== 0) reasons.push(`<40 ${under > 0 ? '+' : ''}${under}`);
    return reasons.length ? reasons : ['mejora ranking compuesto sin cambiar formula oficial'];
  }

  function topReplacementSuggestions(numbers, jsonData, currentEvaluation) {
    const weak = weakestNumber(currentEvaluation);
    if (!weak || typeof window.evaluateManualComboV4 !== 'function') return [];
    const current = new Set(numbers);
    const suggestions = [];
    for (let candidate = 1; candidate <= MAX_NUMBER; candidate += 1) {
      if (current.has(candidate)) continue;
      const next = numbers.map(n => n === weak.number ? candidate : n).sort((a, b) => a - b);
      let evaluated;
      try {
        evaluated = window.evaluateManualComboV4(next, jsonData);
      } catch (_) {
        continue;
      }
      const gain = evaluated.netScoreV4 - currentEvaluation.netScoreV4;
      const componentLift = Math.max(0, componentDelta(currentEvaluation, evaluated, 'modelScore')) * 0.40
        + Math.max(0, componentDelta(currentEvaluation, evaluated, 'structuralBalance')) * 0.24
        + Math.max(0, componentDelta(currentEvaluation, evaluated, 'poolAlignment')) * 0.20
        + Math.max(0, componentDelta(currentEvaluation, evaluated, 'gravityPhysics')) * 0.16;
      suggestions.push({
        remove: weak.number,
        add: candidate,
        next,
        gain,
        ranking: gain + componentLift,
        reasons: replacementReasons(currentEvaluation, evaluated, numbers, next),
      });
    }
    return suggestions.sort((a, b) => b.ranking - a.ranking).slice(0, 3);
  }

  function renderManualDiagnostics(jsonData) {
    const manual = $('manual-result');
    if (!manual || manual.classList.contains('hidden')) return;
    const inputs = [1, 2, 3, 4, 5, 6].map(i => Number($(`manual-n${i}`)?.value));
    if (inputs.some(n => !Number.isInteger(n))) return;
    let evaluation;
    try {
      evaluation = window.evaluateManualComboV4(inputs, jsonData);
    } catch (_) {
      return;
    }
    const compare = compareCruncherVsWebScore(evaluation.numbers, jsonData);
    const badges = getComboProfileV4(evaluation, jsonData);
    const weak = weakestNumber(evaluation);
    const replacements = topReplacementSuggestions(evaluation.numbers, jsonData, evaluation);
    const replacementHtml = replacements.map((item, index) => `<article class="rounded-xl border border-violet-400/20 bg-violet-400/10 p-3">
      <div class="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <p class="font-black text-violet-100">#${index + 1}: ${item.remove} -&gt; ${item.add}</p>
        <p class="text-xs font-bold text-emerald-200">neto ${item.gain >= 0 ? '+' : ''}${fmt(item.gain)}</p>
      </div>
      <p class="mt-2 text-xs leading-5 text-slate-300">${esc(item.next.join(' | '))}</p>
      <p class="mt-2 text-xs leading-5 text-slate-400">${item.reasons.map(esc).join(' | ')}</p>
    </article>`).join('');
    const existing = $('manual-score-compare-card');
    if (existing) existing.remove();
    const cardNode = document.createElement('div');
    cardNode.id = 'manual-score-compare-card';
    cardNode.className = 'mt-4 grid gap-3 rounded-3xl border border-cyan-400/20 bg-slate-900/80 p-5';
    cardNode.innerHTML = `
      <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div>
          <p class="text-xs uppercase tracking-[0.22em] text-cyan-300">Score cruncher vs score web</p>
          <p class="mt-2 text-sm text-slate-300">Web: <b class="text-cyan-100">${fmt(compare.webScore)}</b> | Cruncher: <b class="text-amber-100">${fmt(compare.cruncherScore)}</b> | delta: <b>${compare.delta === null ? 'N/D' : fmt(compare.delta)}</b></p>
          <p class="mt-1 text-xs text-slate-400">${esc(compare.interpretation)} Escala detectada: ${esc(compare.scaleDetected)}.</p>
        </div>
        <button class="min-h-[44px] rounded-xl border border-violet-300/40 bg-violet-400/10 px-3 py-2 text-sm font-bold text-violet-100" data-save-manual-combo="${evaluation.numbers.join(',')}">Guardar al comparador</button>
      </div>
      <div class="flex flex-wrap gap-2">${badges.map(badgeHtml).join('')}</div>
      <div class="rounded-2xl border border-slate-800 bg-slate-950/50 p-4">
        <p class="text-xs uppercase tracking-[0.22em] text-slate-500">Explicabilidad y reemplazos</p>
        <p class="mt-2 text-sm text-slate-300">Numero mas debil: <b class="text-red-200">${weak?.number ?? 'N/D'}</b>. Top 3 reemplazos sugeridos sin cambiar la formula oficial:</p>
        <div class="mt-3 grid gap-3">${replacementHtml || '<p class="text-sm text-slate-400">No se encontraron reemplazos superiores.</p>'}</div>
      </div>`;
    manual.appendChild(cardNode);
    cardNode.querySelector('[data-save-manual-combo]')?.addEventListener('click', event => {
      const nums = event.currentTarget.getAttribute('data-save-manual-combo').split(',').map(Number);
      window.FISICAPAPA_COMPARATOR?.saveCombo(nums, 'Manual evaluada');
      $('combo-comparator-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  function renderAll(jsonData) {
    if (!jsonData) return;
    renderPersonalCenter(jsonData);
    renderAuditor(jsonData);
    renderSystemDiagnostics(jsonData);
    setTimeout(() => enhanceTopCombinationCards(jsonData), 450);
    setTimeout(() => enhanceTopNumberCards(jsonData), 450);
    setTimeout(() => renderManualDiagnostics(jsonData), 0);
  }

  document.addEventListener('fisicapapa:v42-ready', event => renderAll(event.detail?.jsonData));
  document.addEventListener('click', event => {
    if (event.target?.id === 'btn-evaluate-manual') {
      setTimeout(() => renderManualDiagnostics(window.FISICAPAPA_WEB_V2?.jsonData), 0);
    }
  });
  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => renderAll(window.FISICAPAPA_WEB_V2?.jsonData), 500);
  });

  window.validateV42DataQuality = validateV42DataQuality;
  window.compareCruncherVsWebScore = compareCruncherVsWebScore;
  window.getComboProfileV4 = getComboProfileV4;
  window.normalizeComboV4 = comboNumbers;
  window.renderV42PersonalCenter = renderPersonalCenter;
  window.renderV42SystemDiagnostics = renderSystemDiagnostics;
})();
