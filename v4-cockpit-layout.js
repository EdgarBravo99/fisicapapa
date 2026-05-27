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
    videoWeightObservations: 'v4_ball_weight_observations.json',
  };

  const CRITICAL_SOURCE_KEYS = ['slate', 'gapEcho', 'signatureHistory', 'pairLag', 'blockCompletion', 'winnerProfile', 'recentComposition'];
  const OPTIONAL_SOURCE_KEYS = ['postDraw', 'matrix', 'pair', 'slateLegacy', 'physicsMaintenance', 'videoWeightObservations'];
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
      videoWeightObservations: 'py tools\\video_weight_lab\\run_video_weight_lab.py --draw <draw> --channel-url https://www.youtube.com/@LN_electronicos/streams --download true --fps-sample 1',
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
    if (lowCount) practicalAlerts.push(`${lowCount} boleto(s) quedan en prioridad baja por soporte limitado o desalineación.`);
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
    const observations = safeArray(data.videoWeightObservations?.observations);
    const weightPanel = observations.length
      ? `<article class="cockpit-panel cockpit-panel-wide">
          <h3>Pesaje visual observado</h3>
          <p class="cockpit-note">Observación visual review_default. No afecta constructor, scores ni señales.</p>
          <div class="cockpit-diagnostics-grid">
            ${observations.slice(0, 12).map(item => `<article class="cockpit-panel">
              <h4>${esc(item.event_id || 'observación')}</h4>
              ${metric('Sorteo', data.videoWeightObservations?.draw || item.draw || 'no disponible')}
              ${metric('Bola', item.ball ?? 'revisión manual', 'mono')}
              ${metric('Peso g', item.weight_g ?? 'revisión manual', 'mono')}
              ${metric('Escena', item.scene_type || 'no disponible')}
              ${metric('Confianza', item.confidence || 'low')}
              ${metric('Review status', item.review_status || 'pending')}
              ${metric('Revisión manual', item.needs_manual_review ? 'sí' : 'no')}
              ${item.scale_display_crop_path ? `<p><a href="${esc(item.scale_display_crop_path)}">Crop display</a></p>` : ''}
              ${item.ball_crop_path ? `<p><a href="${esc(item.ball_crop_path)}">Crop bola</a></p>` : ''}
            </article>`).join('')}
          </div>
        </article>`
      : `<article class="cockpit-panel cockpit-panel-wide"><h3>Pesaje visual observado</h3><p>Sin observaciones de pesaje visual cargadas.</p><p class="cockpit-note">Observación opcional. No afecta constructor, scores ni señales.</p></article>`;
    if (!notes.length) {
      return `<article class="cockpit-panel cockpit-panel-wide"><h3>Física / mantenimiento</h3><p>Sin notas de mantenimiento cargadas.</p><p class="cockpit-note">Fuente opcional read-only. No afecta constructor ni señales.</p></article>${weightPanel}`;
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
    </article>${weightPanel}`;
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
      numbers,
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

  function buildManualTicket(numbers, manualEvaluation) {
    const result = manualEvaluation || {};
    return {
      numbers: safeArray(numbers).map(Number),
      ticket_type: 'manual_review',
      production_status: 'review_default',
      composition: {
        sum: result.total,
        sum_band: result.band,
        sum_band_es: manualSumBandEs(result.band),
        parity: result.parity,
        block_signature: result.structure?.block_signature,
        block_presence_signature: result.structure?.block_presence_signature,
        visual_structure_label_es: manualVisualLabel(result.structure?.block_presence_signature),
        immediate_overlap_previous_draw: result.immediateOverlap ?? 0,
        pair_companion_count: result.pairCompanionCount || 0,
        pair_lag_relation_count: result.pairLagCount || 0,
        matches_recent_profile: result.matchesRecent === true,
        matches_winner_profile: result.matchesWinner === true,
      },
      signals: result.numberSignals || {},
    };
  }

  function pairKey(pair) {
    const values = safeArray(pair).map(Number).filter(Number.isFinite).sort((a, b) => a - b);
    return values.length === 2 ? values.join('-') : '';
  }

  function internalPairs(numbers) {
    const pairs = [];
    for (let i = 0; i < numbers.length; i += 1) {
      for (let j = i + 1; j < numbers.length; j += 1) {
        pairs.push([numbers[i], numbers[j]].sort((a, b) => a - b));
      }
    }
    return pairs;
  }

  function collectCompanionRows(data) {
    const recent = data.recentComposition || {};
    const pairAudit = data.pair || {};
    return [
      ...safeArray(recent.pair_companion_profile?.pair_companion_candidates),
      ...safeArray(recent.pair_companion_profile?.top_pair_companions),
      ...safeArray(pairAudit.top_co_travel_pairs),
      ...safeArray(pairAudit.top_block_bridge_pairs),
    ];
  }

  function manualPairRelations(numbers, data) {
    const companionByKey = new Map();
    collectCompanionRows(data).forEach(row => {
      const key = pairKey(row.pair || row.numbers || [row.a, row.b]);
      if (key && !companionByKey.has(key)) companionByKey.set(key, row);
    });

    const lagByKey = new Map();
    safeArray(data.pairLag?.signals).forEach(row => {
      const trigger = Number(row.trigger);
      const candidate = Number(row.candidate);
      if (Number.isFinite(trigger) && Number.isFinite(candidate)) lagByKey.set(`${trigger}-${candidate}`, row);
    });

    const pairLagActive = new Set(safeArray(data.pairLag?.active_candidates).map(Number));
    const pairCompanionMatches = [];
    const pairLagMatches = [];
    const neutralPairs = [];

    internalPairs(numbers).forEach(pair => {
      const sortedKey = pairKey(pair);
      const forward = `${pair[0]}-${pair[1]}`;
      const reverse = `${pair[1]}-${pair[0]}`;
      const companion = companionByKey.get(sortedKey);
      const lag = lagByKey.get(forward) || lagByKey.get(reverse);
      if (companion) {
        pairCompanionMatches.push({
          pair,
          relation_type: 'pair_companion',
          explanation_es: `Par ${pair.join('-')} aparece como relacion interna companion en perfiles cargados.`,
        });
      }
      if (lag) {
        pairLagMatches.push({
          pair,
          relation_type: 'pair_lag',
          explanation_es: `Par ${Number(lag.trigger)} -> ${Number(lag.candidate)} aparece como relacion temporal pair-lag.`,
        });
      }
      if (!companion && !lag) {
        const active = pair.filter(number => pairLagActive.has(number));
        neutralPairs.push({
          pair,
          relation_type: active.length ? 'neutral_con_alerta_pair_lag' : 'neutral',
          explanation_es: active.length
            ? `Sin relacion interna directa; ${active.join(', ')} aparece como candidato activo pair-lag.`
            : 'Sin relacion interna cargada en las fuentes disponibles.',
        });
      }
    });

    return {
      pair_companion_matches: pairCompanionMatches,
      pair_lag_matches: pairLagMatches,
      neutral_pairs: neutralPairs,
    };
  }

  function renderManualPairRelations(relations) {
    const companion = safeArray(relations?.pair_companion_matches);
    const lag = safeArray(relations?.pair_lag_matches);
    const neutral = safeArray(relations?.neutral_pairs);
    const relationRows = [
      ...companion.map(item => ({ ...item, label: 'Pair companion' })),
      ...lag.map(item => ({ ...item, label: 'Pair-lag' })),
    ];
    return `<section class="cockpit-ticket-why">
      <h4>Relacion de pares</h4>
      ${relationRows.length
        ? `<ul>${relationRows.map(item => `<li><b>${esc(item.pair.join('-'))}</b> - ${esc(item.label)}. ${esc(item.explanation_es)}</li>`).join('')}</ul>`
        : '<p>No se detectaron relaciones internas de pares en las fuentes cargadas.</p>'}
      <p class="cockpit-note">Pares neutrales: ${esc(neutral.length)} de 15. Lectura review_default; no modifica constructor, scores ni priors.</p>
    </section>`;
  }

  function windowAlignmentLabel(ticket, data, key) {
    const windows = recentWindows(data.recentComposition);
    if (!windows?.[String(key)]) return 'no disponible';
    return matchesRecentWindow(ticket, data.recentComposition, key) ? 'alineado' : 'requiere revision';
  }

  function renderManualSumThesis(result, data) {
    const ticket = buildManualTicket(result.numbers || [], result);
    const hasPairSupport = Number(result.pairCompanionCount || 0) + Number(result.pairLagCount || 0) > 0;
    const structureCount = Object.values(result.numberSignals || {}).filter(items => safeArray(items).some(signal => ['structure_completion', 'block_completion', 'zone_fit'].includes(signal))).length;
    const warnings = [];
    if ((result.band === 'extreme_high' || result.band === 'low_tail') && !hasPairSupport && structureCount < 3) {
      warnings.push('Banda de suma en cola sin soporte suficiente de pares o estructura; no usar como unica tesis.');
    }
    if (!matchesRecentWindow(ticket, data.recentComposition, '5') && (matchesRecentWindow(ticket, data.recentComposition, '20') || matchesRecentWindow(ticket, data.recentComposition, '30'))) {
      warnings.push('Se aleja de ventana corta, pero conserva lectura en ventanas mayores.');
    }
    if (!warnings.length) warnings.push('La suma queda como tesis de revision junto con pares, forma visual y ventanas recientes.');
    return `<section class="cockpit-ticket-why">
      <h4>Suma y tesis</h4>
      <div class="cockpit-mini-grid">
        ${metric('Suma total', result.total, 'mono')}
        ${metric('Banda', `${manualSumBandEs(result.band)} (${result.band})`)}
        ${metric('Ventana 5', windowAlignmentLabel(ticket, data, '5'))}
        ${metric('Ventana 20', windowAlignmentLabel(ticket, data, '20'))}
        ${metric('Ventana 30', windowAlignmentLabel(ticket, data, '30'))}
        ${metric('Perfil historico', result.matchesWinner ? 'alineado' : 'requiere revision')}
      </div>
      <ul>${warnings.map(item => `<li>${esc(item)}</li>`).join('')}</ul>
    </section>`;
  }

  function renderManualStructureCompletion(numbers, result, data) {
    const groups = safeArray(data.blockCompletion?.groups);
    const closing = new Set();
    const recentSeen = new Set();
    groups.forEach(group => {
      const missing = new Set(safeArray(group.missing).map(Number));
      const seen = new Set(safeArray(group.recent_seen).map(Number));
      numbers.forEach(number => {
        if (missing.has(number)) closing.add(number);
        if (seen.has(number)) recentSeen.add(number);
      });
    });
    const blocks = result.structure?.blocks || {};
    return `<section class="cockpit-ticket-why">
      <h4>Completar forma / estructura</h4>
      <div class="cockpit-mini-grid">
        ${Object.entries(blocks).map(([block, count]) => metric(block, count, 'mono')).join('')}
        ${metric('Firma de bloques', result.structure?.block_signature || 'no disponible', 'mono')}
        ${metric('Presencia visual', result.structure?.block_presence_signature || 'no disponible', 'mono')}
      </div>
      <p>${esc(manualVisualLabel(result.structure?.block_presence_signature))}. Esta forma se revisa contra cierres de bloque y perfiles cargados.</p>
      <ul>
        <li>Numeros como cierre de bloque: ${esc([...closing].sort((a, b) => a - b).join(', ') || 'no disponible')}</li>
        <li>Numeros ya vistos en grupos activos: ${esc([...recentSeen].sort((a, b) => a - b).join(', ') || 'no disponible')}</li>
        <li>Grupos de block completion cargados: ${esc(groups.length || 'no disponible')}</li>
      </ul>
    </section>`;
  }

  function addManualCandidate(pool, numbersSet, value, tag) {
    const number = Number(value);
    if (!Number.isInteger(number) || number < 1 || number > 56 || numbersSet.has(number)) return;
    if (!pool.has(number)) pool.set(number, new Set());
    pool.get(number).add(tag);
  }

  function topNumberValue(row) {
    if (Number.isInteger(Number(row))) return Number(row);
    return Number(row?.number ?? row?.ball ?? row?.candidate);
  }

  function diagnosticoIntegrado(numbers, result, data) {
    const problemas = [];
    const sumaCola = result.band === 'extreme_high' || result.band === 'low_tail';
    const sinPares = (Number(result.pairCompanionCount || 0) + Number(result.pairLagCount || 0)) === 0;
    const repetidosAltos = Number(result.immediateOverlap || 0) >= 2;
    const desalineadoTotal = result.matchesRecent === false && result.matchesWinner === false;
    const formaDebil = manualStructureSignalCount(result) < 2;

    if (sumaCola) problemas.push('suma_cola');
    if (sinPares) problemas.push('sin_pares');
    if (repetidosAltos) problemas.push('repetidos_altos');
    if (desalineadoTotal) problemas.push('desalineado_total');
    if (formaDebil) problemas.push('forma_debil');

    if (sumaCola && sinPares) {
      return {
        problemas,
        diagnostico_es: 'La combinación combina suma en cola con falta de pares internos; conviene revisar primero un cambio que aporte relación interna y mueva la suma a una banda más revisable.',
        punto_de_entrada_es: 'Buscar swap que aporte par interno y mueva la suma fuera de cola.',
      };
    }
    if (desalineadoTotal && formaDebil) {
      return {
        problemas,
        diagnostico_es: 'La combinación no queda alineada con ventana reciente ni perfil histórico cargado, y además tiene poca estructura visible; requiere revisar si funciona como cobertura contraria o si conviene reemplazarla.',
        punto_de_entrada_es: 'Revisar si tiene sentido como cobertura contraria o reemplazar la combinación.',
      };
    }
    if (repetidosAltos && sinPares) {
      return {
        problemas,
        diagnostico_es: 'La combinación carga repetidos inmediatos sin una relación interna que los sostenga; conviene revisar el número repetido con menor soporte.',
        punto_de_entrada_es: 'Reducir repetidos inmediatos o agregar relación interna clara.',
      };
    }
    if (problemas.length === 1) {
      return {
        problemas,
        diagnostico_es: 'La combinación tiene una alerta principal de revisión.',
        punto_de_entrada_es: 'Un ajuste puntual puede resolver la combinación. Ver swap sugerido.',
      };
    }
    if (!problemas.length) {
      return {
        problemas,
        diagnostico_es: 'Sin alertas críticas.',
        punto_de_entrada_es: 'Revisión de ajuste fino.',
      };
    }
    return {
      problemas,
      diagnostico_es: 'La combinación acumula alertas que conviene revisar juntas.',
      punto_de_entrada_es: 'Priorizar swaps que atiendan pares, suma y forma al mismo tiempo.',
    };
  }

  function manualCandidatePool(numbers, data) {
    const numbersSet = new Set(safeArray(numbers).map(Number));
    const pool = new Map();
    const companionKeys = new Set();
    const lagKeys = new Set();

    collectCompanionRows(data).forEach(row => {
      const key = pairKey(row.pair || row.numbers || [row.a, row.b]);
      if (key) companionKeys.add(key);
    });
    safeArray(data.pairLag?.signals).forEach(row => {
      const trigger = Number(row.trigger);
      const candidate = Number(row.candidate);
      if (Number.isFinite(trigger) && Number.isFinite(candidate)) lagKeys.add(`${trigger}-${candidate}`);
    });

    safeArray(data.gapEcho?.active_candidates).forEach(number => addManualCandidate(pool, numbersSet, number, 'gap_echo'));
    Object.keys(data.signatureHistory?.numbers_after || {}).forEach(number => addManualCandidate(pool, numbersSet, number, 'signature_history'));
    safeArray(data.pairLag?.active_candidates).forEach(number => addManualCandidate(pool, numbersSet, number, 'pair_lag_candidate'));
    safeArray(data.pairLag?.signals).forEach(row => {
      addManualCandidate(pool, numbersSet, row.candidate, 'pair_lag_candidate');
      addManualCandidate(pool, numbersSet, row.trigger, 'pair_lag_trigger');
    });
    safeArray(data.blockCompletion?.groups).forEach(group => {
      safeArray(group.missing).forEach(number => addManualCandidate(pool, numbersSet, number, 'block_completion'));
      safeArray(group.recent_seen).forEach(number => addManualCandidate(pool, numbersSet, number, 'structure_completion'));
    });
    safeArray(data.recentComposition?.top_recent_numbers).forEach(row => addManualCandidate(pool, numbersSet, topNumberValue(row), 'recent_frequency'));
    Object.values(recentWindows(data.recentComposition) || {}).forEach(window => {
      if (isObject(window)) safeArray(window.top_recent_numbers).forEach(row => addManualCandidate(pool, numbersSet, topNumberValue(row), 'recent_frequency'));
    });
    collectCompanionRows(data).forEach(row => {
      const pair = safeArray(row.pair || row.numbers || [row.a, row.b]).map(Number).filter(Number.isFinite);
      if (pair.length !== 2) return;
      const [first, second] = pair;
      if (numbersSet.has(first) && !numbersSet.has(second)) addManualCandidate(pool, numbersSet, second, 'pair_companion_bridge');
      if (numbersSet.has(second) && !numbersSet.has(first)) addManualCandidate(pool, numbersSet, first, 'pair_companion_bridge');
    });

    const compatibilityByNumber = new Map();
    const compatibilityFor = candidate => {
      let compatibility = 0;
      numbers.forEach(number => {
        const sorted = pairKey([number, candidate]);
        if (companionKeys.has(sorted)) compatibility += 1;
        if (lagKeys.has(`${number}-${candidate}`) || lagKeys.has(`${candidate}-${number}`)) compatibility += 1;
      });
      const candidateBlock = blockName(candidate);
      const blockNumbers = [...numbers, candidate].filter(number => blockName(number) === candidateBlock);
      const hasBlockSupport = blockNumbers.some(number => {
        const tags = signalsForNumber(number, data);
        return tags.includes('block_completion') || tags.includes('structure_completion');
      });
      const expandedResult = evaluateManualNumbers([...numbers, candidate], data);
      const expandedPairCount = Number(expandedResult.pairCompanionCount || 0) + Number(expandedResult.pairLagCount || 0);
      if (blockNumbers.length >= 3 && !hasBlockSupport && expandedPairCount === 0) compatibility -= 1;
      return compatibility;
    };

    return [...pool.entries()]
      .map(([number, tags]) => {
        compatibilityByNumber.set(number, compatibilityFor(number));
        return { number, tags: [...tags].sort() };
      })
      .sort((a, b) => (compatibilityByNumber.get(b.number) || 0) - (compatibilityByNumber.get(a.number) || 0) || b.tags.length - a.tags.length || a.number - b.number);
  }

  function manualSignalCount(result) {
    return Object.values(result.numberSignals || {}).reduce((total, signals) => total + safeArray(signals).length, 0);
  }

  function manualStructureSignalCount(result) {
    return Object.values(result.numberSignals || {}).filter(signals => safeArray(signals).some(signal => ['structure_completion', 'block_completion', 'zone_fit'].includes(signal))).length;
  }

  function manualSwapSummary(result) {
    return {
      pair_count: Number(result.pairCompanionCount || 0) + Number(result.pairLagCount || 0),
      pair_companion_count: Number(result.pairCompanionCount || 0),
      pair_lag_count: Number(result.pairLagCount || 0),
      matches_recent: result.matchesRecent === true,
      matches_winner: result.matchesWinner === true,
      immediate_overlap: result.immediateOverlap ?? 0,
      sum_band: result.band,
      block_presence_signature: result.structure?.block_presence_signature,
      signal_count: manualSignalCount(result),
      structure_signal_count: manualStructureSignalCount(result),
    };
  }

  function evaluateManualSwap(numbers, removeNumber, addNumber, data) {
    function tesisSwap(swap, contexto) {
      const partes = [];
      if (swap.new_summary.pair_lag_count > swap.old_summary.pair_lag_count) partes.push('agrega relación pair-lag');
      else if (swap.new_summary.pair_companion_count > swap.old_summary.pair_companion_count) partes.push('agrega relación companion');
      else if (swap.new_summary.pair_count > swap.old_summary.pair_count) partes.push('agrega relación interna');
      if (['extreme_high', 'low_tail'].includes(swap.old_summary.sum_band) && !['extreme_high', 'low_tail'].includes(swap.new_summary.sum_band)) partes.push('reduce cola de suma');
      if (swap.new_summary.structure_signal_count > swap.old_summary.structure_signal_count) partes.push('aporta lectura de forma');
      if (contexto.diversidad_banda) partes.push('aporta diversidad de banda frente al slate cargado');
      if (contexto.diversidad_forma) partes.push('aporta diversidad de forma frente al slate cargado');
      if (contexto.concentracion_banda) partes.push('requiere revisar concentración de banda');
      return `Este cambio ${partes.length ? partes.join(' y ') : 'es exploratorio con señales cargadas'}, pero requiere revisar la forma resultante.`;
    }

    const oldResult = evaluateManualNumbers(numbers, data);
    const newNumbers = numbers.filter(number => number !== removeNumber).concat([addNumber]).sort((a, b) => a - b);
    const newResult = evaluateManualNumbers(newNumbers, data);
    const newTicket = buildManualTicket(newNumbers, newResult);
    const pairRelations = manualPairRelations(newNumbers, data);
    const oldSummary = manualSwapSummary(oldResult);
    const newSummary = manualSwapSummary(newResult);
    const poolRow = manualCandidatePool(numbers, data).find(row => row.number === addNumber);
    const reasonTags = poolRow?.tags || [];
    const improvements = [];
    const tradeoffs = [];
    const contexto = {};
    let score = 0;

    if (newSummary.pair_count > oldSummary.pair_count) {
      score += (newSummary.pair_count - oldSummary.pair_count) * 3;
      improvements.push('Refuerza lectura de pares internos.');
    }
    if (newSummary.signal_count > oldSummary.signal_count) {
      score += newSummary.signal_count - oldSummary.signal_count;
      improvements.push('Reduce numero huerfano y suma mas señales cargadas.');
    }
    if (newSummary.structure_signal_count > oldSummary.structure_signal_count) {
      score += (newSummary.structure_signal_count - oldSummary.structure_signal_count) * 2;
      improvements.push('Aporta cierre de forma o estructura.');
    }
    if (!oldSummary.matches_recent && newSummary.matches_recent) {
      score += 2;
      improvements.push('Conserva lectura de ventana reciente cargada.');
    }
    if (!oldSummary.matches_winner && newSummary.matches_winner) {
      score += 1.5;
      improvements.push('Se alinea con perfil historico cargado.');
    }
    if (['extreme_high', 'low_tail'].includes(oldSummary.sum_band) && !['extreme_high', 'low_tail'].includes(newSummary.sum_band)) {
      score += 1.5;
      improvements.push('Mueve la suma hacia una banda mas revisable.');
    }
    if (Number(newSummary.immediate_overlap) < Number(oldSummary.immediate_overlap)) {
      score += 1;
      improvements.push('Reduce repetidos inmediatos.');
    }

    const slateTickets = safeArray(data.slate?.tickets);
    if (slateTickets.length) {
      const slateBands = slateTickets.map(ticket => ticket?.composition?.sum_band).filter(Boolean);
      const slatePresence = slateTickets.map(ticket => ticket?.composition?.block_presence_signature).filter(Boolean);
      if (!slateBands.includes(newSummary.sum_band)) {
        score += 1;
        contexto.diversidad_banda = true;
      }
      if (!slatePresence.includes(newSummary.block_presence_signature)) {
        score += 1;
        contexto.diversidad_forma = true;
      }
      if (slateBands.filter(band => band === newSummary.sum_band).length >= 3) {
        score -= 1;
        contexto.concentracion_banda = true;
      }
    } else {
      contexto.slate_disponible = false;
    }

    if (newSummary.pair_count < oldSummary.pair_count) tradeoffs.push('Pierde una relacion interna de pares; revisar si la forma lo compensa.');
    if (newSummary.sum_band !== oldSummary.sum_band) tradeoffs.push(`Cambia banda de suma de ${oldSummary.sum_band} a ${newSummary.sum_band}.`);
    if (Number(newSummary.immediate_overlap) > Number(oldSummary.immediate_overlap)) tradeoffs.push('Aumenta repetidos inmediatos; requiere revision manual.');
    if (!newSummary.matches_recent && !newSummary.matches_winner) tradeoffs.push('No queda alineado con ventana 30 ni perfil historico cargado.');
    if (!tradeoffs.length) tradeoffs.push('Ajuste fino sin sacrificio fuerte visible en las fuentes cargadas.');
    if (!improvements.length) improvements.push('Cambio exploratorio; revisar manualmente antes de priorizarlo.');

    const swap = {
      remove: removeNumber,
      add: addNumber,
      new_numbers: newNumbers,
      old_summary: oldSummary,
      new_summary: newSummary,
      improvements_es: improvements,
      tradeoffs_es: tradeoffs,
      reason_tags: reasonTags,
      tesis_es: '',
      score,
      pair_relations: pairRelations,
      ticket: newTicket,
    };
    swap.tesis_es = tesisSwap(swap, contexto);
    return swap;
  }

  function manualEfficiencySuggestions(numbers, result, data) {
    const diagnostico = diagnosticoIntegrado(numbers, result, data);
    const pool = manualCandidatePool(numbers, data);
    const pairRelations = manualPairRelations(numbers, data);
    const pairNumbers = new Set([
      ...safeArray(pairRelations.pair_companion_matches).flatMap(item => item.pair),
      ...safeArray(pairRelations.pair_lag_matches).flatMap(item => item.pair),
    ].map(Number));
    const latestNumbers = new Set(safeArray(data.recentComposition?.latest_draw_numbers).map(Number));
    const supportRows = numbers.map(number => {
      const tags = safeArray(result.numberSignals?.[String(number)]);
      const pairSupported = pairNumbers.has(number);
      const structureSupported = tags.some(tag => ['block_completion', 'structure_completion', 'zone_fit'].includes(tag));
      const recentSupported = tags.includes('recent_frequency');
      const repeatedWithoutSupport = latestNumbers.has(number) && !pairSupported && tags.length < 2;
      const supportScore = tags.length + (pairSupported ? 2 : 0) + (structureSupported ? 2 : 0) + (recentSupported ? 1 : 0) - (repeatedWithoutSupport ? 1 : 0);
      return { number, tags, pairSupported, structureSupported, recentSupported, repeatedWithoutSupport, supportScore };
    });
    const keepNumbers = supportRows
      .filter(row => row.supportScore >= 3)
      .sort((a, b) => b.supportScore - a.supportScore || a.number - b.number)
      .map(row => ({
        number: row.number,
        reason_es: `${row.number}: conservar por ${row.pairSupported ? 'relacion de pares, ' : ''}${row.structureSupported ? 'cierre estructural, ' : ''}${row.tags.length} señal(es) cargada(s).`.replace(/, $/, '.'),
      }));
    let reviewRows = supportRows
      .filter(row => row.tags.length === 0 || row.supportScore <= 1 || row.repeatedWithoutSupport)
      .sort((a, b) => a.supportScore - b.supportScore || a.number - b.number);
    if (!reviewRows.length) reviewRows = supportRows.slice().sort((a, b) => a.supportScore - b.supportScore || a.number - b.number).slice(0, 2);
    const reviewNumbers = reviewRows.map(row => ({
      number: row.number,
      reason_es: row.tags.length
        ? `${row.number}: revisar porque aporta soporte limitado frente al resto de la combinacion.`
        : `${row.number}: no tiene señales cargadas en las fuentes actuales.`,
    }));
    const candidateRows = pool.slice(0, 12);
    const swaps = [];
    reviewRows.forEach(row => {
      candidateRows.forEach(candidate => {
        swaps.push(evaluateManualSwap(numbers, row.number, candidate.number, data));
      });
    });
    const swapSuggestions = swaps
      .filter(swap => swap.score > 0)
      .sort((a, b) => b.score - a.score || a.remove - b.remove || a.add - b.add)
      .slice(0, 5);
    const candidatePreview = pool.slice(0, 6);
    const hasStrongSupport = keepNumbers.length >= 4 && (result.pairCompanionCount + result.pairLagCount) > 0 && (result.matchesRecent || result.matchesWinner);
    const pairSuggestions = [];
    if ((result.pairCompanionCount + result.pairLagCount) === 0) {
      const pairCandidates = candidatePreview.filter(row => row.tags.includes('pair_companion_bridge') || row.tags.includes('pair_lag_candidate') || row.tags.includes('pair_lag_trigger'));
      pairSuggestions.push(pairCandidates.length
        ? `Revisar candidatos ${pairCandidates.map(row => row.number).join(', ')} para formar o reforzar relacion de pares.`
        : 'No hay pares internos detectados; revisar si la forma visual compensa esa falta.');
    } else {
      pairSuggestions.push('Conservar al menos una relacion interna de pares al probar cambios.');
    }
    const sumSuggestions = [];
    if (['extreme_high', 'low_tail'].includes(result.band)) {
      sumSuggestions.push(`La banda ${result.band} requiere revision; prioriza swaps que mantengan pares o estructura mientras mueven la suma.`);
    } else {
      sumSuggestions.push('La suma queda en banda revisable; no hace falta ajustar solo por suma.');
    }
    const structureSuggestions = [];
    const structureCandidates = candidatePreview.filter(row => row.tags.includes('block_completion') || row.tags.includes('structure_completion'));
    structureSuggestions.push(structureCandidates.length
      ? `Candidatos de cierre/forma para revisar: ${structureCandidates.map(row => row.number).join(', ')}.`
      : 'No hay candidatos claros de cierre de forma con las fuentes cargadas.');

    return {
      diagnostico_integrado: diagnostico,
      has_candidate_pool: pool.length > 0,
      candidate_numbers: candidatePreview,
      keep_numbers: keepNumbers,
      review_numbers: reviewNumbers,
      swap_suggestions: swapSuggestions,
      pair_suggestions: pairSuggestions,
      sum_suggestions: sumSuggestions,
      structure_suggestions: structureSuggestions,
      well_supported_message: hasStrongSupport ? 'La combinacion ya tiene soporte estructural suficiente; las sugerencias son ajustes finos, no cambios obligatorios.' : '',
    };
  }

  function renderManualEfficiencySuggestions(suggestions) {
    const diagnostico = suggestions?.diagnostico_integrado || {};
    const diagnosticoHtml = safeArray(diagnostico.problemas).length
      ? `<p>${esc(diagnostico.diagnostico_es || 'Revisión manual requerida.')}</p><p class="cockpit-note">${esc(diagnostico.punto_de_entrada_es || 'Revisar ajuste puntual.')}</p>`
      : `<p class="cockpit-note">${esc(diagnostico.punto_de_entrada_es || 'Revisión de ajuste fino.')}</p>`;
    if (!suggestions?.has_candidate_pool) {
      return `<section class="cockpit-ticket-why">
        <h4>Sugerencias para hacer mas eficiente la combinacion</h4>
        ${diagnosticoHtml}
        <p>No hay suficientes fuentes cargadas para sugerir cambios. Ejecuta el pipeline V4.4 y vuelve a cargar el cockpit.</p>
      </section>`;
    }
    return `<section class="cockpit-ticket-why">
      <h4>Sugerencias para hacer mas eficiente la combinacion</h4>
      ${diagnosticoHtml}
      ${suggestions.well_supported_message ? `<p class="cockpit-note">${esc(suggestions.well_supported_message)}</p>` : ''}
      <div class="cockpit-human-grid">
        <article>
          <h4>Mantener</h4>
          <ul>${safeArray(suggestions.keep_numbers).map(item => `<li>${esc(item.reason_es)}</li>`).join('') || '<li>No hay numeros con soporte fuerte destacado.</li>'}</ul>
        </article>
        <article>
          <h4>Revisar</h4>
          <ul>${safeArray(suggestions.review_numbers).map(item => `<li>${esc(item.reason_es)}</li>`).join('') || '<li>Sin numeros debiles claros; revisar solo duplicidad y tesis.</li>'}</ul>
        </article>
      </div>
      <article class="cockpit-panel">
        <h4>Cambios sugeridos</h4>
        <ul>${safeArray(suggestions.swap_suggestions).map(swap => `<li>
          <b>Cambiar ${esc(swap.remove)} por ${esc(swap.add)}</b>: ${esc(swap.improvements_es.join(' '))}
          <br><span>Nueva combinacion: <code>${esc(swap.new_numbers.join(' '))}</code></span>
          <br><span>Revisar: ${esc(swap.tradeoffs_es.join(' '))}</span>
          ${swap.tesis_es ? `<br><span>${esc(swap.tesis_es)}</span>` : ''}
          <br><span>Tags: ${esc(swap.reason_tags.join(', ') || 'no disponible')}</span>
        </li>`).join('') || '<li>No se encontraron swaps con ajuste claro desde las fuentes cargadas.</li>'}</ul>
      </article>
      <article class="cockpit-panel">
        <h4>Ajustes de pares / forma / suma</h4>
        <ul>
          ${safeArray(suggestions.pair_suggestions).map(item => `<li>${esc(item)}</li>`).join('')}
          ${safeArray(suggestions.sum_suggestions).map(item => `<li>${esc(item)}</li>`).join('')}
          ${safeArray(suggestions.structure_suggestions).map(item => `<li>${esc(item)}</li>`).join('')}
        </ul>
        <p class="cockpit-note">Candidatos revisables: ${esc(suggestions.candidate_numbers.map(row => `${row.number} (${row.tags.join(', ')})`).join('; ') || 'no disponible')}.</p>
      </article>
    </section>`;
  }

  function weightObservationsForNumbers(numbers, data) {
    const numberSet = new Set(safeArray(numbers).map(Number));
    const source = data.videoWeights || data.videoWeightObservations || {};
    return safeArray(source.observations).filter(item => {
      const ball = Number(item.ball ?? item.number);
      return Number.isFinite(ball) && numberSet.has(ball);
    });
  }

  function renderManualWeightObservations(numbers, data) {
    const observations = weightObservationsForNumbers(numbers, data);
    if (!observations.length) return '';
    return `<section class="cockpit-ticket-why">
      <h4>Pesaje visual observado</h4>
      <p class="cockpit-note">Fuente auxiliar visual. No afecta constructor, scores ni priors.</p>
      <div class="cockpit-diagnostics-grid">
        ${observations.slice(0, 6).map(item => `<article class="cockpit-panel">
          ${metric('Bola', item.ball ?? item.number ?? 'revision manual', 'mono')}
          ${metric('Peso g', item.weight_g ?? 'revision manual', 'mono')}
          ${metric('Confianza', item.confidence || 'no disponible')}
          ${metric('Review status', item.review_status || 'pending')}
          ${metric('Timestamp', item.timestamp_text || 'no disponible')}
        </article>`).join('')}
      </div>
    </section>`;
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
      const manualTicket = buildManualTicket(numbers, result);
      const decision = humanTicketDecision(manualTicket, data);
      const pairRelations = manualPairRelations(numbers, data);
      const suggestions = manualEfficiencySuggestions(numbers, result, data);
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
        ${renderHumanDecisionBlock(decision)}
        ${renderManualPairRelations(pairRelations)}
        ${renderManualSumThesis(result, data)}
        ${renderManualStructureCompletion(numbers, result, data)}
        ${renderManualEfficiencySuggestions(suggestions)}
        <h4>Señales por número</h4>
        <div class="cockpit-diagnostics-grid">${numbers.map(number => `<article class="cockpit-panel"><h5>${esc(number)}</h5><div class="cockpit-role-pills">${signalChips(result.numberSignals[String(number)]) || '<span class="cockpit-pill">sin señal cargada</span>'}</div></article>`).join('')}</div>
        <h4>Lectura por ventanas</h4>
        <ul>${result.windowNotes.map(note => `<li>${esc(note)}</li>`).join('')}</ul>
        ${renderManualWeightObservations(numbers, data)}
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
