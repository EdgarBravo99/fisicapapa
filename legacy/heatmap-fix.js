// heatmap-fix.js - Mapa de calor V3-aware.
// Usa resultados.json V3 cuando existe; conserva fallback legacy si no hay V3.
(function () {
  'use strict';

  const RECENT_WINDOW = 30;
  const PATTERN_WINDOW = 20;

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

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

  function percentileRank(sortedValues, value) {
    if (!sortedValues.length) return 0.5;
    let below = 0;
    for (let i = 0; i < sortedValues.length; i++) {
      if (sortedValues[i] <= value) below++;
      else break;
    }
    return below / sortedValues.length;
  }

  function bucketByPercentile(rank, inverted = false) {
    const r = inverted ? 1 - rank : rank;
    if (r >= 0.82) return 'h2';
    if (r >= 0.62) return 'h3';
    if (r >= 0.38) return 'h1';
    if (r >= 0.18) return 'h4';
    return 'h0';
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
      structural: 'estructura'
    })[key] || key || 'V3';
  }

  function getV3Data() {
    return typeof window.getV3Results === 'function' ? window.getV3Results() : window.MELATE_V3_RESULTS;
  }

  function v3Rows() {
    const data = getV3Data();
    if (!data || data.score_kind !== 'optuna_weighted_net_score') return null;
    const numberScores = data.number_scores || {};
    const byNumber = new Map();
    if (Array.isArray(data.manual_suggestion_seed)) {
      data.manual_suggestion_seed.forEach(row => byNumber.set(Number(row.number), row));
    }
    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    const support = new Array(57).fill(0);
    pool.slice(0, 80).forEach(combo => {
      if (!Array.isArray(combo.numbers)) return;
      combo.numbers.forEach(n => {
        if (n >= 1 && n <= 56) support[n]++;
      });
    });
    const rows = [];
    for (let n = 1; n <= 56; n++) {
      const row = byNumber.get(n) || {};
      const score = num(row.score, num(numberScores[String(n)], 0));
      const expertRaw = row.expert_raw || row.experts || {};
      rows.push({
        n,
        score,
        delay: num(row.uses_in_window, 0),
        support: support[n],
        driver: row.winner_component_human || driverLabel(row.winner_component),
        reason: row.reason || 'Sin explicación V3 disponible',
        effectiveWeight: row.effective_weight,
        physicsBonus: row.physics_bonus,
        expertRaw,
        gameLabel: data.game_label || '',
        buffer: data.historical_forgetting?.recent_buffer_size,
        maxScore: num(data.max_net_score_found, 0) * 100,
        drift: data.drift_detected,
        source: 'v3'
      });
    }
    return rows;
  }

  function countWindow(DATA, start, end) {
    const counts = new Array(57).fill(0);
    const slice = DATA.slice(start, end);
    slice.forEach(row => {
      row.slice(2).forEach(n => {
        if (n >= 1 && n <= 56) counts[n]++;
      });
    });
    return { counts, totalDraws: slice.length };
  }

  function getPatternBias(DATA) {
    const recent = DATA.slice(0, PATTERN_WINDOW);
    const previous = DATA.slice(PATTERN_WINDOW, PATTERN_WINDOW * 2);
    function sideScore(rows) {
      let left = 0;
      let right = 0;
      rows.forEach(row => {
        row.slice(2).forEach(n => {
          if (n <= 28) left++;
          else right++;
        });
      });
      const total = left + right || 1;
      return { left, right, bias: (left - right) / total };
    }
    const cur = sideScore(recent);
    const prev = sideScore(previous);
    const delta = cur.bias - prev.bias;
    const label = Math.abs(cur.bias) < 0.08 ? 'equilibrio' : cur.bias > 0 ? 'sesgo izquierda 1-28' : 'sesgo derecha 29-56';
    return { ...cur, previousBias: prev.bias, delta, label };
  }

  function legacyRows() {
    const DATA = typeof getActiveData === 'function' ? getActiveData() : [];
    const stats = typeof computeStats === 'function' ? computeStats() : null;
    if (!DATA.length || !stats) return [];
    const drift = typeof detectEntropyDrift === 'function' ? detectEntropyDrift(DATA) : { chaosMode: false, kl: 0, confidenceFactor: 1 };
    const shift = typeof detectPatternShift === 'function' ? detectPatternShift() : null;
    const pattern = getPatternBias(DATA);
    const recentWindow = Math.min(RECENT_WINDOW, DATA.length);
    const recent = countWindow(DATA, 0, recentWindow);
    const historical = countWindow(DATA, 0, DATA.length);
    const rows = [];
    for (let n = 1; n <= 56; n++) {
      const histRate = historical.totalDraws ? historical.counts[n] / historical.totalDraws : 0;
      const recentRate = recent.totalDraws ? recent.counts[n] / recent.totalDraws : 0;
      const lift = histRate > 0 ? recentRate / histRate : recentRate > 0 ? 2 : 0;
      const sideBoost = pattern.bias > 0 && n <= 28 ? Math.abs(pattern.bias) * 18 : pattern.bias < 0 && n > 28 ? Math.abs(pattern.bias) * 18 : 0;
      const score = clamp(stats.numScore(n) * 0.62 + clamp((lift - 0.65) * 32, -18, 26) + sideBoost, 0, 100);
      rows.push({ n, score, freq: stats.freq[n], recentFreq: recent.counts[n], delay: stats.lastSeen[n], lift, side: n <= 28 ? 'I' : 'D', drift, shift, pattern, source: 'legacy' });
    }
    return rows;
  }

  function getRows() {
    return v3Rows() || legacyRows();
  }

  window.renderHeatGrid = function renderHeatGridV3Aware() {
    const grid = document.getElementById('heat-grid');
    const legend = document.getElementById('heat-legend');
    if (!grid) return;
    const rows = getRows();
    if (!rows.length) {
      grid.innerHTML = '<div style="color:var(--muted);font-size:12px;">Sin datos para mapa de calor.</div>';
      return;
    }
    const isV3 = rows[0].source === 'v3';
    const values = rows.map(row => {
      if (isV3) {
        if (currentMapView === 'freq') return row.support;
        if (currentMapView === 'delay') return row.physicsBonus ?? 0;
        return row.score;
      }
      if (currentMapView === 'freq') return row.lift;
      if (currentMapView === 'delay') return row.delay;
      return row.score;
    }).sort((a, b) => a - b);

    let html = '';
    rows.forEach(row => {
      const value = isV3
        ? currentMapView === 'freq'
          ? row.support
          : currentMapView === 'delay'
            ? num(row.physicsBonus, 0)
            : row.score
        : currentMapView === 'freq'
          ? row.lift
          : currentMapView === 'delay'
            ? row.delay
            : row.score;
      const rank = percentileRank(values, value);
      const cls = bucketByPercentile(rank, false);
      let label;
      let title;
      if (isV3) {
        label = currentMapView === 'freq'
          ? `${row.support}/80 pool`
          : currentMapView === 'delay'
            ? `fis ${fmt(row.physicsBonus, 1)}`
            : `${fmt(row.score, 1)}`;
        const experts = row.expertRaw && typeof row.expertRaw === 'object'
          ? Object.entries(row.expertRaw).sort((a, b) => num(b[1]) - num(a[1])).slice(0, 4).map(([k, v]) => `${driverLabel(k)}=${fmt(num(v) * 100, 1)}`).join(', ')
          : 'sin desglose';
        title = [
          `Número ${row.n}`,
          `Score V3: ${fmt(row.score, 2)}/100`,
          `Impulsor: ${row.driver}`,
          `Motivo: ${row.reason}`,
          `Peso efectivo: ${row.effectiveWeight ?? 'N/A'}g`,
          `Bonus físico: ${row.physicsBonus ?? 'N/A'}`,
          `Aparece en pool top80: ${row.support}`,
          `Expertos: ${experts}`,
          `Juego: ${row.gameLabel}`,
          `Buffer: ${row.buffer ?? 'N/A'}`,
          `Drift: ${row.drift ? 'sí' : 'no'}`
        ].join(' | ');
      } else {
        label = currentMapView === 'freq' ? `${row.recentFreq}/${RECENT_WINDOW} · x${row.lift.toFixed(1)}` : currentMapView === 'delay' ? `${row.delay} aus.` : `${Math.round(row.score)} · x${row.lift.toFixed(1)}`;
        title = [`Número ${row.n}`, `Score ventana: ${row.score.toFixed(1)}`, `Frecuencia total: ${row.freq}`, `Frecuencia reciente: ${row.recentFreq}/${Math.min(RECENT_WINDOW, getActiveData().length)}`, `Lift reciente/histórico: ${row.lift.toFixed(2)}x`, `Retraso: ${row.delay}`, `Patrón actual: ${row.pattern.label}`, `KL drift: ${(row.drift.kl || 0).toFixed(4)}${row.drift.chaosMode ? ' · Modo Caos' : ''}`].join(' | ');
      }
      html += `<div class="grid-cell ${cls}" title="${esc(title)}"><div class="num">${row.n}</div><div class="sc">${esc(label)}</div></div>`;
    });
    grid.innerHTML = html;

    if (legend) {
      if (isV3) {
        const data = getV3Data();
        const modeText = currentMapView === 'freq'
          ? 'Pool = cuántas veces aparece en las mejores combinaciones V3'
          : currentMapView === 'delay'
            ? 'Físico = bonus/peso efectivo de esfera del modelo V3'
            : 'Score = number_scores ponderado por Optuna V3';
        legend.innerHTML = `
          <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Top V3</span>
          <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Alto</span>
          <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Medio</span>
          <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Bajo</span>
          <span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Último percentil</span>
          <span style="font-size:11px;color:var(--muted);width:100%;margin-top:4px;">${modeText} · Juego: ${esc(data?.game_label || 'V3')} · Buffer: ${esc(data?.historical_forgetting?.recent_buffer_size ?? 'N/A')} · MC: ${Number(data?.total_mc_evaluated || 0).toLocaleString('es-MX')} · Drift: ${data?.drift_detected ? 'sí' : 'no'}</span>
        `;
      } else {
        const drift = rows[0]?.drift || { chaosMode: false, kl: 0 };
        const pattern = rows[0]?.pattern || { label: 'N/A', delta: 0 };
        const shift = rows[0]?.shift;
        const shiftText = shift ? `Cambio patrón: ${shift.currentRegime} · activo ${shift.changedAgo} sorteos` : 'Cambio patrón: datos insuficientes';
        const modeText = currentMapView === 'freq' ? 'Frecuencia = lift últimos 30 vs histórico' : currentMapView === 'delay' ? 'Retraso = ausencia relativa por percentiles' : 'Score = numScore + lift reciente + sesgo espacial';
        legend.innerHTML = `
          <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Top percentil</span>
          <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Momentum</span>
          <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Medio</span>
          <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Bajo</span>
          <span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Último percentil</span>
          <span style="font-size:11px;color:var(--muted);width:100%;margin-top:4px;">${modeText} · ${shiftText} · Sesgo: ${pattern.label} · Δ=${pattern.delta.toFixed(3)} · KL=${(drift.kl || 0).toFixed(4)}${drift.chaosMode ? ' · MODO CAOS' : ''}</span>
        `;
      }
    }
  };

  document.addEventListener('melate:v3-results-loaded', () => {
    if (typeof window.renderHeatGrid === 'function') window.renderHeatGrid();
  });
})();
