// ═══════════════════════════════════════════════════════
// engine.js - MOTOR MATEMÁTICO (V7.3 — Revisado)
// ═══════════════════════════════════════════════════════

// ── SISTEMA DE FÍSICA DE ESFERAS (REGLAMENTO MELATE) ──
const WEIGHT_MIN      = 4.25;
const WEIGHT_MAX      = 5.25;
const WEIGHT_DIFF_MAX = 0.30;
const BASE_WEIGHT     = (WEIGHT_MIN + WEIGHT_MAX) / 2; // 4.75g fallback
const WEAR_PER_USE    = 0.0008; // g perdidos por sorteo de uso

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
    effective[n] = (BALL_WEIGHTS[n] || BASE_WEIGHT) - uses[n] * WEAR_PER_USE;
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
  const wearFactor      = p.uses[n] * WEAR_PER_USE;
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

    return Math.max(0, Math.min(100, s));
  }

  return { total, freq, freq30, lastSeen, numScore, phys };
}

// ── EVALUACIÓN DE COMBINACIÓN ──
function evalCombo(nums) {
  const { numScore } = computeStats();
  const sorted  = [...nums].sort((a, b) => a - b);
  const suma    = sorted.reduce((a, b) => a + b, 0);
  const pares   = sorted.filter(n => n % 2 === 0).length;
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10)));

  let consec = 0;
  for (let i = 0; i < sorted.length - 1; i++) {
    if (sorted[i + 1] === sorted[i] + 1) consec++;
  }

  const avgScore    = nums.reduce((a, n) => a + numScore(n), 0) / 6;
  const balScore    = 20 - Math.abs(pares - 3) * 8;
  const total_score = Math.max(0, Math.min(100,
    (avgScore * 0.6) + balScore + (decades.size * 6) + (consec * 5)
  ));

  return { sorted, suma, pares, impares: 6 - pares, decades: decades.size, consec, total_score };
}

// ── SCORING AVANZADO MULTIFACTOR ──
// Calcula componentes individuales del score para análisis detallado
function computeAdvancedScore(nums) {
  const DATA = getActiveData();
  if (!DATA.length) return { total: 50, components: {}, breakdown: {} };
  
  const sorted = [...nums].sort((a, b) => a - b);
  const stats = computeStats();
  const { freq, lastSeen, numScore } = stats;
  
  // 1. SCORE FRECUENCIA: números que aparecen frecuentemente
  const freqScores = sorted.map(n => numScore(n));
  const frequencyScore = freqScores.reduce((a, b) => a + b, 0) / 6;
  
  // 2. SCORE DE RETRASO: números que llevan mucho sin salir
  const delayScores = sorted.map(n => {
    const delay = lastSeen[n];
    if (delay <= 3) return 20;
    if (delay > 25) return 60;
    if (delay > 15) return 50;
    return 30 + (delay * 1.5);
  });
  const delayScore = delayScores.reduce((a, b) => a + b, 0) / 6;
  
  // 3. SCORE DE BALANCE PAR/IMPAR
  const pares = sorted.filter(n => n % 2 === 0).length;
  const balanceScore = 80 - Math.abs(pares - 3) * 15;
  
  // 4. SCORE DE RANGO: distribución entre 1-28 y 29-56
  const lowRange = sorted.filter(n => n <= 28).length;
  const rangeScore = 100 - Math.abs(lowRange - 3) * 12;
  
  // 5. SCORE DE DISTRIBUCIÓN DE DÉCADAS
  const decades = new Set(sorted.map(n => Math.floor((n - 1) / 10)));
  const decadeScore = (decades.size / 6) * 100;
  
  // 6. SCORE DE SUMA
  const suma = sorted.reduce((a, b) => a + b, 0);
  const allSums = DATA.map(row => row.slice(2).reduce((a, b) => a + b, 0));
  const sumMean = allSums.reduce((a, b) => a + b, 0) / allSums.length;
  const sumStdDev = Math.sqrt(allSums.reduce((a, b) => a + Math.pow(b - sumMean, 2), 0) / allSums.length);
  const sumZScore = Math.abs((suma - sumMean) / sumStdDev) || 0;
  const sumScore = 100 - Math.min(50, sumZScore * 15);
  
  // 7. SCORE DE PARES FRECUENTES
  const pairScore = calculateFrequentPairScore(sorted) || 50;
  
  // 8. SCORE FÍSICO
  const physScore = sorted.reduce((acc, n) => acc + getPhysicsBonus(n, stats.phys) * 1.5, 0) / 6 + 50;
  
  // Ponderación final
  const weights = {
    frequency: 0.25,
    delay: 0.20,
    balance: 0.15,
    range: 0.12,
    decade: 0.08,
    sum: 0.12,
    pair: 0.05,
    physics: 0.03
  };
  
  const components = {
    frequency: Math.max(0, Math.min(100, frequencyScore)),
    delay: Math.max(0, Math.min(100, delayScore)),
    balance: Math.max(0, Math.min(100, balanceScore)),
    range: Math.max(0, Math.min(100, rangeScore)),
    decade: Math.max(0, Math.min(100, decadeScore)),
    sum: Math.max(0, Math.min(100, sumScore)),
    pair: Math.max(0, Math.min(100, pairScore)),
    physics: Math.max(0, Math.min(100, physScore))
  };
  
  const total = Math.round(
    components.frequency * weights.frequency +
    components.delay * weights.delay +
    components.balance * weights.balance +
    components.range * weights.range +
    components.decade * weights.decade +
    components.sum * weights.sum +
    components.pair * weights.pair +
    components.physics * weights.physics
  );
  
  return {
    total: Math.max(0, Math.min(100, total)),
    components,
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

  for (let i = 0; i < 5000; i++) {
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