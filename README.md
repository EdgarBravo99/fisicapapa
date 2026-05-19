# Melate Pro V7 / Fisicapapa

## Estado activo V4.2

Esta rama deja como flujo vigente **Web V2 + Cruncher V4.2**. Las secciones historicas de este README siguen como contexto, pero la referencia operativa actual es:

```txt
Runner oficial: local_cruncher_v4_2_calibrated.py
Motor base: local_cruncher_v4_deep_stacking.py
Salida principal: resultados.json
Web activa: index.html + v4-clean-app.js + v4-results-panels.js + v4-under40-verifier.js + v4-system-diagnostics.js + v4-combo-comparator.js
```

La web valida estrictamente `feedback_loop.version = V4.2` y no debe cargar scripts V3. El verificador `<40` es solo auditoria visual: no modifica el cruncher ni la formula oficial del Score Neto V4.

Flujo personal recomendado:

```txt
Abrir index.html con ?v=20
Revisar Centro Personal V4.2
Evaluar una combinacion manual
Guardar la manual al comparador
Guardar una top combination
Comparar score web vs score cruncher, estructura, fisica, pool y macro <40
Revisar Auditor V4.2 solo si aparece OK/Revisar/Critico fuera de lo esperado
```

Nuevos modulos Web V2:

```txt
v4-system-diagnostics.js   Centro Personal V4.2, validateV42DataQuality, compareCruncherVsWebScore, getComboProfileV4 y Auditor V4.2
v4-combo-comparator.js     Comparador local temporal de 2 a 5 combinaciones con reporte copiable
```

No se debe usar el campo legacy de confianza operativa. Si hay diferencia entre `score_percent`, `net_score`, `confidence` o `score`, la web debe etiquetar claramente si el valor viene del cruncher o del recalculo web.

Sistema local + web para análisis cuantitativo, auditoría, simulación y visualización de combinaciones de **Melate** y **Revancha**.

Este README resume el estado real del proyecto para poder continuar en otra conversación sin leer todo el historial. La versión activa de la web es **V4**.

> Uso informativo/experimental. Los scores del sistema son rankings internos del modelo y métricas de auditoría; no son probabilidades reales garantizadas de ganar ni recomendación financiera.

---

## Estado actual del proyecto

### Versión activa

```txt
Motor local principal: local_cruncher_v3.py / flujo V4 generado por resultados.json
Web activa: V4-only stack
Salida principal: resultados.json
Fuente histórica web: Pakin remoto + fallback local
Deploy: Vercel
Repo: EdgarBravo99/fisicapapa
```

Aunque el archivo Python histórico se llama `local_cruncher_v3.py`, la web actual debe tratar el resultado como **V4** cuando el JSON venga con campos como:

```txt
model_version = V4 / V4.1
source = local_cruncher_v4_deep_stacking o equivalente
v4_score_kind / score_kind
```

### Flujo activo

```txt
Pakin CSV remoto + resultados.json generado localmente
        ↓
Vercel sirve index.html
        ↓
pakin-remote-loader.js carga históricos Melate/Revancha
        ↓
python-results-v4-compat.js + v4-primary-web.js + v4-hit-aware-web.js + v4-manual-science.js
        ↓
Generador V4 + Evaluador Manual V4 + paneles estadísticos
```

### Corte limpio de V3 en la web

El `index.html` fue actualizado para dejar de cargar los scripts V3 que estaban pisando el evaluador con `NET AVG 10.39` y `Sugerencias V3`.

Actualmente debe cargar solamente:

```html
<script src="data.js"></script>
<script src="engine.js"></script>
<script src="ui.js"></script>
<script src="pakin-remote-loader.js"></script>
<script src="python-results-v4-compat.js"></script>
<script src="v4-primary-web.js"></script>
<script src="v4-hit-aware-web.js"></script>
<script src="v4-manual-science.js"></script>
```

No debe cargar:

```txt
python-results-v3-compat.js
heatmap-fix.js
walk-forward-ui.js
v3-panels-bridge.js
v3-left-right-indicator.js
v3-manual-suggestion-diversity.js
v3-generator-elite-rank.js
```

Si en el navegador todavía aparece `NET AVG`, `Sugerencias V3` o cualquier texto V3, normalmente es caché de Vercel/navegador o un `index.html` viejo.

Usar en móvil:

```txt
https://tu-url.vercel.app/?v=11
```

O borrar datos del sitio / abrir incógnito.

---

