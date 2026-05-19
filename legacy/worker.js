// worker.js - Walk-forward training without data leakage.

const MAX_N = 56;
const PICK = 6;
const DEFAULT_WEIGHTS = { physical: 0.25, structural: 0.25, temporal: 0.35, entropy: 0.15 };
const DEFAULT_TRAINING = {
  topK: 10,
  boostRate: 0.05,
  explorationPenalty: 0.05,
  chaosVarianceThreshold: 0.055,
  mcIterations: 1200,
  memoryDecay: 0.9,
  hitMemoryBoost: 0.04,
  missMemoryBoost: 0.18,
  falsePositivePenalty: 0.08
};

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

function normWeights(input) {
  const w = { ...DEFAULT_WEIGHTS, ...(input || {}) };
  let total = 0;
  Object.keys(DEFAULT_WEIGHTS).forEach((k) => {
    w[k] = Math.max(0.01, Number(w[k]) || 0.01);
    total += w[k];
  });
  Object.keys(DEFAULT_WEIGHTS).forEach((k) => { w[k] /= total || 1; });
  return w;
}

function rowsOf(rows) {
  return (rows || [])
    .filter(row => Array.isArray(row) && row.length >= 8)
    .map(row => row.slice(0, 8));
}

function chronologicalRows(rows) {
  const clean = rowsOf(rows);
  if (clean.length < 2) return clean;
  return Number(clean[0][0]) > Number(clean[clean.length - 1][0]) ? clean.slice().reverse() : clean;
}

function recentFirst(rows) {
  return rows.slice().reverse();
}

function makeStats(recentData) {
  const freq = new Array(MAX_N + 1).fill(0);
  const freq15 = new Array(MAX_N + 1).fill(0);
  const lastSeen = new Array(MAX_N + 1).fill(recentData.length + 1);
  recentData.forEach((row, idx) => {
    row.slice(2).forEach((n) => {
      if (n < 1 || n > MAX_N) return;
      freq[n]++;
      if (idx < 15) freq15[n]++;
      if (lastSeen[n] === recentData.length + 1) lastSeen[n] = idx;
    });
  });
  return { total: recentData.length, freq, freq15, lastSeen };
}

function entropyDrift(stats) {
  if (stats.total < 20) return { chaosMode: false, kl: 0, confidenceFactor: 1 };
  let kl = 0;
  const recentTotal = Math.max(1, stats.freq15.reduce((a, b) => a + b, 0));
  const histTotal = Math.max(1, stats.freq.reduce((a, b) => a + b, 0));
  for (let n = 1; n <= MAX_N; n++) {
    const p = (stats.freq15[n] + 1e-6) / recentTotal;
    const q = (stats.freq[n] + 1e-6) / histTotal;
    kl += p * Math.log(p / q);
  }
  return {
    chaosMode: kl >= 0.18,
    kl,
    confidenceFactor: kl >= 0.18 ? clamp(1 - (kl / 0.54), 0.35, 0.8) : 1
  };
}

function expertScores(recentData, weights, numberMemory) {
  const stats = makeStats(recentData);
  const drift = entropyDrift(stats);
  const scores = [];
  for (let n = 1; n <= MAX_N; n++) {
    const useRate = stats.total ? stats.freq[n] / stats.total : 0;
    const gap = stats.lastSeen[n];
    const recent = stats.freq15[n];
    const physical = clamp(48 + useRate * 140 + Math.min(10, stats.freq[n] * 0.7), 0, 100);
    const structural = clamp(56 + (n <= 28 ? 2 : -2) + (n % 2 === 0 ? 1 : -1), 0, 100);
    const temporal = clamp(42 + (recent >= 2 ? 15 : 0) + (gap <= 3 ? 12 : 0) + (gap > 15 ? 16 : 0) + (gap > 25 ? 10 : 0), 0, 100);
    const entropy = clamp((70 - Math.abs(recent - (stats.freq[n] / Math.max(1, stats.total)) * 15) * 7) * drift.confidenceFactor, 0, 100);
    const blended = physical * weights.physical + structural * weights.structural + temporal * weights.temporal + entropy * weights.entropy;
    scores.push({
      n,
      score: clamp(blended * (numberMemory ? (numberMemory[n] || 1) : 1), 1, 150),
      experts: { physical, structural, temporal, entropy }
    });
  }
  return { scores, stats, drift };
}

