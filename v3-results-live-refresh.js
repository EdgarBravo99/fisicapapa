// v3-results-live-refresh.js
// Fuerza recarga real de resultados.json y refresca paneles cuando cambia last_update.
(function () {
  'use strict';

  const REFRESH_MS = 30000;
  let lastSeenUpdate = null;
  let running = false;

  function isV3(data) {
    return Boolean(data && data.score_kind === 'optuna_weighted_net_score');
  }

  async function fetchFreshResults() {
    const url = `resultados.json?v=${Date.now()}&r=${Math.random().toString(36).slice(2)}`;
    const res = await fetch(url, {
      cache: 'no-store',
      headers: {
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
      }
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    if (!isV3(data)) throw new Error('resultados.json no es V3');
    return data;
  }

  async function refreshV3Results(reason = 'timer') {
    if (running) return null;
    running = true;
    try {
      const raw = await fetchFreshResults();
      const current = window.MELATE_V3_RESULTS;
      const newUpdate = raw.last_update || raw.historical_forgetting?.buffer_last_draw || JSON.stringify(raw.expert_weights || {});
      const oldUpdate = current?.last_update || current?.historical_forgetting?.buffer_last_draw || lastSeenUpdate;

      // Reusar el normalizador oficial si existe.
      if (typeof window.loadV3Results === 'function') {
        // Esta llamada fuerza al bridge principal a reconstruir numberMap/manual_suggestion_seed.
        const normalized = await window.loadV3Results(true);
        window.MELATE_V3_RESULTS = normalized || raw;
      } else {
        window.MELATE_V3_RESULTS = raw;
      }

      lastSeenUpdate = newUpdate;
      const changed = newUpdate && newUpdate !== oldUpdate;
      document.dispatchEvent(new CustomEvent('melate:v3-results-live-refresh', {
        detail: { changed, reason, last_update: newUpdate, data: window.MELATE_V3_RESULTS }
      }));

      if (changed) {
        document.dispatchEvent(new CustomEvent('melate:v3-results-loaded', { detail: window.MELATE_V3_RESULTS }));
        if (typeof window.renderV3ModelPortfolio === 'function') window.renderV3ModelPortfolio();
        if (typeof window.renderV3LeftRightIndicator === 'function') window.renderV3LeftRightIndicator();
        if (typeof window.renderV3PanelsBridge === 'function') window.renderV3PanelsBridge();
        if (typeof window.renderCombosList === 'function') window.renderCombosList();
        console.info('[V3] resultados.json actualizado:', newUpdate);
      }
      return window.MELATE_V3_RESULTS;
    } catch (err) {
      console.warn('[V3] No se pudo refrescar resultados.json:', err);
      return null;
    } finally {
      running = false;
    }
  }

  window.refreshV3ResultsNow = refreshV3Results;

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => refreshV3Results('DOMContentLoaded'), 500);
    setInterval(() => refreshV3Results('interval'), REFRESH_MS);
  });

  window.addEventListener('focus', () => refreshV3Results('focus'));
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) refreshV3Results('visibility');
  });
})();
