// v4-feedback-memory-panel.js
// Panel visual de memoria tipo examen y enlace al historial real de resultados.json.
(function () {
  'use strict';

  const HISTORY_URL = 'https://github.com/EdgarBravo99/fisicapapa/commits/main/resultados.json';
  const $ = id => document.getElementById(id);
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => finite(value) ? Number(value).toFixed(digits) : 'N/D';
  const esc = value => String(value ?? 'N/D').replace(/[&<>"']/g, mark => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[mark]));

  async function loadJson(path, cacheKey) {
    try {
      const response = await fetch(`${path}?${cacheKey}=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) return null;
      return response.json();
    } catch (_) {
      return null;
    }
  }

  async function loadMemory() {
    return loadJson('v4_feedback_memory.json', 'memory');
  }

  async function loadArchiveIndex() {
    return loadJson('resultados_archive/index.json', 'archive');
  }

  async function loadHistoryAnalysis() {
    return loadJson('v4_history_analysis.json', 'analysis');
  }

  async function loadReplayMemory() {
    return loadJson('v4_replay_memory.json', 'replayMemory');
  }

  async function loadReplayAnalysis() {
    return loadJson('v4_replay_analysis.json', 'replayAnalysis');
  }

  async function loadLegacyReport() {
    return loadJson('v4_legacy_snapshot_report.json', 'legacyReport');
  }

  function topList(items, emptyText) {
    if (!Array.isArray(items) || !items.length) {
      return `<p class="text-sm text-slate-400">${esc(emptyText)}</p>`;
    }
    return `<div class="grid gap-2">${items.slice(0, 5).map(([number, row]) => `
      <div class="taste-panel-muted flex items-center justify-between gap-3">
        <span class="taste-ball quant-number-ball">${esc(number)}</span>
        <span class="font-mono text-sm text-slate-200">error ${fmt(row?.avg_error)}</span>
      </div>`).join('')}</div>`;
  }

  function latestRecord(memory) {
    const records = Array.isArray(memory?.records) ? memory.records : [];
    return records.length ? records[records.length - 1] : null;
  }

  function statusChip(exported, analysis) {
    if (exported?.memory_prior_applied === true) {
      return '<span class="taste-chip taste-chip-ok">prior aplicado antes de Monte Carlo</span>';
    }
    if (exported?.adjustment_mode === 'pre_monte_carlo_memory_prior') {
      return '<span class="taste-chip taste-chip-warn">prior elegible</span>';
    }
    if (analysis?.summary?.snapshots_imported) {
      return '<span class="taste-chip taste-chip-warn">prior no aplicado</span>';
    }
    return '<span class="taste-chip taste-chip-warn">Sin historico importado</span>';
  }

  function renderReplayAndLegacy(replayMemory, replayAnalysis, legacyReport) {
    const replayAggregate = replayMemory?.aggregate || {};
    const replayAudit = replayAnalysis?.replay_prior_audit || {};
    const legacyRows = Array.isArray(legacyReport?.snapshots) ? legacyReport.snapshots : [];
    const legacyHindsight = legacyRows.filter(row => row?.classification === 'legacy_hindsight_snapshot');
    const sampleLegacy = legacyHindsight.find(row => String(row?.detected_draw) === '4212') || legacyHindsight[0] || null;
    const replayRecords = finite(replayAggregate.records_count) ? replayAggregate.records_count : (Array.isArray(replayMemory?.records) ? replayMemory.records.length : 0);
    const replayStatus = replayRecords > 0
      ? 'Replay prior calculado, no aplicado'
      : 'Replay pendiente; ejecuta el lab historico para generar examenes anti-leakage.';
    return `
      <div class="grid gap-3 mt-4 lg:grid-cols-2">
        <article class="taste-panel-muted">
          <p class="taste-eyebrow">Replay Memory</p>
          <h4 class="mt-1 text-lg font-black text-slate-100">${esc(replayStatus)}</h4>
          <div class="bento-status-grid mt-3">
            <article class="taste-metric"><span>Records replay</span><b>${fmt(replayRecords, 0)}</b></article>
            <article class="taste-metric"><span>Leakage OK</span><b>${fmt(replayAggregate.leakage_passed_count, 0)}</b></article>
            <article class="taste-metric"><span>Fuerza shadow</span><b>${fmt(replayAudit.max_number_adjustment, 3)}</b></article>
            <article class="taste-metric"><span>Aplicado</span><b>No</b></article>
          </div>
          <p class="mt-3 text-xs leading-5 text-slate-400">El replay usa CSV temporal truncado y motor principal. Por defecto solo calcula shadow prior.</p>
        </article>
        <article class="taste-panel-muted">
          <p class="taste-eyebrow">Legacy Snapshots</p>
          <h4 class="mt-1 text-lg font-black text-slate-100">${sampleLegacy ? `Legacy ${esc(sampleLegacy.detected_draw || 'N/D')} detectado` : 'Sin legacy hindsight detectado'}</h4>
          <div class="bento-status-grid mt-3">
            <article class="taste-metric"><span>Hindsight</span><b>${fmt(legacyHindsight.length, 0)}</b></article>
            <article class="taste-metric"><span>Elegibles prior</span><b>${fmt(legacyReport?.summary?.eligible_for_prior, 0)}</b></article>
          </div>
          <p class="mt-3 text-xs leading-5 text-slate-400">${sampleLegacy ? 'No elegible por contener auditoria inversa / combinacion real.' : 'Los snapshots legacy se muestran solo como diagnostico.'}</p>
        </article>
      </div>`;
  }

  function renderEmpty(jsonData, archiveIndex, analysis, replayMemory, replayAnalysis, legacyReport) {
    const node = $('feedback-memory-panel');
    if (!node) return;
    const exported = jsonData?.feedback_memory;
    const entries = Array.isArray(archiveIndex?.entries) ? archiveIndex.entries : [];
    const summary = analysis?.summary || {};
    node.innerHTML = `
      <div class="taste-card-heading">
        <div>
          <p class="taste-eyebrow">Memoria inteligente</p>
          <h3>Prior no aplicado</h3>
        </div>
        ${statusChip(exported, analysis)}
      </div>
      <p class="mt-3 text-sm leading-6 text-slate-300">El runner puede importar historico Git y calificarlo contra CSV revelado. Si falta evidencia real suficiente, solo se muestra diagnostico.</p>
      <div class="bento-status-grid mt-4">
        <article class="taste-metric"><span>Snapshots indexados</span><b>${fmt(entries.length, 0)}</b></article>
        <article class="taste-metric"><span>Records reales</span><b>${fmt(summary.records_real_used ?? exported?.valid_real_records_used, 0)}</b></article>
        <article class="taste-metric"><span>Omitidos</span><b>${fmt(summary.snapshots_omitted, 0)}</b></article>
        <article class="taste-metric"><span>Ajuste</span><b>${esc(exported?.adjustment_mode || 'diagnostico pendiente')}</b></article>
      </div>
      <div class="taste-panel-muted mt-4">
        <p class="taste-eyebrow">Anti-leakage</p>
        <p>resultados.json historico es prediccion pasada. La verdad revelada vive en el CSV actualizado.</p>
      </div>
      ${renderReplayAndLegacy(replayMemory, replayAnalysis, legacyReport)}
      <a class="taste-ghost mt-4" href="${HISTORY_URL}" target="_blank" rel="noopener">Ver historial resultados.json</a>`;
  }

  function renderMemory(memory, jsonData, archiveIndex, analysis, replayMemory, replayAnalysis, legacyReport) {
    const node = $('feedback-memory-panel');
    if (!node) return;
    if (!memory || !Array.isArray(memory.records) || !memory.records.length) {
      renderEmpty(jsonData, archiveIndex, analysis, replayMemory, replayAnalysis, legacyReport);
      return;
    }
    const aggregate = memory.aggregate || {};
    const exported = jsonData?.feedback_memory || {};
    const audit = jsonData?.memory_prior_audit || {};
    const summary = analysis?.summary || jsonData?.history_analysis_summary || {};
    const entries = Array.isArray(archiveIndex?.entries) ? archiveIndex.entries : [];
    const last = latestRecord(memory) || {};
    const over = Object.entries(aggregate.overestimated_numbers || {});
    const under = Object.entries(aggregate.underestimated_numbers || {});
    node.innerHTML = `
      <div class="taste-card-heading">
        <div>
          <p class="taste-eyebrow">Memoria de predicciones</p>
          <h3>Examenes calificados contra CSV real</h3>
        </div>
        ${statusChip(exported, analysis)}
      </div>
      <div class="bento-status-grid mt-4">
        <article class="taste-metric"><span>Records</span><b>${fmt(aggregate.records_count, 0)}</b></article>
        <article class="taste-metric"><span>Records reales</span><b>${fmt(aggregate.valid_real_records_count ?? exported.valid_real_records_used, 0)}</b></article>
        <article class="taste-metric"><span>Snapshots</span><b>${fmt(entries.length, 0)}</b></article>
        <article class="taste-metric"><span>Fuerza</span><b>${fmt(exported.memory_strength ?? audit.memory_strength, 2)}</b></article>
        <article class="taste-metric"><span>Ultima prediccion</span><b>${esc(last.prediction_draw)}</b></article>
        <article class="taste-metric"><span>Ultimo real</span><b>${esc(last.target_draw)}</b></article>
        <article class="taste-metric"><span>Best hits</span><b>${fmt(aggregate.best_hits_seen, 0)}</b></article>
        <article class="taste-metric"><span>Omitidos</span><b>${fmt(summary.snapshots_omitted, 0)}</b></article>
      </div>
      <div class="grid gap-3 mt-4 lg:grid-cols-2">
        <article class="taste-panel-muted">
          <p class="taste-eyebrow">Sobreestimados</p>
          <div class="mt-3">${topList(over, 'Sin sobreestimados recurrentes.')}</div>
        </article>
        <article class="taste-panel-muted">
          <p class="taste-eyebrow">Subestimados</p>
          <div class="mt-3">${topList(under, 'Sin subestimados recurrentes.')}</div>
        </article>
      </div>
      <div class="taste-panel-muted mt-4">
        <p class="taste-eyebrow">Impacto del prior</p>
        <p>${exported.memory_prior_applied === true ? 'Prior aplicado antes de Monte Carlo.' : 'Prior no aplicado; la memoria quedo en diagnostico.'}</p>
        <p class="mt-2 text-xs text-slate-400">Cambios por numero: ${fmt(exported.before_after_summary?.number_scores_changed ?? audit.number_prior?.length, 0)} · max delta ${fmt(exported.before_after_summary?.max_delta_seen, 6)}</p>
      </div>
      <div class="taste-panel-muted mt-4">
        <p class="taste-eyebrow">Nota anti-leakage</p>
        <p>${esc(exported.note || 'Esta memoria mide errores de predicciones pasadas; no es probabilidad garantizada.')}</p>
      </div>
      ${renderReplayAndLegacy(replayMemory, replayAnalysis, legacyReport)}
      <a class="taste-ghost mt-4" href="${HISTORY_URL}" target="_blank" rel="noopener">Ver historial resultados.json</a>`;
  }

  async function render(jsonData) {
    const [memory, archiveIndex, analysis, replayMemory, replayAnalysis, legacyReport] = await Promise.all([
      loadMemory(),
      loadArchiveIndex(),
      loadHistoryAnalysis(),
      loadReplayMemory(),
      loadReplayAnalysis(),
      loadLegacyReport(),
    ]);
    renderMemory(memory, jsonData || window.FISICAPAPA_WEB_V2?.jsonData || null, archiveIndex, analysis, replayMemory, replayAnalysis, legacyReport);
  }

  document.addEventListener('fisicapapa:v42-ready', event => render(event.detail?.jsonData));
  document.addEventListener('DOMContentLoaded', () => setTimeout(() => render(window.FISICAPAPA_WEB_V2?.jsonData), 700));
  window.renderV4FeedbackMemoryPanel = render;
})();
