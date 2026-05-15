// Compatibilidad V3: adapta resultados.json de local_cruncher_v3.py al Generador sin tocar otras pestañas.
(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  let v3Results = null;
  let cursor = 0;

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

  function scorePercent(item) {
    if (Number.isFinite(Number(item?.score_percent))) return Number(item.score_percent);
    if (Number.isFinite(Number(item?.net_score))) return Number(item.net_score) * 100;
    if (Number.isFinite(Number(item?.confidence))) return Number(item.confidence);
    return 0;
  }

  function fmt(value, digits = 1) {
    return num(value).toFixed(digits);
  }

  async function loadV3(force = false) {
    if (v3Results && !force) return v3Results;
    try {
      const res = await fetch(`${RESULTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      v3Results = {
        ...data,
        generator_pool: Array.isArray(data.generator_pool) ? data.generator_pool : [],
        manual_suggestion_seed: Array.isArray(data.manual_suggestion_seed) ? data.manual_suggestion_seed : [],
        walk_forward: data.walk_forward || {}
      };
      renderV3Panel();
      return v3Results;
    } catch (err) {
      console.warn('V3 compat no pudo leer resultados.json:', err);
      return null;
    }
  }

  function ensurePanel() {
    const body = document.querySelector('#tab-generador .card .card-body');
    if (!body) return null;
    let panel = document.getElementById('v3-sequential-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'v3-sequential-panel';
      panel.style.margin = '0 0 16px 0';
      const combos = document.getElementById('combos-container');
      body.insertBefore(panel, combos || body.firstChild);
    }
    return panel;
  }

  function renderV3Panel() {
    const panel = ensurePanel();
    if (!panel || !v3Results) return;
    const wf = v3Results.walk_forward || {};
    const forgetting = v3Results.historical_forgetting || {};
    const weights = v3Results.expert_weights || v3Results.optuna_audit?.best_weights || {};
    const sortedWeights = Object.entries(weights).sort((a, b) => Number(b[1]) - Number(a[1])).slice(0, 4);
    const maxScore = Number(v3Results.max_net_score_found || 0) * 100;
    const recent = Array.isArray(wf.rows) ? wf.rows.slice(-5).reverse() : [];

    panel.innerHTML = `<div style="background:linear-gradient(135deg, rgba(188,140,255,.12), rgba(57,208,194,.08));border:1px solid rgba(188,140,255,.35);border-radius:10px;padding:14px;">
      <div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:flex-start;">
        <div>
          <div style="color:var(--purple);font-family:var(--cond);font-size:16px;font-weight:700;">🧬 Motor Secuencial V3 · ${esc(v3Results.game_label || '')}</div>
          <div style="font-size:12px;color:var(--muted);line-height:1.55;max-width:820px;">
            ${esc(v3Results.procedure_log || 'Sin procedimiento V3.')}
          </div>
        </div>
        <button class="btn btn-sm btn-teal" id="v3-refresh-btn">↻ Refrescar V3</button>
      </div>
      <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(135px,1fr));margin-top:12px;">
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--purple)">${fmt(maxScore, 2)}</div><div class="stat-lbl">Max net score</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${Number(v3Results.total_mc_evaluated || 0).toLocaleString('es-MX')}</div><div class="stat-lbl">MC evaluadas</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(forgetting.recent_buffer_size ?? 'N/A')}</div><div class="stat-lbl">Buffer reciente</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--red)">${esc(forgetting.discarded_old_draws ?? '0')}</div><div class="stat-lbl">Sorteos olvidados</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--blue)">${esc(wf.avg_hits ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top6</div></div>
        <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--green)">${esc(wf.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">OOS avg Top10</div></div>
      </div>
      <div style="margin-top:10px;font-size:12px;color:var(--muted);">
        <b style="color:var(--text);">Pesos Optuna:</b>
        ${sortedWeights.map(([k, v]) => `<span style="margin-right:10px;">${esc(k)}=${(Number(v) * 100).toFixed(1)}%</span>`).join('')}
      </div>
      ${recent.length ? `<div class="tbl-wrap" style="margin-top:10px;max-height:160px;overflow:auto;"><table><thead><tr><th>Sorteo</th><th>Hits</th><th>Top10</th><th>MSE</th></tr></thead><tbody>${recent.map(r => `<tr><td>${esc(r.draw_id)}</td><td>${esc(r.hits)}</td><td>${esc(r.hits_top10)}</td><td>${esc(r.mse)}</td></tr>`).join('')}</tbody></table></div>` : ''}
    </div>`;

    const btn = document.getElementById('v3-refresh-btn');
    if (btn) btn.onclick = async () => {
      await loadV3(true);
      if (typeof showToast === 'function') showToast('🧬 V3 recargado desde resultados.json');
    };
  }

  function normalizeV3Combo(item) {
    const sp = scorePercent(item);
    return {
      nums: Array.isArray(item?.numbers) ? item.numbers.map(Number).sort((a, b) => a - b) : [],
      name: `V3 ${item?.game_label || 'Python'} · ${sp.toFixed(2)}/100`,
      confidence: sp,
      procedure: item?.human_explanation || item?.procedure || item?.plain_route || 'Generado por local_cruncher_v3.py',
      source: 'sequential_gpu_montecarlo_v3',
      metrics: item || {}
    };
  }

  function takeV3Combos(count) {
    if (!v3Results?.generator_pool?.length) return [];
    const out = [];
    for (let i = 0; i < count; i++) {
      out.push(normalizeV3Combo(v3Results.generator_pool[cursor % v3Results.generator_pool.length]));
      cursor += 1;
    }
    return out;
  }

  function ballHtml(nums) {
    return nums.map(n => `<div class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid var(--purple);color:var(--purple)">${esc(n)}</div>`).join('');
  }

  const fallbackGenerate = window.generateCombos;
  window.generateCombos = async function generateCombosV3Aware(count) {
    const data = await loadV3(true);
    const combos = data?.score_kind === 'optuna_weighted_net_score' ? takeV3Combos(count) : [];
    if (combos.length) {
      generatedCombos.unshift(...combos);
      renderCombosList();
      if (typeof showToast === 'function') showToast(`🧬 ${combos.length} combinaciones V3 cargadas`);
      return;
    }
    return typeof fallbackGenerate === 'function' ? fallbackGenerate(count) : undefined;
  };

  const fallbackRender = window.renderCombosList;
  window.renderCombosList = function renderCombosV3Aware() {
    const container = document.getElementById('combos-container');
    if (!container) return;
    const hasV3 = generatedCombos.some(c => c.source === 'sequential_gpu_montecarlo_v3');
    if (!hasV3) return typeof fallbackRender === 'function' ? fallbackRender() : undefined;

    container.innerHTML = generatedCombos.map((cb, i) => {
      if (cb.source !== 'sequential_gpu_montecarlo_v3') return '';
      const ev = typeof evalCombo === 'function' ? evalCombo(cb.nums) : { suma: cb.nums.reduce((a, b) => a + b, 0), pares: cb.nums.filter(n => n % 2 === 0).length, impares: 0, decades: '-' };
      const score = Number(cb.confidence || 0);
      const color = score >= 80 ? 'var(--green)' : score >= 65 ? 'var(--gold)' : 'var(--purple)';
      const savedLabel = typeof isComboSaved === 'function' && isComboSaved(cb.nums) ? 'Guardado' : 'Guardar';
      const savedDisabled = savedLabel === 'Guardado' ? 'disabled' : '';
      return `<div class="combo-card" style="border-color:${color}70">
        <div class="combo-card-header">
          <span style="color:${color};font-weight:700">#${generatedCombos.length - i} · ${esc(cb.name)}</span>
          <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">NET SCORE: ${score.toFixed(2)}</span>
        </div>
        <div class="combo-balls">${ballHtml(cb.nums)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;">Suma: ${ev.suma} | P/I: ${ev.pares}P/${ev.impares}I | Décadas: ${ev.decades}</div>
        <div style="margin-top:10px;background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:8px;padding:10px;font-size:12px;color:var(--muted);line-height:1.55;">
          <div style="color:var(--purple);font-weight:700;margin-bottom:6px;">🧬 Explicación V3</div>
          <div>${esc(cb.procedure)}</div>
          <div style="margin-top:8px;color:var(--dim);">${esc(cb.metrics?.plain_route || '')}</div>
        </div>
        <div style="display:flex;justify-content:flex-end;gap:8px;margin-top:10px;">
          <button class="btn btn-sm btn-blue" onclick="window.evalPythonComboFromGenerated && window.evalPythonComboFromGenerated(${i})">📊 Explicar</button>
          <button class="btn btn-sm btn-teal" onclick="saveGeneratedCombo(${i})" ${savedDisabled}>${savedLabel}</button>
        </div>
      </div>`;
    }).join('');
    if (typeof renderFavoritesPanel === 'function') renderFavoritesPanel();
  };

  document.addEventListener('DOMContentLoaded', () => loadV3(true));
})();
