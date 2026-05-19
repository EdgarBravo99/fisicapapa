// v3-manual-suggestion-diversity.js
// LEGACY SHIM.
// V3 quedó legacy. Este archivo ya no pinta NET AVG ni sugerencias V3.
// Su única función es cargar el evaluador V4-only con balance estructural y sugerencias profundas.
(function () {
  'use strict';

  function injectV4ScienceEvaluator() {
    const base = 'v4-manual-science.js';
    const s = document.createElement('script');
    s.src = base + '?v4science=' + Date.now();
    s.onload = () => { window.__manualEvaluatorMode = 'v4-only-science'; };
    s.onerror = () => console.warn('No se pudo cargar v4-manual-science.js');
    document.body.appendChild(s);
  }

  window.__v3ManualSuggestionDisabled = true;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(injectV4ScienceEvaluator, 120));
  } else {
    setTimeout(injectV4ScienceEvaluator, 120);
  }
  setTimeout(injectV4ScienceEvaluator, 700);
  setTimeout(injectV4ScienceEvaluator, 1600);
})();
