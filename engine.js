// ═══════════════════════════════════════════════════════
// engine.js - MOTOR MATEMÁTICO (V7.3 — Revisado)
// ═══════════════════════════════════════════════════════

// ── SISTEMA DE FÍSICA DE ESFERAS (REGLAMENTO MELATE) ──
const WEIGHT_MIN      = 4.25;
const WEIGHT_MAX      = 5.25;
const WEIGHT_DIFF_MAX = 0.30;
const BASE_WEIGHT     = (WEIGHT_MIN + WEIGHT_MAX) / 2; // 4.75g fallback
const WEAR_PER_USE    = 0.0008; // g perdidos por sorteo de uso
const ENGINE_CALIBRATION_PREFIX = 'melate_engine_calibration_';

const DEFAULT_ENGINE_CONFIG = {
  sigmoidWear: { L: 0, K: 0.085, r: 0.055, n0: 60 },
  entropy: { windowSize: 15, klThreshold: 0.18, smoothing: 1e-6 },
  montecarlo: { iterations: 5000, eliteSize: 64 },
  training: { topK: 10, boostRate: 0.05, explorationPenalty: 0.05, chaosVarianceThreshold: 0.055 },
  ensembleWeights: {
    physical: 0.25,
    structural: 0.25,
    temporal: 0.35,
    entropy: 0.15
  },
  confidence: 70,
  chaosMode: false,
  updatedAt: null
};

// ── PESOS POR DEFECTO (medición real — imagen de referencia del usuario) ──
const DEFAULT_BALL_WEIGHTS_REVANCHA = [
  0,     // índice 0 sin uso
  4.35, 4.33, 4.36, 4.31, 4.35, 4.39, 4.33, 4.37, 4.34, 4.37, // 1-10
  4.36, 4.32, 4.35, 4.32, 4.35, 4.33, 4.31, 4.33, 4.31, 4.39, // 11-20
  4.37, 4.33, 4.34, 4.31, 4.31, 4.38, 4.31, 4.34, 4.36, 4.34, // 21-30
  4.35, 4.35, 4.36, 4.34, 4.37, 4.34, 4.39, 4.32, 4.32, 4.33, // 31-40
  4.37, 4.39, 4.34, 4.35, 4.32, 4.36, 4.40, 4.30, 4.31, 4.32, // 41-50
  4.30, 4.29, 4.29, 4.43, 4.42, 4.44                           // 51-56
];
const DEFAULT_BALL_WEIGHTS_MELATE = [
  0,
  4.53, 4.56, 4.53, 4.54, 4.53, 4.52, 4.52, 4.55, 4.54, 4.59, // 1-10
  4.51, 4.60, 4.54, 4.58, 4.60, 4.53, 4.55, 4.55, 4.51, 4.58, // 11-20
  4.57, 4.51, 4.58, 4.50, 4.53, 4.51, 4.50, 4.55, 4.51, 4.54, // 21-30
  4.51, 4.54, 4.52, 4.53, 4.52, 4.59, 4.59, 4.58, 4.52, 4.59, // 31-40
  4.53, 4.53, 4.58, 4.59, 4.51, 4.58, 4.58, 4.58, 4.55, 4.58, // 41-50
  4.59, 4.56, 4.61, 4.58, 4.59, 4.54                           // 51-56
];

// Pesos activos — sobreescritos por reloadWeightsForMode() al iniciar / cambiar modo
let BALL_WEIGHTS = [...DEFAULT_BALL_WEIGHTS_REVANCHA];
let ENGINE_CONFIG = cloneEngineConfig(DEFAULT_ENGINE_CONFIG);

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function cloneEngineConfig(config) {
  return JSON.parse(JSON.stringify(config));
}

function normalizeEnsembleWeights(weights) {
  const base = { ...DEFAULT_ENGINE_CONFIG.ensembleWeights, ...(weights || {}) };
  const clean = {};
  let total = 0;
  Object.keys(DEFAULT_ENGINE_CONFIG.ensembleWeights).forEach((key) => {
    clean[key] = Math.max(0.01, Number(base[key]) || 0.01);
    total += clean[key];
  });
  Object.keys(clean).forEach((key) => { clean[key] /= total || 1; });
  return clean;
}

