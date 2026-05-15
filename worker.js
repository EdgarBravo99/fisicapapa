// worker.js - Motor pesado de Montecarlo y backtesting.
// Recibe snapshots simples desde la UI para no depender del hilo principal.

const NUMBER_MAX = 56;
const COMBO_SIZE = 6;
const BASE_WEIGHT = 4.75;

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
  }
};

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function normalizeWeights(weights) {
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

function mergeConfig(config) {
  return {
    sigmoidWear: { ...DEFAULT_ENGINE_CONFIG.sigmoidWear, ...(config && config.sigmoidWear) },
    entropy: { ...DEFAULT_ENGINE_CONFIG.entropy, ...(config && config.entropy) },
    montecarlo: { ...DEFAULT_ENGINE_CONFIG.montecarlo, ...(config && config.montecarlo) },
    ensembleWeights: normalizeWeights(config && config.ensembleWeights)
  };
}

function normalizeRows(rows) {
  return (rows || [])
    .filter(row => Array.isArray(row) && row.length >= 8)
    .map(row => row.slice(0, 8));
}

function normalizeChronologicalRows(rows) {
  const clean = normalizeRows(rows);
  if (clean.length < 2) return clean;
  const first = Number(clean[0][0]);
  const last = Number(clean[clean.length - 1][0]);
  return Number.isFinite(first) && Number.isFinite(last) && first > last
    ? clean.slice().reverse()
    : clean;
}

function toRecentFirst(chronologicalRows) {
  return chronologicalRows.slice().reverse();
}

function sigmoidWear(useCount, params) {
  const p = { ...DEFAULT_ENGINE_CONFIG.sigmoidWear, ...(params || {}) };
  return p.L + ((p.K - p.L) / (1 + Math.exp(-p.r * (useCount - p.n0))));
}

function buildPhysics(data, ballWeights, config) {
  const weights = Array.isArray(ballWeights) && ballWeights.length >= 57 ? ballWeights : [];
  const uses = new Array(NUMBER_MAX + 1).fill(0);
  data.forEach(row => row.slice(2).forEach((n) => {
    if (n >= 1 && n <= NUMBER_MAX) uses[n]++;
  }));

  const effective = new Array(NUMBER_MAX + 1).fill(0);
  let sumEffective = 0;
  for (let n = 1; n <= NUMBER_MAX; n++) {
    const baseWeight = weights[n] || BASE_WEIGHT;
    effective[n] = baseWeight - sigmoidWear(uses[n], config.sigmoidWear);
    sumEffective += effective[n];
  }
  return { uses, effective, avgEffective: sumEffective / NUMBER_MAX };
}

function frequencyDistribution(data, smoothing) {
  const counts = new Array(NUMBER_MAX + 1).fill(smoothing);
  let total = smoothing * NUMBER_MAX;
  data.forEach(row => row.slice(2).forEach((n) => {
    if (n >= 1 && n <= NUMBER_MAX) {
      counts[n]++;
      total++;
    }
  }));
  return counts.map(value => value / total);
}

function shannonEntropy(dist) {
  let entropy = 0;
  for (let n = 1; n <= NUMBER_MAX; n++) {
    const p = dist[n] || 0;
    if (p > 0) entropy -= p * Math.log2(p);
  }
  return entropy;
}

function klDivergence(p, q) {
  let kl = 0;
  for (let n = 1; n <= NUMBER_MAX; n++) {
    if (p[n] > 0 && q[n] > 0) kl += p[n] * Math.log(p[n] / q[n]);
  }
  return kl;
}

function detectEntropyDrift(data, config) {
  const opts = config.entropy;
  if (!data || data.length < opts.windowSize + 5) {
    return { chaosMode: false, kl: 0, recentEntropy: 0, historicalEntropy: 0, confidenceFactor: 1 };
  }
  const recent = data.slice(0, opts.windowSize);
  const hist = data;
  const recentDist = frequencyDistribution(recent, opts.smoothing);
  const histDist = frequencyDistribution(hist, opts.smoothing);
  const kl = klDivergence(recentDist, histDist);
  const chaosMode = kl >= opts.klThreshold;
  return {
    chaosMode,
    kl,
    recentEntropy: shannonEntropy(recentDist),
    historicalEntropy: shannonEntropy(histDist),
    confidenceFactor: chaosMode ? clamp(1 - (kl / (opts.klThreshold * 3)), 0.35, 0.8) : 1
  };
}

function computeStats(data, ballWeights, config) {
  const total = data.length;
  const freq = new Array(NUMBER_MAX + 1).fill(0);
  const freq30 = new Array(NUMBER_MAX + 1).fill(0);
  const lastSeen = new Array(NUMBER_MAX + 1).fill(total);

  data.forEach((row, i) => row.slice(2).forEach((n) => {
    if (n < 1 || n > NUMBER_MAX) return;
    freq[n]++;
    if (i < 30) freq30[n]++;
    if (lastSeen[n] === total) lastSeen[n] = i;
  }));

  const phys = buildPhysics(data, ballWeights, config);
  const entropy = detectEntropyDrift(data, config);
  return { total, freq, freq30, lastSeen, phys, entropy };
}

function physicsBonus(n, stats, ballWeights) {
  if (!stats.total) return 0;
  const weight = (ballWeights && ballWeights[n]) || BASE_WEIGHT;
  const deltaWeight = stats.phys.effective[n] - stats.phys.avgEffective;
  let bonus = -(deltaWeight / 0.05) * 6;
  const useRate = stats.phys.uses[n] / stats.total;
  if (useRate > 0.40) bonus += 10;
  else if (useRate > 0.30) bonus += 5;
  if (weight > BASE_WEIGHT + 0.15) bonus -= 5;
  return clamp(bonus, -15, 20);
}

function structuralScore(combo, data) {
  const sorted = [...combo].sort((a, b) => a - b);
  const pares = sorted.filter(n => n % 2 === 0).length;
  const lowRange = sorted.filter(n => n <= 28).length;
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10))).size;
  const suma = sorted.reduce((acc, n) => acc + n, 0);
  const allSums = data.map(row => row.slice(2).reduce((acc, n) => acc + n, 0));
  const mean = allSums.length ? allSums.reduce((a, b) => a + b, 0) / allSums.length : 168;
  const variance = allSums.length ? allSums.reduce((a, b) => a + Math.pow(b - mean, 2), 0) / allSums.length : 1;
  const z = Math.abs((suma - mean) / (Math.sqrt(variance) || 1));
  const parityScore = 100 - Math.abs(pares - 3) * 18;
  const rangeScore = 100 - Math.abs(lowRange - 3) * 14;
  const decadeScore = (decades / 6) * 100;
  const sumScore = 100 - Math.min(60, z * 18);
  return clamp((parityScore * 0.25) + (rangeScore * 0.25) + (decadeScore * 0.25) + (sumScore * 0.25), 0, 100);
}

