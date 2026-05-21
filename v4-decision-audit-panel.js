// v4-decision-audit-panel.js
// Read-only V4.4 decision diagnostics: diversity, benchmark, and physics regime.
(function () {
  'use strict';

  const FILES = {
    diversity: 'v4_diversity_output.json',
    benchmark: 'v4_baseline_benchmark.json',
    physics: 'v4_physics_regime_analysis.json',
    candidatePool: 'v4_candidate_pool_audit.json',
    qualification: 'v4_replay_qualification.json',
    slate: 'v4_decision_slate.json',
  };

  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => finite(value) ? Number(value).toFixed(digits) : 'N/D';
  const text = value => {
    if (value === null || value === undefined || value === '' || Number.isNaN(value)) return 'N/D';
    return String(value);
  };
  const esc = value => text(value).replace(/[&<>"']/g, mark => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[mark]));

  async function loadJson(path) {
    try {
      const response = await fetch(`${path}?audit=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) return null;
      return response.json();
    } catch (_) {
      return null;
    }
  }

  function ensurePanel() {
    let panel = document.getElementById('decision-audit-panel');
    if (panel) return panel;
    const dashboard = document.getElementById('dashboard') || document.getElementById('app-root');
    if (!dashboard) {
      console.warn('[Fisicapapa] Decision Audit Panel could not mount: no dashboard container.');
      return null;
    }
    const section = document.createElement('section');
    section.id = 'decision-audit-section';
    section.className = 'taste-section taste-decision-audit';
    section.innerHTML = `
      <div class="taste-section-heading">
        <div>
          <p class="taste-eyebrow">Decision Audit Pack V4.4</p>
          <h2>Diversidad, benchmark y regimen fisico</h2>
        </div>
        <span class="taste-chip taste-chip-warn">diagnostic_only</span>
      </div>
      <div id="decision-audit-panel" class="taste-stack"></div>`;
    const auditor = document.getElementById('auditor-section');
    if (auditor?.parentNode) {
      auditor.parentNode.insertBefore(section, auditor);
    } else {
      dashboard.appendChild(section);
    }
    panel = document.getElementById('decision-audit-panel');
    return panel;
  }

  function emptyCard(title, body) {
    return `
      <article class="taste-panel-muted">
        <p class="taste-eyebrow">${esc(title)}</p>
        <p class="mt-2 text-sm leading-6 text-slate-400">${esc(body)}</p>
      </article>`;
  }

  function comboBalls(numbers) {
    if (!Array.isArray(numbers) || !numbers.length) return '<span class="text-sm text-slate-400">N/D</span>';
    return `<div class="flex flex-wrap gap-2">${numbers.map(number => `<span class="taste-ball quant-number-ball">${esc(number)}</span>`).join('')}</div>`;
  }

  function renderDiversity(data) {
    if (!data) {
      return emptyCard('Diversidad de combinaciones', 'Sin v4_diversity_output.json. Ejecuta el selector MMR para ver overlap y tickets diversificados.');
    }
    const combos = Array.isArray(data.diversified_combinations) ? data.diversified_combinations : [];
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Diversidad de combinaciones</p>
            <h3>Ranking diversificado</h3>
          </div>
          <span class="taste-chip taste-chip-warn">No es probabilidad de ganar</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Overlap original</span><b>${fmt(data.average_pairwise_jaccard_original, 3)}</b></article>
          <article class="taste-metric"><span>Overlap MMR</span><b>${fmt(data.average_pairwise_jaccard_diversified, 3)}</b></article>
          <article class="taste-metric"><span>Diversity gain</span><b>${fmt(data.diversity_gain, 3)}</b></article>
          <article class="taste-metric"><span>Unicos top/MMR</span><b>${fmt(data.unique_numbers_original_top_k, 0)} / ${fmt(data.unique_numbers_diversified, 0)}</b></article>
        </div>
        <div class="grid gap-3 mt-4">
          ${combos.slice(0, 5).map(combo => `
            <div class="taste-panel-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <span class="taste-chip">#${esc(combo.rank_diversified)} desde #${esc(combo.rank_original)}</span>
                <span class="font-mono text-xs text-slate-400">MMR ${fmt(combo.mmr_score, 3)}</span>
              </div>
              <div class="mt-3">${comboBalls(combo.numbers)}</div>
            </div>`).join('')}
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc((data.quality_notes || []).join(' ') || 'Ranking diversificado. No es probabilidad de ganar.')}</p>
      </article>`;
  }

  function renderCandidatePool(data) {
    if (!data) {
      return emptyCard('Candidate Pool', 'Sin v4_candidate_pool_audit.json. Si el pool es estrecho, MMR no puede crear diversidad real.');
    }
    const bestPool = data.best_available_pool || 'N/D';
    const best = data.pools_detected?.[bestPool] || {};
    const canImprove = data.can_improve_diversity_with_existing_data === true;
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Candidate Pool</p>
            <h3>${esc(bestPool)}</h3>
          </div>
          <span class="taste-chip ${canImprove ? 'taste-chip-ok' : 'taste-chip-warn'}">${canImprove ? 'pool util' : 'pool estrecho'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Pool size</span><b>${fmt(data.best_available_pool_size, 0)}</b></article>
          <article class="taste-metric"><span>Unicos</span><b>${fmt(best.unique_numbers, 0)}</b></article>
          <article class="taste-metric"><span>Jaccard</span><b>${fmt(best.average_pairwise_jaccard, 3)}</b></article>
          <article class="taste-metric"><span>Status</span><b>${esc(best.status || 'N/D')}</b></article>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Si el pool es estrecho, MMR no puede crear diversidad real. ${esc(data.reason)}</p>
      </article>`;
  }

  function baselineStatus(row, fallback) {
    if (!row) return esc(fallback);
    if (row.available === false) return `No disponible: ${esc(row.reason)}`;
    return `top10 ${fmt(row.top10_hit_rate, 4)} - hits ${fmt(row.frequency_baseline_hits ?? row.recency_baseline_hits, 3)}`;
  }

  function renderBenchmark(data) {
    if (!data) {
      return emptyCard('Benchmark ligero', 'Sin v4_baseline_benchmark.json. El benchmark debe seguir en diagnostic_only hasta medir replay contra baselines.');
    }
    const summary = data.benchmark_summary || {};
    const baselines = data.baselines || {};
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Benchmark ligero</p>
            <h3>Random / frecuencia / recencia</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${esc(summary.recommendation || 'diagnostic_only')}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Records</span><b>${fmt(data.records_count, 0)}</b></article>
          <article class="taste-metric"><span>Leakage OK</span><b>${fmt(data.leakage_passed_count, 0)}</b></article>
          <article class="taste-metric"><span>Signal</span><b>${esc(summary.signal_quality || 'unknown')}</b></article>
          <article class="taste-metric"><span>Top10 cruncher</span><b>${fmt(data.cruncher_metrics?.top10_hit_rate, 4)}</b></article>
        </div>
        <div class="grid gap-3 mt-4 lg:grid-cols-3">
          <div class="taste-panel-muted"><p class="taste-eyebrow">Random</p><p class="text-sm text-slate-300">hit ${fmt(baselines.random_uniform?.hit_rate_per_number, 4)}</p></div>
          <div class="taste-panel-muted"><p class="taste-eyebrow">Frecuencia</p><p class="text-sm text-slate-300">${baselineStatus(baselines.frequency_baseline, 'Sin baseline de frecuencia')}</p></div>
          <div class="taste-panel-muted"><p class="taste-eyebrow">Recencia</p><p class="text-sm text-slate-300">${baselineStatus(baselines.recency_baseline, 'Sin baseline de recencia')}</p></div>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Benchmark diagnostico. No activa prior. Brier desactivado: ${esc(data.experimental_brier?.reason || 'Scores internos no son probabilidades calibradas.')}</p>
      </article>`;
  }

  function renderPhysics(data) {
    if (!data) {
      return emptyCard('Evento fisico / regimen', 'Sin v4_physics_regime_analysis.json. El tracker fisico es diagnostico y no ajusta el cruncher.');
    }
    const event = data.latest_event || {};
    const metrics = data.latest_metrics || {};
    const timing = data.regime_timing || {};
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Evento fisico / regimen</p>
            <h3>4215 sospechoso, no confirmado</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${esc(event.status || 'hypothesis_not_confirmed')}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Ultimo draw</span><b>${esc(data.latest_draw)}</b></article>
          <article class="taste-metric"><span>Severidad</span><b>${esc(event.severity || 'N/D')}</b></article>
          <article class="taste-metric"><span>Bloque 33-56 delta</span><b>${fmt(metrics.block_33_56_minus_global, 4)}</b></article>
          <article class="taste-metric"><span>Periodicidad</span><b>${timing.can_estimate_periodicity ? 'estimable' : 'no estimable'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Evidencia</p>
          <ul class="mt-2 grid gap-1 text-sm leading-6 text-slate-300">
            ${(event.evidence || []).map(item => `<li>${esc(item)}</li>`).join('') || '<li>N/D</li>'}
          </ul>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Evento fisico sospechoso, no confirmado. No ajusta el cruncher. ${esc(timing.reason || '')}</p>
      </article>`;
  }

  function renderQualification(data) {
    if (!data) {
      return emptyCard('Replay Qualification', 'Sin v4_replay_qualification.json. Replay Qualification Gate. No activa prior.');
    }
    const canInfluence = data.can_influence_future_prior === true;
    const eligible = data.eligible_for_future_experiment === true;
    const gates = data.gates || {};
    const missing = Array.isArray(data.required_next_evidence) ? data.required_next_evidence : [];
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Replay Qualification</p>
            <h3>${eligible ? 'Elegible para experimento futuro' : 'Replay bloqueado'}</h3>
          </div>
          <span class="taste-chip ${canInfluence ? 'taste-chip-ok' : 'taste-chip-warn'}">${canInfluence ? 'elegible' : 'diagnostico'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Influye prior</span><b>${canInfluence ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Experimento</span><b>${eligible ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Ranking</span><b>${gates.ranking_quality_ok ? 'OK' : 'bloqueado'}</b></article>
          <article class="taste-metric"><span>Benchmark</span><b>${gates.benchmark_ok ? 'OK' : 'bloqueado'}</b></article>
          <article class="taste-metric"><span>Diversidad</span><b>${gates.diversity_ok ? 'OK' : 'bloqueado'}</b></article>
          <article class="taste-metric"><span>Fisica</span><b>${gates.physics_regime_ok ? 'OK' : 'bloqueado'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Evidencia faltante</p>
          <ul class="mt-2 grid gap-1 text-sm leading-6 text-slate-300">
            ${missing.map(item => `<li>${esc(item)}</li>`).join('') || '<li>N/D</li>'}
          </ul>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Replay Qualification Gate. No activa prior. ${esc(data.reason)}</p>
      </article>`;
  }

  function renderSlate(data) {
    if (!data) {
      return emptyCard('Decision Slate', 'Sin v4_decision_slate.json. Set de revision diagnostico. No es probabilidad de ganar.');
    }
    const balanced = data.review_sets?.balanced_review_set;
    const rows = Array.isArray(balanced) ? balanced : [];
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Decision Slate</p>
            <h3>Set de revision diagnostico</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${esc(data.mode || 'diagnostic_only')}</span>
        </div>
        <div class="grid gap-3 mt-4">
          ${rows.slice(0, 5).map(row => `
            <div class="taste-panel-muted">
              <div class="flex flex-wrap items-center justify-between gap-3">
                <span class="taste-chip">${esc(row.source)} #${esc(row.rank_diversified || row.rank_original)}</span>
                <span class="font-mono text-xs text-slate-400">${fmt(row.score_reference, 3)}</span>
              </div>
              <div class="mt-3">${comboBalls(row.numbers)}</div>
            </div>`).join('') || '<p class="text-sm text-slate-400">Sin slate disponible.</p>'}
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Set de revision diagnostico. No es probabilidad de ganar. ${esc(warnings.join(' ') || data.language_guardrail)}</p>
      </article>`;
  }

  async function render() {
    const panel = ensurePanel();
    if (!panel) return;
    const [diversity, benchmark, physics, candidatePool, qualification, slate] = await Promise.all([
      loadJson(FILES.diversity),
      loadJson(FILES.benchmark),
      loadJson(FILES.physics),
      loadJson(FILES.candidatePool),
      loadJson(FILES.qualification),
      loadJson(FILES.slate),
    ]);
    panel.innerHTML = `
      <div class="grid gap-4 xl:grid-cols-3">
        ${renderDiversity(diversity)}
        ${renderBenchmark(benchmark)}
        ${renderPhysics(physics)}
      </div>`;
    panel.insertAdjacentHTML('beforeend', `
      <div class="grid gap-4 mt-4 xl:grid-cols-3">
        ${renderCandidatePool(candidatePool)}
        ${renderQualification(qualification)}
        ${renderSlate(slate)}
      </div>`);
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(render, 500));
  document.addEventListener('fisicapapa:v42-ready', () => render());
  window.renderV4DecisionAuditPanel = render;
})();