function adjustEnsembleWeights(currentWeights, rewardScore, options = {}) {
  const cfg = { ...ENGINE_CONFIG.training, ...(options || {}) };
  const weights = normalizeEnsembleWeights(currentWeights || ENGINE_CONFIG.ensembleWeights);
  const rewards = rewardScore && rewardScore.experts ? rewardScore.experts : {};
  const ranked = Object.entries(rewards).sort((a, b) => b[1] - a[1]);
  const bestExpert = ranked.length ? ranked[0][0] : null;

  if ((rewardScore && rewardScore.bestHits || 0) === 0) {
    const uniform = 1 / Object.keys(weights).length;
    const penalized = {};
    Object.keys(weights).forEach((key) => {
      penalized[key] = weights[key] * (1 - cfg.explorationPenalty) + uniform * cfg.explorationPenalty;
    });
    return normalizeEnsembleWeights(penalized);
  }

  if (!bestExpert) return weights;
  return normalizeEnsembleWeights({
    ...weights,
    [bestExpert]: weights[bestExpert] * (1 + cfg.boostRate)
  });
}

function mergeEngineConfig(config) {
  const source = config || {};
  return {
    sigmoidWear: { ...DEFAULT_ENGINE_CONFIG.sigmoidWear, ...(source.sigmoidWear || {}) },
    entropy: { ...DEFAULT_ENGINE_CONFIG.entropy, ...(source.entropy || {}) },
    montecarlo: { ...DEFAULT_ENGINE_CONFIG.montecarlo, ...(source.montecarlo || {}) },
    training: { ...DEFAULT_ENGINE_CONFIG.training, ...(source.training || {}) },
    ensembleWeights: normalizeEnsembleWeights(source.ensembleWeights),
    confidence: Number.isFinite(source.confidence) ? source.confidence : DEFAULT_ENGINE_CONFIG.confidence,
    chaosMode: Boolean(source.chaosMode),
    mse: source.mse || null,
    chaosRate: source.chaosRate || 0,
    avgHits: source.avgHits || 0,
    updatedAt: source.updatedAt || null
  };
}

function getEngineCalibrationKey(mode) {
  return `${ENGINE_CALIBRATION_PREFIX}${mode || CURRENT_MODE || 'revancha'}`;
}

function getEngineConfigSnapshot() {
  return cloneEngineConfig(ENGINE_CONFIG);
}

function setEngineCalibration(calibration, persist = true, mode = CURRENT_MODE) {
  ENGINE_CONFIG = mergeEngineConfig({ ...ENGINE_CONFIG, ...(calibration || {}) });
  if (persist) saveEngineCalibration(mode, ENGINE_CONFIG);
  return getEngineConfigSnapshot();
}

function loadEngineCalibrationFromStorage(mode = CURRENT_MODE) {
  try {
    const raw = localStorage.getItem(getEngineCalibrationKey(mode));
    if (!raw) return null;
    return mergeEngineConfig(JSON.parse(raw));
  } catch (e) {
    console.warn('No se pudo leer la calibracion del motor:', e);
    return null;
  }
}

async function loadEngineCalibration(mode = CURRENT_MODE) {
  let stored = loadEngineCalibrationFromStorage(mode);
  if (DB_INSTANCE) {
    stored = await new Promise((resolve) => {
      const tx = DB_INSTANCE.transaction('metadata', 'readonly');
      const req = tx.objectStore('metadata').get(getEngineCalibrationKey(mode));
      req.onsuccess = () => resolve(req.result && req.result.value ? req.result.value : stored);
      req.onerror = () => resolve(stored);
    });
  }
  ENGINE_CONFIG = mergeEngineConfig(stored || DEFAULT_ENGINE_CONFIG);
  return getEngineConfigSnapshot();
}

