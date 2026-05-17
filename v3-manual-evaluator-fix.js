// v3-manual-evaluator-fix.js
// DESACTIVADO.
// Esta capa provocaba fallback a score 0.0 / sin datos en el evaluador manual.
// Se conserva el archivo para no romper el auto-loader, pero no sobreescribe evalUserComboUI.
(function () {
  'use strict';
  window.__v3ManualEvaluatorFixDisabled = true;
})();
