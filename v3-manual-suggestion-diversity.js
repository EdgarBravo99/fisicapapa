// v3-manual-suggestion-diversity.js
// LEGACY SHIM.
// V3 quedó legacy. Este archivo ya no debe pintar NET AVG ni sugerencias V3.
// Se conserva porque index.html lo carga, pero su única función es asegurar el evaluador V4 final.
(function () {
  'use strict';

  function injectV4Evaluator() {
    const base = 'v3-manual-evaluator-fix.js';
    const already = document.querySelector('script[src^="' + base + '"]');
    if (!already) {
      const s = document.createElement('script');
      s.src = base + '?v4only=' + Date.now();
      s.onload = () => { window.__manualEvaluatorMode = 'v4-components'; };
      s.onerror = () => console.warn('No se pudo cargar evaluador V4 final');
      document.body.appendChild(s);
    } else if (window.__manualEvaluatorMode !== 'v4-components') {
      // Si ya está cargado pero otra capa lo pisó, recargarlo con cache-bust.
      const s = document.createElement('script');
      s.src = base + '?v4only=' + Date.now();
      s.onload = () => { window.__manualEvaluatorMode = 'v4-components'; };
      document.body.appendChild(s);
    }
  }

  window.__v3ManualSuggestionDisabled = true;
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => setTimeout(injectV4Evaluator, 120));
  } else {
    setTimeout(injectV4Evaluator, 120);
  }
  setTimeout(injectV4Evaluator, 700);
  setTimeout(injectV4Evaluator, 1600);
})();