async function saveEngineCalibration(mode = CURRENT_MODE, calibration = ENGINE_CONFIG) {
  const value = mergeEngineConfig(calibration);
  try {
    localStorage.setItem(getEngineCalibrationKey(mode), JSON.stringify(value));
  } catch (e) {
    console.warn('No se pudo guardar la calibracion en localStorage:', e);
  }
  if (!DB_INSTANCE) return value;
  return new Promise((resolve) => {
    const tx = DB_INSTANCE.transaction('metadata', 'readwrite');
    tx.objectStore('metadata').put({ key: getEngineCalibrationKey(mode), value, updatedAt: new Date().toISOString() });
    tx.oncomplete = () => resolve(value);
    tx.onerror = () => resolve(value);
  });
}

function sigmoidWearFactor(useCount, params = ENGINE_CONFIG.sigmoidWear) {
  const p = { ...DEFAULT_ENGINE_CONFIG.sigmoidWear, ...(params || {}) };
  return p.L + ((p.K - p.L) / (1 + Math.exp(-p.r * (useCount - p.n0))));
}

// ── VALIDACIÓN REGLAMENTARIA ──
function validateWeights() {
  const violations = [];
  const validBalls = BALL_WEIGHTS.slice(1);
  const minW = Math.min(...validBalls);
  const maxW = Math.max(...validBalls);
  for (let n = 1; n <= 56; n++) {
    const w = BALL_WEIGHTS[n];
    if (w < WEIGHT_MIN) violations.push({ n, type: 'bajo', w });
    if (w > WEIGHT_MAX) violations.push({ n, type: 'alto', w });
  }
  if (maxW - minW > WEIGHT_DIFF_MAX)
    violations.push({ n: null, type: 'diferencia', diff: parseFloat((maxW - minW).toFixed(4)), minW, maxW });
  return violations;
}

// ── HELPER: usos y pesos efectivos de todas las esferas en O(n) ──
// Se llama UNA vez por operación para evitar loops O(n²) o peor.
function _buildPhysics(DATA) {
  const uses = new Array(57).fill(0);
  DATA.forEach(row => {
    row.slice(2).forEach(n => { if (n >= 1 && n <= 56) uses[n]++; });
  });
  const effective = new Array(57).fill(0);
  let sumEff = 0;
  for (let n = 1; n <= 56; n++) {
    effective[n] = (BALL_WEIGHTS[n] || BASE_WEIGHT) - sigmoidWearFactor(uses[n]);
    sumEff += effective[n];
  }
  const avgEffective = sumEff / 56;
  return { uses, effective, avgEffective };
}

// ── BONUS DE FÍSICA — acepta physics precalculado para evitar recómputos ──
function getPhysicsBonus(n, physics) {
  const DATA = getActiveData();
  if (!DATA.length) return 0;
  const p = physics || _buildPhysics(DATA);

  const deltaWeight  = p.effective[n] - p.avgEffective;
  let bonus = -(deltaWeight / 0.05) * 6;

  const useRate = p.uses[n] / DATA.length;
  if (useRate > 0.40) bonus += 10;
  else if (useRate > 0.30) bonus += 5;

  if ((BALL_WEIGHTS[n] || BASE_WEIGHT) > BASE_WEIGHT + 0.15) bonus -= 5;

  return Math.max(-15, Math.min(20, bonus));
}

// ── INFO DETALLADA DE FÍSICA PARA LA UI ──
function getBallPhysicsInfo(n) {
  const DATA   = getActiveData();
  const p      = _buildPhysics(DATA);
  const weight = BALL_WEIGHTS[n] || BASE_WEIGHT;
  const wearFactor      = sigmoidWearFactor(p.uses[n]);
  const effectiveWeight = parseFloat((weight - wearFactor).toFixed(4));
  const useRate         = DATA.length > 0 ? p.uses[n] / DATA.length : 0;
  const bonus           = getPhysicsBonus(n, p);
  const violations      = validateWeights().filter(v => v.n === n);
  return { weight, effectiveWeight, uses: p.uses[n], useRate, wearFactor: parseFloat(wearFactor.toFixed(4)), bonus, violations };
}

