// python-results-v3-compat.js
// Fuente única V3 para Generador, Evaluador Manual y datos compartidos del mapa de calor.
(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  let v3Results = null;
  let cursor = 0;
  const originalGenerateCombos = window.generateCombos;
  const originalRenderCombosList = window.renderCombosList;
  const originalEvalUserComboUI = window.evalUserComboUI;

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

  function fmt(value, digits = 1) {
    return num(value).toFixed(digits);
  }

  function scorePercent(item) {
    if (Number.isFinite(Number(item?.score_percent))) return Number(item.score_percent);
    if (Number.isFinite(Number(item?.net_score))) return Number(item.net_score) * 100;
    if (Number.isFinite(Number(item?.confidence))) return Number(item.confidence);
    return 0;
  }

  function isV3(data) {
    return Boolean(data && data.score_kind === 'optuna_weighted_net_score');
  }

  function driverLabel(key) {
    return ({
      physical: 'física de esferas',
      temporal: 'inercia temporal',
      entropy: 'estabilidad de entropía',
      fourier: 'micro-ciclos Fourier',
      bayes: 'Bayes por desgaste/frecuencia',
      xgboost: 'XGBoost',
      lstm: 'memoria secuencial LSTM',
      markov: 'transición Markov',
      structural: 'estructura de combinación'
    })[key] || key || 'modelo V3';
  }

  function normalizeV3(data) {
    const seed = Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : [];
    const numberScores = data.number_scores || {};
    const byNumber = new Map();
    for (let n = 1; n <= 56; n++) {
      byNumber.set(n, {
        number: n,
        score: num(numberScores[String(n)], 0),
        winner_component_human: 'sin desglose V3',
        reason: 'sin explicación disponible',
        expert_raw: {}
      });
    }
    seed.forEach(row => {
      const n = Number(row.number);
      if (!Number.isFinite(n)) return;
      byNumber.set(n, {
        ...byNumber.get(n),
        ...row,
        number: n,
        score: num(row.score, byNumber.get(n)?.score || 0),
        winner_component_human: row.winner_component_human || driverLabel(row.winner_component),
        reason: row.reason || 'sin explicación disponible',
        expert_raw: row.expert_raw || {}
      });
    });
    return {
      ...data,
      generator_pool: Array.isArray(data.generator_pool) ? data.generator_pool : [],
      top_combinations: Array.isArray(data.top_combinations) ? data.top_combinations : [],
      manual_suggestion_seed: Array.from(byNumber.values()).sort((a, b) => num(b.score) - num(a.score)),
      numberMap: byNumber,
      walk_forward: data.walk_forward || {},
      expert_weights: data.expert_weights || data.optuna_audit?.best_weights || {}
    };
  }

  async function loadV3(force = false) {
    if (v3Results && !force) return v3Results;
    try {
      const res = await fetch(`${RESULTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      if (!isV3(data)) throw new Error('resultados.json no es V3');
      v3Results = normalizeV3(data);
      window.MELATE_V3_RESULTS = v3Results;
      renderV3Panel();
      document.dispatchEvent(new CustomEvent('melate:v3-results-loaded', { detail: v3Results }));
      return v3Results;
    } catch (err) {
      console.warn('V3 no pudo leer resultados.json:', err);
      v3Results = null;
      window.MELATE_V3_RESULTS = null;
      return null;
    }
  }

  window.loadV3Results = loadV3;
  window.getV3Results = () => v3Results || window.MELATE_V3_RESULTS || null;
  window.getV3NumberRow = (n) => {
    const data = window.getV3Results?.();
    return data?.numberMap?.get(Number(n)) || null;
  };

  function ensurePanel() {
    const body = document.querySelector('#tab-generador .card .card-body');
    if (!body) return null;
    let panel = document.getElementById('v3-sequential-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'v3-sequential-panel';
      panel.style.margin = '0 0 16px 0';
      const combos = document.getElementById('combos-container');
      body.insertBefore(panel, combos || body.firstChild);
    }
    return panel;
  }

  function renderWeights(weights) {
    return Object.entries(weights || {})
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 5)
      .map(([k, v]) => `<span style="margin-right:10px;">${esc(driverLabel(k))}=${(Number(v) * 100).toFixed(1)}%</span>`)
      .join('');
  }

  function renderV3Panel() {
    const panel = ensurePanel();
    if (!panel || !v3Results) return;
    const wf = v3Results.walk_forward || {};
    const forgetting = v3Results.historical_forgetting || {};
    const maxScore = Number(v3Results.max_net_score_found || 0) * 100;
    const recent = Array.isArray(wf.rows) ? wf.rows.slice(-5).reverse() : [];

    panel.innerHTML = `<div style="background:linear-gradient(135deg, rgba(188,140,255,.12), rgba(57,208,194,.08));border:1px solid rgba(188,140,255,.35);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;">
        <div>
          <div style="color:var(--purple);font-family:var(--cond);font-size:16px;font-weight:700;">🧬 Motor Secuencial V3 · ${esc(v3Results.game_label || '')}</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:820px;">${esc(v3Results.procedure_log || 'Sin procedimiento V3.')}</div>
        </div>
        <button class="btn btn-sm btn-teal" id="v3-refresh-btn">↻ Refrescar V3</button>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--purple)">${fmt(maxScore, 2)}</div><div class="stat-lbl">Max net score</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${Number(v3Results.total_mc_evaluated || 0).toLocaleString('es-MX')}</div><div class="stat-lbl">MC evaluadas</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(forgetting.recent_buffer_size ?? 'N/A')}</div><div class="stat-lbl">Buffer reciente</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--red)">${esc(forgetting.discarded_old_draws ?? '0')}</div><div class="stat-lbl">Sorteos olvidados</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--blue)">${esc(wf.avg_hits ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top6</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--green)">${esc(wf.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top10</div></div>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--muted);"><b style="color:var(--text);">Pesos Optuna:</b> ${renderWeights(v3Results.expert_weights)}</div>
      ${recent.length ? `<div class="tbl-wrap" style="margin-top:10px;max-height:160px;overflow:auto;"><table><thead><tr><th>Sorteo</th><th>Hits</th><th>Top10</th><th>MSE</th></tr></thead><tbody>${recent.map(r => `<tr><td>${esc(r.draw_id)}</td><td>${esc(r.hits)}</td><td>${esc(r.hits_top10)}</td><td>${esc(r.mse)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    </div>`;

    document.getElementById('v3-refresh-btn')?.addEventListener('click', async () => {
      await loadV3(true);
      if (typeof renderHeatGrid === 'function') renderHeatGrid();
      if (typeof showToast === 'function') showToast('🧬 V3 recargado desde resultados.json');
    });
  }

  function normalizeV3Combo(item) {
    const sp = scorePercent(item);
    return {
      nums: Array.isArray(item?.numbers) ? item.numbers.map(Number).sort((a, b) => a - b) : [],
      name: `V3 ${item?.game_label || v3Results?.game_label || 'Python'} · ${sp.toFixed(2)}/100`,
      confidence: sp,
      procedure: item?.human_explanation || item?.procedure || item?.plain_route || 'Generado por local_cruncher_v3.py',
      source: 'sequential_gpu_montecarlo_v3',
      metrics: item || {}
    };
  }

  function takeV3Combos(count) {
    if (!v3Results?.generator_pool?.length) return [];
    const out = [];
    for (let i = 0; i < count; i++) {
      out.push(normalizeV3Combo(v3Results.generator_pool[cursor % v3Results.generator_pool.length]));
      cursor += 1;
    }
    return out;
  }

  function ballHtml(nums, color = 'var(--purple)') {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</div>`).join('');
  }

  window.generateCombos = async function generateCombosV3Only(count) {
    const data = await loadV3(true);
    if (!data) {
      if (typeof showToast === 'function') showToast('⚠️ Ejecuta local_cruncher_v3.py para generar resultados.json V3');
      return typeof originalGenerateCombos === 'function' ? originalGenerateCombos(count) : undefined;
    }
    const combos = takeV3Combos(count);
    if (!combos.length) {
      if (typeof showToast === 'function') showToast('⚠️ resultados.json V3 no trae generator_pool');
      return;
    }
    generatedCombos.unshift(...combos);
    renderCombosList();
    if (typeof showToast === 'function') showToast(`🧬 ${combos.length} combinaciones V3 cargadas`);
  };

  window.renderCombosList = function renderCombosV3Only() {
    const container = document.getElementById('combos-container');
    if (!container) return;
    if (!generatedCombos.length) {
      container.innerHTML = '';
      if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
      return;
    }
    const hasV3 = generatedCombos.some(c => c.source === 'sequential_gpu_montecarlo_v3');
    if (!hasV3 && typeof originalRenderCombosList === 'function') return originalRenderCombosList();

    container.innerHTML = generatedCombos.map((cb, i) => {
      if (cb.source !== 'sequential_gpu_montecarlo_v3') return '';
      const ev = typeof evalCombo === 'function' ? evalCombo(cb.nums) : {};
      const pares = Number.isFinite(Number(ev.pares)) ? Number(ev.pares) : cb.nums.filter(n => n % 2 === 0).length;
      const impares = Number.isFinite(Number(ev.impares)) ? Number(ev.impares) : 6 - pares;
      const suma = Number.isFinite(Number(ev.suma)) ? Number(ev.suma) : cb.nums.reduce((a, b) => a + b, 0);
      const decades = ev.decades ?? ev.decadas ?? new Set(cb.nums.map(n => Math.floor((n - 1) / 10))).size;
      const score = Number(cb.confidence || 0);
      const color = score >= 80 ? 'var(--green)' : score >= 65 ? 'var(--gold)' : 'var(--purple)';
      const savedLabel = typeof isComboSaved === 'function' && isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
      const savedDisabled = savedLabel === 'Guardado' ? 'disabled' : '';
      const route = cb.metrics?.plain_route || (Array.isArray(cb.metrics?.number_explanations) ? cb.metrics.number_explanations.map(x => `${x.number}: ${x.main_driver_human || x.driver_human || 'V3'}`).join(' | ') : '');
      return `<div class="combo-card" style="border-color:${color}70">
        <div class="combo-card-header">
          <span style="color:${color};font-weight:700">#${generatedCombos.length - i} · ${esc(cb.name)}</span>
          <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">NET SCORE: ${score.toFixed(2)}</span>
        </div>
        <div class="combo-balls">${ballHtml(cb.nums, color)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;">Suma: ${suma} | P/I: ${pares}P/${impares}I | Décadas: ${decades}</div>
        <div style="margin-top:10px;background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:8px;padding:10px;font-size:12px;color:var(--muted);line-height:1.55;">
          <div style="color:var(--purple);font-weight:700;margin-bottom:6px;">🧬 Explicación V3</div>
          <div>${esc(cb.procedure)}</div>
          <div style="margin-top:8px;color:var(--dim);">${esc(route)}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;">
          <button class="btn btn-sm btn-blue" onclick="window.evalPythonComboFromGenerated(${i})">📊 Explicar</button>
          <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
        </div>
      </div>`;
    }).join('');
    if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
  };

  window.evalPythonComboFromGenerated = function evalPythonComboFromGenerated(index) {
    const item = generatedCombos[index];
    if (!item) return;
    item.nums.forEach((n, i) => {
      const input = document.getElementById(`u${i + 1}`);
      if (input) input.value = n;
    });
    window.evalUserComboUI();
  };

  function getManualNums() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`)?.value, 10));
    if (nums.some(n => Number.isNaN(n) || n < 1 || n > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(nums).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return nums.sort((a, b) => a - b);
  }

  function comboStats(nums) {
    const pares = nums.filter(n => n % 2 === 0).length;
    const lows = nums.filter(n => n <= 28).length;
    const decades = new Set(nums.map(n => Math.floor((n - 1) / 10))).size;
    const suma = nums.reduce((a, b) => a + b, 0);
    const consec = nums.slice(1).filter((n, i) => n - nums[i] === 1).length;
    return { pares, impares: 6 - pares, lows, highs: 6 - lows, decades, suma, consec };
  }

  function manualAnalysis(nums, data) {
    const details = nums.map(n => {
      const row = data.numberMap.get(n) || { number: n, score: 0, winner_component_human: 'sin datos', reason: 'sin explicación' };
      return { ...row, score: num(row.score) };
    });
    const score = details.reduce((acc, row) => acc + row.score, 0) / 6;
    return { score, details, stats: comboStats(nums) };
  }

  function rankCandidatePool(nums, data) {
    const current = new Set(nums);
    const rows = data.manual_suggestion_seed.filter(row => !current.has(Number(row.number)));
    const currentDrivers = new Set(nums.map(n => data.numberMap.get(n)?.winner_component_human).filter(Boolean));
    const stats = comboStats(nums);
    return rows.map(row => {
      const n = Number(row.number);
      let bonus = 0;
      const driver = row.winner_component_human || driverLabel(row.winner_component);
      if (!currentDrivers.has(driver)) bonus += 4;
      if ((stats.pares < 2 && n % 2 === 0) || (stats.pares > 4 && n % 2 === 1)) bonus += 6;
      if ((stats.lows < 2 && n <= 28) || (stats.lows > 4 && n > 28)) bonus += 6;
      if (!nums.some(x => Math.floor((x - 1) / 10) === Math.floor((n - 1) / 10))) bonus += 3;
      if (stats.suma < 115 && n > 28) bonus += 4;
      if (stats.suma > 235 && n <= 28) bonus += 4;
      const poolSupport = data.generator_pool.slice(0, 60).filter(c => Array.isArray(c.numbers) && c.numbers.includes(n)).length;
      bonus += Math.min(8, poolSupport * 0.9);
      return { ...row, candidate_score: num(row.score) + bonus, driver };
    }).sort((a, b) => num(b.candidate_score) - num(a.candidate_score));
  }

  function buildSuggestions(nums, data, analysis) {
    const weak = analysis.details.slice().sort((a, b) => num(a.score) - num(b.score));
    const candidatePool = rankCandidatePool(nums, data);
    const currentSet = new Set(nums);
    const suggestions = [];

    function addSuggestion(type, remove, add, reason) {
      if (!Number.isFinite(remove) || !Number.isFinite(add) || currentSet.has(add) || remove === add) return;
      const next = nums.map(n => n === remove ? add : n).sort((a, b) => a - b);
      const key = next.join('-');
      if (suggestions.some(s => s.key === key)) return;
      const nextScore = next.reduce((acc, n) => acc + num(data.numberMap.get(n)?.score), 0) / 6;
      suggestions.push({ key, type, remove, add, next, nextScore, reason });
    }

    // 1) Sustitución cruda por score V3 + explicación del experto dominante.
    for (const bad of weak.slice(0, 3)) {
      const good = candidatePool.find(c => num(c.score) > num(bad.score) + 1.5);
      if (good) {
        addSuggestion(
          'Mejora por score V3',
          Number(bad.number),
          Number(good.number),
          `Sustituye ${bad.number} (${fmt(bad.score, 1)}/100, ${esc(bad.winner_component_human)}) por ${good.number} (${fmt(good.score, 1)}/100, ${esc(good.driver)}). ${good.reason || ''}`
        );
      }
    }

    // 2) Alineación con una combinación fuerte del Monte Carlo V3 que comparta estructura.
    const nearest = data.generator_pool
      .filter(c => Array.isArray(c.numbers))
      .map(c => {
        const cNums = c.numbers.map(Number);
        const overlap = cNums.filter(n => currentSet.has(n)).length;
        return { combo: c, nums: cNums, overlap, score: scorePercent(c) };
      })
      .sort((a, b) => (b.overlap * 10 + b.score) - (a.overlap * 10 + a.score))[0];
    if (nearest) {
      const add = nearest.nums.find(n => !currentSet.has(n));
      const remove = weak.find(w => !nearest.nums.includes(Number(w.number)))?.number ?? weak[0]?.number;
      if (Number.isFinite(add) && Number.isFinite(Number(remove))) {
        addSuggestion(
          'Alinear con Monte Carlo V3',
          Number(remove),
          Number(add),
          `La simulación V3 tiene una ruta cercana con ${nearest.overlap}/6 números compartidos y score ${fmt(nearest.score, 1)}/100. Cambiar ${remove} por ${add} acerca tu jugada a ese patrón sin copiarla completa.`
        );
      }
    }

    // 3) Balance estructural usando datos V3, no números fijos.
    const stats = analysis.stats;
    if (stats.pares < 2 || stats.pares > 4 || stats.lows < 2 || stats.lows > 4 || stats.decades < 4 || stats.suma < 105 || stats.suma > 245) {
      const structuralCandidate = candidatePool.find(c => {
        const n = Number(c.number);
        if (stats.pares < 2 && n % 2 === 0) return true;
        if (stats.pares > 4 && n % 2 === 1) return true;
        if (stats.lows < 2 && n <= 28) return true;
        if (stats.lows > 4 && n > 28) return true;
        if (stats.decades < 4 && !nums.some(x => Math.floor((x - 1) / 10) === Math.floor((n - 1) / 10))) return true;
        if (stats.suma < 105 && n > 28) return true;
        if (stats.suma > 245 && n <= 28) return true;
        return false;
      });
      const remove = weak[0]?.number;
      if (structuralCandidate && Number.isFinite(Number(remove))) {
        addSuggestion(
          'Balance estructural',
          Number(remove),
          Number(structuralCandidate.number),
          `Tu combinación está desbalanceada (pares=${stats.pares}, bajos=${stats.lows}, décadas=${stats.decades}, suma=${stats.suma}). ${structuralCandidate.number} ayuda a corregir estructura y tiene soporte V3 de ${fmt(structuralCandidate.score, 1)}/100.`
        );
      }
    }

    return suggestions.slice(0, 3);
  }

  window.evalUserComboUI = async function evalUserComboUIV3() {
    const data = await loadV3(false);
    if (!data) {
      if (typeof originalEvalUserComboUI === 'function') return originalEvalUserComboUI();
      if (typeof showToast === 'function') showToast('⚠️ No hay resultados V3 para evaluar');
      return;
    }
    let nums;
    try {
      nums = getManualNums();
    } catch (err) {
      if (typeof showToast === 'function') showToast(`⚠️ ${err.message}`);
      return;
    }
    const analysis = manualAnalysis(nums, data);
    const suggestions = buildSuggestions(nums, data, analysis);
    const color = analysis.score >= 80 ? 'var(--green)' : analysis.score >= 65 ? 'var(--gold)' : 'var(--purple)';
    const rows = analysis.details.map(row => `<tr>
      <td><b style="color:var(--text)">${esc(row.number)}</b></td>
      <td>${fmt(row.score, 2)}</td>
      <td>${esc(row.winner_component_human || driverLabel(row.winner_component))}</td>
      <td>${esc(row.reason || 'sin explicación')}</td>
    </tr>`).join('');
    const suggestionHtml = suggestions.length ? suggestions.map(s => `<div class="suggestion-card top">
      <div style="font-weight:700;color:var(--teal);margin-bottom:8px;">${esc(s.type)} · ${s.remove} → ${s.add}</div>
      <div class="suggestion-nums">${s.next.map(n => `<div class="suggestion-num">${n}</div>`).join('')}</div>
      <div class="suggestion-strategy">${esc(s.reason)}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">Score estimado nuevo: ${fmt(s.nextScore, 2)}/100</div>
      <button class="btn btn-sm btn-blue" onclick="evalSuggestion([${s.next.join(',')}])">📊 Probar sugerencia</button>
    </div>`).join('') : '<div style="color:var(--muted);">No hay cambios recomendados con mejora clara frente a los datos V3 actuales.</div>';

    const resultEl = document.getElementById('user-result');
    if (!resultEl) return;
    resultEl.innerHTML = `<div class="card" style="margin-top:16px;border-color:${color}70;background:rgba(0,0,0,.2);">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;">Análisis Manual V3 · ${esc(data.game_label || '')}</h2>
        <span class="badge" style="background:rgba(0,0,0,.3);color:${color};border:1px solid ${color};font-size:14px;padding:6px 14px">NET AVG · ${fmt(analysis.score, 2)}/100</span>
      </div>
      <div class="card-body">
        <div class="combo-balls" style="margin-bottom:12px;">${ballHtml(nums, color)}</div>
        <div style="background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:10px;padding:12px;margin-bottom:14px;color:var(--muted);line-height:1.55;font-size:12px;">
          <div style="font-weight:700;color:var(--purple);margin-bottom:8px;">🧬 Lectura V3</div>
          <div>${esc(data.procedure_log || 'Sin procedure_log V3.')}</div>
          <div style="margin-top:8px;">Buffer: <b style="color:var(--text)">${esc(data.historical_forgetting?.recent_buffer_size ?? 'N/A')}</b> · MC: <b style="color:var(--text)">${Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')}</b> · Max net: <b style="color:var(--text)">${fmt(Number(data.max_net_score_found || 0) * 100, 2)}/100</b></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;font-size:13px;color:var(--muted);margin-bottom:14px;background:var(--surface);padding:12px;border-radius:8px;border:1px solid var(--border);">
          <div>Suma: <b style="color:var(--text)">${analysis.stats.suma}</b></div>
          <div>Pares/Imp: <b style="color:var(--text)">${analysis.stats.pares}P/${analysis.stats.impares}I</b></div>
          <div>Bajos/Altos: <b style="color:var(--text)">${analysis.stats.lows}/${analysis.stats.highs}</b></div>
          <div>Décadas: <b style="color:var(--text)">${analysis.stats.decades}/6</b></div>
        </div>
        <div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Score V3</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>${rows}</tbody></table></div>
        <div class="suggestion-panel">
          <div class="suggestion-title">💡 Sugerencias profundas V3</div>
          <div class="suggestions-grid">${suggestionHtml}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:14px;"><button class="btn btn-teal" onclick="saveManualComboUI([${nums.join(',')}])">💾 Guardar combinación</button></div>
      </div>
    </div>`;
  };

  document.addEventListener('DOMContentLoaded', () => loadV3(true));
})();