function numberExpertScores(data, ballWeights, config) {
  const stats = computeStats(data, ballWeights, config);
  const expected = 6 / NUMBER_MAX;
  const histDist = frequencyDistribution(data, config.entropy.smoothing);
  const recentDist = frequencyDistribution(data.slice(0, config.entropy.windowSize), config.entropy.smoothing);
  const experts = {
    physical: new Array(NUMBER_MAX + 1).fill(50),
    structural: new Array(NUMBER_MAX + 1).fill(50),
    temporal: new Array(NUMBER_MAX + 1).fill(50),
    entropy: new Array(NUMBER_MAX + 1).fill(50)
  };

  for (let n = 1; n <= NUMBER_MAX; n++) {
    const f = stats.total ? stats.freq[n] / stats.total : expected;
    const ret = stats.lastSeen[n];
    const recent = stats.freq30[n];
    experts.physical[n] = clamp(50 + physicsBonus(n, stats, ballWeights) * 1.9, 0, 100);
    experts.temporal[n] = clamp(
      42 +
      (recent >= 3 ? 18 : 0) +
      (ret <= 3 ? 12 : 0) +
      (ret > 15 ? 16 : 0) +
      (ret > 25 ? 10 : 0) +
      ((f - expected) / expected) * 8,
      0,
      100
    );
    experts.structural[n] = clamp(55 + (n <= 28 ? 2 : -2) + ((n % 2 === 0) ? 1 : -1), 0, 100);
    const ratio = histDist[n] > 0 ? recentDist[n] / histDist[n] : 1;
    experts.entropy[n] = clamp(70 - Math.abs(Math.log(ratio || 1)) * 18, 0, 100);
  }

  return { experts, stats };
}

