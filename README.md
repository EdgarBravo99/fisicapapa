# Melate Pro V7 / Fisicapapa

## Estado activo V4.2

Esta rama deja como flujo vigente **Web V2 + Cruncher V4.2**. Las secciones historicas de este README siguen como contexto, pero la referencia operativa actual es:

```txt
Runner oficial: local_cruncher_v4_2_calibrated.py
Motor base: local_cruncher_v4_deep_stacking.py
Salida principal: resultados.json
Web activa: index.html + v4-clean-app.js + v4-results-panels.js + v4-under40-verifier.js + v4-system-diagnostics.js + v4-combo-comparator.js + v4-visual-system.css
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

Sistema local + web para analisis cuantitativo, auditoria y visualizacion de combinaciones de Melate/Revancha.

Estado activo: **Web V2 / V4.2-only**.

> Uso informativo y experimental. Los scores son rankings internos del modelo y metricas de auditoria; no son probabilidades reales garantizadas ni recomendacion financiera.

## Stack activo

La raiz del proyecto queda reservada para la version activa V4.2 y su documentacion:

```txt
index.html
v4-clean-app.js
v4-results-panels.js
v4-under40-verifier.js
v4-system-diagnostics.js
v4-combo-comparator.js
v4-feedback-memory-panel.js
v4-decision-audit-panel.js
v4-visual-system.css
data.js
pakin-remote-loader.js
local_cruncher_v4_2_calibrated.py
local_cruncher_v4_deep_stacking.py
v4_feedback_memory.py
v4_github_sync.py
resultados.json
CODEX_HANDOFF_V4_2.md
README.md
```

Tambien se conservan en raiz los archivos de configuracion de deploy (`vercel.json`, `.vercelignore`).

## Regla V4.2-only

No reactivar V3 ni scripts historicos desde `index.html`.

La web debe aceptar unicamente JSON V4.2 con:

```json
{
  "model_version": "V4.2-oos-feedback-loop",
  "walk_forward": {
    "feedback_loop": {
      "version": "V4.2"
    }
  }
}
```

Si `walk_forward.feedback_loop.version` no es `"V4.2"`, la web debe detenerse con error visible.

## Web activa

`index.html` carga solamente:

```html
<script src="data.js"></script>
<script src="pakin-remote-loader.js"></script>
<script src="v4-clean-app.js"></script>
<script src="v4-results-panels.js"></script>
<script src="v4-under40-verifier.js"></script>
<script src="v4-system-diagnostics.js"></script>
<script src="v4-combo-comparator.js"></script>
<script src="v4-feedback-memory-panel.js"></script>
<script src="v4-decision-audit-panel.js"></script>
```

Responsabilidades:

- `v4-clean-app.js`: carga `resultados.json`, valida contrato V4.2, inicializa la app y expone `evaluateManualComboV4()`.
- `v4-results-panels.js`: renderiza combinaciones, top de numeros y panel fisico V4.2.
- `v4-under40-verifier.js`: agrega auditoria visual de macroestructura `<40`; no modifica score ni cruncher.
- `v4-system-diagnostics.js`: valida calidad de `resultados.json`, muestra estado del sistema y agrega explicabilidad manual visual.
- `v4-combo-comparator.js`: mantiene el comparador personal temporal en localStorage.
- `v4-feedback-memory-panel.js`: muestra memoria tipo examen y el historial GitHub de `resultados.json`.
- `v4-decision-audit-panel.js`: muestra diversidad MMR, benchmark lite y evento fisico como diagnostico read-only.
- `v4-visual-system.css`: aplica el sistema visual Personal Quant Desk sin tocar logica matematica.
- `pakin-remote-loader.js`: carga historicos remotos de Pakin para Melate/Revancha.
- `data.js`: dataset y utilidades base para la web.

## Cruncher activo

Runner recomendado:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Ese runner importa:

```txt
local_cruncher_v4_deep_stacking.py
```

No modificar la logica del cruncher sin medir primero. En particular, conservar:

- validacion y salida V4.2 en `resultados.json`;
- fisica calibrada del sorteo 4214 del `2026-05-17`;
- reset de vida util despues del sorteo 4213;
- manejo visible de errores y `cruncher_error.log`;
- correccion de `mat()` para la bola 56.

## Salida activa

`resultados.json` es la fuente de verdad para la web.

Contrato minimo esperado:

```json
{
  "source": "local_cruncher_v4_2_oos_feedback_loop",
  "model_version": "V4.2-oos-feedback-loop",
  "score_kind": "v4_2_deep_stacking_meta_score",
  "walk_forward": {
    "feedback_loop": {
      "enabled": true,
      "version": "V4.2"
    },
    "rows": []
  },
  "physics_summary": {},
  "manual_suggestion_seed": [],
  "generator_pool": [],
  "top_combinations": [],
  "number_scores": {}
}
```

## Carpeta legacy

Los scripts historicos, patchers, hotfixes, motores previos, UI V3/V4.1 y archivos auxiliares no activos fueron movidos a:

```txt
legacy/
```

No fueron borrados. Quedan disponibles para consulta historica, pero no deben cargarse desde la web ni usarse como flujo principal.

`legacy/` esta excluida del deploy de Vercel.

## Flujo recomendado

Actualizar predicciones:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Menu del runner calibrado:

```txt
[1] Ejecutar pipeline V4.3 completo
[2] Inspeccionar resultados.json
[3] Sincronizar resultados con GitHub
[4] Salir
```

La opcion `[1]` intenta importar historico, calificar memoria y correr el pipeline normal. Al final pregunta si quieres subir resultados a GitHub.

Subir resultados manualmente:

```powershell
git add resultados.json
git commit -m "Update V4.2 calibrated predictions"
git push origin main
```

Ver web con cache-bust:

```txt
https://tu-deploy.vercel.app/?v=42
```

## Continuidad

El contexto operativo completo vive en:

```txt
CODEX_HANDOFF_V4_2.md
```

Ese archivo manda sobre notas historicas: V4.2-only, no V3, no reglas nuevas dentro del cruncher sin validacion OOS.

## V4.4 Recent Windows, Manual Evaluator y automatizacion

V4.4 conserva a V4.2 como motor protegido y a V4.3 como fallback legacy. La capa V4.4 trabaja sobre artefactos generados y mantiene `production_status: review_default`.

Comando local V4.4:

```powershell
py tools\v4_refresh.py --game revancha --scrape --reconstruct --full-signals --recent-composition --construct
```

El perfil reciente ahora calcula tres ventanas:

- `windows["5"]`: micro-alerta reciente. Sirve para detectar cambios cortos, pero no debe dominar el constructor.
- `windows["20"]`: tendencia corta con peso medio.
- `windows["30"]`: perfil reciente base y compatibilidad legacy de la raiz del JSON.

`recent_regime_summary` compara ventanas y describe si hay cambio de micro-regimen. `window_5_vs_20_shift` indica si la ventana 5 contradice o cambia contra la ventana 20. `window_20_vs_30_shift` hace lo mismo entre tendencia corta y base reciente. Si hay empate en campos dominantes, se conserva el campo singular y se agregan listas plurales como `dominant_sum_bands`, `dominant_parities`, `dominant_presence_signatures` o `dominant_immediate_overlaps`.

El cockpit V4.4 incluye un evaluador manual read-only. Este evaluador:

- calcula suma, banda, paridad, firmas de bloque y repetidos inmediatos;
- lee señales ya cargadas desde los JSON V4.4;
- compara contra ventanas 5, 20 y 30;
- no escribe archivos;
- no usa `resultados.json`;
- no modifica scores, priors ni memoria.

Archivo manual opcional de fisica/mantenimiento:

```txt
v4_physics_maintenance_notes.json
```

Estructura operativa inicial:

```json
{
  "production_status": "review_default",
  "generated_at": "manual",
  "notes": []
}
```

Ejemplo para uso manual futuro, no se debe colocar automaticamente por pipeline:

```json
{
  "date": "2026-05-20",
  "draw": 4210,
  "type": "maintenance",
  "description_es": "Posible mantenimiento o cambio operativo reportado manualmente.",
  "confidence": "manual_note"
}
```

Estas notas son solo lectura en la web. No afectan constructor, senales ni priors.

GitHub Actions automatiza el pipeline V4.4 en:

```txt
.github/workflows/v44_pipeline.yml
```

Corre lunes, jueves y sabado a las 09:00 UTC para dar margen posterior a sorteos de domingo, miercoles y viernes. Tambien puede correrse manualmente desde GitHub con `workflow_dispatch`. El workflow usa `python`, corre pipeline y smoke test, y solo hace commit de artefactos generados permitidos si el smoke pasa. Nunca debe commitear `resultados.json`, `v4_replay_memory.json`, motores V4.2 ni `v4_physics_maintenance_notes.json`.

Todo el flujo sigue siendo de revision interna. No hay promesa de resultado.

## V4.4 Video Weight Observation Lab

PR #42 agrega un laboratorio separado para localizar videos de sorteos, extraer evidencia visual de pesaje de bolas y dejar observaciones auditables en modo `review_default`.

Este laboratorio no afecta constructor, scores, boletos, senales, priors ni memoria. Sus salidas son evidencia visual pendiente de revision manual.

Buscar video automaticamente:

```powershell
py tools\video_weight_lab\youtube_stream_finder.py --draw 4218 --channel-url https://www.youtube.com/@LN_electronicos/streams --output v4_video_weight_source.json
```

Correr el pipeline completo:

```powershell
py tools\video_weight_lab\run_video_weight_lab.py --draw 4218 --channel-url https://www.youtube.com/@LN_electronicos/streams --download true --fps-sample 1
```

Dependencias opcionales:

```txt
yt-dlp              localizar/listar/descargar videos de YouTube
opencv-python      extraer frames y crops
pytesseract        OCR de display y bola
tesseract          binario del sistema usado por pytesseract
```

Limitaciones:

- Si `yt-dlp` no esta disponible, el localizador falla con mensaje claro y se puede usar `--video-url` manual.
- Si `opencv-python` no esta disponible, no se extraen frames ni crops.
- Si `pytesseract` o Tesseract no estan disponibles, el OCR queda como revision manual.
- La bola puede estar girada, parcial o en recuadro pequeno.
- Las observaciones se guardan como `v4_ball_weight_observations.json` y el cockpit las muestra como fuente opcional.
- La evidencia visual no modifica constructor, scores, senales ni priors.

## Pipeline V4.3.1 de memoria tipo examen

V4.3.1 no cambia el runner oficial ni crea otro programa principal. El flujo sigue entrando por:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Menu activo:

```txt
[1] Ejecutar pipeline V4.3 completo
[2] Inspeccionar resultados.json
[3] Sincronizar resultados con GitHub
[4] Salir
```

La opcion `[1]` hace automaticamente:

```txt
git pull seguro si aplica
importacion historica de resultados.json con git log/git show
archivo local pre-run en resultados_archive/
deteccion de CSV revelado
calificacion de snapshots posibles
analisis historico crudo
construccion de memory_prior
hook pre-Monte-Carlo si hay evidencia suficiente
pipeline normal
auditoria en resultados.json
pregunta de sync a GitHub
```

La memoria persistente vive en `v4_feedback_memory.py` y, cuando existe al menos un examen real calificado, en `v4_feedback_memory.json`. El analisis crudo vive en `v4_history_analysis.json` cuando puede generarse.

Modelo mental:

```txt
resultados.json historico = prediccion pasada del cruncher
CSV historico actualizado = verdad revelada
v4_feedback_memory.json = libreta de calificaciones
v4_history_analysis.json = diagnostico de errores historicos
memory_prior = sesgo suave pre-Monte-Carlo
```

Reglas anti-leakage:

- Nunca usar `resultados.json` como verdad.
- Para calificar una prediccion 4214 contra un target 4215, el CSV ya debe contener 4215 como sorteo revelado.
- Nunca usar 4215 para generar la prediccion 4215.
- Si no hay sorteo target posterior en el CSV, la memoria muestra warning y no inventa resultados.
- Si hay menos de 3 records reales unicos calificados, la memoria queda en modo diagnostico y no altera simulacion.
- Records mock solo sirven para pruebas y nunca activan memoria aplicada en uso normal.
- `resultados_archive/index.json` es inventario tecnico: no es verdad, no es scoring y no activa aprendizaje.

Modos:

```txt
diagnostic_only                 sin prior aplicado
pre_monte_carlo_memory_prior    prior instalado antes de Monte Carlo
```

Fuerza progresiva del prior:

```txt
3-4 records reales: 25%
5-7 records reales: 50%
8-10 records reales: 75%
10+ records reales: 100%
```

El ajuste maximo absoluto por numero es +/-5%. El prior no elimina numeros, no fuerza numeros, no toca el entrenamiento profundo y no reemplaza el modelo base.

## Replay historico V4.3.2

PR #19 agrega un laboratorio de replay anti-leakage para generar mas examenes sin esperar nuevos sorteos reales. No crea otro motor y no reemplaza el runner oficial.

Modelo mental:

```txt
Live memory:
predicciones reales guardadas antes del sorteo.