## Archivos principales actuales

```txt
index.html                         Web principal V4-only
styles.css                         Estilos generales
data.js                            Dataset base, IndexedDB, parser CSV, historial local
engine.js                          Heurísticas base legacy usadas por algunos paneles
ui.js                              UI base: tabs, historial, favoritos, render inicial
pakin-remote-loader.js             Carga automática de Melate/Revancha desde pakinja/pakin
python-results-v4-compat.js        Compatibilidad resultados.json V4
v4-primary-web.js                  Bridge/paneles V4 principales
v4-hit-aware-web.js                Lecturas hit-aware / métricas V4
v4-manual-science.js               Evaluador manual V4 por componentes
resultados.json                    Salida que consume la web
local_cruncher_v3.py               Motor local histórico que genera resultados.json
```

### Legacy / histórico

Estos archivos existen por historial del proyecto, pero ya no deben guiar la web activa:

```txt
local_cruncher_v2.py
python-results-bridge.js
python-results-v3-compat.js
v3-panels-bridge.js
v3-left-right-indicator.js
v3-manual-suggestion-diversity.js
v3-generator-elite-rank.js
walk-forward-ui.js
heatmap-fix.js
fix_*.py
```

Los `fix_*.py` fueron patchers usados para aplicar cambios manuales durante el desarrollo. El objetivo final es absorber sus mejoras en el motor principal y dejar de depender de ellos.

---

## Fuente de datos histórica: Pakin

La web ya no debe depender de cargar CSV manual por dispositivo.

Archivo:

```txt
pakin-remote-loader.js
```

Carga automáticamente:

```txt
https://raw.githubusercontent.com/pakinja/pakin/master/Melate.csv
https://raw.githubusercontent.com/pakinja/pakin/master/Historico-Melate.csv
https://raw.githubusercontent.com/pakinja/pakin/master/Revancha.csv
https://raw.githubusercontent.com/pakinja/pakin/master/Historico-Revancha.csv
```

El parser fue corregido para formato por encabezados de Pakin:

```csv
CONCURSO,ID,R1,R2,R3,R4,R5,R6,BOLSA,FECHA,...
```

Para Melate también puede existir `R7`, que se trata como adicional y no como uno de los 6 naturales.

La web debe mostrar algo similar a:

```txt
Pakin remoto activo: XXXX Revancha / XXXX Melate
```

Si móvil sigue mostrando solo 42 sorteos, revisar caché o que `pakin-remote-loader.js` sí esté cargado.

---

## resultados.json: contrato activo V4

`resultados.json` es la fuente de verdad de predicciones y auditoría para la web.

Campos esperados o útiles:

```json
{
  "last_update": "timestamp",
  "source": "local_cruncher_v4_deep_stacking | local_cruncher_v3...",
  "model_version": "V4 | V4.1-hit-aware",
  "game_mode": "melate | revancha",
  "game_label": "Melate | Revancha",
  "score_kind": "optuna_weighted_net_score",
  "v4_score_kind": "...",
  "historical_forgetting": {},
  "data_source": {},
  "drift_detected": false,
  "procedure_log": "...",
  "optuna_audit": {},
  "walk_forward": {},
  "physics_summary": {},
  "expert_weights": {},
  "number_scores": {},
  "manual_suggestion_seed": [],
  "generator_pool": [],
  "top_combinations": [],
  "postmortem_feedback": {}
}
```

### `number_scores`

Mapa por número del score calculado por el motor.

Ejemplo:

```json
"number_scores": {
  "1": 0.134,
  "2": 0.198,
  "17": 0.241
}
```

La web convierte escalas `0-1` a `0-100` cuando aplica.

### `manual_suggestion_seed`

Ranking por número con explicación.

Ejemplo:

```json
{
  "number": 17,
  "score": 74.2,
  "winner_component": "physical",
  "winner_component_human": "física de esferas",
  "reason": "...",
  "expert_raw": {
    "physical": 0.72,
    "xgboost": 0.51,
    "fourier": 0.44,
    "structural": 0.61
  }
}
```

Lo usa `v4-manual-science.js` para:

```txt
Score por número
Impulsor dominante
Motivo
Sugerencias V4
Física de esferas si viene en expert_raw
```

### `generator_pool`

Pool de combinaciones generado localmente por el cruncher.

Ejemplo:

```json
{
  "numbers": [5, 12, 18, 33, 41, 55],
  "net_score": 0.2072,
  "score_percent": 20.72,
  "human_explanation": "...",
  "plain_route": "...",
  "number_explanations": []
}
```