function structuralComboScore(nums, recentData) {
  const sorted = nums.slice().sort((a, b) => a - b);
  const even = sorted.filter(n => n % 2 === 0).length;
  const low = sorted.filter(n => n <= 28).length;
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10))).size;
  const sum = sorted.reduce((a, b) => a + b, 0);
  const histSums = recentData.map(row => row.slice(2).reduce((a, b) => a + b, 0));
  const mean = histSums.length ? histSums.reduce((a, b) => a + b, 0) / histSums.length : 168;
  return clamp(100 - Math.abs(even - 3) * 12 - Math.abs(low - 3) * 10 + decades * 3 - Math.abs(sum - mean) * 0.15, 0, 100);
}

function weightedPick(pool, used) {
  const available = pool.filter(x => !used.has(x.n));
  let total = available.reduce((sum, x) => sum + x.score, 0);
  let cut = Math.random() * total;
  for (const item of available) {
    cut -= item.score;
    if (cut <= 0) return item.n;
  }
  return available.length ? available[available.length - 1].n : null;
}

function comboScore(nums, scoreMap, recentData, weights) {
  const avg = (key) => nums.reduce((sum, n) => sum + scoreMap[n].experts[key], 0) / PICK;
  const parts = {
    physical: avg('physical'),
    structural: structuralComboScore(nums, recentData),
    temporal: avg('temporal'),
    entropy: avg('entropy')
  };
  return parts.physical * weights.physical + parts.structural * weights.structural + parts.temporal * weights.temporal + parts.entropy * weights.entropy;
}

function monteCarlo(recentData, weights, options) {
  const topK = options.count || 10;
  const iterations = options.iterations || DEFAULT_TRAINING.mcIterations;
  const { scores, drift } = expertScores(recentData, weights, options.numberMemory);
  const scoreMap = {};
  scores.forEach(item => { scoreMap[item.n] = item; });
  const seen = new Set();
  const combos = [];
  for (let i = 0; i < iterations; i++) {
    const used = new Set();
    while (used.size < PICK) {
      const n = weightedPick(scores, used);
      if (!n) break;
      used.add(n);
    }
    if (used.size !== PICK) continue;
    const nums = [...used].sort((a, b) => a - b);
    const key = nums.join(',');
    if (seen.has(key)) continue;
    seen.add(key);
    combos.push({ nums, score: comboScore(nums, scoreMap, recentData, weights) });
  }
  combos.sort((a, b) => b.score - a.score);
  return { combos: combos.slice(0, topK), drift };
}

function logChoose(n, k) {
  if (k < 0 || k > n) return Number.NEGATIVE_INFINITY;
  const m = Math.min(k, n - k);
  let total = 0;
  for (let i = 1; i <= m; i++) total += Math.log(n - m + i) - Math.log(i);
  return total;
}

function hypergeom(k) {
  return Math.exp(logChoose(PICK, k) + logChoose(MAX_N - PICK, PICK - k) - logChoose(MAX_N, PICK));
}

function expectedTopBest(topK) {
  let running = 0;
  const cdf = [];
  for (let k = 0; k <= PICK; k++) {
    running += hypergeom(k);
    cdf[k] = clamp(running, 0, 1);
  }
  let expected = 0;
  for (let m = 1; m <= PICK; m++) expected += 1 - Math.pow(cdf[m - 1], topK);
  return expected;
}

