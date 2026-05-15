// ═══════════════════════════════════════════════════════
// ui.js - INTERFAZ DE USUARIO (V7.3 — Revisado)
// ═══════════════════════════════════════════════════════

let currentMapView  = 'score';
let generatedCombos = [];
let favoriteCombos  = { melate: [], revancha: [] };

// ── PERSISTENCIA EN localStorage ──
const LS_KEY_REVANCHA = 'melate_ball_weights_revancha';
const LS_KEY_MELATE   = 'melate_ball_weights_melate';
const LS_KEY_FAV_REV  = 'melate_fav_combos_revancha';
const LS_KEY_FAV_MEL  = 'melate_fav_combos_melate';

function getDefaultWeights(mode) {
  // Devuelve copia fresca de los defaults definidos en engine.js
  return mode === 'melate'
    ? [...DEFAULT_BALL_WEIGHTS_MELATE]
    : [...DEFAULT_BALL_WEIGHTS_REVANCHA];
}

function saveWeightsToStorage(mode, weights) {
  try {
    const key = mode === 'melate' ? LS_KEY_MELATE : LS_KEY_REVANCHA;
    localStorage.setItem(key, JSON.stringify(weights));
  } catch (e) {
    console.warn('No se pudo guardar en localStorage:', e);
  }
}

function loadWeightsFromStorage(mode) {
  try {
    const key = mode === 'melate' ? LS_KEY_MELATE : LS_KEY_REVANCHA;
    const raw = localStorage.getItem(key);
    if (!raw) return null;
    const arr = JSON.parse(raw);
    // Validar integridad: array de 57 elementos (índice 0 + 1-56)
    if (Array.isArray(arr) && arr.length === 57) return arr;
  } catch (e) {}
  return null;
}

function reloadWeightsForMode(mode) {
  const saved = loadWeightsFromStorage(mode);
  BALL_WEIGHTS = saved ? saved : getDefaultWeights(mode);
}

function loadFavoritesFromStorage(mode) {
  try {
    const key = mode === 'melate' ? LS_KEY_FAV_MEL : LS_KEY_FAV_REV;
    const raw = localStorage.getItem(key);
    if (!raw) return [];
    const arr = JSON.parse(raw);
    if (!Array.isArray(arr)) return [];
    return arr.filter(item => item && Array.isArray(item.nums) && item.nums.length === 6);
  } catch (e) {
    return [];
  }
}

function saveFavoritesToStorage(mode, favorites) {
  try {
    const key = mode === 'melate' ? LS_KEY_FAV_MEL : LS_KEY_FAV_REV;
    localStorage.setItem(key, JSON.stringify(favorites));
  } catch (e) {
    console.warn('No se pudo guardar favoritos:', e);
  }
}

function isComboSaved(nums) {
  const key = nums.slice().sort((a, b) => a - b).join(',');
  return favoriteCombos[CURRENT_MODE].some(item => item.nums.join(',') === key);
}

function addFavoriteCombo(nums, source = 'Generada') {
  const sorted = [...nums].sort((a, b) => a - b);
  const key = sorted.join(',');
  if (isComboSaved(sorted)) return;
  favoriteCombos[CURRENT_MODE].unshift({ nums: sorted, source, savedAt: new Date().toISOString() });
  saveFavoritesToStorage(CURRENT_MODE, favoriteCombos[CURRENT_MODE]);
  renderFavoritesPanel();
  showToast('💾 Combinación guardada en favoritos');
}

function removeFavoriteCombo(index) {
  favoriteCombos[CURRENT_MODE].splice(index, 1);
  saveFavoritesToStorage(CURRENT_MODE, favoriteCombos[CURRENT_MODE]);
  renderFavoritesPanel();
}

function loadAllFavorites() {
  favoriteCombos.melate = loadFavoritesFromStorage('melate');
  favoriteCombos.revancha = loadFavoritesFromStorage('revancha');
}

function renderFavoritesPanel() {
  const container = document.getElementById('favorites-container');
  if (!container) return;
  const favorites = favoriteCombos[CURRENT_MODE] || [];
  if (!favorites.length) {
    container.innerHTML = '<div style="color:var(--muted);font-size:13px;">Aún no tienes combinaciones guardadas. Usa el botón Guardar en cualquier combinación.</div>';
    return;
  }

  container.innerHTML = favorites.map((fav, idx) => {
    const balls = fav.nums.map(n => `<span class="ball" style="margin:0 2px;padding:8px 8px;font-size:12px;">${n}</span>`).join('');
    return `<div class="combo-card" style="border-color:rgba(255,255,255,0.08);display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
      <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;"><span style="font-size:12px;color:var(--muted);">${fav.source}</span>${balls}</div>
      <button class="btn btn-small btn-blue" onclick="removeFavoriteCombo(${idx})">Eliminar</button>
    </div>`;
  }).join('');
}

// ── UTILIDADES GRÁFICAS ──
function getStatus(ret) {
  if (ret === 0)   return ['⚡ Reciente', 'b-recent'];
  if (ret <= 2)    return ['🔴 Caliente', 'b-hot'];
  if (ret <= 5)    return ['🟡 Tibio',    'b-warm'];
  if (ret <= 10)   return ['🔵 Normal',   'b-normal'];
  if (ret <= 18)   return ['❄️ Frío',     'b-cold'];
  return           ['👻 Fantasma',        'b-ghost'];
}

function getBallClass(score) {
  if (score >= 72) return 'ball-lg s-high';
  if (score >= 55) return 'ball-lg s-mid';
  if (score >= 40) return 'ball-lg s-low';
  return 'ball-lg s-avoid';
}

function showToast(msg) {
  const t = document.getElementById('toast');
  if (!t) return;
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}

