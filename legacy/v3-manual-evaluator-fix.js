// v3-manual-evaluator-fix.js
// Evaluador manual V4 compacto: califica por score de números, física, estructura y alineación.
(function () {
  'use strict';

  const labels = {
    physical: 'física de esferas', temporal: 'inercia temporal', entropy: 'entropía',
    fourier: 'Fourier', bayes: 'Bayes', xgboost: 'XGBoost', transformer: 'Transformer',
    graph: 'grafo', structural: 'estructura', meta: 'MetaStacking', lstm: 'LSTM', markov: 'Markov'
  };
  const esc = v => String(v ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const num = (v, f = 0) => Number.isFinite(Number(v)) ? Number(v) : f;
  const pct = v => { const x = num(v, 0); return x > 0 && x <= 1 ? x * 100 : x; };
  const fmt = (v, d = 2) => num(v).toFixed(d);
  const label = k => labels[k] || k || 'modelo';

  async function getResults() {
    let d = null;
    try { d = window.getV4Results?.() || window.getV3Results?.(); } catch (_) {}
    d = d || window.MELATE_V4_RESULTS || window.MELATE_V3_RESULTS;
    if (!d || (!d.number_scores && !d.manual_suggestion_seed && !d.generator_pool)) {
      const r = await fetch('resultados.json?manual=' + Date.now(), { cache: 'no-store' });
      d = await r.json();
    }
    return normalize(d);
  }

  function normalize(d) {
    if (d.numberMap instanceof Map) return d;
    const m = new Map();
    const scores = d.number_scores || {};
    for (let i = 1; i <= 56; i++) {
      m.set(i, { number: i, score: pct(scores[String(i)] || scores[i] || 0), winner_component_human: 'score del modelo', reason: 'Score leído desde resultados.json.', expert_raw: {} });
    }
    (d.manual_suggestion_seed || []).forEach(r => {
      const i = Number(r.number);
      if (!Number.isFinite(i) || i < 1 || i > 56) return;
      const comp = r.winner_component || r.main_driver || r.driver;
      m.set(i, { ...m.get(i), ...r, number: i, score: pct(r.score ?? r.score_percent ?? r.net_score ?? m.get(i).score), winner_component_human: r.winner_component_human || r.main_driver_human || label(comp), reason: r.reason || r.explanation || 'Ranking por número del modelo.', expert_raw: r.expert_raw || r.experts || {} });
    });
    d.numberMap = m;
    d.manual_suggestion_seed = Array.from(m.values()).sort((a, b) => num(b.score) - num(a.score));
    window.MELATE_V4_RESULTS = d;
    window.MELATE_V3_RESULTS = d;
    return d;
  }

  function readNums() {
    const a = [1,2,3,4,5,6].map(i => parseInt(document.getElementById('u' + i)?.value, 10));
    if (a.some(x => Number.isNaN(x) || x < 1 || x > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(a).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return a.sort((x, y) => x - y);
  }

  function stats(a) {
    const pares = a.filter(x => x % 2 === 0).length;
    const lows = a.filter(x => x <= 28).length;
    const decades = new Set(a.map(x => Math.floor((x - 1) / 10))).size;
    const suma = a.reduce((x, y) => x + y, 0);
    const consec = a.slice(1).filter((x, i) => x - a[i] === 1).length;
    return { pares, impares: 6 - pares, lows, highs: 6 - lows, decades, suma, consec };
  }

  function structure(a) {
    const s = stats(a);
    const parity = Math.max(0, 100 - Math.abs(s.pares - 3) * 24);
    const side = Math.max(0, 100 - Math.abs(s.lows - 3) * 22);
    const decade = Math.min(100, s.decades / 6 * 100);
    const sum = Math.max(0, 100 - Math.min(65, Math.abs(s.suma - 171) / 38 * 22));
    const consecutive = Math.max(0, 100 - s.consec * 16);
    const score = parity * .24 + side * .22 + decade * .22 + sum * .22 + consecutive * .10;
    return { ...s, score, parity, side, decade, sum, consecutive };
  }

  function numberScore(a, d) {
    return a.reduce((z, x) => z + num(d.numberMap.get(x)?.score), 0) / 6;
  }

  function physics(a, d) {
    const vals = a.map(x => d.numberMap.get(x) || {}).map(r => {
      const e = r.expert_raw || {};
      return pct(e.physical ?? e.physics ?? (r.winner_component === 'physical' ? r.score : 0));
    }).filter(x => x > 0);
    return vals.length ? vals.reduce((x, y) => x + y, 0) / vals.length : (d.physics_summary?.regulatory_ok === false ? 45 : 62);
  }

  function alignment(a, d) {
    const set = new Set(a);
    let best = { overlap: 0, score: 0, rank: null };
    (d.generator_pool || []).slice(0, 150).forEach((c, i) => {
      const nums = (c.numbers || c.nums || c.combo || []).map(Number);
      const overlap = nums.filter(x => set.has(x)).length;
      const sc = pct(c.score_percent ?? c.net_score ?? c.confidence);
      if (overlap * 18 + sc > best.overlap * 18 + best.score) best = { overlap, score: sc, rank: i + 1 };
    });
    return { ...best, value: Math.min(100, best.overlap * 16 + Math.min(36, best.score * .36)) };
  }

  function grade(a, d) {
    const ns = numberScore(a, d), st = structure(a), ph = physics(a, d), al = alignment(a, d);
    return { ns, st, ph, al, final: ns * .40 + st.score * .24 + ph * .16 + al.value * .20 };
  }

  function balls(a, color) {
    return a.map(x => '<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ' + color + ';color:' + color + '">' + x + '</div>').join('');
  }

  function box(t, v, color, detail) {
    return '<div style="background:rgba(255,255,255,.04);border:1px solid ' + color + '66;border-radius:8px;padding:9px"><div style="font-size:11px;color:var(--muted)">' + esc(t) + '</div><div style="font-size:18px;font-weight:800;color:' + color + ';font-family:var(--mono)">' + fmt(v) + '</div><div style="font-size:10px;color:var(--dim)">' + esc(detail || '') + '</div></div>';
  }

  async function evalManualV4() {
    const el = document.getElementById('user-result');
    if (!el) return;
    let a;
    try { a = readNums(); } catch (e) { if (typeof showToast === 'function') showToast('⚠️ ' + e.message); return; }
    const d = await getResults();
    const g = grade(a, d);
    const color = g.final >= 78 ? 'var(--green)' : g.final >= 62 ? 'var(--gold)' : 'var(--purple)';
    const rows = a.map(x => d.numberMap.get(x) || { number: x, score: 0 }).map(r => '<tr><td><b style="color:var(--text)">' + r.number + '</b></td><td>' + fmt(r.score) + '</td><td>' + esc(r.winner_component_human || label(r.winner_component)) + '</td><td>' + esc(r.reason || 'Sin motivo disponible') + '</td></tr>').join('');
    const top = (d.manual_suggestion_seed || []).filter(r => !a.includes(Number(r.number))).slice(0, 3).map(r => '<div class="suggestion-card top"><div style="font-weight:800;color:var(--teal)">Candidato V4 ' + r.number + ' · ' + fmt(r.score) + '/100</div><div class="suggestion-strategy">Impulsor: ' + esc(r.winner_component_human || label(r.winner_component)) + '. ' + esc(r.reason || '') + '</div></div>').join('');
    el.innerHTML = '<div class="card" style="margin-top:16px;border-color:' + color + '70;background:rgba(0,0,0,.2)"><div class="card-header" style="display:flex;justify-content:space-between;align-items:center;gap:10px"><h2 style="margin:0">Evaluador Manual V4 · Componentes reales</h2><span class="badge" style="background:rgba(0,0,0,.3);color:' + color + ';border:1px solid ' + color + ';font-size:14px;padding:6px 14px">CALIFICACIÓN V4 · ' + fmt(g.final) + '/100</span></div><div class="card-body"><div class="combo-balls" style="margin-bottom:12px">' + balls(a, color) + '</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px">' + box('Score por números', g.ns, 'var(--purple)', 'number_scores / ranking por número') + box('Física de esferas', g.ph, 'var(--teal)', 'patrón físico del JSON') + box('Estructura', g.st.score, 'var(--gold)', 'P/I ' + g.st.pares + '/' + g.st.impares + ', Izq/Der ' + g.st.lows + '/' + g.st.highs) + box('Alineación pool', g.al.value, 'var(--blue)', 'Rank ' + (g.al.rank || 'N/A') + ', overlap ' + g.al.overlap + '/6') + '</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(110px,1fr));gap:6px;font-size:11px;color:var(--muted);margin-bottom:14px"><div>Paridad<br><b style="color:var(--text)">' + fmt(g.st.parity,1) + '</b></div><div>Izq/Der<br><b style="color:var(--text)">' + fmt(g.st.side,1) + '</b></div><div>Décadas<br><b style="color:var(--text)">' + fmt(g.st.decade,1) + '</b></div><div>Suma ' + g.st.suma + '<br><b style="color:var(--text)">' + fmt(g.st.sum,1) + '</b></div><div>Consecutivos<br><b style="color:var(--text)">' + fmt(g.st.consecutive,1) + '</b></div></div><div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Score</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>' + rows + '</tbody></table></div><div class="suggestion-panel"><div class="suggestion-title">💡 Candidatos fuertes V4 del JSON</div><div class="suggestions-grid">' + top + '</div></div></div></div>';
  }

  function installV4Evaluator() {
    window.evalUserComboUI = evalManualV4;
    window.__manualEvaluatorMode = 'v4-components';
  }

  installV4Evaluator();
  setTimeout(installV4Evaluator, 250);
  setTimeout(installV4Evaluator, 900);
  setTimeout(installV4Evaluator, 1800);
  document.addEventListener('DOMContentLoaded', () => setTimeout(installV4Evaluator, 400));
  document.addEventListener('melate:v3-results-loaded', () => setTimeout(installV4Evaluator, 120));
  document.addEventListener('melate:v4-primary-loaded', () => setTimeout(installV4Evaluator, 120));
})();