function comboExpertScores(combo, data, ballWeights, config) {
  const { experts, stats } = numberExpertScores(data, ballWeights, config);
  const avg = key => combo.reduce((acc, n) => acc + experts[key][n], 0) / COMBO_SIZE;
  return {
    physical: avg('physical'),
    structural: structuralScore(combo, data),
    temporal: avg('temporal'),
    entropy: avg('entropy') * stats.entropy.confidenceFactor,
    entropyMeta: stats.entropy
  };
}

function ensembleScore(combo, data, ballWeights, config) {
  const weights = normalizeWeights(config.ensembleWeights);
  const expert = comboExpertScores(combo, data, ballWeights, config);
  const total = (
    expert.physical * weights.physical +
    expert.structural * weights.structural +
    expert.temporal * weights.temporal +
    expert.entropy * weights.entropy
  );
  return { total: clamp(total, 0, 100), components: expert, weights };
}

function weightedPick(items, used) {
  const available = items.filter(item => !used.has(item.n));
  const total = available.reduce((acc, item) => acc + Math.max(1, item.score), 0);
  let r = Math.random() * total;
  for (const item of available) {
    r -= Math.max(1, item.score);
    if (r <= 0) return item.n;
  }
  return available.length ? available[available.length - 1].n : null;
}

function runMonteCarlo(data, options) {
  const config = mergeConfig(options.config);
  const count = options.count || 5;
  const iterations = options.iterations || config.montecarlo.iterations;
  const ballWeights = options.ballWeights || [];
  const { experts, stats } = numberExpertScores(data, ballWeights, config);
  const candidates = [];

  for (let n = 1; n <= NUMBER_MAX; n++) {
    const blended =
      experts.physical[n] * config.ensembleWeights.physical +
      experts.structural[n] * config.ensembleWeights.structural +
      experts.temporal[n] * config.ensembleWeights.temporal +
      experts.entropy[n] * config.ensembleWeights.entropy;
    candidates.push({ n, score: clamp(blended, 1, 100) });
  }

  const results = [];
  const seen = new Set();
  for (let i = 0; i < iterations; i++) {
    const used = new Set();
    while (used.size < COMBO_SIZE) {
      const pick = weightedPick(candidates, used);
      if (!pick) break;
      used.add(pick);
    }
    if (used.size !== COMBO_SIZE) continue;
    const nums = [...used].sort((a, b) => a - b);
    const key = nums.join(',');
    if (seen.has(key)) continue;
    seen.add(key);
    const scored = ensembleScore(nums, data, ballWeights, config);
    results.push({ nums, score: scored.total, components: scored.components });

    if (i % 250 === 0) {
      self.postMessage({ type: 'progress', phase: 'montecarlo', percent: Math.round((i / iterations) * 100) });
    }
  }

  results.sort((a, b) => b.score - a.score);
  return {
    combos: results.slice(0, count),
    entropy: stats.entropy,
    confidence: clamp(100 * stats.entropy.confidenceFactor, 0, 100)
  };
}

function scoresToDistribution(scores) {
  const shifted = new Array(NUMBER_MAX + 1).fill(0);
  let total = 0;
  for (let n = 1; n <= NUMBER_MAX; n++) {
    shifted[n] = Math.max(1, scores[n] || 1);
    total += shifted[n];
  }
  for (let n = 1; n <= NUMBER_MAX; n++) shifted[n] /= total || 1;
  return shifted;
}

