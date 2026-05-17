// pakin-remote-loader.js
// Fuente remota automática para Melate/Revancha desde github.com/pakinja/pakin.
// La web deja de depender de cargar CSV manual en cada dispositivo.
(function () {
  'use strict';

  const PAKIN_SOURCES = {
    melate: [
      'https://raw.githubusercontent.com/pakinja/pakin/master/Melate.csv',
      'https://raw.githubusercontent.com/pakinja/pakin/master/Historico-Melate.csv'
    ],
    revancha: [
      'https://raw.githubusercontent.com/pakinja/pakin/master/Revancha.csv',
      'https://raw.githubusercontent.com/pakinja/pakin/master/Historico-Revancha.csv'
    ]
  };

  const STATE = {
    loaded: false,
    loading: false,
    melateRows: 0,
    revanchaRows: 0,
    errors: []
  };

  window.PAKIN_REMOTE_STATE = STATE;

  function setStatus(message, kind = 'info') {
    const status = document.getElementById('db-status');
    if (status) {
      const color = kind === 'ok' ? 'var(--green)' : kind === 'warn' ? 'var(--gold)' : kind === 'err' ? 'var(--red)' : 'var(--muted)';
      status.innerHTML = `<span style="color:${color}">${message}</span>`;
    }
    const info = document.getElementById('combo-info');
    if (info && STATE.loaded) info.textContent = `Pakin remoto · ${CURRENT_MODE === 'melate' ? STATE.melateRows : STATE.revanchaRows} sorteos`;
  }

  async function fetchTextWithFallback(urls) {
    let lastErr = null;
    for (const url of urls) {
      try {
        const res = await fetch(`${url}?v=${Date.now()}`, { cache: 'no-store' });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const text = await res.text();
        if (!text || text.trim().length < 20) throw new Error('CSV vacío');
        return { text, url };
      } catch (err) {
        lastErr = err;
        STATE.errors.push(`${url}: ${err.message}`);
      }
    }
    throw lastErr || new Error('No se pudo descargar CSV remoto');
  }

  function sortRowsNewestFirst(rows) {
    return (rows || [])
      .filter(r => Array.isArray(r) && r.length >= 8)
      .sort((a, b) => Number(b[0]) - Number(a[0]));
  }

  function parseRemoteCsv(mode, text) {
    if (typeof parseCsvText !== 'function') throw new Error('parseCsvText no está disponible');
    const parsed = parseCsvText(text, mode);
    if (mode === 'melate') return sortRowsNewestFirst(parsed.newMelate || []);
    return sortRowsNewestFirst(parsed.newRevancha || []);
  }

  function applyRowsWithoutManualCsv(melateRows, revanchaRows) {
    if (Array.isArray(melateRows) && melateRows.length) {
      DATA_MELATE = melateRows;
      STATE.melateRows = melateRows.length;
    }
    if (Array.isArray(revanchaRows) && revanchaRows.length) {
      DATA_REVANCHA = revanchaRows;
      STATE.revanchaRows = revanchaRows.length;
    }
  }

  async function mirrorToIndexedDbForCompatibility() {
    // Pakin sigue siendo la fuente de verdad. Esto solo mantiene compatibilidad
    // con paneles que leen snapshots/física desde IndexedDB.
    try {
      if (typeof openLocalDatabase === 'function' && !DB_INSTANCE) await openLocalDatabase();
      if (typeof saveModeDataToDB === 'function') {
        if (Array.isArray(DATA_MELATE) && DATA_MELATE.length) await saveModeDataToDB('melate', DATA_MELATE);
        if (Array.isArray(DATA_REVANCHA) && DATA_REVANCHA.length) await saveModeDataToDB('revancha', DATA_REVANCHA);
      }
    } catch (err) {
      console.warn('No se pudo espejear Pakin a IndexedDB:', err);
    }
  }

  function hideManualCsvNoise() {
    ['csv-file', 'csv-file-melate', 'csv-file-revancha'].forEach(id => {
      const input = document.getElementById(id);
      if (!input) return;
      input.style.opacity = '0.45';
      input.title = 'Opcional: Pakin remoto se carga automáticamente al abrir la web.';
    });
    const histPanel = document.querySelector('#tab-historial .card-body');
    if (histPanel && !document.getElementById('pakin-remote-banner')) {
      const banner = document.createElement('div');
      banner.id = 'pakin-remote-banner';
      banner.style.cssText = 'border:1px solid var(--teal);background:rgba(57,208,194,.08);color:var(--teal);padding:10px;border-radius:8px;font-size:12px;margin-bottom:10px;';
      banner.innerHTML = '🌐 Fuente automática activa: <b>pakinja/pakin</b>. La carga manual de CSV queda como respaldo opcional.';
      histPanel.prepend(banner);
    }
  }

  async function loadPakinRemoteData(force = false) {
    if (STATE.loading) return STATE;
    if (STATE.loaded && !force) return STATE;
    STATE.loading = true;
    STATE.errors = [];
    setStatus('🌐 Descargando históricos desde Pakin...', 'info');

    try {
      const [melate, revancha] = await Promise.all([
        fetchTextWithFallback(PAKIN_SOURCES.melate),
        fetchTextWithFallback(PAKIN_SOURCES.revancha)
      ]);

      const melateRows = parseRemoteCsv('melate', melate.text);
      const revanchaRows = parseRemoteCsv('revancha', revancha.text);

      if (!melateRows.length && !revanchaRows.length) throw new Error('Pakin descargó, pero no se detectaron filas válidas.');

      applyRowsWithoutManualCsv(melateRows, revanchaRows);
      await mirrorToIndexedDbForCompatibility();
      STATE.loaded = true;
      STATE.loading = false;

      setStatus(`✅ Pakin remoto activo: ${STATE.revanchaRows} Revancha / ${STATE.melateRows} Melate. Fuente común para todos los dispositivos.`, 'ok');
      hideManualCsvNoise();

      if (typeof rebuildAll === 'function') rebuildAll();
      if (typeof renderDbStatusUI === 'function') {
        // Reescribir después de renderDbStatusUI para que el usuario vea la fuente remota.
        setTimeout(() => setStatus(`✅ Pakin remoto activo: ${STATE.revanchaRows} Revancha / ${STATE.melateRows} Melate. Fuente común para todos los dispositivos.`, 'ok'), 150);
      }
      if (typeof showToast === 'function') showToast(`🌐 Pakin cargado: ${STATE.revanchaRows} Revancha / ${STATE.melateRows} Melate`);
      document.dispatchEvent(new CustomEvent('melate:pakin-remote-loaded', { detail: STATE }));
      return STATE;
    } catch (err) {
      STATE.loading = false;
      setStatus(`⚠️ No se pudo leer Pakin remoto. Usando datos locales/cache. ${err.message}`, 'warn');
      console.warn('Pakin remote loader failed:', err, STATE.errors);
      return STATE;
    }
  }

  window.loadPakinRemoteData = loadPakinRemoteData;

  function boot() {
    hideManualCsvNoise();
    // Dar tiempo a initLocalDatabase/ui.js. Luego Pakin sobreescribe como fuente de verdad.
    setTimeout(() => loadPakinRemoteData(false), 350);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
