// v4-combo-comparator.js
// Temporary local comparator for personal V4.2 combo analysis.
(function () {
  'use strict';

  const STORAGE_KEY = 'fisicapapa:v42:combo-comparator';
  const MAX_ITEMS = 5;
  const $ = id => document.getElementById(id);
  const finite = value => Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => finite(value) ? Number(value).toFixed(digits) : 'N/D';
  const esc = value => String(value ?? 'N/D').replace(/[&<>"']/g, mark => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[mark]));
  const comboNumbers = input => (window.normalizeComboV4 ? window.normalizeComboV4(input) : (Array.isArray(input) ? input : []))
    .map(Number)
    .filter(n => Number.isInteger(n))
    .sort((a, b) => a - b);

  let items = [];

  function jsonData() {
    return window.FISICAPAPA_WEB_V2?.jsonData || null;
  }

  function readItems() {
    try {
      const parsed = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]');
      items = Array.isArray(parsed) ? parsed.slice(0, MAX_ITEMS) : [];
    } catch (_) {
      items = [];
    }
  }

  function writeItems() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.slice(0, MAX_ITEMS)));
  }

  function currentManualNumbers() {
    return [1, 2, 3, 4, 5, 6].map(i => Number($(`manual-n${i}`)?.value));
  }

  function evaluate(nums) {
    const data = jsonData();
    if (!data || typeof window.evaluateManualComboV4 !== 'function') return null;
    try {
      const evaluation = window.evaluateManualComboV4(nums, data);
      const compare = typeof window.compareCruncherVsWebScore === 'function'
        ? window.compareCruncherVsWebScore(nums, data)
        : { foundInPool: false, cruncherScore: null, webScore: evaluation.netScoreV4, delta: null, scaleDetected: 'unknown', interpretation: 'Comparacion no disponible.' };
      const profile = typeof window.getComboProfileV4 === 'function' ? window.getComboProfileV4(evaluation, data) : [];
      const under40 = typeof window.computeUnder40Pressure === 'function' ? window.computeUnder40Pressure(data, nums) : null;
      return { evaluation, compare, profile, under40 };
    } catch (err) {
      return { error: err.message };
    }
  }

  function scoreOf(item, key) {
    const result = evaluate(item.numbers);
    if (!result || result.error) return -Infinity;
    if (key === 'total') return Number(result.evaluation.netScoreV4);
    if (key === 'cruncher') return finite(result.compare.cruncherScore) ? Number(result.compare.cruncherScore) : -Infinity;
    if (key === 'model') return Number(result.evaluation.summary.modelScore);
    if (key === 'structure') return Number(result.evaluation.summary.structuralBalance);
    if (key === 'physics') return Number(result.evaluation.summary.gravityPhysics);
    if (key === 'pool') return Number(result.evaluation.summary.poolAlignment);
    return -Infinity;
  }

  function winner(key) {
    if (!items.length) return null;
    return items.slice().sort((a, b) => scoreOf(b, key) - scoreOf(a, key))[0] || null;
  }

  function conclusion() {
    if (items.length < 2) return 'Guarda al menos dos combinaciones para comparar.';
    const total = winner('total');
    const model = winner('model');
    const physics = winner('physics');
    const structure = winner('structure');
    if (!total) return 'No hay evaluaciones validas.';
    if (total.id === model?.id && total.id === physics?.id && total.id === structure?.id) {
      return `${total.label} gana globalmente y tambien se sostiene por modelo, fisica y estructura.`;
    }
    const notes = [];
    if (model && model.id !== total.id) notes.push(`${model.label} gana por modelo`);
    if (physics && physics.id !== total.id) notes.push(`${physics.label} gana por fisica`);
    if (structure && structure.id !== total.id) notes.push(`${structure.label} gana por estructura`);
    return `${total.label} gana por Score Neto V4 web. ${notes.join('; ') || 'No hay una ventaja secundaria clara.'}.`;
  }

  function badgeHtml(badge) {
    const tone = {
      cyan: 'border-cyan-300/30 bg-cyan-400/10 text-cyan-100',
      emerald: 'border-emerald-300/30 bg-emerald-400/10 text-emerald-100',
      violet: 'border-violet-300/30 bg-violet-400/10 text-violet-100',
      amber: 'border-amber-300/30 bg-amber-400/10 text-amber-100',
      red: 'border-red-300/30 bg-red-500/10 text-red-100',
      slate: 'border-slate-600 bg-slate-800/80 text-slate-100',
    }[badge.tone] || 'border-slate-600 bg-slate-800/80 text-slate-100';
    return `<span class="rounded-full border ${tone} px-3 py-1 text-xs font-bold">${esc(badge.label)}</span>`;
  }

  function renderMetric(label, value, tone) {
    return `<div class="quant-metric component-meter rounded-xl border border-slate-800 bg-slate-950/50 p-3">
      <p class="text-[10px] uppercase tracking-[0.18em] text-slate-500">${esc(label)}</p>
      <p class="mt-1 text-sm font-black ${tone}">${fmt(value)}</p>
    </div>`;
  }

  function showNotice(message, tone = 'amber') {
    const panel = $('combo-comparator-panel');
    if (!panel) return;
    const existing = $('combo-comparator-notice');
    if (existing) existing.remove();
    const cls = tone === 'red'
      ? 'border-red-400/40 bg-red-500/10 text-red-100'
      : 'border-amber-400/40 bg-amber-500/10 text-amber-100';
    const node = document.createElement('div');
    node.id = 'combo-comparator-notice';
    node.className = `rounded-2xl border ${cls} p-4 text-sm font-bold`;
    node.textContent = message;
    panel.prepend(node);
  }

  function render() {
    const panel = $('combo-comparator-panel');
    if (!panel) return;
    if (!items.length) {
      panel.innerHTML = '<div class="comparator-board-empty rounded-2xl border border-slate-800 bg-slate-900/70 p-4 text-sm text-slate-300">Aun no hay combinaciones guardadas. Evalua una manual o guarda una top combination.</div>';
      return;
    }
    const winTotal = winner('total');
    const winModel = winner('model');
    const winStructure = winner('structure');
    const winPhysics = winner('physics');
    const winPool = winner('pool');
    panel.innerHTML = `
      <div class="winner-ribbon rounded-2xl border border-violet-400/20 bg-violet-400/10 p-4">
        <p class="text-xs uppercase tracking-[0.22em] text-violet-200">Conclusion humana</p>
        <p class="mt-2 text-sm font-bold text-violet-50">${esc(conclusion())}</p>
        <p class="mt-2 text-xs text-violet-100/80">Ganadoras: general ${esc(winTotal?.label)} | modelo ${esc(winModel?.label)} | estructura ${esc(winStructure?.label)} | fisica ${esc(winPhysics?.label)} | pool ${esc(winPool?.label)}.</p>
      </div>
      <div class="comparator-card-grid grid gap-3 lg:grid-cols-2">
        ${items.map(item => {
          const result = evaluate(item.numbers);
          if (!result || result.error) {
            return `<article class="decision-card rounded-2xl border border-red-400/30 bg-red-500/10 p-4 text-sm text-red-100">${esc(item.label)}: ${esc(result?.error || 'No evaluable')}</article>`;
          }
          const s = result.evaluation.summary;
          return `<article class="decision-card comparator-combo-card rounded-2xl border border-slate-800 bg-slate-900/70 p-4">
            <div class="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p class="text-xs uppercase tracking-[0.22em] text-slate-500">${esc(item.label)}</p>
                <div class="combo-ball-row mt-2">${item.numbers.map(n => `<span class="quant-number-ball">${n}</span>`).join('')}</div>
              </div>
              <button class="min-h-[44px] rounded-xl border border-red-300/30 bg-red-500/10 px-3 py-2 text-xs font-bold text-red-100" data-remove-combo="${esc(item.id)}">Quitar</button>
            </div>
            <div class="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4">
              ${renderMetric('Score web', result.evaluation.netScoreV4, 'text-cyan-200')}
              ${renderMetric('Cruncher', result.compare.cruncherScore, 'text-amber-200')}
              ${renderMetric('Modelo', s.modelScore, 'text-cyan-200')}
              ${renderMetric('Estructura', s.structuralBalance, 'text-violet-200')}
              ${renderMetric('Fisica', s.gravityPhysics, 'text-emerald-200')}
              ${renderMetric('Pool', s.poolAlignment, 'text-amber-200')}
              ${renderMetric('Conteo <40', result.under40?.userUnder40, 'text-slate-200')}
              ${renderMetric('Delta web/cruncher', result.compare.delta, 'text-slate-200')}
            </div>
            <p class="mt-3 text-xs text-slate-400">${esc(result.compare.interpretation)}</p>
            <div class="mt-3 flex flex-wrap gap-2">${result.profile.map(badgeHtml).join('')}</div>
          </article>`;
        }).join('')}
      </div>`;
    panel.querySelectorAll('[data-remove-combo]').forEach(button => {
      button.addEventListener('click', () => {
        items = items.filter(item => item.id !== button.getAttribute('data-remove-combo'));
        writeItems();
        render();
      });
    });
  }

  function saveCombo(nums, label) {
    const numbers = comboNumbers(nums);
    if (numbers.length !== 6 || new Set(numbers).size !== 6 || numbers.some(n => n < 1 || n > 56)) return false;
    const key = numbers.join('-');
    items = items.filter(item => item.key !== key);
    items.unshift({
      id: `${Date.now()}-${key}`,
      key,
      label: label || `Combo ${items.length + 1}`,
      numbers,
      savedAt: new Date().toISOString(),
    });
    items = items.slice(0, MAX_ITEMS);
    writeItems();
    render();
    return true;
  }

  function clear() {
    items = [];
    writeItems();
    render();
  }

  function report() {
    if (!items.length) return 'Comparador V4.2 sin combinaciones guardadas.';
    const lines = ['Reporte comparador personal V4.2', conclusion(), ''];
    items.forEach(item => {
      const result = evaluate(item.numbers);
      if (!result || result.error) {
        lines.push(`${item.label}: ${item.numbers.join(' ')} | error: ${result?.error || 'No evaluable'}`);
        return;
      }
      const s = result.evaluation.summary;
      lines.push(`${item.label}: ${item.numbers.join(' ')}`);
      lines.push(`Score web ${fmt(result.evaluation.netScoreV4)} | cruncher ${fmt(result.compare.cruncherScore)} | delta ${fmt(result.compare.delta)}`);
      lines.push(`Modelo ${fmt(s.modelScore)} | estructura ${fmt(s.structuralBalance)} | fisica ${fmt(s.gravityPhysics)} | pool ${fmt(s.poolAlignment)}`);
      lines.push(`Perfil: ${result.profile.map(badge => badge.label).join(', ') || 'N/D'}`);
      lines.push('');
    });
    lines.push('Nota: scores internos de analisis; no son probabilidad garantizada de ganar.');
    return lines.join('\n');
  }

  async function copyReport() {
    const text = report();
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
    }
    return text;
  }

  function bind() {
    $('btn-save-current-combo')?.addEventListener('click', () => {
      if (!saveCombo(currentManualNumbers(), 'Manual actual')) {
        showNotice('Ingresa 6 numeros validos y sin repetir antes de guardar la combinacion actual.', 'red');
      }
    });
    $('btn-clear-comparator')?.addEventListener('click', clear);
    $('btn-copy-comparator-report')?.addEventListener('click', () => {
      copyReport().catch(err => console.warn('[V4 comparator] No se pudo copiar reporte:', err));
    });
  }

  document.addEventListener('DOMContentLoaded', () => {
    readItems();
    bind();
    setTimeout(render, 500);
  });
  document.addEventListener('fisicapapa:v42-ready', () => {
    readItems();
    render();
  });

  window.FISICAPAPA_COMPARATOR = { saveCombo, clear, render, report, copyReport };
})();
