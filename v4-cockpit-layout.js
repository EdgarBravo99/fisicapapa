// v4-cockpit-layout.js
// Read-only V4.4 Decision Cockpit renderer. It presents generated JSON fields only.
(function () {
  'use strict';

  window.FISICAPAPA_V44_COCKPIT_ACTIVE = true;

  const FILES = {
    slate: 'v4_combination_slate.json',
    slateLegacy: 'v4_hybrid_composition_slate.json',
    pair: 'v4_pair_companion_audit.json',
    gapEcho: 'v4_gap_echo_output.json',
    signatureHistory: 'v4_signature_history.json',
    pairLag: 'v4_pair_lag_signals.json',
    blockCompletion: 'v4_block_completion_signals.json',
    winnerProfile: 'v4_winner_profile.json',
    recentComposition: 'v4_recent_composition_profile.json',
    postDraw: 'v4_post_draw_audit.json',
    matrix: 'v4_visual_matrix_export_report.json',
  };

  const CRITICAL_SOURCE_KEYS = ['slate', 'gapEcho', 'signatureHistory', 'pairLag', 'blockCompletion', 'winnerProfile', 'recentComposition'];
  const OPTIONAL_SOURCE_KEYS = ['postDraw', 'matrix', 'pair', 'slateLegacy'];
  const ROOT_ID = 'v44-cockpit-root';
  const LEGACY_ROOT_ID = 'v43-cockpit-root';
  const SUM_BANDS = ['low_tail', 'historical_core', 'upper_core', 'high_tail', 'extreme_high'];

  const TICKET_TYPE_LABELS = {
    pair_sum_structure: 'Par, suma y estructura',
    recent_signature_fit: 'Firma reciente',
    block_completion_main: 'Cierre de bloque',
    pair_companion_bridge: 'Puente companion',
    controlled_contrarian: 'Contraria controlada',
    composition_main: 'V4.3 armonía principal',
    activated_block_main: 'V4.3 bloque activo',
    pair_lag_support: 'V4.3 soporte pair-lag',
    visual_support: 'V4.3 soporte visual',
    balanced_hybrid: 'V4.3 balance híbrido',
  };

  const SIGNAL_LABELS = {
    gap_echo: 'Eco de gap',
    signature_history: 'Firma histórica',
    pair_lag_candidate: 'Pair-lag candidato',
    pair_lag_trigger: 'Pair-lag gatillo',
    pair_companion: 'Par companion',
    block_completion: 'Cierre de bloque',
    recent_frequency: 'Frecuencia reciente',
    winner_profile_fit: 'Perfil ganador',
    structure_completion: 'Cierre estructural',
    zone_fit: 'Zona compatible',
  };

  const state = { sources: {}, loadStartedAt: 0, loadEndedAt: 0 };

  const byId = id => document.getElementById(id);
  const isObject = value => value && typeof value === 'object' && !Array.isArray(value);
  const safeArray = value => Array.isArray(value) ? value : [];
  const finite = value => value !== null && value !== undefined && value !== '' && Number.isFinite(Number(value));
  const clean = value => {
    if (value === null || value === undefined || Number.isNaN(value) || value === '') return 'no disponible';
    if (Array.isArray(value)) return value.map(clean).join(', ');
    if (typeof value === 'object') return Object.entries(value).map(([key, item]) => `${key}: ${clean(item)}`).join(', ');
    return String(value);
  };
  const esc = value => clean(value).replace(/[&<>"']/g, mark => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[mark]));
  const fmt = (value, digits = 2) => finite(value) ? Number(value).toFixed(digits) : 'no disponible';
  const intText = value => finite(value) ? String(Math.trunc(Number(value))) : 'no disponible';

  function unique(items) {
    const seen = new Set();
    const output = [];
    for (const item of safeArray(items)) {
      const text = clean(item);
      if (!seen.has(text) && text !== 'no disponible') {
        seen.add(text);
        output.push(text);
      }
    }
    return output;
  }

  async function loadJson(path) {
    const url = `${path}?v44=${Date.now()}`;
    const startedAt = performance.now();
    try {
      const response = await fetch(url, { cache: 'no-store', headers: { Accept: 'application/json,text/plain,*/*' } });
      const raw = (await response.text()).replace(/^\uFEFF/, '').trim();
      const preview = raw.slice(0, 80).replace(/\s+/g, ' ');
      if (!response.ok) {
        return { path, ok: false, status: response.status, error: `HTTP ${response.status}`, preview, nonJson: preview.startsWith('<'), data: null, ms: performance.now() - startedAt };
      }
      if (!raw || raw[0] === '<') {
        return { path, ok: false, status: response.status, error: raw ? 'respuesta no JSON' : 'respuesta vacía', preview, nonJson: true, data: null, ms: performance.now() - startedAt };
      }
      try {
        return { path, ok: true, status: response.status, error: null, preview: '', nonJson: false, data: JSON.parse(raw), ms: performance.now() - startedAt };
      } catch (err) {
        return { path, ok: false, status: response.status, error: err?.message || String(err), preview, nonJson: true, data: null, ms: performance.now() - startedAt };
      }
    } catch (err) {
      return { path, ok: false, status: 0, error: err?.message || String(err), preview: '', nonJson: false, data: null, ms: performance.now() - startedAt };
    }
  }

  function expectedCommand(key, targetDraw) {
    const commands = {
      slate: 'py tools\\v4_refresh.py --game revancha --scrape --reconstruct --full-signals --recent-composition --construct',
      gapEcho: 'py tools\\v4_gap_echo_engine.py',
      signatureHistory: 'py tools\\v4_signature_history_engine.py',
      pairLag: 'py tools\\v4_pair_lag_constructor.py',
      blockCompletion: 'py tools\\v4_block_completion_engine.py',
      winnerProfile: 'py tools\\v4_winner_profile_engine.py',
      recentComposition: 'py tools\\v4_recent_composition_engine.py',
      postDraw: `py tools\\v4_post_draw_audit.py --target-draw ${targetDraw || '<draw>'}`,
      matrix: 'py tools\\v4_visual_matrix_export.py',
      pair: 'py tools\\v4_pair_companion_audit.py',
      slateLegacy: 'py tools\\v4_refresh.py --game revancha --sync-history-from-pakin --export-visual-matrix --pair-companion-audit --snapshot-predraw',
    };
    return commands[key] || commands.slate;
  }

  function primarySlate(data) {
    if (data.slate?.tickets?.length) return { slate: data.slate, tickets: data.slate.tickets, source: 'V4.4' };
    if (data.slateLegacy?.slate?.length) return { slate: data.slateLegacy, tickets: data.slateLegacy.slate, source: 'V4.3 fallback' };
    return { slate: data.slate || data.slateLegacy || {}, tickets: [], source: 'no disponible' };
  }

  function inferTargetDraw(data) {
    const { slate } = primarySlate(data);
    if (finite(slate?.target_draw)) return Number(slate.target_draw);
    if (finite(slate?.latest_draw)) return Number(slate.latest_draw) + 1;
    if (finite(data.recentComposition?.latest_draw)) return Number(data.recentComposition.latest_draw) + 1;
    if (finite(data.postDraw?.target_draw)) return Number(data.postDraw.target_draw);
    return null;
  }

  function emptyState(section, filename, command) {
    return `<article class="cockpit-empty"><b>${esc(section)} no disponible.</b><span>Fuente esperada: ${esc(filename)}</span><code>Comando: ${esc(command)}</code></article>`;
  }

  function metric(label, value, extraClass = '') {
    return `<article class="cockpit-metric ${extraClass}"><span>${esc(label)}</span><b>${esc(value)}</b></article>`;
  }

  function bandPill(band) {
    const key = clean(band);
    return `<span class="cockpit-pill cockpit-band cockpit-band-${esc(key)}">${esc(key)}</span>`;
  }

  function sourceErrors() {
    const failed = Object.entries(state.sources).filter(([key, source]) => CRITICAL_SOURCE_KEYS.includes(key) && !source.ok);
    if (!failed.length) return '';
    return `<div class="cockpit-panel cockpit-panel-wide"><h3>Errores críticos de fuentes</h3><ul>${failed.map(([key, source]) => `<li><b>${esc(source.path || FILES[key])}</b>: HTTP ${esc(source.status || 'N/D')}, ${esc(source.error || 'no disponible')} ${source.nonJson ? '(HTML/no JSON)' : ''} ${source.preview ? `<code>${esc(source.preview)}</code>` : ''}</li>`).join('')}</ul></div>`;
  }

  function renderControl(data) {
    const { slate, tickets, source } = primarySlate(data);
    const targetDraw = inferTargetDraw(data);
    const loaded = Object.values(state.sources).filter(sourceItem => sourceItem.ok).length;
    const missingCritical = CRITICAL_SOURCE_KEYS.filter(key => !state.sources[key]?.ok).map(key => FILES[key]);
    return `<section id="cockpit-control" class="cockpit-zone">
      <div class="cockpit-zone-heading">
        <p class="cockpit-kicker">Control del sistema</p>
        <h2>V4.4 constructor cockpit</h2>
        <p>Fuente principal: ${esc(source)}. production_status: ${esc(slate.production_status || 'review_default')}.</p>
      </div>
      <div class="cockpit-status-grid">
        ${metric('Último sorteo leído', slate.latest_draw || data.recentComposition?.latest_draw || 'no disponible', 'mono')}
        ${metric('Sorteo objetivo', targetDraw || 'no disponible', 'mono')}
        ${metric('Estado del sistema', slate.production_status || 'review_default')}
        ${metric('Fuentes cargadas', `${loaded}/${Object.keys(FILES).length}`, 'mono')}
        ${metric('Boletos', tickets.length || 'no disponible', 'mono')}
        ${metric('Perfil reciente', data.recentComposition?.window ? `últimas ${data.recentComposition.window}` : 'no cargado')}
        ${metric('Modo pair-lag', data.pairLag?.lag_window ? `ventana ${data.pairLag.lag_window}` : 'no cargado')}
        ${metric('Fallback', source === 'V4.3 fallback' ? 'V4.3 legacy' : 'no')}
      </div>
      <div class="cockpit-panel cockpit-panel-wide">
        <h3>Fuentes críticas faltantes</h3>
        <p>${missingCritical.length ? esc(missingCritical.join(', ')) : 'ninguna'}</p>
        ${missingCritical.length ? `<code>${esc(expectedCommand('slate', targetDraw))}</code>` : ''}
      </div>
      ${sourceErrors()}
    </section>`;
  }

  function numberBalls(numbers) {
    return `<div class="cockpit-balls">${safeArray(numbers).map(number => `<span class="cockpit-ball">${esc(number)}</span>`).join('')}</div>`;
  }

  function signalChips(signals) {
    return safeArray(signals).map(signal => `<span class="cockpit-pill" title="${esc(signal)}">${esc(SIGNAL_LABELS[signal] || signal)}</span>`).join('');
  }

  function renderTicket(ticket, index) {
    const numbers = safeArray(ticket.numbers);
    const composition = isObject(ticket.composition) ? ticket.composition : {};
    const trace = safeArray(ticket.construction_trace_es);
    const risks = unique(ticket.risk_notes_es).slice(0, 6);
    const signalRows = numbers.map(number => {
      const signals = safeArray(ticket.signals?.[String(number)]);
      return `<article class="cockpit-panel"><h5>${esc(number)}</h5><div class="cockpit-role-pills">${signalChips(signals)}</div></article>`;
    }).join('');
    return `<article class="cockpit-ticket">
      <div class="cockpit-ticket-header">
        <div>
          <p class="cockpit-kicker">Boleto ${index + 1}</p>
          <h3 title="${esc(ticket.ticket_type)}">${esc(TICKET_TYPE_LABELS[ticket.ticket_type] || ticket.ticket_type)}</h3>
        </div>
        <button class="cockpit-copy" data-copy="${esc(numbers.join(' '))}">Copiar</button>
      </div>
      ${numberBalls(numbers)}
      <div class="cockpit-mini-grid">
        ${metric('Suma', composition.sum || 'no disponible', 'mono')}
        ${metric('Banda', `${composition.sum_band_es || 'no disponible'} (${composition.sum_band || 'N/D'})`)}
        ${metric('Firma de bloques', composition.block_signature || 'no disponible', 'mono')}
        ${metric('Presencia visual', composition.block_presence_signature || 'no disponible', 'mono')}
        ${metric('Lectura visual', composition.visual_structure_label_es || 'no disponible')}
        ${metric('Paridad', composition.parity || 'no disponible')}
        ${metric('Repetidos', composition.immediate_overlap_label_es || 'no disponible')}
        ${metric('Pair companion', composition.pair_companion_count ?? 'no disponible', 'mono')}
        ${metric('Pair-lag', composition.pair_lag_relation_count ?? 'no disponible', 'mono')}
        ${metric('Perfil reciente', composition.matches_recent_profile ? 'alineado' : 'revisar')}
        ${metric('Perfil histórico', composition.matches_winner_profile ? 'alineado' : 'revisar')}
      </div>
      <section class="cockpit-ticket-why">
        <h4>Por qué existe este boleto</h4>
        <p>${esc(ticket.reason_es || 'Boleto formado desde señales activas y estructura histórica.')}</p>
        <p>${esc(ticket.thesis_es || 'Tesis no disponible.')}</p>
        <p class="cockpit-note">${esc(composition.immediate_overlap_reason_es || 'Repetidos inmediatos medidos, no bloqueados automáticamente.')}</p>
      </section>
      <details class="cockpit-ticket-why" open>
        <summary>Trazabilidad de construcción</summary>
        <ul>${trace.map(item => `<li>${esc(item)}</li>`).join('') || '<li>no disponible</li>'}</ul>
      </details>
      <details class="cockpit-ticket-why">
        <summary>Señales activas por número</summary>
        <div class="cockpit-diagnostics-grid">${signalRows}</div>
      </details>
      ${risks.length ? `<div class="cockpit-risk"><b>Notas de riesgo</b><ul>${risks.map(item => `<li>${esc(item)}</li>`).join('')}</ul></div>` : ''}
      <details class="cockpit-ticket-why">
        <summary>JSON crudo</summary>
        <pre>${esc(JSON.stringify(ticket, null, 2))}</pre>
      </details>
    </article>`;
  }

  function renderSlate(data) {
    const { tickets, source } = primarySlate(data);
    if (!tickets.length) {
      return `<section id="cockpit-slate" class="cockpit-zone">${emptyState('Boletos V4.4', FILES.slate, expectedCommand('slate', inferTargetDraw(data)))}</section>`;
    }
    return `<section id="cockpit-slate" class="cockpit-zone">
      <div class="cockpit-zone-heading">
        <p class="cockpit-kicker">Boletos sugeridos</p>
        <h2>5 formaciones para revisión</h2>
        <p>${esc(source)}. Cada boleto muestra señales activas, composición, repetidos inmediatos y trazabilidad en español.</p>
      </div>
      <div class="cockpit-ticket-grid">${tickets.slice(0, 5).map(renderTicket).join('')}</div>
    </section>`;
  }

  function renderDistribution(distribution) {
    if (!isObject(distribution)) return '<p>no disponible</p>';
    return `<ul>${Object.entries(distribution).map(([key, value]) => `<li><b>${esc(key)}:</b> ${esc(value)}</li>`).join('')}</ul>`;
  }

  function renderDiagnostics(data) {
    const { slate } = primarySlate(data);
    const recent = data.recentComposition || {};
    const winner = data.winnerProfile || {};
    const summary = slate.slate_structure_summary || {};
    const gapActive = safeArray(data.gapEcho?.active_candidates).slice(0, 20);
    const lagActive = safeArray(data.pairLag?.active_candidates).slice(0, 20);
    const blockGroups = safeArray(data.blockCompletion?.groups).slice(0, 6);
    return `<section id="cockpit-diagnostics" class="cockpit-zone">
      <div class="cockpit-zone-heading">
        <p class="cockpit-kicker">Diagnóstico</p>
        <h2>Perfil reciente, histórico y señales globales</h2>
      </div>
      <div class="cockpit-diagnostics-grid">
        <article class="cockpit-panel">
          <h3>Perfil reciente de composición, últimas 30</h3>
          ${metric('Ventana', recent.window || 'no disponible')}
          ${metric('Banda dominante', recent.sum_profile?.dominant_sum_band || 'no disponible')}
          ${metric('Paridad dominante', recent.parity_profile?.dominant_parity || 'no disponible')}
          ${metric('Firma dominante', recent.presence_signature_profile?.dominant_presence_signature || 'no disponible')}
          ${metric('Repetido dominante', recent.immediate_overlap_profile?.dominant_immediate_overlap ?? 'no disponible')}
          <p>${esc(recent.summary_es || 'no disponible')}</p>
        </article>
        <article class="cockpit-panel">
          <h3>Uso de formación del conjunto</h3>
          ${metric('Pares companion usados', summary.pair_companion_usage_count ?? 'no disponible')}
          ${metric('Relaciones pair-lag usadas', summary.pair_lag_usage_count ?? 'no disponible')}
          ${metric('Cierres estructurales', summary.structure_completion_usage_count ?? 'no disponible')}
          <p>${esc(summary.recent_alignment_summary_es || 'no disponible')}</p>
          <p>${esc(summary.diversity_summary_es || 'no disponible')}</p>
          <p>${esc(summary.relaxation_summary_es || 'no disponible')}</p>
        </article>
        <article class="cockpit-panel">
          <h3>Perfil ganador histórico</h3>
          <h4>Bandas de suma</h4>${renderDistribution(winner.sum_profile?.sum_band_distribution)}
          <h4>Paridad</h4>${renderDistribution(winner.parity_profile?.parity_distribution)}
          <h4>Firma de presencia</h4>${renderDistribution(winner.presence_signature_profile?.presence_signature_distribution)}
          <h4>Repetidos inmediatos</h4>${renderDistribution(winner.immediate_overlap_profile?.immediate_overlap_distribution)}
        </article>
        <article class="cockpit-panel">
          <h3>Señales activas globales</h3>
          ${metric('Gap echo activos', gapActive.join(', ') || 'no disponible')}
          ${metric('Pair-lag activos', lagActive.join(', ') || 'no disponible')}
          ${metric('Firma actual', data.signatureHistory?.current_signature || 'no disponible')}
          ${metric('Presencia actual', data.signatureHistory?.current_presence_signature || 'no disponible')}
          ${metric('Respuesta frecuente', data.signatureHistory?.most_frequent_response || 'no disponible')}
          <h4>Bloques parcialmente activados</h4>
          <ul>${blockGroups.map(row => `<li>${esc(clean(row.numbers))}: vistos ${esc(clean(row.recent_seen))}, faltan ${esc(clean(row.missing))}</li>`).join('') || '<li>no disponible</li>'}</ul>
        </article>
      </div>
    </section>`;
  }

  function renderAudit(data) {
    const targetDraw = inferTargetDraw(data);
    const audit = data.postDraw;
    if (!audit) {
      return `<section id="cockpit-audit" class="cockpit-zone">${emptyState('Auditoría post-sorteo', FILES.postDraw, expectedCommand('postDraw', targetDraw))}</section>`;
    }
    return `<section id="cockpit-audit" class="cockpit-zone">
      <div class="cockpit-zone-heading">
        <p class="cockpit-kicker">Auditoría post-sorteo</p>
        <h2>Sorteo ${esc(audit.target_draw || audit.draw_id || 'no disponible')}</h2>
      </div>
      <div class="cockpit-status-grid">
        ${metric('Best ticket hits', audit.best_ticket_hits ?? 'no disponible')}
        ${metric('Avg hits', audit.avg_hits ?? 'no disponible')}
        ${metric('Cero hits', audit.zero_ticket_count ?? 'no disponible')}
        ${metric('Leakage check', audit.leakage_check?.status || 'no disponible')}
      </div>
      <p>${esc(audit.post_draw_summary_es || audit.structure_match_summary_es || 'Auditoría disponible como diagnóstico.')}</p>
    </section>`;
  }

  function renderSystemDiagnostics() {
    const optionalFailed = Object.entries(state.sources).filter(([key, source]) => OPTIONAL_SOURCE_KEYS.includes(key) && !source.ok);
    return `<details class="cockpit-zone cockpit-secondary-details">
      <summary><span><b>Diagnóstico de fuentes</b><small>JSONs cargados, faltantes opcionales y tiempos</small></span></summary>
      <div class="cockpit-diagnostics-grid">
        ${Object.entries(state.sources).map(([key, source]) => `<article class="cockpit-panel"><h3>${esc(FILES[key] || key)}</h3>${metric('Estado', source.ok ? 'cargado' : 'no cargado')}${metric('HTTP', source.status || 'N/D')}${metric('Tiempo', `${fmt(source.ms, 1)} ms`)}${source.error ? `<p>${esc(source.error)}</p>` : ''}${source.preview ? `<code>${esc(source.preview)}</code>` : ''}</article>`).join('')}
      </div>
      ${optionalFailed.length ? `<p class="cockpit-note">Fuentes opcionales no cargadas: ${esc(optionalFailed.map(([key]) => FILES[key]).join(', '))}</p>` : ''}
    </details>`;
  }

  async function loadAll() {
    state.loadStartedAt = performance.now();
    const entries = await Promise.all(Object.entries(FILES).map(async ([key, path]) => [key, await loadJson(path)]));
    state.sources = Object.fromEntries(entries);
    state.loadEndedAt = performance.now();
    const data = {};
    for (const [key, source] of Object.entries(state.sources)) {
      data[key] = source.ok ? source.data : null;
    }
    return data;
  }

  function wireCopyButtons(root) {
    root.querySelectorAll('[data-copy]').forEach(button => {
      button.addEventListener('click', async () => {
        const value = button.getAttribute('data-copy') || '';
        try {
          await navigator.clipboard.writeText(value);
          button.textContent = 'Copiado';
          setTimeout(() => { button.textContent = 'Copiar'; }, 1200);
        } catch (_) {
          button.textContent = value;
        }
      });
    });
  }

  async function render() {
    const root = byId(ROOT_ID) || byId(LEGACY_ROOT_ID);
    if (!root) return;
    const data = await loadAll();
    root.innerHTML = [
      renderControl(data),
      renderSlate(data),
      renderDiagnostics(data),
      renderAudit(data),
      renderSystemDiagnostics(),
      '<footer class="cockpit-footer">Este sistema es experimental. Los scores y composiciones son métricas de auditoría interna, no promesas ni certeza de resultado. production_status: review_default.</footer>',
    ].join('');
    wireCopyButtons(root);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
