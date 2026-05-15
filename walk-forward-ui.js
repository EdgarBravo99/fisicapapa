// walk-forward-ui.js - Add-on de calibracion Walk-Forward para la UI legacy.
(function () {
  'use strict';

  function pct(value) {
    return `${Math.round((Number(value) || 0) * 100)}%`;
  }

  function getActiveWeights(result) {
    if (result && result.weights) return result.weights;
    if (typeof getEngineConfigSnapshot === 'function') return getEngineConfigSnapshot().ensembleWeights;
    return { physical: 0.25, structural: 0.25, temporal: 0.35, entropy: 0.15 };
  }

  function renderCalibrationPanel(result) {
    const combosContainer = document.getElementById('combos-container');
    if (!combosContainer) return;

    let panel = document.getElementById('engine-calibration-panel');
    if (!panel) {
      panel = document.createElement('div');
      panel.id = 'engine-calibration-panel';
      panel.className = 'combo-card';
      panel.style.borderColor = 'rgba(57,208,194,0.35)';
      panel.style.marginBottom = '16px';
      combosContainer.parentNode.insertBefore(panel, combosContainer);
    }

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
        <span style="color:var(--teal);font-weight:700">Motor Walk-Forward</span>
        <span style="background:${color}30;padding:4px 8px;border-radius:4px;color:${color};font-family:var(--mono)">Confianza: ${Math.round(confidence)}%</span>
      </div>
      <div style="display:grid;gap:10px;">
        <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;">
          <button class="btn btn-teal" id="btn-calibrate-engine">Calibrar Motor (Backtesting)</button>
          <span style="font-size:12px;color:var(--muted);">KL: ${(drift.kl || 0).toFixed(4)} ${chaosMode ? '| Modo Caos activo' : '| Regimen estable'}</span>
        </div>
        <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:8px;font-size:12px;">
          <div>Physical <b style="color:var(--teal)">${pct(weights.physical)}</b></div>
          <div>Structural <b style="color:var(--blue)">${pct(weights.structural)}</b></div>
          <div>Temporal <b style="color:var(--gold)">${pct(weights.temporal)}</b></div>
          <div>Entropy <b style="color:var(--purple)">${pct(weights.entropy)}</b></div>
        </div>
        <div id="engine-calibration-result" style="font-size:12px;color:var(--muted);"></div>
      </div>
    `;

    document.getElementById('btn-calibrate-engine')?.addEventListener('click', calibrateEngineWalkForward);

    if (result) {
      const target = document.getElementById('engine-calibration-result');
      target.innerHTML = `Walk-forward: ${result.evaluated || 0} pasos | aciertos promedio: ${(result.avgHits || 0).toFixed(2)}/6 | caos: ${Math.round((result.chaosRate || 0) * 100)}%`;
      if (result.DO_NOT_BET) target.innerHTML += ' | <b style="color:var(--red)">DO_NOT_BET activo</b>';
      if (Number.isFinite(result.errorVarianceLast3)) target.innerHTML += ` | varianza ultimos 3: ${result.errorVarianceLast3.toFixed(4)}`;
    }
  }

  async function calibrateEngineWalkForward() {
    if (typeof timeTravelTraining !== 'function') {
      alert('No se encontro timeTravelTraining. Verifica que engine.js y worker.js esten cargados.');
      return;
    }
    const data = typeof getActiveData === 'function' ? getActiveData() : [];
    if (!Array.isArray(data) || data.length < 15) {
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
      if (typeof updateLoadingProgress === 'function') updateLoadingProgress(100, 'Calibracion completada');
      if (typeof showLoadingModal === 'function') showLoadingModal(false);
      renderCalibrationPanel(result);

      if (result.DO_NOT_BET || result.chaosMode || result.confidence < 70) {
        alert('Nivel de confianza bajo o Modo Caos activo. Sugerencia: NO apostar con esta calibracion.');
      } else if (typeof showToast === 'function') {
        showToast(`Motor calibrado: confianza ${Math.round(result.confidence)}%`);
      }
    } catch (error) {
      if (typeof showLoadingModal === 'function') showLoadingModal(false);
      console.error(error);
      alert('No se pudo calibrar el motor: ' + (error.message || error));
    }
  }

  document.addEventListener('DOMContentLoaded', () => {
    setTimeout(() => renderCalibrationPanel(), 0);
  });
})();
