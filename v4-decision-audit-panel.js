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
    postRankingHoldout: 'v4_post_ranking_holdout_experiment.json',
    postRankingRolling: 'v4_post_ranking_rolling_validation.json',
    postRankingSummary: 'v4_post_ranking_holdout_summary.json',
    postRankingCandidate: 'v4_post_ranking_layer_candidate.json',
    postRankingSmoothing: 'v4_post_ranking_smoothing_stress_test.json',
    postRankingConfidence: 'v4_post_ranking_confidence_gate_experiment.json',
    postRankingWorstFold: 'v4_post_ranking_worst_fold_analysis.json',
    postRankingFullSummary: 'v4_post_ranking_full_validation_summary.json',
    postRankingDecisionRecord: 'v4_post_ranking_candidate_decision_record.json',
    postRankingControlledLayer: 'v4_post_ranking_controlled_layer_output.json',
    postRankingControlledComparison: 'v4_post_ranking_controlled_comparison.json',
    postRankingControlledSummary: 'v4_post_ranking_controlled_summary.json',
    futureUnseenValidation: 'v4_future_unseen_validation_log.json',
    v43Slate: 'v4_hybrid_composition_slate.json',
    v43Visual: 'v4_visual_pattern_output.json',
    v43Audit: 'v4_winner_composition_audit.json',
    v43PairCompanion: 'v4_pair_companion_audit.json',
    v43PostDrawAudit: 'v4_post_draw_audit.json',
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

  function parseOptionalJson(rawText, path, url) {
    const raw = String(rawText ?? '');
    const cleaned = raw.replace(/^\uFEFF/, '').trim();

    if (!cleaned) {
      console.warn('[Fisicapapa] JSON auxiliar vacío:', { path, url });
      return null;
    }

    if (cleaned[0] === '<') {
      console.warn('[Fisicapapa] JSON auxiliar parece HTML/no JSON:', {
        path,
        url,
        preview: cleaned.slice(0, 220).replace(/\s+/g, ' '),
      });
      return null;
    }

    try {
      return JSON.parse(cleaned);
    } catch (err) {
      console.warn('[Fisicapapa] JSON auxiliar inválido:', {
        path,
        url,
        message: err.message,
        preview: cleaned.slice(0, 220).replace(/\s+/g, ' '),
      });
      return null;
    }
  }

  async function loadJson(path) {
    const url = `${path}?audit=${Date.now()}`;
    try {
      const response = await fetch(url, {
        cache: 'no-store',
        headers: { 'Accept': 'application/json,text/plain,*/*' },
      });

      if (!response.ok) {
        console.warn('[Fisicapapa] JSON auxiliar no disponible:', {
          path,
          url,
          status: response.status,
        });
        return null;
      }

      const rawText = await response.text();
      return parseOptionalJson(rawText, path, url);
    } catch (err) {
      console.warn('[Fisicapapa] No se pudo cargar JSON auxiliar:', {
        path,
        url,
        message: err?.message || String(err),
      });
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
          <p class="taste-eyebrow">V4.3 Decision Cockpit</p>
          <h2>Composicion armonica, diagnostico y auditoria</h2>
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

  function compactList(items) {
    if (!Array.isArray(items) || !items.length) return 'N/D';
    return items.map(item => esc(item)).join(', ');
  }

  const ROLE_LABELS = {
    activated_block: 'Active block',
    block_completion: 'Block fill',
    bridge_pair_lag: 'Pair-lag',
    pair_lag_support: 'Pair support',
    co_travel_companion: 'Co-travel',
    block_bridge_pair: 'Bridge pair',
    harmonic_cluster: 'Cluster',
    anti_pair_risk: 'Anti-pair risk',
    cold_companion: 'Cold',
    gap_echo: 'Gap echo',
    v42_signal_optional: 'V4.2 signal',
    contrarian_controlled: 'Contrarian',
    sum_band_guardrail: 'Sum guard',
    harmonic_support: 'Harmonic',
    anchor: 'Anchor',
    support: 'Support',
  };

  function roleChips(roles) {
    if (!Array.isArray(roles) || !roles.length) return '<span class="taste-chip v43-role-chip" title="support">Support</span>';
    return roles.slice(0, 4).map(role => {
      const safeRole = esc(role).replace(/[^a-z0-9_-]/gi, '-');
      const label = ROLE_LABELS[role] || String(role).replace(/_/g, ' ');
      return `<span class="taste-chip v43-role-chip v43-role-${safeRole}" title="${esc(role)}">${esc(label)}</span>`;
    }).join('');
  }

  function renderV43HybridComposition(slate, visual, audit, pairCompanion, postDrawAudit) {
    if (!slate) {
      return emptyCard('V4.3 Decision Cockpit', 'Aun no hay slate V4.3. Ejecuta tools/v4_refresh.py --game revancha --pair-companion-audit para generar la vista armonica.');
    }
    const tickets = Array.isArray(slate.slate) ? slate.slate.slice(0, 6) : [];
    const warnings = Array.isArray(slate.warnings) ? slate.warnings : [];
    const validation = slate.validation_summary || {};
    const source = slate.source_policy || {};
    const pairLagMode = source.pair_lag_mode || visual?.pair_lag_mode || 'support_only';
    const zone = visual?.zone_activation || {};
    const activeBlocks = Object.entries(zone)
      .filter(([, row]) => Number(row?.unique_activation || 0) >= 0.40)
      .map(([name, row]) => `${name} ${fmt(row?.unique_activation, 2)}`);
    const sumDistribution = validation.slate_sum_distribution || {};
    const coherence = validation.harmonic_coherence_summary || {};
    const pairSummary = validation.pair_companion_summary || {};
    const postDraw = postDrawAudit || null;
    return `
      <article class="taste-card v43-slate-card" id="v43-hybrid-slate">
        <div class="taste-card-heading v43-slate-heading">
          <div>
            <p class="taste-eyebrow">V4.3 Decision Cockpit</p>
            <h3>Candidate slate por coherencia historica</h3>
            <p class="v43-slate-subcopy">Review-default: composicion armonica, companion pairs, bloques y disciplina de suma. No reemplaza el output oficial V4.2.</p>
          </div>
          <span class="taste-chip taste-chip-warn">${esc(slate.production_status || 'review_default')}</span>
        </div>
        <div class="v43-status-strip mt-4">
          <article class="taste-metric"><span>Tickets</span><b>${fmt(tickets.length, 0)}</b></article>
          <article class="taste-metric"><span>Modo</span><b>${esc(source.fallback_mode || visual?.mode || 'csv_plus_v42_signal')}</b></article>
          <article class="taste-metric"><span>Latest draw</span><b>${fmt(slate.latest_draw || visual?.latest_draw || audit?.history?.latest_draw, 0)}</b></article>
          <article class="taste-metric"><span>Harmonic avg</span><b>${fmt(coherence.avg_score, 3)}</b></article>
        </div>
        <div class="v43-policy-strip">
          <span>Review-default</span>
          <span>V4.2 legacy signal optional</span>
          <span>Pair-lag: ${esc(pairLagMode)}</span>
          <span>Active blocks: ${esc(activeBlocks.join(' | ') || 'N/D')}</span>
        </div>
        <div class="v43-ticket-grid mt-4">
          ${tickets.map(ticket => {
            const roles = ticket.roles || {};
            const composition = ticket.composition || {};
            const harmonic = composition.harmonic_coherence || {};
            const notes = Array.isArray(harmonic.notes) ? harmonic.notes : [];
            const riskNotes = Array.isArray(ticket.risk_notes) ? ticket.risk_notes : [];
            return `
              <section class="v43-ticket-card">
                <div class="v43-ticket-head">
                  <div>
                    <p class="taste-eyebrow">${esc(ticket.ticket_type || 'composition')}</p>
                    <p class="v43-ticket-id">${esc(ticket.ticket_id || '')}</p>
                  </div>
                  <div class="v43-ticket-badges">
                    <span class="taste-chip">sum ${esc(composition.sum || 'N/D')}</span>
                    <span class="taste-chip">${esc(composition.sum_band || 'sum_band N/D')}</span>
                    <span class="taste-chip">HC ${fmt(harmonic.score, 3)}</span>
                  </div>
                </div>
                <div class="v43-ticket-numbers">${comboBalls(ticket.numbers)}</div>
                <div class="v43-ticket-thesis">
                  <p>${esc(ticket.reason || 'Ticket compuesto por soporte armonico V4.3.')}</p>
                  <p>${esc(notes.slice(0, 2).join(' | ') || 'Sin notas armonicas adicionales.')}</p>
                </div>
                <div class="v43-role-grid">
                  ${(Array.isArray(ticket.numbers) ? ticket.numbers : []).map(number => `
                    <div class="v43-role-row">
                      <b>${esc(number)}</b>
                      ${roleChips(roles[String(number)])}
                    </div>`).join('')}
                </div>
                <details class="v43-ticket-details">
                  <summary>Why this ticket exists</summary>
                  <p class="mt-2">Blocks: ${esc(JSON.stringify(composition.blocks || {}))}</p>
                  <p class="mt-1">Co-travel: ${fmt(harmonic.co_travel_score, 3)} | Bridge pairs: ${fmt(harmonic.block_bridge_pair_count, 0)} | Clusters: ${fmt(harmonic.cluster_support_count, 0)}</p>
                  <p class="mt-1">Risk notes: ${esc(riskNotes.slice(0, 4).join(' | ') || 'Sin riesgos destacados.')}</p>
                </details>
              </section>`;
          }).join('') || '<p class="text-sm text-slate-400">No V4.3 tickets available.</p>'}
        </div>
        <div class="v43-support-grid mt-4">
          <section class="taste-panel-muted v43-compact-panel">
            <p class="taste-eyebrow">Source policy</p>
            <p class="text-sm leading-6 text-slate-300">Primary: ${esc(source.primary_source || 'revancha.csv')}</p>
            <p class="text-sm leading-6 text-slate-300">V4.2 legacy signal: ${source.v42_signal_available ? 'available' : 'not used'}</p>
          </section>
          <section class="taste-panel-muted v43-compact-panel">
            <p class="taste-eyebrow">Slate diagnostics</p>
            <p class="text-sm leading-6 text-slate-300">Sum bands: ${esc(JSON.stringify(sumDistribution))}</p>
            <p class="text-sm leading-6 text-slate-300">Pair support: ${esc(JSON.stringify(pairSummary))}</p>
          </section>
          <section class="taste-panel-muted v43-compact-panel">
            <p class="taste-eyebrow">Warnings</p>
            <p class="text-sm leading-6 text-slate-300">${warnings.slice(0, 2).map(item => esc(item)).join(' | ') || 'Sin warnings V4.3.'}</p>
          </section>
        </div>
        <div class="v43-support-grid mt-4">
          <section class="taste-panel-muted v43-compact-panel">
            <p class="taste-eyebrow">Pair companion audit</p>
            <p class="text-sm leading-6 text-slate-300">Co-travel pairs: ${fmt(pairCompanion?.top_co_travel_pairs?.length, 0)}</p>
            <p class="text-sm leading-6 text-slate-300">Bridge pairs: ${fmt(pairCompanion?.top_block_bridge_pairs?.length, 0)} | Anti-pairs: ${fmt(pairCompanion?.anti_pairs?.length, 0)}</p>
          </section>
          <section class="taste-panel-muted v43-compact-panel">
            <p class="taste-eyebrow">Post-draw audit</p>
            ${postDraw ? `
              <p class="text-sm leading-6 text-slate-300">Audited draw: ${fmt(postDraw.target_draw, 0)} | Best ticket hits: ${fmt(postDraw.best_ticket_hits, 0)}</p>
              <p class="text-sm leading-6 text-slate-300">Matched thesis: ${postDraw.actual_draw_matched_slate_thesis ? 'review signal present' : 'review needed'}</p>
            ` : `
              <p class="text-sm leading-6 text-slate-300">No post-draw audit yet. Freeze a pre-draw snapshot, add official result, then run post-draw audit.</p>
            `}
          </section>
          <details class="taste-panel-muted v43-compact-panel">
            <summary class="taste-eyebrow">V4.2 legacy diagnostics</summary>
            <p class="text-sm leading-6 text-slate-300 mt-2">Best hits WF: ${fmt(validation.best_ticket_hits_per_draw, 2)}</p>
            <p class="text-sm leading-6 text-slate-300">Avg hits/ticket: ${fmt(validation.avg_hits_per_ticket, 2)}</p>
            <p class="text-sm leading-6 text-slate-300">GE2 rate: ${fmt(validation.hit_ge_2_rate, 3)}</p>
          </details>
        </div>
      </article>`;
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
          <span class="taste-chip taste-chip-warn">revision diagnostica</span>
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
        <p class="mt-3 text-xs leading-5 text-slate-400">${esc((data.quality_notes || []).join(' ') || 'Ranking diversificado para revision diagnostica.')}</p>
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
        <p class="mt-3 text-xs leading-5 text-slate-400">Benchmark diagnostico. No activa prior. Brier desactivado: ${esc(data.experimental_brier?.reason || 'Scores internos no tienen calibracion real.')}</p>
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
        <p class="mt-3 text-xs leading-5 text-slate-400">Benchmark endurecido. No activa prior. Scores internos son ranking de revision. Ventaja sobre baseline requiere estabilidad, no solo una muestra.</p>
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
        <p class="mt-3 text-xs leading-5 text-slate-400">Experimento de reparacion de ranking. No modifica el motor. Este experimento no activa prior ni cambia resultados oficiales. Una mejora diagnostica no equivale a autorizacion operativa. Accion: ${esc(summary?.recommended_next_action || 'diagnostic_only')}</p>
      </article>`;
  }

  function renderPostRankingHoldoutValidation(summary, holdout, rolling, candidate) {
    if (!summary && !holdout && !rolling && !candidate) {
      return emptyCard('Post-Ranking Holdout Validation', 'Sin v4_post_ranking_holdout_summary.json. Validacion holdout de post-ranking. No modifica produccion.');
    }
    const evidence = Array.isArray(summary?.required_next_evidence) ? summary.required_next_evidence : [];
    const holdoutSummary = holdout?.summary || {};
    const rollingSummary = rolling?.summary || {};
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Post-Ranking Holdout Validation</p>
            <h3>${esc(summary?.candidate_variant || candidate?.candidate_variant || 'candidate_not_applied')}</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${summary?.prior_should_remain_blocked === false ? 'revisar' : 'prior bloqueado'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Holdout quality</span><b>${esc(summary?.holdout_signal_quality || holdoutSummary.holdout_signal_quality || 'unknown')}</b></article>
          <article class="taste-metric"><span>Rolling quality</span><b>${esc(summary?.rolling_signal_quality || rollingSummary.rolling_signal_quality || 'unknown')}</b></article>
          <article class="taste-metric"><span>Overfit risk</span><b>${esc(summary?.overfit_risk || 'unknown')}</b></article>
          <article class="taste-metric"><span>Future layer</span><b>${summary?.future_experimental_layer_candidate ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Production ready</span><b>${summary?.production_ready ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Prior bloqueado</span><b>${summary?.prior_should_remain_blocked === false ? 'No' : 'Si'}</b></article>
          <article class="taste-metric"><span>Holdout pass</span><b>${fmt((summary?.holdout_pass_rate || 0) * 100, 0)}%</b></article>
          <article class="taste-metric"><span>Rolling pass</span><b>${fmt((summary?.rolling_pass_rate || 0) * 100, 0)}%</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Lectura</p>
          <p class="text-sm leading-6 text-slate-300">${esc(summary?.reason || 'La capa candidata no esta aplicada.')}</p>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Evidencia requerida</p>
          <ul class="mt-2 grid gap-1 text-sm leading-6 text-slate-300">
            ${evidence.slice(0, 5).map(item => `<li>${esc(item)}</li>`).join('') || '<li>N/D</li>'}
          </ul>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Validacion holdout de post-ranking. No modifica produccion. La capa candidata no esta aplicada. Produccion requiere validacion futura no vista.</p>
      </article>`;
  }

  function renderPostRankingFullValidation(summary, smoothing, confidence, worstFold, decisionRecord) {
    if (!summary && !smoothing && !confidence && !worstFold && !decisionRecord) {
      return emptyCard('Post-Ranking Full Validation', 'Sin v4_post_ranking_full_validation_summary.json. Validacion completa de candidato post-ranking. No modifica produccion.');
    }
    const bestSmoothing = summary?.best_smoothing_variant || smoothing?.best_smoothing_variant?.name || 'N/D';
    const bestPolicy = summary?.best_policy || confidence?.best_policy?.name || 'N/D';
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Post-Ranking Full Validation</p>
            <h3>${esc(summary?.candidate_status || decisionRecord?.decision || 'diagnostic_only')}</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${summary?.production_ready ? 'revisar' : 'produccion bloqueada'}</span>
        </div>
        <div class="bento-status-grid mt-4">
          <article class="taste-metric"><span>Best smoothing</span><b>${esc(bestSmoothing)}</b></article>
          <article class="taste-metric"><span>Best policy</span><b>${esc(bestPolicy)}</b></article>
          <article class="taste-metric"><span>Rolling pass</span><b>${fmt((summary?.rolling_pass_rate || 0) * 100, 0)}%</b></article>
          <article class="taste-metric"><span>Holdout pass</span><b>${fmt((summary?.holdout_pass_rate || 0) * 100, 0)}%</b></article>
          <article class="taste-metric"><span>Edge original</span><b>${fmt(summary?.avg_edge_vs_original, 3)}</b></article>
          <article class="taste-metric"><span>Edge frequency</span><b>${fmt(summary?.avg_edge_vs_frequency, 3)}</b></article>
          <article class="taste-metric"><span>Edge random</span><b>${fmt(summary?.avg_edge_vs_random, 3)}</b></article>
          <article class="taste-metric"><span>Worst vs freq</span><b>${fmt(summary?.worst_fold_delta_vs_frequency, 3)}</b></article>
          <article class="taste-metric"><span>Overfit risk</span><b>${esc(summary?.overfit_risk || 'unknown')}</b></article>
          <article class="taste-metric"><span>Controlled future</span><b>${summary?.future_controlled_layer_candidate ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Production ready</span><b>${summary?.production_ready ? 'Si' : 'No'}</b></article>
          <article class="taste-metric"><span>Prior bloqueado</span><b>${summary?.prior_should_remain_blocked === false ? 'No' : 'Si'}</b></article>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Decision</p>
          <p class="text-sm leading-6 text-slate-300">${esc(summary?.reason || 'Decision record pendiente.')}</p>
          <p class="mt-2 text-sm leading-6 text-slate-300">Siguiente PR: ${esc(summary?.recommended_next_pr || 'diagnostic_only')}</p>
        </div>
        <p class="mt-3 text-xs leading-5 text-slate-400">Validacion completa de candidato post-ranking. No modifica produccion. El candidato puede vivir como hipotesis aunque produccion siga bloqueada. Production ready siempre debe permanecer false en este PR.</p>
      </article>`;
  }

  function renderPostRankingControlledLayer(summary, layer, comparison, futureLog) {
    if (!summary && !layer && !comparison && !futureLog) {
      return emptyCard('Post-Ranking Controlled Layer', 'Sin capa controlada. Review-only. Does not replace official V4.2 output. Outcome-neutral review view.');
    }
    const controlledStatus = summary?.controlled_layer_status || layer?.status || 'blocked';
    const overlap = comparison?.overlap || {};
    const warnings = Array.isArray(layer?.warnings) ? layer.warnings : [];
    return `
      <article class="taste-card">
        <div class="taste-card-heading">
          <div>
            <p class="taste-eyebrow">Post-Ranking Controlled Layer</p>
            <h3>${esc(controlledStatus)}</h3>
          </div>
          <span class="taste-chip taste-chip-warn">${summary?.usable_in_app ? 'review_only' : 'bloqueada'}</span>
        </div>
        <p class="mt-3 text-sm leading-6 text-slate-300">Controlled post-ranking layer. Review-only. Does not replace official V4.2 output.</p>
        <p class="text-sm leading-6 text-slate-300">Production ready remains false. Replay prior remains blocked. Outcome-neutral review view.</p>
        <p class="mt-2 text-sm leading-6 text-slate-300">Review-only. Does not replace official V4.2 output.</p>
        <div class="grid gap-4 mt-4 lg:grid-cols-2">
          <section class="taste-panel-muted">
            <p class="taste-eyebrow">Official V4.2 Output</p>
            <div class="mt-3 grid gap-3">
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-500">Original top numbers</p>
                ${comboBalls(layer?.original_top_numbers)}
              </div>
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-500">Legacy core preservado</p>
                ${comboBalls(layer?.top6_preserved)}
              </div>
              <div class="bento-status-grid">
                <article class="taste-metric"><span>Overlap top10</span><b>${fmt(overlap.top10 ?? layer?.diff_vs_original?.overlap_top10, 0)}</b></article>
                <article class="taste-metric"><span>Overlap top20</span><b>${fmt(overlap.top20 ?? layer?.diff_vs_original?.overlap_top20, 0)}</b></article>
                <article class="taste-metric"><span>Core OK</span><b>${comparison?.top6_preservation_ok || layer?.diff_vs_original?.preserved_top6 ? 'Si' : 'No'}</b></article>
              </div>
            </div>
          </section>
          <section class="taste-panel-muted">
            <p class="taste-eyebrow">Controlled Post-Ranking Layer</p>
            <div class="mt-3 grid gap-3">
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-500">Controlled top20</p>
                ${comboBalls(layer?.controlled_top20_numbers)}
              </div>
              <div>
                <p class="text-xs uppercase tracking-wide text-slate-500">Frequency window 15 rank</p>
                ${comboBalls(Array.isArray(layer?.frequency_window_15_rank) ? layer.frequency_window_15_rank.slice(0, 20) : [])}
              </div>
              <div class="bento-status-grid">
                <article class="taste-metric"><span>Context</span><b>${esc(layer?.frequency_context || 'N/D')}</b></article>
                <article class="taste-metric"><span>Window</span><b>${fmt(layer?.frequency_window_size, 0)}</b></article>
                <article class="taste-metric"><span>Truth source</span><b>${layer?.frequency_is_truth_source ? 'Si' : 'No'}</b></article>
                <article class="taste-metric"><span>Overfit risk</span><b>${esc(comparison?.validation_status?.overfit_risk || 'N/D')}</b></article>
              </div>
            </div>
          </section>
        </div>
        <div class="grid gap-4 mt-4 lg:grid-cols-2">
          <section class="taste-panel-muted">
            <p class="taste-eyebrow">Diff top20</p>
            <p class="text-sm leading-6 text-slate-300">Agregados: ${compactList(layer?.diff_vs_original?.added_numbers_top20 || comparison?.added_numbers_top20)}</p>
            <p class="text-sm leading-6 text-slate-300">Removidos: ${compactList(layer?.diff_vs_original?.removed_numbers_top20 || comparison?.removed_numbers_top20)}</p>
          </section>
          <section class="taste-panel-muted">
            <p class="taste-eyebrow">Estado</p>
            <p class="text-sm leading-6 text-slate-300">Uso: ${esc(summary?.recommended_usage || comparison?.recommended_usage || 'review_only')}</p>
            <p class="text-sm leading-6 text-slate-300">Production ready: ${summary?.production_ready ? 'Si' : 'No'}</p>
            <p class="text-sm leading-6 text-slate-300">Prior bloqueado: ${summary?.prior_should_remain_blocked === false ? 'No' : 'Si'}</p>
            <p class="text-sm leading-6 text-slate-300">Futuro no visto: ${fmt(futureLog?.records?.length, 0)} registros</p>
          </section>
        </div>
        <div class="taste-panel-muted mt-4">
          <p class="taste-eyebrow">Reason / warnings</p>
          <p class="text-sm leading-6 text-slate-300">${esc(summary?.reason || layer?.interpretation || 'Controlled review-only layer.')}</p>
          <p class="mt-2 text-sm leading-6 text-slate-300">${warnings.slice(0, 4).map(item => esc(item)).join(' | ') || 'Sin warnings de capa.'}</p>
        </div>
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
      return emptyCard('Decision Slate', 'Sin v4_decision_slate.json. Set de revision diagnostico.');
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
        <p class="mt-3 text-xs leading-5 text-slate-400">Set de revision diagnostico. ${esc(warnings.join(' ') || 'Revision read-only.')}</p>
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
      postRankingHoldout,
      postRankingRolling,
      postRankingSummary,
      postRankingCandidate,
      postRankingSmoothing,
      postRankingConfidence,
      postRankingWorstFold,
      postRankingFullSummary,
      postRankingDecisionRecord,
      postRankingControlledLayer,
      postRankingControlledComparison,
      postRankingControlledSummary,
      futureUnseenValidation,
      v43Slate,
      v43Visual,
      v43Audit,
      v43PairCompanion,
      v43PostDrawAudit,
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
      loadJson(FILES.postRankingHoldout),
      loadJson(FILES.postRankingRolling),
      loadJson(FILES.postRankingSummary),
      loadJson(FILES.postRankingCandidate),
      loadJson(FILES.postRankingSmoothing),
      loadJson(FILES.postRankingConfidence),
      loadJson(FILES.postRankingWorstFold),
      loadJson(FILES.postRankingFullSummary),
      loadJson(FILES.postRankingDecisionRecord),
      loadJson(FILES.postRankingControlledLayer),
      loadJson(FILES.postRankingControlledComparison),
      loadJson(FILES.postRankingControlledSummary),
      loadJson(FILES.futureUnseenValidation),
      loadJson(FILES.v43Slate),
      loadJson(FILES.v43Visual),
      loadJson(FILES.v43Audit),
      loadJson(FILES.v43PairCompanion),
      loadJson(FILES.v43PostDrawAudit),
    ]);
    panel.innerHTML = `
      <div class="grid gap-4 mb-4">
        ${renderV43HybridComposition(v43Slate, v43Visual, v43Audit, v43PairCompanion, v43PostDrawAudit)}
      </div>
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
      <div class="grid gap-4 mt-4">
        ${renderPostRankingHoldoutValidation(postRankingSummary, postRankingHoldout, postRankingRolling, postRankingCandidate)}
      </div>
      <div class="grid gap-4 mt-4">
        ${renderPostRankingFullValidation(postRankingFullSummary, postRankingSmoothing, postRankingConfidence, postRankingWorstFold, postRankingDecisionRecord)}
      </div>
      <div class="grid gap-4 mt-4">
        ${renderPostRankingControlledLayer(postRankingControlledSummary, postRankingControlledLayer, postRankingControlledComparison, futureUnseenValidation)}
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
