const fs = require('fs');
const assert = require('assert');

function read(path) {
  return fs.readFileSync(path, 'utf8');
}

const cleanApp = read('v4-clean-app.js');
const auditPanel = read('v4-decision-audit-panel.js');

assert(
  cleanApp.includes('function parseJsonText(rawText, label, url)'),
  'v4-clean-app.js must parse resultados.json from text with diagnostics'
);
assert(
  cleanApp.includes('async function fetchJsonFile(path, label, queryKey = \'v42\')'),
  'v4-clean-app.js must fetch JSON as text before parsing'
);
assert(
  !cleanApp.includes('response.json(); initApp(jsonData)'),
  'v4-clean-app.js must not use response.json() directly for resultados.json'
);
assert(
  cleanApp.includes('Preview recibido:'),
  'v4-clean-app.js parse failures must include a received preview'
);
assert(
  cleanApp.includes('parece HTML o una respuesta de error'),
  'v4-clean-app.js must detect HTML/non-JSON responses'
);

assert(
  auditPanel.includes('function parseOptionalJson(rawText, path, url)'),
  'v4-decision-audit-panel.js must parse optional JSON from text'
);
assert(
  auditPanel.includes('JSON auxiliar inválido'),
  'auxiliary JSON parse failures must log useful diagnostics'
);
assert(
  auditPanel.includes('response.text()'),
  'auxiliary JSON loader must read text before parsing'
);

console.log('web json loader smoke ok');
