// v4-clean-app.js
// Web V2 foundation: V4.2-only strict validator + pure V4 manual math evaluator.
(function () {
  'use strict';

  const REQUIRED_FEEDBACK_VERSION = 'V4.2';
  const REQUIRED_SOURCE_HINTS = ['v4_2', 'V4.2', 'oos_feedback'];
  const MAX_NUMBER = 56;
  const PICK_COUNT = 6;

  const COMPONENT_WEIGHTS = Object.freeze({
    modelScore: 0.40,
    structuralBalance: 0.24,
    poolAlignment: 0.20,
    gravityPhysics: 0.16,
  });

  const state = {
    jsonData: null,
    initialized: false,
  };

  const $ = id => document.getElementById(id);

  function text(id, value) {
    const el = $(id);
    if (el) el.textContent = value ?? '—';
  }

  function show(el) {
    if (el) el.classList.remove('hidden');
  }

  function hide(el) {
    if (el) el.classList.add('hidden');
  }

  function clamp(value, min = 0, max = 100) {
    return Math.max(min, Math.min(max, Number.isFinite(Number(value)) ? Number(value) : 0));
  }

  function asPercent(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return 0;
    return n > 0 && n <= 1 ? n * 100 : n;
  }

  function mean(values) {
    const valid = values.filter(v => Number.isFinite(Number(v))).map(Number);
    return valid.length ? valid.reduce((a, b) => a + b, 0) / valid.length : 0;
  }

  function std(values) {
    const valid = values.filter(v => Number.isFinite(Number(v))).map(Number);
    if (!valid.length) return 0;
    const m = mean(valid);
    return Math.sqrt(valid.reduce((acc, v) => acc + Math.pow(v - m, 2), 0) / valid.length);
  }

  function fmtDate(value) {
    if (!value) return 'Sin timestamp';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return date.toLocaleString('es-MX', {
      year: 'numeric', month: 'short', day: '2-digit',
      hour: '2-digit', minute: '2-digit'
    });
  }

  function normalizeGameMode(value) {
    const raw = String(value || '').toLowerCase();
    if (raw.includes('melate')) return 'Melate';
    if (raw.includes('revancha')) return 'Revancha';
    return value || 'No declarado';
  }

  function getFeedbackLoop(jsonData) {
    return jsonData?.feedback_loop || jsonData?.walk_forward?.feedback_loop || jsonData?.deep_stacking?.feedback_loop || null;
  }

  function isV42(jsonData) {
    const feedback = getFeedbackLoop(jsonData);
    const versionOk = feedback?.version === REQUIRED_FEEDBACK_VERSION;
    const source = [jsonData?.source, jsonData?.model_version, jsonData?.v4_score_kind, jsonData?.score_kind]
      .filter(Boolean)
      .join(' ');
    const sourceLooksV42 = REQUIRED_SOURCE_HINTS.some(hint => source.includes(hint));
    return Boolean(versionOk && sourceLooksV42);
  }

  function fatal(message, jsonData) {
    hide($('loading-panel'));
    hide($('dashboard'));
    const box = $('fatal-error');
    text('fatal-error-message', message);
    show(box);
    console.error('[Web V2] JSON rejected:', { message, jsonData });
    throw new Error(message);
  }

  function validateV42(jsonData) {
    if (!jsonData || typeof jsonData !== 'object') {
      fatal('resultados.json no contiene un objeto JSON válido. La Web V2 solo acepta salidas V4.2.', jsonData);
    }

    const feedback = getFeedbackLoop(jsonData);
    if (!feedback) {
      fatal('El JSON no trae feedback_loop ni walk_forward.feedback_loop. Ejecuta local_cruncher_v4_deep_stacking.py actualizado a V4.2 y vuelve a subir resultados.json.', jsonData);
    }

    if (feedback.version !== REQUIRED_FEEDBACK_VERSION) {
      fatal(`Versión de feedback_loop inválida: ${feedback.version || 'sin versión'}. Requerido: ${REQUIRED_FEEDBACK_VERSION}.`, jsonData);
    }

    if (!isV42(jsonData)) {
      fatal('El JSON declara feedback_loop V4.2, pero source/model_version/v4_score_kind no parecen pertenecer al motor V4.2 OOS Feedback Loop. Se detiene para evitar mezclar datos legacy.', jsonData);
    }

    return feedback;
  }

  function normalizeNumbers(numbersArray) {
    if (!Array.isArray(numbersArray)) {
      throw new Error('evaluateManualComboV4 requiere un array de 6 números.');
    }
    const numbers = numbersArray.map(n => Number(n)).filter(n => Number.isInteger(n));
    if (numbers.length !== PICK_COUNT) {
      throw new Error(`La combinación debe tener exactamente ${PICK_COUNT} números.`);
    }
    if (new Set(numbers).size !== PICK_COUNT) {
      throw new Error('La combinación no puede contener números repetidos.');
    }
    if (numbers.some(n => n < 1 || n > MAX_NUMBER)) {
      throw new Error(`Todos los números deben estar entre 1 y ${MAX_NUMBER}.`);
    }
    return numbers.slice().sort((a, b) => a - b);
  }

  function buildManualSeedMap(jsonData) {
    const seed = Array.isArray(jsonData?.manual_suggestion_seed) ? jsonData.manual_suggestion_seed : [];
    const map = new Map();
    seed.forEach(row => {
      const n = Number(row?.number ?? row?.n ?? row?.ball);
      if (Number.isInteger(n) && n >= 1 && n <= MAX_NUMBER) {
        map.set(n, row);
      }
    });
    return map;
  }

  function getNumberScore(number, jsonData, seedMap) {
    const row = seedMap.get(number) || {};
    const scoreFromSeed = row.score ?? row.meta_score ?? row.score_percent ?? row.net_score;
    const scoreFromMap = jsonData?.number_scores?.[String(number)] ?? jsonData?.number_scores?.[number];
    return clamp(asPercent(scoreFromSeed ?? scoreFromMap ?? 0));
  }

  function getExpertScore(row, key) {
    const raw = row?.expert_raw || row?.expert_scores || row?.experts || {};
    return asPercent(raw[key]);
  }

  function extractPhysicalNode(number, jsonData, seedMap) {
    const row = seedMap.get(number) || {};
    const physics = jsonData?.physics_summary || {};

    const realWeight = Number(
      row.real_weight ?? row.raw_weight ?? row.base_weight ?? row.ball_weight ?? row.weight ?? row.measured_weight
    );
    const effectiveWeight = Number(
      row.effective_weight ?? row.effectiveWeight ?? row.weight_effective ?? row.sigmoid_weight ?? row.w_eff
    );
    const usesInWindow = Number(row.uses_in_window ?? row.uses ?? row.hits_in_window);
    const physicsBonus = Number(row.physics_bonus ?? row.physical_bonus ?? row.bonus_physics);
    const avgEffectiveWeight = Number(
      physics.avg_effective_weight ?? physics.average_effective_weight ?? physics.mean_effective_weight ?? physics.avgEffectiveWeight
    );

    return {
      number,
      realWeight: Number.isFinite(realWeight) ? realWeight : null,
      effectiveWeight: Number.isFinite(effectiveWeight) ? effectiveWeight : null,
      avgEffectiveWeight: Number.isFinite(avgEffectiveWeight) ? avgEffectiveWeight : null,
      usesInWindow: Number.isFinite(usesInWindow) ? usesInWindow : null,
      physicsBonus: Number.isFinite(physicsBonus) ? physicsBonus : null,
      source: 'manual_suggestion_seed + physics_summary',
      hasRealWeight: Number.isFinite(realWeight),
      hasEffectiveWeight: Number.isFinite(effectiveWeight),
    };
  }

  function evaluateModelScore(numbers, jsonData, seedMap) {
    const rows = numbers.map(number => {
      const seed = seedMap.get(number) || {};
      const modelScore = getNumberScore(number, jsonData, seedMap);
      const transformer = getExpertScore(seed, 'transformer');
      const graph = getExpertScore(seed, 'graph');
      const xgboost = getExpertScore(seed, 'xgboost');
      const expertValues = [transformer, graph, xgboost].filter(v => Number.isFinite(v) && v > 0);
      const expertAverage = expertValues.length ? mean(expertValues) : modelScore;
      return { number, modelScore, transformer, graph, xgboost, expertAverage };
    });
    return {
      score: clamp(mean(rows.map(r => r.expertAverage))),
      numberAverageScore: clamp(mean(rows.map(r => r.modelScore))),
      rows,
      formula: 'Promedio de Transformer/Grafo/XGBoost cuando existen; fallback a score del número.',
    };
  }

  function evaluateStructuralBalance(numbers) {
    const sorted = numbers.slice().sort((a, b) => a - b);
    const evenCount = sorted.filter(n => n % 2 === 0).length;
    const oddCount = PICK_COUNT - evenCount;
    const leftCount = sorted.filter(n => n <= 28).length;
    const rightCount = PICK_COUNT - leftCount;
    const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10))).size;
    const consecutivePairs = sorted.slice(1).filter((n, idx) => n - sorted[idx] === 1).length;
    const sum = sorted.reduce((acc, n) => acc + n, 0);

    const parityScore = clamp(100 - Math.abs(evenCount - 3) * 24);
    const sideScore = clamp(100 - Math.abs(leftCount - 3) * 22);
    const decadeScore = clamp((decades / 6) * 100);
    const consecutiveScore = clamp(100 - consecutivePairs * 18);
    const sumScore = clamp(100 - Math.min(65, Math.abs(sum - 171) / 38 * 22));

    const score = clamp(
      parityScore * 0.24 +
      sideScore * 0.24 +
      decadeScore * 0.22 +
      consecutiveScore * 0.14 +
      sumScore * 0.16
    );

    return {
      score,
      parityScore,
      sideScore,
      decadeScore,
      consecutiveScore,
      sumScore,
      evenCount,
      oddCount,
      leftCount,
      rightCount,
      decades,
      consecutivePairs,
      sum,
      profile: `${evenCount} pares/${oddCount} impares · ${leftCount} izquierda/${rightCount} derecha · ${decades} décadas`,
    };
  }

  function evaluatePoolAlignment(numbers, jsonData) {
    const pool = Array.isArray(jsonData?.generator_pool) ? jsonData.generator_pool : [];
    const target = new Set(numbers);
    let best = {
      rank: null,
      overlap: 0,
      poolScore: 0,
      numbers: [],
    };

    pool.slice(0, 180).forEach((combo, index) => {
      const comboNumbers = (combo.numbers || combo.nums || combo.combo || [])
        .map(Number)
        .filter(n => Number.isInteger(n) && n >= 1 && n <= MAX_NUMBER);
      if (comboNumbers.length !== PICK_COUNT) return;
      const overlap = comboNumbers.filter(n => target.has(n)).length;
      const poolScore = clamp(asPercent(combo.score_percent ?? combo.net_score ?? combo.confidence ?? combo.score));
      const value = overlap * 18 + poolScore;
      const bestValue = best.overlap * 18 + best.poolScore;
      if (value > bestValue) {
        best = { rank: index + 1, overlap, poolScore, numbers: comboNumbers };
      }
    });

    const score = clamp(best.overlap * 16 + Math.min(36, best.poolScore * 0.36));
    return {
      score,
      bestRank: best.rank,
      overlap: best.overlap,
      poolScore: best.poolScore,
      nearestPoolCombo: best.numbers,
      poolSize: pool.length,
    };
  }

  function classifyGravityProfile(meanDeviation, avgAbsDeviation) {
    const heavyThreshold = 0.035;
    const extremeThreshold = 0.070;
    if (meanDeviation >= heavyThreshold && avgAbsDeviation >= heavyThreshold) return 'Muy Pesado';
    if (meanDeviation <= -heavyThreshold && avgAbsDeviation >= heavyThreshold) return 'Muy Ligero';
    if (avgAbsDeviation >= extremeThreshold) return meanDeviation >= 0 ? 'Muy Pesado' : 'Muy Ligero';
    return 'Balanceado';
  }

  function evaluateGravityPhysics(numbers, jsonData, seedMap) {
    const physicalRows = numbers.map(number => extractPhysicalNode(number, jsonData, seedMap));
    const effectiveWeights = physicalRows.map(row => row.effectiveWeight).filter(v => Number.isFinite(v));
    const avgEffectiveFromSummary = physicalRows.find(row => Number.isFinite(row.avgEffectiveWeight))?.avgEffectiveWeight;
    const avgEffectiveWeight = Number.isFinite(avgEffectiveFromSummary)
      ? avgEffectiveFromSummary
      : mean(effectiveWeights);

    if (!effectiveWeights.length || !Number.isFinite(avgEffectiveWeight) || avgEffectiveWeight <= 0) {
      return {
        score: 0,
        gravityProfile: 'Sin datos físicos',
        avgComboEffectiveWeight: null,
        avgEffectiveWeight: Number.isFinite(avgEffectiveWeight) ? avgEffectiveWeight : null,
        meanDeviation: null,
        avgAbsDeviation: null,
        dispersion: null,
        physicalRows,
        warning: 'No hay effective_weight suficiente en manual_suggestion_seed/physics_summary.',
      };
    }

    const deviations = effectiveWeights.map(w => w - avgEffectiveWeight);
    const avgComboEffectiveWeight = mean(effectiveWeights);
    const meanDeviation = avgComboEffectiveWeight - avgEffectiveWeight;
    const avgAbsDeviation = mean(deviations.map(Math.abs));
    const dispersion = std(effectiveWeights);
    const gravityProfile = classifyGravityProfile(meanDeviation, avgAbsDeviation);

    const deviationPenalty = Math.min(52, (Math.abs(meanDeviation) / 0.09) * 52);
    const homogenousExtremePenalty = gravityProfile === 'Balanceado' ? 0 : Math.min(22, (avgAbsDeviation / 0.09) * 22);
    const dispersionPenalty = Math.min(12, (dispersion / 0.07) * 12);
    const score = clamp(100 - deviationPenalty - homogenousExtremePenalty - dispersionPenalty);

    return {
      score,
      gravityProfile,
      avgComboEffectiveWeight,
      avgEffectiveWeight,
      meanDeviation,
      avgAbsDeviation,
      dispersion,
      deviationPenalty,
      homogenousExtremePenalty,
      dispersionPenalty,
      physicalRows: physicalRows.map(row => ({
        ...row,
        effectiveDeviation: Number.isFinite(row.effectiveWeight) ? row.effectiveWeight - avgEffectiveWeight : null,
      })),
    };
  }

  function evaluateManualComboV4(numbersArray, jsonData) {
    const numbers = normalizeNumbers(numbersArray);
    validateV42(jsonData);
    const seedMap = buildManualSeedMap(jsonData);

    const model = evaluateModelScore(numbers, jsonData, seedMap);
    const structural = evaluateStructuralBalance(numbers);
    const pool = evaluatePoolAlignment(numbers, jsonData);
    const gravity = evaluateGravityPhysics(numbers, jsonData, seedMap);

    const netScoreV4 = clamp(
      model.score * COMPONENT_WEIGHTS.modelScore +
      structural.score * COMPONENT_WEIGHTS.structuralBalance +
      pool.score * COMPONENT_WEIGHTS.poolAlignment +
      gravity.score * COMPONENT_WEIGHTS.gravityPhysics
    );

    return {
      numbers,
      netScoreV4,
      score: netScoreV4,
      gravityProfile: gravity.gravityProfile,
      componentWeights: COMPONENT_WEIGHTS,
      components: {
        modelScore: model,
        structuralBalance: structural,
        poolAlignment: pool,
        gravityPhysics: gravity,
      },
      summary: {
        modelScore: model.score,
        structuralBalance: structural.score,
        poolAlignment: pool.score,
        gravityPhysics: gravity.score,
        netScoreV4,
        gravityProfile: gravity.gravityProfile,
      },
    };
  }

  function headerModelVersion(jsonData) {
    return jsonData?.model_version || jsonData?.source || 'V4.2';
  }

  function renderHeader(jsonData) {
    text('header-last-update', fmtDate(jsonData.last_update));
    text('header-game-mode', normalizeGameMode(jsonData.game_mode || jsonData.game_label));
    text('header-model-version', headerModelVersion(jsonData));
  }

  function renderKpis(jsonData, feedback) {
    const wf = jsonData.walk_forward || {};
    const pool = Array.isArray(jsonData.generator_pool) ? jsonData.generator_pool : [];
    text('kpi-score-kind', jsonData.v4_score_kind || jsonData.score_kind || 'No declarado');
    text('kpi-feedback-loop', `${feedback.version} · decay ${feedback.decay ?? '—'}`);
    text('kpi-walk-forward', `${wf.steps ?? wf.rows?.length ?? 0} folds · avg hits ${wf.avg_hits ?? '—'}`);
    text('kpi-generator-pool', `${pool.length} combos`);
  }

  function renderPreview(jsonData, feedback) {
    const preview = {
      accepted_contract: 'Web V2 / V4.2-only',
      source: jsonData.source,
      model_version: jsonData.model_version,
      score_kind: jsonData.score_kind,
      v4_score_kind: jsonData.v4_score_kind,
      feedback_loop: feedback,
      evaluator: {
        function: 'evaluateManualComboV4(numbersArray, jsonData)',
        weights: COMPONENT_WEIGHTS,
        gravity_source: 'manual_suggestion_seed.effective_weight + physics_summary.avg_effective_weight',
      },
      walk_forward_summary: {
        steps: jsonData.walk_forward?.steps,
        avg_hits: jsonData.walk_forward?.avg_hits,
        avg_hits_top10: jsonData.walk_forward?.avg_hits_top10,
        avg_mse: jsonData.walk_forward?.avg_mse,
      },
      generator_pool_size: Array.isArray(jsonData.generator_pool) ? jsonData.generator_pool.length : 0,
      top_combinations_size: Array.isArray(jsonData.top_combinations) ? jsonData.top_combinations.length : 0,
    };
    const el = $('contract-preview');
    if (el) el.textContent = JSON.stringify(preview, null, 2);
  }

  function initApp(jsonData) {
    const feedback = validateV42(jsonData);
    state.jsonData = jsonData;
    state.initialized = true;

    hide($('fatal-error'));
    hide($('loading-panel'));
    show($('dashboard'));

    renderHeader(jsonData);
    renderKpis(jsonData, feedback);
    renderPreview(jsonData, feedback);

    window.FISICAPAPA_WEB_V2 = {
      version: 'Web V2 foundation + V4 manual math evaluator',
      requiredFeedbackVersion: REQUIRED_FEEDBACK_VERSION,
      componentWeights: COMPONENT_WEIGHTS,
      jsonData,
      feedback,
      state,
      evaluateManualComboV4: numbers => evaluateManualComboV4(numbers, jsonData),
    };
  }

  async function loadJsonAndInit() {
    hide($('fatal-error'));
    show($('loading-panel'));
    hide($('dashboard'));

    const response = await fetch(`resultados.json?v42=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) {
      fatal(`No se pudo cargar resultados.json. HTTP ${response.status}.`, null);
    }
    const jsonData = await response.json();
    initApp(jsonData);
  }

  function bindReload() {
    const btn = $('btn-reload-json');
    if (btn) btn.addEventListener('click', () => loadJsonAndInit().catch(err => fatal(err.message, null)));
  }

  document.addEventListener('DOMContentLoaded', () => {
    bindReload();
    loadJsonAndInit().catch(err => fatal(err.message, null));
  });

  window.initApp = initApp;
  window.evaluateManualComboV4 = evaluateManualComboV4;
})();