// ── LISTENERS PRINCIPALES ──
document.addEventListener('DOMContentLoaded', async () => {
  await initLocalDatabase();
  setupCsvInputHandlers();
  loadAllFavorites();

  // Cambiar Modo Melate/Revancha
  document.getElementById('game-mode')?.addEventListener('change', () => {
    CURRENT_MODE = document.getElementById('game-mode').value;
    const header = document.getElementById('main-header');
    document.getElementById('lbl-hist-mode').textContent = CURRENT_MODE.toUpperCase();
    header.className = `header ${CURRENT_MODE === 'melate' ? 'mode-melate' : ''}`;
    document.getElementById('app-title').style.color = CURRENT_MODE === 'melate' ? 'var(--red)' : 'var(--gold)';
    reloadWeightsForMode(CURRENT_MODE);
    rebuildAll();
    if (typeof renderDbStatusUI === 'function') renderDbStatusUI();
    showToast(`Modo cambiado a: ${CURRENT_MODE.toUpperCase()} — pesos cargados`);
  });

  // Navegación de Pestañas
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', (e) => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      e.target.classList.add('active');
      const targetPanel = document.getElementById('tab-' + e.target.dataset.target);
      if (targetPanel) targetPanel.classList.add('active');
      rebuildAll();
    });
  });

  // Vistas Mapa de Calor
  document.querySelectorAll('.view-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      currentMapView = e.target.dataset.view;
      document.querySelectorAll('.view-btn').forEach(b => {
        b.style.background   = 'var(--surface)';
        b.style.color        = 'var(--muted)';
        b.style.borderColor  = 'var(--border)';
      });
      e.target.style.background  = 'rgba(240,180,41,.15)';
      e.target.style.color       = 'var(--gold)';
      e.target.style.borderColor = 'var(--gold)';
      renderHeatGrid();
    });
  });

  // Botones Generador
  document.getElementById('btn-gen-5')?.addEventListener('click',  () => generateCombos(5));
  document.getElementById('btn-gen-10')?.addEventListener('click', () => generateCombos(10));
  document.getElementById('btn-clear')?.addEventListener('click',  () => { generatedCombos = []; renderCombosList(); });
  document.getElementById('btn-eval')?.addEventListener('click',   evalUserComboUI);
  document.getElementById('btn-search-coinc')?.addEventListener('click', searchCoincidencesUI);

  // Cargar pesos del modo inicial desde localStorage (o defaults)
  reloadWeightsForMode(CURRENT_MODE);
  rebuildAll();
  if (typeof renderDbStatusUI === 'function') renderDbStatusUI();
});

// ── 1. GENERADOR ──
function generateCombos(count) {
  const { numScore, freq30, lastSeen } = computeStats();
  const scores     = Array.from({ length: 56 }, (_, i) => ({ n: i + 1, s: numScore(i + 1) }));
  // CORRECCIÓN: usar spread para no mutar el array fuente en cada iteración
  const hotNumbers = Array.from({ length: 56 }, (_, i) => i + 1)
    .filter(n => freq30[n] >= 2 && lastSeen[n] <= 15);

  const useMonteCarlo = document.getElementById('strat-montecarlo')?.checked;
  const useMigration  = document.getElementById('strat-migration')?.checked;

  for (let c = 0; c < count; c++) {
    let combo = [], stratName = '';

    if (useMonteCarlo) {
      stratName = 'Montecarlo con Inercia 🤖';
      combo = runMonteCarloBatch(1)[0];
    } else {
      const pool      = [];
      const useInertia = (c % 2 === 0);

      if (useInertia && hotNumbers.length >= 2) {
        stratName = 'Inercia de Máquina 🔥';
        // CORRECCIÓN: spread antes de sort para no mutar hotNumbers
        const shuffHot = [...hotNumbers].sort(() => 0.5 - Math.random());
        pool.push(shuffHot[0], shuffHot[1]);
      } else {
        stratName = 'Balance Probabilístico ⚖️';
      }

      if (useMigration && getOppositeData().length > 0) {
        const oppDraw = getOppositeData()[0].slice(2);
        const migrants = oppDraw.map(n => ({ n, s: numScore(n) }))
          .sort((a, b) => b.s - a.s).slice(0, 1);
        if (!pool.includes(migrants[0].n)) pool.push(migrants[0].n);
        stratName += ' + Migración';
      }

      const restScores = scores.filter(x => !pool.includes(x.n));
      const chosenRest = weightedRandom(restScores, 6 - pool.length);
      combo = [...pool, ...chosenRest].sort((a, b) => a - b);
    }

    generatedCombos.unshift({ nums: combo, name: stratName });
  }
  renderCombosList();
}

function renderCombosList() {
  const c = document.getElementById('combos-container');
  if (!c) return;
  c.innerHTML = generatedCombos.map((cb, i) => {
    const ev    = evalCombo(cb.nums);
    const color = ev.total_score >= 72 ? 'var(--green)' : ev.total_score >= 55 ? 'var(--gold)' : 'var(--blue)';
    const balls = cb.nums.map(n =>
      `<div class="ball-lg" style="background:rgba(255,255,255,0.05);border:2px solid ${color};color:${color}">${n}</div>`
    ).join('');
    const savedLabel = isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
    const savedDisabled = isComboSaved(cb.nums) ? 'disabled' : '';
    return `<div class="combo-card" style="border-color:${color}40">
      <div class="combo-card-header">
        <span style="color:${color};font-weight:700">#${generatedCombos.length - i} · ${cb.name}</span>
        <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">SCORE: ${Math.round(ev.total_score)}</span>
      </div>
      <div class="combo-balls">${balls}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;margin-top:10px;">
        <div style="font-size:12px;color:var(--muted)">Suma: ${ev.suma} | P/I: ${ev.pares}P/${ev.impares}I | Décadas: ${ev.decades}</div>
        <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
      </div>
    </div>`;
  }).join('');
  document.getElementById('combo-info').textContent = `${generatedCombos.length} jugadas`;
  renderFavoritesPanel();
}

function saveGeneratedCombo(index) {
  const item = generatedCombos[index];
  if (!item) return;
  addFavoriteCombo(item.nums, item.name);
}

function saveManualComboUI(nums) {
  addFavoriteCombo(nums, 'Manual');
}

