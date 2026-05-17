// v4-clean-app.js
// Web V2 foundation: V4.2-only strict validator.
(function () {
  'use strict';

  const REQUIRED_FEEDBACK_VERSION = 'V4.2';
  const REQUIRED_SOURCE_HINTS = ['v4_2', 'V4.2', 'oos_feedback'];

  const state = {
    jsonData: null,
    initialized: false,
  };

  const $ = id => document.getElementById(id);

  function text(id, value) {
    const el = $(id);
    if (el) el.textContent = value ?? '—';
  }

  function show(el) {
    if (el) el.classList.remove('hidden');
  }

  function hide(el) {
    if (el) el.classList.add('hidden');
  }

  function fmtDate(value) {
    if (!value) return 'Sin timestamp';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('es-MX', {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function normalizeGameMode(value) {
    const raw = String(value || '').toLowerCase();
    if (raw.includes('melate')) return 'Melate';
    if (raw.includes('revancha')) return 'Revancha';
    return value || 'No declarado';
  }

  function getFeedbackLoop(jsonData) {
    return jsonData?.feedback_loop || jsonData?.walk_forward?.feedback_loop || jsonData?.deep_stacking?.feedback_loop || null;
  }

  function isV42(jsonData) {
    const feedback = getFeedbackLoop(jsonData);
    const versionOk = feedback?.version === REQUIRED_FEEDBACK_VERSION;
    const source = [jsonData?.source, jsonData?.model_version, jsonData?.v4_score_kind, jsonData?.score_kind]
      .filter(Boolean)
      .join(' ');
    const sourceLooksV42 = REQUIRED_SOURCE_HINTS.some(hint => source.includes(hint));
    return Boolean(versionOk && sourceLooksV42);
  }

  function fatal(message, jsonData) {
    hide($('loading-panel'));
    hide($('dashboard'));
    const box = $('fatal-error');
    text('fatal-error-message', message);
    show(box);
    console.error('[Web V2] JSON rejected:', { message, jsonData });
    throw new Error(message);
  }

  function validateV42(jsonData) {
    if (!jsonData || typeof jsonData !== 'object') {
      fatal('resultados.json no contiene un objeto JSON válido. La Web V2 solo acepta salidas V4.2.', jsonData);
    }

    const feedback = getFeedbackLoop(jsonData);
    if (!feedback) {
      fatal('El JSON no trae feedback_loop ni walk_forward.feedback_loop. Ejecuta local_cruncher_v4_deep_stacking.py actualizado a V4.2 y vuelve a subir resultados.json.', jsonData);
    }

    if (feedback.version !== REQUIRED_FEEDBACK_VERSION) {
      fatal(`Versión de feedback_loop inválida: ${feedback.version || 'sin versión'}. Requerido: ${REQUIRED_FEEDBACK_VERSION}.`, jsonData);
    }

    if (!isV42(jsonData)) {
      fatal('El JSON declara feedback_loop V4.2, pero source/model_version/v4_score_kind no parecen pertenecer al motor V4.2 OOS Feedback Loop. Se detiene para evitar mezclar datos legacy.', jsonData);
    }

    return feedback;
  }

  function headerModelVersion(jsonData) {
    return jsonData?.model_version || jsonData?.source || 'V4.2';
  }

  function renderHeader(jsonData) {
    text('header-last-update', fmtDate(jsonData.last_update));
    text('header-game-mode', normalizeGameMode(jsonData.game_mode || jsonData.game_label));
    text('header-model-version', headerModelVersion(jsonData));
  }

  function renderKpis(jsonData, feedback) {
    const wf = jsonData.walk_forward || {};
    const pool = Array.isArray(jsonData.generator_pool) ? jsonData.generator_pool : [];
    text('kpi-score-kind', jsonData.v4_score_kind || jsonData.score_kind || 'No declarado');
    text('kpi-feedback-loop', `${feedback.version} · decay ${feedback.decay ?? '—'}`);
    text('kpi-walk-forward', `${wf.steps ?? wf.rows?.length ?? 0} folds · avg hits ${wf.avg_hits ?? '—'}`);
    text('kpi-generator-pool', `${pool.length} combos`);
  }

  function renderPreview(jsonData, feedback) {
    const preview = {
      accepted_contract: 'Web V2 / V4.2-only',
      source: jsonData.source,
      model_version: jsonData.model_version,
      score_kind: jsonData.score_kind,
      v4_score_kind: jsonData.v4_score_kind,
      feedback_loop: feedback,
      walk_forward_summary: {
        steps: jsonData.walk_forward?.steps,
        avg_hits: jsonData.walk_forward?.avg_hits,
        avg_hits_top10: jsonData.walk_forward?.avg_hits_top10,
        avg_mse: jsonData.walk_forward?.avg_mse,
      },
      generator_pool_size: Array.isArray(jsonData.generator_pool) ? jsonData.generator_pool.length : 0,
      top_combinations_size: Array.isArray(jsonData.top_combinations) ? jsonData.top_combinations.length : 0,
    };
    const el = $('contract-preview');
    if (el) el.textContent = JSON.stringify(preview, null, 2);
  }

  function initApp(jsonData) {
    const feedback = validateV42(jsonData);
    state.jsonData = jsonData;
    state.initialized = true;

    hide($('fatal-error'));
    hide($('loading-panel'));
    show($('dashboard'));

    renderHeader(jsonData);
    renderKpis(jsonData, feedback);
    renderPreview(jsonData, feedback);

    window.FISICAPAPA_WEB_V2 = {
      version: 'Web V2 foundation',
      requiredFeedbackVersion: REQUIRED_FEEDBACK_VERSION,
      jsonData,
      feedback,
      state,
    };
  }

  async function loadJsonAndInit() {
    hide($('fatal-error'));
    show($('loading-panel'));
    hide($('dashboard'));

    const response = await fetch(`resultados.json?v42=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) {
      fatal(`No se pudo cargar resultados.json. HTTP ${response.status}.`, null);
    }
    const jsonData = await response.json();
    initApp(jsonData);
  }

  function bindReload() {
    const btn = $('btn-reload-json');
    if (btn) btn.addEventListener('click', () => loadJsonAndInit().catch(err => fatal(err.message, null)));
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindReload();
    loadJsonAndInit().catch(err => fatal(err.message, null));
  });

  window.initApp = initApp;
})();
