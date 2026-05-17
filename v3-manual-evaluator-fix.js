// v3-manual-evaluator-fix.js
// Capa final para el evaluador manual: reconstruye numberMap si falta y evita score 0.0/sin datos.
(function () {
  'use strict';

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
      structural: 'estructura de combinación',
      transformer: 'Transformer secuencial',
      graph: 'grafo de co-ocurrencias',
      meta: 'MetaStacking'
    })[key] || key || 'modelo';
  }

  function isUsableResults(data) {
    return Boolean(data && (
      data.score_kind === 'optuna_weighted_net_score' ||
      data.v4_score_kind ||
      Array.isArray(data.manual_suggestion_seed) ||
      data.number_scores ||
      Array.isArray(data.generator_pool)
    ));
  }

  async function getResults() {
    let data = null;
    try { data = typeof window.getV3Results === 'function' ? window.getV3Results() : null; } catch (_) {}
    if (!isUsableResults(data)) data = window.MELATE_V4_RESULTS || window.MELATE_V3_RESULTS || null;
    if (!isUsableResults(data) && typeof window.loadV3Results === 'function') {
      try { data = await window.loadV3Results(true); } catch (_) {}
    }
    if (!isUsableResults(data)) {
      try {
        const res = await fetch(`resultados.json?t=${Date.now()}`, { cache: 'no-store' });
        if (res.ok) data = await res.json();
      } catch (_) {}
    }
    return isUsableResults(data) ? normalizeResults(data) : null;
  }

  function normalizeResults(data) {
    if (data.__manualEvaluatorNormalized && data.numberMap instanceof Map) return data;
    const numberScores = data.number_scores || data.numberScores || {};
    const seed = Array.isArray(data.manual_suggestion_seed)
      ? data.manual_suggestion_seed
      : Array.isArray(data.number_rankings)
        ? data.number_rankings
        : [];

    const byNumber = new Map();
    for (let n = 1; n <= 56; n++) {
      let score = num(numberScores[String(n)], NaN);
      if (!Number.isFinite(score)) score = num(numberScores[n], 0);
      if (score > 0 && score <= 1) score *= 100;
      byNumber.set(n, {
        number: n,
        score,
        winner_component: null,
        winner_component_human: score > 0 ? 'score V3/V4' : 'sin datos',
        reason: score > 0 ? 'score leído desde resultados.json' : 'sin explicación disponible',
        expert_raw: {}
      });
    }

    seed.forEach(row => {
      const n = Number(row.number ?? row.n ?? row.ball);
      if (!Number.isFinite(n) || n < 1 || n > 56) return;
      let score = num(row.score ?? row.score_percent ?? row.net_score, byNumber.get(n)?.score || 0);
      if (score > 0 && score <= 1) score *= 100;
      const component = row.winner_component || row.main_driver || row.driver || row.component;
      byNumber.set(n, {
        ...byNumber.get(n),
        ...row,
        number: n,
        score,
        winner_component: component,
        winner_component_human: row.winner_component_human || row.main_driver_human || row.driver_human || driverLabel(component),
        reason: row.reason || row.explanation || row.motive || 'sin explicación detallada disponible',
        expert_raw: row.expert_raw || row.expert_scores || {}
      });
    });

    // Si no hay manual_suggestion_seed suficiente, extraer señales desde generator_pool.
    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    const accum = new Map();
    pool.slice(0, 120).forEach((combo, idx) => {
      const nums = combo.numbers || combo.nums || combo.combo;
      if (!Array.isArray(nums)) return;
      const comboScore = num(combo.score_percent, num(combo.net_score, 0) * 100);
      const w = Math.max(0.12, 1 - idx / 140);
      nums.forEach(n0 => {
        const n = Number(n0);
        if (!Number.isFinite(n) || n < 1 || n > 56) return;
        const cur = accum.get(n) || { total: 0, weight: 0, count: 0 };
        cur.total += comboScore * w;
        cur.weight += w;
        cur.count += 1;
        accum.set(n, cur);
      });
    });
    accum.forEach((v, n) => {
      const row = byNumber.get(n) || { number: n, score: 0 };
      if (num(row.score) <= 0 && v.weight > 0) {
        byNumber.set(n, {
          ...row,
          score: v.total / v.weight,
          winner_component_human: 'soporte Monte Carlo',
          reason: `aparece ${v.count} veces dentro del top del generator_pool`,
        });
      }
    });

    const normalized = {
      ...data,
      numberMap: byNumber,
      manual_suggestion_seed: Array.from(byNumber.values()).sort((a, b) => num(b.score) - num(a.score)),
      generator_pool: pool,
      __manualEvaluatorNormalized: true
    };
    window.MELATE_V3_RESULTS = normalized;
    return normalized;
  }

  function getManualNums() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`)?.value, 10));
    if (nums.some(n => Number.isNaN(n) || n < 1 || n > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(nums).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return nums.sort((a, b) => a - b);
  }

  function rowFor(data, n) {
    return data.numberMap?.get(Number(n)) || { number: Number(n), score: 0, winner_component_human: 'sin datos', reason: 'sin explicación', expert_raw: {} };
  }

  function scoreOf(data, n) {
    return num(rowFor(data, n).score, 0);
  }

  function comboScore(data, nums) {
    return nums.reduce((acc, n) => acc + scoreOf(data, n), 0) / 6;
  }

  function comboStats(nums) {
    const sorted = nums.slice().sort((a, b) => a - b);
    const pares = sorted.filter(n => n % 2 === 0).length;
    const lows = sorted.filter(n => n <= 28).length;
    const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10))).size;
    const suma = sorted.reduce((a, b) => a + b, 0);
    const consec = sorted.slice(1).filter((n, i) => n - sorted[i] === 1).length;
    return { pares, impares: 6 - pares, lows, highs: 6 - lows, decades, suma, consec };
  }

  function historicalSumStats() {
    let sumMean = 171;
    let sumStd = 38;
    try {
      const rows = typeof getActiveData === 'function' ? getActiveData() : [];
      const sums = (rows || [])
        .map(r => (r || []).slice(2).reduce((a, b) => a + Number(b || 0), 0))
        .filter(Number.isFinite);
      if (sums.length > 20) {
        sumMean = sums.reduce((a, b) => a + b, 0) / sums.length;
        sumStd = Math.sqrt(sums.reduce((a, b) => a + Math.pow(b - sumMean, 2), 0) / sums.length) || sumStd;
      }
    } catch (_) {}
    return { sumMean, sumStd };
  }

  function structuralBalance(nums) {
    const st = comboStats(nums);
    const { sumMean, sumStd } = historicalSumStats();
    const parity = Math.max(0, 100 - Math.abs(st.pares - 3) * 24);
    const side = Math.max(0, 100 - Math.abs(st.lows - 3) * 22);
    const decade = Math.max(0, Math.min(100, (st.decades / 6) * 100));
    const sum = Math.max(0, 100 - Math.min(65, Math.abs((st.suma - sumMean) / Math.max(1, sumStd)) * 22));
    const consecutive = Math.max(0, 100 - st.consec * 16);
    const balance = parity * 0.24 + side * 0.22 + decade * 0.22 + sum * 0.22 + consecutive * 0.10;
    return { ...st, balance: Math.max(0, Math.min(100, balance)), parity, side, decade, sum, consecutive };
  }

  function supportMap(data) {
    const support = new Array(57).fill(0);
    const weighted = new Array(57).fill(0);
    (data.generator_pool || []).slice(0, 120).forEach((combo, idx) => {
      const nums = combo.numbers || combo.nums || combo.combo;
      if (!Array.isArray(nums)) return;
      const w = Math.max(0.15, 1 - idx / 140);
      nums.forEach(n => {
        n = Number(n);
        if (n >= 1 && n <= 56) {
          support[n] += 1;
          weighted[n] += w;
        }
      });
    });
    return { support, weighted };
  }

  function nearestPoolAlignment(data, nums) {
    const current = new Set(nums);
    let best = { overlap: 0, score: 0 };
    (data.generator_pool || []).slice(0, 120).forEach(c => {
      const cnums = c.numbers || c.nums || c.combo;
      if (!Array.isArray(cnums)) return;
      const overlap = cnums.filter(n => current.has(Number(n))).length;
      const score = num(c.score_percent, num(c.net_score, 0) * 100);
      if (overlap * 10 + score > best.overlap * 10 + best.score) best = { overlap, score };
    });
    return best;
  }

  function buildSuggestions(nums, data) {
    const current = new Set(nums);
    const baseScore = comboScore(data, nums);
    const baseBalance = structuralBalance(nums);
    const { support, weighted } = supportMap(data);
    const details = nums.map(n => ({ ...rowFor(data, n), number: n, score: scoreOf(data, n) }));
    const weak = details.slice().sort((a, b) => num(a.score) - num(b.score));
    const currentDrivers = new Set(details.map(r => r.winner_component_human || driverLabel(r.winner_component)).filter(Boolean));
    const candidates = (data.manual_suggestion_seed || [])
      .map(r => ({ ...r, number: Number(r.number), score: num(r.score), driver: r.winner_component_human || driverLabel(r.winner_component) }))
      .filter(r => Number.isFinite(r.number) && r.number >= 1 && r.number <= 56 && !current.has(r.number))
      .sort((a, b) => (num(b.score) + weighted[b.number] * 0.8) - (num(a.score) + weighted[a.number] * 0.8))
      .slice(0, 30);

    const reps = [];
    for (const bad of weak.slice(0, 4)) {
      for (const good of candidates) {
        const add = Number(good.number);
        const remove = Number(bad.number);
        if (!Number.isFinite(add) || !Number.isFinite(remove) || current.has(add)) continue;
        const next = nums.map(n => n === remove ? add : n).sort((a, b) => a - b);
        const nextScore = comboScore(data, next);
        const nextBalance = structuralBalance(next);
        const gain = nextScore - baseScore;
        const balanceGain = nextBalance.balance - baseBalance.balance;
        const alignment = nearestPoolAlignment(data, next);
        const newDriver = !currentDrivers.has(good.driver) ? 2.2 : 0;
        const supportBonus = Math.min(7.5, support[add] * 0.38 + weighted[add] * 0.55);
        const rawImprovement = scoreOf(data, add) - scoreOf(data, remove);
        const total = gain * 1.65 + balanceGain * 0.08 + supportBonus + newDriver + alignment.overlap * 0.9 + Math.max(0, rawImprovement) * 0.12;
        reps.push({ remove, add, next, nextScore, gain, baseBalance: baseBalance.balance, nextBalance: nextBalance.balance, balanceGain, alignment, support: support[add], driver: good.driver, addReason: good.reason || 'sin explicación', removeDriver: bad.winner_component_human || driverLabel(bad.winner_component), addScore: scoreOf(data, add), removeScore: scoreOf(data, remove), total });
      }
    }
    reps.sort((a, b) => b.total - a.total);
    const picked = [];
    const usedAdd = new Set();
    const usedRemove = new Set();
    for (const r of reps) {
      if (picked.length >= 3) break;
      if (usedAdd.has(r.add) || usedRemove.has(r.remove)) continue;
      if (r.gain < 0.25 && r.balanceGain < 2.5 && r.support < 4) continue;
      picked.push(r);
      usedAdd.add(r.add);
      usedRemove.add(r.remove);
    }
    return picked;
  }

  function ballHtml(nums, color = 'var(--purple)') {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</div>`).join('');
  }

  function balanceMiniGrid(b) {
    const color = b.balance >= 78 ? 'var(--green)' : b.balance >= 62 ? 'var(--gold)' : 'var(--red)';
    return `<div style="background:rgba(255,255,255,.04);border:1px solid ${color};border-radius:10px;padding:12px;margin-bottom:14px;">
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:8px;">
        <div style="font-weight:800;color:${color};">Balance estructural: ${fmt(b.balance, 2)}/100</div>
        <div style="font-size:11px;color:var(--muted);">recalculado por combinación</div>
      </div>
      <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;font-size:11px;color:var(--muted);">
        <div>Paridad<br><b style="color:var(--text)">${fmt(b.parity, 1)}</b></div>
        <div>Izq/Der<br><b style="color:var(--text)">${fmt(b.side, 1)}</b></div>
        <div>Décadas<br><b style="color:var(--text)">${fmt(b.decade, 1)}</b></div>
        <div>Suma<br><b style="color:var(--text)">${fmt(b.sum, 1)}</b></div>
        <div>Consecutivos<br><b style="color:var(--text)">${fmt(b.consecutive, 1)}</b></div>
      </div>
    </div>`;
  }

  window.evalUserComboUI = async function evalUserComboUIFixed() {
    const data = await getResults();
    if (!data) {
      const resultEl = document.getElementById('user-result');
      if (resultEl) resultEl.innerHTML = `<div class="card" style="margin-top:16px;border-color:var(--red)"><div class="card-body" style="color:var(--red)">No pude leer resultados.json con scores por número. Ejecuta el cruncher y sube resultados.json.</div></div>`;
      return;
    }

    let nums;
    try { nums = getManualNums(); }
    catch (err) { if (typeof showToast === 'function') showToast(`⚠️ ${err.message}`); return; }

    const details = nums.map(n => ({ ...rowFor(data, n), number: n, score: scoreOf(data, n) }));
    const score = comboScore(data, nums);
    const stats = comboStats(nums);
    const balance = structuralBalance(nums);
    const suggestions = buildSuggestions(nums, data);
    const color = score >= 80 ? 'var(--green)' : score >= 65 ? 'var(--gold)' : 'var(--purple)';
    const rows = details.map(row => `<tr>
      <td><b style="color:var(--text)">${esc(row.number)}</b></td>
      <td>${fmt(row.score, 2)}</td>
      <td>${esc(row.winner_component_human || driverLabel(row.winner_component))}</td>
      <td>${esc(row.reason || 'sin explicación')}</td>
    </tr>`).join('');

    const suggestionHtml = suggestions.length ? suggestions.map(s => `<div class="suggestion-card top">
      <div style="font-weight:700;color:var(--teal);margin-bottom:8px;">Sugerencia V3 · ${s.remove} → ${s.add}</div>
      <div class="suggestion-nums">${s.next.map(n => `<div class="suggestion-num">${n}</div>`).join('')}</div>
      <div class="suggestion-strategy">Cambiar ${s.remove} (${fmt(s.removeScore, 1)}/100, ${esc(s.removeDriver)}) por ${s.add} (${fmt(s.addScore, 1)}/100, ${esc(s.driver)}). Ganancia neta ${s.gain >= 0 ? '+' : ''}${fmt(s.gain, 2)} pts; balance ${fmt(s.baseBalance, 2)} → ${fmt(s.nextBalance, 2)} (${s.balanceGain >= 0 ? '+' : ''}${fmt(s.balanceGain, 2)}); soporte MC top120: ${s.support}; alineación pool: ${s.alignment.overlap}/6. ${esc(s.addReason)}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">Score estimado nuevo: ${fmt(s.nextScore, 2)}/100 · Balance nuevo ${fmt(s.nextBalance, 2)}/100</div>
      <button class="btn btn-sm btn-blue" onclick="evalSuggestion([${s.next.join(',')}])">📊 Probar sugerencia</button>
    </div>`).join('') : '<div style="color:var(--muted);">No hay cambios recomendados con mejora clara frente a los datos actuales.</div>';

    const resultEl = document.getElementById('user-result');
    if (!resultEl) return;
    resultEl.innerHTML = `<div class="card" style="margin-top:16px;border-color:${color}70;background:rgba(0,0,0,.2);">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;">Análisis Manual · ${esc(data.game_label || data.game_mode || '')}</h2>
        <span class="badge" style="background:rgba(0,0,0,.3);color:${color};border:1px solid ${color};font-size:14px;padding:6px 14px">NET AVG · ${fmt(score, 2)}/100</span>
      </div>
      <div class="card-body">
        <div class="combo-balls" style="margin-bottom:12px;">${ballHtml(nums, color)}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;font-size:13px;color:var(--muted);margin-bottom:14px;background:var(--surface);padding:12px;border-radius:8px;border:1px solid var(--border);">
          <div>Suma: <b style="color:var(--text)">${stats.suma}</b></div>
          <div>Pares/Imp: <b style="color:var(--text)">${stats.pares}P/${stats.impares}I</b></div>
          <div>Bajos/Altos: <b style="color:var(--text)">${stats.lows}/${stats.highs}</b></div>
          <div>Décadas: <b style="color:var(--text)">${stats.decades}/6</b></div>
        </div>
        ${balanceMiniGrid(balance)}
        <div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Score</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>${rows}</tbody></table></div>
        <div class="suggestion-panel">
          <div class="suggestion-title">💡 Sugerencias profundas con datos del JSON</div>
          <div class="suggestions-grid">${suggestionHtml}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:14px;"><button class="btn btn-teal" onclick="saveManualComboUI([${nums.join(',')}])">💾 Guardar combinación</button></div>
      </div>
    </div>`;
  };
})();