// ── 2. EVALUADOR MANUAL (RAYOS X) ──
function evalUserComboUI() {
  const inputs = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`).value));
  if (inputs.some(n => isNaN(n) || n < 1 || n > 56)) { showToast('⚠️ Ingresa 6 números válidos del 1 al 56'); return; }
  if ([...new Set(inputs)].length !== 6) { showToast('⚠️ Los 6 números deben ser distintos'); return; }

  const { numScore, lastSeen } = computeStats();
  const ev = evalCombo(inputs);
  const physicsDetails = ev.sorted.map(n => getBallPhysicsInfo(n));
  const averageEffectiveWeight = physicsDetails.reduce((sum, info) => sum + info.effectiveWeight, 0) / physicsDetails.length;
  const totalPhysicsBonus = physicsDetails.reduce((sum, info) => sum + info.bonus, 0);

  const scoreColor = ev.total_score >= 72 ? 'var(--green)' : ev.total_score >= 55 ? 'var(--gold)' : ev.total_score >= 40 ? 'var(--blue)' : 'var(--red)';
  const levelLabel = ev.total_score >= 72 ? '⭐⭐⭐ PREMIUM' : ev.total_score >= 55 ? '⭐⭐ ALTA' : ev.total_score >= 40 ? '⭐ MEDIA' : '⚠️ BAJA';

  const balls = ev.sorted.map(n =>
    `<div class="${getBallClass(numScore(n))}" title="${n}">${n}</div>`
  ).join('');

  const numDetails = ev.sorted.map(n => {
    const s = Math.round(numScore(n));
    const ret = lastSeen[n];
    const [st, bc] = getStatus(ret);
    return `<tr>
      <td><b style="color:var(--text);font-size:14px">${n}</b></td>
      <td>${n % 2 === 0 ? '<span style="color:var(--teal)">Par</span>' : '<span style="color:var(--purple)">Impar</span>'}</td>
      <td>D${Math.floor((n - 1) / 10) + 1}</td>
      <td style="color:${ret > 12 ? 'var(--purple)' : ret < 4 ? 'var(--red)' : 'var(--muted)'}">${ret}</td>
      <td><span class="badge ${bc}">${st}</span></td>
      <td><div class="score-bar"><div class="score-track"><div class="score-fill" style="width:${s}%;background:${s >= 70 ? 'var(--green)' : s >= 50 ? 'var(--gold)' : 'var(--red)'}"></div></div><span style="font-family:var(--mono);font-size:11px;color:var(--muted);width:28px">${s}</span></div></td>
    </tr>`;
  }).join('');

  document.getElementById('user-result').innerHTML = `
    <div class="card" style="margin-top:16px;border-color:${scoreColor}50;background:rgba(0,0,0,0.2);">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;">Análisis (${CURRENT_MODE.toUpperCase()})</h2>
        <span class="badge" style="background:rgba(0,0,0,.3);color:${scoreColor};border:1px solid ${scoreColor};font-size:14px;padding:6px 14px">${levelLabel} · ${Math.round(ev.total_score)}/100</span>
      </div>
      <div class="card-body">
        <div class="combo-balls" style="margin-bottom:20px">${balls}</div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;font-size:13px;color:var(--muted);margin-bottom:20px;background:var(--surface);padding:12px;border-radius:8px;border:1px solid var(--border);">
          <div>Suma: <span style="color:var(--text);font-weight:700">${ev.suma}</span></div>
          <div>Pares/Imp: <span style="color:var(--text);font-weight:700">${ev.pares}P/${ev.impares}I</span></div>
          <div>Décadas: <span style="color:var(--text);font-weight:700">${ev.decades}/6</span></div>
          <div>Consecutivos: <span style="color:var(--text);font-weight:700">${ev.consec}</span></div>
          <div>Promedio peso efectivo: <span style="color:var(--text);font-weight:700">${averageEffectiveWeight.toFixed(4)}g</span></div>
          <div>Bonus físico total: <span style="color:var(--text);font-weight:700">${totalPhysicsBonus.toFixed(1)}</span></div>
          <div style="grid-column:1/-1;font-weight:700;color:${totalPhysicsBonus < 0 ? 'var(--red)' : totalPhysicsBonus > 10 ? 'var(--green)' : 'var(--gold)'};">${totalPhysicsBonus < 0 ? 'Peso físico desfavorable' : totalPhysicsBonus > 10 ? 'Muy favorable para este combo' : 'Físicamente aceptable'}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-bottom:16px;"><button class="btn btn-teal" onclick="saveManualComboUI([${ev.sorted.join(',')}])">💾 Guardar combinación</button></div>
        <div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>P/I</th><th>Década</th><th>Retraso</th><th>Estado</th><th>Score Individual</th></tr></thead><tbody>${numDetails}</tbody></table></div>
      </div>
    </div>`;
}

// ── 3. MAPA DE CALOR DINÁMICO ──
// Siempre usa computeStats() → getActiveData() → refleja el CSV cargado
function renderHeatGrid() {
  const { freq, lastSeen, numScore } = computeStats();
  const grid   = document.getElementById('heat-grid');
  const legend = document.getElementById('heat-legend');
  if (!grid) return;

  const maxF = Math.max(...freq.slice(1));
  let html = '';

  for (let n = 1; n <= 56; n++) {
    let val, c;
    if (currentMapView === 'score') {
      val = Math.round(numScore(n));
      c   = val < 40 ? 'h0' : val < 60 ? 'h1' : val < 80 ? 'h2' : 'h3';
    } else if (currentMapView === 'freq') {
      val = freq[n];
      const ratio = maxF > 0 ? val / maxF : 0;
      c   = ratio < 0.3 ? 'h4' : ratio < 0.5 ? 'h3' : ratio < 0.7 ? 'h1' : 'h0';
    } else {
      // delay
      val = lastSeen[n];
      c   = val <= 3 ? 'h0' : val <= 7 ? 'h1' : val <= 12 ? 'h2' : val <= 20 ? 'h3' : 'h4';
    }
    html += `<div class="grid-cell ${c}"><div class="num">${n}</div><div class="sc">${val}</div></div>`;
  }

  grid.innerHTML = html;

  if (legend) {
    if (currentMapView === 'score')
      legend.innerHTML = `<span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Evitar (&lt;40)</span> <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Medio (40-59)</span> <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Recomendado (60-79)</span> <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Hot Momentum (≥80)</span>`;
    else if (currentMapView === 'freq')
      legend.innerHTML = `<span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Muy Frecuente</span> <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Frecuente</span> <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Poco frecuente</span> <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Raro</span>`;
    else
      legend.innerHTML = `<span class="h0" style="padding:2px 8px;border-radius:4px;border:1px solid var(--red);color:var(--red);font-size:11px">🔴 Salió Reciente (≤3)</span> <span class="h1" style="padding:2px 8px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);font-size:11px">🟡 Reciente (4-7)</span> <span class="h2" style="padding:2px 8px;border-radius:4px;border:1px solid var(--green);color:var(--green);font-size:11px">🟢 Moderado (8-12)</span> <span class="h3" style="padding:2px 8px;border-radius:4px;border:1px solid var(--blue);color:var(--blue);font-size:11px">🔵 Tardío (13-20)</span> <span class="h4" style="padding:2px 8px;border-radius:4px;border:1px solid var(--purple);color:var(--purple);font-size:11px">🟣 Ausente (&gt;20)</span>`;
  }
}

// ── 4. ESTADÍSTICAS Y CAMBIO DE PATRÓN ──
function renderStatsUI() {
  const DATA = getActiveData();
  if (DATA.length === 0) return;
  const { total, freq } = computeStats();
  const physics = calcPhysicsOverview();

  const statsSummary = document.getElementById('stats-summary');
  if (statsSummary) {
    statsSummary.innerHTML = `
      <div class="stat-card" style="background:rgba(57,208,194,0.08);border:1px solid var(--teal);">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">⚖️ Promedio físico</div>
        <div style="font-size:24px;font-weight:800;color:var(--gold);">${physics.avgEffective}g</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">Peso efectivo promedio por bola con desgaste</div>
      </div>
      <div class="stat-card" style="background:rgba(240,180,41,0.08);border:1px solid var(--gold);">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">🔥 Ventaja física</div>
        <div style="font-size:24px;font-weight:800;color:var(--green);">${physics.advantage}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">Bolas con ventaja de peso</div>
      </div>
      <div class="stat-card" style="background:rgba(248,81,73,0.08);border:1px solid var(--red);">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">⚠️ Desventaja física</div>
        <div style="font-size:24px;font-weight:800;color:var(--red);">${physics.disadvantage}</div>
        <div style="font-size:11px;color:var(--muted);margin-top:4px;">Bolas con peso en contra</div>
      </div>
      <div class="stat-card" style="background:rgba(255,255,255,0.04);border:1px solid var(--surface);">
        <div style="font-size:12px;color:var(--muted);margin-bottom:8px;">🏆 Top ligeras</div>
        <div style="display:flex;gap:6px;flex-wrap:wrap;">${physics.top3.map(n => `<span class="ball" style="font-size:11px;padding:6px 8px;">${n}</span>`).join('')}</div>
      </div>
    `;
  }

  // Décadas
  const decEl = document.getElementById('decade-chart');
  if (decEl) decEl.innerHTML = [[1,10],[11,20],[21,30],[31,40],[41,50],[51,56]].map(([lo, hi], di) => {
    const cnt   = Array.from({ length: hi - lo + 1 }, (_, i) => i + lo).reduce((a, n) => a + freq[n], 0);
    const pct   = cnt / (total * 6);
    const exp   = (hi - lo + 1) / 56;
    const delta = pct - exp;
    const color = Math.abs(delta) < 0.02 ? 'var(--green)' : delta > 0 ? 'var(--red)' : 'var(--blue)';
    return `<div class="decade-row"><div class="decade-label">D${di + 1} (${lo}–${hi})</div><div class="decade-bar"><div class="decade-fill" style="width:${Math.min(100, pct * 500)}%;background:${color}"></div></div><div class="decade-pct">${(pct * 100).toFixed(1)}%</div></div>`;
  }).join('');

  // Pares e Impares
  const piCounts = [0, 0, 0, 0, 0, 0, 0];
  DATA.forEach(r => { piCounts[r.slice(2).filter(n => n % 2 === 0).length]++; });
  const piEl = document.getElementById('pi-chart');
  if (piEl) piEl.innerHTML = piCounts.map((cnt, p) => {
    const color = p === 3 ? 'var(--green)' : p === 2 || p === 4 ? 'var(--gold)' : 'var(--red)';
    return `<div class="decade-row"><div class="decade-label">${p}P/${6 - p}I</div><div class="decade-bar"><div class="decade-fill" style="width:${cnt / Math.max(...piCounts) * 100}%;background:${color}"></div></div><div class="decade-pct">${(cnt / total * 100).toFixed(1)}%</div></div>`;
  }).join('');

  // Sumas
  const sumas   = DATA.map(r => r.slice(2).reduce((a, b) => a + b, 0));
  const buckets = [[21,80],[81,120],[121,160],[161,200],[201,240],[241,336]];
  const sumEl   = document.getElementById('sum-chart');
  if (sumEl) {
    const counts = buckets.map(([lo, hi]) => sumas.filter(s => s >= lo && s <= hi).length);
    const maxCnt = Math.max(...counts);
    sumEl.innerHTML = buckets.map(([lo, hi], idx) => {
      const cnt   = counts[idx];
      const color = (lo >= 121 && hi <= 240) ? 'var(--green)' : lo >= 81 ? 'var(--gold)' : 'var(--red)';
      return `<div class="decade-row"><div class="decade-label">${lo}–${hi}</div><div class="decade-bar"><div class="decade-fill" style="width:${maxCnt > 0 ? cnt / maxCnt * 100 : 0}%;background:${color}"></div></div><div class="decade-pct">${total > 0 ? (cnt / total * 100).toFixed(0) : 0}%</div></div>`;
    }).join('');
  }

  // Tendencia Izq/Der
  const trendEl = document.getElementById('trend-chart');
  if (trendEl && DATA.length >= 20) {
    let html = '';
    for (let i = 0; i < Math.min(DATA.length, 100); i += 20) {
      const chunk = DATA.slice(i, i + 20);
      if (!chunk.length) break;
      let left = 0, right = 0, tot = 0;
      chunk.forEach(r => { r.slice(2).forEach(n => { if (n <= 28) left++; else right++; tot++; }); });
      const pL  = (left  / tot) * 100;
      const pR  = (right / tot) * 100;
      const lbl = i === 0 ? 'Últimos 20 (Actual)' : 'Sorteos pasados';
      const dom  = left > right ? '◀ Izquierda (1-28)' : (right > left ? 'Derecha (29-56) ▶' : 'Equilibrio');
      const cDom = left > right ? 'var(--blue)' : (right > left ? 'var(--red)' : 'var(--teal)');
      html += `<div style="margin-bottom:14px"><div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px"><span style="color:var(--muted)">${lbl}</span><span style="color:${cDom};font-weight:bold">${dom}</span></div><div style="display:flex;height:16px;border-radius:4px;overflow:hidden;border:1px solid var(--border)"><div style="width:${pL}%;background:rgba(88,166,255,0.2);border-right:1px solid var(--blue);display:flex;align-items:center;padding-left:6px;font-size:10px;font-weight:bold;color:var(--blue)">Izq ${Math.round(pL)}%</div><div style="width:${pR}%;background:rgba(248,81,73,0.2);display:flex;justify-content:flex-end;align-items:center;padding-right:6px;font-size:10px;font-weight:bold;color:var(--red)">Der ${Math.round(pR)}%</div></div></div>`;
    }
    trendEl.innerHTML = html;
  }
}

