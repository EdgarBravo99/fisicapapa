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
    physicsMaintenance: 'v4_physics_maintenance_notes.json',
  };

  const CRITICAL_SOURCE_KEYS = ['slate', 'gapEcho', 'signatureHistory', 'pairLag', 'blockCompletion', 'winnerProfile', 'recentComposition'];
  const OPTIONAL_SOURCE_KEYS = ['postDraw', 'matrix', 'pair', 'slateLegacy', 'physicsMaintenance'];
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
  const classToken = value => clean(value).normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^\w-]+/g, '_').replace(/^_+|_+$/g, '');

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
      physicsMaintenance: 'crear v4_physics_maintenance_notes.json manualmente',
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

  function countTicketSignal(ticket, names) {
    const wanted = new Set(safeArray(names));
    return Object.values(ticket.signals || {}).filter(items => safeArray(items).some(item => wanted.has(item))).length;
  }

  function matchesRecentWindow(ticket, recent, key) {
    const window = recentWindows(recent)?.[String(key)];
    const composition = ticket.composition || {};
    if (!window) return false;
    return Boolean(
      window.sum_profile?.dominant_sum_band === composition.sum_band
      || safeArray(window.sum_profile?.dominant_sum_bands).includes(composition.sum_band)
      || window.presence_signature_profile?.dominant_presence_signature === composition.block_presence_signature
      || safeArray(window.presence_signature_profile?.dominant_presence_signatures).includes(composition.block_presence_signature)
    );
  }

  function ticketIntersections(tickets) {
    const alerts = [];
    for (let i = 0; i < safeArray(tickets).length; i += 1) {
      for (let j = i + 1; j < safeArray(tickets).length; j += 1) {
        const first = new Set(safeArray(tickets[i].numbers).map(Number));
        const shared = safeArray(tickets[j].numbers).map(Number).filter(number => first.has(number));
        if (shared.length === 3) {
          alerts.push({ level: 'media', a: i + 1, b: j + 1, shared, text: `Boletos ${i + 1} y ${j + 1} se parecen bastante: comparten ${shared.join(', ')}.` });
        } else if (shared.length > 3) {
          alerts.push({ level: 'alta', a: i + 1, b: j + 1, shared, text: `Boletos ${i + 1} y ${j + 1}: no conviene jugar ambos salvo cobertura explícita. Comparten ${shared.join(', ')}.` });
        }
      }
    }
    return alerts;
  }

  function humanTicketDecision(ticket, data) {
    const composition = ticket.composition || {};
    const pairCompanion = Number(composition.pair_companion_count || 0);
    const pairLag = Number(composition.pair_lag_relation_count || 0);
    const overlap = finite(composition.immediate_overlap_previous_draw) ? Number(composition.immediate_overlap_previous_draw) : 0;
    const structureStrongCount = countTicketSignal(ticket, ['structure_completion', 'block_completion', 'zone_fit']);
    const hasPairs = pairCompanion > 0 || pairLag > 0;
    const matchesRecent = composition.matches_recent_profile === true;
    const matchesWinner = composition.matches_winner_profile === true;
    const awayFromWindow5 = !matchesRecentWindow(ticket, data.recentComposition, '5');
    const keepsWindow20Or30 = matchesRecentWindow(ticket, data.recentComposition, '20') || matchesRecentWindow(ticket, data.recentComposition, '30');
    const extremeWithoutSupport = composition.sum_band === 'extreme_high' && !hasPairs && structureStrongCount < 3;
    const coverageContrary = ticket.ticket_type === 'controlled_contrarian' || (awayFromWindow5 && keepsWindow20Or30);
    const high = pairCompanion > 0 && pairLag > 0 && matchesRecent && overlap <= 1;
    const medium = !high && (hasPairs || structureStrongCount >= 3) && (overlap === 2 || awayFromWindow5 || matchesRecent || matchesWinner);
    const low = !high && !medium && ((!hasPairs && !matchesRecent) || extremeWithoutSupport);
    const reviewBeforeUse = low || overlap >= 2 || extremeWithoutSupport;
    const priority = high ? 'prioridad_alta' : medium ? 'prioridad_media' : low ? 'prioridad_baja' : 'prioridad_media';
    const consider = [];
    const review = [];
    const avoid = [];
    const role = [];

    if (pairCompanion > 0) consider.push(`Tiene ${pairCompanion} relación(es) pair companion dentro del boleto.`);
    if (pairLag > 0) consider.push(`Tiene ${pairLag} relación(es) pair-lag internas.`);
    if (matchesRecent) consider.push('Conserva alineación con el perfil reciente cargado.');
    if (matchesWinner) consider.push('Conserva alineación con el perfil histórico.');
    if (structureStrongCount >= 3) consider.push(`Aporta cierre estructural en ${structureStrongCount} números.`);
    if (!consider.length) consider.push('Sirve como lectura secundaria porque conserva señales cargadas, pero requiere comparación manual.');

    if (overlap >= 2) review.push(`${overlap} repetidos inmediatos: revisar si esa exposición conviene dentro del conjunto.`);
    if (awayFromWindow5) review.push('Se aleja de la ventana de 5 sorteos; revisar contra ventanas 20 y 30.');
    if (composition.sum_band === 'extreme_high') review.push('Suma en extremo alto: revisar que no concentre todo el slate en la misma banda.');
    if (!hasPairs) review.push('Pocos pares internos detectados; revisar si la estructura compensa esa falta.');
    if (!review.length) review.push('Revisar duplicidad contra otros boletos antes de priorizarlo.');

    if (extremeWithoutSupport) avoid.push('No usarlo como boleto principal si la suma extrema no tiene soporte operativo suficiente.');
    if (!matchesRecent && !matchesWinner) avoid.push('No usarlo como prioridad si tampoco se alinea con perfil reciente ni histórico.');
    if (overlap >= 3) avoid.push('No usarlo sin justificación fuerte por exceso de repetidos inmediatos.');
    if (!avoid.length) avoid.push('No usarlo aislado de la lectura del slate completo.');

    if (coverageContrary) role.push('Cobertura contraria: ayuda a no concentrar toda la revisión en la misma tesis.');
    else if (high) role.push('Candidato principal de revisión por pares, perfil reciente y repetición controlada.');
    else if (medium) role.push('Candidato secundario: tiene soporte, pero requiere una revisión de ventana o repetidos.');
    else role.push('Candidato de baja prioridad: mantener solo si aporta cobertura que otros boletos no cubren.');

    return {
      priority,
      coverageContrary,
      reviewBeforeUse,
      awayFromWindow5,
      hasPairs,
      structureStrongCount,
      consider,
      review,
      avoid,
      role,
    };
  }

  function humanPriorityLabel(priority) {
    return {
      prioridad_alta: 'Prioridad alta',
      prioridad_media: 'Prioridad media',
      prioridad_baja: 'Prioridad baja',
    }[priority] || 'Prioridad media';
  }

  function renderHumanDecisionBlock(decision) {
    return `<section class="cockpit-human-read">
      <div class="cockpit-human-flags">
        <span class="cockpit-pill cockpit-priority-${esc(decision.priority)}">${esc(humanPriorityLabel(decision.priority))}</span>
        ${decision.coverageContrary ? '<span class="cockpit-pill">Cobertura contraria</span>' : ''}
        ${decision.reviewBeforeUse ? '<span class="cockpit-pill cockpit-pill-warning">Revisar antes de jugar</span>' : ''}
      </div>
      <div class="cockpit-human-grid">
        <article><h4>Por qué considerarlo</h4><ul>${decision.consider.map(item => `<li>${esc(item)}</li>`).join('')}</ul></article>
        <article><h4>Qué revisar</h4><ul>${decision.review.map(item => `<li>${esc(item)}</li>`).join('')}</ul></article>
        <article><h4>Cuándo no usarlo</h4><ul>${decision.avoid.map(item => `<li>${esc(item)}</li>`).join('')}</ul></article>
        <article><h4>Rol dentro del slate</h4><ul>${decision.role.map(item => `<li>${esc(item)}</li>`).join('')}</ul></article>
      </div>
    </section>`;
  }

  function buildDayDecision(data) {
    const { slate, tickets } = primarySlate(data);
    const regime = data.recentComposition?.recent_regime_summary || {};
    const priorities = safeArray(tickets).map(ticket => humanTicketDecision(ticket, data));
    const duplicateAlerts = ticketIntersections(tickets);
    const lowCount = priorities.filter(item => item.priority === 'prioridad_baja').length;
    const reviewCount = priorities.filter(item => item.reviewBeforeUse).length;
    const microShift = Boolean(regime.window_5_vs_20_shift || regime.window_20_vs_30_shift);
    const practicalAlerts = [];
    if (slate.production_status && slate.production_status !== 'review_default') practicalAlerts.push(`production_status es ${slate.production_status}; revisar estado antes de usar la vista.`);
    if (microShift) practicalAlerts.push('La ventana de 5 sorteos cambió contra ventanas mayores. Conviene revisar concentración por banda y firma.');
    if (lowCount) practicalAlerts.push(`${lowCount} boleto(s) quedan en prioridad baja por soporte limitado o desalineaciÃ³n.`);
    if (reviewCount) practicalAlerts.push(`${reviewCount} boleto(s) requieren revisión antes de jugar por repetidos, suma o ventana corta.`);
    duplicateAlerts.forEach(alert => practicalAlerts.push(alert.text));
    if (!tickets.length) practicalAlerts.push('No hay boletos cargados para traducir a decisión operativa.');

    const status = !tickets.length || duplicateAlerts.some(alert => alert.level === 'alta') || lowCount >= 3
      ? 'revisar antes de usar'
      : microShift || reviewCount || duplicateAlerts.length
        ? 'usable con revisión'
        : 'usable';
    const resumen = status === 'usable'
      ? 'Hay señales suficientes para revisar el slate sin alertas prácticas fuertes. Mantén la lectura como review_default.'
      : status === 'usable con revisión'
        ? 'Hay señales suficientes para revisar el slate, pero conviene ajustar prioridad por micro-régimen, repetidos o duplicidad entre boletos.'
        : 'El slate necesita revisión operativa antes de usarlo porque las alertas prácticas dominan la lectura.';

    return {
      estado_operativo_es: status,
      resumen_decision_es: resumen,
      alertas_practicas_es: practicalAlerts.length ? practicalAlerts : ['Sin alertas prácticas fuertes en la lectura cargada.'],
      priorities,
      duplicateAlerts,
    };
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

  function renderDecisionDay(data) {
    const decision = buildDayDecision(data);
    const { tickets, slate } = primarySlate(data);
    const summary = slate.slate_structure_summary || {};
    const windowsUsed = slate.recent_windows_used || {};
    return `<section id="cockpit-decision-day" class="cockpit-zone cockpit-human-zone">
      <div class="cockpit-zone-heading">
        <p class="cockpit-kicker">Decisión del día</p>
        <h2>Lectura humana del slate</h2>
        <p>Traducción operativa desde production_status, ventanas recientes, estructura del slate y boletos cargados. No modifica JSONs ni constructor.</p>
      </div>
      <div class="cockpit-decision-layout">
        <article class="cockpit-decision-main">
          <span class="cockpit-pill cockpit-priority-${esc(classToken(decision.estado_operativo_es))}">${esc(decision.estado_operativo_es)}</span>
          <h3>${esc(decision.resumen_decision_es)}</h3>
          <p>${esc(summary.recent_alignment_summary_es || 'Lectura de conjunto disponible solo desde los campos generados.')}</p>
          <div class="cockpit-mini-grid">
            ${metric('production_status', slate.production_status || 'review_default')}
            ${metric('Ventana 5 usada', windowsUsed['5']?.dominant_sum_band || 'no disponible')}
            ${metric('Ventana 20 usada', windowsUsed['20']?.dominant_sum_band || 'no disponible')}
            ${metric('Ventana 30 usada', windowsUsed['30']?.dominant_sum_band || 'no disponible')}
          </div>
        </article>
        <article class="cockpit-panel">
          <h3>Prioridad por boleto</h3>
          <ul class="cockpit-priority-list">
            ${decision.priorities.map((item, index) => `<li><b>Boleto ${index + 1}:</b> ${esc(humanPriorityLabel(item.priority))}${item.coverageContrary ? ' · cobertura contraria' : ''}${item.reviewBeforeUse ? ' · revisar antes de jugar' : ''}</li>`).join('') || '<li>no disponible</li>'}
          </ul>
        </article>
        <article class="cockpit-panel">
          <h3>Alertas prácticas</h3>
          <ul>${decision.alertas_practicas_es.map(item => `<li>${esc(item)}</li>`).join('')}</ul>
        </article>
        <article class="cockpit-panel">
          <h3>Duplicidad entre boletos</h3>
          <ul>${decision.duplicateAlerts.map(alert => `<li>${esc(alert.text)}</li>`).join('') || '<li>Sin duplicidad fuerte entre boletos cargados.</li>'}</ul>
          <p class="cockpit-note">${esc(tickets.length ? 'Comparación read-only entre boletos del slate.' : 'Sin boletos cargados para comparar.')}</p>
        </article>
      </div>
    </section>`;
  }

  function numberBalls(numbers) {
    return `<div class="cockpit-balls">${safeArray(numbers).map(number => `<span class="cockpit-ball">${esc(number)}</span>`).join('')}</div>`;
  }

  function signalChips(signals) {
    return safeArray(signals).map(signal => `<span class="cockpit-pill" title="${esc(signal)}">${esc(SIGNAL_LABELS[signal] || signal)}</span>`).join('');
  }

  function renderTicket(ticket, index, data) {
    const numbers = safeArray(ticket.numbers);
    const composition = isObject(ticket.composition) ? ticket.composition : {};
    const trace = safeArray(ticket.construction_trace_es);
    const risks = unique(ticket.risk_notes_es).slice(0, 6);
    const humanDecision = humanTicketDecision(ticket, data);
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
      ${renderHumanDecisionBlock(humanDecision)}
      <details class="cockpit-ticket-why cockpit-tech-details">
        <summary>Ver explicación técnica</summary>
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
      </details>
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
      <div class="cockpit-ticket-grid">${tickets.slice(0, 5).map((ticket, index) => renderTicket(ticket, index, data)).join('')}</div>
    </section>`;
  }

  function renderDistribution(distribution) {
    if (!isObject(distribution)) return '<p>no disponible</p>';
    return `<ul>${Object.entries(distribution).map(([key, value]) => `<li><b>${esc(key)}:</b> ${esc(value)}</li>`).join('')}</ul>`;
  }

  function recentWindows(recent) {
    if (isObject(recent?.windows)) return recent.windows;
    if (!recent) return null;
    return {
      source: 'legacy_window_30_only',
      30: {
        window: recent.window || 30,
        draws_used: safeArray(recent.draws_used),
        sum_profile: recent.sum_profile || {},
        parity_profile: recent.parity_profile || {},
        presence_signature_profile: recent.presence_signature_profile || {},
        immediate_overlap_profile: recent.immediate_overlap_profile || {},
        pair_companion_profile: recent.pair_companion_profile || {},
        top_recent_numbers: safeArray(recent.top_recent_numbers),
      },
    };
  }

  function renderPairList(rows, limit = 4) {
    return safeArray(rows).slice(0, limit).map(row => safeArray(row.pair).join('-')).filter(Boolean).join(', ') || 'no disponible';
  }

  function renderTopNumbers(rows, limit = 8) {
    return safeArray(rows).slice(0, limit).map(row => row.number).filter(value => value !== undefined).join(', ') || 'no disponible';
  }

  function renderRecentWindowsPanel(recent) {
    const windows = recentWindows(recent);
    if (!windows || windows.source === 'legacy_window_30_only') {
      return `<article class="cockpit-panel cockpit-panel-wide"><h3>Ventanas recientes</h3><p>Ventanas múltiples no disponibles. Actualiza el pipeline con PR #40.</p><code>${esc(expectedCommand('slate'))}</code></article>`;
    }
    const rows = ['5', '20', '30'].map(key => {
      const window = windows[key] || {};
      return `<tr>
        <td>Últimos ${esc(key)}</td>
        <td>${esc(window.sum_profile?.dominant_sum_band || 'no disponible')}</td>
        <td>${esc(window.parity_profile?.dominant_parity || 'no disponible')}</td>
        <td><code>${esc(window.presence_signature_profile?.dominant_presence_signature || 'no disponible')}</code></td>
        <td>${esc(window.immediate_overlap_profile?.dominant_immediate_overlap ?? 'no disponible')}</td>
        <td>${esc(renderTopNumbers(window.top_recent_numbers, 6))}</td>
        <td>${esc(renderPairList(window.pair_companion_profile?.top_pair_companions, 3))}</td>
      </tr>`;
    }).join('');
    return `<article class="cockpit-panel cockpit-panel-wide">
      <h3>Ventanas recientes</h3>
      <div class="cockpit-table-wrap"><table class="cockpit-table">
        <thead><tr><th>Ventana</th><th>Banda suma</th><th>Paridad</th><th>Firma presencia</th><th>Repetido dominante</th><th>Top números</th><th>Top pares companion</th></tr></thead>
        <tbody>${rows}</tbody>
      </table></div>
    </article>`;
  }

  function renderRegimePanel(recent) {
    const regime = recent?.recent_regime_summary;
    if (!isObject(regime)) return '';
    return `<article class="cockpit-panel cockpit-panel-wide">
      <h3>Micro-régimen reciente</h3>
      <div class="cockpit-mini-grid">
        ${metric('Cambio 5 vs 20', regime.window_5_vs_20_shift ? 'sí' : 'no')}
        ${metric('Cambio 20 vs 30', regime.window_20_vs_30_shift ? 'sí' : 'no')}
        ${'window_30_vs_historical_shift' in regime ? metric('30 vs histórico', regime.window_30_vs_historical_shift ? 'sí' : 'no') : ''}
      </div>
      <p>${esc(regime.sum_band_shift_es || 'sin cambio')}</p>
      <p>${esc(regime.presence_shift_es || 'sin cambio')}</p>
      <p>${esc(regime.pair_companion_shift_es || 'sin cambio')}</p>
      ${regime.historical_shift_es ? `<p>${esc(regime.historical_shift_es)}</p>` : ''}
      <p class="cockpit-note">${esc(regime.interpretation_es || 'Lectura diagnóstica de micro-régimen. No implica promesa de resultado futuro.')}</p>
    </article>`;
  }

  function renderPhysicsPanel(data) {
    const notes = safeArray(data.physicsMaintenance?.notes);
    if (!notes.length) {
      return `<article class="cockpit-panel cockpit-panel-wide"><h3>Física / mantenimiento</h3><p>Sin notas de mantenimiento cargadas.</p><p class="cockpit-note">Fuente opcional read-only. No afecta constructor ni señales.</p></article>`;
    }
    return `<article class="cockpit-panel cockpit-panel-wide">
      <h3>Física / mantenimiento</h3>
      <div class="cockpit-diagnostics-grid">
        ${notes.map(note => `<article class="cockpit-panel">
          <h4>${esc(note.type || 'nota manual')}</h4>
          ${metric('Fecha', note.date || 'no disponible')}
          ${metric('Sorteo', note.draw || 'no disponible')}
          ${metric('Confianza', note.confidence || 'manual_note')}
          <p>${esc(note.description_es || 'Sin descripción.')}</p>
          <p class="cockpit-note">Nota manual. Estado: review_default. No afecta constructor ni señales.</p>
        </article>`).join('')}
      </div>
    </article>`;
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
        ${renderRecentWindowsPanel(recent)}
        ${renderRegimePanel(recent)}
        ${renderPhysicsPanel(data)}
      </div>
    </section>`;
  }

  function blockName(number) {
    const n = Number(number);
    if (n <= 10) return '1_10';
    if (n <= 20) return '11_20';
    if (n <= 30) return '21_30';
    if (n <= 40) return '31_40';
    return '41_56';
  }

  function manualSumBand(total) {
    if (total < 100) return 'low_tail';
    if (total <= 140) return 'historical_core';
    if (total <= 170) return 'upper_core';
    if (total <= 200) return 'high_tail';
    return 'extreme_high';
  }

  function manualSumBandEs(band) {
    return {
      low_tail: 'cola baja',
      historical_core: 'núcleo histórico',
      upper_core: 'núcleo alto',
      high_tail: 'cola alta',
      extreme_high: 'extremo alto',
    }[band] || band;
  }

  function manualPresence(numbers) {
    const blocks = { '1_10': 0, '11_20': 0, '21_30': 0, '31_40': 0, '41_56': 0 };
    numbers.forEach(number => { blocks[blockName(number)] += 1; });
    const values = ['1_10', '11_20', '21_30', '31_40', '41_56'].map(key => blocks[key]);
    return {
      blocks,
      block_signature: values.join('-'),
      block_presence_signature: values.map(value => value > 0 ? 1 : 0).join('-'),
    };
  }

  function manualVisualLabel(presence) {
    return {
      '0-0-1-0-1': 'Activación media-alta: presencia en 21_30 y 41_56',
      '0-1-1-0-1': 'Puente 11_20 + 21_30 + 41_56',
      '0-1-0-0-1': 'Puente bajo-medio con bloque alto',
      '1-0-1-0-1': 'Triángulo 1_10 + 21_30 + 41_56',
      '1-1-1-0-0': 'Escalera baja-media hasta 21_30',
      '0-1-1-1-0': 'Centro extendido 11_20 + 21_30 + 31_40',
    }[presence] || `Presencia visual ${presence}`;
  }

  function signalsForNumber(number, data) {
    const signals = [];
    const n = Number(number);
    const gapRow = data.gapEcho?.numbers?.[String(n)];
    if (gapRow?.in_active_window || safeArray(data.gapEcho?.active_candidates).includes(n)) signals.push('gap_echo');
    if (data.signatureHistory?.numbers_after?.[String(n)]) signals.push('signature_history');
    if (safeArray(data.pairLag?.active_candidates).includes(n)) signals.push('pair_lag_candidate');
    safeArray(data.pairLag?.signals).slice(0, 500).forEach(row => {
      if (Number(row.trigger) === n) signals.push('pair_lag_trigger');
      if (Number(row.candidate) === n) signals.push('pair_lag_candidate');
    });
    safeArray(data.blockCompletion?.groups).forEach(row => {
      if (safeArray(row.missing).map(Number).includes(n)) signals.push('block_completion');
      if (safeArray(row.recent_seen).map(Number).includes(n)) signals.push('structure_completion');
    });
    safeArray(data.recentComposition?.top_recent_numbers).forEach(row => {
      if (Number(row.number) === n) signals.push('recent_frequency');
    });
    return unique(signals);
  }

  function evaluateManualNumbers(numbers, data) {
    const total = numbers.reduce((sum, number) => sum + number, 0);
    const band = manualSumBand(total);
    const even = numbers.filter(number => number % 2 === 0).length;
    const parity = `${even}_even_${6 - even}_odd`;
    const structure = manualPresence(numbers);
    const latestNumbers = safeArray(data.recentComposition?.latest_draw_numbers).map(Number).filter(Number.isFinite);
    const immediateOverlap = latestNumbers.length ? numbers.filter(number => latestNumbers.includes(number)).length : null;
    const numberSignals = Object.fromEntries(numbers.map(number => [String(number), signalsForNumber(number, data)]));
    const pairKeys = new Set();
    safeArray(data.recentComposition?.pair_companion_profile?.pair_companion_candidates).forEach(row => {
      const pair = safeArray(row.pair).map(Number).sort((a, b) => a - b);
      if (pair.length === 2) pairKeys.add(pair.join('-'));
    });
    const pairs = [];
    for (let i = 0; i < numbers.length; i += 1) {
      for (let j = i + 1; j < numbers.length; j += 1) {
        pairs.push([numbers[i], numbers[j]].sort((a, b) => a - b).join('-'));
      }
    }
    const pairCompanionCount = pairs.filter(pair => pairKeys.has(pair)).length;
    const numberSet = new Set(numbers);
    const pairLagCount = safeArray(data.pairLag?.signals).filter(row => numberSet.has(Number(row.trigger)) && numberSet.has(Number(row.candidate))).length;
    const recent30 = recentWindows(data.recentComposition)?.['30'] || data.recentComposition || {};
    const matchesRecent = Boolean(
      recent30.sum_profile?.sum_band_distribution?.[band]
      || recent30.presence_signature_profile?.presence_signature_distribution?.[structure.block_presence_signature]
    );
    const winner = data.winnerProfile || {};
    const matchesWinner = Boolean(
      winner.sum_profile?.sum_band_distribution?.[band]
      || winner.presence_signature_profile?.presence_signature_distribution?.[structure.block_presence_signature]
    );
    const windowNotes = ['5', '20', '30'].map(key => {
      const window = recentWindows(data.recentComposition)?.[key];
      if (!window) return `Ventana ${key}: no disponible.`;
      const aligned = window.sum_profile?.dominant_sum_band === band || window.presence_signature_profile?.dominant_presence_signature === structure.block_presence_signature;
      return aligned ? `Esta combinación coincide con perfil ventana ${key}.` : `Esta combinación se aleja del perfil de últimos ${key}.`;
    });
    return {
      total,
      band,
      parity,
      structure,
      numberSignals,
      pairCompanionCount,
      pairLagCount,
      matchesRecent,
      matchesWinner,
      immediateOverlap,
      windowNotes,
    };
  }

  function renderManualEvaluator() {
    return `<details id="manual-evaluator-v44" class="cockpit-zone cockpit-secondary-details">
      <summary><span><b>Evaluador manual V4.4</b><small>Read-only, revisión interna desde JSONs cargados</small></span></summary>
      <div id="manual-evaluator-v44-panel">
        <label class="cockpit-manual-label" for="manual-v44-numbers">Escribe 6 números separados por espacios o comas</label>
        <div class="cockpit-manual-row">
          <input id="manual-v44-numbers" class="cockpit-manual-input" type="text" inputmode="numeric" placeholder="7 15 23 27 41 49" />
          <button id="manual-v44-evaluate" class="cockpit-copy" type="button">Evaluar</button>
        </div>
        <p class="cockpit-note">Estado: review_default. Este diagnóstico es revisión interna.</p>
        <div id="manual-v44-result" class="cockpit-panel cockpit-panel-wide">Ingresa una combinación para revisar señales, suma, paridad, firmas y ventanas recientes.</div>
      </div>
    </details>`;
  }

  function wireManualEvaluator(root, data) {
    const button = root.querySelector('#manual-v44-evaluate');
    const input = root.querySelector('#manual-v44-numbers');
    const output = root.querySelector('#manual-v44-result');
    if (!button || !input || !output) return;
    button.addEventListener('click', () => {
      const numbers = unique(String(input.value || '').split(/[\s,;]+/).map(value => Number(value)).filter(Number.isFinite)).map(Number).sort((a, b) => a - b);
      if (numbers.length !== 6 || numbers.some(number => !Number.isInteger(number) || number < 1 || number > 56)) {
        output.innerHTML = '<p>Ingresa exactamente 6 números enteros únicos entre 1 y 56.</p><p class="cockpit-note">Estado: review_default. Este diagnóstico es revisión interna.</p>';
        return;
      }
      const result = evaluateManualNumbers(numbers, data);
      output.innerHTML = `<h3>Diagnóstico manual V4.4</h3>
        ${numberBalls(numbers)}
        <div class="cockpit-mini-grid">
          ${metric('Suma', result.total, 'mono')}
          ${metric('Banda', `${manualSumBandEs(result.band)} (${result.band})`)}
          ${metric('Paridad', result.parity)}
          ${metric('Firma de bloques', result.structure.block_signature, 'mono')}
          ${metric('Presencia visual', result.structure.block_presence_signature, 'mono')}
          ${metric('Lectura visual', manualVisualLabel(result.structure.block_presence_signature))}
          ${metric('Pair companion', result.pairCompanionCount, 'mono')}
          ${metric('Pair-lag', result.pairLagCount, 'mono')}
          ${metric('Repetidos inmediatos', result.immediateOverlap === null ? 'no disponible' : result.immediateOverlap, 'mono')}
          ${metric('Perfil ventana 30', result.matchesRecent ? 'alineado' : 'revisar')}
          ${metric('Perfil histórico', result.matchesWinner ? 'alineado' : 'revisar')}
        </div>
        <h4>Señales por número</h4>
        <div class="cockpit-diagnostics-grid">${numbers.map(number => `<article class="cockpit-panel"><h5>${esc(number)}</h5><div class="cockpit-role-pills">${signalChips(result.numberSignals[String(number)]) || '<span class="cockpit-pill">sin señal cargada</span>'}</div></article>`).join('')}</div>
        <h4>Lectura por ventanas</h4>
        <ul>${result.windowNotes.map(note => `<li>${esc(note)}</li>`).join('')}</ul>
        <p class="cockpit-note">Relaciones internas detectadas: ${esc(result.pairCompanionCount + result.pairLagCount)}. Estado: review_default. Este diagnóstico es revisión interna.</p>`;
    });
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
      renderDecisionDay(data),
      renderSlate(data),
      renderDiagnostics(data),
      renderManualEvaluator(data),
      renderAudit(data),
      renderSystemDiagnostics(),
      '<footer class="cockpit-footer">Este sistema es experimental. Los scores y composiciones son métricas de auditoría interna, no promesas de resultado. production_status: review_default.</footer>',
    ].join('');
    wireCopyButtons(root);
    wireManualEvaluator(root, data);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', render);
  } else {
    render();
  }
})();