// ── POOL PONDERADO POR FÍSICA PARA MONTECARLO ──
function getPhysicsWeightedPool(DATA, physics) {
  const draws = DATA || getActiveData();
  const p     = physics || _buildPhysics(draws);

  const vals  = [];
  for (let n = 1; n <= 56; n++) vals.push(p.effective[n]);
  const minW  = Math.min(...vals);
  const maxW  = Math.max(...vals);
  const range = maxW - minW || 0.001;

  const weighted = [];
  for (let n = 1; n <= 56; n++) {
    const tickets = Math.max(1, Math.round(5 - ((p.effective[n] - minW) / range) * 4));
    for (let t = 0; t < tickets; t++) weighted.push(n);
  }
  return weighted;
}

function _frequencyDistribution(DATA, smoothing = ENGINE_CONFIG.entropy.smoothing) {
  const counts = new Array(57).fill(smoothing);
  let total = smoothing * 56;
  DATA.forEach(row => {
    row.slice(2).forEach(n => {
      if (n >= 1 && n <= 56) {
        counts[n]++;
        total++;
      }
    });
  });
  return counts.map(value => value / total);
}

function _shannonEntropy(distribution) {
  let entropy = 0;
  for (let n = 1; n <= 56; n++) {
    const p = distribution[n] || 0;
    if (p > 0) entropy -= p * Math.log2(p);
  }
  return entropy;
}

function _klDivergence(p, q) {
  let kl = 0;
  for (let n = 1; n <= 56; n++) {
    if (p[n] > 0 && q[n] > 0) kl += p[n] * Math.log(p[n] / q[n]);
  }
  return kl;
}

function detectEntropyDrift(DATA = getActiveData()) {
  const opts = ENGINE_CONFIG.entropy;
  if (!DATA || DATA.length < opts.windowSize + 5) {
    return { chaosMode: false, kl: 0, recentEntropy: 0, historicalEntropy: 0, confidenceFactor: 1 };
  }

  const recentDist = _frequencyDistribution(DATA.slice(0, opts.windowSize), opts.smoothing);
  const historicalDist = _frequencyDistribution(DATA, opts.smoothing);
  const kl = _klDivergence(recentDist, historicalDist);
  const chaosMode = kl >= opts.klThreshold;

  return {
    chaosMode,
    kl,
    recentEntropy: _shannonEntropy(recentDist),
    historicalEntropy: _shannonEntropy(historicalDist),
    confidenceFactor: chaosMode ? clamp(1 - (kl / (opts.klThreshold * 3)), 0.35, 0.8) : 1
  };
}

function getSystemConfidence() {
  const drift = detectEntropyDrift();
  const trained = Number.isFinite(ENGINE_CONFIG.confidence) ? ENGINE_CONFIG.confidence : 70;
  return clamp(trained * drift.confidenceFactor, 0, 100);
}

// ── ESTADÍSTICAS PRINCIPALES ──
// Siempre opera sobre getActiveData() — refleja inmediatamente cualquier CSV cargado.
function computeStats() {
  const DATA  = getActiveData();
  const total = DATA.length;
  const freq     = new Array(57).fill(0);
  const freq30   = new Array(57).fill(0);
  // lastSeen[n]: índice del sorteo más reciente (0 = más nuevo, array desc)
  // Si nunca salió → total (máximo retraso)
  const lastSeen = new Array(57).fill(total);

  DATA.forEach((row, i) => {
    row.slice(2).forEach(n => {
      if (n < 1 || n > 56) return;
      freq[n]++;
      if (i < 30) freq30[n]++;
      if (lastSeen[n] === total) lastSeen[n] = i;
    });
  });

  const expected = 6 / 56;

  // Física pre-calculada UNA vez para todos los numScore (O(n) total, no O(n²))
  const phys = _buildPhysics(DATA);
  const entropy = detectEntropyDrift(DATA);

  function numScore(n) {
    if (total === 0) return 50;
    const f   = freq[n] / total;
    const ret = lastSeen[n];
    const f30 = freq30[n];
    let s = 50;

    // Inercia (racha caliente)
    if (f30 >= 3) s += 20;
    if (ret <= 3) s += 15;
    if (f > expected) s += 10;

    // Compensación (rebote frío)
    if (ret > 15) s += 15;
    if (ret > 25) s += 10;

    // Penalización
    if (ret === 0 && f30 < 2) s -= 10;

    // Física de esferas (O(1) con caché)
    s += getPhysicsBonus(n, phys);

    return Math.max(0, Math.min(100, s * entropy.confidenceFactor));
  }

  return { total, freq, freq30, lastSeen, numScore, phys, entropy };
}