function renderPatternShiftUI() {
  const shift     = detectPatternShift();
  const container = document.getElementById('pattern-shift-container');
  if (!container) return;
  if (!shift) { container.innerHTML = '<p style="color:var(--muted)">Datos insuficientes para detectar patrón.</p>'; return; }

  const color = shift.currentRegime.includes('IZQ') ? 'var(--blue)' : 'var(--red)';
  container.innerHTML = `
    <div style="display:flex;align-items:center;gap:16px;">
      <div style="font-size:40px;">⏱️</div>
      <div>
        <div style="font-size:14px;color:var(--muted)">Patrón de acomodo dominante actual:</div>
        <div style="font-size:22px;font-weight:800;color:${color};font-family:var(--cond)">CARGA ${shift.currentRegime}</div>
        <div style="font-size:13px;color:var(--text);margin-top:6px;">
          Este patrón lleva activo <b style="color:var(--gold)">${shift.changedAgo} sorteos</b>.
          <br><span style="color:var(--muted)">(El cambio de régimen ocurrió en el sorteo de fecha: ${shift.dateShift})</span>
        </div>
      </div>
    </div>`;
}

// ── 5. LABORATORIO FORENSE ──
function analyzeRhythmsUI() {
  const DATA      = getActiveData();
  const container = document.getElementById('ritmos-container');
  if (!container) return;

  const rhythms = [];
  for (let n = 1; n <= 56; n++) {
    const indices = [];
    for (let i = 0; i < DATA.length; i++) if (DATA[i].slice(2).includes(n)) indices.push(i);
    if (indices.length >= 3) {
      const g1 = indices[1] - indices[0];
      const g2 = indices[2] - indices[1];
      if (g1 === g2 && g1 > 0) {
        let streaks = 3;
        for (let k = 2; k < indices.length - 1; k++) {
          if (indices[k + 1] - indices[k] === g1) streaks++; else break;
        }
        rhythms.push({ num: n, gap: g1, streaks, due: g1 - (indices[0] + 1), lastSeen: indices[0] });
      }
    }
  }

  if (!rhythms.length) { container.innerHTML = '<p style="color:var(--muted)">No hay ritmos exactos detectados recientemente.</p>'; return; }

  rhythms.sort((a, b) => Math.abs(a.due) - Math.abs(b.due));
  container.innerHTML = rhythms.map(r => {
    let status = '', borderColor = 'var(--border)';
    if      (r.due === 0) { status = '🔥 ¡TOCA HOY!';                      borderColor = 'var(--red)';  }
    else if (r.due === 1) { status = '⏳ Toca en 1 sorteo';                 borderColor = 'var(--gold)'; }
    else if (r.due < 0)   { status = `⚠️ Patrón roto hace ${Math.abs(r.due)} sorteos`; }
    else                  { status = `Faltan ${r.due} sorteos`; }
    return `<div style="background:var(--surface);border:1px solid ${borderColor};padding:12px;border-radius:8px;display:flex;align-items:center;gap:12px;margin-bottom:8px;">
      <div class="ball ball-lg" style="margin:0;border-color:${borderColor};color:${borderColor === 'var(--border)' ? 'var(--text)' : borderColor}">${r.num}</div>
      <div>
        <div style="font-family:var(--cond);font-size:16px;font-weight:700;color:var(--text)">Salto exacto de ${r.gap} sorteos</div>
        <div style="font-size:12px;color:var(--muted)">Visto hace ${r.lastSeen} sorteos · Repitió ciclo ${r.streaks} veces</div>
        <div style="font-size:12px;font-weight:bold;color:${borderColor === 'var(--border)' ? 'var(--muted)' : borderColor};margin-top:4px">${status}</div>
      </div>
    </div>`;
  }).join('');
}

