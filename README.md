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
```

Responsabilidades:

- `v4-clean-app.js`: carga `resultados.json`, valida contrato V4.2, inicializa la app y expone `evaluateManualComboV4()`.
- `v4-results-panels.js`: renderiza combinaciones, top de numeros y panel fisico V4.2.
- `v4-under40-verifier.js`: agrega auditoria visual de macroestructura `<40`; no modifica score ni cruncher.
- `v4-system-diagnostics.js`: valida calidad de `resultados.json`, muestra estado del sistema y agrega explicabilidad manual visual.
- `v4-combo-comparator.js`: mantiene el comparador personal temporal en localStorage.
- `v4-feedback-memory-panel.js`: muestra memoria tipo examen y el historial GitHub de `resultados.json`.
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
[1] Ejecutar pipeline V4.2 completo
[2] Inspeccionar resultados.json
[3] Actualizar memoria de predicciones / calificar examenes
[4] Sincronizar resultados con GitHub
[5] Pipeline + memoria + GitHub sync
```

La opcion `[1]` pregunta al final si quieres subir resultados a GitHub. La opcion `[5]` ejecuta pipeline y sync porque fue elegida explicitamente.

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

## Pipeline V4.3 de memoria tipo examen

V4.3 no cambia el runner oficial ni crea otro programa principal. El flujo sigue entrando por:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

La memoria persistente vive en `v4_feedback_memory.py` y, cuando existe al menos un examen real calificado, en `v4_feedback_memory.json`.

Modelo mental:

```txt
resultados.json historico = prediccion pasada del cruncher
CSV historico actualizado = verdad revelada
v4_feedback_memory.json = libreta de calificaciones
```

Reglas anti-leakage:

- Nunca usar `resultados.json` como verdad.
- Para calificar una prediccion 4214 contra un target 4215, el CSV ya debe contener 4215 como sorteo revelado.
- Nunca usar 4215 para generar la prediccion 4215.
- Si no hay sorteo target posterior en el CSV, la memoria muestra warning y no inventa resultados.
- Si hay menos de 3 records reales calificados, la memoria queda en modo diagnostico y no altera ranking ni score.

## GitHub sync local

`v4_github_sync.py` usa solo git CLI local. No guarda tokens, no contiene credenciales y depende de la autenticacion que ya tenga configurada tu maquina.

Flujo de sync:

```txt
git pull --rebase origin main
git add outputs permitidos
git commit -m "Update V4.3 results, memory, and dashboard"
git push origin rama-actual
```

Si no hay cambios, evita commit vacio. Si `git` no existe o el directorio no es repo, muestra error claro y no rompe el pipeline.

## Historial real de resultados.json

GitHub conserva las versiones anteriores de `resultados.json` por commit:

```txt
https://github.com/EdgarBravo99/fisicapapa/commits/main/resultados.json
```

Para recuperar manualmente un snapshot:

```powershell
git log -- resultados.json
git show COMMIT_SHA:resultados.json > resultados_archive/resultados_manual_COMMIT.json
```

Luego, con el CSV ya actualizado con el sorteo posterior, usa la opcion `[3]` del runner para calificar ese snapshot.

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
Guardar o recuperar un resultados.json historico en resultados_archive/
Actualizar el CSV con el sorteo posterior real
Ejecutar opcion [3] del runner calibrado
Confirmar que v4_feedback_memory.json se crea solo si se califico un record real
```

Sync:

```txt
Ejecutar opcion [4] para subir cambios ya generados
Ejecutar opcion [5] para pipeline + memoria + sync
```