// ── EVALUACIÓN DE COMBINACIÓN ──
function evalCombo(nums) {
  const sorted  = [...nums].sort((a, b) => a - b);
  const advanced = computeAdaptiveComboScore(sorted);
  const suma    = sorted.reduce((a, b) => a + b, 0);
  const pares   = sorted.filter(n => n % 2 === 0).length;
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10)));
  let consec = 0;
  for (let i = 0; i < sorted.length - 1; i++) {
    if (sorted[i + 1] === sorted[i] + 1) consec++;
  }
  return { sorted, suma, pares, impares: 6 - pares, decades: decades.size, consec, total_score: advanced.total };
}

function computeAdaptiveComboScore(nums) {
  const DATA = getActiveData();
  if (!DATA.length) {
    return {
      total: 50,
      components: { physical: 50, structural: 50, temporal: 50, entropy: 50 },
      weights: normalizeEnsembleWeights(ENGINE_CONFIG.ensembleWeights),
      confidence: 50,
      chaosMode: false,
      entropy: detectEntropyDrift(DATA),
      breakdown: {}
    };
  }

  const sorted = [...nums].sort((a, b) => a - b);
  const stats = computeStats();
  const { lastSeen, numScore } = stats;
  const frequencyScore = sorted.reduce((acc, n) => acc + numScore(n), 0) / 6;
  const delayScore = sorted.reduce((acc, n) => {
    const delay = lastSeen[n];
    if (delay <= 3) return acc + 20;
    if (delay > 25) return acc + 60;
    if (delay > 15) return acc + 50;
    return acc + 30 + (delay * 1.5);
  }, 0) / 6;

  const pares = sorted.filter(n => n % 2 === 0).length;
  const lowRange = sorted.filter(n => n <= 28).length;
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10)));
  const suma = sorted.reduce((a, b) => a + b, 0);
  const allSums = DATA.map(row => row.slice(2).reduce((a, b) => a + b, 0));
  const sumMean = allSums.reduce((a, b) => a + b, 0) / allSums.length;
  const sumStdDev = Math.sqrt(allSums.reduce((a, b) => a + Math.pow(b - sumMean, 2), 0) / allSums.length) || 1;
  const sumScore = 100 - Math.min(50, Math.abs((suma - sumMean) / sumStdDev) * 15);
  const pairScore = calculateFrequentPairScore(sorted) || 50;
  const balanceScore = 80 - Math.abs(pares - 3) * 15;
  const rangeScore = 100 - Math.abs(lowRange - 3) * 12;
  const decadeScore = (decades.size / 6) * 100;
  const physScore = sorted.reduce((acc, n) => acc + getPhysicsBonus(n, stats.phys) * 1.5, 0) / 6 + 50;
  const entropyMeta = stats.entropy || detectEntropyDrift(DATA);
  const histDist = _frequencyDistribution(DATA);
  const recentDist = _frequencyDistribution(DATA.slice(0, ENGINE_CONFIG.entropy.windowSize));
  const entropyScore = sorted.reduce((acc, n) => {
    const ratio = histDist[n] > 0 ? recentDist[n] / histDist[n] : 1;
    return acc + clamp(70 - Math.abs(Math.log(ratio || 1)) * 18, 0, 100);
  }, 0) / 6;

  const components = {
    physical: clamp(physScore, 0, 100),
    structural: clamp((balanceScore + rangeScore + decadeScore + sumScore) / 4, 0, 100),
    temporal: clamp((frequencyScore * 0.45) + (delayScore * 0.45) + (pairScore * 0.10), 0, 100),
    entropy: clamp(entropyScore * entropyMeta.confidenceFactor, 0, 100)
  };
  const weights = normalizeEnsembleWeights(ENGINE_CONFIG.ensembleWeights);
  const total = Math.round(
    components.physical * weights.physical +
    components.structural * weights.structural +
    components.temporal * weights.temporal +
    components.entropy * weights.entropy
  );

  return {
    total: clamp(total, 0, 100),
    components,
    weights,
    confidence: getSystemConfidence(),
    chaosMode: entropyMeta.chaosMode,
    entropy: entropyMeta,
    breakdown: {
      pares,
      impares: 6 - pares,
      lowRange,
      highRange: 6 - lowRange,
      suma,
      decades: decades.size,
      avgFreq: Math.round(frequencyScore),
      avgDelay: Math.round(delayScore)
    }
  };
}

