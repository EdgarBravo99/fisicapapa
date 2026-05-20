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

  async function loadMemory() {
    try {
      const response = await fetch(`v4_feedback_memory.json?memory=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) return null;
      return response.json();
    } catch (_) {
      return null;
    }
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

  function renderEmpty(jsonData) {
    const node = $('feedback-memory-panel');
    if (!node) return;
    const exported = jsonData?.feedback_memory;
    node.innerHTML = `
      <div class="taste-card-heading">
        <div>
          <p class="taste-eyebrow">Memoria de predicciones</p>
          <h3>Aun no hay examenes calificados</h3>
        </div>
        <span class="taste-chip taste-chip-warn">Pendiente</span>
      </div>
      <p class="mt-3 text-sm leading-6 text-slate-300">Se generara cuando el runner califique un resultados.json anterior contra un sorteo real ya revelado en el CSV.</p>
      <div class="bento-status-grid mt-4">
        <article class="taste-metric"><span>Records usados</span><b>${fmt(exported?.records_used, 0)}</b></article>
        <article class="taste-metric"><span>Ajuste</span><b>${esc(exported?.adjustment_mode || 'diagnostico pendiente')}</b></article>
      </div>
      <div class="taste-panel-muted mt-4">
        <p class="taste-eyebrow">Anti-leakage</p>
        <p>resultados.json historico es prediccion pasada. La verdad revelada vive en el CSV actualizado.</p>
      </div>
      <a class="taste-ghost mt-4" href="${HISTORY_URL}" target="_blank" rel="noopener">Ver historial resultados.json</a>`;
  }

  function renderMemory(memory, jsonData) {
    const node = $('feedback-memory-panel');
    if (!node) return;
    if (!memory || !Array.isArray(memory.records) || !memory.records.length) {
      renderEmpty(jsonData);
      return;
    }
    const aggregate = memory.aggregate || {};
    const exported = jsonData?.feedback_memory || {};
    const last = latestRecord(memory) || {};
    const over = Object.entries(aggregate.overestimated_numbers || {});
    const under = Object.entries(aggregate.underestimated_numbers || {});
    node.innerHTML = `
      <div class="taste-card-heading">
        <div>
          <p class="taste-eyebrow">Memoria de predicciones</p>
          <h3>Examenes calificados contra CSV real</h3>
        </div>
        <span class="taste-chip taste-chip-ok">${esc(exported.adjustment_mode || 'diagnostico')}</span>
      </div>
      <div class="bento-status-grid mt-4">
        <article class="taste-metric"><span>Records</span><b>${fmt(aggregate.records_count, 0)}</b></article>
        <article class="taste-metric"><span>Ultima prediccion</span><b>${esc(last.prediction_draw)}</b></article>
        <article class="taste-metric"><span>Ultimo real</span><b>${esc(last.target_draw)}</b></article>
        <article class="taste-metric"><span>Best hits</span><b>${fmt(aggregate.best_hits_seen, 0)}</b></article>
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
        <p class="taste-eyebrow">Nota anti-leakage</p>
        <p>${esc(exported.note || 'Esta memoria mide errores de predicciones pasadas; no es probabilidad garantizada.')}</p>
      </div>
      <a class="taste-ghost mt-4" href="${HISTORY_URL}" target="_blank" rel="noopener">Ver historial resultados.json</a>`;
  }

  async function render(jsonData) {
    const memory = await loadMemory();
    renderMemory(memory, jsonData || window.FISICAPAPA_WEB_V2?.jsonData || null);
  }

  document.addEventListener('fisicapapa:v42-ready', event => render(event.detail?.jsonData));
  document.addEventListener('DOMContentLoaded', () => setTimeout(() => render(window.FISICAPAPA_WEB_V2?.jsonData), 700));
  window.renderV4FeedbackMemoryPanel = render;
})();