function analyzeForensicsUI() {
  const DATA = getActiveData();
  const seq  = {};
  const end  = new Array(10).fill(0);

  for (let i = 0; i < DATA.length - 1; i++) {
    const current = DATA[i].slice(2);
    const prev    = DATA[i + 1].slice(2);
    prev.forEach(p => {
      if (!seq[p]) seq[p] = {};
      current.forEach(c => { seq[p][c] = (seq[p][c] || 0) + 1; });
    });
    current.forEach(n => end[n % 10]++);
  }

  const seqC = document.getElementById('secuencias-container');
  if (seqC) {
    let html = '';
    Object.keys(seq).sort((a, b) => a - b).forEach(k => {
      const t = Object.entries(seq[k]).sort((a, b) => b[1] - a[1]);
      if (t.length > 0 && t[0][1] >= 2)
        html += `<div class="seq-card"><span class="seq-highlight">${k}</span> ➔ <span>${t.slice(0, 3).map(x => `<b>${x[0]}</b>(${x[1]}x)`).join(' • ')}</span></div>`;
    });
    seqC.innerHTML = html || '<p style="color:var(--muted)">No hay secuencias frecuentes.</p>';
  }

  const termC = document.getElementById('terminaciones-container');
  if (termC) termC.innerHTML = end.map((c, i) =>
    `<div style="background:var(--surface);border:1px solid var(--border);padding:10px;border-radius:8px;width:70px;text-align:center;"><div style="font-size:22px;font-weight:800;color:var(--teal)">${i}</div><div style="font-size:10px;color:var(--muted)">${c}x</div></div>`
  ).join('');
}