function computeAdvancedScore(nums) {
  return computeAdaptiveComboScore(nums);
}

// Helper para calcular score de parejas frecuentes
function calculateFrequentPairScore(nums) {
  const DATA = getActiveData();
  if (!DATA.length) return 50;

  const pairFreq = {};
  DATA.forEach(row => {
    const rowNums = row.slice(2);
    for (let i = 0; i < rowNums.length; i++) {
      for (let j = i + 1; j < rowNums.length; j++) {
        const pair = [Math.min(rowNums[i], rowNums[j]), Math.max(rowNums[i], rowNums[j])].join(',');
        pairFreq[pair] = (pairFreq[pair] || 0) + 1;
      }
    }
  });

  let pairCount = 0;
  for (let i = 0; i < nums.length; i++) {
    for (let j = i + 1; j < nums.length; j++) {
      const pair = [nums[i], nums[j]].join(',');
      if (pairFreq[pair] && pairFreq[pair] >= 2) pairCount++;
    }
  }

  return 30 + (pairCount * 15);
}

// Generar sugerencias automáticas de combinaciones
function generateComboSuggestions(userNums, suggestionCount = 5) {
  const DATA = getActiveData();
  if (!DATA.length) return [];

  const suggestions = [];
  const stats = computeStats();
  const poolBase = Array.from({ length: 56 }, (_, i) => i + 1);

  // Estrategia 1: Reemplazar números individuales
  for (let replaceIdx = 0; replaceIdx < userNums.length && suggestions.length < suggestionCount; replaceIdx++) {
    const candidates = poolBase.filter(n => !userNums.includes(n)).slice(0, 2);

    candidates.forEach(candidate => {
      if (suggestions.length >= suggestionCount) return;
      const testCombo = [...userNums];
      testCombo[replaceIdx] = candidate;
      const score = computeAdvancedScore(testCombo);
      suggestions.push({
        nums: [...testCombo].sort((a, b) => a - b),
        score: score.total,
        strategy: `Incluir ${candidate}`,
        components: score.components
      });
    });
  }

  // Estrategia 2: Números con mayor retraso
  const delayedNums = poolBase
    .filter(n => !userNums.includes(n))
    .map(n => ({ n, delay: stats.lastSeen[n] }))
    .sort((a, b) => b.delay - a.delay)
    .slice(0, 8);

  for (let i = 0; i < Math.min(3, delayedNums.length) && suggestions.length < suggestionCount; i++) {
    const combo = [...userNums];
    let minDelayIdx = 0;
    for (let j = 1; j < combo.length; j++) {
      if (stats.lastSeen[combo[j]] < stats.lastSeen[combo[minDelayIdx]]) {
        minDelayIdx = j;
      }
    }
    combo[minDelayIdx] = delayedNums[i].n;
    const score = computeAdvancedScore(combo);
    suggestions.push({
      nums: [...combo].sort((a, b) => a - b),
      score: score.total,
      strategy: `Atrasado: ${delayedNums[i].n}`,
      components: score.components
    });
  }

  // Deduplicar y ordenar
  const uniqueMap = new Map();
  suggestions.forEach(s => {
    const key = s.nums.join(',');
    if (!uniqueMap.has(key) || uniqueMap.get(key).score < s.score) {
      uniqueMap.set(key, s);
    }
  });

  return Array.from(uniqueMap.values())
    .sort((a, b) => b.score - a.score)
    .slice(0, suggestionCount);
}

