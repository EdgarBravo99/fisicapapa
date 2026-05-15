// v3-manual-suggestion-diversity.js
// Corrige sugerencias repetitivas del evaluador manual V3.
// En lugar de tomar siempre el primer candidato global, enumera reemplazos,
// calcula ganancia real, soporte Monte Carlo y balance estructural.
(function () {
  'use strict';

  const originalEvalUserComboUI = window.evalUserComboUI;

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function num(value, fallback = 0) {
    const n = Number(value);
    return Number.isFinite(n) ? n : fallback;
  }

  function fmt(value, digits = 1) {
    return num(value).toFixed(digits);
  }

  function driverLabel(key) {
    return ({
      physical: 'física de esferas',
      temporal: 'inercia temporal',
      entropy: 'estabilidad de entropía',
      fourier: 'micro-ciclos Fourier',
      bayes: 'Bayes por desgaste/frecuencia',
      xgboost: 'XGBoost',
      lstm: 'memoria secuencial LSTM',
      markov: 'transición Markov',
      structural: 'estructura de combinación'
    })[key] || key || 'modelo V3';
  }

  function getData() {
    const data = typeof window.getV3Results === 'function' ? window.getV3Results() : window.MELATE_V3_RESULTS;
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  async function ensureData() {
    let data = getData();
    if (!data && typeof window.loadV3Results === 'function') data = await window.loadV3Results(false);
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  function getManualNums() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => parseInt(document.getElementById(`u${i}`)?.value, 10));
    if (nums.some(n => Number.isNaN(n) || n < 1 || n > 56)) throw new Error('Ingresa 6 números válidos del 1 al 56.');
    if (new Set(nums).size !== 6) throw new Error('Los 6 números deben ser distintos.');
    return nums.sort((a, b) => a - b);
  }

  function comboStats(nums) {
    const pares = nums.filter(n => n % 2 === 0).length;
    const lows = nums.filter(n => n <= 28).length;
    const decades = new Set(nums.map(n => Math.floor((n - 1) / 10))).size;
    const suma = nums.reduce((a, b) => a + b, 0);
    const consec = nums.slice(1).filter((n, i) => n - nums[i] === 1).length;
    return { pares, impares: 6 - pares, lows, highs: 6 - lows, decades, suma, consec };
  }

  function rowFor(data, n) {
    return data?.numberMap?.get(Number(n)) || { number: Number(n), score: 0, winner_component_human: 'sin datos', reason: 'sin explicación', expert_raw: {} };
  }

  function scoreOf(data, n) {
    return num(rowFor(data, n).score, 0);
  }

  function comboScore(data, nums) {
    return nums.reduce((acc, n) => acc + scoreOf(data, n), 0) / 6;
  }

  function structuralPenalty(nums) {
    const st = comboStats(nums);
    let penalty = 0;
    penalty += Math.abs(st.pares - 3) * 2.25;
    penalty += Math.abs(st.lows - 3) * 2.25;
    penalty += Math.max(0, 4 - st.decades) * 3.25;
    if (st.suma < 105) penalty += (105 - st.suma) / 14;
    if (st.suma > 245) penalty += (st.suma - 245) / 14;
    penalty += Math.min(3, st.consec) * 1.2;
    return penalty;
  }

  function supportMap(data) {
    const support = new Array(57).fill(0);
    const weighted = new Array(57).fill(0);
    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    pool.slice(0, 120).forEach((combo, idx) => {
      if (!Array.isArray(combo.numbers)) return;
      const w = Math.max(0.15, 1 - idx / 140);
      combo.numbers.forEach(n => {
        if (n >= 1 && n <= 56) {
          support[n] += 1;
          weighted[n] += w;
        }
      });
    });
    return { support, weighted };
  }

  function nearestPoolAlignment(data, nums) {
    const current = new Set(nums);
    const pool = Array.isArray(data.generator_pool) ? data.generator_pool : [];
    let best = { overlap: 0, score: 0 };
    pool.slice(0, 120).forEach(c => {
      if (!Array.isArray(c.numbers)) return;
      const overlap = c.numbers.filter(n => current.has(Number(n))).length;
      const score = Number.isFinite(Number(c.score_percent)) ? Number(c.score_percent) : num(c.net_score) * 100;
      if (overlap * 10 + score > best.overlap * 10 + best.score) best = { overlap, score };
    });
    return best;
  }

  function buildDeepSuggestions(nums, data) {
    const current = new Set(nums);
    const stats = comboStats(nums);
    const baseScore = comboScore(data, nums);
    const basePenalty = structuralPenalty(nums);
    const { support, weighted } = supportMap(data);

    const details = nums.map(n => ({ ...rowFor(data, n), number: n, score: scoreOf(data, n) }));
    const weak = details.slice().sort((a, b) => num(a.score) - num(b.score));
    const currentDrivers = new Set(details.map(r => r.winner_component_human || driverLabel(r.winner_component)).filter(Boolean));

    const candidates = (Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : [])
      .map(r => ({ ...r, number: Number(r.number), score: num(r.score), driver: r.winner_component_human || driverLabel(r.winner_component) }))
      .filter(r => Number.isFinite(r.number) && r.number >= 1 && r.number <= 56 && !current.has(r.number))
      .sort((a, b) => (num(b.score) + weighted[b.number] * 0.8) - (num(a.score) + weighted[a.number] * 0.8))
      .slice(0, 28);

    const replacements = [];
    for (const bad of weak.slice(0, 4)) {
      for (const good of candidates) {
        const add = Number(good.number);
        const remove = Number(bad.number);
        if (!Number.isFinite(add) || !Number.isFinite(remove) || add === remove || current.has(add)) continue;
        const next = nums.map(n => n === remove ? add : n).sort((a, b) => a - b);
        const nextScore = comboScore(data, next);
        const gain = nextScore - baseScore;
        const penaltyGain = basePenalty - structuralPenalty(next);
        const newDriver = !currentDrivers.has(good.driver) ? 2.2 : 0;
        const supportBonus = Math.min(7.5, support[add] * 0.38 + weighted[add] * 0.55);
        const rawImprovement = scoreOf(data, add) - scoreOf(data, remove);
        const alignment = nearestPoolAlignment(data, next);
        const alignmentBonus = Math.min(5.5, alignment.overlap * 0.9 + alignment.score / 80);
        const total = gain * 1.65 + penaltyGain * 0.85 + supportBonus + newDriver + alignmentBonus + Math.max(0, rawImprovement) * 0.12;
        replacements.push({
          type: gain >= 2.0 ? 'Mejora por score V3' : penaltyGain > 1.2 ? 'Balance estructural V3' : 'Alineación Monte Carlo V3',
          remove,
          add,
          next,
          nextScore,
          gain,
          penaltyGain,
          rawImprovement,
          support: support[add],
          weightedSupport: weighted[add],
          alignment,
          driver: good.driver,
          addReason: good.reason || 'sin explicación V3',
          removeDriver: bad.winner_component_human || driverLabel(bad.winner_component),
          addScore: scoreOf(data, add),
          removeScore: scoreOf(data, remove),
          total
        });
      }
    }

    replacements.sort((a, b) => b.total - a.total);

    const picked = [];
    const usedAdds = new Set();
    const usedRemoves = new Set();
    const usedKeys = new Set();

    for (const r of replacements) {
      if (picked.length >= 3) break;
      if (usedAdds.has(r.add)) continue;
      if (usedRemoves.has(r.remove)) continue;
      const key = r.next.join('-');
      if (usedKeys.has(key)) continue;
      // No recomendar cambios prácticamente neutros salvo que corrijan estructura o pool.
      if (r.gain < 0.25 && r.penaltyGain < 1.25 && r.support < 4) continue;
      picked.push(r);
      usedAdds.add(r.add);
      usedRemoves.add(r.remove);
      usedKeys.add(key);
    }

    // Si solo hay una recomendación fuerte, añade alternativas distintas al mismo número removido,
    // pero nunca repite el mismo número agregado dentro de la misma evaluación.
    if (picked.length < 2) {
      for (const r of replacements) {
        if (picked.length >= 3) break;
        if (usedAdds.has(r.add)) continue;
        const key = r.next.join('-');
        if (usedKeys.has(key)) continue;
        if (r.gain < -0.25 && r.support < 6) continue;
        picked.push(r);
        usedAdds.add(r.add);
        usedKeys.add(key);
      }
    }

    return picked.slice(0, 3).map(r => ({
      ...r,
      reason: `Cambiar ${r.remove} (${fmt(r.removeScore, 1)}/100, ${esc(r.removeDriver)}) por ${r.add} (${fmt(r.addScore, 1)}/100, ${esc(r.driver)}). Ganancia neta ${r.gain >= 0 ? '+' : ''}${fmt(r.gain, 2)} pts; soporte MC top120: ${r.support}; alineación pool: ${r.alignment.overlap}/6. ${r.addReason}`
    }));
  }

  function ballHtml(nums, color = 'var(--purple)') {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</div>`).join('');
  }

  window.evalUserComboUI = async function evalUserComboUIDiverseV3() {
    const data = await ensureData();
    if (!data) {
      if (typeof originalEvalUserComboUI === 'function') return originalEvalUserComboUI();
      if (typeof showToast === 'function') showToast('⚠️ No hay resultados V3 para evaluar');
      return;
    }

    let nums;
    try {
      nums = getManualNums();
    } catch (err) {
      if (typeof showToast === 'function') showToast(`⚠️ ${err.message}`);
      return;
    }

    const details = nums.map(n => ({ ...rowFor(data, n), number: n, score: scoreOf(data, n) }));
    const score = comboScore(data, nums);
    const stats = comboStats(nums);
    const suggestions = buildDeepSuggestions(nums, data);
    const color = score >= 80 ? 'var(--green)' : score >= 65 ? 'var(--gold)' : 'var(--purple)';
    const rows = details.map(row => `<tr>
      <td><b style="color:var(--text)">${esc(row.number)}</b></td>
      <td>${fmt(row.score, 2)}</td>
      <td>${esc(row.winner_component_human || driverLabel(row.winner_component))}</td>
      <td>${esc(row.reason || 'sin explicación')}</td>
    </tr>`).join('');

    const suggestionHtml = suggestions.length ? suggestions.map(s => `<div class="suggestion-card top">
      <div style="font-weight:700;color:var(--teal);margin-bottom:8px;">${esc(s.type)} · ${s.remove} → ${s.add}</div>
      <div class="suggestion-nums">${s.next.map(n => `<div class="suggestion-num">${n}</div>`).join('')}</div>
      <div class="suggestion-strategy">${esc(s.reason)}</div>
      <div style="font-size:11px;color:var(--muted);margin-top:6px;">Score estimado nuevo: ${fmt(s.nextScore, 2)}/100 · Cambio ${s.gain >= 0 ? '+' : ''}${fmt(s.gain, 2)} · Balance ${s.penaltyGain >= 0 ? '+' : ''}${fmt(s.penaltyGain, 2)}</div>
      <button class="btn btn-sm btn-blue" onclick="evalSuggestion([${s.next.join(',')}])">📊 Probar sugerencia</button>
    </div>`).join('') : '<div style="color:var(--muted);">No hay cambios recomendados con mejora clara frente a los datos V3 actuales.</div>';

    const resultEl = document.getElementById('user-result');
    if (!resultEl) return;
    resultEl.innerHTML = `<div class="card" style="margin-top:16px;border-color:${color}70;background:rgba(0,0,0,.2);">
      <div class="card-header" style="display:flex;justify-content:space-between;align-items:center;">
        <h2 style="margin:0;">Análisis Manual V3 · ${esc(data.game_label || '')}</h2>
        <span class="badge" style="background:rgba(0,0,0,.3);color:${color};border:1px solid ${color};font-size:14px;padding:6px 14px">NET AVG · ${fmt(score, 2)}/100</span>
      </div>
      <div class="card-body">
        <div class="combo-balls" style="margin-bottom:12px;">${ballHtml(nums, color)}</div>
        <div style="background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:10px;padding:12px;margin-bottom:14px;color:var(--muted);line-height:1.55;font-size:12px;">
          <div style="font-weight:700;color:var(--purple);margin-bottom:8px;">🧬 Lectura V3</div>
          <div>${esc(data.procedure_log || 'Sin procedure_log V3.')}</div>
          <div style="margin-top:8px;">Buffer: <b style="color:var(--text)">${esc(data.historical_forgetting?.recent_buffer_size ?? 'N/A')}</b> · MC: <b style="color:var(--text)">${Number(data.total_mc_evaluated || 0).toLocaleString('es-MX')}</b> · Max net: <b style="color:var(--text)">${fmt(Number(data.max_net_score_found || 0) * 100, 2)}/100</b></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:10px;font-size:13px;color:var(--muted);margin-bottom:14px;background:var(--surface);padding:12px;border-radius:8px;border:1px solid var(--border);">
          <div>Suma: <b style="color:var(--text)">${stats.suma}</b></div>
          <div>Pares/Imp: <b style="color:var(--text)">${stats.pares}P/${stats.impares}I</b></div>
          <div>Bajos/Altos: <b style="color:var(--text)">${stats.lows}/${stats.highs}</b></div>
          <div>Décadas: <b style="color:var(--text)">${stats.decades}/6</b></div>
        </div>
        <div class="tbl-wrap"><table><thead><tr><th>Núm</th><th>Score V3</th><th>Impulsor</th><th>Motivo</th></tr></thead><tbody>${rows}</tbody></table></div>
        <div class="suggestion-panel">
          <div class="suggestion-title">💡 Sugerencias profundas V3 diversificadas</div>
          <div style="font-size:11px;color:var(--muted);margin-bottom:10px;">Ahora se evita repetir el mismo número agregado dentro de una evaluación; si el 17 aparece en distintas jugadas, es porque en ambas supera a alternativas según score + soporte Monte Carlo + estructura.</div>
          <div class="suggestions-grid">${suggestionHtml}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;margin-top:14px;"><button class="btn btn-teal" onclick="saveManualComboUI([${nums.join(',')}])">💾 Guardar combinación</button></div>
      </div>
    </div>`;
  };
})();
