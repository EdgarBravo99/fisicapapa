# Melate Pro V7 / Fisicapapa

Sistema local + web para análisis cuantitativo, simulación y visualización de combinaciones de **Melate** y **Revancha**.

Este README resume el contexto del proyecto para poder continuar en otra conversación sin leer todo el historial. La versión activa es **V3**.

> Uso informativo/experimental. Los scores del sistema son rankings internos del modelo, no probabilidades reales garantizadas de ganar.

---

## Estado actual

### Flujo activo

```txt
CSV histórico → local_cruncher_v3.py → resultados.json → web V3
```

### Archivos principales

```txt
local_cruncher_v3.py                 Motor local principal
resultados.json                      Salida consumida por la web
index.html                           Página principal
engine.js                            Reglas base web / heurísticas originales
ui.js                                UI base / legacy
python-results-v3-compat.js          Bridge V3 generador/evaluador manual
v3-panels-bridge.js                  Bridge V3 para mapa, stats, forense, coincidencias, física
v3-left-right-indicator.js           Indicador Izquierda/Derecha V3
walk-forward-ui.js                   Panel Walk-Forward V3
heatmap-fix.js                       Capa/fallback mapa de calor
run_local_cruncher_v3.bat            Launcher Windows
```

### Obsoleto / legacy

```txt
local_cruncher_v2.py
python-results-bridge.js
```

V2 ya no debe guiar el proyecto. La web está orientada a V3.

---

## Motor local V3

Archivo:

```txt
local_cruncher_v3.py
```

Objetivo:

1. Leer CSV local de Melate/Revancha.
2. Aplicar olvido histórico y usar solo buffer reciente.
3. Entrenar expertos sin data leakage.
4. Optimizar pesos con Optuna.
5. Generar Monte Carlo local.
6. Exportar `resultados.json`.

### Modos

El script permite escoger:

```txt
[1] Revancha
[2] Melate
```

Busca CSV en orden aproximado:

```txt
Revancha: historial_revancha.csv, revancha.csv, historial.csv
Melate:   historial_melate.csv, melate.csv, historial.csv
```

### Olvido histórico

V3 descarta historia antigua y usa un buffer reciente:

```txt
RECENT_BUFFER_MIN = 150
RECENT_BUFFER_MAX = 200
RECENT_BUFFER_DEFAULT = 180
```

Esto se exporta en:

```json
"historical_forgetting": {
  "total_loaded_draws": 0,
  "discarded_old_draws": 0,
  "recent_buffer_size": 180,
  "buffer_first_draw": "...",
  "buffer_last_draw": "..."
}
```

### Anti-leakage

En el backtesting ciego secuencial, para predecir el sorteo `T`, todos los expertos solo pueden usar datos hasta `T-1`.

Esto aplica para:

```txt
XGBoost, LSTM, Markov, Fourier, Bayes, Física, Temporal, Entropía, Estructura
```

### Expertos / jueces

V3 usa un ensemble de expertos:

```txt
physical    → física de esferas
structural  → estructura de combinación
temporal    → inercia temporal
entropy     → drift / estabilidad
fourier     → micro-ciclos recientes
bayes       → frecuencia + desgaste sigmoide
xgboost     → clasificador tabular
lstm        → memoria secuencial con ventana de 20 sorteos
markov      → transición desde sorteo anterior
```

### Física de esferas

V3 sí considera pesos físicos separados por juego:

```txt
DEFAULT_BALL_WEIGHTS_MELATE
DEFAULT_BALL_WEIGHTS_REVANCHA
```

Incluye:

```txt
peso medido
peso efectivo
desgaste sigmoide
bonus físico
uso dentro del buffer reciente
validación reglamentaria
```

Rangos:

```txt
WEIGHT_MIN = 4.25
WEIGHT_MAX = 5.25
WEIGHT_DIFF_MAX = 0.30
```

### Optuna

Optuna ajusta pesos dinámicos del ensemble con backtesting OOS reciente:

```txt
avg_hits
avg_hits_top10
avg_hits_top12
avg_mse
```

Se agregó parche para evitar monopolio de XGBoost u otro experto:

```txt
fix_v3_ensemble_diversity.py
```