// ── DETECTOR DE CAMBIO DE PATRÓN ESPACIAL ──
function detectPatternShift() {
  const DATA = getActiveData();
  if (DATA.length < 10) return null;

  const masses = DATA.map(row => {
    const nums      = row.slice(2);
    const leftCount = nums.filter(n => n <= 28).length;
    return leftCount - (6 - leftCount);
  });

  const smoothed = [];
  for (let i = 0; i < masses.length - 4; i++)
    smoothed.push(masses[i] + masses[i+1] + masses[i+2] + masses[i+3] + masses[i+4]);

  const label = v => v > 0 ? 'IZQUIERDA (1-28)' : (v < 0 ? 'DERECHA (29-56)' : 'EQUILIBRIO');
  const currentRegime = label(smoothed[0]);
  let changedAgo = 0;

  for (let i = 1; i < smoothed.length; i++) {
    const past = label(smoothed[i]);
    if (past !== currentRegime && past !== 'EQUILIBRIO') { changedAgo = i; break; }
  }

  return { currentRegime, changedAgo, dateShift: DATA[changedAgo] ? DATA[changedAgo][1] : 'N/A' };
}

// ── MONTECARLO CON INERCIA + FÍSICA DE ESFERAS ──
function runMonteCarloBatch(count) {
  const DATA     = getActiveData();
  const stats    = computeStats(); // calcula freq30, lastSeen, phys en un solo paso
  const { freq30, lastSeen, phys } = stats;
  const poolBase = Array.from({ length: 56 }, (_, i) => i + 1);

  // Números calientes: presentes ≥2 veces en últimos 30 sorteos y activos recientemente
  const hotNumbers = poolBase.filter(n => freq30[n] >= 2 && lastSeen[n] <= 15);

  // Top 8 con mayor ventaja aerodinámica (peso + desgaste)
  const physicsTop = poolBase
    .map(n => ({ n, bonus: getPhysicsBonus(n, phys) }))
    .sort((a, b) => b.bonus - a.bonus)
    .slice(0, 8);

  // Pool ponderado pre-calculado — reutilizado en las 5000 simulaciones
  const physicsPool = getPhysicsWeightedPool(DATA, phys);

  function pickFromPool(exclude) {
    for (let tries = 0; tries < 300; tries++) {
      const n = physicsPool[Math.floor(Math.random() * physicsPool.length)];
      if (!exclude.includes(n)) return n;
    }
    // Fallback garantizado
    const remaining = poolBase.filter(n => !exclude.includes(n));
    return remaining[Math.floor(Math.random() * remaining.length)];
  }

  const results = [];

  const iterations = ENGINE_CONFIG.montecarlo.iterations || 5000;
  for (let i = 0; i < iterations; i++) {
    const combo = [];

    // Segmento INERCIA (1 de cada 3): inyectar 2 números calientes
    if (i % 3 === 0 && hotNumbers.length >= 2) {
      const shuffHot = [...hotNumbers].sort(() => 0.5 - Math.random()); // copia — no muta original
      combo.push(shuffHot[0], shuffHot[1]);
    }

    // Segmento FÍSICA (1 de cada 3): inyectar 1-2 números más ligeros
    if (i % 3 === 1) {
      const shuffPhys = [...physicsTop].sort(() => 0.5 - Math.random());
      if (!combo.includes(shuffPhys[0].n)) combo.push(shuffPhys[0].n);
      if (shuffPhys[1] && !combo.includes(shuffPhys[1].n)) combo.push(shuffPhys[1].n);
    }

    // Completar con pool ponderado por física
    while (combo.length < 6) {
      const picked = pickFromPool(combo);
      if (picked && !combo.includes(picked)) combo.push(picked);
    }

    combo.sort((a, b) => a - b);
    const ev = evalCombo(combo);
    results.push({ nums: combo, score: ev.total_score + Math.random() * 3 });
  }

  results.sort((a, b) => b.score - a.score);

  // Deduplicar: extraer los mejores `count` únicos
  const uniqueCombos = [];
  const seen = new Set();
  for (const res of results) {
    const key = res.nums.join(',');
    if (!seen.has(key)) {
      seen.add(key);
      uniqueCombos.push(res.nums);
      if (uniqueCombos.length >= count) break;
    }
  }

  // Garantía de completitud si las 5000 sims no generaron suficientes únicos
  while (uniqueCombos.length < count) {
    const combo = [];
    while (combo.length < 6) {
      const p = pickFromPool(combo);
      if (p && !combo.includes(p)) combo.push(p);
    }
    combo.sort((a, b) => a - b);
    const key = combo.join(',');
    if (!seen.has(key)) { seen.add(key); uniqueCombos.push(combo); }
  }

  return uniqueCombos;
}

