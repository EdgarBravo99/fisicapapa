const DATA_URL = 'resultados.json';
const THRESHOLD = 70;

function byId(id) {
  return document.getElementById(id);
}

function formatDate(value) {
  if (!value) return '--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return new Intl.DateTimeFormat('es-MX', {
    dateStyle: 'medium',
    timeStyle: 'short'
  }).format(date);
}

function formatPercent(value) {
  const n = Number(value);
  return Number.isFinite(n) ? n.toFixed(1) + '%' : '--%';
}

function normalizeData(raw) {
  return {
    last_update: raw && (raw.last_update || raw.lastUpdate) || null,
    drift_detected: Boolean(raw && raw.drift_detected),
    hindsight_log: raw && raw.hindsight_log || 'Sin auditoria disponible.',
    max_confidence_found: Number(raw && raw.max_confidence_found || 0),
    top_combinations: Array.isArray(raw && raw.top_combinations) ? raw.top_combinations : [],
    capital_preservation: Boolean(raw && raw.capital_preservation)
  };
}

function setRisk(data) {
  const stopLoss = data.capital_preservation || data.top_combinations.length === 0 || data.max_confidence_found < THRESHOLD;
  const pill = byId('risk-pill');
  const kpiRisk = byId('kpi-risk');
  const driftBanner = byId('drift-banner');
  const riskCard = kpiRisk ? kpiRisk.closest('.kpi-card') : null;

  driftBanner.classList.toggle('hidden', !data.drift_detected);

  if (data.drift_detected || stopLoss) {
    pill.textContent = data.drift_detected ? 'MODO CAOS' : 'STOP-LOSS';
    pill.classList.add('danger');
    kpiRisk.textContent = data.drift_detected ? 'RIESGO CRITICO' : 'AHORRO CAPITAL';
    if (riskCard) riskCard.classList.add('danger');
  } else {
    pill.textContent = 'OPERATIVO';
    pill.classList.remove('danger');
    kpiRisk.textContent = 'CONTROLADO';
    if (riskCard) riskCard.classList.remove('danger');
  }
}

function renderKPIs(data) {
  byId('kpi-update').textContent = formatDate(data.last_update);
  byId('kpi-confidence').textContent = formatPercent(data.max_confidence_found);
  byId('kpi-count').textContent = String(data.top_combinations.length || 0);
  setRisk(data);
}

function renderBalls(numbers) {
  return numbers.map(function (n) {
    return '<span class="ball">' + Number(n) + '</span>';
  }).join('');
}

function renderCombinations(data) {
  const body = byId('combo-body');
  const stopLoss = byId('stop-loss');
  const tableWrap = byId('table-wrap');
  const combos = data.top_combinations
    .filter(function (item) { return Number(item.confidence) >= THRESHOLD; })
    .slice(0, 10);

  if (!combos.length) {
    stopLoss.classList.remove('hidden');
    tableWrap.classList.add('hidden');
    body.innerHTML = '';
    return;
  }

  stopLoss.classList.add('hidden');
  tableWrap.classList.remove('hidden');

  body.innerHTML = combos.map(function (item, index) {
    const confidence = Math.max(0, Math.min(100, Number(item.confidence) || 0));
    const numbers = Array.isArray(item.numbers) ? item.numbers : [];
    return '<tr>' +
      '<td>' + String(index + 1).padStart(2, '0') + '</td>' +
      '<td><div class="combo-balls">' + renderBalls(numbers) + '</div></td>' +
      '<td class="confidence">' + formatPercent(confidence) + '</td>' +
      '<td><div class="progress-track"><div class="progress-fill" style="width:' + confidence + '%"></div></div></td>' +
      '</tr>';
  }).join('');
}

function renderAudit(data) {
  byId('hindsight-log').textContent = data.hindsight_log || 'Sin auditoria disponible.';
}

function showError(message) {
  const banner = byId('error-banner');
  banner.textContent = message;
  banner.classList.remove('hidden');
  byId('risk-pill').textContent = 'SIN DATOS';
  byId('risk-pill').classList.add('danger');
}

async function loadResults() {
  byId('error-banner').classList.add('hidden');
  byId('risk-pill').textContent = 'CARGANDO';
  byId('risk-pill').classList.remove('danger');

  try {
    const response = await fetch(DATA_URL + '?t=' + Date.now(), { cache: 'no-store' });
    if (!response.ok) throw new Error('No se pudo leer resultados.json. HTTP ' + response.status);
    const data = normalizeData(await response.json());
    renderKPIs(data);
    renderCombinations(data);
    renderAudit(data);
  } catch (error) {
    showError(error.message + '. Genera resultados.json con local_cruncher.py y subelo al repositorio.');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  byId('reload-btn').addEventListener('click', loadResults);
  loadResults();
});
