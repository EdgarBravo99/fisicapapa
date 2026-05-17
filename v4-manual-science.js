// v4-manual-science.js
// Evaluador manual V4-only: balance estructural + sugerencias múltiples por componentes.
(function () {
  'use strict';
  const labels = {physical:'física de esferas', temporal:'inercia temporal', entropy:'entropía', fourier:'Fourier', bayes:'Bayes', xgboost:'XGBoost', transformer:'Transformer', graph:'grafo', structural:'estructura', meta:'MetaStacking', lstm:'LSTM', markov:'Markov'};
  const esc = v => String(v ?? '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const num = (v, f = 0) => Number.isFinite(Number(v)) ? Number(v) : f;
  const pct = v => { const x = num(v, 0); return x > 0 && x <= 1 ? x * 100 : x; };
  const fmt = (v, d = 2) => num(v).toFixed(d);
  const label = k => labels[k] || k || 'modelo V4';

  async function results() {
    let d = null;
    try { d = window.getV4Results?.() || window.MELATE_V4_RESULTS; } catch (_) {}
    d = d || window.MELATE_V3_RESULTS;
    if (!d || (!d.number_scores && !d.manual_suggestion_seed && !d.generator_pool)) {
      const r = await fetch('resultados.json?v4science=' + Date.now(), { cache: 'no-store' });
      d = await r.json();
    }
    return normalize(d || {});
  }

  function normalize(d) {
    const m = new Map();
    const scores = d.number_scores || d.numberScores || {};
    for (let i = 1; i <= 56; i++) {
      m.set(i, { number:i, score:pct(scores[String(i)] ?? scores[i] ?? 0), winner_component_human:'score del modelo', reason:'Score leído desde resultados.json.', expert_raw:{} });
    }
    (Array.isArray(d.manual_suggestion_seed) ? d.manual_suggestion_seed : []).forEach(r => {
      const i = Number(r.number ?? r.n ?? r.ball);
      if (!Number.isFinite(i) || i < 1 || i > 56) return;
      const comp = r.winner_component || r.main_driver || r.driver || r.component;
      m.set(i, { ...m.get(i), ...r, number:i, score:pct(r.score ?? r.score_percent ?? r.net_score ?? m.get(i).score), winner_component:comp, winner_component_human:r.winner_component_human || r.main_driver_human || r.driver_human || label(comp), reason:r.reason || r.explanation || r.human_reason || 'Ranking por número del modelo V4.', expert_raw:r.expert_raw || r.expert_scores || r.experts || {} });
    });
    (Array.isArray(d.generator_pool) ? d.generator_pool : []).slice(0,150).forEach((c, idx) => {
      const cscore = pct(c.score_percent ?? c.net_score ?? c.confidence);
      (Array.isArray(c.number_explanations) ? c.number_explanations : []).forEach(e => {
        const i = Number(e.number);
        if (!Number.isFinite(i) || i < 1 || i > 56) return;
        const cur = m.get(i) || { number:i, score:0, expert_raw:{} };
        const comp = e.main_driver || e.winner_component || e.driver;
        if (num(cur.score) <= 0) cur.score = cscore * Math.max(.15, 1 - idx / 170);
        m.set(i, { ...cur, winner_component:cur.winner_component || comp, winner_component_human:cur.winner_component_human && cur.winner_component_human !== 'score del modelo' ? cur.winner_component_human : (e.main_driver_human || e.winner_component_human || label(comp)), reason:cur.reason && cur.reason !== 'Score leído desde resultados.json.' ? cur.reason : (e.reason || 'Aparece dentro del generator_pool V4.'), expert_raw:Object.keys(cur.expert_raw || {}).length ? cur.expert_raw : (e.expert_raw || {}) });
      });
    });
    const out = { ...d, model_version:'V4', numberMap:m, manual_suggestion_seed:Array.from(m.values()).sort((a,b) => num(b.score) - num(a.score)), generator_pool:Array.isArray(d.generator_pool) ? d.generator_pool : [] };
    window.MELATE_V4_RESULTS = out;
    window.MELATE_V3_RESULTS = out;
    return out;
  }

  function readNums() {
    const a = [1,2,3,4,5,6].map(i => parseInt(document.getElementById('u' + i)?.value, 10));
    if (a.some(x => Number.isNaN(x) || x < 1 || x > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(a).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return a.sort((x,y) => x-y);
  }

  function stats(a) {
    const pares = a.filter(x => x % 2 === 0).length;
    const lows = a.filter(x => x <= 28).length;
    const decades = new Set(a.map(x => Math.floor((x - 1) / 10))).size;
    const suma = a.reduce((x,y) => x+y, 0);
    const consec = a.slice(1).filter((x,i) => x - a[i] === 1).length;
    return { pares, impares:6-pares, lows, highs:6-lows, decades, suma, consec };
  }

  function sumStats() {
    let mean = 171, std = 38;
    try {
      const rows = typeof getActiveData === 'function' ? getActiveData() : [];
      const sums = rows.map(r => (r || []).slice(2).reduce((a,b) => a + Number(b || 0), 0)).filter(Number.isFinite);
      if (sums.length > 20) { mean = sums.reduce((a,b)=>a+b,0)/sums.length; std = Math.sqrt(sums.reduce((a,b)=>a+Math.pow(b-mean,2),0)/sums.length) || std; }
    } catch (_) {}
    return { mean, std };
  }

  function structure(a) {
    const s = stats(a), ss = sumStats();
    const parity = Math.max(0, 100 - Math.abs(s.pares - 3) * 24);
    const side = Math.max(0, 100 - Math.abs(s.lows - 3) * 22);
    const decade = Math.min(100, s.decades / 6 * 100);
    const sum = Math.max(0, 100 - Math.min(65, Math.abs((s.suma - ss.mean) / Math.max(1, ss.std)) * 22));
    const consecutive = Math.max(0, 100 - s.consec * 16);
    const score = parity * .24 + side * .22 + decade * .22 + sum * .22 + consecutive * .10;
    return { ...s, score, parity, side, decade, sum, consecutive };
  }

  function numberScore(a,d){ return a.reduce((z,x)=>z+num(d.numberMap.get(x)?.score),0)/6; }
  function physics(a,d){ const vals = a.map(x => d.numberMap.get(x)||{}).map(r => { const e = r.expert_raw || {}; return pct(e.physical ?? e.physics ?? e.fisica ?? (r.winner_component === 'physical' ? r.score : 0)); }).filter(x => x > 0); return vals.length ? vals.reduce((x,y)=>x+y,0)/vals.length : (d.physics_summary?.regulatory_ok === false ? 45 : 62); }
  function alignment(a,d){ const set = new Set(a); let best = {overlap:0, score:0, rank:null}; d.generator_pool.slice(0,150).forEach((c,i)=>{ const ns = (c.numbers || c.nums || c.combo || []).map(Number).filter(Number.isFinite); const ov = ns.filter(x=>set.has(x)).length; const sc = pct(c.score_percent ?? c.net_score ?? c.confidence); if (ov*18+sc > best.overlap*18+best.score) best = {overlap:ov, score:sc, rank:i+1}; }); return { ...best, value:Math.min(100, best.overlap*16 + Math.min(36, best.score*.36)) }; }
  function grade(a,d){ const ns = numberScore(a,d), st = structure(a), ph = physics(a,d), al = alignment(a,d); return { ns, st, ph, al, final: ns*.40 + st.score*.24 + ph*.16 + al.value*.20 }; }

  function support(d){ const s = Array(57).fill(0); d.generator_pool.slice(0,150).forEach(c => (c.numbers||c.nums||c.combo||[]).map(Number).forEach(x => { if (x>=1 && x<=56) s[x]++; })); return s; }
  function suggestions(a,d,g){ const cur = new Set(a), sup = support(d); const weak = a.map(x => ({n:x, score:num(d.numberMap.get(x)?.score)})).sort((x,y)=>x.score-y.score).slice(0,4); const cand = d.manual_suggestion_seed.filter(r => !cur.has(Number(r.number))).slice(0,36); const reps=[]; weak.forEach(bad => cand.forEach(good => { const add = Number(good.number); if(!Number.isFinite(add)) return; const next = a.map(x => x===bad.n ? add : x).sort((x,y)=>x-y); const ng = grade(next,d); const gain = ng.final - g.final; const total = gain + Math.min(8, sup[add]*.35) + Math.max(0, num(good.score)-bad.score)*.04; reps.push({remove:bad.n, add, next, ng, gain, support:sup[add], total, good}); })); reps.sort((x,y)=>y.total-x.total); const out=[], ua=new Set(), ur=new Set(), uk=new Set(); for(const r of reps){ if(out.length>=3) break; const k=r.next.join('-'); if(ua.has(r.add)||ur.has(r.remove)||uk.has(k)) continue; if(r.gain < -2 && r.support < 4) continue; out.push(r); ua.add(r.add); ur.add(r.remove); uk.add(k); } return out; }

  const balls = (a,c) => a.map(x => '<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid '+c+';color:'+c+'">'+x+'</div>').join('');
  const box = (t,v,c,d) => '<div style="background:rgba(255,255,255,.04);border:1px solid '+c+'66;border-radius:8px;padding:9px"><div style="font-size:11px;color:var(--muted)">'+esc(t)+'</div><div style="font-size:18px;font-weight:800;color:'+c+';font-family:var(--mono)">'+fmt(v)+'</div><div style="font-size:10px;color:var(--dim)">'+esc(d||'')+'</div></div>';
  const mini = (t,v) => '<div>'+esc(t)+'<br><b style="color:var(--text)">'+fmt(v,1)+'</b></div>';

  async function evaluate() {
    const el = document.getElementById('user-result'); if(!el) return;
    let a; try { a = readNums(); } catch(e) { if(typeof showToast === 'function') showToast('⚠️ '+e.message); return; }
    const d = await results(); const g = grade(a,d), st = g.st;
    const color = g.final >= 78 ? 'var(--green)' : g.final >= 62 ? 'var(--gold)' : 'var(--purple)';
    const rows = a.map(x => d.numberMap.get(x) || {number:x, score:0}).map(r => '<tr><td><b style="color:var(--text)">'+r.number+'</b></td><td>'+fmt(r.score)+'</td><td>'+esc(r.winner_component_human || label(r.winner_component))+'</td><td>'+esc(r.reason || 'Sin motivo disponible')+'</td></tr>').join('');
    const sug = suggestions(a,d,g).map(s => '<div class="suggestion-card top"><div style="font-weight:800;color:var(--teal);margin-bottom:8px">V4: cambiar '+s.remove+' → '+s.add+' · mejora '+(s.gain>=0?'+':'')+fmt(s.gain)+'</div><div class="suggestion-nums">'+s.next.map(x => '<div class="suggestion-num">'+x+'</div>').join('')+'</div><div class="suggestion-strategy">Nueva calificación: '+fmt(s.ng.final)+'/100 · números='+fmt(s.ng.ns)+', estructura='+fmt(s.ng.st.score)+', física='+fmt(s.ng.ph)+', alineación='+fmt(s.ng.al.value)+'. Soporte pool top150: '+s.support+'. Impulsor: '+esc(s.good.winner_component_human || label(s.good.winner_component))+'.</div><button class="btn btn-sm btn-blue" onclick="evalSuggestion(['+s.next.join(',')+'])">📊 Probar sugerencia</button></div>').join('') || '<div style="color:var(--muted)">No hay cambio claro que mejore el perfil V4 compuesto.</div>';
    el.innerHTML = '<div class="card" style="margin-top:16px;border-color:'+color+'70;background:rgba(0,0,0,.2)"><div class="card-header" style="display:flex;justify-content:space-between;align-items:center;gap:10px"><h2 style="margin:0">Evaluador Manual V4 · Ciencia de datos</h2><span class="badge" style="background:rgba(0,0,0,.3);color:'+color+';border:1px solid '+color+';font-size:14px;padding:6px 14px">CALIFICACIÓN V4 · '+fmt(g.final)+'/100</span></div><div class="card-body"><div class="combo-balls" style="margin-bottom:12px">'+balls(a,color)+'</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-bottom:14px">'+box('Score por números',g.ns,'var(--purple)','ranking por número del JSON')+box('Física de esferas',g.ph,'var(--teal)','expert_raw físico / resumen físico')+box('Balance estructural',st.score,'var(--gold)','paridad, izquierda/derecha, décadas, suma')+box('Alineación pool',g.al.value,'var(--blue)','Rank '+(g.al.rank||'N/A')+', overlap '+g.al.overlap+'/6')+'</div><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(105px,1fr));gap:6px;font-size:11px;color:var(--muted);margin-bottom:14px;background:rgba(255,255,255,.03);border:1px solid var(--border);border-radius:8px;padding:10px">'+mini('Paridad',st.parity)+mini('Izq/Der',st.side)+mini('Décadas',st.decade)+mini('Suma '+st.suma,st.sum)+mini('Consecutivos',st.consecutive)+'</div><div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Score V4</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>'+rows+'</tbody></table></div><div class="suggestion-panel"><div class="suggestion-title">💡 Sugerencias V4 por componentes</div><div class="suggestions-grid">'+sug+'</div></div></div></div>';
  }

  function install(){ window.evalUserComboUI = evaluate; window.__manualEvaluatorMode = 'v4-only-science'; }
  install(); [250,900,1800,3000].forEach(t => setTimeout(install,t));
  document.addEventListener('DOMContentLoaded', () => setTimeout(install,400));
  document.addEventListener('melate:v4-primary-loaded', () => setTimeout(install,120));
})();