Lo usa la web para:

```txt
Generador V4
Alineación pool
Sugerencias V4
Coincidencias
Forense
Indicadores de tendencia
```

### `walk_forward.rows`

Validación OOS / backtesting ciego.

Ejemplo:

```json
{
  "draw_id": "4213",
  "actual": [7, 29, 39, 43, 47, 49],
  "predicted_top6": [1, 8, 12, 20, 31, 45],
  "predicted_top10": [],
  "hits": 0,
  "hits_top10": 1,
  "mse": 0.123,
  "drift_detected": false
}
```

Debe usarse para evaluar si el modelo mejora realmente contra baseline, no solo por score visual.

---

## Evaluador Manual V4

Archivo activo:

```txt
v4-manual-science.js
```

Objetivo: reemplazar definitivamente el viejo `NET AVG` V3 por una lectura V4 por componentes.

### Calificación V4

La calificación manual V4 combina:

```txt
40% Score por números
24% Balance estructural
16% Física de esferas
20% Alineación con generator_pool
```

### Componentes visibles

Debe mostrar:

```txt
CALIFICACIÓN V4
Score por números
Física de esferas
Balance estructural
Alineación pool
Paridad
Izquierda/Derecha
Décadas
Suma
Consecutivos
Score V4 por número
Impulsor
Motivo
Sugerencias V4 por componentes
```

### Balance estructural

Se recalcula por combinación. No debe ser constante.

Factores:

```txt
Paridad: ideal cerca de 3 pares / 3 impares
Izquierda/Derecha: ideal cerca de 3 bajos / 3 altos, usando 1-28 y 29-56
Décadas: cobertura de décadas
Suma: cercanía a zona histórica media
Consecutivos: penalización por exceso de consecutivos
```

### Sugerencias V4

Las sugerencias deben ser múltiples, no una sola, y deben evaluar:

```txt
Número débil actual
Número fuerte candidato
Ganancia en calificación V4 total
Score por números
Balance estructural
Física
Alineación con pool
Soporte en generator_pool top N
Impulsor del candidato
```

No deben decir `Sugerencias V3`.

---

## Generador V4

El generador web ya no debe ejecutar Monte Carlo pesado en navegador.

Debe tomar combinaciones desde:

```txt
generator_pool de resultados.json
```

Los botones:

```txt
Generar 5
Generar 10
Limpiar
```

No deben mostrar ni depender de:

```txt
Montecarlo 5000x del navegador
Migración Cruzada legacy
```

La calificación de cada combinación generada debe usar el mismo criterio del evaluador V4:

```txt
Score por números + física + estructura + alineación pool
```

---

## Motor local / cruncher

El motor local sigue siendo el responsable de generar `resultados.json`.

Archivo histórico:

```txt
local_cruncher_v3.py
```

Durante el desarrollo evolucionó a un flujo V4/V4.1 con:

```txt
buffer reciente
walk-forward OOS
Optuna
XGBoost
Fourier
Bayes
física de esferas
estructura
Markov
LSTM / memoria secuencial
Transformer / deep stacking en V4.1 si está presente
postmortem feedback
Monte Carlo local
```

### Principio actual

El navegador solo visualiza y analiza. La generación pesada debe venir del cruncher local:

```txt
local_cruncher_v3.py → resultados.json → git push → Vercel web
```

### Git sync

El script intenta subir automáticamente `resultados.json` si Git está disponible:

```txt
git add resultados.json
git commit -m "Update predictions"
git push origin main
```

Si aparece:

```txt
"git" no se reconoce como un comando interno o externo
```

instalar Git, reiniciar PowerShell y verificar:

```powershell
git --version
```

Comandos manuales:

```powershell
git add resultados.json
git commit -m "Update predictions"
git push origin main
```

---

## Retroalimentación post-sorteo

Se agregó un patcher para auditar `resultados.json` anterior contra un sorteo nuevo en CSV:

```txt
fix_v3_postmortem_feedback.py
```

Objetivo:

```txt
Leer resultados.json anterior
Detectar sorteo nuevo
Comparar top_combinations y generator_pool contra el resultado real
Medir hits, fallos, números acertados y números fallidos
Ajustar suavemente multiplicadores por experto
Exportar postmortem_feedback
```

Debe aprender del error sin sobre-reaccionar a un solo sorteo.

---

## Evaluación objetiva de mejora

