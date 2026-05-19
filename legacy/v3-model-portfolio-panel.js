// v3-model-portfolio-panel.js
// Panel separado para cartera informativa V3 y líderes por década.
(function () {
  'use strict';

  function esc(value) {
    return String(value ?? '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function getV3() {
    const data = typeof window.getV3Results === 'function'
      ? window.getV3Results()
      : window.MELATE_V3_RESULTS;
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  async function ensureV3() {
    let data = getV3();
    if (!data && typeof window.loadV3Results === 'function') {
      data = await window.loadV3Results(false);
    }
    return data && data.score_kind === 'optuna_weighted_net_score' ? data : null;
  }

  function score(combo) {
    if (Number.isFinite(Number(combo?.score_percent))) return Number(combo.score_percent);
    if (Number.isFinite(Number(combo?.net_score))) return Number(combo.net_score) * 100;
    return 0;
  }

  function ballHtml(nums, color = 'var(--green)') {
    return (nums || []).map(n => `<span class="ball-lg" style="background:rgba(255,255,255,.05);border:2px solid ${color};color:${color}">${esc(n)}</span>`).join('');
  }

  function ensurePanel() {
    if (document.querySelector('[data-target="seleccion-v3"]')) return;
    const tabs = document.querySelector('.tabs');
    const wrap = document.querySelector('.wrap');
    if (!tabs || !wrap) return;

    const tab = document.createElement('div');
    tab.className = 'tab';
    tab.dataset.target = 'seleccion-v3';
    tab.style.borderColor = 'rgba(0,255,102,.4)';
    tab.style.color = 'var(--green)';
    tab.textContent = '🎯 Selección V3';
    tabs.appendChild(tab);

    const panel = document.createElement('div');
    panel.className = 'panel';
    panel.id = 'tab-seleccion-v3';
    panel.innerHTML = `
      <div class="card" style="border-color:var(--green)">
        <div class="card-header"><h2>🎯 Portafolio Informativo V3</h2></div>
        <div class="card-body">
          <p style="color:var(--muted);font-size:13px;line-height:1.5;">
            Esta sección muestra 10 combinaciones fijas derivadas del pool optimizado de Python.
            No depende del botón Generar ni ejecuta Monte Carlo en navegador.
          </p>
          <div id="v3-portfolio-top10"></div>
        </div>
      </div>
      <div class="card" style="border-color:var(--gold);margin-top:18px;">
        <div class="card-header"><h2>🔢 Mejor número por década</h2></div>
        <div class="card-body"><div id="v3-best-decades"></div></div>
      </div>
    `;
    wrap.appendChild(panel);

    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      panel.classList.add('active');
      renderPortfolio();
    });
  }

  async function renderPortfolio() {
    const data = await ensureV3();
    const topEl = document.getElementById('v3-portfolio-top10');
    const decEl = document.getElementById('v3-best-decades');
    if (!topEl || !decEl) return;

    if (!data) {
      topEl.innerHTML = '<div style="color:var(--muted)">No hay resultados V3 cargados.</div>';
      decEl.innerHTML = '';
      return;
    }

    const portfolio = data.model_portfolio?.top10 || data.top_combinations || [];
    const decades = data.best_numbers_by_decade || [];

    topEl.innerHTML = portfolio.length ? portfolio.map((combo, idx) => {
      const color = idx < 3 ? 'var(--green)' : idx < 6 ? 'var(--gold)' : 'var(--purple)';
      return `<div class="combo-card" style="border-color:${color}70;margin-bottom:12px;">
        <div class="combo-card-header">
          <b style="color:${color}">#${idx + 1} · Pool Rank ${esc(combo.pool_rank ?? combo.portfolio_rank ?? 'N/A')}</b>
          <span style="color:var(--gold);font-family:var(--mono);">${score(combo).toFixed(2)}/100</span>
        </div>
        <div class="combo-balls">${ballHtml(combo.numbers || [], color)}</div>
        <div style="font-size:12px;color:var(--muted);margin-top:8px;line-height:1.5;">
          ${esc(combo.portfolio_reason || combo.human_explanation || combo.procedure || '')}
        </div>
        <div style="font-size:11px;color:var(--dim);margin-top:6px;">${esc(combo.plain_route || '')}</div>
      </div>`;
    }).join('') : '<div style="color:var(--muted)">No hay model_portfolio.top10 en resultados.json. Corre local_cruncher_v3.py después de aplicar el patcher.</div>';

    decEl.innerHTML = decades.length ? `
      <div class="tbl-wrap"><table>
        <thead><tr><th>Década</th><th>Número líder</th><th>Score</th><th>Impulsor</th><th>Motivo</th></tr></thead>
        <tbody>
          ${decades.map(row => `<tr>
            <td>${esc(row.decade)}</td>
            <td><b style="color:var(--green)">${esc(row.number)}</b></td>
            <td>${Number(row.score || 0).toFixed(2)}</td>
            <td>${esc(row.main_driver_human)}</td>
            <td>${esc(row.reason)}</td>
          </tr>`).join('')}
        </tbody>
      </table></div>
    ` : '<div style="color:var(--muted)">No hay best_numbers_by_decade en resultados.json.</div>';
  }

  window.renderV3ModelPortfolio = renderPortfolio;

  document.addEventListener('DOMContentLoaded', () => {
    ensurePanel();
    setTimeout(renderPortfolio, 500);
  });

  document.addEventListener('melate:v3-results-loaded', () => {
    ensurePanel();
    renderPortfolio();
  });
})();
