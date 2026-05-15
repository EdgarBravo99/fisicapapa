// ═══════════════════════════════════════════════════════
// python-results-bridge.js
// Capa segura: solo modifica el apartado Generador/Evaluador Manual.
// No toca historial, mapa de calor, física de esferas, estadísticas ni laboratorio.
// Consume resultados.json producido por local_cruncher.py.
// ═══════════════════════════════════════════════════════

(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  const PY_THRESHOLD = 70;
  let pythonResults = null;
  let pythonPoolCursor = 0;

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fmt(value, digits = 1) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(digits) : '0.0';
  }

  function asPct(value) {
    return `${fmt(value, 1)}%`;
  }

  function normalizeCombo(item, fallbackName = 'Python GPU') {
    const nums = Array.isArray(item?.numbers) ? item.numbers.map(Number).sort((a, b) => a - b) : [];
    return {
      nums,
      name: `${fallbackName} · ${asPct(item?.confidence)}`,
      confidence: Number(item?.confidence || 0),
      procedure: item?.procedure || pythonResults?.procedure_log || 'Generado por local_cruncher.py.',
      source: item?.source || 'python_gpu_montecarlo',
      metrics: item || {}
    };
  }

  async function loadPythonResults(force = false) {
    if (pythonResults && !force) return pythonResults;
    try {
      const response = await fetch(`${RESULTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      const generatorPool = Array.isArray(data.generator_pool) && data.generator_pool.length
        ? data.generator_pool
        : Array.isArray(data.top_combinations)
          ? data.top_combinations
          : [];
      pythonResults = {
        ...data,
        generator_pool: generatorPool,
        manual_suggestion_seed: Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : [],
        top_combinations: Array.isArray(data.top_combinations) ? data.top_combinations : [],
        walk_forward: data.walk_forward || {}
      };
      renderPythonStatusBadge();
      renderWalkForwardPanel();
      return pythonResults;
    } catch (error) {
      console.warn('No se pudo cargar resultados.json:', error);
      pythonResults = null;
      renderPythonStatusBadge(error.message);
      renderWalkForwardPanel(error.message);
      return null;
    }
  }

  function ensureWalkForwardPanel() {
    const generatorPanel = document.querySelector('#tab-generador .card .card-body');
    if (!generatorPanel) return null;
    let panel = document.getElementById('python-walkforward-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'python-walkforward-panel';
      panel.style.margin = '0 0 16px 0';
      const combos = document.getElementById('combos-container');
      if (combos) generatorPanel.insertBefore(panel, combos);
      else generatorPanel.appendChild(panel);
    }
    return panel;
  }

  function renderWalkForwardPanel(errorMsg = '') {
    const panel = ensureWalkForwardPanel();
    if (!panel) return;
    if (!pythonResults) {
      panel.innerHTML = `<div style="background:rgba(248,81,73,.08);border:1px solid rgba(248,81,73,.35);border-radius:10px;padding:12px;color:var(--muted);font-size:12px;">
        <div style="color:var(--red);font-weight:700;margin-bottom:4px;">⚠ Motor Python no sincronizado</div>
        <div>No se pudo leer <code>resultados.json</code>${errorMsg ? `: ${esc(errorMsg)}` : ''}. El generador JS queda como respaldo.</div>
      </div>`;
      return;
    }

    const wf = pythonResults.walk_forward || {};
    const rows = Array.isArray(wf.rows) ? wf.rows : [];
    const lastRows = rows.slice(-5).reverse();
    const confidenceKind = pythonResults.confidence_kind || 'operational_score';
    const target = pythonResults.target_operational_confidence || 80;
    const mc = Number(pythonResults.total_mc_evaluated || 0).toLocaleString('es-MX');
    const maxConf = Number(pythonResults.max_confidence_found || 0);
    const drift = Boolean(pythonResults.drift_detected);
    const wfFactor = wf.walk_forward_factor ?? 'N/A';

    const recentTable = lastRows.length ? `<div class="tbl-wrap" style="margin-top:10px;max-height:180px;overflow:auto;">
      <table>
        <thead><tr><th>Sorteo</th><th>Hits Top6</th><th>Hits Top10</th><th>MSE</th><th>KL</th></tr></thead>
        <tbody>${lastRows.map(row => `<tr>
          <td>${esc(row.draw_id ?? '-')}</td>
          <td>${esc(row.hits ?? '-')}</td>
          <td>${esc(row.hits_top10 ?? '-')}</td>
          <td>${esc(row.mse ?? '-')}</td>
          <td>${esc(row.kl ?? '-')}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>` : '<div style="color:var(--muted);font-size:12px;margin-top:8px;">Sin filas Walk-Forward en resultados.json.</div>';

    panel.innerHTML = `<div style="background:linear-gradient(135deg, rgba(57,208,194,.12), rgba(240,180,41,.08));border:1px solid rgba(57,208,194,.35);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;align-items:flex-start;gap:12px;flex-wrap:wrap;">
        <div>
          <div style="color:var(--teal);font-family:var(--cond);font-size:16px;font-weight:700;">🧠 Motor Walk-Forward Python</div>
          <div style="color:var(--muted);font-size:12px;line-height:1.45;max-width:760px;">${esc(pythonResults.procedure_log || 'Sin procedure_log.')}<br><b>Tipo de confianza:</b> ${esc(confidenceKind)}. No representa probabilidad real de ganar; es score operativo con datos crudos.</div>
        </div>
        <button class="btn btn-sm btn-teal" id="refresh-python-results-btn">↻ Refrescar Python</button>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(130px,1fr));margin-top:12px;">
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:${maxConf >= target ? 'var(--green)' : 'var(--gold)'}">${asPct(maxConf)}</div><div class="stat-lbl">Max confianza</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${mc}</div><div class="stat-lbl">MC evaluadas</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--blue)">${esc(wf.avg_hits ?? 'N/A')}</div><div class="stat-lbl">WF avg hits</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--purple)">${esc(wf.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">WF Top10</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:${drift ? 'var(--red)' : 'var(--green)'}">${drift ? 'CAOS' : 'OK'}</div><div class="stat-lbl">Drift</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(wfFactor)}</div><div class="stat-lbl">WF factor</div></div>
      </div>
      ${recentTable}
    </div>`;

    const refreshBtn = document.getElementById('refresh-python-results-btn');
    if (refreshBtn) refreshBtn.addEventListener('click', async () => {
      await loadPythonResults(true);
      showToast('🔄 resultados.json recargado');
    });
  }

  function renderPythonStatusBadge(errorMsg = '') {
    const info = document.getElementById('combo-info');
    if (!info) return;
    if (!pythonResults) {
      info.textContent = errorMsg ? `Sin resultados Python (${errorMsg})` : 'Sin resultados Python';
      return;
    }
    const wf = pythonResults.walk_forward || {};
    const poolCount = pythonResults.generator_pool?.length || 0;
    const mc = Number(pythonResults.total_mc_evaluated || 0).toLocaleString('es-MX');
    info.textContent = `Python pool: ${poolCount} · MC: ${mc} · WF hits: ${wf.avg_hits ?? 'N/A'} · Max: ${asPct(pythonResults.max_confidence_found)}`;
  }

  function takePythonCombos(count) {
    const data = pythonResults;
    if (!data || !data.generator_pool || !data.generator_pool.length) return [];
    const pool = data.generator_pool;
    const out = [];
    for (let i = 0; i < count; i++) {
      const item = pool[pythonPoolCursor % pool.length];
      pythonPoolCursor += 1;
      out.push(normalizeCombo(item, 'Python GPU'));
    }
    return out;
  }

  function ballHtml(nums) {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,0.05);border:2px solid var(--teal);color:var(--teal)">${esc(n)}</div>`).join('');
  }

  function renderProcedureBlock(item) {
    const metrics = item.metrics || {};
    return `<div style="margin-top:10px;background:rgba(57,208,194,0.08);border:1px solid rgba(57,208,194,0.35);border-radius:8px;padding:10px;font-size:12px;color:var(--muted);line-height:1.55;">
      <div style="color:var(--teal);font-weight:700;margin-bottom:6px;">🧠 Procedimiento Python</div>
      <div>${esc(item.procedure)}</div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:6px;margin-top:8px;">
        <span>Conf: <b style="color:var(--text)">${asPct(metrics.confidence)}</b></span>
        <span>Raw: <b style="color:var(--text)">${fmt(metrics.raw_quality, 2)}</b></span>
        <span>Percentil: <b style="color:var(--text)">${fmt(metrics.rank_percentile, 2)}</b></span>
        <span>Consenso: <b style="color:var(--text)">${fmt(metrics.consensus_score, 2)}</b></span>
        <span>XGB: <b style="color:var(--text)">${fmt(metrics.xgboost_contrast_mean, 3)}</b></span>
        <span>Bayes: <b style="color:var(--text)">${fmt(metrics.bayes_mean, 3)}</b></span>
        <span>Fourier: <b style="color:var(--text)">${fmt(metrics.fourier_mean, 3)}</b></span>
        <span>Estructura: <b style="color:var(--text)">${fmt(metrics.structure_mean, 3)}</b></span>
      </div>
    </div>`;
  }

  window.renderCombosList = function renderCombosListPythonAware() {
    const container = document.getElementById('combos-container');
    if (!container) return;

    if (!generatedCombos.length) {
      container.innerHTML = '';
      renderPythonStatusBadge();
      renderFavoritesPanel();
      return;
    }

    container.innerHTML = generatedCombos.map((cb, i) => {
      const isPython = cb.source === 'python_gpu_montecarlo' || cb.procedure;
      if (!isPython) {
        const ev = evalCombo(cb.nums);
        const color = ev.total_score >= 72 ? 'var(--green)' : ev.total_score >= 55 ? 'var(--gold)' : 'var(--blue)';
        const balls = cb.nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,0.05);border:2px solid ${color};color:${color}">${n}</div>`).join('');
        const savedLabel = isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
        const savedDisabled = isComboSaved(cb.nums) ? 'disabled' : '';
        return `<div class="combo-card" style="border-color:${color}40">
          <div class="combo-card-header">
            <span style="color:${color};font-weight:700">#${generatedCombos.length - i} · ${esc(cb.name)}</span>
            <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">SCORE: ${Math.round(ev.total_score)}</span>
          </div>
          <div class="combo-balls">${balls}</div>
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-top:10px;">
            <div style="font-size:12px;color:var(--muted)">Suma: ${ev.suma} | P/I: ${ev.pares}P/${ev.impares}I | Décadas: ${ev.decades}</div>
            <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
          </div>
        </div>`;
      }

      const confidence = Number(cb.confidence || 0);
      const color = confidence >= 80 ? 'var(--green)' : confidence >= PY_THRESHOLD ? 'var(--gold)' : 'var(--blue)';
      const ev = evalCombo(cb.nums);
      const savedLabel = isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
      const savedDisabled = isComboSaved(cb.nums) ? 'disabled' : '';
      return `<div class="combo-card" style="border-color:${color}60">
        <div class="combo-card-header">
          <span style="color:${color};font-weight:700">#${generatedCombos.length - i} · ${esc(cb.name)}</span>
          <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">PY CONF: ${asPct(confidence)}</span>
        </div>
        <div class="combo-balls">${ballHtml(cb.nums)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;">Suma: ${ev.suma} | P/I: ${ev.pares}P/${ev.impares}I | Décadas: ${ev.decades}</div>
        ${renderProcedureBlock(cb)}
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;">
          <button class="btn btn-sm btn-blue" onclick="window.evalPythonComboFromGenerated(${i})">📊 Explicar</button>
          <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
        </div>
      </div>`;
    }).join('');

    const info = document.getElementById('combo-info');
    if (info) info.textContent = `${generatedCombos.length} jugadas · alimentado por ${pythonResults ? 'Python' : 'JS local'}`;
    renderFavoritesPanel();
  };

  window.evalPythonComboFromGenerated = function evalPythonComboFromGenerated(index) {
    const item = generatedCombos[index];
    if (!item) return;
    item.nums.forEach((n, i) => {
      const input = document.getElementById(`u${i + 1}`);
      if (input) input.value = n;
    });
    evalUserComboUI();
  };

  const originalGenerateCombos = window.generateCombos;
  window.generateCombos = async function generateCombosPythonFed(count) {
    await loadPythonResults(true);
    const pythonCombos = takePythonCombos(count);
    if (pythonCombos.length) {
      generatedCombos.unshift(...pythonCombos);
      renderCombosList();
      showToast(`🤖 ${pythonCombos.length} combinaciones surtidas desde local_cruncher.py`);
      return;
    }
    if (typeof originalGenerateCombos === 'function') {
      showToast('⚠️ Sin resultados.json; usando generador JS de respaldo');
      return originalGenerateCombos(count);
    }
  };

  function getManualNums() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`).value, 10));
    if (nums.some(n => Number.isNaN(n) || n < 1 || n > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(nums).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return nums.sort((a, b) => a - b);
  }

  function scoreManualAgainstPython(nums) {
    const seed = pythonResults?.manual_suggestion_seed || [];
    const map = new Map(seed.map((item, idx) => [Number(item.number), { ...item, rank: idx + 1 }]));
    let acc = 0;
    const details = nums.map(n => {
      const row = map.get(n);
      if (!row) return { number: n, score: 0, rank: null, component: 'Fuera del pool Python' };
      const score = Number(row.score || 0);
      acc += score;
      return { number: n, score, rank: row.rank, component: row.winner_component || 'Ensemble' };
    });
    return { score: acc / 6, details, seed };
  }

  function buildPythonSuggestions(nums, analysis) {
    const current = new Set(nums);
    const weak = analysis.details.slice().sort((a, b) => a.score - b.score).slice(0, 2);
    const replacements = analysis.seed.filter(item => !current.has(Number(item.number))).slice(0, 8);
    return weak.map((bad, idx) => {
      const repl = replacements[idx];
      if (!repl) return null;
      const next = nums.map(n => n === bad.number ? Number(repl.number) : n).sort((a, b) => a - b);
      return {
        remove: bad.number,
        add: Number(repl.number),
        next,
        reason: `Python sugiere sustituir ${bad.number} (${fmt(bad.score, 1)}) por ${repl.number} (${fmt(repl.score, 1)}), componente dominante: ${repl.winner_component}.`
      };
    }).filter(Boolean);
  }

  const originalEvalUserComboUI = window.evalUserComboUI;
  window.evalUserComboUI = async function evalUserComboUIPythonAware() {
    await loadPythonResults(true);
    if (!pythonResults) {
      if (typeof originalEvalUserComboUI === 'function') return originalEvalUserComboUI();
      return;
    }

    let nums;
    try {
      nums = getManualNums();
    } catch (error) {
      showToast(`⚠️ ${error.message}`);
      return;
    }

    const ev = evalCombo(nums);
    const analysis = scoreManualAgainstPython(nums);
    const suggestions = buildPythonSuggestions(nums, analysis);
    const confidence = Math.max(0, Math.min(100, analysis.score));
    const color = confidence >= 80 ? 'var(--green)' : confidence >= 60 ? 'var(--gold)' : 'var(--red)';

    const detailRows = analysis.details.map(d => `<tr>
      <td><b style="color:var(--text);font-size:14px">${d.number}</b></td>
      <td>${d.rank ? `#${d.rank}` : 'N/A'}</td>
      <td>${fmt(d.score, 2)}</td>
      <td>${esc(d.component)}</td>
    </tr>`).join('');

    const suggestionHtml = suggestions.length ? suggestions.map(s => `<div class="suggestion-card top">
      <div style="font-weight:700;color:var(--teal);margin-bottom:8px;">Cambiar ${s.remove} → ${s.add}</div>
      <div class="suggestion-nums">${s.next.map(n => `<div class="suggestion-num">${n}</div>`).join('')}</div>
      <div class="suggestion-strategy">${esc(s.reason)}</div>
      <button class="btn btn-sm btn-blue" onclick="evalSuggestion([${s.next.join(',')}])">📊 Probar sugerencia</button>
    </div>`).join('') : '<div style="color:var(--muted);">La combinación está alineada con el pool Python actual.</div>';

    document.getElementById('user-result').innerHTML = `<div class="card" style="margin-top:16px;border-color:${color}60;background:rgba(0,0,0,0.2);">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;">Análisis Python (${CURRENT_MODE.toUpperCase()})</h2>
        <span class="badge" style="background:rgba(0,0,0,.3);color:${color};border:1px solid ${color};font-size:14px;padding:6px 14px">PY SCORE · ${fmt(confidence, 1)}/100</span>
      </div>
      <div class="card-body">
        <div class="combo-balls" style="margin-bottom:12px;">${ballHtml(nums)}</div>
        <div style="background:rgba(57,208,194,0.08);border:1px solid var(--teal);border-radius:10px;padding:12px;margin-bottom:14px;color:var(--muted);line-height:1.55;">
          <div style="font-weight:700;color:var(--teal);margin-bottom:8px;">🧠 Procedimiento absorbido desde local_cruncher.py</div>
          <div>${esc(pythonResults.procedure_log || 'Sin procedure_log en resultados.json.')}</div>
          <div style="margin-top:8px;">MC evaluado: <b style="color:var(--text)">${Number(pythonResults.total_mc_evaluated || 0).toLocaleString('es-MX')}</b> · Max confianza operativa: <b style="color:var(--text)">${asPct(pythonResults.max_confidence_found)}</b></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;font-size:13px;color:var(--muted);margin-bottom:16px;background:var(--surface);padding:12px;border-radius:8px;border:1px solid var(--border);">
          <div>Suma: <span style="color:var(--text);font-weight:700">${ev.suma}</span></div>
          <div>Pares/Imp: <span style="color:var(--text);font-weight:700">${ev.pares}P/${ev.impares}I</span></div>
          <div>Décadas: <span style="color:var(--text);font-weight:700">${ev.decades}/6</span></div>
          <div>Consecutivos: <span style="color:var(--text);font-weight:700">${ev.consec}</span></div>
        </div>
        <div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Rank Python</th><th>Score Python</th><th>Componente dominante</th></tr></thead><tbody>${detailRows}</tbody></table></div>
        <div class="suggestion-panel">
          <div class="suggestion-title">💡 Sugerencias Python para combinación manual</div>
          <div class="suggestions-grid">${suggestionHtml}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:14px;"><button class="btn btn-teal" onclick="saveManualComboUI([${nums.join(',')}])">💾 Guardar combinación</button></div>
      </div>
    </div>`;
  };

  document.addEventListener('DOMContentLoaded', () => {
    loadPythonResults(true);
  });
})();