No confiar solo en `max_net_score_found` o en scores visuales.

Métricas importantes:

```txt
avg_hits_top6
avg_hits_top8
avg_hits_top10
max_hits_top6
zero_hit_rate
calibration_r2
brier_score
mse
comparación contra baseline aleatorio
```

Baseline aproximado para Melate/Revancha 6 de 56:

```txt
Top6 esperado random ≈ 6 * 6 / 56 = 0.6429 hits
Top10 esperado random ≈ 10 * 6 / 56 = 1.0714 hits
```

Si el walk-forward está debajo de eso, la arquitectura puede ser más sofisticada pero no necesariamente más efectiva.

---

## Problemas conocidos y diagnóstico

### Sigue apareciendo `NET AVG 10.39`

Causa probable:

```txt
index.html viejo en caché
scripts V3 todavía cargados
Vercel no desplegó último commit
navegador móvil con datos cacheados
```

Solución:

```txt
Verificar que index.html no cargue scripts v3-*
Abrir con ?v=11 o superior
Borrar datos del sitio
Abrir incógnito
Esperar deploy de Vercel
```

### Móvil sigue mostrando 42 sorteos

Causa probable:

```txt
pakin-remote-loader.js no cargó
parser remoto falló
caché móvil
```

Solución:

```txt
Revisar banner Pakin remoto activo
Abrir con cache-bust
Borrar datos del sitio
```

### `nvrtc*.dll`

Si CuPy falla:

```txt
Failure finding "nvrtc*.dll"
```

Verificar CUDA:

```powershell
echo $env:CUDA_PATH
Get-ChildItem "$env:CUDA_PATH\bin\nvrtc*.dll"
```

También puede usarse fallback NumPy si el script lo tiene integrado.

### Vercel paquete demasiado grande

Evitar subir entornos Python, dependencias pesadas, `.venv`, caches, `node_modules` innecesarios o modelos pesados.

La web debe ser estática y ligera. El cruncher corre local.

---

## Comandos recomendados

Actualizar repo:

```powershell
git pull origin main
```

Ejecutar cruncher local:

```powershell
py -X utf8 .\local_cruncher_v3.py
```

Subir resultados manualmente si el auto-git falla:

```powershell
git add resultados.json
git commit -m "Update predictions"
git push origin main
```

Abrir web rompiendo caché:

```txt
https://tu-url.vercel.app/?v=11
```

---

## Checklist para continuar en otra conversación

Pegar este bloque si se abre una conversación nueva:

```txt
Repo: EdgarBravo99/fisicapapa
Proyecto: Melate Pro V7 / Fisicapapa
Estado actual: Web V4-only
Motor local: local_cruncher_v3.py, pero resultados.json puede venir como V4/V4.1
Salida principal: resultados.json
Fuente histórica web: Pakin remoto vía pakin-remote-loader.js
index.html debe cargar solo stack V4:
  data.js
  engine.js
  ui.js
  pakin-remote-loader.js
  python-results-v4-compat.js
  v4-primary-web.js
  v4-hit-aware-web.js
  v4-manual-science.js
No volver a activar scripts V3:
  python-results-v3-compat.js
  v3-panels-bridge.js
  v3-left-right-indicator.js
  v3-manual-suggestion-diversity.js
  v3-generator-elite-rank.js
Problema histórico: NET AVG 10.39 y Sugerencias V3 venían de scripts legacy pisando el evaluador.
Objetivo actual: que toda la web use ciencia de datos V4, calificación V4 por componentes, física de esferas, izquierda/derecha, balance estructural, alineación con generator_pool y sugerencias V4.
```

---

## Pendientes técnicos sugeridos

- Renombrar definitivamente `local_cruncher_v3.py` a `local_cruncher_v4.py` cuando el flujo V4 esté estable.
- Crear `v4-clean-app.js` como controlador único para generador/evaluador y reducir dependencia de `ui.js` legacy.
- Mover scripts V3 a una carpeta `legacy/` o eliminarlos del deploy.
- Agregar prueba automática simple que falle si `index.html` contiene `v3-` o `python-results-v3`.
- Agregar versión visible de `resultados.json` en la web.
- Mostrar fecha `last_update` y `game_mode` en el header.
- Crear comparación A/B automática: V3 legacy vs V4 vs baseline random vs frecuencia reciente.
- Validar que `manual_suggestion_seed`, `number_scores` y `generator_pool` siempre existan antes de desplegar.
