// v4-cockpit-layout.js
// Read-only V4.3 Decision Cockpit renderer. It presents existing JSON fields only.
(function () {
  'use strict';

  window.FISICAPAPA_V43_COCKPIT_ACTIVE = true;

  const FILES = {
    slate: 'v4_hybrid_composition_slate.json',
    pair: 'v4_pair_companion_audit.json',
    postDraw: 'v4_post_draw_audit.json',
    historySync: 'v4_history_sync_report.json',
    resultados: 'resultados.json',
    winnerAudit: 'v4_winner_composition_audit.json',
    visual: 'v4_visual_pattern_output.json',
    matrix: 'v4_visual_matrix_export_report.json',
  };

  const ROLE_LABELS = {
    activated_block: 'Active block',
    block_completion: 'Block fill',
    bridge_pair_lag: 'Pair-lag',
    pair_lag_support: 'Pair support',
    co_travel_companion: 'Co-travel',
    block_bridge_pair: 'Bridge pair',
    harmonic_cluster: 'Cluster',
    anti_pair_risk: 'Warning: Anti-pair',
    cold_companion: 'Cold',
    gap_echo: 'Gap echo',
    v42_signal_optional: 'V4.2 signal',
    contrarian_controlled: 'Contrarian',
    sum_band_guardrail: 'Sum guard',
    harmonic_support: 'Harmonic',
    anchor: 'Anchor',
    support: 'Support',
  };

  const TICKET_TYPE_LABELS = {
    composition_main: 'Main harmonic ticket',
    activated_block_main: 'Active block ticket',
    pair_lag_bridge: 'Pair-lag bridge ticket',
    pair_lag_support: 'Pair support ticket',
    visual_support: 'Visual support ticket',
    balanced_hybrid: 'Balanced harmonic ticket',
    contrarian_controlled: 'Contrarian review ticket',
    cold_companion_high_edge: 'Companion edge ticket',
  };

  const SUM_BANDS = ['low_tail', 'historical_core', 'upper_core', 'high_tail', 'extreme_high'];
  const CRITICAL_SOURCE_KEYS = ['slate', 'visual', 'pair'];

  const state = {
    sources: {},
    loadStartedAt: 0,
    loadEndedAt: 0,
  };

  const qs = selector => document.querySelector(selector);
  const byId = id => document.getElementById(id);
  const isObject = value => value && typeof value === 'object' && !Array.isArray(value);
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const fmt = (value, digits = 2) => finite(value) ? Number(value).toFixed(digits) : 'not available';
  const intText = value => finite(value) ? String(Math.trunc(Number(value))) : 'not available';
  const clean = value => {
    if (value === null || value === undefined || value === '' || Number.isNaN(value)) return 'not available';
    if (Array.isArray(value)) return value.map(clean).join(', ');
    if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}: ${clean(item)}`).join(', ');
    return String(value);
  };
  const esc = value => clean(value).replace(/[&<>"']/g, mark => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[mark]));

  function safeArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function unique(items) {
    const seen = new Set();
    const output = [];
    for (const item of safeArray(items)) {
      const text = clean(item);
      if (!seen.has(text) && text !== 'not available') {
        seen.add(text);
        output.push(text);
      }
    }
    return output;
  }

  async function loadJson(path) {
    const url = `${path}?cockpit=${Date.now()}`;
    const startedAt = performance.now();
    try {
      const response = await fetch(url, {
        cache: 'no-store',
        headers: { Accept: 'application/json,text/plain,*/*' },
      });
      if (!response.ok) {
        const preview = (await response.text()).replace(/^\uFEFF/, '').trim().slice(0, 80);
        const lookedLikeHtml = preview.startsWith('<');
        return {
          path,
          ok: false,
          status: response.status,
          error: `HTTP ${response.status}`,
          lookedLikeHtml,
          nonJson: lookedLikeHtml,
          preview,
          ms: performance.now() - startedAt,
          data: null,
        };
      }
      const raw = (await response.text()).replace(/^\uFEFF/, '').trim();
      if (!raw || raw[0] === '<') {
        return {
          path,
          ok: false,
          status: response.status,
          error: raw ? 'non-JSON response' : 'empty response',
          lookedLikeHtml: raw.startsWith('<'),
          nonJson: Boolean(raw),
          preview: raw.slice(0, 80),
          ms: performance.now() - startedAt,
          data: null,
        };
      }
      try {
        return { path, ok: true, status: response.status, error: null, lookedLikeHtml: false, nonJson: false, preview: '', ms: performance.now() - startedAt, data: JSON.parse(raw) };
      } catch (err) {
        return {
          path,
          ok: false,
          status: response.status,
          error: err?.message || String(err),
          lookedLikeHtml: false,
          nonJson: true,
          preview: raw.slice(0, 80),
          ms: performance.now() - startedAt,
          data: null,
        };
      }
    } catch (err) {
      return { path, ok: false, status: 0, error: err?.message || String(err), lookedLikeHtml: false, nonJson: false, preview: '', ms: performance.now() - startedAt, data: null };
    }
  }

  function expectedCommand(key, targetDraw) {
    const commands = {
      slate: 'py tools\\v4_refresh.py --game revancha --sync-history-from-pakin --export-visual-matrix --pair-companion-audit --snapshot-predraw',
      pair: 'py tools\\v4_refresh.py --game revancha --pair-companion-audit',
      postDraw: `py tools\\v4_post_draw_audit.py --target-draw ${targetDraw || '<draw>'}`,
      historySync: 'py tools\\v4_history_sync_from_pakin.py --game revancha',
      winnerAudit: 'py tools\\v4_refresh.py --game revancha',
      visual: 'py tools\\v4_refresh.py --game revancha --export-visual-matrix',
      matrix: 'py tools\\v4_refresh.py --game revancha --export-visual-matrix',
      resultados: 'py local_cruncher_v4_2_calibrated.py',
    };
    return commands[key] || 'py tools\\v4_refresh.py --game revancha';
  }

  function inferTargetDraw(data) {
    if (finite(data?.slate?.latest_draw)) return Number(data.slate.latest_draw) + 1;
    if (finite(data?.visual?.latest_draw)) return Number(data.visual.latest_draw) + 1;
    if (finite(data?.historySync?.latest_draw)) return Number(data.historySync.latest_draw) + 1;
    if (finite(data?.postDraw?.target_draw)) return Number(data.postDraw.target_draw);
    return null;
  }

  function targetDrawText(data) {
    const targetDraw = inferTargetDraw(data);
    return targetDraw || 'not available';
  }

  function pairLagMode(data) {
    return data?.slate?.source_policy?.pair_lag_mode || data?.visual?.pair_lag_mode || 'not loaded';
  }

  function missingCriticalSources() {
    return CRITICAL_SOURCE_KEYS
      .filter(key => !state.sources[key]?.ok)
      .map(key => FILES[key]);
  }

  function renderSourceLoadErrors() {
    const failed = Object.entries(state.sources).filter(([, source]) => !source.ok);
    if (!failed.length) return '';
    return `
      <div class="cockpit-panel cockpit-panel-wide">
        <h3>Source load errors</h3>
        <ul>
          ${failed.map(([key, source]) => `
            <li>
              <b>${esc(source.path || FILES[key] || key)}</b>
              <span>HTTP ${esc(source.status || 'not available')}</span>
              <span>${esc(source.error || 'not available')}</span>
              <span>${source.lookedLikeHtml || source.nonJson ? 'non-JSON or HTML-like response' : 'fetch/load error'}</span>
              ${source.preview ? `<code>${esc(source.preview)}</code>` : ''}
            </li>`).join('')}
        </ul>
      </div>`;
  }

  function emptyState(section, filename, command) {
    return `
      <article class="cockpit-empty">
        <strong>${esc(section)} no disponible.</strong>
        <span>Fuente esperada: ${esc(filename)}</span>
        <code>Comando: ${esc(command)}</code>
      </article>`;
  }

  function metric(label, value, extraClass = '') {
    return `<article class="cockpit-metric ${extraClass}"><span>${esc(label)}</span><b>${esc(value)}</b></article>`;
  }

  function numberBalls(numbers, hitNumbers = []) {
    const hitSet = new Set(safeArray(hitNumbers).map(Number));
    if (!Array.isArray(numbers) || numbers.length === 0) return '<span class="cockpit-muted">not available</span>';
    return `<div class="cockpit-balls">${numbers.map(number => `<span class="cockpit-ball${hitSet.has(Number(number)) ? ' is-hit' : ''}">${esc(number)}</span>`).join('')}</div>`;
  }

  function bandPill(band) {
    const safeBand = clean(band).replace(/[^a-z0-9_-]/gi, '-');
    return `<span class="cockpit-pill cockpit-band cockpit-band-${safeBand}">${esc(band)}</span>`;
  }

  function rolePills(roles) {
    const allRoles = unique(roles);
    if (!allRoles.length) return '<span class="cockpit-pill" title="support">Support</span>';
    const visible = allRoles.slice(0, 4);
    const hidden = allRoles.length - visible.length;
    return `
      <div class="cockpit-role-pills">
        ${visible.map(role => `<span class="cockpit-pill cockpit-role" title="${esc(role)}">${esc(ROLE_LABELS[role] || role.replace(/_/g, ' '))}</span>`).join('')}
        ${hidden > 0 ? `<span class="cockpit-pill" title="${esc(allRoles.slice(4).join(', '))}">+${hidden} more</span>` : ''}
      </div>`;
  }

  function ticketRoles(ticket) {
    const roles = ticket?.roles;
    if (!isObject(roles)) return [];
    return unique(Object.values(roles).flat());
  }

  function ticketWhy(ticket) {
    const harmonic = ticket?.composition?.harmonic_coherence;
    const notes = safeArray(harmonic?.notes);
    const candidates = [
      ticket?.thesis,
      ticket?.human_explanation,
      ...notes,
      ticket?.reason,
      'Ticket included for V4.3 harmonic review using existing composition fields.',
    ];
    return unique(candidates).slice(0, 5);
  }

  function blockText(blocks) {
    if (!isObject(blocks)) return 'not available';
    return Object.entries(blocks).map(([key, value]) => `${key}:${value}`).join(' ');
  }

  function copyNumbers(numbers, button) {
    const value = safeArray(numbers).join(' ');
    if (!value) return;
    navigator.clipboard?.writeText(value).then(() => {
      const original = button.textContent;
      button.textContent = 'Copied';
      window.setTimeout(() => { button.textContent = original; }, 1200);
    }).catch(() => {
      button.textContent = value;
    });
  }

  function aggregateSumBands(tickets, validation) {
    if (isObject(validation?.slate_sum_distribution)) return validation.slate_sum_distribution;
    const counts = {};
    for (const ticket of safeArray(tickets)) {
      const band = ticket?.composition?.sum_band;
      if (band) counts[band] = (counts[band] || 0) + 1;
    }
    return counts;
  }

  function aggregateBlocks(tickets) {
    const counts = {};
    let total = 0;
    for (const ticket of safeArray(tickets)) {
      const blocks = ticket?.composition?.blocks;
      if (!isObject(blocks)) continue;
      for (const [block, count] of Object.entries(blocks)) {
        const value = Number(count) || 0;
        counts[block] = (counts[block] || 0) + value;
        total += value;
      }
    }
    return { counts, total };
  }

  function renderMissionControl(data, snapshot) {
    const slate = data.slate;
    const visual = data.visual;
    const history = data.historySync;
    const resultados = data.resultados;
    const postDraw = data.postDraw;
    const sourcePolicy = slate?.source_policy || {};
    const tickets = safeArray(slate?.slate);
    const latestDraw = slate?.latest_draw || visual?.latest_draw || history?.latest_draw || 'not available';
    const targetDraw = targetDrawText(data);
    const loaded = Object.values(state.sources).filter(source => source.ok).length;
    const total = Object.values(FILES).length + (snapshot ? 1 : 0);
    const snapshotText = snapshot?.ok ? `Snapshot frozen for ${targetDraw}` : 'Snapshot not loaded / unknown';
    const auditSnapshot = postDraw?.leakage_check ? `Audit leakage: ${clean(postDraw.leakage_check.status)}` : 'Audit not loaded';
    const currentPairLagMode = pairLagMode(data);
    const missingCritical = missingCriticalSources();
    const slateRefreshCommand = expectedCommand('slate');
    const slateMissingNote = !state.sources.slate?.ok
      ? `<p class="cockpit-note">Missing v4_hybrid_composition_slate.json. Run: ${esc(slateRefreshCommand)}</p>`
      : '';
    const pairLagNote = currentPairLagMode === 'not loaded'
      ? '<p class="cockpit-note">Pair-lag mode comes from v4_visual_pattern_output.json or v4_hybrid_composition_slate.json.</p>'
      : '';
    return `
      <section id="cockpit-mission" class="cockpit-zone cockpit-mission">
        <div class="cockpit-zone-heading">
          <p class="cockpit-kicker">Mission Control</p>
          <h2>V4.3 Decision Cockpit</h2>
          <p>Review the current harmonic candidate slate, support signals, risks, and post-draw accountability from already-generated JSON.</p>
        </div>
        <div class="cockpit-status-grid">
          ${metric('Last draw read', latestDraw, 'mono')}
          ${metric('Target draw', targetDraw, 'mono')}
          ${metric('System state', slate?.production_status || 'review_default')}
          ${metric('Sources loaded', `${loaded}/${total}`, 'mono')}
          ${metric('Ticket count', state.sources.slate?.ok ? tickets.length : 'Slate not loaded', 'mono')}
          ${metric('Pair-lag mode', currentPairLagMode)}
          ${metric('History sync latest', history?.latest_draw || 'not available', 'mono')}
          ${metric('Sync time', history?.generated_at || 'not available')}
          ${metric('V4.2 signal active', sourcePolicy.v42_signal_available || resultados?.number_scores ? 'yes' : 'no')}
          ${metric('Fallback mode', sourcePolicy.fallback_mode || 'none')}
          ${metric('Snapshot status', snapshotText)}
          ${metric('Post-draw status', auditSnapshot)}
        </div>
        <div class="cockpit-role-pills mt-3">
          <span class="cockpit-pill">Missing critical sources</span>
          ${missingCritical.length ? missingCritical.map(path => `<span class="cockpit-pill">${esc(path)}</span>`).join('') : '<span class="cockpit-pill">none</span>'}
        </div>
        ${slateMissingNote}
        ${pairLagNote}
        ${renderSourceLoadErrors()}
      </section>`;
  }

  function renderTicket(ticket, index) {
    const composition = ticket?.composition || {};
    const harmonic = composition?.harmonic_coherence || {};
    const numbers = safeArray(ticket?.numbers);
    const type = ticket?.ticket_type || 'composition';
    const whyItems = ticketWhy(ticket);
    const risks = unique(ticket?.risk_notes).slice(0, 5);
    return `
      <article class="cockpit-ticket">
        <header class="cockpit-ticket-header">
          <div>
            <p class="cockpit-kicker">Ticket ${index + 1}</p>
            <h3 title="${esc(type)}">${esc(TICKET_TYPE_LABELS[type] || type.replace(/_/g, ' '))}</h3>
          </div>
          <div class="cockpit-ticket-score">
            <span>harmonic coherence</span>
            <b>${fmt(harmonic.score, 3)}</b>
            ${finite(ticket?.selection_score) ? `<small>selection ${fmt(ticket.selection_score, 3)}</small>` : ''}
          </div>
        </header>
        <div class="cockpit-ticket-numbers">
          ${numberBalls(numbers)}
          <button class="cockpit-copy" type="button" data-copy="${esc(numbers.join(' '))}">Copy numbers</button>
        </div>
        <div class="cockpit-ticket-meta">
          ${metric('Sum', composition.sum || 'not available', 'mono')}
          ${metric('Sum band', composition.sum_band ? bandPill(composition.sum_band) : 'not available')}
          ${metric('Immediate overlap', composition.immediate_overlap_previous_draw ?? 'not available', 'mono')}
          ${metric('Blocks', blockText(composition.blocks))}
        </div>
        ${rolePills(ticketRoles(ticket))}
        <details class="cockpit-ticket-why" open>
          <summary>Why this ticket exists</summary>
          <ul>${whyItems.map(item => `<li>${esc(item)}</li>`).join('')}</ul>
        </details>
        ${risks.length ? `<div class="cockpit-risk"><b>Risk notes</b><ul>${risks.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>` : ''}
      </article>`;
  }

  function renderRecommendedSlate(data) {
    const slate = data.slate;
    if (!slate) {
      return `<section id="cockpit-slate" class="cockpit-zone">${emptyState('Recommended Slate', FILES.slate, expectedCommand('slate'))}</section>`;
    }
    const tickets = safeArray(slate.slate);
    return `
      <section id="cockpit-slate" class="cockpit-zone cockpit-slate">
        <div class="cockpit-zone-heading">
          <p class="cockpit-kicker">Recommended Slate</p>
          <h2>Tickets to review today</h2>
          <p>Each card shows existing V4.3 composition support, visible roles, and risk notes.</p>
        </div>
        <div class="cockpit-ticket-grid">
          ${tickets.map(renderTicket).join('') || emptyState('Recommended Slate', FILES.slate, expectedCommand('slate'))}
        </div>
      </section>`;
  }

  function renderDiagnostics(data) {
    const slate = data.slate;
    const tickets = safeArray(slate?.slate);
    const validation = slate?.validation_summary || {};
    const sumBands = aggregateSumBands(tickets, validation);
    const pairSummary = validation.pair_companion_summary || {};
    const pair = data.pair;
    const blocks = aggregateBlocks(tickets);
    const risks = unique(tickets.flatMap(ticket => safeArray(ticket?.risk_notes))).slice(0, 8);
    const typeCounts = {};
    for (const ticket of tickets) {
      const type = ticket?.ticket_type || 'unknown';
      typeCounts[type] = (typeCounts[type] || 0) + 1;
    }
    const oneBlockDominates = Object.values(blocks.counts).some(value => blocks.total && value / blocks.total > 0.5);
    const sameBand = Object.keys(sumBands).length === 1 && tickets.length > 1;
    const tooManyExtreme = Number(sumBands.extreme_high || 0) > 1;
    const body = `
      <div class="cockpit-diagnostics-grid">
        <article class="cockpit-panel">
          <h3>Sum band distribution</h3>
          <div class="cockpit-band-row">${SUM_BANDS.map(band => `<span>${bandPill(band)} <b>${intText(sumBands[band] || 0)}</b></span>`).join('')}</div>
          ${(tooManyExtreme || sameBand) ? `<p class="cockpit-note">Review note: ${tooManyExtreme ? 'more than one extreme_high ticket. ' : ''}${sameBand ? 'all tickets share one sum band.' : ''}</p>` : ''}
        </article>
        <article class="cockpit-panel">
          <h3>Pair companion summary</h3>
          <div class="cockpit-mini-grid">
            ${metric('Co-travel pairs', pairSummary.top_co_travel_pairs ?? safeArray(pair?.top_co_travel_pairs).length, 'mono')}
            ${metric('Bridge pairs', pairSummary.top_block_bridge_pairs ?? safeArray(pair?.top_block_bridge_pairs).length, 'mono')}
            ${metric('Anti-pairs', pairSummary.anti_pairs ?? safeArray(pair?.anti_pairs).length, 'mono')}
            ${metric('Clusters', safeArray(pair?.cluster_companions).length, 'mono')}
          </div>
        </article>
        <article class="cockpit-panel">
          <h3>Block distribution</h3>
          <p>${esc(blockText(blocks.counts))}</p>
          ${oneBlockDominates ? '<p class="cockpit-note">Review note: one block carries more than half of visible ticket positions.</p>' : ''}
        </article>
        <article class="cockpit-panel">
          <h3>Thesis diversity</h3>
          <p>${esc(blockText(typeCounts))}</p>
          <p class="cockpit-note">${Object.keys(typeCounts).length > 2 ? 'Slate has multiple ticket theses.' : 'Slate is concentrated by ticket type.'}</p>
        </article>
        <article class="cockpit-panel cockpit-panel-wide">
          <h3>Slate risk notes</h3>
          ${risks.length ? `<ul>${risks.map(item => `<li>${esc(item)}</li>`).join('')}</ul>` : '<p>No visible risk notes in loaded slate.</p>'}
        </article>
        <article class="cockpit-panel cockpit-panel-wide">
          <h3>Visual matrix export</h3>
          ${data.matrix ? renderMatrixPaths(data.matrix) : emptyState('Visual matrix export', FILES.matrix, expectedCommand('matrix'))}
        </article>
      </div>`;
    return `
      <details id="cockpit-diagnostics" class="cockpit-zone cockpit-details" open>
        <summary>
          <span>
            <small class="cockpit-kicker">Slate Diagnostics</small>
            <b>Composition support, risk and source diagnostics</b>
          </span>
        </summary>
        ${body}
      </details>`;
  }

  function renderMatrixPaths(matrix) {
    const paths = matrix?.paths;
    if (!isObject(paths)) return '<p>Visual matrix paths not available.</p>';
    return `<ul>${Object.entries(paths).map(([key, value]) => `<li><b>${esc(key)}:</b> ${esc(value)}</li>`).join('')}</ul>
      <p class="cockpit-note">visual_exports paths are diagnostics only, not canonical history.</p>`;
  }

  function renderPostDraw(data, targetDraw) {
    const audit = data.postDraw;
    if (!audit) {
      return `
        <section id="cockpit-audit" class="cockpit-zone cockpit-audit">
          ${emptyState('Post-draw audit', FILES.postDraw, expectedCommand('postDraw', targetDraw))}
          <article class="cockpit-empty">
            <strong>No post-draw audit available.</strong>
            <span>To audit draw ${esc(targetDraw || '<draw>')}:</span>
            <code>1. Add official result to revancha.csv</code>
            <code>2. Run: ${esc(expectedCommand('postDraw', targetDraw))}</code>
            <code>3. Refresh this page.</code>
          </article>
        </section>`;
    }
    const leakage = audit.leakage_check || {};
    const results = safeArray(audit.ticket_results);
    const roleSummary = audit.role_hit_summary || {};
    const matchedRoles = Object.entries(roleSummary).filter(([, row]) => Number(row?.hits || 0) > 0);
    const zeroRoles = Object.entries(roleSummary).filter(([, row]) => Number(row?.hits || 0) === 0);
    return `
      <section id="cockpit-audit" class="cockpit-zone cockpit-audit">
        <div class="cockpit-zone-heading">
          <p class="cockpit-kicker">Post-Draw Audit</p>
          <h2>Draw ${esc(audit.target_draw || 'not available')} review</h2>
          <p>Audit generated at ${esc(audit.generated_at || 'not available')}. Leakage status: ${esc(leakage.status || 'not available')}.</p>
        </div>
        ${leakage.status && leakage.status !== 'ok' ? `<p class="cockpit-note">Leakage check note: ${esc(leakage.reason || leakage.status)}</p>` : ''}
        <div class="cockpit-status-grid">
          ${metric('Best ticket hits', audit.best_ticket_hits ?? 'not available', 'mono')}
          ${metric('Avg hits', fmt(audit.avg_hits, 2), 'mono')}
          ${metric('Zero-ticket count', audit.zero_ticket_count ?? 'not available', 'mono')}
          ${metric('Hit >= 1', audit.hit_ge_1_count ?? 'not available', 'mono')}
          ${metric('Hit >= 2', audit.hit_ge_2_count ?? 'not available', 'mono')}
          ${metric('Hit >= 3', audit.hit_ge_3_count ?? 'not available', 'mono')}
        </div>
        <div class="cockpit-audit-grid">
          ${results.map(result => `
            <article class="cockpit-result-card">
              <h3>${esc(result.ticket_id || 'ticket')}</h3>
              <p>${esc(result.ticket_type || 'not available')}</p>
              ${numberBalls(result.numbers, result.hit_numbers)}
              <p><b>${intText(result.hits)}</b> matches. Sum band: ${esc(result.sum_band || 'not available')}</p>
            </article>`).join('')}
        </div>
        <div class="cockpit-diagnostics-grid">
          <article class="cockpit-panel">
            <h3>Roles with matches</h3>
            ${matchedRoles.length ? `<ul>${matchedRoles.map(([role, row]) => `<li>${esc(role)}: ${intText(row.hits)} / ${intText(row.total)}</li>`).join('')}</ul>` : '<p>not available</p>'}
          </article>
          <article class="cockpit-panel">
            <h3>Roles with zero matches</h3>
            ${zeroRoles.length ? `<ul>${zeroRoles.map(([role, row]) => `<li>${esc(role)}: 0 / ${intText(row.total)}</li>`).join('')}</ul>` : '<p>not available</p>'}
          </article>
          <article class="cockpit-panel cockpit-panel-wide">
            <h3>Thesis result</h3>
            <p>Block profile: ${esc(blockText(audit.actual_draw_block_profile))}</p>
            <p>Pair/co-travel profile: ${esc(clean(audit.actual_draw_pair_co_travel_profile))}</p>
            <p>Sum band result: ${esc(clean(audit.sum_band_result))}</p>
            <p>Matched slate thesis: ${esc(audit.actual_draw_matched_slate_thesis ?? 'not available')}</p>
            <p>New harmonic pattern to review: ${esc(audit.new_harmonic_pattern_to_review ?? 'not available')}</p>
          </article>
        </div>
      </section>`;
  }

  function renderSystemDiagnostics(data, snapshot) {
    const loaded = Object.entries(state.sources).filter(([, source]) => source.ok);
    const missing = Object.entries(state.sources).filter(([, source]) => !source.ok);
    return `
      <details id="cockpit-system" class="cockpit-zone cockpit-details">
        <summary>
          <span>
            <small class="cockpit-kicker">System Diagnostics</small>
            <b>JSON loading, source paths and optional artifacts</b>
          </span>
        </summary>
        <div class="cockpit-diagnostics-grid">
          <article class="cockpit-panel">
            <h3>JSONs loaded</h3>
            <ul>${loaded.map(([key, source]) => `<li>${esc(key)}: ${esc(source.path)} (${fmt(source.ms, 0)} ms)</li>`).join('') || '<li>none</li>'}</ul>
          </article>
          <article class="cockpit-panel">
            <h3>JSONs missing</h3>
            <ul>${missing.map(([key, source]) => `<li>${esc(key)}: ${esc(source.path)} (${esc(source.error || source.status)})</li>`).join('') || '<li>none</li>'}</ul>
          </article>
          <article class="cockpit-panel cockpit-panel-wide">
            <h3>Snapshot</h3>
            <p>${snapshot?.ok ? `Loaded ${esc(snapshot.path)}` : `Snapshot not loaded / unknown (${esc(snapshot?.path || 'not attempted')})`}</p>
          </article>
        </div>
      </details>`;
  }

  function renderFooter() {
    return '<footer class="cockpit-footer">Este sistema es experimental. Los scores y composiciones son metricas de auditoria interna, no probabilidades garantizadas. production_status: review_default.</footer>';
  }

  function render(data, snapshot) {
    const root = byId('v43-cockpit-root');
    if (!root) return;
    const targetDraw = inferTargetDraw(data);
    root.innerHTML = `
      ${renderMissionControl(data, snapshot)}
      ${renderRecommendedSlate(data)}
      ${renderDiagnostics(data)}
      ${renderPostDraw(data, targetDraw)}
      ${renderSystemDiagnostics(data, snapshot)}
      ${renderFooter()}`;
    root.querySelectorAll('[data-copy]').forEach(button => {
      button.addEventListener('click', () => copyNumbers(button.dataset.copy.split(' ').map(Number), button));
    });
    if (window.matchMedia('(max-width: 639px)').matches) {
      root.querySelectorAll('.cockpit-ticket-why[open], #cockpit-diagnostics[open]').forEach(details => details.removeAttribute('open'));
    }
  }

  async function loadAll() {
    state.loadStartedAt = performance.now();
    const entries = await Promise.all(Object.entries(FILES).map(async ([key, path]) => [key, await loadJson(path)]));
    state.sources = Object.fromEntries(entries);
    const data = Object.fromEntries(entries.map(([key, source]) => [key, source.data]));
    const targetDraw = inferTargetDraw(data);
    let snapshot = null;
    if (targetDraw) {
      const path = `v4_predraw_slate_snapshots/v4_predraw_slate_target_${targetDraw}.json`;
      snapshot = await loadJson(path);
      state.sources.snapshot = snapshot;
    }
    state.loadEndedAt = performance.now();
    render(data, snapshot);
  }

  document.addEventListener('DOMContentLoaded', () => {
    loadAll();
  });
  document.addEventListener('fisicapapa:v42-ready', () => {
    loadAll();
  });
  window.renderV43DecisionCockpit = loadAll;
})();
