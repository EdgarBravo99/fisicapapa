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
    errors: [],
    sourceUrls: {}
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

  function splitCsvLine(line, delimiter) {
    const out = [];
    let cur = '';
    let quoted = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        quoted = !quoted;
      } else if (ch === delimiter && !quoted) {
        out.push(cur.trim().replace(/^"|"$/g, ''));
        cur = '';
      } else {
        cur += ch;
      }
    }
    out.push(cur.trim().replace(/^"|"$/g, ''));
    return out;
  }

  function normalizeHeader(h) {
    return String(h || '')
      .trim()
      .toUpperCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^A-Z0-9_]/g, '');
  }

  function parseDateCell(value) {
    const s = String(value || '').trim();
    if (!s) return '';
    const iso = s.match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (iso) return `${iso[3]}/${iso[2]}/${iso[1]}`;
    const slash = s.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
    if (slash) return `${slash[1].padStart(2, '0')}/${slash[2].padStart(2, '0')}/${slash[3]}`;
    return s;
  }

  function validNums(nums) {
    return nums.length === 6 && new Set(nums).size === 6 && nums.every(n => Number.isInteger(n) && n >= 1 && n <= 56);
  }

  function parsePakinHeaderCsv(mode, text) {
    const cleaned = String(text || '').replace(/^\uFEFF/, '').replace(/\r/g, '').trim();
    if (!cleaned) return [];
    const lines = cleaned.split('\n').filter(Boolean);
    if (lines.length < 2) return [];
    const delimiter = lines[0].includes(';') && !lines[0].includes(',') ? ';' : ',';
    const headers = splitCsvLine(lines[0], delimiter).map(normalizeHeader);
    const col = name => headers.indexOf(normalizeHeader(name));
    const concursoIdx = Math.max(col('CONCURSO'), col('SORTEO'), col('DRAW'));
    const fechaIdx = Math.max(col('FECHA'), col('DATE'));

    // Pakin usa:
    // Melate:   CONCURSO,ID,R1,R2,R3,R4,R5,R6,R7,BOLSA,FECHA...
    // Revancha: CONCURSO,ID,R1,R2,R3,R4,R5,R6,BOLSA,FECHA...
    // Tomamos R1-R6 como naturales; R7 es adicional de Melate y se ignora aquí.
    let numberIdxs = ['R1', 'R2', 'R3', 'R4', 'R5', 'R6'].map(col);
    if (numberIdxs.some(i => i < 0)) {
      numberIdxs = ['N1', 'N2', 'N3', 'N4', 'N5', 'N6'].map(col);
    }
    if (concursoIdx < 0 || numberIdxs.some(i => i < 0)) return [];

    const rows = [];
    for (let i = 1; i < lines.length; i++) {
      const cells = splitCsvLine(lines[i], delimiter);
      const draw = parseInt(cells[concursoIdx], 10);
      const date = fechaIdx >= 0 ? parseDateCell(cells[fechaIdx]) : '';
      const nums = numberIdxs.map(idx => parseInt(cells[idx], 10)).filter(n => Number.isFinite(n));
      if (!Number.isFinite(draw) || !validNums(nums)) continue;
      rows.push([draw, date, ...nums]);
    }
    rows.sort((a, b) => Number(b[0]) - Number(a[0]));
    return rows;
  }

  function parseRemoteCsv(mode, text) {
    const pakinRows = parsePakinHeaderCsv(mode, text);
    if (pakinRows.length > 42) return pakinRows;

    // Fallback al parser viejo para CSV dual/local.
    if (typeof parseCsvText === 'function') {
      const parsed = parseCsvText(text, mode);
      const rows = mode === 'melate' ? (parsed.newMelate || []) : (parsed.newRevancha || []);
      return (rows || [])
        .filter(r => Array.isArray(r) && r.length >= 8)
        .sort((a, b) => Number(b[0]) - Number(a[0]));
    }
    return pakinRows;
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

  function forceRenderAfterRemoteLoad() {
    try {
      if (typeof rebuildAll === 'function') rebuildAll();
      if (typeof renderHistoryUI === 'function') renderHistoryUI();
      if (typeof renderDbStatusUI === 'function') renderDbStatusUI();
      if (typeof renderHeatmapUI === 'function') renderHeatmapUI();
      if (typeof renderStatsUI === 'function') renderStatsUI();
    } catch (err) {
      console.warn('Render post-Pakin incompleto:', err);
    }
    setTimeout(() => {
      setStatus(`✅ Pakin remoto activo: ${STATE.revanchaRows} Revancha / ${STATE.melateRows} Melate. Últimos: R ${DATA_REVANCHA?.[0]?.[0] || 'N/A'} · M ${DATA_MELATE?.[0]?.[0] || 'N/A'}.`, 'ok');
      const count = document.getElementById('drawCount');
      if (count) count.textContent = `${CURRENT_MODE === 'melate' ? STATE.melateRows : STATE.revanchaRows} SORTEOS`;
    }, 220);
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

      STATE.sourceUrls = { melate: melate.url, revancha: revancha.url };
      const melateRows = parseRemoteCsv('melate', melate.text);
      const revanchaRows = parseRemoteCsv('revancha', revancha.text);

      if (melateRows.length <= 42 && revanchaRows.length <= 42) {
        throw new Error(`Pakin descargó, pero el parser solo detectó ${revanchaRows.length} Revancha / ${melateRows.length} Melate.`);
      }

      applyRowsWithoutManualCsv(melateRows, revanchaRows);
      STATE.loaded = true;
      STATE.loading = false;
      hideManualCsvNoise();
      forceRenderAfterRemoteLoad();

      // Guardar en IndexedDB después de pintar; en móvil puede tardar y no debe bloquear UI.
      setTimeout(() => mirrorToIndexedDbForCompatibility(), 50);

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
    setTimeout(() => loadPakinRemoteData(true), 350);
    // Segundo intento para móviles/Safari cuando la primera carga compite con IndexedDB.
    setTimeout(() => {
      if (!STATE.loaded || STATE.revanchaRows <= 42 || STATE.melateRows <= 42) loadPakinRemoteData(true);
    }, 1800);
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