function renderConditionalPatternsUI() {
  const DATA = getActiveData();
  const container = document.getElementById('conditional-container');
  if (!container) return;
  if (!DATA.length) { container.innerHTML = '<p style="color:var(--muted)">No hay datos suficientes para patrones condicionales.</p>'; return; }

  const { freq } = computeStats();
  const coMap = {};
  DATA.forEach((draw) => {
    const nums = draw.slice(2);
    nums.forEach((a) => {
      coMap[a] = coMap[a] || {};
      nums.forEach((b) => {
        if (a === b) return;
        coMap[a][b] = (coMap[a][b] || 0) + 1;
      });
    });
  });

  const topSeries = Object.entries(coMap).map(([num, map]) => {
    const items = Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 3);
    return {
      num,
      freq: freq[num] || 0,
      top: items.map(([other, count]) => ({ other, count, pct: freq[num] ? (count / freq[num]) * 100 : 0 }))
    };
  }).sort((a, b) => b.freq - a.freq).slice(0, 8);

  const structureCounts = {};
  DATA.forEach(draw => {
    const decades = new Array(6).fill(0);
    draw.slice(2).forEach(n => { decades[Math.floor((n - 1) / 10)]++; });
    const key = decades.join('-');
    structureCounts[key] = (structureCounts[key] || 0) + 1;
  });

  const topStructures = Object.entries(structureCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([pattern, count]) => ({ pattern, count, pct: (count / DATA.length) * 100 }));

  container.innerHTML = `
    <div style="display:grid;gap:12px;">
      <div style="display:flex;gap:12px;flex-wrap:wrap;">
        ${topSeries.map(item => `
          <div style="flex:1 1 200px;background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px;">
            <div style="font-size:13px;color:var(--muted);margin-bottom:6px;">Número ${item.num} aparece ${item.freq} veces</div>
            <div style="font-size:14px;font-weight:800;color:var(--text);">Tendencia al salir con:</div>
            <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:8px;">${item.top.map(x => `<span style="background:rgba(57,208,194,0.12);border:1px solid var(--teal);border-radius:6px;padding:4px 8px;font-size:11px;color:var(--teal);">${x.other} (${x.count}x · ${x.pct.toFixed(0)}%)</span>`).join('')}</div>
          </div>`).join('')}
      </div>
      <div style="background:rgba(240,180,41,0.08);border:1px solid var(--gold);border-radius:10px;padding:12px;">
        <div style="font-size:13px;color:var(--muted);margin-bottom:8px;">Estructuras más frecuentes por décadas</div>
        ${topStructures.map(s => `
          <div style="display:flex;justify-content:space-between;gap:12px;margin-bottom:6px;">
            <div style="font-family:var(--mono);font-weight:700;color:var(--text);">${s.pattern}</div>
            <div style="color:var(--gold);font-weight:700;">${s.count} sorteos · ${s.pct.toFixed(1)}%</div>
          </div>
        `).join('')}
      </div>
    </div>
  `;
}

// ── 6. COINCIDENCIAS HISTÓRICAS ──
function searchCoincidencesUI() {
  const inputs = [1, 2, 3, 4, 5, 6]
    .map(i => parseInt(document.getElementById(`coinc-${i}`).value))
    .filter(n => !isNaN(n) && n >= 1 && n <= 56);

  if (inputs.length < 2) { showToast('⚠️ Ingresa al menos 2 números para buscar'); return; }

  const uniqueInputs = [...new Set(inputs)];
  const DATA    = getActiveData();
  const matches = DATA.filter(draw => uniqueInputs.every(val => draw.slice(2).includes(val)));

  const resDiv = document.getElementById('coincidencias-resultados');
  if (!matches.length) {
    resDiv.innerHTML = `<p style="color:var(--red);padding:10px;background:rgba(248,81,73,0.1);border-radius:6px;">No se encontró ningún sorteo donde salieran juntos.</p>`;
    return;
  }

  let html = `<p style="color:var(--green);margin-bottom:10px;">✅ Salieron juntos en <b>${matches.length}</b> sorteos:</p>
    <div class="tbl-wrap"><table><thead><tr><th>Sorteo</th><th>Fecha</th><th colspan="6">Números</th></tr></thead><tbody>`;
  html += matches.map(m => {
    const balls = m.slice(2).map(n =>
      `<span class="ball" style="${uniqueInputs.includes(n) ? 'background:var(--teal);color:#000;' : 'background:rgba(255,255,255,0.05);color:var(--muted);'}">${n}</span>`
    ).join('');
    return `<tr><td>${m[0]}</td><td>${m[1]}</td><td colspan="6">${balls}</td></tr>`;
  }).join('');
  resDiv.innerHTML = html + `</tbody></table></div>`;
}

function renderTopPairsUI() {
  const DATA  = getActiveData();
  const pairs = {};
  DATA.forEach(draw => {
    const nums = [...draw.slice(2)].sort((a, b) => a - b);
    for (let i = 0; i < nums.length - 1; i++)
      for (let j = i + 1; j < nums.length; j++) {
        const p = `${nums[i]}-${nums[j]}`;
        pairs[p] = (pairs[p] || 0) + 1;
      }
  });

  const topPairs = Object.entries(pairs).sort((a, b) => b[1] - a[1]).slice(0, 15);
  const container = document.getElementById('top-pairs-container');
  if (container) container.innerHTML = topPairs.map(p => {
    const [n1, n2] = p[0].split('-');
    return `<div style="background:var(--surface);border:1px solid var(--border);padding:8px 12px;border-radius:6px;display:flex;align-items:center;gap:8px;">
      <span class="ball ball-warm" style="width:24px;height:24px;font-size:11px">${n1}</span>
      <span class="ball ball-warm" style="width:24px;height:24px;font-size:11px">${n2}</span>
      <span style="color:var(--muted);font-size:11px;margin-left:4px">${p[1]} veces</span>
    </div>`;
  }).join('');
}

