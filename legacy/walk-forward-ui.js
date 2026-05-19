// walk-forward-ui.js - Panel Walk-Forward compatible con legacy/V2/V3.
(function () {
  'use strict';

  const RESULTS_URL = 'resultados.json';
  let cachedPythonResults = null;

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function pct(value) {
    return `${Math.round((Number(value) || 0) * 100)}%`;
  }

  function asPct(value, digits = 2) {
    const n = Number(value);
    return Number.isFinite(n) ? `${n.toFixed(digits)}` : '0.00';
  }

  function isV3(result) {
    return Boolean(result && result.score_kind === 'optuna_weighted_net_score');
  }

  async function loadPythonResults(force = false) {
    if (cachedPythonResults && !force) return cachedPythonResults;
    try {
      const response = await fetch(`${RESULTS_URL}?t=${Date.now()}`, { cache: 'no-store' });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      cachedPythonResults = await response.json();
      return cachedPythonResults;
    } catch (error) {
      console.warn('Walk-forward no pudo leer resultados.json:', error);
      cachedPythonResults = null;
      return null;
    }
  }

  function getActiveWeights(result) {
    if (isV3(result)) return result.expert_weights || result.optuna_audit?.best_weights || {};
    if (result && result.weights) return result.weights;
    if (result && result.optimized_weights) return result.optimized_weights;
    if (typeof getEngineConfigSnapshot === 'function') return getEngineConfigSnapshot().ensembleWeights;
    return { physical: 0.25, structural: 0.25, temporal: 0.35, entropy: 0.15 };
  }

  function weightLabel(key) {
    return ({
      physical: 'Físico',
      temporal: 'Temporal',
      entropy: 'Entropía',
      fourier: 'Fourier',
      bayes: 'Bayes',
      xgboost: 'XGBoost',
      lstm: 'LSTM',
      markov: 'Markov',
      structural: 'Estructura'
    })[key] || key;
  }

  function ensurePanel() {
    const combosContainer = document.getElementById('combos-container');
    if (!combosContainer) return null;
    let panel = document.getElementById('engine-calibration-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'engine-calibration-panel';
      panel.className = 'combo-card';
      panel.style.borderColor = 'rgba(57,208,194,0.35)';
      panel.style.marginBottom = '16px';
      combosContainer.parentNode.insertBefore(panel, combosContainer);
    }
    return panel;
  }

  function renderWeights(weights) {
    const entries = Object.entries(weights || {})
      .filter(([, value]) => Number.isFinite(Number(value)))
      .sort((a, b) => Number(b[1]) - Number(a[1]));
    if (!entries.length) return '<div style="color:var(--muted);font-size:12px;">Sin pesos disponibles.</div>';
    return entries.map(([key, value]) => {
      const percent = Number(value) * 100;
      return `<div style="background:rgba(255,255,255,.04);border:1px solid var(--border);border-radius:8px;padding:8px;">
        <div style="font-size:11px;color:var(--muted);">${esc(weightLabel(key))}</div>
        <div style="font-family:var(--mono);font-weight:700;color:var(--teal);">${percent.toFixed(1)}%</div>
      </div>`;
    }).join('');
  }

  function renderRows(rows) {
    if (!Array.isArray(rows) || !rows.length) return '<div style="font-size:12px;color:var(--muted);">Sin filas de validación disponibles.</div>';
    const recent = rows.slice(-8).reverse();
    return `<div class="tbl-wrap" style="max-height:230px;overflow:auto;margin-top:10px;">
      <table>
        <thead><tr><th>Sorteo</th><th>Real</th><th>Top6</th><th>Hits</th><th>Top10</th><th>MSE</th><th>KL</th></tr></thead>
        <tbody>${recent.map(row => `<tr>
          <td>${esc(row.draw_id)}</td>
          <td>${Array.isArray(row.actual) ? row.actual.join(' ') : '-'}</td>
          <td>${Array.isArray(row.predicted_top6) ? row.predicted_top6.join(' ') : '-'}</td>
          <td><b style="color:${Number(row.hits || 0) >= 3 ? 'var(--green)' : 'var(--gold)'}">${esc(row.hits ?? '-')}</b></td>
          <td>${esc(row.hits_top10 ?? '-')}</td>
          <td>${esc(row.mse ?? '-')}</td>
          <td>${esc(row.kl ?? '-')}</td>
        </tr>`).join('')}</tbody>
      </table>
    </div>`;
  }

  function renderV3Panel(result) {
    const panel = ensurePanel();
    if (!panel) return;
    const wf = result.walk_forward || {};
    const forgetting = result.historical_forgetting || {};
    const weights = getActiveWeights(result);
    const topWeight = Object.entries(weights).sort((a, b) => Number(b[1]) - Number(a[1]))[0];
    const maxScore = Number(result.max_net_score_found || 0) * 100;
    const drift = Boolean(result.drift_detected);
    const color = maxScore >= 80 && !drift ? 'var(--green)' : maxScore >= 65 ? 'var(--gold)' : 'var(--red)';

    panel.innerHTML = `
      <div class="combo-card-header">
        <span style="color:var(--purple);font-weight:700">🧬 Motor Walk-Forward V3 · ${esc(result.game_label || '')}</span>
        <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">Net score: ${asPct(maxScore, 2)}/100</span>
      </div>
      <div style="display:grid;gap:12px;">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <button class="btn btn-teal" id="btn-refresh-python-wf">↻ Actualizar desde resultados.json</button>
          <span style="font-size:12px;color:var(--muted);">OOS secuencial sin leakage · score_kind: ${esc(result.score_kind)}</span>
        </div>
        <div class="stats-grid" style="grid-template-columns:repeat(auto-fit,minmax(145px,1fr));">
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--purple)">${esc(wf.steps ?? 0)}</div><div class="stat-lbl">Folds OOS</div></div>
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--blue)">${esc(wf.avg_hits ?? 'N/A')}</div><div class="stat-lbl">Avg hits Top6</div></div>
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--green)">${esc(wf.avg_hits_top10 ?? 'N/A')}</div><div class="stat-lbl">Avg hits Top10</div></div>
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--gold)">${esc(wf.avg_mse ?? 'N/A')}</div><div class="stat-lbl">Avg MSE</div></div>
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:${drift ? 'var(--red)' : 'var(--green)'}">${drift ? 'DRIFT' : 'OK'}</div><div class="stat-lbl">Entropía</div></div>
          <div class="stat-card"><div class="stat-val" style="font-size:20px;color:var(--teal)">${Number(result.total_mc_evaluated || 0).toLocaleString('es-MX')}</div><div class="stat-lbl">MC evaluadas</div></div>
        </div>
        <div style="background:rgba(188,140,255,.08);border:1px solid rgba(188,140,255,.35);border-radius:10px;padding:12px;font-size:12px;color:var(--muted);line-height:1.55;">
          <div style="color:var(--purple);font-weight:700;margin-bottom:6px;">Audit Trail de aprendizaje</div>
          <div>${esc(result.optuna_audit?.summary || result.procedure_log || 'Sin audit trail disponible.')}</div>
          <div style="margin-top:6px;">Buffer reciente: <b style="color:var(--text)">${esc(forgetting.recent_buffer_size ?? 'N/A')}</b> · Sorteos olvidados: <b style="color:var(--text)">${esc(forgetting.discarded_old_draws ?? 0)}</b> · Dominante: <b style="color:var(--text)">${topWeight ? `${esc(weightLabel(topWeight[0]))} ${(Number(topWeight[1]) * 100).toFixed(1)}%` : 'N/A'}</b></div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:8px;">
          ${renderWeights(weights)}
        </div>
        <div id="engine-calibration-result" style="font-size:12px;color:var(--muted);">
          ${renderRows(wf.rows)}
        </div>
      </div>
    `;

    document.getElementById('btn-refresh-python-wf')?.addEventListener('click', async () => {
      const refreshed = await loadPythonResults(true);
      if (refreshed) renderCalibrationPanel(refreshed);
      if (typeof showToast === 'function') showToast('🧬 Walk-Forward V3 actualizado desde resultados.json');
    });
  }

  function renderLegacyPanel(result) {
    const panel = ensurePanel();
    if (!panel) return;

    const weights = getActiveWeights(result);
    const confidence = result && Number.isFinite(result.confidence)
      ? result.confidence
      : (typeof getSystemConfidence === 'function' ? getSystemConfidence() : 70);
    const drift = typeof detectEntropyDrift === 'function'
      ? detectEntropyDrift()
      : { kl: 0, chaosMode: false };
    const chaosMode = Boolean(result && (result.DO_NOT_BET || result.chaosMode) || drift.chaosMode);
    const color = confidence >= 70 && !chaosMode ? 'var(--green)' : confidence >= 55 ? 'var(--gold)' : 'var(--red)';

    panel.innerHTML = `
      <div class="combo-card-header">
        <span style="color:var(--teal);font-weight:700">Motor Walk-Forward Legacy</span>
        <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">Confianza: ${Math.round(confidence)}%</span>
      </div>
      <div style="display:grid;gap:10px;">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <button class="btn btn-teal" id="btn-calibrate-engine">Calibrar Motor (Backtesting JS)</button>
          <button class="btn btn-blue btn-sm" id="btn-load-python-results">Leer resultados.json</button>
          <span style="font-size:12px;color:var(--muted);">KL: ${(drift.kl || 0).toFixed(4)} ${chaosMode ? '| Modo Caos activo' : '| Régimen estable'}</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;font-size:12px;">
          ${renderWeights(weights)}
        </div>
        <div id="engine-calibration-result" style="font-size:12px;color:var(--muted);"></div>
      </div>
    `;

    document.getElementById('btn-calibrate-engine')?.addEventListener('click', calibrateEngineWalkForward);
    document.getElementById('btn-load-python-results')?.addEventListener('click', async () => {
      const py = await loadPythonResults(true);
      if (py) renderCalibrationPanel(py);
      else if (typeof showToast === 'function') showToast('No pude leer resultados.json');
    });

    if (result) {
      const target = document.getElementById('engine-calibration-result');
      if (target) {
        target.innerHTML = `Walk-forward: ${result.evaluated || result.steps || 0} pasos | aciertos promedio: ${(result.avgHits || result.avg_hits || 0).toFixed ? (result.avgHits || result.avg_hits || 0).toFixed(2) : result.avg_hits}/6`;
        if (result.DO_NOT_BET) target.innerHTML += ' | <b style="color:var(--red)">DO_NOT_BET activo</b>';
      }
    }
  }

  function renderCalibrationPanel(result) {
    if (isV3(result)) return renderV3Panel(result);
    return renderLegacyPanel(result);
  }

  async function calibrateEngineWalkForward() {
    if (typeof timeTravelTraining !== 'function') {
      const py = await loadPythonResults(true);
      if (py) {
        renderCalibrationPanel(py);
        if (typeof showToast === 'function') showToast('Usando resultados Python desde resultados.json');
        return;
      }
      alert('No se encontró timeTravelTraining ni resultados.json. Ejecuta local_cruncher_v3.py y vuelve a refrescar.');
      return;
    }
    const data = typeof getActiveData === 'function' ? getActiveData() : [];
    if (!Array.isArray(data) || data.length < 15) {
      const py = await loadPythonResults(true);
      if (py) return renderCalibrationPanel(py);
      if (typeof showToast === 'function') showToast('Se necesitan al menos 15 sorteos para calibrar.');
      return;
    }

    const lookback = Math.min(50, Math.max(6, data.length - 8));
    try {
      if (typeof showLoadingModal === 'function') showLoadingModal(true, 'Calibrando motor Walk-Forward...');
      const result = await timeTravelTraining(lookback, (progress) => {
        if (typeof updateLoadingProgress === 'function') {
          updateLoadingProgress(progress.percent || 0, `Walk-forward ${progress.percent || 0}%`);
        }
      });
      if (typeof updateLoadingProgress === 'function') updateLoadingProgress(100, 'Calibración completada');
      if (typeof showLoadingModal === 'function') showLoadingModal(false);
      renderCalibrationPanel(result);

      if (result.DO_NOT_BET || result.chaosMode || result.confidence < 70) {
        alert('Nivel de confianza bajo o Modo Caos activo. Sugerencia: NO apostar con esta calibración.');
      } else if (typeof showToast === 'function') {
        showToast(`Motor calibrado: confianza ${Math.round(result.confidence)}%`);
      }
    } catch (error) {
      if (typeof showLoadingModal === 'function') showLoadingModal(false);
      console.error(error);
      const py = await loadPythonResults(true);
      if (py) {
        renderCalibrationPanel(py);
        if (typeof showToast === 'function') showToast('Fallback: usando resultados Python V3');
        return;
      }
      alert('No se pudo calibrar el motor: ' + (error.message || error));
    }
  }

  document.addEventListener('DOMContentLoaded', async () => {
    const py = await loadPythonResults(true);
    if (py) renderCalibrationPanel(py);
    else setTimeout(() => renderCalibrationPanel(), 0);
  });
})();
