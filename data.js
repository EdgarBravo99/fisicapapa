// ═══════════════════════════════════════════════════════
// data.js - DATOS Y CARGA DE CSV (V7.3 — Revisado)
// ═══════════════════════════════════════════════════════

let DATA_REVANCHA = [
  [4212,"13/05/2026",9,15,22,27,47,49], [4211,"10/05/2026",7,16,18,20,27,42], [4210,"08/05/2026",1,32,41,45,55,56],
  [4209,"06/05/2026",2,8,20,26,38,54], [4208,"03/05/2026",6,7,26,27,30,40], [4207,"01/05/2026",11,30,33,35,46,48],
  [4206,"29/04/2026",4,18,24,27,45,53], [4205,"26/04/2026",6,20,39,41,42,48], [4204,"24/04/2026",4,15,29,43,44,46],
  [4203,"22/04/2026",11,13,16,24,32,41], [4202,"19/04/2026",6,15,17,23,27,51], [4201,"17/04/2026",23,42,48,49,50,53],
  [4200,"15/04/2026",7,15,17,22,45,51], [4199,"12/04/2026",11,34,38,47,48,52], [4198,"10/04/2026",9,12,19,26,36,49],
  [4197,"08/04/2026",15,27,41,43,46,53], [4196,"05/04/2026",13,23,26,39,41,44], [4195,"03/04/2026",1,16,18,21,24,50],
  [4194,"01/04/2026",8,13,15,25,35,42], [4193,"29/03/2026",4,34,35,39,51,56], [4192,"27/03/2026",7,16,27,29,34,37],
  [4191,"25/03/2026",5,9,23,25,35,45], [4190,"22/03/2026",15,19,25,33,52,54], [4189,"20/03/2026",13,15,16,18,28,40],
  [4188,"18/03/2026",2,29,31,43,45,52], [4187,"15/03/2026",4,5,19,50,52,53], [4186,"13/03/2026",4,7,23,34,37,55],
  [4185,"11/03/2026",2,17,20,34,40,43], [4184,"08/03/2026",9,15,43,44,45,47], [4183,"06/03/2026",4,20,22,27,31,48],
  [4182,"04/03/2026",2,9,17,18,47,51], [4181,"01/03/2026",7,15,23,36,43,46], [4180,"27/02/2026",13,14,18,21,37,40],
  [4179,"25/02/2026",6,15,26,35,50,53], [4178,"22/02/2026",4,8,19,30,44,49], [4177,"20/02/2026",1,6,15,24,36,44],
  [4176,"18/02/2026",5,8,10,29,54,56], [4175,"15/02/2026",14,32,35,46,50,51], [4174,"13/02/2026",5,11,12,13,29,44],
  [4173,"11/02/2026",12,26,32,40,51,54], [4172,"08/02/2026",8,11,34,38,44,54], [4171,"06/02/2026",4,5,7,14,15,55]
];
let DATA_MELATE = [...DATA_REVANCHA];
let CURRENT_MODE = 'revancha';

function getActiveData()   { return CURRENT_MODE === 'revancha' ? DATA_REVANCHA : DATA_MELATE; }
function getOppositeData() { return CURRENT_MODE === 'revancha' ? DATA_MELATE   : DATA_REVANCHA; }

const DB_NAME    = 'MelateRevanchaDB';
const DB_VERSION = 1;
let DB_INSTANCE = null;

function openLocalDatabase() {
  return new Promise((resolve) => {
    if (!window.indexedDB) {
      console.warn('IndexedDB no disponible en este navegador.');
      return resolve(null);
    }

    const request = indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = function (event) {
      const db = event.target.result;
      if (!db.objectStoreNames.contains('draws')) {
        const store = db.createObjectStore('draws', { keyPath: 'id' });
        store.createIndex('mode', 'mode', { unique: false });
        store.createIndex('drawNumber', 'drawNumber', { unique: false });
        store.createIndex('sortIndex', 'sortIndex', { unique: false });
      }
      if (!db.objectStoreNames.contains('metadata')) {
        db.createObjectStore('metadata', { keyPath: 'key' });
      }
    };
    request.onsuccess = function (event) {
      DB_INSTANCE = event.target.result;
      resolve(DB_INSTANCE);
    };
    request.onerror = function () {
      console.warn('No se pudo abrir IndexedDB:', request.error);
      resolve(null);
    };
  });
}