function renderHistory() {
  const DATA  = getActiveData();
  const tbody = document.getElementById('history-tbody');
  if (tbody) tbody.innerHTML = DATA.map(r => {
    const n = r.slice(2);
    const p = n.filter(x => x % 2 === 0).length;
    return `<tr><td>${r[0]}</td><td>${r[1]}</td><td colspan="6">${n.map(x => `<span class="ball ball-normal">${x}</span>`).join('')}</td><td>${n.reduce((a, b) => a + b, 0)}</td><td>${p}P/${6 - p}I</td></tr>`;
  }).join('');
}

// ── 7. FÍSICA DE ESFERAS ──
function calcPhysicsOverview() {
  const DATA    = getActiveData();
  const p       = _buildPhysics(DATA);
  let advantage = 0, disadvantage = 0;
  const byBonus = [];

  for (let n = 1; n <= 56; n++) {
    const bonus = getPhysicsBonus(n, p);
    if (bonus > 3)  advantage++;
    if (bonus < -3) disadvantage++;
    byBonus.push({ n, bonus });
  }

  const avgEffective = p.avgEffective.toFixed(4);
  const top3 = [...byBonus].sort((a, b) => b.bonus - a.bonus).slice(0, 3).map(x => x.n);
  return { advantage, disadvantage, top3, avgEffective };
}

function renderWeightsGrid() {
  const grid = document.getElementById('weights-grid');
  if (!grid) return;

  const violations  = validateWeights();
  const diffViol    = violations.find(v => v.type === 'diferencia');
  const physicsStats = calcPhysicsOverview();

  // Panel de validación
  const ballViolations = violations.filter(v => v.n !== null);
  const isCompliant    = violations.length === 0;

  let validHtml;
  if (!isCompliant) {
    const msgs = [];
    if (diffViol) msgs.push(`⚠️ Diferencia entre esferas: <b style="color:var(--red)">${diffViol.diff}g</b> (máx permitido: 0.30g)`);
    ballViolations.forEach(v => msgs.push(`⚠️ Bola <b>${v.n}</b>: ${v.w}g está ${v.type === 'bajo' ? 'por debajo del mínimo (4.25g)' : 'por encima del máximo (5.25g)'}`));
    validHtml = `<div style="grid-column:1/-1;background:rgba(248,81,73,0.08);border:1px solid var(--red);border-radius:8px;padding:12px 16px;margin-bottom:8px;font-size:12px;line-height:1.8;">${msgs.join('<br>')}</div>`;
  } else {
    validHtml = `<div style="grid-column:1/-1;background:rgba(63,185,80,0.07);border:1px solid var(--green);border-radius:8px;padding:10px 16px;margin-bottom:8px;font-size:12px;color:var(--green);">✅ Todos los pesos cumplen el reglamento Melate (4.25g – 5.25g, Δmáx 0.30g)</div>`;
  }

  // Panel resumen
  const summaryHtml = `
    <div style="grid-column:1/-1;display:flex;gap:12px;flex-wrap:wrap;background:rgba(57,208,194,0.05);border:1px solid var(--teal);border-radius:8px;padding:14px 18px;margin-bottom:4px;align-items:center;">
      <div style="flex:1;min-width:150px;">
        <div style="font-family:var(--cond);font-size:12px;color:var(--muted);">⚖️ Rango reglamentario</div>
        <div style="font-family:var(--mono);font-size:18px;color:var(--teal);font-weight:700;">4.25g – 5.25g</div>
        <div style="font-size:10px;color:var(--dim);">Δmáx entre esferas: 0.30g</div>
      </div>
      <div style="flex:1;min-width:130px;">
        <div style="font-family:var(--cond);font-size:12px;color:var(--muted);">🔥 Ventaja física</div>
        <div style="font-family:var(--mono);font-size:20px;color:var(--green);font-weight:700;">${physicsStats.advantage} bolas</div>
      </div>
      <div style="flex:1;min-width:130px;">
        <div style="font-family:var(--cond);font-size:12px;color:var(--muted);">🪨 Desventaja (pesadas)</div>
        <div style="font-family:var(--mono);font-size:20px;color:var(--red);font-weight:700;">${physicsStats.disadvantage} bolas</div>
      </div>
      <div style="flex:1;min-width:180px;">
        <div style="font-family:var(--cond);font-size:12px;color:var(--muted);margin-bottom:4px;">🏆 Top 3 ligeras (mayor ventaja):</div>
        <div style="display:flex;gap:6px;">${physicsStats.top3.map(n => `<div style="background:rgba(63,185,80,.15);border:1px solid var(--green);border-radius:6px;padding:4px 8px;font-family:var(--mono);font-weight:700;color:var(--green);">${n}</div>`).join('')}</div>
      </div>
      <div style="flex:1;min-width:180px;">
        <div style="font-family:var(--cond);font-size:12px;color:var(--muted);margin-bottom:4px;">📊 Peso efectivo promedio:</div>
        <div style="font-family:var(--mono);font-size:18px;color:var(--gold);font-weight:700;">${physicsStats.avgEffective}g</div>
        <div style="font-size:10px;color:var(--dim);">con desgaste acumulado</div>
      </div>
    </div>`;

  // Grid de bolas
  let html = '';
  for (let n = 1; n <= 56; n++) {
    const info        = getBallPhysicsInfo(n);
    const w           = BALL_WEIGHTS[n] || BASE_WEIGHT;
    const bonus       = info.bonus;
    const isViolating = info.violations && info.violations.length > 0;

    let borderColor, labelColor, bonusLabel;
    if (isViolating)      { borderColor = 'var(--red)';   labelColor = 'var(--red)';   bonusLabel = '⚠️'; }
    else if (bonus >= 8)  { borderColor = 'var(--green)'; labelColor = 'var(--green)'; bonusLabel = `+${bonus.toFixed(0)}`; }
    else if (bonus >= 3)  { borderColor = 'var(--teal)';  labelColor = 'var(--teal)';  bonusLabel = `+${bonus.toFixed(0)}`; }
    else if (bonus <= -8) { borderColor = 'var(--red)';   labelColor = 'var(--red)';   bonusLabel = `${bonus.toFixed(0)}`; }
    else if (bonus <= -3) { borderColor = 'var(--gold)';  labelColor = 'var(--gold)';  bonusLabel = `${bonus.toFixed(0)}`; }
    else                  { borderColor = 'var(--dim)';   labelColor = 'var(--dim)';   bonusLabel = '~0'; }

    const tooltip = `Peso nominal: ${w}g | Efectivo: ${info.effectiveWeight}g | Usos: ${info.uses} | Bonus: ${bonus > 0 ? '+' : ''}${bonus.toFixed(1)}`;

    html += `
      <div style="background:var(--surface);border:1.5px solid ${borderColor};border-radius:8px;padding:8px 4px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:4px;transition:border-color .2s;" title="${tooltip}">
        <div style="font-family:var(--mono);font-size:13px;font-weight:700;color:var(--text);">${n}</div>
        <input type="number" class="inp" id="w${n}"
          step="0.01" min="${WEIGHT_MIN}" max="${WEIGHT_MAX}"
          value="${w.toFixed(2)}"
          style="width:58px;font-size:11px;padding:3px 4px;border-color:${borderColor};color:var(--text);background:rgba(0,0,0,0.3);"
          oninput="previewBallPhysics(${n}, this.value)">
        <div id="phys-badge-${n}" style="font-size:9px;font-weight:700;font-family:var(--mono);color:${labelColor};">${bonusLabel}</div>
        <div style="font-size:9px;color:var(--muted);">${info.uses}× usado</div>
        <div style="font-size:8px;color:var(--dim);">ef: ${info.effectiveWeight}g</div>
      </div>`;
  }

  grid.innerHTML = validHtml + summaryHtml + html;
}