function rewardExperts(scoreRows, targetNums) {
  const target = new Set(targetNums);
  const reward = { physical: 0, structural: 0, temporal: 0, entropy: 0 };
  target.forEach((n) => {
    const row = scoreRows.find(x => x.n === n);
    if (!row) return;
    Object.keys(reward).forEach((key) => { reward[key] += row.experts[key] / 100; });
  });
  Object.keys(reward).forEach((key) => { reward[key] /= Math.max(1, target.size); });
  return reward;
}

function adjustWeights(weights, reward, bestHits, cfg) {
  if (!bestHits) {
    const next = {};
    Object.keys(weights).forEach((key) => {
      next[key] = weights[key] * (1 - cfg.explorationPenalty) + 0.25 * cfg.explorationPenalty;
    });
    return { weights: normWeights(next), expert: null, reason: 'exploration_penalty' };
  }
  const expert = Object.entries(reward).sort((a, b) => b[1] - a[1])[0][0];
  return { weights: normWeights({ ...weights, [expert]: weights[expert] * (1 + cfg.boostRate) }), expert, reason: 'expert_boost' };
}

function updateMemory(memory, targetNums, bestCombo, cfg) {
  const target = new Set(targetNums);
  const predicted = new Set(bestCombo || []);
  const next = memory.map((v, i) => i === 0 ? 1 : 1 + (v - 1) * cfg.memoryDecay);
  for (let n = 1; n <= MAX_N; n++) {
    if (target.has(n) && predicted.has(n)) next[n] *= 1 + cfg.hitMemoryBoost;
    else if (target.has(n)) next[n] *= 1 + cfg.missMemoryBoost;
    else if (predicted.has(n)) next[n] *= 1 - cfg.falsePositivePenalty;
    next[n] = clamp(next[n], 0.65, 1.8);
  }
  return next;
}

function variance(values) {
  if (!values.length) return 0;
  const mean = values.reduce((a, b) => a + b, 0) / values.length;
  return values.reduce((sum, v) => sum + Math.pow(v - mean, 2), 0) / values.length;
}