Replay memory:
predicciones generadas hoy simulando el pasado con CSV truncado.

Legacy hindsight:
snapshots viejos con resultado real embebido; solo diagnostico.
```

El replay usa el motor principal asi:

```txt
CSV completo -> CSV temporal con sorteos < target_draw
CSV temporal -> load_draws(path) del motor principal
motor principal -> resultados.json temporal
replay lab -> califica contra target_draw real del CSV completo
```

Ejemplo de replay pequeno:

```powershell
py .\tools\v4_historical_replay_lab.py --csv revancha.csv --game-mode revancha --start-draw 4210 --end-draw 4214 --max-targets 3 --intensity replay_fast
```

Dry-run seguro:

```powershell
py .\tools\v4_historical_replay_lab.py --csv revancha.csv --game-mode revancha --start-draw 4210 --end-draw 4214 --max-targets 3 --intensity replay_fast --dry-run
```

Intensidad:

- `replay_fast`: setea variables de entorno antes de cargar el engine para bajar costo.
- `replay_medium`: costo intermedio.
- `replay_full`: no reduce parametros.

Importante: `local_cruncher_v4_deep_stacking.py` lee `MELATE_V4_MC_TOTAL`, `MELATE_V4_MC_BATCH` y `MELATE_V4_OOS_STEPS` al importarse. Por eso el replay lab setea esas variables antes de llamar `load_engine()` y restaura el entorno en `finally`.

El replay siempre corre en un `TemporaryDirectory`, porque el motor escribe `resultados.json` en el working directory actual. El lab captura ese archivo, lo copia a `replay_archive/` y restaura el `cwd`.

Replay memory vive en `v4_replay_memory.py`. Si existen records replay reales, puede escribir `v4_replay_memory.json` y `v4_replay_analysis.json`. Por default el replay prior es `shadow_replay_prior`: se calcula y se muestra, pero no se aplica. `ENABLE_REPLAY_PRIOR = False`.

### Calidad del replay prior V4.3.3

PR #19 generaba replay memory y shadow prior. PR #20 mejora la calidad del shadow prior para evitar castigar numeros solo porque no salieron.

Antes, casi cualquier numero con score positivo que no aparecia podia sumar como sobreestimado. Eso era demasiado amplio porque en cada sorteo aparecen 6 numeros y fallan 50.

Nuevo criterio:

```txt
overestimated = numero top-ranked / high-percentile que fallo
underestimated = numero low-ranked / low-percentile que si aparecio
```

El aggregate ahora deriva, aun para records viejos:

- rank por numero;
- percentile;
- bucket `p0_p20`, `p20_p40`, `p40_p60`, `p60_p80`, `p80_p90`, `p90_p100`;
- `score_bucket_performance`;
- `rank_band_performance`;
- `calibration_summary`;
- evidencia ponderada `overestimated_weighted` / `underestimated_weighted`.

`compute_replay_prior()` usa evidencia ponderada:

```txt
weighted_underestimated - weighted_overestimated
```

Aunque existan 30+ records, el prior queda diagnostic-only si los buckets altos no muestran mejor hit-rate que los buckets medios.

Recalcular aggregate sin regenerar replays:

```powershell
py .\v4_replay_memory.py --rebuild
```

El replay prior sigue apagado por defecto. No debe activarse hasta revisar `prior_quality`.

Reglas replay:

- minimo 30 records replay limpios para shadow prior;
- maximo +/-2% con 30-59 records;
- maximo +/-3% con 60+ records;
- no cuenta como live memory;
- no incrementa `valid_real_records_used`;
- no fuerza numeros;
- no elimina numeros;
- no cambia `score_kind`;
- no se presenta como garantia.

## Decision Audit Pack V4.4

PR #21 agrega un paquete de diagnostico read-only para responder tres preguntas practicas antes de activar cualquier senal nueva:

```txt
1. Mis top_combinations estan clonadas?
2. El cruncher supera baselines simples o solo ruido sofisticado?
3. El sorteo 4215 sugiere un evento fisico que deba vigilarse?
```

Todo el paquete queda en `diagnostic_only`. No toca `local_cruncher_v4_deep_stacking.py`, no cambia `score_kind`, no activa replay prior y no modifica `resultados.json`.

### Diversity-Aware Combination Selector

Genera `v4_diversity_output.json` desde `top_combinations` usando MMR:

```powershell
py .\tools\v4_diversity_selector.py --input resultados.json --output v4_diversity_output.json
```

La salida conserva los scores originales, ancla el top #1 original y calcula overlap/Jaccard para detectar boletos clonados. Es ranking diversificado, no promesa de resultado.

### Baseline Benchmark Lite

Genera `v4_baseline_benchmark.json` desde `v4_replay_memory.json` si existe:

```powershell
py .\tools\v4_baseline_benchmark.py --replay-memory v4_replay_memory.json --output v4_baseline_benchmark.json
```

Si `v4_replay_memory.json` no existe, el reporte no falla: deja `records_count = 0`, `signal_quality = unknown` y `recommendation = diagnostic_only`. Si no hay datos suficientes para `frequency_baseline` o `recency_baseline`, esos baselines aparecen como `unavailable` con razon clara. Brier formal queda desactivado porque los scores internos no son probabilidades calibradas.

### Physics Regime Tracker

Registra el hallazgo manual del sorteo 4215 en `sphere_weight_history.json` y genera `v4_physics_regime_analysis.json`:

```powershell
py .\tools\v4_physics_regime_audit.py --weights sphere_weight_history.json --output v4_physics_regime_analysis.json
```

El draw 4215 queda como `suspected_physics_event_not_confirmed`: evento fisico sospechoso, no confirmado. No crea physics prior, no ajusta numeros y con un solo registro no estima periodicidad.

### Comando integrado

```powershell
py .\tools\v4_decision_audit_pack.py
```

Corre diversidad, benchmark y fisica. Si un modulo falla, reporta warning y sigue con los demas. No consulta GitHub y no toca el motor base.

Para que replay pueda influir en el futuro se requiere:

- benchmark favorable contra random/frequency/recency;
- `ranking_signal_quality >= moderate`;
- `prior_quality = usable_shadow`;
- regimen fisico estable o segmentado;
- validacion con datos posteriores;
- activacion explicita, nunca por default.

## Replay Qualification Gate V4.4

PR #22 convierte los diagnosticos de PR #21 en una compuerta explicita de evidencia. El replay sigue bloqueado hasta que todos los gates pasen. Esta compuerta no activa prior y no modifica simulaciones.

```powershell
py .\tools\v4_candidate_pool_audit.py --input resultados.json --output v4_candidate_pool_audit.json
py .\tools\v4_replay_qualification_gate.py --output v4_replay_qualification.json
py .\tools\v4_decision_slate.py --output v4_decision_slate.json
py .\tools\v4_decision_audit_pack.py
```

### Candidate Pool Audit

`tools/v4_candidate_pool_audit.py` revisa pools ya existentes dentro de `resultados.json`:

```txt
top_combinations
candidate_combinations
generated_combinations
monte_carlo_combinations
combination_pool
manual_suggestion_seed
generator_pool
```

Solo cuenta filas con exactamente 6 numeros validos entre 1 y 56. No inventa combinaciones, no lee CSV y no usa memoria. Si `top_combinations` esta clonado y no hay pool amplio, el problema esta aguas arriba en la generacion de candidatos. Si existe un pool amplio, el selector puede usar `--pool auto` para diversificar desde datos ya presentes.

### Replay Qualification Gate

`tools/v4_replay_qualification_gate.py` lee memoria replay, benchmark, diversidad, candidate pool y fisica. Bloquea `can_influence_future_prior` si falta evidencia:

- menos de 30 records limpios;
- `ranking_signal_quality` debil;
- `prior_quality` distinto de `usable_shadow`;
- benchmark `unknown` o `weak`;
- diversidad sin pool util;
- evento fisico sospechoso sin regimen estable.

Aunque todo pase, este PR solo marca `eligible_for_future_experiment = true`. Nunca aplica prior.

### Decision Slate

`tools/v4_decision_slate.py` crea `v4_decision_slate.json`: un set de revision diagnostico, no probabilidad. Usa combinaciones existentes:

1. `diversified_combinations` si hay mejora;
2. `diversified_combinations` con warning si la diversidad sigue baja;
3. `top_combinations` como fallback.

La web muestra Replay Qualification, Candidate Pool y Decision Slate en el panel de Decision Audit. El frontend solo lee JSON: no recalibra, no usa `localStorage` para auditoria y no modifica `resultados.json`.

## Physics Timeline & Local Audit State V4.4

PR #24 agrega herramientas diagnosticas para cuidar el historial fisico y revisar el estado local antes de correr o subir outputs. Todo sigue `diagnostic_only`: no activa physics prior, replay prior, Monte Carlo ni cambios de score.

### Agregar pesos nuevos

Para agregar un nuevo sorteo sin editar JSON a mano:

```powershell
py .\tools\v4_add_sphere_weights.py --draw 4216 --game-mode revancha --winning "1,2,3,4,5,6" --weights-file sphere_weights_4216.json
```

Tambien se puede usar `--weights "1=4.56,2=4.52,..."` si conviene. El comando valida exactamente 56 pesos, 6 ganadores unicos, numeros 1-56 y deduplica por `draw_id + game_mode`. Si ya existe el draw, no sobrescribe salvo `--force`. El status por defecto es `observed_weight_record`; `suspected_physics_event_not_confirmed` solo debe pasarse explicitamente.

### Timeline fisico

```powershell
py .\tools\v4_physics_timeline.py --weights sphere_weight_history.json --output v4_physics_regime_timeline.json
```

`can_estimate_periodicity` queda en `false` con menos de 5 registros porque aun no hay suficientes shifts preliminares. Con 5+ registros calcula shifts simples. Con 10+ puede marcar periodicidad preliminar posible. Con 20+ puede quedar elegible para metodos futuros de changepoint. BOCPD y ruptures quedan fuera de este PR.

### Auditoria local

```powershell
py .\tools\v4_audit_state.py
```

Genera `v4_audit_state.json` sin consultar GitHub. Revisa rama actual, cambios sin commit, conflictos, archivos criticos, outputs generados, records fisicos, replay qualification, `ENABLE_REPLAY_PRIOR`, `feedback_calibrator.py` y runners sospechosos. Antes de correr pipeline o subir outputs, revisa que la recomendacion sea `ok` o entiende los warnings.

El comando integrado tambien corre timeline y audit state:

```powershell
py .\tools\v4_decision_audit_pack.py
```

## Benchmark Hardening + Calibration Diagnostics V4.4

PR #25 endurece el benchmark replay sin activar ningun prior. El benchmark lite da una primera lectura; este paquete agrega comparacion contra baselines, calibracion por ranking/buckets, evaluacion de diversidad contra el top original, bootstrap simple y una compuerta de resumen.

```powershell
py .\tools\v4_benchmark_hardening.py --output v4_benchmark_hardening.json
py .\tools\v4_calibration_diagnostics.py --output v4_calibration_diagnostics.json
py .\tools\v4_diversified_vs_original_eval.py --output v4_diversified_vs_original_eval.json
py .\tools\v4_benchmark_stability.py --output v4_benchmark_stability.json
py .\tools\v4_benchmark_summary_gate.py --output v4_benchmark_summary.json
py .\tools\v4_decision_audit_pack.py
```

El hardening pregunta si el cruncher supera random, frecuencia y recencia con margen util. Si alguna baseline no tiene datos suficientes, queda `available=false` con razon clara; no se inventan historiales.

La calibracion de ranking revisa si `top6`, `top10`, `top20`, `top40` y `rest` se comportan como deberian. Tambien revisa buckets por percentil cuando hay scores por numero. `ranking_signal_quality` solo puede subir si los grupos altos superan random/rest con consistencia.

La evaluacion diversificada compara `pure_rank_top`, `diversified_top` y `balanced_review_set` sin generar combinaciones nuevas. Puede medir cobertura y overlap aunque no haya hits comparables; si no puede medir hits contra targets, lo declara explicitamente.

El bootstrap simple evita autoengano por muestra pequena. Si el intervalo 95% cruza 0, la ventaja no es estable. Brier formal sigue desactivado porque los scores internos no son probabilidades calibradas.

Para que replay sea elegible a un experimento futuro se requiere benchmark favorable contra random/frequency/recency, `ranking_signal_quality >= moderate`, ventaja estable en bootstrap, buckets altos superando al resto y slate diversificado que mejore best-of-N sin perdida excesiva.

Aunque esas condiciones pasaran, PR #25 mantiene `recommendation = diagnostic_only`: no activa replay prior, physics prior, live prior, Monte Carlo ni cambia `score_kind`.

## Replay Failure Analysis V4.4

PR #26 analiza por que el replay sigue debil despues de ampliar la muestra. No hace mas replay, no activa prior y no cambia el motor: solo descompone la falla en ventanas, ranking, frecuencia y targets concretos.

```powershell
py .\tools\v4_replay_window_diagnostics.py --output v4_replay_window_diagnostics.json
py .\tools\v4_ranking_inversion_audit.py --output v4_ranking_inversion_audit.json
py .\tools\v4_frequency_dominance_audit.py --output v4_frequency_dominance_audit.json
py .\tools\v4_draw_failure_report.py --output v4_draw_failure_report.json
py .\tools\v4_signal_decomposition_summary.py --output v4_signal_decomposition_summary.json
py .\tools\v4_decision_audit_pack.py
```

`v4_replay_window_diagnostics.py` separa los records por ventanas de draws. Si todas las ventanas quedan debiles, la falla es global; si solo falla un tramo, la falla puede ser de regimen o periodo.

`v4_ranking_inversion_audit.py` revisa si el ranking esta plano o invertido. Un ranking `weak`, `flat` o `inverted` significa que los numeros altos no estan ganando de forma consistente contra random/rest, asi que no debe usarse para modificar simulacion.

`v4_frequency_dominance_audit.py` reconstruye una frecuencia progresiva usando solo targets anteriores dentro del replay. Si frequency vence al cruncher, falta senal o calibracion: no se debe convertir esa diferencia en prior sin entender el origen.

`v4_draw_failure_report.py` lista target por target: hits top10/top20, numeros ganadores omitidos, numeros sobreestimados que fallaron y numeros subestimados que salieron. Esto sirve para ver fallas extremas sin inventar combinaciones.

`v4_signal_decomposition_summary.py` integra todo y mantiene `prior_should_remain_blocked = true`. Random/frequency ganando, ranking weak o falla global bloquean replay prior. El siguiente paso recomendado es mejorar generacion de senal o ranking antes de hacer mas replay o tocar Monte Carlo.

## Ranking Repair Experiment V4.4

PR #27 prueba reparaciones externas de ranking despues de confirmar 60 replay records con falla global, ranking invertido y frequency dominance. Es un experimento read-only: no modifica `v4_replay_memory.json`, no cambia scores oficiales, no toca el motor y no activa prior.

```powershell
py .\tools\v4_ranking_repair_experiment.py --output v4_ranking_repair_experiment.json
py .\tools\v4_ranking_repair_window_stability.py --output v4_ranking_repair_window_stability.json
py .\tools\v4_combination_repair_experiment.py --output v4_combination_repair_experiment.json
py .\tools\v4_ranking_repair_summary_gate.py --output v4_ranking_repair_summary.json
py .\tools\v4_decision_audit_pack.py
```

El punto de partida es que `top6` puede conservar algo de senal mientras ranks 7-20 degradan el top. Por eso se prueban variantes como `top6_only`, `top6_preserved_plus_frequency`, penalizaciones diagnosticas a ranks 7-20, hibridos cruncher/frequency y `frequency_only`.

Frequency es el rival principal porque PR #26 mostro que supera al cruncher en agregado usando solo targets previos. Cualquier reparacion debe compararse contra original, random y frequency; mejorar al original no basta si sigue perdiendo contra frequency o si solo funciona en una ventana.

`v4_ranking_repair_window_stability.py` revisa si la mejora es estable por ventanas. `future_post_ranking_layer_candidate` solo puede ser true si mejora al original, es estable, supera random y no empeora fuerte contra frequency. Aun si eso ocurriera, PR #27 mantiene `prior_should_remain_blocked = true` y `recommendation = diagnostic_only`.

`v4_combination_repair_experiment.py` separa problema de ranking numerico vs seleccion de combinaciones. Solo reordena combinaciones existentes en cada replay record; no inventa boletos ni usa resultados reales como prediccion.

No se debe hacer todavia: activar replay prior, tocar Monte Carlo, crear post-ranking layer productivo, crear nuevo runner, ni tratar una mejora diagnostica como promesa de resultado.

## Post-Ranking Holdout Experiment V4.4

PR #28 valida la variante candidata de PR #27, `top6_preserved_plus_frequency_no_duplicates`, fuera del mismo analisis donde fue descubierta. PR #27 no bastaba porque una reparacion puede verse fuerte sobre los mismos 60 replay records y aun asi no generalizar.

```powershell
py .\tools\v4_post_ranking_holdout_experiment.py --output v4_post_ranking_holdout_experiment.json
py .\tools\v4_post_ranking_rolling_validation.py --output v4_post_ranking_rolling_validation.json
py .\tools\v4_post_ranking_holdout_summary_gate.py --output v4_post_ranking_holdout_summary.json
py .\tools\v4_decision_audit_pack.py
```

El holdout separa train/test por tiempo y evalua la variante contra `original_cruncher`, `frequency_only` y `random_expected`. La frecuencia sigue siendo progresiva: para cada target solo puede usar targets anteriores a ese target, nunca el holdout completo ni CSV futuro.

La rolling validation usa una ventana inicial de 30 records y pruebas de 5 records. Esto mide si la mejora vive en varias ventanas o si fue un accidente local. `overfit_risk` queda alto cuando holdout o rolling no llegan al menos a calidad moderada, aunque alguna metrica agregada se vea positiva.

`v4_post_ranking_layer_candidate.json` documenta la capa candidata como especificacion estructurada, no como codigo productivo. Su estado debe permanecer `candidate_not_applied`: no modifica scores oficiales, no escribe `resultados.json`, no toca Monte Carlo y no activa replay prior.

Para una futura capa experimental todavia faltaria validar en sorteos futuros no vistos, correr una simulacion controlada separada, superar frequency/random sin usar futuro y mantener `prior_should_remain_blocked = true` hasta que exista evidencia externa suficiente.

## Post-Ranking Candidate Full Validation Pack V4.4

PR #29 concentra el stress test final de la hipotesis `top6_preserved_plus_frequency_no_duplicates`. PR #28 no bastaba porque el holdout agregado se veia fuerte, pero la rolling validation fina seguia debil; este paquete prueba smoothing, gates de confianza, fallbacks y worst folds antes de decidir si la hipotesis vive o muere.

```powershell
py .\tools\v4_post_ranking_smoothing_stress_test.py --output v4_post_ranking_smoothing_stress_test.json
py .\tools\v4_post_ranking_confidence_gate_experiment.py --output v4_post_ranking_confidence_gate_experiment.json
py .\tools\v4_post_ranking_worst_fold_analysis.py --output v4_post_ranking_worst_fold_analysis.json
py .\tools\v4_post_ranking_full_validation_summary_gate.py --output v4_post_ranking_full_validation_summary.json
py .\tools\v4_decision_audit_pack.py
```

Smoothing significa cambiar como se rankea la frecuencia que rellena despues del top6: conteo crudo, Laplace, decay temporal y ventanas recientes de 15/30/45 records. La prueba conserva la regla anti-leakage: cada target solo puede usar sorteos anteriores.

Confidence gate significa decidir si se usa la reparacion o si se cae a un fallback. Las policies probadas incluyen `always_repair`, fallback a original, fallback a frequency y versiones condicionadas por historial minimo, overlap top6/frequency, estabilidad de frequency y edge reciente.

Worst-fold analysis explica donde falla la hipotesis: folds donde gana original, gana frequency, cae contra random o el top6 pierde calidad. Esto evita tomar una decision por promedio agregado cuando hay ventanas fragiles.

`candidate_status` puede ser `reject`, `keep_candidate` o `ready_for_controlled_layer`. Incluso si aparece `ready_for_controlled_layer`, no significa produccion: `production_ready` debe seguir `false`, `prior_should_remain_blocked` debe seguir `true` y cualquier PR #30 tendria que ser una implementacion controlada separada, explicitamente aprobada, sin mutar scores oficiales ni activar prior.

La hipotesis debe detenerse si ningun smoothing/policy mejora rolling, si frequency sigue dominando, si el peor fold es demasiado negativo o si el riesgo de overfit queda alto. Debe mantenerse viva solo si mejora original/random, no pierde contra frequency de forma estable y deja claro que el siguiente paso sigue siendo diagnostico/controlado.

## Controlled Post-Ranking Layer V4.4

PR #30 toma la decision de PR #29 y la convierte en una vista controlada, separada y review-only. La capa candidata sigue siendo `top6_preserved_plus_frequency_no_duplicates`: conserva el top6 oficial derivado de `resultados.json` y rellena el resto del top20 con `frequency_window_15` calculado desde la ventana reciente de replay memory.

```powershell
py .\tools\v4_post_ranking_controlled_layer.py --output v4_post_ranking_controlled_layer_output.json
py .\tools\v4_post_ranking_controlled_comparison.py --output v4_post_ranking_controlled_comparison.json
py .\tools\v4_post_ranking_controlled_summary_gate.py --output v4_post_ranking_controlled_summary.json
py .\tools\v4_decision_audit_pack.py
```

La capa queda bloqueada salvo que `v4_post_ranking_full_validation_summary.json` tenga `candidate_status = ready_for_controlled_layer`, `production_ready = false`, `prior_should_remain_blocked = true` y `future_controlled_layer_candidate = true`. Aunque pase esos gates, el uso permitido es `review_only`.

El output controlado escribe archivos separados:

```txt
v4_post_ranking_controlled_layer_output.json
v4_post_ranking_controlled_comparison.json
v4_post_ranking_controlled_summary.json
v4_future_unseen_validation_log.json
```

No modifica `resultados.json`, no modifica `v4_replay_memory.json`, no cambia scores oficiales, no activa replay/live/physics prior y no reemplaza el output oficial V4.2. La web debe mostrarlo separado de Official V4.2 Output con la copia: Review-only. Does not replace official V4.2 output. Not a probability of winning.

`v4_future_unseen_validation_log.json` queda vacio a proposito. Solo debe recibir registros despues de sorteos reales futuros, y no puede usarse para generar predicciones actuales ni activar prior en PR #30.

## V4.3 Hybrid Composition Engine

V4.3 separa la senal del motor V4.2 de la composicion final de tickets. `revancha.csv` es la fuente primaria; `resultados.json` solo se usa como senal auxiliar si es JSON valido. Si falta, esta vacio, esta corrupto o contiene conflict markers, V4.3 continua en modo `csv_visual_composition_only` y escribe warnings en sus outputs.

```powershell
py .\tools\v4_winner_composition_audit.py
py .\tools\v4_visual_pattern_features.py
py .\tools\v4_hybrid_composition_engine.py
py .\tools\v4_hybrid_composition_smoke_test.py
```

Outputs:

```txt
v4_winner_composition_audit.json
v4_visual_pattern_output.json
v4_hybrid_composition_slate.json
```

La salida principal `v4_hybrid_composition_slate.json` contiene 4 a 6 tickets maximos, todos con 6 numeros unicos, roles por numero, razones, resumen de composicion y `production_status = review_default`. No reemplaza `resultados.json`, no cambia `score_kind`, no activa priors y no modifica el motor base.

El pase de produccion de PR #32 mantiene el aprendizaje 4217 como regla generica, no como boost fijo a un numero. La activacion de bloque usa `unique_activation` para decidir bloques activos y deja `hit_density` como metadata. La senal `pair_lag` se valida walk-forward contra frecuencia reciente, gap echo y candidatos visuales neutrales; si no supera esas referencias queda como `support_only` o `disabled_by_validation`, nunca como promotor duro.

El panel `v4-decision-audit-panel.js` carga estos JSON como auxiliares opcionales. Si faltan o son invalidos, la web no se cae: muestra un estado pequeno de V4.3 no disponible. Los tickets se muestran como tarjetas compactas con role chips y detalles colapsables para mantener lectura rapida en movil.

## V4.3 Refresh Runner

`tools/v4_refresh.py` regenera los outputs V4.3 en orden y corre el smoke test operativo. Por ahora solo soporta Revancha.

```powershell
python tools/v4_refresh.py --game revancha
```

El runner ejecuta:

```txt
tools/v4_winner_composition_audit.py
tools/v4_visual_pattern_features.py
tools/v4_hybrid_composition_engine.py
tools/v4_hybrid_composition_smoke_test.py
```

Si un paso falla, se detiene con exit code distinto de cero. Al terminar confirma que existen `v4_winner_composition_audit.json`, `v4_visual_pattern_output.json` y `v4_hybrid_composition_slate.json`, y resume `latest_draw`, `production_status`, `pair_lag_mode`, cantidad de tickets, `fallback_mode` y warnings.

## V4.3 Harmonic History Sync And Decision Cockpit

V4.3 now treats each draw as a historical composition, not as isolated number picks. The harmonic layer uses local history, block behavior, same-draw companion pairs, pair-lag support, sum-band discipline, and post-draw accountability to build a review-default candidate slate.

V4.2 remains the official optional individual-number signal provider. V4.3 is the composition layer. It writes separate diagnostic outputs, keeps `production_status = review_default`, does not replace `resultados.json`, does not activate priors, and does not modify the cruncher internals.

First run with internet:

```powershell
python tools/v4_history_sync_from_pakin.py --game revancha --dry-run
python tools/v4_refresh.py --game revancha --sync-history-from-pakin --export-visual-matrix --pair-companion-audit --snapshot-predraw
```

Normal pre-draw workflow when internet is available:

```powershell
python tools/v4_refresh.py --game revancha --sync-history-from-pakin --export-visual-matrix --pair-companion-audit --snapshot-predraw
```

Offline workflow:

```powershell
python tools/v4_refresh.py --game revancha --export-visual-matrix --pair-companion-audit --snapshot-predraw
```

After the official result is added to `revancha.csv`:

```powershell
python tools/v4_post_draw_audit.py --target-draw <draw>
```

Optional manual visual review:

```txt
visual_exports/revancha_visual_matrix.csv
visual_exports/revancha_visual_matrix_compact.csv
visual_exports/revancha_visual_candidate_overlay.csv
visual_exports/revancha_visual_pair_overlay.csv
```

Important workflow rules:

- `tools/v4_history_sync_from_pakin.py` refreshes or rebuilds the local historical source from Pakin when internet is available.
- Pre-draw snapshots freeze the exact V4.3 slate before the target draw, preventing post-result leakage in later audits.
- Post-draw audit is diagnostic only and compares a frozen snapshot against the official CSV result.
- Candidate overlays under `visual_exports/` are visual-only rows marked `synthetic=true` and `row_type=candidate`; they are never canonical history.
- No script should treat `visual_exports/` as a historical input folder.
- V4.3 uses harmonic composition: companion pairs, block harmony, sum bands, roles, and risk notes.
- `v4_pair_companion_audit.json` measures same-draw co-travel pairs, bridge pairs, anti-pair risks, and simple clusters with transparent support thresholds.
- High sums are not banned, but `sum_band` and `slate_sum_distribution` keep the slate from clustering blindly in high-tail territory.
- `production_status` remains `review_default`.

## V4.3 Harmonic Decision Cockpit Contract

V4.2 remains the optional individual-number signal provider. V4.3 is the harmonic composition and cockpit layer: it reads generated JSON, explains ticket structure, and presents a review slate. The web does not compute model ranking and does not mutate `resultados.json`.

Refresh the full V4.3 workflow with:

```powershell
py tools\v4_refresh.py --game revancha --sync-history-from-pakin --export-visual-matrix --pair-companion-audit --snapshot-predraw
```

The generated slate now exposes ticket-level structure:

- `composition.block_signature`: exact counts by canonical blocks `1_10`, `11_20`, `21_30`, `31_40`, `41_56`.
- `composition.block_presence_signature`: 1/0 presence by the same block order.
- `composition.visual_structure_label_es`: Spanish reading of the visual structure.
- `explanation_es`, `reason_es`, `risk_notes_es`, `decision_summary_es`, and `structure_summary_es`: Spanish-first review copy.
- `slate_structure_summary`: slate-level distribution of block presence, block signatures, sum bands, immediate overlap, and dominant visual structure.

Example:

```txt
0-0-1-0-1 = presence in 21_30 and 41_56 only.
```

That signature describes a visual architecture for review. It is not a result guarantee, not a probability, and not an automatic betting signal.

After an official draw is added to `revancha.csv`, run:

```powershell
py tools\v4_post_draw_audit.py --target-draw <draw>
```

Post-draw audit reads the frozen pre-draw snapshot and can compare actual block signatures against ticket signatures. It remains diagnostic-only.

## V4.4 Full Constructor + Decision Cockpit

V4.4 agrega una capa nueva de constructor de combinaciones. V4.2 sigue siendo el motor oficial opcional de señal individual y V4.3 queda como fallback/legacy. V4.4 no modifica `resultados.json`, no toca los crunchers V4.2, no cambia `score_kind` y no activa priors.

Comando integrado V4.4:

```powershell
py tools\v4_refresh.py --game revancha --scrape --reconstruct --full-signals --recent-composition --construct
```

Ese flujo ejecuta, en orden:

```txt
tools/v4_scraper_pakin.py              descarga Pakin en v4_scraper_raw.csv
tools/v4_csv_reconstructor.py          reconstruye revancha.csv canonico
tools/v4_matrix_builder.py             crea v4_history_matrix.json
tools/v4_gap_echo_engine.py            crea v4_gap_echo_output.json
tools/v4_signature_history_engine.py   crea v4_signature_history.json
tools/v4_pair_lag_constructor.py       crea v4_pair_lag_signals.json
tools/v4_block_completion_engine.py    crea v4_block_completion_signals.json
tools/v4_winner_profile_engine.py      crea v4_winner_profile.json
tools/v4_recent_composition_engine.py  crea v4_recent_composition_profile.json
tools/v4_combination_constructor.py    crea v4_combination_slate.json
```

`v4_combination_slate.json` es la salida principal V4.4. Contiene exactamente cinco boletos cuando el pool tiene suficientes señales. Cada boleto se forma con señales activas, relación de pares, suma objetivo, paridad, firma visual, perfil ganador, perfil reciente, repetidos inmediatos medidos y trazabilidad en español. No es un ranking top 6 por score.

`v4_recent_composition_profile.json` analiza las últimas 30 combinaciones ganadoras. Resume bandas de suma, paridad, firmas de presencia, repetidos inmediatos, pares companion y frecuencia reciente. La frecuencia reciente es señal secundaria, no ranking único.

`pair_companion` y `pair_lag` no significan lo mismo:

- `pair_companion`: dos números aparecen juntos dentro del mismo sorteo.
- `pair_lag`: un número aparece y otro aparece dentro de los siguientes tres sorteos.

`block_presence_signature` describe qué bloques tienen presencia. Con bloques `1_10`, `11_20`, `21_30`, `31_40`, `41_56`, la firma `0-0-1-0-1` significa presencia en `21_30` y `41_56` solamente. `block_signature` guarda los conteos exactos por bloque.

`construction_trace_es` explica cómo se formó cada boleto: señales activas, pares, suma, paridad, estructura, repetidos inmediatos y cualquier relajación aplicada. Los repetidos inmediatos no se prohíben: se miden, se justifican cuando aparecen y se marcan como riesgo cuando son altos.

La web principal ahora es el cockpit V4.4 limpio. Lee `v4_combination_slate.json` como fuente primaria y cae a `v4_hybrid_composition_slate.json` solo si falta la salida V4.4. La web no calcula ranking de modelo, no genera boletos, no modifica JSON y no usa `resultados.json` como verdad histórica.

Estado operativo:

```txt
production_status = review_default
```

Uso experimental de revisión. No hay promesa de resultado ni certeza operativa.

## Legacy Snapshot Classifier

`tools/v4_legacy_snapshot_classifier.py` clasifica snapshots antiguos para conservar diagnostico sin contaminar memoria aplicada.

Ejemplo:

```powershell
py .\tools\v4_legacy_snapshot_classifier.py --commit c5d4a18594c4c4b70833f62b70db694964a2aa12
```

El commit legacy del sorteo 4212 debe clasificarse como `legacy_hindsight_snapshot` porque contiene auditoria inversa y combinacion real embebida. No activa prior.

## GitHub sync local

`v4_github_sync.py` usa solo git CLI local. No guarda tokens, no contiene credenciales y depende de la autenticacion que ya tenga configurada tu maquina.

Flujo de sync:

```txt
git pull --rebase origin main
git add outputs permitidos
git commit -m "Update V4.3 results, memory, and dashboard"
git push origin rama-actual
```

Si no hay cambios, evita commit vacio. Si `git` no existe, no hay autenticacion o el directorio no es repo, muestra warning claro y no rompe el pipeline.

### GitHub Desktop como fallback

El runner no guarda tokens, no pide contrasenas y no intenta login web. Si Git CLI no puede pushear, deja los archivos generados en el working tree para abrir GitHub Desktop, revisar cambios, commitear y hacer push manual.

## Historial real de resultados.json

GitHub conserva las versiones anteriores de `resultados.json` por commit:

```txt
https://github.com/EdgarBravo99/fisicapapa/commits/main/resultados.json
```

El runner importa automaticamente snapshots con:

```powershell
git log --format=%H -- resultados.json
git show COMMIT_SHA:resultados.json
```

Tambien puedes recuperar manualmente un snapshot si necesitas auditar un commit especifico:

```powershell
git show COMMIT_SHA:resultados.json > resultados_archive/resultados_manual_COMMIT.json
```

Los snapshots duplicados se deduplican por `prediction_draw`, `target_draw`, `game_mode`, `snapshot_source` y `commit_sha` o hash de contenido. Duplicados no cuentan doble para activar memoria.

## Pruebas recomendadas

Web:

```txt
Abrir index.html con ?v=43
Evaluar 16 19 25 29 45 50
Guardar al comparador
Revisar Top combinaciones, Top numeros, Fisica, Memoria y Auditor
```

Memoria:

```txt
Actualizar el CSV con el sorteo posterior real
Ejecutar opcion [1] del runner calibrado
Confirmar que v4_feedback_memory.json se crea solo si se califico un record real
Confirmar que con 0-2 records el modo es diagnostic_only
Confirmar que con 3+ records reales el prior se instala antes de Monte Carlo
```

Replay:

```txt
Ejecutar classifier contra commit c5d4a185...
Ejecutar replay dry-run con max-targets 3
Ejecutar tools/v4_replay_smoke_test.py
Ejecutar tools/v4_replay_quality_smoke_test.py
Confirmar que v4_replay_memory.json no se crea en dry-run ni sin records reales
```

Sync:

```txt
Ejecutar opcion [3] para subir cambios ya generados
O aceptar la pregunta de sync al final de opcion [1]
```
