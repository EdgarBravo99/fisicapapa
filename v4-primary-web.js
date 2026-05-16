// v4-primary-web.js
// Convierte resultados.json V4 en la fuente principal de toda la web.
(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  const V4_SCORE_KIND = 'v4_deep_stacking_meta_score';
  let v4Results = null;
  let cursor = 0;
  const previousRenderCombosList = window.renderCombosList;

  const LABELS = {
    physical: 'física de esferas',
    temporal: 'inercia temporal',
    entropy: 'estabilidad de entropía',
    fourier: 'micro-ciclos Fourier',
    bayes: 'Bayes por desgaste/frecuencia',
    xgboost: 'XGBoost',
    transformer: 'Transformer Self-Attention',
    graph: 'grafo de co-ocurrencia',
    structural: 'estructura de combinación',
    meta: 'Meta-Stacking V4',
    lstm: 'memoria LSTM',
    markov: 'transición Markov'
  };

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

  function fmt(value, digits = 2) {
    return num(value).toFixed(digits);
  }

  function isV4(data) {
    return Boolean(data && (
      data.model_version === 'V4' ||
      data.v4_score_kind === V4_SCORE_KIND ||
      data.score_kind === V4_SCORE_KIND ||
      data.source === 'local_cruncher_v4_deep_stacking'
    ));
  }

  function scorePercent(item) {
    if (Number.isFinite(Number(item?.score_percent))) return Number(item.score_percent);
    if (Number.isFinite(Number(item?.net_score))) return Number(item.net_score) * 100;
    if (Number.isFinite(Number(item?.confidence))) return Number(item.confidence);
    return 0;
  }

  function comboNumbers(item) {
    return (item?.numbers || item?.nums || item?.combo || []).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
  }

  function driverLabel(key) {
    return LABELS[key] || key || 'modelo V4';
  }

  function normalizeNumberRow(n, row, scoreFromMap) {
    const winner = row?.winner_component || row?.main_driver || row?.driver || row?.winner_component_key;
    return {
      ...(row || {}),
      number: n,
      score: num(row?.score, num(scoreFromMap, 0)),
      winner_component: winner,
      winner_component_human: row?.winner_component_human || row?.main_driver_human || row?.driver_human || driverLabel(winner),
      reason: row?.reason || row?.human_reason || 'Score V4 derivado del meta-modelo Deep Stacking.',
      expert_raw: row?.expert_raw || row?.experts || {}
    };
  }

  function normalizeV4(data) {
    const numberScores = data.number_scores || {};
    const seed = Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : [];
    const byNumber = new Map();

    for (let n = 1; n <= 56; n++) {
      byNumber.set(n, normalizeNumberRow(n, null, numberScores[String(n)]));
    }

    seed.forEach(row => {
      const n = Number(row.number);
      if (!Number.isFinite(n) || n < 1 || n > 56) return;
      byNumber.set(n, normalizeNumberRow(n, row, numberScores[String(n)]));
    });

    const generatorPool = Array.isArray(data.generator_pool) && data.generator_pool.length
      ? data.generator_pool
      : (Array.isArray(data.model_portfolio?.top10) && data.model_portfolio.top10.length
        ? data.model_portfolio.top10
        : (Array.isArray(data.top_combinations) ? data.top_combinations : []));

    const topCombinations = Array.isArray(data.model_portfolio?.top10) && data.model_portfolio.top10.length
      ? data.model_portfolio.top10
      : (Array.isArray(data.top_combinations) ? data.top_combinations : generatorPool.slice(0, 10));

    return {
      ...data,
      model_version: 'V4',
      v4_score_kind: data.v4_score_kind || V4_SCORE_KIND,
      // Compatibilidad intencional para módulos antiguos que esperan este score_kind.
      score_kind: 'optuna_weighted_net_score',
      generator_pool: generatorPool,
      top_combinations: topCombinations,
      manual_suggestion_seed: Array.from(byNumber.values()).sort((a, b) => num(b.score) - num(a.score)),
      numberMap: byNumber,
      expert_weights: data.expert_weights || data.optuna_audit?.best_weights || {},
      walk_forward: data.walk_forward || {},
      game_label: data.game_label || (data.game_mode === 'melate' ? 'Melate' : 'Revancha')
    };
  }

  async function loadV4Primary(force = false) {
    if (v4Results && !force) return v4Results;
    const url = `${RESULTS_URL}?v4=${Date.now()}&r=${Math.random().toString(36).slice(2)}`;
    const res = await fetch(url, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        Pragma: 'no-cache',
        Expires: '0'
      }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const raw = await res.json();
    if (!isV4(raw)) throw new Error('resultados.json no es V4');
    v4Results = normalizeV4(raw);

    window.MELATE_V4_RESULTS = v4Results;
    // Vista compatible para que mapa, evaluador, estadísticas y módulos V3 sigan vivos, pero leyendo V4.
    window.MELATE_V3_RESULTS = v4Results;

    updateBranding(v4Results);
    renderV4PrimaryPanel(v4Results);
    renderV4DashboardTab(v4Results);

    document.dispatchEvent(new CustomEvent('melate:v4-results-loaded', { detail: v4Results }));
    document.dispatchEvent(new CustomEvent('melate:v3-results-loaded', { detail: v4Results }));
    document.dispatchEvent(new CustomEvent('melate:v4-primary-loaded', { detail: v4Results }));
    return v4Results;
  }

  window.loadV4Results = loadV4Primary;
  window.getV4Results = () => v4Results || window.MELATE_V4_RESULTS || null;
  window.loadV3Results = loadV4Primary;
  window.getV3Results = () => v4Results || window.MELATE_V4_RESULTS || window.MELATE_V3_RESULTS || null;
  window.getV3NumberRow = (n) => window.getV3Results()?.numberMap?.get(Number(n)) || null;
  window.refreshV4ResultsNow = () => loadV4Primary(true);
  window.refreshV3ResultsNow = () => loadV4Primary(true);

  function updateBranding(data) {
    const title = document.getElementById('app-title');
    if (title) title.textContent = 'ANALIZADOR PRO V4';
    const subtitle = document.querySelector('.header-text p');
    if (subtitle) subtitle.textContent = 'Deep Stacking · Transformer · Grafo · Búsqueda Exhaustiva';
    const badge = document.getElementById('drawCount');
    const buf = data.historical_forgetting?.recent_buffer_size || data.historical_forgetting?.buffer_size;
    if (badge && buf) badge.textContent = `V4 · ${buf} BUFFER`;
  }

  function ensureV4Tab() {
    if (document.querySelector('[data-target="v4"]')) return document.getElementById('tab-v4');
    const tabs = document.querySelector('.tabs');
    const wrap = document.querySelector('.wrap');
    if (!tabs || !wrap) return null;

    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.target = 'v4';
    tab.style.borderColor = 'rgba(57,208,194,.55)';
    tab.style.color = 'var(--teal)';
    tab.textContent = '🧠 V4 Deep Stacking';
    tabs.appendChild(tab);

    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id = 'tab-v4';
    panel.innerHTML = '<div id="v4-dashboard-root"></div>';
    wrap.appendChild(panel);

    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      panel.classList.add('active');
      renderV4DashboardTab(window.getV4Results?.());
    });
    return panel;
  }

  function renderAuditPills(data) {
    const wf = data.walk_forward || {};
    const forgetting = data.historical_forgetting || {};
    return [
      ['Motor', 'V4 Deep Stacking'],
      ['Búsqueda', data.search_mode || 'exhaustive/model pool'],
      ['Evaluadas', Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')],
      ['Buffer', `${forgetting.recent_buffer_size || forgetting.buffer_size || '?'} sorteos`],
      ['OOS', `${wf.steps || (Array.isArray(wf.rows) ? wf.rows.length : 0)} folds`],
      ['Drift', data.drift_detected ? 'ACTIVO' : 'estable']
    ].map(([label, value]) => `<span style="display:inline-flex;gap:6px;align-items:center;padding:6px 9px;border-radius:6px;border:1px solid rgba(57,208,194,.25);background:rgba(57,208,194,.06);font-size:12px;"><b style="color:var(--teal)">${esc(label)}</b><span style="color:var(--muted)">${esc(value)}</span></span>`).join('');
  }

  function ballHtml(nums, color = 'var(--teal)') {
    return nums.map(n => `<span class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</span>`).join('');
  }

  function comboRoute(item) {
    if (item?.plain_route) return item.plain_route;
    if (Array.isArray(item?.number_explanations)) {
      return item.number_explanations.map(x => `${x.number}: ${x.main_driver_human || driverLabel(x.main_driver)}`).join(' | ');
    }
    return item?.human_explanation || item?.procedure || 'Candidata V4 generada por Deep Stacking.';
  }

  function renderV4PrimaryPanel(data) {
    const body = document.querySelector('#tab-generador .card .card-body');
    if (!body || !data) return;
    let panel = document.getElementById('v4-primary-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'v4-primary-panel';
      panel.style.margin = '0 0 16px 0';
      const combos = document.getElementById('combos-container');
      body.insertBefore(panel, combos || body.firstChild);
    }
    const wf = data.walk_forward || {};
    const maxScore = scorePercent({ net_score: data.max_net_score_found });
    panel.innerHTML = `<div style="background:linear-gradient(135deg, rgba(57,208,194,.16), rgba(188,140,255,.08));border:1px solid rgba(57,208,194,.45);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;">
        <div>
          <div style="color:var(--teal);font-family:var(--cond);font-size:17px;font-weight:800;">🧠 Motor principal V4 · ${esc(data.game_label || '')}</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:900px;">${esc(data.procedure_log || data.meta_stacking_audit?.summary || 'V4 activo: Deep Stacking + Transformer + Grafo + búsqueda exhaustiva.')}</div>
        </div>
        <button class="btn btn-sm btn-teal" id="v4-refresh-btn">↻ Refrescar V4</button>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:10px;">${renderAuditPills(data)}</div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${fmt(maxScore, 2)}</div><div class="stat-lbl">Max score V4</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--green)">${esc(wf.avg_hits ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top6</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(wf.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top10</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--purple)">${esc(data.search_mode || 'V4')}</div><div class="stat-lbl">Modo búsqueda</div></div>
      </div>
    </div>`;
    document.getElementById('v4-refresh-btn')?.addEventListener('click', async () => {
      await loadV4Primary(true);
      if (typeof renderHeatGrid === 'function') renderHeatGrid();
      if (typeof window.renderV3LeftRightIndicator === 'function') window.renderV3LeftRightIndicator();
      if (typeof showToast === 'function') showToast('🧠 V4 recargado desde resultados.json');
    });
  }

  function renderV4DashboardTab(data) {
    ensureV4Tab();
    const root = document.getElementById('v4-dashboard-root');
    if (!root || !data) return;
    const portfolio = data.model_portfolio?.top10 || data.top_combinations || [];
    const decades = data.best_numbers_by_decade || [];
    const wfRows = Array.isArray(data.walk_forward?.rows) ? data.walk_forward.rows.slice(-12).reverse() : [];

    root.innerHTML = `
      <div class="card" style="border-color:var(--teal)">
        <div class="card-header"><h2>🧠 V4 Deep Stacking · Resultados principales</h2></div>
        <div class="card-body" style="display:grid;gap:14px;">
          <div style="display:flex;gap:8px;flex-wrap:wrap;">${renderAuditPills(data)}</div>
          <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(150px,1fr));">
            <div class="stat-card"><div class="stat-val" style="font-size:21px;color:var(--teal)">${fmt(scorePercent({ net_score: data.max_net_score_found }), 2)}</div><div class="stat-lbl">Mejor score neto</div></div>
            <div class="stat-card"><div class="stat-val" style="font-size:21px;color:var(--green)">${Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')}</div><div class="stat-lbl">Espacio evaluado</div></div>
            <div class="stat-card"><div class="stat-val" style="font-size:21px;color:var(--gold)">${esc(data.walk_forward?.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">Walk-forward Top10</div></div>
            <div class="stat-card"><div class="stat-val" style="font-size:21px;color:${data.drift_detected ? 'var(--red)' : 'var(--teal)'}">${data.drift_detected ? 'CAOS' : 'OK'}</div><div class="stat-lbl">Drift</div></div>
          </div>
        </div>
      </div>

      <div class="card" style="border-color:rgba(57,208,194,.45);margin-top:18px;">
        <div class="card-header"><h2>🎯 Portafolio Top 10 V4</h2></div>
        <div class="card-body" style="display:grid;gap:10px;">
          ${portfolio.slice(0, 10).map((item, idx) => {
            const nums = comboNumbers(item);
            const color = idx < 3 ? 'var(--teal)' : idx < 6 ? 'var(--gold)' : 'var(--purple)';
            return `<div class="combo-card" style="border-color:${color}70">
              <div class="combo-card-header"><b style="color:${color}">#${idx + 1} · V4 Deep Stacking</b><span style="color:${color};font-family:var(--mono)">${fmt(scorePercent(item), 2)}/100</span></div>
              <div class="combo-balls">${ballHtml(nums, color)}</div>
              <div style="font-size:12px;color:var(--muted);margin-top:8px;line-height:1.55;">${esc(item.human_explanation || item.portfolio_reason || item.procedure || '')}</div>
              <div style="font-size:11px;color:var(--dim);margin-top:6px;">${esc(comboRoute(item))}</div>
            </div>`;
          }).join('') || '<div style="color:var(--muted)">Sin portafolio V4 en resultados.json.</div>'}
        </div>
      </div>

      <div class="card" style="border-color:var(--gold);margin-top:18px;">
        <div class="card-header"><h2>🔢 Mejores números por década · V4</h2></div>
        <div class="card-body">
          ${decades.length ? `<div class="tbl-wrap"><table><thead><tr><th>Década</th><th>Número</th><th>Score</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>${decades.map(row => `<tr><td>${esc(row.decade)}</td><td><b style="color:var(--teal)">${esc(row.number)}</b></td><td>${fmt(row.score, 2)}</td><td>${esc(row.main_driver_human || driverLabel(row.main_driver))}</td><td>${esc(row.reason)}</td></tr>`).join('')}</tbody></table></div>` : '<div style="color:var(--muted)">Sin best_numbers_by_decade.</div>'}
        </div>
      </div>

      <div class="card" style="margin-top:18px;">
        <div class="card-header"><h2>🧪 Walk-forward V4 reciente</h2></div>
        <div class="card-body">
          ${wfRows.length ? `<div class="tbl-wrap"><table><thead><tr><th>Sorteo</th><th>Real</th><th>Pred Top6</th><th>Hits</th><th>Top10</th><th>MSE</th></tr></thead><tbody>${wfRows.map(r => `<tr><td>${esc(r.draw_id)}</td><td>${esc((r.actual || []).join(' '))}</td><td>${esc((r.predicted_top6 || []).join(' '))}</td><td>${esc(r.hits)}</td><td>${esc(r.hits_top10 ?? '')}</td><td>${esc(r.mse ?? '')}</td></tr>`).join('')}</tbody></table></div>` : '<div style="color:var(--muted)">Sin filas walk_forward.</div>'}
        </div>
      </div>

      <div class="card" style="border-color:rgba(188,140,255,.45);margin-top:18px;">
        <div class="card-header"><h2>🧾 Auditoría V4</h2></div>
        <div class="card-body"><pre style="white-space:pre-wrap;color:var(--muted);font-size:12px;line-height:1.55;background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:8px;padding:12px;">${esc(data.hindsight_log || data.meta_stacking_audit?.summary || data.procedure_log || 'Sin auditoría.')}</pre></div>
      </div>
    `;
  }

  function normalizeGeneratedCombo(item) {
    const sp = scorePercent(item);
    return {
      nums: comboNumbers(item),
      name: `V4 ${item?.game_label || v4Results?.game_label || 'Deep Stacking'} · ${sp.toFixed(2)}/100`,
      confidence: sp,
      procedure: item?.human_explanation || item?.portfolio_reason || item?.procedure || item?.plain_route || 'Generado por local_cruncher_v4_deep_stacking.py',
      source: 'deep_stacking_v4',
      metrics: item || {}
    };
  }

  function takeV4Combos(count) {
    const data = window.getV4Results();
    const pool = data?.model_portfolio?.top10?.length ? data.model_portfolio.top10 : data?.generator_pool || [];
    const out = [];
    if (!pool.length) return out;
    for (let i = 0; i < count; i++) {
      out.push(normalizeGeneratedCombo(pool[cursor % pool.length]));
      cursor += 1;
    }
    return out;
  }

  window.generateCombos = async function generateCombosV4(count) {
    const data = await loadV4Primary(true);
    if (!data) return;
    const combos = takeV4Combos(count);
    if (!combos.length) {
      if (typeof showToast === 'function') showToast('⚠️ resultados.json V4 no trae combinaciones');
      return;
    }
    try {
      generatedCombos.unshift(...combos);
      window.renderCombosList();
    } catch (err) {
      renderV4TopIntoGenerator(data);
    }
    if (typeof showToast === 'function') showToast(`🧠 ${combos.length} combinaciones V4 cargadas`);
  };

  window.renderCombosList = function renderCombosListV4Primary() {
    const container = document.getElementById('combos-container');
    if (!container) return;
    let list = [];
    try { list = generatedCombos || []; } catch (_) { list = []; }
    const hasV4 = list.some(c => c.source === 'deep_stacking_v4');
    if (!hasV4) {
      if (typeof previousRenderCombosList === 'function') return previousRenderCombosList();
      return;
    }
    container.innerHTML = list.map((cb, i) => {
      if (cb.source !== 'deep_stacking_v4') return '';
      const nums = cb.nums || [];
      const pares = nums.filter(n => n % 2 === 0).length;
      const suma = nums.reduce((a, b) => a + b, 0);
      const decades = new Set(nums.map(n => Math.floor((n - 1) / 10))).size;
      const score = num(cb.confidence);
      const color = score >= 80 ? 'var(--green)' : score >= 65 ? 'var(--gold)' : 'var(--teal)';
      const route = comboRoute(cb.metrics);
      const savedLabel = typeof isComboSaved === 'function' && isComboSaved(nums) ? 'Guardado' : 'Guardar';
      const savedDisabled = savedLabel === 'Guardado' ? 'disabled' : '';
      return `<div class="combo-card" style="border-color:${color}70">
        <div class="combo-card-header"><span style="color:${color};font-weight:700">#${list.length - i} · ${esc(cb.name)}</span><span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">V4 SCORE: ${score.toFixed(2)}</span></div>
        <div class="combo-balls">${ballHtml(nums, color)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;">Suma: ${suma} | P/I: ${pares}P/${6 - pares}I | Décadas: ${decades}</div>
        <div style="margin-top:10px;background:rgba(57,208,194,.08);border:1px solid rgba(57,208,194,.35);border-radius:8px;padding:10px;font-size:12px;color:var(--muted);line-height:1.55;"><div style="color:var(--teal);font-weight:700;margin-bottom:6px;">🧠 Explicación V4</div><div>${esc(cb.procedure)}</div><div style="margin-top:8px;color:var(--dim);">${esc(route)}</div></div>
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;"><button class="btn btn-sm btn-blue" onclick="window.evalV4GeneratedCombo(${i})">📊 Explicar</button><button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button></div>
      </div>`;
    }).join('');
    if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
  };

  window.evalV4GeneratedCombo = function evalV4GeneratedCombo(index) {
    let item;
    try { item = generatedCombos[index]; } catch (_) { item = null; }
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
    return { pares, impares: 6 - pares, lows, highs: 6 - lows, decades, suma };
  }

  function buildManualSuggestions(nums, data, details) {
    const current = new Set(nums);
    const weak = details.slice().sort((a, b) => num(a.score) - num(b.score));
    const poolSupport = new Map();
    (data.generator_pool || []).slice(0, 120).forEach(c => comboNumbers(c).forEach(n => poolSupport.set(n, (poolSupport.get(n) || 0) + 1)));
    const candidates = data.manual_suggestion_seed
      .filter(row => !current.has(Number(row.number)))
      .map(row => ({ ...row, support: poolSupport.get(Number(row.number)) || 0, candidate_score: num(row.score) + Math.min(10, (poolSupport.get(Number(row.number)) || 0) * 0.7) }))
      .sort((a, b) => num(b.candidate_score) - num(a.candidate_score));
    const suggestions = [];
    for (const bad of weak.slice(0, 3)) {
      const good = candidates.find(c => num(c.score) > num(bad.score) + 1 || c.support > 0);
      if (!good) continue;
      const next = nums.map(n => n === Number(bad.number) ? Number(good.number) : n).sort((a, b) => a - b);
      const key = next.join('-');
      if (suggestions.some(s => s.key === key)) continue;
      suggestions.push({ key, remove: Number(bad.number), add: Number(good.number), next, nextScore: next.reduce((a, n) => a + num(data.numberMap.get(n)?.score), 0) / 6, reason: `Cambiar ${bad.number} por ${good.number}: ${good.number} tiene score V4 ${fmt(good.score, 1)}/100 y aparece ${good.support} veces en el pool élite.` });
    }
    return suggestions.slice(0, 3);
  }

  window.evalUserComboUI = async function evalUserComboUIV4() {
    const data = await loadV4Primary(false);
    let nums;
    try { nums = getManualNums(); } catch (err) { if (typeof showToast === 'function') showToast(`⚠️ ${err.message}`); return; }
    const details = nums.map(n => data.numberMap.get(n) || normalizeNumberRow(n, null, 0));
    const avgScore = details.reduce((a, r) => a + num(r.score), 0) / 6;
    const stats = comboStats(nums);
    const suggestions = buildManualSuggestions(nums, data, details);
    const color = avgScore >= 80 ? 'var(--green)' : avgScore >= 65 ? 'var(--gold)' : 'var(--teal)';
    const rows = details.map(row => `<tr><td><b>${esc(row.number)}</b></td><td>${fmt(row.score, 2)}</td><td>${esc(row.winner_component_human || driverLabel(row.winner_component))}</td><td>${esc(row.reason)}</td></tr>`).join('');
    const sugHtml = suggestions.length ? suggestions.map(s => `<div class="suggestion-card top"><b>V4 sugiere:</b> cambiar <b>${s.remove}</b> por <b style="color:var(--teal)">${s.add}</b><br><span style="color:var(--muted)">${esc(s.reason)}</span><br><span style="font-family:var(--mono);color:var(--gold)">${s.next.join(' - ')} · score estimado ${fmt(s.nextScore, 2)}</span></div>`).join('') : '<div style="color:var(--muted);font-size:12px;">Sin cambios obvios: la combinación está alineada con V4 o faltan candidatos superiores claros.</div>';
    const target = document.getElementById('user-result');
    if (!target) return;
    target.innerHTML = `<div style="margin-top:16px;border:1px solid ${color};border-radius:10px;padding:14px;background:rgba(57,208,194,.06);"><div style="display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;"><div><div style="color:${color};font-weight:800;font-size:16px;">Evaluación Manual V4</div><div style="color:var(--muted);font-size:12px;">Deep Stacking analiza score por número, estructura y soporte del pool exhaustivo.</div></div><div style="font-family:var(--mono);font-size:22px;color:${color};font-weight:800;">${fmt(avgScore, 2)}/100</div></div><div style="margin-top:8px;color:var(--muted);font-size:12px;">Suma=${stats.suma} · Pares=${stats.pares} · Bajos=${stats.lows} · Décadas=${stats.decades}</div><div class="tbl-wrap" style="margin-top:12px;"><table><thead><tr><th>#</th><th>Score V4</th><th>Impulsor</th><th>Lectura</th></tr></thead><tbody>${rows}</tbody></table></div><div style="margin-top:12px;display:grid;gap:8px;">${sugHtml}</div></div>`;
  };

  function renderV4TopIntoGenerator(data) {
    const container = document.getElementById('combos-container');
    if (!container) return;
    const items = data.model_portfolio?.top10 || data.top_combinations || data.generator_pool || [];
    container.innerHTML = items.slice(0, 10).map((item, i) => `<div class="combo-card"><div class="combo-card-header"><b style="color:var(--teal)">#${i + 1} · V4</b><span style="color:var(--teal);font-family:var(--mono)">${fmt(scorePercent(item), 2)}/100</span></div><div class="combo-balls">${ballHtml(comboNumbers(item), 'var(--teal)')}</div><div style="font-size:12px;color:var(--muted);margin-top:8px;">${esc(comboRoute(item))}</div></div>`).join('');
  }

  async function boot() {
    try {
      const data = await loadV4Primary(true);
      const tab = document.querySelector('[data-target="v4"]');
      if (tab) tab.title = 'Fuente principal activa: resultados.json V4';
      console.info('[V4] Web usando resultados V4 como fuente principal', data.last_update || data.historical_forgetting?.buffer_last_draw);
    } catch (err) {
      console.warn('[V4] No se pudo activar V4 como fuente principal:', err);
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(boot, 250));
  window.addEventListener('focus', () => loadV4Primary(true).catch(() => null));
})();