function timeTravelTraining(historicalData, sorteosAtras, options = {}) {
  const chrono = chronologicalRows(historicalData);
  if (chrono.length < 12) throw new Error('Historico insuficiente para Walk-Forward.');
  const cfg = { ...DEFAULT_TRAINING, ...((options.config && options.config.training) || {}), ...(options.training || {}) };
  const topK = cfg.topK || 10;
  const start = Math.max(8, chrono.length - (Number(sorteosAtras) || 50) - 1);
  const baselineBestHits = expectedTopBest(topK);
  let weights = normWeights(options.config && options.config.ensembleWeights);
  let numberMemory = new Array(MAX_N + 1).fill(1);
  const steps = [];

  for (let t = start; t < chrono.length - 1; t++) {
    const trainingChrono = chrono.slice(0, t + 1);
    const trainingData = recentFirst(trainingChrono);
    const target = chrono[t + 1];
    const targetNums = target.slice(2);
    const mc = monteCarlo(trainingData, weights, { count: topK, iterations: cfg.mcIterations, numberMemory });
    const targetSet = new Set(targetNums);
    const hitsByCombo = mc.combos.map(item => item.nums.filter(n => targetSet.has(n)).length);
    const bestHits = hitsByCombo.length ? Math.max(...hitsByCombo) : 0;
    const bestCombo = mc.combos[hitsByCombo.indexOf(bestHits)] ? mc.combos[hitsByCombo.indexOf(bestHits)].nums : [];
    const { scores } = expertScores(trainingData, weights, numberMemory);
    const expertRewards = rewardExperts(scores, targetNums);
    const update = adjustWeights(weights, expertRewards, bestHits, cfg);
    weights = update.weights;
    numberMemory = updateMemory(numberMemory, targetNums, bestCombo, cfg);
    const error = 1 - bestHits / PICK;

    steps.push({
      t,
      trainingUntilDraw: trainingChrono[trainingChrono.length - 1][0],
      revealedDraw: target[0],
      topCombos: mc.combos,
      target: targetNums,
      bestCombo,
      hitsByCombo,
      bestHits,
      avgHits: hitsByCombo.reduce((a, b) => a + b, 0) / Math.max(1, hitsByCombo.length),
      baselineBestHits,
      liftVsBaseline: baselineBestHits > 0 ? bestHits / baselineBestHits : 1,
      error,
      expertRewards,
      winningExpert: update.expert,
      adjustmentReason: update.reason,
      weights: { ...weights },
      chaosMode: mc.drift.chaosMode,
      kl: mc.drift.kl
    });

    self.postMessage({
      type: 'progress',
      phase: 'walk-forward',
      percent: Math.round(((t - start + 1) / (chrono.length - 1 - start)) * 100),
      step: t - start + 1,
      totalSteps: chrono.length - 1 - start
    });
  }

  const last3 = steps.slice(-3);
  const recentErrors = last3.map(step => step.error);
  const errorVarianceLast3 = variance(recentErrors);
  const avgBestHits = steps.reduce((sum, step) => sum + step.bestHits, 0) / Math.max(1, steps.length);
  const last3BestHits = last3.reduce((sum, step) => sum + step.bestHits, 0) / Math.max(1, last3.length);
  const avgLiftVsBaseline = baselineBestHits > 0 ? avgBestHits / baselineBestHits : 1;
  const last3LiftVsBaseline = baselineBestHits > 0 ? last3BestHits / baselineBestHits : 1;
  const chaosRate = steps.filter(step => step.chaosMode).length / Math.max(1, steps.length);
  let confidence = clamp(
    72 +
    clamp((avgLiftVsBaseline - 1) * 22, -10, 20) +
    clamp((last3LiftVsBaseline - 1) * 12, -8, 14) +
    clamp((cfg.chaosVarianceThreshold - errorVarianceLast3) * 140, -10, 10) -
    Math.min(7, chaosRate * 7),
    40,
    92
  );
  if (avgLiftVsBaseline >= 0.75 && errorVarianceLast3 < cfg.chaosVarianceThreshold) confidence = Math.max(confidence, 70);
  const DO_NOT_BET = confidence < 70 || errorVarianceLast3 >= cfg.chaosVarianceThreshold * 2.2 || avgLiftVsBaseline < 0.75;

  return {
    weights,
    confidence,
    DO_NOT_BET,
    chaosMode: DO_NOT_BET,
    chaosRate,
    avgHits: avgBestHits,
    baselineBestHits,
    avgLiftVsBaseline,
    last3LiftVsBaseline,
    errorVarianceLast3,
    evaluated: steps.length,
    validationSteps: steps.length,
    recentErrors,
    steps,
    updatedAt: new Date().toISOString()
  };
}

self.onmessage = function (event) {
  const msg = event.data || {};
  try {
    if (msg.type === 'RUN_MONTECARLO') {
      const weights = normWeights(msg.config && msg.config.ensembleWeights);
      self.postMessage({ type: 'result', jobId: msg.jobId, payload: monteCarlo(rowsOf(msg.historicalData), weights, { count: msg.count || 5, iterations: (msg.config && msg.config.montecarlo && msg.config.montecarlo.iterations) || 5000 }) });
      return;
    }
    if (msg.type === 'TRAIN_ENGINE' || msg.type === 'TIME_TRAVEL_TRAINING') {
      self.postMessage({ type: 'result', jobId: msg.jobId, payload: timeTravelTraining(msg.historicalData, msg.sorteosAtras, msg) });
      return;
    }
    self.postMessage({ type: 'error', jobId: msg.jobId, error: 'Tipo de trabajo no soportado.' });
  } catch (error) {
    self.postMessage({ type: 'error', jobId: msg.jobId, error: error.message || String(error) });
  }
};
