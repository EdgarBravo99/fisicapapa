// v4-decision-audit-panel.js
// Read-only V4.4 decision diagnostics: diversity, benchmark, and physics regime.
(function () {
  'use strict';

  const FILES = {
    diversity: 'v4_diversity_output.json',
    benchmark: 'v4_baseline_benchmark.json',
    physics: 'v4_physics_regime_analysis.json',
    physicsTimeline: 'v4_physics_regime_timeline.json',
    candidatePool: 'v4_candidate_pool_audit.json',
    qualification: 'v4_replay_qualification.json',
    slate: 'v4_decision_slate.json',
    auditState: 'v4_audit_state.json',
    benchmarkHardening: 'v4_benchmark_hardening.json',
    calibration: 'v4_calibration_diagnostics.json',
    diversifiedEval: 'v4_diversified_vs_original_eval.json',
    benchmarkStability: 'v4_benchmark_stability.json',
    benchmarkSummary: 'v4_benchmark_summary.json',
    replayWindows: 'v4_replay_window_diagnostics.json',
    rankingInversion: 'v4_ranking_inversion_audit.json',
    frequencyDominance: 'v4_frequency_dominance_audit.json',
    drawFailure: 'v4_draw_failure_report.json',
    signalDecomposition: 'v4_signal_decomposition_summary.json',
    rankingRepair: 'v4_ranking_repair_experiment.json',
    rankingRepairStability: 'v4_ranking_repair_window_stability.json',
    combinationRepair: 'v4_combination_repair_experiment.json',
    rankingRepairSummary: 'v4_ranking_repair_summary.json',
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

  function renderBenchmarkHardening(summary, hardening, calibration, stability) {
    if (!summary && !hardening && !calibration && !stability) {
      return emptyCard('Benchmark Hardening', 'Sin reportes endurecidos. Benchmark endurecido. No activa prior.');
    }
    const signal = summary?.benchmark_signal_quality || 'unknown';
    const ranking = summary?.ranking_signal_quality || calibration?.ranking_signal_quality || 'unknown';
    const stabilityValue = summary?.stability || stability?.stability || 'unknown';
    const unlock = summary?.can_unlock_replay_prior === true;
    const future = summary?.eligible_for_future_experiment === true;
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Benchmark Hardening</p>
            <h3>Calibracion y estabilidad</h3>
          </div>
          <span class="taste-chip taste-chip-warn">diagnostic_only</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Benchmark</span><b>${esc(signal)}</b></article>
          <article class="taste-metric"><span>Ranking</span><b>${esc(ranking)}</b></article>
          <article class="taste-metric"><span>Stability</span><b>${esc(stabilityValue)}</b></article>
          <article class="taste-metric"><span>Vs random</span><b>${fmt(summary?.cruncher_minus_random ?? hardening?.cruncher_minus_random, 3)}</b></article>
          <article class="taste-metric"><span>Vs frecuencia</span><b>${fmt(summary?.cruncher_minus_frequency ?? hardening?.cruncher_minus_frequency, 3)}</b></article>
          <article class="taste-metric"><span>Vs recencia</span><b>${fmt(summary?.cruncher_minus_recency ?? hardening?.cruncher_minus_recency, 3)}</b></article>
          <article class="taste-metric"><span>Desbloquea prior</span><b>${unlock ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Experimento futuro</span><b>${future ? 'Si' : 'No'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Lectura</p>
          <p class="text-sm leading-6 text-slate-300">${esc(summary?.reason || calibration?.reason || 'Benchmark endurecido pendiente de datos suficientes.')}</p>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Benchmark endurecido. No activa prior. Scores internos no son probabilidades. Ventaja sobre baseline requiere estabilidad, no solo una muestra.</p>
      </article>`;
  }

  function renderReplayFailureAnalysis(signal, windows, ranking, frequency, drawFailure) {
    if (!signal && !windows && !ranking && !frequency && !drawFailure) {
      return emptyCard('Replay Failure Analysis', 'Sin diagnosticos de fallas replay. Analisis de fallas replay. No activa prior.');
    }
    const windowSummary = windows?.summary || {};
    const drawSummary = drawFailure?.summary || {};
    const findings = Array.isArray(signal?.main_findings) ? signal.main_findings : [];
    const blocked = signal?.prior_should_remain_blocked !== false;
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Replay Failure Analysis</p>
            <h3>${esc(signal?.failure_scope || 'diagnostic_only')}</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${blocked ? 'prior bloqueado' : 'revisar'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Records</span><b>${fmt(windows?.records_count ?? drawFailure?.records_count, 0)}</b></article>
          <article class="taste-metric"><span>Ranking mode</span><b>${esc(signal?.ranking_failure_mode || ranking?.ranking_failure_mode)}</b></article>
          <article class="taste-metric"><span>Frequency domina</span><b>${signal?.frequency_dominance ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Prior bloqueado</span><b>${blocked ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Best window</span><b>${esc(windowSummary.best_window)}</b></article>
          <article class="taste-metric"><span>Worst window</span><b>${esc(windowSummary.worst_window)}</b></article>
          <article class="taste-metric"><span>Freq - cruncher</span><b>${fmt(frequency?.frequency_minus_cruncher, 3)}</b></article>
          <article class="taste-metric"><span>Fallos altos</span><b>${fmt(drawSummary.high_or_extreme_failures, 0)}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Top failure notes</p>
          <ul class="mt-2 grid gap-1 text-sm leading-6 text-slate-300">
            ${findings.slice(0, 5).map(item => `<li>${esc(item)}</li>`).join('') || '<li>N/D</li>'}
          </ul>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Analisis de fallas replay. No activa prior. Un ranking weak no debe usarse para modificar simulacion. Frequency baseline venciendo al cruncher indica que falta senal o calibracion. Accion: ${esc(signal?.recommended_next_action || 'diagnostic_only')}</p>
      </article>`;
  }

  function renderRankingRepairExperiment(summary, experiment, stability, combination) {
    if (!summary && !experiment && !stability && !combination) {
      return emptyCard('Ranking Repair Experiment', 'Sin v4_ranking_repair_summary.json. Experimento de reparacion de ranking. No modifica el motor.');
    }
    const blocked = summary?.prior_should_remain_blocked !== false;
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Ranking Repair Experiment</p>
            <h3>${esc(summary?.best_repair_variant || experiment?.best_variant?.name || 'diagnostic_only')}</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${blocked ? 'prior bloqueado' : 'revisar'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Mejora original</span><b>${summary?.repair_improves_original ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Supera frequency</span><b>${summary?.repair_beats_frequency ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Supera random</span><b>${summary?.repair_beats_random ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Estable ventanas</span><b>${summary?.repair_stable_across_windows ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Post-ranking futuro</span><b>${summary?.future_post_ranking_layer_candidate ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Combo repair</span><b>${summary?.combination_repair_available || combination?.combination_repair_available ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Windows improved</span><b>${fmt(stability?.summary?.windows_improved_count, 0)} / ${fmt(stability?.summary?.windows_total, 0)}</b></article>
          <article class="taste-metric"><span>Prior bloqueado</span><b>${blocked ? 'Si' : 'No'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Lectura</p>
          <p class="text-sm leading-6 text-slate-300">${esc(summary?.reason || 'Experimento pendiente de datos.')}</p>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Experimento de reparacion de ranking. No modifica el motor. Este experimento no activa prior ni cambia resultados oficiales. Una mejora diagnostica no equivale a probabilidad de ganar. Accion: ${esc(summary?.recommended_next_action || 'diagnostic_only')}</p>
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

  function renderPhysicsTimeline(data) {
    if (!data) {
      return emptyCard('Physics Timeline', 'Sin v4_physics_regime_timeline.json. Timeline fisico diagnostico. No activa prior.');
    }
    const summary = data.event_summary || {};
    const shifts = Array.isArray(data.shifts) ? data.shifts : [];
    const latestShift = shifts.length ? shifts[shifts.length - 1] : null;
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Physics Timeline</p>
            <h3>Historial de pesos</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${summary.can_estimate_periodicity ? 'estimable' : 'diagnostico'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Records</span><b>${fmt(data.records_count, 0)}</b></article>
          <article class="taste-metric"><span>Latest draw</span><b>${esc(data.latest_draw)}</b></article>
          <article class="taste-metric"><span>Eventos</span><b>${fmt(summary.events_detected_count, 0)}</b></article>
          <article class="taste-metric"><span>Periodicidad</span><b>${summary.can_estimate_periodicity ? 'si' : 'no'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Ultimo shift</p>
          <p class="text-sm text-slate-300">${latestShift ? `${esc(latestShift.from_draw)} -> ${esc(latestShift.to_draw)} · bloque ${esc(latestShift.largest_block_shift?.block)} ${fmt(latestShift.largest_block_shift?.delta, 4)}` : 'Sin shifts; se requieren al menos dos registros.'}</p>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Timeline fisico diagnostico. No activa prior. ${esc(summary.reason)}</p>
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

  function renderAuditState(data) {
    if (!data) {
      return emptyCard('Local Audit State', 'Sin v4_audit_state.json. Auditoria local. No consulta GitHub.');
    }
    const warnings = Array.isArray(data.warnings) ? data.warnings : [];
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Local Audit State</p>
            <h3>${esc(data.recommendation || 'review_warnings')}</h3>
          </div>
          <span class="taste-chip ${warnings.length ? 'taste-chip-warn' : 'taste-chip-ok'}">${warnings.length ? 'warnings' : 'ok'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Branch</span><b>${esc(data.git?.branch)}</b></article>
          <article class="taste-metric"><span>Uncommitted</span><b>${data.git?.has_uncommitted_changes ? 'si' : 'no'}</b></article>
          <article class="taste-metric"><span>Conflicts</span><b>${data.git?.conflict_detected ? 'si' : 'no'}</b></article>
          <article class="taste-metric"><span>Replay gate</span><b>${data.replay?.can_influence_future_prior ? 'si' : 'no'}</b></article>
          <article class="taste-metric"><span>Physics records</span><b>${fmt(data.physics?.weight_records_count, 0)}</b></article>
          <article class="taste-metric"><span>Outputs</span><b>${fmt(Object.values(data.generated_outputs || {}).filter(row => row?.exists).length, 0)}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Warnings</p>
          <ul class="mt-2 grid gap-1 text-sm leading-6 text-slate-300">
            ${warnings.slice(0, 5).map(item => `<li>${esc(item)}</li>`).join('') || '<li>Sin warnings.</li>'}
          </ul>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Auditoria local. No consulta GitHub.</p>
      </article>`;
  }

  async function render() {
    const panel = ensurePanel();
    if (!panel) return;
    const [
      diversity,
      benchmark,
      physics,
      physicsTimeline,
      candidatePool,
      qualification,
      slate,
      auditState,
      benchmarkHardening,
      calibration,
      diversifiedEval,
      benchmarkStability,
      benchmarkSummary,
      replayWindows,
      rankingInversion,
      frequencyDominance,
      drawFailure,
      signalDecomposition,
      rankingRepair,
      rankingRepairStability,
      combinationRepair,
      rankingRepairSummary,
    ] = await Promise.all([
      loadJson(FILES.diversity),
      loadJson(FILES.benchmark),
      loadJson(FILES.physics),
      loadJson(FILES.physicsTimeline),
      loadJson(FILES.candidatePool),
      loadJson(FILES.qualification),
      loadJson(FILES.slate),
      loadJson(FILES.auditState),
      loadJson(FILES.benchmarkHardening),
      loadJson(FILES.calibration),
      loadJson(FILES.diversifiedEval),
      loadJson(FILES.benchmarkStability),
      loadJson(FILES.benchmarkSummary),
      loadJson(FILES.replayWindows),
      loadJson(FILES.rankingInversion),
      loadJson(FILES.frequencyDominance),
      loadJson(FILES.drawFailure),
      loadJson(FILES.signalDecomposition),
      loadJson(FILES.rankingRepair),
      loadJson(FILES.rankingRepairStability),
      loadJson(FILES.combinationRepair),
      loadJson(FILES.rankingRepairSummary),
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
      </div>
      <div class="grid gap-4 mt-4">
        ${renderBenchmarkHardening(benchmarkSummary, benchmarkHardening, calibration, benchmarkStability)}
      </div>
      <div class="grid gap-4 mt-4">
        ${renderReplayFailureAnalysis(signalDecomposition, replayWindows, rankingInversion, frequencyDominance, drawFailure)}
      </div>
      <div class="grid gap-4 mt-4">
        ${renderRankingRepairExperiment(rankingRepairSummary, rankingRepair, rankingRepairStability, combinationRepair)}
      </div>
      <div class="grid gap-4 mt-4 xl:grid-cols-2">
        ${renderPhysicsTimeline(physicsTimeline)}
        ${renderAuditState(auditState)}
      </div>`);
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(render, 500));
  document.addEventListener('fisicapapa:v42-ready', () => render());
  window.renderV4DecisionAuditPanel = render;
})();