function buildSnapshotsForMode(mode, rows) {
  const baseWeights = mode === 'melate' ? DEFAULT_BALL_WEIGHTS_MELATE : DEFAULT_BALL_WEIGHTS_REVANCHA;
  const uses = new Array(57).fill(0);
  const snapshots = new Array(rows.length);

  for (let i = rows.length - 1; i >= 0; i--) {
    const row = rows[i];
    row.slice(2).forEach(n => { if (n >= 1 && n <= 56) uses[n]++; });
    const effective = new Array(57).fill(0);
    for (let n = 1; n <= 56; n++) {
      effective[n] = parseFloat((baseWeights[n] - uses[n] * WEAR_PER_USE).toFixed(4));
    }
    snapshots[i] = {
      id: `${mode}_${row[0]}`,
      mode,
      drawNumber: row[0],
      date: row[1],
      numbers: row.slice(2),
      sortIndex: i,
      snapshot: {
        uses: [...uses],
        effectiveWeights: effective
      }
    };
  }
  return snapshots;
}

function clearModeDataFromDB(mode) {
  if (!DB_INSTANCE) return Promise.resolve();
  return new Promise((resolve) => {
    const tx = DB_INSTANCE.transaction('draws', 'readwrite');
    const index = tx.objectStore('draws').index('mode');
    const request = index.openCursor(mode);
    request.onsuccess = function (event) {
      const cursor = event.target.result;
      if (cursor) {
        cursor.delete();
        cursor.continue();
      }
    };
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  });
}

function saveModeDataToDB(mode, rows) {
  if (!DB_INSTANCE) return Promise.resolve();
  const snapshots = buildSnapshotsForMode(mode, rows);
  return clearModeDataFromDB(mode).then(() => new Promise((resolve) => {
    const tx = DB_INSTANCE.transaction('draws', 'readwrite');
    const store = tx.objectStore('draws');
    snapshots.forEach(item => store.put(item));
    tx.oncomplete = () => resolve();
    tx.onerror = () => resolve();
  }));
}

function loadModeDataFromDB(mode) {
  if (!DB_INSTANCE) return Promise.resolve(null);
  return new Promise((resolve) => {
    const tx = DB_INSTANCE.transaction('draws', 'readonly');
    const index = tx.objectStore('draws').index('mode');
    const request = index.getAll(mode);
    request.onsuccess = function (event) {
      const items = event.target.result;
      if (!items || !items.length) return resolve(null);
      items.sort((a, b) => a.sortIndex - b.sortIndex);
      resolve(items.map(item => [item.drawNumber, item.date, ...item.numbers]));
    };
    request.onerror = () => resolve(null);
  });
}

function getLatestDrawSnapshot(mode) {
  if (!DB_INSTANCE) return Promise.resolve(null);
  return new Promise((resolve) => {
    const tx = DB_INSTANCE.transaction('draws', 'readonly');
    const index = tx.objectStore('draws').index('mode');
    const request = index.getAll(mode);
    request.onsuccess = function (event) {
      const items = event.target.result;
      if (!items || !items.length) return resolve(null);
      items.sort((a, b) => a.sortIndex - b.sortIndex);
      resolve(items[items.length - 1] || null);
    };
    request.onerror = () => resolve(null);
  });
}

function parseCsvText(text, targetMode) {
  const lines = text.replace(/\r/g, '').split('\n');
  const delimiter = lines[0].includes(';') ? ';' : ',';
  const newMelate = [];
  const newRevancha = [];

  for (let i = 1; i < lines.length; i++) {
    const raw = lines[i].trim();
    if (!raw) continue;

    const r = raw.split(delimiter).map(cell => cell.trim());
    const s = parseInt(r[0], 10);
    const f = r[1] || '';
    if (isNaN(s) || !f) continue;

    const canParseMelate = r.length >= 8;
    const canParseRevancha = r.length >= 15;

    if (targetMode === 'melate') {
      if (canParseMelate) {
        const mNums = [r[2], r[3], r[4], r[5], r[6], r[7]].map(Number);
        if (mNums.every(n => !isNaN(n) && n >= 1 && n <= 56)) newMelate.push([s, f, ...mNums]);
      }
    } else if (targetMode === 'revancha') {
      if (canParseRevancha) {
        const rNums = [r[9], r[10], r[11], r[12], r[13], r[14]].map(Number);
        if (rNums.every(n => !isNaN(n) && n >= 1 && n <= 56)) newRevancha.push([s, f, ...rNums]);
      } else if (canParseMelate) {
        const nums = [r[2], r[3], r[4], r[5], r[6], r[7]].map(Number);
        if (nums.every(n => !isNaN(n) && n >= 1 && n <= 56)) newRevancha.push([s, f, ...nums]);
      }
    } else {
      if (canParseRevancha) {
        const mNums = [r[2], r[3], r[4], r[5], r[6], r[7]].map(Number);
        const rNums = [r[9], r[10], r[11], r[12], r[13], r[14]].map(Number);
        if (mNums.every(n => !isNaN(n) && n >= 1 && n <= 56)) newMelate.push([s, f, ...mNums]);
        if (rNums.every(n => !isNaN(n) && n >= 1 && n <= 56)) newRevancha.push([s, f, ...rNums]);
      } else if (canParseMelate) {
        const nums = [r[2], r[3], r[4], r[5], r[6], r[7]].map(Number);
        if (nums.every(n => !isNaN(n) && n >= 1 && n <= 56)) {
          newMelate.push([s, f, ...nums]);
          newRevancha.push([s, f, ...nums]);
        }
      }
    }
  }

  return { newMelate, newRevancha };
}