Ese parche agrega guardrails:

```txt
máximo 38% por experto
mínimo 4 expertos activos
penalización por concentración
```

### Monte Carlo

Configuración V3:

```txt
MC_TOTAL_COMBINATIONS = 32_000_000
MC_BATCH_SIZE = 400_000
MC_KEEP_PER_BATCH = 2500
```

Puede usar CuPy/CUDA si está disponible. Si falta NVRTC, puede caer a NumPy CPU usando el parche de fallback.

---

## Parches auxiliares

### PyTorch / TinyLSTM

```txt
fix_local_cruncher_v3_torch.py
```

Corrige:

```txt
AttributeError: 'NoneType' object has no attribute 'Module'
```

### CuPy / NVRTC

```txt
fix_v3_runtime_cupy_guard.py
```

Corrige o evita bloqueo por:

```txt
Failure finding "nvrtc*.dll"
```

Si CuPy falla, reintenta Monte Carlo con NumPy CPU.

### Diversidad del ensemble

```txt
fix_v3_ensemble_diversity.py
```

Evita que XGBoost monopolice el resultado. El modelo debe comportarse como jurado de expertos.

---

## Comandos recomendados

Desde PowerShell dentro del repo:

```powershell
git pull origin main
py -X utf8 .\fix_local_cruncher_v3_torch.py
py -X utf8 .\fix_v3_runtime_cupy_guard.py
py -X utf8 .\fix_v3_ensemble_diversity.py
py -X utf8 .\local_cruncher_v3.py
```

Después de generar `resultados.json`:

```powershell
git add resultados.json
git commit -m "Update predictions"
git push origin main
```

Si el script ya hizo push automático, no hace falta repetirlo.

---

## Contrato de `resultados.json` V3

La web reconoce V3 si existe:

```json
"score_kind": "optuna_weighted_net_score"
```

Campos importantes:

```json
{
  "last_update": "timestamp",
  "source": "local_cruncher_v3_sequential_gpu",
  "game_mode": "melate | revancha",
  "game_label": "Melate | Revancha",
  "historical_forgetting": {},
  "score_kind": "optuna_weighted_net_score",
  "drift_detected": false,
  "procedure_log": "...",
  "optuna_audit": {},
  "walk_forward": {},
  "physics_summary": {},
  "expert_weights": {},
  "number_scores": {},
  "manual_suggestion_seed": [],
  "total_mc_evaluated": 32000000,
  "max_net_score_found": 0.8428,
  "generator_pool": [],
  "top_combinations": []
}
```

### `number_scores`

Score V3 por número. Lo usan mapa de calor y evaluador manual.

### `manual_suggestion_seed`

Datos por número:

```json
{
  "number": 5,
  "score": 84.2,
  "winner_component": "lstm",
  "winner_component_human": "memoria secuencial LSTM",
  "reason": "...",
  "expert_raw": {},
  "effective_weight": 4.52,
  "physics_bonus": 3.2,
  "uses_in_window": 18
}
```

Lo usan:

```txt
Evaluador manual
Sugerencias profundas
Mapa de calor
Física solo lectura
```

### `generator_pool`

Combinaciones candidatas Monte Carlo:

```json
{
  "numbers": [5, 12, 18, 33, 41, 55],
  "net_score": 0.8428,
  "score_percent": 84.28,
  "human_explanation": "...",
  "plain_route": "...",
  "number_explanations": []
}
```

Lo usan:

```txt
Generador
Coincidencias
Forense
Estadísticas
Indicador Izquierda/Derecha
```

### `walk_forward.rows`

Validaciones OOS:

```json
{
  "draw_id": "4212",
  "actual": [1, 2, 3, 4, 5, 6],
  "predicted_top6": [1, 8, 12, 20, 31, 45],
  "predicted_top10": [],
  "hits": 2,
  "hits_top10": 3,
  "mse": 0.123,
  "kl": 0.04,
  "drift_detected": false
}
```

Lo usan:

```txt
Walk-Forward panel
Estadísticas
Indicador Izquierda/Derecha
```

---

## Web V3

### Carga de scripts

Orden actual importante en `index.html`:

```html
<script src="data.js"></script>
<script src="engine.js"></script>
<script src="ui.js"></script>
<script src="python-results-v3-compat.js"></script>
<script src="heatmap-fix.js"></script>
<script src="walk-forward-ui.js"></script>
<script src="v3-panels-bridge.js"></script>
<script src="v3-left-right-indicator.js"></script>
```

Los scripts V3 deben ir al final porque sobreescriben renderizados legacy.

### Generador

Usa `generator_pool`. No genera Monte Carlo pesado en navegador.

Muestra:

```txt
net score
explicación humana
ruta por número
favoritos
```

### Evaluador manual

Usa:

```txt
manual_suggestion_seed
number_scores
generator_pool
```

Analiza:

```txt
score promedio V3
score por número
impulsor dominante
motivo por número
par/impar
bajos/altos
décadas
suma
cercanía con Monte Carlo V3
```

Sugerencias:

```txt
Mejora por score V3
Alineación con Monte Carlo V3
Balance estructural
```

### Mapa de calor

Vistas:

```txt
Score      → number_scores V3
Frecuencia → presencia en generator_pool
Retraso    → bonus físico V3 / peso efectivo
```

### Estadísticas

Usa:

```txt
max_net_score_found
total_mc_evaluated
historical_forgetting
drift_detected
expert_weights
physics_summary
manual_suggestion_seed
generator_pool
walk_forward.rows
```

### Indicador Izquierda/Derecha

Archivo:

```txt
v3-left-right-indicator.js
```

Calcula:

```txt
Izquierda: números 1-28
Derecha: números 29-56
```

Usa:

```txt
generator_pool
walk_forward.rows.actual
walk_forward.rows.predicted_top6
```

Muestra:

```txt
Futuro simulado
Backtesting real reciente
Predicción Walk-Forward reciente
Bloques de 20 combinaciones
```

### Forense

Usa:

```txt
LSTM / Markov dominantes
pares frecuentes en generator_pool
terminaciones ponderadas por score V3
patrones por impulsor dominante
estructuras frecuentes del Monte Carlo
```

### Coincidencias

Busca coincidencias dentro del `generator_pool`.

### Física

Mantiene el simulador original y agrega una lectura V3 de solo consulta:

```txt
peso efectivo promedio
diferencia de peso
reglamento OK / revisar
mayor bonus físico
menor bonus físico
```

No modifica pesos guardados ni inputs.

---

## Problemas conocidos

### `git no se reconoce`

Instalar Git y reiniciar PowerShell.

Verificar:

```powershell
git --version
```

### `nvrtc*.dll`

Verificar CUDA:

```powershell
echo $env:CUDA_PATH
Get-ChildItem "$env:CUDA_PATH\bin\nvrtc*.dll"
```

Aplicar fallback:

```powershell
py -X utf8 .\fix_v3_runtime_cupy_guard.py
```

### La web no refleja cambios

Usar:

```txt
Ctrl + F5
```

Si está en Vercel, esperar el deploy.

---

## Checklist para otra conversación

Pegar esto al iniciar una conversación nueva:

```txt
Repo: EdgarBravo99/fisicapapa
Proyecto: Melate Pro V7 / Fisicapapa
Versión activa: V3
Motor principal: local_cruncher_v3.py
Salida principal: resultados.json
Web V3-only: python-results-v3-compat.js + v3-panels-bridge.js + v3-left-right-indicator.js
V2 obsoleto: no usar python-results-bridge.js ni local_cruncher_v2.py como flujo principal
El modelo usa: buffer reciente 150-200, LSTM ventana 20, Markov, XGBoost, Fourier, Bayes, física de esferas, temporal, entropía, estructura, Optuna y Monte Carlo.
No usar operational_confidence. Usar net_score / score_kind=optuna_weighted_net_score.
```

---

## Pendientes sugeridos

- Integrar permanentemente los patchers dentro de `local_cruncher_v3.py`.
- Agregar modo `--fast` y `--full`.
- Mostrar `last_update` en todos los paneles.
- Agregar indicador visible de si `resultados.json` corresponde a Melate o Revancha.
- Compactar `resultados.json` si crece demasiado para Vercel.
- Exportar contribuciones por experto de forma más compacta para evitar futuros `undefined`.
