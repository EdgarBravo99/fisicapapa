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

La salida conserva los scores originales, ancla el top #1 original y calcula overlap/Jaccard para detectar boletos clonados. Es ranking diversificado, no probabilidad de ganar.

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