// ── PROBABILIDAD PONDERADA (modo no-Montecarlo) ──
function weightedRandom(scores, count) {
  const pool  = [...scores];
  const combo = [];
  while (combo.length < count && pool.length > 0) {
    const totalWeight = pool.reduce((acc, val) => acc + Math.max(1, val.s), 0);
    let r = Math.random() * totalWeight;
    for (let i = 0; i < pool.length; i++) {
      r -= Math.max(1, pool[i].s);
      if (r <= 0) { combo.push(pool.splice(i, 1)[0].n); break; }
    }
  }
  return combo.sort((a, b) => a - b);
}

function runEngineWorkerJob(type, payload = {}, onProgress) {
  return new Promise((resolve, reject) => {
    if (typeof Worker === 'undefined') {
      reject(new Error('Web Worker no disponible en este navegador.'));
      return;
    }

    const worker = new Worker('worker.js');
    const jobId = `${type}_${Date.now()}_${Math.random().toString(16).slice(2)}`;

    worker.onmessage = (event) => {
      const msg = event.data || {};
      if (msg.type === 'progress') {
        if (typeof onProgress === 'function') onProgress(msg);
        return;
      }
      if (msg.jobId !== jobId) return;
      worker.terminate();
      if (msg.type === 'result') resolve(msg.payload);
      else reject(new Error(msg.error || 'El worker no pudo completar el trabajo.'));
    };

    worker.onerror = (error) => {
      worker.terminate();
      reject(error);
    };

    worker.postMessage({
      ...payload,
      type,
      jobId,
      config: getEngineConfigSnapshot(),
      ballWeights: [...BALL_WEIGHTS],
      mode: CURRENT_MODE
    });
  });
}

async function runMonteCarloBatchAsync(count, onProgress) {
  const result = await runEngineWorkerJob('RUN_MONTECARLO', {
    count,
    historicalData: getActiveData()
  }, onProgress);
  return (result.combos || []).map(item => item.nums || item);
}

async function trainEngine(historicalData = getActiveData(), sorteosAtras = 12, onProgress) {
  const result = await runEngineWorkerJob('TRAIN_ENGINE', {
    historicalData,
    sorteosAtras
  }, onProgress);

  const calibration = setEngineCalibration({
    ensembleWeights: result.weights,
    confidence: result.confidence,
    chaosMode: result.chaosMode || result.DO_NOT_BET,
    mse: result.mse,
    chaosRate: result.chaosRate,
    avgHits: result.avgHits,
    updatedAt: result.updatedAt || new Date().toISOString()
  }, false);
  await saveEngineCalibration(CURRENT_MODE, calibration);
  return { ...result, calibration };
}

async function timeTravelTraining(sorteosAtras = 50, onProgress) {
  const result = await runEngineWorkerJob('TIME_TRAVEL_TRAINING', {
    historicalData: getActiveData(),
    sorteosAtras
  }, onProgress);

  const calibration = setEngineCalibration({
    ensembleWeights: result.weights,
    confidence: result.confidence,
    chaosMode: result.DO_NOT_BET || result.chaosMode,
    chaosRate: result.chaosRate,
    avgHits: result.avgHits,
    updatedAt: result.updatedAt || new Date().toISOString()
  }, false);
  await saveEngineCalibration(CURRENT_MODE, calibration);
  return { ...result, calibration };
}