function mseForDistribution(dist, actualNums) {
  const actual = new Set(actualNums);
  let mse = 0;
  for (let n = 1; n <= NUMBER_MAX; n++) {
    const y = actual.has(n) ? 1 / COMBO_SIZE : 0;
    mse += Math.pow((dist[n] || 0) - y, 2);
  }
  return mse / NUMBER_MAX;
}

function topNumbersFromWeights(experts, weights) {
  const rows = [];
  for (let n = 1; n <= NUMBER_MAX; n++) {
    rows.push({
      n,
      score:
        experts.physical[n] * weights.physical +
        experts.structural[n] * weights.structural +
        experts.temporal[n] * weights.temporal +
        experts.entropy[n] * weights.entropy
    });
  }
  return rows.sort((a, b) => b.score - a.score).slice(0, COMBO_SIZE).map(x => x.n);
}

function variance(values) {
  if (!values.length) return 0;
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  return values.reduce((acc, value) => acc + Math.pow(value - avg, 2), 0) / values.length;
}

function rewardScoreForExperts(experts, actualNums) {
  const actual = new Set(actualNums);
  const rewards = {};
  Object.keys(DEFAULT_ENGINE_CONFIG.ensembleWeights).forEach((key) => {
    let signal = 0;
    actual.forEach((n) => { signal += (experts[key][n] || 0) / 100; });
    rewards[key] = signal / Math.max(1, actual.size);
  });
  return rewards;
}

function adjustEnsembleWeights(currentWeights, rewardScore, options = {}) {
  const cfg = { ...DEFAULT_ENGINE_CONFIG.training, ...(options || {}) };
  const weights = normalizeWeights(currentWeights);
  const rewards = rewardScore.experts || {};
  const entries = Object.entries(rewards).sort((a, b) => b[1] - a[1]);
  const bestExpert = entries.length ? entries[0][0] : null;

  if ((rewardScore.bestHits || 0) === 0) {
    const uniform = 1 / Object.keys(weights).length;
    const penalized = {};
    Object.keys(weights).forEach((key) => {
      penalized[key] = weights[key] * (1 - cfg.explorationPenalty) + uniform * cfg.explorationPenalty;
    });
    return { weights: normalizeWeights(penalized), bestExpert: null, reason: 'exploration_penalty' };
  }

  if (!bestExpert) {
    return { weights, bestExpert: null, reason: 'no_reward' };
  }

  // Recompensa multiplicativa: el experto con mayor correlacion contra t+1 recibe +5%.
  // Luego normalizamos, lo que reduce proporcionalmente el resto y conserva suma = 1.
  const boosted = { ...weights, [bestExpert]: weights[bestExpert] * (1 + cfg.boostRate) };
  return { weights: normalizeWeights(boosted), bestExpert, reason: 'expert_boost' };
}

