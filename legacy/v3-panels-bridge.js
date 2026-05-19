// v3-panels-bridge.js
// Última capa V3: alimenta Mapa, Estadísticas, Forense, Coincidencias y Física desde resultados.json.
// No modifica ni persiste pesos de bolas; solo muestra lectura V3.
(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  let cache = null;

  const originalRenderHeatGrid = window.renderHeatGrid;
  const originalRenderStatsUI = window.renderStatsUI;
  const originalRenderPatternShiftUI = window.renderPatternShiftUI;
  const originalAnalyzeRhythmsUI = window.analyzeRhythmsUI;
  const originalAnalyzeForensicsUI = window.analyzeForensicsUI;
  const originalRenderConditionalPatternsUI = window.renderConditionalPatternsUI;
  const originalSearchCoincidencesUI = window.searchCoincidencesUI;
  const originalRenderTopPairsUI = window.renderTopPairsUI;
  const originalRenderWeightsGrid = window.renderWeightsGrid;

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

  function currentView() {
    try {
      // currentMapView es let global de ui.js; no vive en window.
      return typeof currentMapView !== 'undefined' ? currentMapView : 'score';
    } catch (_) {
      return 'score';
    }
  }

  function driverLabel(key) {
    return ({
      physical: 'física de esferas',
      temporal: 'inercia temporal',
      entropy: 'estabilidad de entropía',
      fourier: 'micro-ciclos Fourier',
      bayes: 'Bayes desgaste/frecuencia',
      xgboost: 'XGBoost',
      lstm: 'memoria LSTM',
      markov: 'transición Markov',
      structural: 'estructura'
    })[key] || key || 'V3';
  }

  function colorForScore(score) {
    if (score >= 82) return 'var(--green)';
    if (score >= 65) return 'var(--gold)';
    if (score >= 45) return 'var(--blue)';
    return 'var(--red)';
  }

  function bucket(rank) {
    if (rank >= 0.82) return 'h2';
    if (rank >= 0.62) return 'h3';
    if (rank >= 0.38) return 'h1';
    if (rank >= 0.18) return 'h4';
    return 'h0';
  }

  function percentile(values, value) {
    if (!values.length) return 0.5;
    const sorted = [...values].sort((a, b) => a - b);
    let below = 0;
    for (const v of sorted) {
      if (v <= value) below++;
      else break;
    }
    return below / sorted.length;
  }

  async function loadV3(force = false) {
    if (cache && !force) return cache;
    const existing = typeof window.getV3Results === 'function' ? window.getV3Results() : window.MELATE_V3_RESULTS;
    if (existing && existing.score_kind === 'optuna_weighted_net_score' && !force) {
      cache = normalize(existing);
      return cache;
    }
    try {
      const response = await fetch(`${RESULTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      const data = await response.json();
      if (data.score_kind !== 'optuna_weighted_net_score') throw new Error('No es resultados V3');
      cache = normalize(data);
      window.MELATE_V3_RESULTS = cache;
      document.dispatchEvent(new CustomEvent('melate:v3-results-loaded', { detail: cache }));
      return cache;
    } catch (error) {
      console.warn('v3-panels-bridge no pudo cargar resultados.json:', error);
      return null;
    }
  }

  function normalize(data) {
    const map = new Map();
    const scores = data.number_scores || {};
    for (let n = 1; n <= 56; n++) {
      map.set(n, {
        number: n,
        score: num(scores[String(n)], 0),
        winner_component_human: 'V3',
        reason: 'Sin explicación V3 disponible',
        expert_raw: {},
        effective_weight: null,
        physics_bonus: null,
        uses_in_window: 0
      });
    }
    (Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : []).forEach(row => {
      const n = Number(row.number);
      if (!Number.isFinite(n) || n < 1 || n > 56) return;
      const old = map.get(n) || {};
      map.set(n, {
        ...old,
        ...row,
        number: n,
        score: num(row.score, old.score || 0),
        winner_component_human: row.winner_component_human || driverLabel(row.winner_component),
        reason: row.reason || old.reason,
        expert_raw: row.expert_raw || row.experts || old.expert_raw || {}
      });
    });
    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    const top = Array.isArray(data.top_combinations) ? data.top_combinations : [];
    return {
      ...data,
      generator_pool: pool,
      top_combinations: top,
      numberMap: map,
      seed: [...map.values()].sort((a, b) => num(b.score) - num(a.score)),
      expert_weights: data.expert_weights || data.optuna_audit?.best_weights || {},
      walk_forward: data.walk_forward || {},
      physics_summary: data.physics_summary || {}
    };
  }

  function getV3Sync() {
    const existing = cache || (typeof window.getV3Results === 'function' ? window.getV3Results() : window.MELATE_V3_RESULTS);
    if (existing && existing.score_kind === 'optuna_weighted_net_score') {
      cache = existing.numberMap ? existing : normalize(existing);
      return cache;
    }
    return null;
  }

  function comboPoolSupport(data) {
    const support = new Array(57).fill(0);
    data.generator_pool.slice(0, 120).forEach(combo => {
      if (!Array.isArray(combo.numbers)) return;
      combo.numbers.forEach(n => {
        if (n >= 1 && n <= 56) support[n] += 1;
      });
    });
    return support;
  }

  function expertBreakdown(row) {
    const raw = row.expert_raw || row.experts || {};
    const parts = Object.entries(raw)
      .filter(([, v]) => Number.isFinite(Number(v)))
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .slice(0, 4)
      .map(([k, v]) => `${driverLabel(k)} ${fmt(Number(v) * 100, 1)}`);
    return parts.length ? parts.join(' · ') : 'sin desglose experto';
  }

  window.renderHeatGrid = function renderHeatGridV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalRenderHeatGrid === 'function') return originalRenderHeatGrid();
      return;
    }
    const grid = document.getElementById('heat-grid');
    const legend = document.getElementById('heat-legend');
    if (!grid) return;

    const view = currentView();
    const support = comboPoolSupport(data);
    const rows = [];
    for (let n = 1; n <= 56; n++) {
      const row = data.numberMap.get(n) || { number: n, score: 0 };
      rows.push({
        n,
        score: num(row.score),
        support: support[n],
        physics: num(row.physics_bonus, 0),
        driver: row.winner_component_human || driverLabel(row.winner_component),
        reason: row.reason || 'Sin explicación V3 disponible',
        effective: row.effective_weight,
        uses: row.uses_in_window,
        row
      });
    }

    const values = rows.map(row => view === 'freq' ? row.support : view === 'delay' ? row.physics : row.score);
    grid.style.display = 'grid';
    grid.style.gridTemplateColumns = 'repeat(8, minmax(54px, 1fr))';
    grid.style.gap = '6px';
    grid.style.maxWidth = '760px';
    grid.style.minHeight = '420px';

    grid.innerHTML = rows.map(row => {
      const value = view === 'freq' ? row.support : view === 'delay' ? row.physics : row.score;
      const rank = percentile(values, value);
      const cls = bucket(rank);
      const label = view === 'freq'
        ? `${row.support}/120`
        : view === 'delay'
          ? `${fmt(row.physics, 1)} fis`
          : `${fmt(row.score, 1)}`;
      const title = [
        `Número ${row.n}`,
        `Score V3 ${fmt(row.score, 2)}/100`,
        `Pool MC top120 ${row.support}`,
        `Impulsor ${row.driver}`,
        `Motivo ${row.reason}`,
        `Peso efectivo ${row.effective ?? 'N/A'}g`,
        `Bonus físico ${row.physics}`,
        `Usos en buffer ${row.uses ?? 'N/A'}`,
        `Expertos ${expertBreakdown(row.row)}`
      ].join(' | ');
      return `<div class="grid-cell ${cls}" title="${esc(title)}" style="min-height:70px;opacity:1;visibility:visible;">
        <div class="num">${row.n}</div>
        <div class="sc">${esc(label)}</div>
      </div>`;
    }).join('');

    if (legend) {
      const modeText = view === 'freq'
        ? 'Frecuencia V3 = presencia en las mejores 120 combinaciones Monte Carlo'
        : view === 'delay'
          ? 'Vista Física V3 = bonus físico calculado por peso efectivo/desgaste'
          : 'Score V3 = number_scores ponderado por Optuna';
      legend.innerHTML = `
        <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Top V3</span>
        <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Alto</span>
        <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Medio</span>
        <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Bajo</span>
        <span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Último percentil</span>
        <span style="font-size:11px;color:var(--muted);width:100%;margin-top:4px;">${esc(modeText)} · ${esc(data.game_label || '')} · Buffer ${esc(data.historical_forgetting?.recent_buffer_size ?? 'N/A')} · MC ${Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')} · Drift ${data.drift_detected ? 'sí' : 'no'}</span>
      `;
    }
  };

  window.renderStatsUI = function renderStatsUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalRenderStatsUI === 'function') return originalRenderStatsUI();
      return;
    }
    const statsSummary = document.getElementById('stats-summary');
    const decEl = document.getElementById('decade-chart');
    const piEl = document.getElementById('pi-chart');
    const sumEl = document.getElementById('sum-chart');
    const trendEl = document.getElementById('trend-chart');

    const weights = Object.entries(data.expert_weights || {}).sort((a, b) => Number(b[1]) - Number(a[1]));
    const leader = weights[0];
    const topNums = data.seed.slice(0, 6);
    const phys = data.physics_summary || {};
    if (statsSummary) {
      statsSummary.innerHTML = `
        <div class="stat-card" style="border-color:var(--purple);background:rgba(188,140,255,.08);"><div class="stat-val">${fmt(num(data.max_net_score_found) * 100, 2)}</div><div class="stat-lbl">Max net score V3</div></div>
        <div class="stat-card" style="border-color:var(--teal);background:rgba(57,208,194,.08);"><div class="stat-val">${Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')}</div><div class="stat-lbl">Monte Carlo evaluadas</div></div>
        <div class="stat-card" style="border-color:var(--gold);background:rgba(240,180,41,.08);"><div class="stat-val">${esc(data.historical_forgetting?.recent_buffer_size ?? 'N/A')}</div><div class="stat-lbl">Buffer reciente</div></div>
        <div class="stat-card" style="border-color:${data.drift_detected ? 'var(--red)' : 'var(--green)'};background:rgba(255,255,255,.04);"><div class="stat-val" style="color:${data.drift_detected ? 'var(--red)' : 'var(--green)'}">${data.drift_detected ? 'DRIFT' : 'OK'}</div><div class="stat-lbl">Entropía</div></div>
        <div class="stat-card" style="border-color:var(--blue);background:rgba(88,166,255,.08);"><div class="stat-val">${leader ? `${(Number(leader[1]) * 100).toFixed(1)}%` : 'N/A'}</div><div class="stat-lbl">Peso líder · ${leader ? esc(driverLabel(leader[0])) : ''}</div></div>
        <div class="stat-card" style="border-color:var(--teal);background:rgba(57,208,194,.08);"><div class="stat-val">${esc(phys.avg_effective_weight ?? 'N/A')}g</div><div class="stat-lbl">Peso efectivo promedio V3</div></div>
        <div class="stat-card" style="grid-column:1/-1;text-align:left;"><div style="font-size:12px;color:var(--muted);margin-bottom:8px;">Top números V3 por Optuna</div><div style="display:flex;gap:6px;flex-wrap:wrap;">${topNums.map(r => `<span class="ball" style="border:1px solid var(--purple);color:var(--purple);background:rgba(188,140,255,.12);" title="${esc(r.reason)}">${r.number}</span><span style="font-size:11px;color:var(--muted);align-self:center;margin-right:8px;">${fmt(r.score, 1)}</span>`).join('')}</div></div>
      `;
    }

    const decadeScores = new Array(6).fill(0);
    const decadeCounts = new Array(6).fill(0);
    data.seed.forEach(r => {
      const d = Math.floor((Number(r.number) - 1) / 10);
      decadeScores[d] += num(r.score);
      decadeCounts[d] += 1;
    });
    if (decEl) {
      const max = Math.max(...decadeScores.map((s, i) => s / Math.max(1, decadeCounts[i])), 1);
      decEl.innerHTML = decadeScores.map((s, i) => {
        const avg = s / Math.max(1, decadeCounts[i]);
        const lo = i * 10 + 1;
        const hi = i === 5 ? 56 : (i + 1) * 10;
        return `<div class="decade-row"><div class="decade-label">D${i + 1} (${lo}-${hi})</div><div class="decade-bar"><div class="decade-fill" style="width:${(avg / max) * 100}%;background:${colorForScore(avg)}"></div></div><div class="decade-pct">${fmt(avg, 1)}</div></div>`;
      }).join('');
    }

    const parity = [0, 0, 0, 0, 0, 0, 0];
    data.generator_pool.slice(0, 120).forEach(c => {
      if (!Array.isArray(c.numbers)) return;
      const p = c.numbers.filter(n => n % 2 === 0).length;
      parity[p] += 1;
    });
    if (piEl) {
      const maxP = Math.max(...parity, 1);
      piEl.innerHTML = parity.map((cnt, p) => `<div class="decade-row"><div class="decade-label">${p}P/${6 - p}I</div><div class="decade-bar"><div class="decade-fill" style="width:${(cnt / maxP) * 100}%;background:${p === 3 ? 'var(--green)' : p === 2 || p === 4 ? 'var(--gold)' : 'var(--red)'}"></div></div><div class="decade-pct">${cnt}</div></div>`).join('');
    }

    const buckets = [[21,80],[81,120],[121,160],[161,200],[201,240],[241,336]];
    const sumCounts = buckets.map(([lo, hi]) => data.generator_pool.slice(0, 120).filter(c => Array.isArray(c.numbers) && c.numbers.reduce((a, b) => a + b, 0) >= lo && c.numbers.reduce((a, b) => a + b, 0) <= hi).length);
    if (sumEl) {
      const maxS = Math.max(...sumCounts, 1);
      sumEl.innerHTML = buckets.map(([lo, hi], i) => `<div class="decade-row"><div class="decade-label">${lo}-${hi}</div><div class="decade-bar"><div class="decade-fill" style="width:${(sumCounts[i] / maxS) * 100}%;background:${lo >= 121 && hi <= 240 ? 'var(--green)' : 'var(--gold)'}"></div></div><div class="decade-pct">${sumCounts[i]}</div></div>`).join('');
    }

    if (trendEl) {
      const rows = Array.isArray(data.walk_forward?.rows) ? data.walk_forward.rows.slice(-12) : [];
      trendEl.innerHTML = rows.length ? rows.map(row => {
        const hits = num(row.hits);
        const color = hits >= 3 ? 'var(--green)' : hits >= 2 ? 'var(--gold)' : 'var(--red)';
        return `<div style="margin-bottom:10px;"><div style="display:flex;justify-content:space-between;font-size:12px;"><span style="color:var(--muted)">Sorteo ${esc(row.draw_id)}</span><span style="color:${color};font-weight:700">${hits}/6 · Top10 ${esc(row.hits_top10 ?? '-')}</span></div><div class="score-track" style="height:7px;"><div class="score-fill" style="width:${Math.min(100, hits / 6 * 100)}%;background:${color}"></div></div></div>`;
      }).join('') : `<div style="color:var(--muted);font-size:12px;">Sin filas Walk-Forward V3.</div>`;
    }
  };

  window.renderPatternShiftUI = function renderPatternShiftUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalRenderPatternShiftUI === 'function') return originalRenderPatternShiftUI();
      return;
    }
    const container = document.getElementById('pattern-shift-container');
    if (!container) return;
    const audit = data.optuna_audit?.summary || data.procedure_log || 'Sin audit trail V3.';
    const weights = Object.entries(data.expert_weights || {}).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 6);
    container.innerHTML = `<div style="display:grid;gap:12px;">
      <div style="background:rgba(188,140,255,.08);border:1px solid var(--purple);border-radius:10px;padding:14px;"><div style="font-weight:800;color:var(--purple);font-family:var(--cond);font-size:18px;">Régimen V3 · ${esc(data.game_label || '')}</div><div style="font-size:12px;color:var(--muted);line-height:1.55;margin-top:6px;">${esc(audit)}</div></div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px;">${weights.map(([k, v]) => `<div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${(Number(v) * 100).toFixed(1)}%</div><div class="stat-lbl">${esc(driverLabel(k))}</div></div>`).join('')}</div>
    </div>`;
  };

  window.analyzeRhythmsUI = function analyzeRhythmsUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalAnalyzeRhythmsUI === 'function') return originalAnalyzeRhythmsUI();
      return;
    }
    const container = document.getElementById('ritmos-container');
    if (!container) return;
    const lstm = data.seed.filter(r => String(r.winner_component || '').toLowerCase() === 'lstm' || String(r.winner_component_human || '').toLowerCase().includes('lstm')).slice(0, 8);
    const markov = data.seed.filter(r => String(r.winner_component || '').toLowerCase() === 'markov' || String(r.winner_component_human || '').toLowerCase().includes('markov')).slice(0, 8);
    const mixed = [...lstm, ...markov].filter((r, i, arr) => arr.findIndex(x => x.number === r.number) === i).slice(0, 10);
    container.innerHTML = mixed.length ? mixed.map(r => `<div style="background:var(--surface);border:1px solid var(--purple);padding:12px;border-radius:8px;display:flex;align-items:center;gap:12px;margin-bottom:8px;"><div class="ball ball-lg" style="margin:0;border:2px solid var(--purple);color:var(--purple);background:rgba(188,140,255,.1)">${r.number}</div><div><div style="font-family:var(--cond);font-size:16px;font-weight:700;color:var(--text)">${esc(r.winner_component_human || driverLabel(r.winner_component))}</div><div style="font-size:12px;color:var(--muted)">${esc(r.reason || 'Señal secuencial detectada por V3')}</div><div style="font-size:12px;color:var(--gold);font-family:var(--mono);margin-top:4px">Score ${fmt(r.score, 2)}/100</div></div></div>`).join('') : `<p style="color:var(--muted)">V3 no marcó señales LSTM/Markov dominantes en este corte.</p>`;
  };

  window.analyzeForensicsUI = function analyzeForensicsUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalAnalyzeForensicsUI === 'function') return originalAnalyzeForensicsUI();
      return;
    }
    const seqC = document.getElementById('secuencias-container');
    const termC = document.getElementById('terminaciones-container');
    if (seqC) {
      const pairs = {};
      data.generator_pool.slice(0, 120).forEach(c => {
        if (!Array.isArray(c.numbers)) return;
        const nums = [...c.numbers].sort((a, b) => a - b);
        for (let i = 0; i < nums.length - 1; i++) for (let j = i + 1; j < nums.length; j++) {
          const key = `${nums[i]}-${nums[j]}`;
          pairs[key] = (pairs[key] || 0) + 1;
        }
      });
      const topPairs = Object.entries(pairs).sort((a, b) => b[1] - a[1]).slice(0, 18);
      seqC.innerHTML = topPairs.length ? topPairs.map(([pair, count]) => {
        const [a, b] = pair.split('-');
        return `<div class="seq-card"><span class="seq-highlight">${a}</span> + <span class="seq-highlight">${b}</span><span>aparecen juntos en ${count} combinaciones top V3</span></div>`;
      }).join('') : '<p style="color:var(--muted)">Sin pares V3 suficientes.</p>';
    }
    if (termC) {
      const term = new Array(10).fill(0);
      data.seed.slice(0, 56).forEach(r => { term[Number(r.number) % 10] += num(r.score); });
      const max = Math.max(...term, 1);
      termC.innerHTML = term.map((score, i) => `<div style="background:var(--surface);border:1px solid var(--border);padding:10px;border-radius:8px;width:80px;text-align:center;"><div style="font-size:22px;font-weight:800;color:var(--teal)">${i}</div><div style="font-size:10px;color:var(--muted)">${fmt(score / max * 100, 0)}%</div></div>`).join('');
    }
  };

  window.renderConditionalPatternsUI = function renderConditionalPatternsUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalRenderConditionalPatternsUI === 'function') return originalRenderConditionalPatternsUI();
      return;
    }
    const container = document.getElementById('conditional-container');
    if (!container) return;
    const drivers = {};
    data.seed.forEach(r => {
      const d = r.winner_component_human || driverLabel(r.winner_component);
      drivers[d] = drivers[d] || [];
      drivers[d].push(r);
    });
    const structures = {};
    data.generator_pool.slice(0, 120).forEach(c => {
      if (!Array.isArray(c.numbers)) return;
      const key = new Array(6).fill(0);
      c.numbers.forEach(n => key[Math.floor((n - 1) / 10)]++);
      const s = key.join('-');
      structures[s] = (structures[s] || 0) + 1;
    });
    const driverCards = Object.entries(drivers).sort((a, b) => b[1].length - a[1].length).slice(0, 8).map(([driver, rows]) => `<div style="flex:1 1 210px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;"><div style="font-size:13px;color:var(--muted);margin-bottom:6px;">${esc(driver)}</div><div style="display:flex;flex-wrap:wrap;gap:6px;">${rows.slice(0, 6).map(r => `<span style="background:rgba(57,208,194,.12);border:1px solid var(--teal);border-radius:6px;padding:4px 8px;font-size:11px;color:var(--teal);">${r.number} · ${fmt(r.score, 1)}</span>`).join('')}</div></div>`).join('');
    const topStruct = Object.entries(structures).sort((a, b) => b[1] - a[1]).slice(0, 5);
    container.innerHTML = `<div style="display:grid;gap:12px;"><div style="display:flex;gap:12px;flex-wrap:wrap;">${driverCards}</div><div style="background:rgba(240,180,41,.08);border:1px solid var(--gold);border-radius:10px;padding:12px;"><div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Estructuras más comunes en Monte Carlo V3</div>${topStruct.map(([s, c]) => `<div style="display:flex;justify-content:space-between;gap:12px;margin-bottom:6px;"><div style="font-family:var(--mono);font-weight:700;color:var(--text);">${esc(s)}</div><div style="color:var(--gold);font-weight:700;">${c} combos</div></div>`).join('')}</div></div>`;
  };

  window.searchCoincidencesUI = function searchCoincidencesUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalSearchCoincidencesUI === 'function') return originalSearchCoincidencesUI();
      return;
    }
    const inputs = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`coinc-${i}`)?.value, 10)).filter(n => !Number.isNaN(n) && n >= 1 && n <= 56);
    if (inputs.length < 2) { if (typeof showToast === 'function') showToast('⚠️ Ingresa al menos 2 números para buscar'); return; }
    const unique = [...new Set(inputs)];
    const poolMatches = data.generator_pool.filter(c => Array.isArray(c.numbers) && unique.every(n => c.numbers.includes(n))).slice(0, 30);
    const partial = data.generator_pool.filter(c => Array.isArray(c.numbers) && unique.filter(n => c.numbers.includes(n)).length >= Math.max(2, unique.length - 1)).slice(0, 20);
    const resDiv = document.getElementById('coincidencias-resultados');
    if (!resDiv) return;
    const exactHtml = poolMatches.length ? poolMatches.map(c => `<tr><td>${fmt(num(c.score_percent, num(c.net_score) * 100), 2)}</td><td colspan="6">${c.numbers.map(n => `<span class="ball" style="${unique.includes(n) ? 'background:var(--teal);color:#000;' : 'background:rgba(255,255,255,.05);color:var(--muted);'}">${n}</span>`).join('')}</td><td>${esc(c.plain_route || '')}</td></tr>`).join('') : `<tr><td colspan="8" style="color:var(--red);">No aparecen juntos dentro del pool top V3.</td></tr>`;
    const partialHtml = partial.length ? `<div style="margin-top:12px;color:var(--muted);font-size:12px;">Coincidencias parciales fuertes:</div><div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">${partial.slice(0, 8).map(c => `<span style="background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:6px 8px;font-family:var(--mono);font-size:11px;">${c.numbers.join(' ')} · ${fmt(num(c.score_percent, num(c.net_score) * 100), 1)}</span>`).join('')}</div>` : '';
    resDiv.innerHTML = `<p style="color:var(--green);margin-bottom:10px;">V3 encontró <b>${poolMatches.length}</b> coincidencias exactas en el pool Monte Carlo.</p><div class="tbl-wrap"><table><thead><tr><th>Score</th><th colspan="6">Combinación</th><th>Ruta</th></tr></thead><tbody>${exactHtml}</tbody></table></div>${partialHtml}`;
  };

  window.renderTopPairsUI = function renderTopPairsUIV3Final() {
    const data = getV3Sync();
    if (!data) {
      if (typeof originalRenderTopPairsUI === 'function') return originalRenderTopPairsUI();
      return;
    }
    const container = document.getElementById('top-pairs-container');
    if (!container) return;
    const pairs = {};
    data.generator_pool.slice(0, 160).forEach(c => {
      if (!Array.isArray(c.numbers)) return;
      const nums = [...c.numbers].sort((a, b) => a - b);
      for (let i = 0; i < nums.length - 1; i++) for (let j = i + 1; j < nums.length; j++) {
        const key = `${nums[i]}-${nums[j]}`;
        pairs[key] = (pairs[key] || 0) + 1;
      }
    });
    const top = Object.entries(pairs).sort((a, b) => b[1] - a[1]).slice(0, 18);
    container.innerHTML = top.map(([pair, count]) => {
      const [n1, n2] = pair.split('-');
      return `<div style="background:var(--surface);border:1px solid var(--purple);padding:8px 12px;border-radius:6px;display:flex;align-items:center;gap:8px;"><span class="ball ball-warm" style="width:24px;height:24px;font-size:11px">${n1}</span><span class="ball ball-warm" style="width:24px;height:24px;font-size:11px">${n2}</span><span style="color:var(--muted);font-size:11px;margin-left:4px">${count}x en pool V3</span></div>`;
    }).join('');
  };

  window.renderWeightsGrid = function renderWeightsGridV3Final() {
    if (typeof originalRenderWeightsGrid === 'function') originalRenderWeightsGrid();
    const data = getV3Sync();
    const grid = document.getElementById('weights-grid');
    if (!grid || !data) return;
    if (document.getElementById('v3-physics-readonly-panel')) return;
    const phys = data.physics_summary || {};
    const topPhysical = data.seed
      .filter(r => Number.isFinite(Number(r.physics_bonus)))
      .sort((a, b) => num(b.physics_bonus) - num(a.physics_bonus))
      .slice(0, 6);
    const bottomPhysical = data.seed
      .filter(r => Number.isFinite(Number(r.physics_bonus)))
      .sort((a, b) => num(a.physics_bonus) - num(b.physics_bonus))
      .slice(0, 6);
    grid.insertAdjacentHTML('afterbegin', `<div id="v3-physics-readonly-panel" style="grid-column:1/-1;background:rgba(188,140,255,.08);border:1px solid var(--purple);border-radius:10px;padding:14px;margin-bottom:10px;">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;"><div><div style="font-family:var(--cond);font-size:17px;font-weight:800;color:var(--purple);">Lectura física V3 · solo consulta</div><div style="font-size:12px;color:var(--muted);line-height:1.55;">Estos datos vienen de resultados.json y NO modifican tus pesos guardados en la web.</div></div><div style="font-family:var(--mono);color:${phys.regulatory_ok ? 'var(--green)' : 'var(--red)'};font-weight:700;">Reglamento: ${phys.regulatory_ok ? 'OK' : 'REVISAR'}</div></div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(145px,1fr));margin-top:10px;"><div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${esc(phys.avg_effective_weight ?? 'N/A')}g</div><div class="stat-lbl">Peso efectivo promedio</div></div><div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(phys.diff_weight ?? 'N/A')}g</div><div class="stat-lbl">Diferencia de peso</div></div><div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--green)">${topPhysical.map(r => r.number).join(', ') || 'N/A'}</div><div class="stat-lbl">Mayor bonus físico</div></div><div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--red)">${bottomPhysical.map(r => r.number).join(', ') || 'N/A'}</div><div class="stat-lbl">Menor bonus físico</div></div></div>
    </div>`);
  };

  document.addEventListener('DOMContentLoaded', async () => {
    await loadV3(true);
    setTimeout(() => {
      if (document.getElementById('tab-mapa')?.classList.contains('active')) window.renderHeatGrid();
      if (document.getElementById('tab-estadisticas')?.classList.contains('active')) { window.renderPatternShiftUI(); window.renderStatsUI(); }
      if (document.getElementById('tab-laboratorio')?.classList.contains('active')) { window.analyzeRhythmsUI(); window.analyzeForensicsUI(); window.renderConditionalPatternsUI(); }
      if (document.getElementById('tab-coincidencias')?.classList.contains('active')) window.renderTopPairsUI();
      if (document.getElementById('tab-fisica')?.classList.contains('active')) window.renderWeightsGrid();
    }, 150);
  });

  document.addEventListener('melate:v3-results-loaded', (event) => {
    cache = normalize(event.detail || {});
    if (typeof window.renderHeatGrid === 'function') window.renderHeatGrid();
  });
})();