async function processCsvImport(text, targetMode) {
  const { newMelate, newRevancha } = parseCsvText(text, targetMode);
  let loadedM = 0;
  let loadedR = 0;

  if ((targetMode === 'melate' || targetMode === null) && newMelate.length > 0) {
    DATA_MELATE = newMelate;
    loadedM = newMelate.length;
    await saveModeDataToDB('melate', DATA_MELATE);
  }
  if ((targetMode === 'revancha' || targetMode === null) && newRevancha.length > 0) {
    DATA_REVANCHA = newRevancha;
    loadedR = newRevancha.length;
    await saveModeDataToDB('revancha', DATA_REVANCHA);
  }

  return { loadedM, loadedR };
}

function setupCsvInputHandlers() {
  ['csv-file', 'csv-file-melate', 'csv-file-revancha'].forEach((id) => {
    const input = document.getElementById(id);
    if (!input) return;
    input.addEventListener('change', async function (e) {
      const file = e.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async function (event) {
        const targetMode = id === 'csv-file-melate' ? 'melate' : id === 'csv-file-revancha' ? 'revancha' : null;
        const { loadedM, loadedR } = await processCsvImport(event.target.result, targetMode);
        if (loadedM > 0 || loadedR > 0) {
          if (typeof showToast === 'function') showToast(`✅ CSV cargado: ${loadedR} Revancha / ${loadedM} Melate`);
          if (typeof rebuildAll === 'function') rebuildAll();
          if (typeof renderDbStatusUI === 'function') renderDbStatusUI();
        } else {
          alert('❌ Error: no se encontraron filas válidas. Verifica el formato del CSV.');
        }
        e.target.value = '';
      };
      reader.readAsText(file, 'UTF-8');
    });
  });
}

async function loadSavedDataFromDB() {
  await openLocalDatabase();
  if (!DB_INSTANCE) return;
  const [melateRows, revanchaRows] = await Promise.all([loadModeDataFromDB('melate'), loadModeDataFromDB('revancha')]);
  if (Array.isArray(melateRows) && melateRows.length) DATA_MELATE = melateRows;
  if (Array.isArray(revanchaRows) && revanchaRows.length) DATA_REVANCHA = revanchaRows;
}

async function renderDbStatusUI() {
  const status = document.getElementById('db-status');
  if (!status) return;
  if (!DB_INSTANCE) {
    status.textContent = 'Base local: IndexedDB no disponible o no inicializada.';
    return;
  }
  const tx = DB_INSTANCE.transaction('draws', 'readonly');
  const store = tx.objectStore('draws');
  const countReq = store.count();
  countReq.onsuccess = async function () {
    const total = countReq.result;
    const latest = await getLatestDrawSnapshot(CURRENT_MODE);
    let extra = '';
    if (latest) {
      const effective = latest.snapshot.effectiveWeights.filter((_, i) => i > 0);
      const avg = effective.reduce((a, b) => a + b, 0) / effective.length;
      extra = ` Último sorteo ${latest.drawNumber}: promedio efectivo ${avg.toFixed(4)}g.`;
    }
    status.textContent = `Base local: ${total} sorteos guardados${extra}`;
  };
  countReq.onerror = function () {
    status.textContent = 'Base local: error al leer el estado.';
  };
}

function initLocalDatabase() {
  return loadSavedDataFromDB();
}

// ── PARSER CSV ──
// Formato oficial Melate/Revancha (columnas base-0):
//   [0]=sorteo  [1]=fecha
//   Melate:   [2..7]  (6 números)
//   Revancha: [9..14] (6 números) — requiere ≥15 columnas (índices 0-14)
// Formato simple (solo Revancha):
//   [0]=sorteo  [1]=fecha  [2..7] = 6 números — requiere ≥8 columnas

