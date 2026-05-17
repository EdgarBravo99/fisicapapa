// v3-generator-elite-rank.js
// Generador V3 directo: usa generator_pool optimizado de resultados.json.
// No ejecuta Monte Carlo en navegador ni usa opciones legacy.
(function () {
  'use strict';

  const originalGenerateCombos = window.generateCombos;
  const originalRenderCombosList = window.renderCombosList;

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

  function combosRef() {
    try {
      if (Array.isArray(generatedCombos)) return generatedCombos;
    } catch (_) {}
    window.generatedCombos = window.generatedCombos || [];
    return window.generatedCombos;
  }

  function setCombos(next) {
    try {
      generatedCombos = next;
      return generatedCombos;
    } catch (_) {
      window.generatedCombos = next;
      return window.generatedCombos;
    }
  }

  function getV3() {
    const data = typeof window.getV3Results === 'function' ? window.getV3Results() : window.MELATE_V3_RESULTS;
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  async function ensureV3(force = false) {
    let data = getV3();
    if ((!data || force) && typeof window.loadV3Results === 'function') {
      data = await window.loadV3Results(force);
    }
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  function rawScore(combo) {
    if (Number.isFinite(Number(combo?.score_percent))) return Number(combo.score_percent);
    if (Number.isFinite(Number(combo?.net_score))) return Number(combo.net_score) * 100;
    if (Number.isFinite(Number(combo?.confidence))) return Number(combo.confidence);
    return 0;
  }

  function keyOf(nums) {
    return (nums || []).map(Number).sort((a, b) => a - b).join('-');
  }

  function poolStats(data) {
    const pool = Array.isArray(data?.generator_pool) ? data.generator_pool : [];
    const scores = pool.map(rawScore).filter(v => Number.isFinite(v));
    const max = scores.length ? Math.max(...scores) : 0;
    const min = scores.length ? Math.min(...scores) : max;
    const byKey = new Map();
    pool.forEach((c, idx) => byKey.set(keyOf(c.numbers), { idx, combo: c }));
    return { pool, max, min, byKey };
  }

  function eliteIndex(comboLike, data) {
    const { pool, max, min, byKey } = poolStats(data);
    const nums = comboLike?.numbers || comboLike?.nums || [];
    const found = byKey.get(keyOf(nums));
    const idx = found ? found.idx : pool.findIndex(c => keyOf(c.numbers) === keyOf(nums));
    const raw = rawScore(found?.combo || comboLike);
    const denom = Math.max(0.0001, max - min);
    const relative = ((raw - min) / denom) * 100;
    const maxRankSpan = Math.max(1, Math.min(pool.length, 250) - 1);
    const rankComponent = idx >= 0 && pool.length > 1 ? (1 - idx / maxRankSpan) * 100 : relative;
    const index = Math.max(0, Math.min(100, 0.58 * rankComponent + 0.42 * relative));
    return { index, raw, rank: idx >= 0 ? idx + 1 : null, total: pool.length, max, min };
  }

  function normalizeCombo(item, data) {
    const nums = Array.isArray(item?.numbers) ? item.numbers.map(Number).sort((a, b) => a - b) : [];
    const q = eliteIndex(item, data);
    return {
      nums,
      name: `V3 ${item?.game_label || data?.game_label || 'Python'} · Optimizada`,
      confidence: q.raw,
      elite_index: q.index,
      pool_rank: q.rank,
      pool_total: q.total,
      procedure: item?.human_explanation || item?.procedure || item?.plain_route || 'Generado por local_cruncher_v3.py con parámetros optimizados.',
      source: 'sequential_gpu_montecarlo_v3',
      metrics: item || {}
    };
  }

  function comboSignature(nums) {
    const sorted = nums.slice().sort((a, b) => a - b);
    return [
      sorted.filter(n => n % 2 === 0).length,
      sorted.filter(n => n <= 28).length,
      new Set(sorted.map(n => Math.floor((n - 1) / 10))).size,
      Math.floor(sorted.reduce((a, b) => a + b, 0) / 20)
    ].join('|');
  }

  function structuralBalance(nums, data) {
    const sorted = (nums || []).map(Number).filter(n => n >= 1 && n <= 56).sort((a, b) => a - b);
    const suma = sorted.reduce((a, b) => a + b, 0);
    const pares = sorted.filter(n => n % 2 === 0).length;
    const lows = sorted.filter(n => n <= 28).length;
    const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10))).size;
    const consec = sorted.slice(1).filter((n, i) => n - sorted[i] === 1).length;

    let sumMean = 171;
    let sumStd = 38;
    try {
      const rows = typeof getActiveData === 'function' ? getActiveData() : [];
      const sums = (rows || []).map(r => (r || []).slice(2).reduce((a, b) => a + Number(b || 0), 0)).filter(Number.isFinite);
      if (sums.length > 20) {
        sumMean = sums.reduce((a, b) => a + b, 0) / sums.length;
        sumStd = Math.sqrt(sums.reduce((a, b) => a + Math.pow(b - sumMean, 2), 0) / sums.length) || sumStd;
      }
    } catch (_) {}

    const parity = Math.max(0, 100 - Math.abs(pares - 3) * 24);
    const side = Math.max(0, 100 - Math.abs(lows - 3) * 22);
    const decade = Math.max(0, Math.min(100, (decades / 6) * 100));
    const sum = Math.max(0, 100 - Math.min(65, Math.abs((suma - sumMean) / Math.max(1, sumStd)) * 22));
    const consecutive = Math.max(0, 100 - consec * 16);
    const balance = parity * 0.24 + side * 0.22 + decade * 0.22 + sum * 0.22 + consecutive * 0.10;
    return {
      balance: Math.max(0, Math.min(100, balance)),
      parity, side, decade, sum, consecutive,
      suma, pares, impares: 6 - pares, lows, highs: 6 - lows, decades, consec,
      sumMean, sumStd
    };
  }

  function takeEliteCombos(data, count) {
    const pool = Array.isArray(data?.generator_pool) ? data.generator_pool : [];
    if (!pool.length) return [];

    const list = combosRef();
    const existing = new Set(list.map(c => keyOf(c.nums || c.numbers)));
    const eliteWindow = pool.slice(0, Math.min(110, pool.length));
    const selected = [];
    const usedSignatures = new Set();

    for (const item of eliteWindow) {
      if (selected.length >= count) break;
      if (!Array.isArray(item.numbers)) continue;
      const key = keyOf(item.numbers);
      const sig = comboSignature(item.numbers);
      if (existing.has(key)) continue;
      if (usedSignatures.has(sig) && selected.length < Math.ceil(count / 2)) continue;
      selected.push(normalizeCombo(item, data));
      usedSignatures.add(sig);
    }

    if (selected.length < count) {
      for (const item of eliteWindow) {
        if (selected.length >= count) break;
        if (!Array.isArray(item.numbers)) continue;
        const key = keyOf(item.numbers);
        if (existing.has(key) || selected.some(c => keyOf(c.nums) === key)) continue;
        selected.push(normalizeCombo(item, data));
      }
    }
    return selected;
  }

  function ballHtml(nums, color = 'var(--purple)') {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</div>`).join('');
  }

  function hideLegacyGeneratorOptions() {
    const mc = document.getElementById('strat-montecarlo');
    const mig = document.getElementById('strat-migration');
    const row = mc?.closest('div') || mig?.closest('div');
    if (row) row.style.display = 'none';
    const info = document.getElementById('combo-info');
    if (info) info.textContent = 'V3 optimizado desde resultados.json';
  }

  window.generateCombos = async function generateOptimizedV3Combos(count) {
    hideLegacyGeneratorOptions();
    const data = await ensureV3(true);
    if (!data) {
      if (typeof originalGenerateCombos === 'function') return originalGenerateCombos(count);
      if (typeof showToast === 'function') showToast('⚠️ Ejecuta local_cruncher_v3.py para generar resultados.json V3');
      return;
    }

    const combos = takeEliteCombos(data, count);
    if (!combos.length) {
      if (typeof showToast === 'function') showToast('⚠️ No hay combinaciones nuevas en el pool optimizado V3');
      return;
    }

    const list = combosRef();
    list.unshift(...combos);
    window.renderCombosList();
    if (typeof showToast === 'function') showToast(`🧬 ${combos.length} combinaciones V3 optimizadas cargadas`);
  };

  window.renderCombosList = function renderOptimizedV3CombosList() {
    const container = document.getElementById('combos-container');
    const data = getV3();
    const list = combosRef();
    if (!container) return;
    hideLegacyGeneratorOptions();

    if (!list.length) {
      container.innerHTML = '';
      const info = document.getElementById('combo-info');
      if (info) info.textContent = 'V3 optimizado desde resultados.json';
      if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
      return;
    }

    const hasV3 = list.some(c => c.source === 'sequential_gpu_montecarlo_v3');
    if (!hasV3 || !data) {
      if (typeof originalRenderCombosList === 'function') return originalRenderCombosList();
      return;
    }

    container.innerHTML = list.map((cb, i) => {
      if (cb.source !== 'sequential_gpu_montecarlo_v3') return '';
      const q = {
        index: Number.isFinite(Number(cb.elite_index)) ? Number(cb.elite_index) : eliteIndex(cb, data).index,
        raw: Number.isFinite(Number(cb.confidence)) ? Number(cb.confidence) : eliteIndex(cb, data).raw,
        rank: cb.pool_rank || eliteIndex(cb, data).rank,
        total: cb.pool_total || eliteIndex(cb, data).total
      };
      const b = structuralBalance(cb.nums, data);
      const color = q.index >= 92 ? 'var(--green)' : q.index >= 82 ? 'var(--gold)' : 'var(--purple)';
      const balanceColor = b.balance >= 78 ? 'var(--green)' : b.balance >= 62 ? 'var(--gold)' : 'var(--red)';
      const savedLabel = typeof isComboSaved === 'function' && isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
      const savedDisabled = savedLabel === 'Guardado' ? 'disabled' : '';
      const route = cb.metrics?.plain_route || (Array.isArray(cb.metrics?.number_explanations) ? cb.metrics.number_explanations.map(x => `${x.number}: ${x.main_driver_human || x.driver_human || 'V3'}`).join(' | ') : '');
      const rankText = q.rank ? `Rank ${q.rank}/${q.total}` : 'Rank N/A';

      return `<div class="combo-card" style="border-color:${color}70">
        <div class="combo-card-header">
          <span style="color:${color};font-weight:700">#${list.length - i} · ${esc(cb.name || 'V3 Optimizada')}</span>
          <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">ÍNDICE TOP: ${q.index.toFixed(2)}</span>
        </div>
        <div class="combo-balls">${ballHtml(cb.nums, color)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;display:flex;gap:8px;flex-wrap:wrap;">
          <span>${rankText}</span>
          <span>net_score crudo: ${q.raw.toFixed(2)}/100</span>
          <span>Suma: ${b.suma}</span>
          <span>P/I: ${b.pares}P/${b.impares}I</span>
          <span>Décadas: ${b.decades}</span>
          <span style="color:${balanceColor};font-weight:700;">Balance estructural: ${b.balance.toFixed(2)}/100</span>
        </div>
        <div style="margin-top:8px;display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;font-size:11px;color:var(--muted);">
          <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:6px;">Paridad<br><b style="color:var(--text)">${b.parity.toFixed(1)}</b></div>
          <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:6px;">Izq/Der<br><b style="color:var(--text)">${b.side.toFixed(1)}</b></div>
          <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:6px;">Décadas<br><b style="color:var(--text)">${b.decade.toFixed(1)}</b></div>
          <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:6px;">Suma<br><b style="color:var(--text)">${b.sum.toFixed(1)}</b></div>
          <div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:6px;padding:6px;">Consecutivos<br><b style="color:var(--text)">${b.consecutive.toFixed(1)}</b></div>
        </div>
        <div style="margin-top:10px;background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:8px;padding:10px;font-size:12px;color:var(--muted);line-height:1.55;">
          <div style="color:var(--purple);font-weight:700;margin-bottom:6px;">🧬 Explicación V3 optimizada</div>
          <div>${esc(cb.procedure)}</div>
          <div style="margin-top:8px;color:var(--dim);">${esc(route)}</div>
          <div style="margin-top:8px;color:var(--gold);font-size:11px;">El balance se recalcula por combinación: paridad, izquierda/derecha, décadas, suma y consecutivos. No usa un valor global fijo.</div>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;">
          <button class="btn btn-sm btn-blue" onclick="window.evalPythonComboFromGenerated(${i})">📊 Explicar</button>
          <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
        </div>
      </div>`;
    }).join('');

    const info = document.getElementById('combo-info');
    if (info) info.textContent = `${list.length} jugadas V3 optimizadas`;
    if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
  };

  document.addEventListener('DOMContentLoaded', () => {
    hideLegacyGeneratorOptions();
    document.getElementById('btn-clear')?.addEventListener('click', () => {
      setCombos([]);
      window.renderCombosList();
    });
  });
})();
