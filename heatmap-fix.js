// ═══════════════════════════════════════════════════════
// heatmap-fix.js - Override mapa de calor V7.3
// Corrige escala roja fija y agrega lectura por ventana/patrón.
// Debe cargarse después de ui.js.
// ═══════════════════════════════════════════════════════

(function () {
  'use strict';

  const RECENT_WINDOW = 30;
  const PATTERN_WINDOW = 20;

  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
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
    if (r >= 0.82) return 'h2'; // fuerte/recomendado
    if (r >= 0.62) return 'h3'; // momentum
    if (r >= 0.38) return 'h1'; // medio
    if (r >= 0.18) return 'h4'; // bajo/frío
    return 'h0';                // evitar/alerta
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
    const label = Math.abs(cur.bias) < 0.08
      ? 'equilibrio'
      : cur.bias > 0
        ? 'sesgo izquierda 1-28'
        : 'sesgo derecha 29-56';

    return { ...cur, previousBias: prev.bias, delta, label };
  }

  function getHeatRows() {
    const DATA = getActiveData();
    const stats = computeStats();
    const drift = typeof detectEntropyDrift === 'function'
      ? detectEntropyDrift(DATA)
      : { chaosMode: false, kl: 0, confidenceFactor: 1 };
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
      const sideBoost = pattern.bias > 0 && n <= 28 ? Math.abs(pattern.bias) * 18
        : pattern.bias < 0 && n > 28 ? Math.abs(pattern.bias) * 18
          : 0;
      const score = clamp(
        stats.numScore(n) * 0.62 +
        clamp((lift - 0.65) * 32, -18, 26) +
        sideBoost,
        0,
        100
      );
      rows.push({
        n,
        score,
        freq: stats.freq[n],
        recentFreq: recent.counts[n],
        delay: stats.lastSeen[n],
        lift,
        side: n <= 28 ? 'I' : 'D',
        drift,
        shift,
        pattern
      });
    }
    return rows;
  }

  window.renderHeatGrid = function renderHeatGridPatternAware() {
    const grid = document.getElementById('heat-grid');
    const legend = document.getElementById('heat-legend');
    if (!grid) return;

    const rows = getHeatRows();
    const values = rows.map(row => {
      if (currentMapView === 'freq') return row.lift;
      if (currentMapView === 'delay') return row.delay;
      return row.score;
    }).sort((a, b) => a - b);

    let html = '';
    rows.forEach(row => {
      const value = currentMapView === 'freq'
        ? row.lift
        : currentMapView === 'delay'
          ? row.delay
          : row.score;
      const rank = percentileRank(values, value);
      const cls = currentMapView === 'delay'
        ? bucketByPercentile(rank, false)
        : bucketByPercentile(rank, false);
      const label = currentMapView === 'freq'
        ? `${row.recentFreq}/${RECENT_WINDOW} · x${row.lift.toFixed(1)}`
        : currentMapView === 'delay'
          ? `${row.delay} aus.`
          : `${Math.round(row.score)} · x${row.lift.toFixed(1)}`;
      const title = [
        `Número ${row.n}`,
        `Score ventana: ${row.score.toFixed(1)}`,
        `Frecuencia total: ${row.freq}`,
        `Frecuencia reciente: ${row.recentFreq}/${Math.min(RECENT_WINDOW, getActiveData().length)}`,
        `Lift reciente/histórico: ${row.lift.toFixed(2)}x`,
        `Retraso: ${row.delay}`,
        `Lado: ${row.side === 'I' ? 'Izquierda 1-28' : 'Derecha 29-56'}`,
        `Patrón actual: ${row.pattern.label}`,
        `KL drift: ${(row.drift.kl || 0).toFixed(4)}${row.drift.chaosMode ? ' · Modo Caos' : ''}`
      ].join(' | ');
      html += `<div class="grid-cell ${cls}" title="${title}"><div class="num">${row.n}</div><div class="sc">${label}</div></div>`;
    });

    grid.innerHTML = html;

    if (legend) {
      const drift = rows[0]?.drift || { chaosMode: false, kl: 0 };
      const pattern = rows[0]?.pattern || { label: 'N/A', delta: 0 };
      const shift = rows[0]?.shift;
      const shiftText = shift
        ? `Cambio patrón: ${shift.currentRegime} · activo ${shift.changedAgo} sorteos`
        : 'Cambio patrón: datos insuficientes';
      const modeText = currentMapView === 'freq'
        ? 'Frecuencia = lift últimos 30 vs histórico'
        : currentMapView === 'delay'
          ? 'Retraso = ausencia relativa por percentiles'
          : 'Score = numScore + lift reciente + sesgo espacial';
      legend.innerHTML = `
        <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Top percentil</span>
        <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Momentum</span>
        <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Medio</span>
        <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Bajo</span>
        <span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Último percentil</span>
        <span style="font-size:11px;color:var(--muted);width:100%;margin-top:4px;">${modeText} · ${shiftText} · Sesgo: ${pattern.label} · Δ=${pattern.delta.toFixed(3)} · KL=${(drift.kl || 0).toFixed(4)}${drift.chaosMode ? ' · MODO CAOS' : ''}</span>
      `;
    }
  };
})();