function timeTravelTrainingLocal(historicalData, sorteosAtras, options) {
  const chronological = normalizeChronologicalRows(historicalData);
  const baseConfig = mergeConfig(options.config);
  const trainingCfg = { ...DEFAULT_ENGINE_CONFIG.training, ...(options.config && options.config.training), ...(options.training || {}) };
  const ballWeights = options.ballWeights || [];
  const validationWindow = clamp(Number(sorteosAtras) || trainingCfg.sorteosAtras || 50, 3, Math.max(3, chronological.length - 2));
  const startIndex = Math.max(8, chronological.length - validationWindow - 1);
  let weights = normalizeWeights(baseConfig.ensembleWeights);
  const steps = [];
  const recentErrors = [];

  for (let t = startIndex; t < chronological.length - 1; t++) {
    const trainingChrono = chronological.slice(0, t + 1);
    const target = chronological[t + 1];
    const targetNums = target.slice(2);
    const trainingRecentFirst = toRecentFirst(trainingChrono);
    const stepConfig = mergeConfig({ ...baseConfig, ensembleWeights: weights });
    const topResult = runMonteCarlo(trainingRecentFirst, {
      config: stepConfig,
      count: trainingCfg.topK || 10,
      iterations: trainingCfg.mcIterations || Math.min(4500, stepConfig.montecarlo.iterations),
      ballWeights
    });
    const { experts, stats } = numberExpertScores(trainingRecentFirst, ballWeights, stepConfig);
    const actualSet = new Set(targetNums);
    const topCombos = topResult.combos.slice(0, trainingCfg.topK || 10);
    const hitsByCombo = topCombos.map(item => item.nums.filter(n => actualSet.has(n)).length);
    const bestHits = hitsByCombo.length ? Math.max(...hitsByCombo) : 0;
    const avgHits = hitsByCombo.length ? hitsByCombo.reduce((a, b) => a + b, 0) / hitsByCombo.length : 0;
    const error = 1 - (bestHits / COMBO_SIZE);
    const expertRewards = rewardScoreForExperts(experts, targetNums);
    const adjustment = adjustEnsembleWeights(weights, { experts: expertRewards, bestHits, avgHits, error }, trainingCfg);
    weights = adjustment.weights;
    recentErrors.push(error);
    if (recentErrors.length > 3) recentErrors.shift();

    steps.push({
      t,
      trainingUntilDraw: trainingChrono[trainingChrono.length - 1][0],
      revealedDraw: target[0],
      topCombos,
      target: targetNums,
      hitsByCombo,
      bestHits,
      avgHits,
      error,
      expertRewards,
      winningExpert: adjustment.bestExpert,
      adjustmentReason: adjustment.reason,
      weights: { ...weights },
      chaosMode: stats.entropy.chaosMode,
      kl: stats.entropy.kl
    });

    self.postMessage({
      type: 'progress',
      phase: 'walk-forward',
      percent: Math.round(((t - startIndex + 1) / (chronological.length - 1 - startIndex)) * 100),
      step: t - startIndex + 1,
      totalSteps: chronological.length - 1 - startIndex
    });
  }

  const last3Errors = steps.slice(-3).map(step => step.error);
  const errorVarianceLast3 = variance(last3Errors);
  const avgBestHits = steps.length ? steps.reduce((acc, step) => acc + step.bestHits, 0) / steps.length : 0;
  const chaosRate = steps.length ? steps.filter(step => step.chaosMode).length / steps.length : 0;
  const confidence = clamp(35 + avgBestHits * 12 - chaosRate * 20 - errorVarianceLast3 * 120, 5, 95);
  const DO_NOT_BET = errorVarianceLast3 >= trainingCfg.chaosVarianceThreshold || confidence < 70 || chaosRate > 0.45;

  return {
    weights,
    confidence,
    DO_NOT_BET,
    chaosMode: DO_NOT_BET,
    chaosRate,
    avgHits: avgBestHits,
    errorVarianceLast3,
    evaluated: steps.length,
    validationSteps: steps.length,
    steps,
    recentErrors: last3Errors,
    updatedAt: new Date().toISOString()
  };
}

