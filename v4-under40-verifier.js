// v4-under40-verifier.js
// Verificador visual de macroestructura <40. No modifica el cruncher ni el score oficial.
(function () {
  'use strict';

  const PICK_COUNT = 6;
  const RANGE_CUTOFF = 40;
  const BLOCK_DRAWS = 5;
  const LOOKBACK_DRAWS = 4;
  const EXPECTED_UNDER_40_BLOCK = 21;
  const NEUTRAL_EXPECTED_TODAY = 6 * 39 / 56;

  const $ = id => document.getElementById(id);
  const esc = value => String(value ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
  const clamp = (value, min, max) => Math.max(min, Math.min(max, value));

  function validV42(data) {
    const fb = data?.feedback_loop || data?.walk_forward?.feedback_loop || data?.deep_stacking?.feedback_loop;
    return fb?.version === 'V4.2';
  }

  function currentJson() {
    return window.FISICAPAPA_WEB_V2?.jsonData || null;
  }

  function readManualNumbers() {
    const nums = [1, 2, 3, 4, 5, 6].map(i => Number($(`manual-n${i}`)?.value));
    if (nums.length !== PICK_COUNT || nums.some(n => !Number.isInteger(n) || n < 1 || n > 56) || new Set(nums).size !== PICK_COUNT) {
      return null;
    }
    return nums.sort((a, b) => a - b);
  }

  function lastFourActualDraws(data) {
    const rows = Array.isArray(data?.walk_forward?.rows) ? data.walk_forward.rows : [];
    return rows
      .filter(row => Array.isArray(row?.actual) && row.actual.length >= PICK_COUNT)
      .slice(-LOOKBACK_DRAWS)
      .map(row => ({ drawId: row.draw_id ?? row.id ?? '—', numbers: row.actual.map(Number).filter(Number.isFinite) }));
  }

  function computeUnder40Pressure(data, numbers) {
    const draws = lastFourActualDraws(data);
    const userUnder40 = numbers.filter(n => n < RANGE_CUTOFF).length;

    if (draws.length < LOOKBACK_DRAWS) {
      return {
        available: false,
        userUnder40,
        message: 'No hay suficientes folds recientes en walk_forward.rows para calcular presión <40. Se necesitan 4 sorteos reales recientes.',
      };
    }

    const last4Under40 = draws.reduce((acc, row) => acc + row.numbers.filter(n => n < RANGE_CUTOFF).length, 0);
    const expectedTodayRaw = EXPECTED_UNDER_40_BLOCK - last4Under40;
    const expectedToday = clamp(expectedTodayRaw, 0, PICK_COUNT);
    const diff = userUnder40 - expectedToday;
    const absDiff = Math.abs(diff);

    let status = 'alineado';
    let tone = 'emerald';
    let headline = 'Presión de Rango <40 alineada';
    if (absDiff >= 3) {
      status = 'desalineado';
      tone = 'red';
      headline = 'Presión de Rango <40 muy desalineada';
    } else if (absDiff >= 2) {
      status = 'alerta';
      tone = 'amber';
      headline = 'Presión de Rango <40 con alerta suave';
    }

    return {
      available: true,
      draws,
      last4Under40,
      expectedTodayRaw,
      expectedToday,
      userUnder40,
      diff,
      absDiff,
      status,
      tone,
      headline,
      neutralExpectedToday: NEUTRAL_EXPECTED_TODAY,
      blockTarget: EXPECTED_UNDER_40_BLOCK,
      blockDraws: BLOCK_DRAWS,
      lookbackDraws: LOOKBACK_DRAWS,
    };
  }

  function toneClasses(tone) {
    if (tone === 'red') return 'border-red-400/60 bg-red-500/10 text-red-100';
    if (tone === 'amber') return 'border-amber-400/60 bg-amber-500/10 text-amber-100';
    return 'border-emerald-400/50 bg-emerald-500/10 text-emerald-100';
  }

  function renderVerifier() {
    const data = currentJson();
    const resultBox = $('manual-result');
    if (!data || !validV42(data) || !resultBox || resultBox.classList.contains('hidden')) return;

    const numbers = readManualNumbers();
    const old = $('under40-verifier-card');
    if (old) old.remove();
    if (!numbers) return;

    const pressure = computeUnder40Pressure(data, numbers);
    let html = '';

    if (!pressure.available) {
      html = `<section id="under40-verifier-card" class="rounded-2xl border border-slate-700 bg-slate-900/70 p-4 text-sm text-slate-300">
        <p class="text-xs uppercase tracking-[0.22em] text-slate-500">Verificador macroestructura &lt;40</p>
        <p class="mt-2">${esc(pressure.message)}</p>
        <p class="mt-2">Tu combo tiene <b>${pressure.userUnder40}</b> números menores a 40.</p>
      </section>`;
    } else {
      const classes = toneClasses(pressure.tone);
      const drawText = pressure.draws.map(d => `${d.drawId}: ${d.numbers.filter(n => n < RANGE_CUTOFF).length}/6`).join(' · ');
      html = `<section id="under40-verifier-card" class="rounded-2xl border ${classes} p-4 text-sm">
        <div class="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div>
            <p class="text-xs uppercase tracking-[0.22em] opacity-80">Verificador macroestructura &lt;40</p>
            <h3 class="mt-2 text-lg font-black">${esc(pressure.headline)}</h3>
            <p class="mt-2 leading-6">Presión de Rango &lt;40: Tu combo tiene <b>${pressure.userUnder40}</b> números menores a 40. La tendencia de cierre de bloque sugiere <b>${pressure.expectedToday}</b> para este sorteo.</p>
          </div>
          <div class="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-xs font-bold">Δ ${pressure.diff > 0 ? '+' : ''}${pressure.diff}</div>
        </div>
        <div class="mt-3 grid gap-3 md:grid-cols-3">
          <div class="rounded-xl border border-white/10 bg-black/20 p-3"><p class="text-[10px] uppercase tracking-[0.18em] opacity-70">Últimos 4 sorteos</p><p class="mt-1 font-black">${pressure.last4Under40} números &lt;40</p></div>
          <div class="rounded-xl border border-white/10 bg-black/20 p-3"><p class="text-[10px] uppercase tracking-[0.18em] opacity-70">Objetivo bloque 5 sorteos</p><p class="mt-1 font-black">${pressure.blockTarget}/30</p></div>
          <div class="rounded-xl border border-white/10 bg-black/20 p-3"><p class="text-[10px] uppercase tracking-[0.18em] opacity-70">Esperanza neutral</p><p class="mt-1 font-black">${pressure.neutralExpectedToday.toFixed(2)}/6</p></div>
        </div>
        <p class="mt-3 text-xs leading-5 opacity-80">Detalle últimos folds: ${esc(drawText)}. Este verificador es auditoría visual; no cambia el Score Neto V4 ni el cruncher.</p>
      </section>`;
    }

    resultBox.insertAdjacentHTML('beforeend', html);
  }

  function bind() {
    $('btn-evaluate-manual')?.addEventListener('click', () => setTimeout(renderVerifier, 80));
    [1, 2, 3, 4, 5, 6].forEach(i => {
      $(`manual-n${i}`)?.addEventListener('keydown', event => {
        if (event.key === 'Enter') setTimeout(renderVerifier, 120);
      });
    });

    const resultBox = $('manual-result');
    if (resultBox) {
      const observer = new MutationObserver(() => setTimeout(renderVerifier, 80));
      observer.observe(resultBox, { childList: true, subtree: false });
    }
  }

  document.addEventListener('DOMContentLoaded', () => setTimeout(bind, 300));
  window.computeUnder40Pressure = computeUnder40Pressure;
  window.renderUnder40Verifier = renderVerifier;
})();