function previewBallPhysics(n, rawVal) {
  const val = parseFloat(rawVal);
  if (isNaN(val)) return;
  BALL_WEIGHTS[n] = val;

  const info  = getBallPhysicsInfo(n);
  const bonus = info.bonus;
  const badge = document.getElementById(`phys-badge-${n}`);
  const input = document.getElementById(`w${n}`);
  if (!badge) return;

  const outOfRange = val < WEIGHT_MIN || val > WEIGHT_MAX;
  let color = 'var(--dim)', label = '~0';

  if (outOfRange)       { color = 'var(--red)';   label = '⚠️ OOB'; }
  else if (bonus >= 8)  { color = 'var(--green)'; label = `+${bonus.toFixed(0)}`; }
  else if (bonus >= 3)  { color = 'var(--teal)';  label = `+${bonus.toFixed(0)}`; }
  else if (bonus <= -8) { color = 'var(--red)';   label = `${bonus.toFixed(0)}`; }
  else if (bonus <= -3) { color = 'var(--gold)';  label = `${bonus.toFixed(0)}`; }

  badge.style.color   = color;
  badge.textContent   = label;
  if (input) input.style.borderColor = color;
}

function saveWeightsUI() {
  let changed = 0, rejected = 0;
  for (let n = 1; n <= 56; n++) {
    const inp = document.getElementById(`w${n}`);
    if (!inp) continue;
    const val = parseFloat(inp.value);
    if (!isNaN(val) && val >= WEIGHT_MIN && val <= WEIGHT_MAX) {
      if (BALL_WEIGHTS[n] !== val) changed++;
      BALL_WEIGHTS[n] = val;
    } else if (!isNaN(val)) {
      rejected++;
    }
  }

  saveWeightsToStorage(CURRENT_MODE, BALL_WEIGHTS);

  const violations = validateWeights();
  const diffViol   = violations.find(v => v.type === 'diferencia');
  if (diffViol)
    showToast(`⚠️ Guardado (${CURRENT_MODE.toUpperCase()}) con advertencia: Δ${diffViol.diff}g supera 0.30g`);
  else if (rejected > 0)
    showToast(`⚠️ ${rejected} valores fuera de rango ignorados`);
  else
    showToast(`💾 Pesos ${CURRENT_MODE.toUpperCase()} guardados (${changed} modificadas)`);

  renderWeightsGrid();
  renderHeatGrid();
  renderCombosList();
}

function resetWeightsUI() {
  BALL_WEIGHTS = getDefaultWeights(CURRENT_MODE);
  try {
    const key = CURRENT_MODE === 'melate' ? LS_KEY_MELATE : LS_KEY_REVANCHA;
    localStorage.removeItem(key);
  } catch (e) {}
  showToast(`↩️ Pesos ${CURRENT_MODE.toUpperCase()} restablecidos a medición original.`);
  renderWeightsGrid();
  renderHeatGrid();
  renderCombosList();
}

// ── ACTUALIZACIÓN MAESTRA ──
function rebuildAll() {
  const drawCount = document.getElementById('drawCount');
  if (drawCount) drawCount.textContent = `${getActiveData().length} SORTEOS`;

  if (document.getElementById('tab-generador')?.classList.contains('active'))    { renderCombosList(); renderFavoritesPanel(); }
  if (document.getElementById('tab-historial')?.classList.contains('active'))    { renderHistory(); if (typeof renderDbStatusUI === 'function') renderDbStatusUI(); }
  if (document.getElementById('tab-mapa')?.classList.contains('active'))         renderHeatGrid();
  if (document.getElementById('tab-estadisticas')?.classList.contains('active')) { renderPatternShiftUI(); renderStatsUI(); }
  if (document.getElementById('tab-laboratorio')?.classList.contains('active'))  { analyzeRhythmsUI(); analyzeForensicsUI(); if (typeof renderConditionalPatternsUI === 'function') renderConditionalPatternsUI(); }
  if (document.getElementById('tab-coincidencias')?.classList.contains('active')) renderTopPairsUI();
  if (document.getElementById('tab-fisica')?.classList.contains('active'))       renderWeightsGrid();
}