function trainEngineLocal(historicalData, sorteosAtras, options) {
  const data = normalizeRows(historicalData);
  const config = mergeConfig(options.config);
  const ballWeights = options.ballWeights || [];
  const maxSteps = clamp(Number(sorteosAtras) || 12, 3, Math.max(3, data.length - 8));
  const errors = { physical: 0, structural: 0, temporal: 0, entropy: 0 };
  let ensembleError = 0;
  let chaosCount = 0;
  let hitTotal = 0;
  let evaluated = 0;

  for (let offset = maxSteps; offset >= 1; offset--) {
    const trainData = data.slice(offset);
    const actual = data[offset - 1] ? data[offset - 1].slice(2) : [];
    if (trainData.length < 8 || actual.length !== COMBO_SIZE) continue;

    const { experts, stats } = numberExpertScores(trainData, ballWeights, config);
    if (stats.entropy.chaosMode) chaosCount++;

    Object.keys(errors).forEach((key) => {
      const dist = scoresToDistribution(experts[key]);
      errors[key] += mseForDistribution(dist, actual);
    });

    const predicted = topNumbersFromWeights(experts, config.ensembleWeights);
    const actualSet = new Set(actual);
    hitTotal += predicted.filter(n => actualSet.has(n)).length;
    const ensembleScores = new Array(NUMBER_MAX + 1).fill(0);
    for (let n = 1; n <= NUMBER_MAX; n++) {
      ensembleScores[n] =
        experts.physical[n] * config.ensembleWeights.physical +
        experts.structural[n] * config.ensembleWeights.structural +
        experts.temporal[n] * config.ensembleWeights.temporal +
        experts.entropy[n] * config.ensembleWeights.entropy;
    }
    ensembleError += mseForDistribution(scoresToDistribution(ensembleScores), actual);
    evaluated++;

    self.postMessage({
      type: 'progress',
      phase: 'training',
      percent: Math.round(((maxSteps - offset + 1) / maxSteps) * 100)
    });
  }

  if (!evaluated) {
    return {
      weights: config.ensembleWeights,
      mse: errors,
      confidence: 50,
      chaosMode: false,
      evaluated: 0
    };
  }

  Object.keys(errors).forEach((key) => { errors[key] /= evaluated; });
  ensembleError /= evaluated;

  const inverse = {};
  let inverseTotal = 0;
  Object.keys(errors).forEach((key) => {
    inverse[key] = 1 / Math.max(errors[key], 1e-9);
    inverseTotal += inverse[key];
  });

  const learned = {};
  Object.keys(inverse).forEach((key) => {
    learned[key] = inverse[key] / inverseTotal;
  });

  const oldWeights = config.ensembleWeights;
  let weights = normalizeWeights({
    physical: oldWeights.physical * 0.35 + learned.physical * 0.65,
    structural: oldWeights.structural * 0.35 + learned.structural * 0.65,
    temporal: oldWeights.temporal * 0.35 + learned.temporal * 0.65,
    entropy: oldWeights.entropy * 0.35 + learned.entropy * 0.65
  });

  const chaosRate = chaosCount / evaluated;
  if (chaosRate > 0.35) {
    weights = normalizeWeights({
      ...weights,
      entropy: weights.entropy * 1.25,
      temporal: weights.temporal * 0.85
    });
  }

  const avgHits = hitTotal / evaluated;
  const confidence = clamp(42 + avgHits * 12 - chaosRate * 22 - Math.min(15, ensembleError * 2000), 5, 95);

  return {
    weights,
    mse: errors,
    ensembleMse: ensembleError,
    confidence,
    chaosMode: chaosRate > 0.35,
    chaosRate,
    avgHits,
    evaluated,
    updatedAt: new Date().toISOString()
  };
}

self.onmessage = function (event) {
  const msg = event.data || {};
  try {
    if (msg.type === 'RUN_MONTECARLO') {
      const result = runMonteCarlo(normalizeRows(msg.historicalData), msg);
      self.postMessage({ type: 'result', jobId: msg.jobId, payload: result });
      return;
    }

    if (msg.type === 'TRAIN_ENGINE') {
      const result = timeTravelTrainingLocal(msg.historicalData, msg.sorteosAtras, msg);
      self.postMessage({ type: 'result', jobId: msg.jobId, payload: result });
      return;
    }

    if (msg.type === 'TIME_TRAVEL_TRAINING') {
      const result = timeTravelTrainingLocal(msg.historicalData, msg.sorteosAtras, msg);
      self.postMessage({ type: 'result', jobId: msg.jobId, payload: result });
      return;
    }

    self.postMessage({ type: 'error', jobId: msg.jobId, error: 'Tipo de trabajo no soportado.' });
  } catch (error) {
    self.postMessage({ type: 'error', jobId: msg.jobId, error: error && error.message ? error.message : String(error) });
  }
};
