# Codex Handoff — Fisicapapa / Melate Pro V7 Web V2 + Cruncher V4.2

Este archivo es el punto de continuidad para trabajar en Codex sin depender del historial completo de la conversación.

## Estado actual

```txt
Repo: EdgarBravo99/fisicapapa
Proyecto: Fisicapapa / Melate Pro V7
Versión activa: V4.2
Web activa: Web V2, V4.2-only
Motor local recomendado: local_cruncher_v4_2_calibrated.py
Motor base importado por el runner: local_cruncher_v4_deep_stacking.py
Salida principal: resultados.json
Deploy: Vercel estático
Fuente remota histórica web: Pakin loader
```

## Regla principal

No volver a V3. No reactivar scripts V3. No meter reglas nuevas al cruncher sin medirlas antes como verificadores visuales o auditoría.

La Web V2 debe aceptar únicamente JSON V4.2 con:

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

Si el JSON no trae `feedback_loop.version = "V4.2"`, la web debe detenerse con error rojo.

---

## Runner correcto

Usar siempre:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Este runner:

- Importa `local_cruncher_v4_deep_stacking.py`.
- Inyecta pesos físicos calibrados del sorteo 4214.
- Aplica la calibración tanto a Melate como a Revancha.
- Exporta pesos reales y efectivos por número.
- Mantiene visible cualquier error y guarda `cruncher_error.log`.

Después de correr:

```powershell
git add resultados.json
git commit -m "Update V4.2 calibrated predictions"
git push origin main
```

---

## Calibración física actual

Fecha y sorteo de calibración:

```txt
calibration_date: 2026-05-17
draw_id: 4214
calibration_id: weights_2026_05_17_draw_4214
```

La tabla de pesos vive en:

```txt
local_cruncher_v4_2_calibrated.py
CALIBRATED_WEIGHTS_2026_05_17_DRAW_4214
```

Se aplica a:

```txt
BALL_WEIGHTS["melate"]
BALL_WEIGHTS["revancha"]
```

### Reset de vida útil

Después de mantenimiento/calibración, la vida útil/desgaste no debe usar el histórico completo.

Debe contar usos físicos solo desde después del sorteo:

```txt
4213
```

La intención funcional es:

```txt
uses_since_calibration = conteo de salidas con draw_id > 4213
```

La web debe mostrar:

- salidas reales desde calibración;
- peso real;
- peso efectivo;
- desgaste estimado en mg;
- reset post-sorteo 4213.

No debe mostrar “vida 50% / 60%” como si fuera vida útil real.

---

## Archivos principales

### Python

```txt
local_cruncher_v4_2_calibrated.py   Runner recomendado actual
local_cruncher_v4_deep_stacking.py  Motor base V4.2
resultados.json                     Salida consumida por la web
```

### Web V2

```txt
index.html
v4-clean-app.js
v4-results-panels.js
v4-under40-verifier.js
pakin-remote-loader.js
data.js
```

La web carga actualmente:

```html
<script src="data.js"></script>
<script src="pakin-remote-loader.js"></script>
<script src="v4-clean-app.js"></script>
<script src="v4-results-panels.js"></script>
<script src="v4-under40-verifier.js"></script>
```

No cargar scripts legacy:

```txt
ui.js
engine.js
python-results-v3-compat.js
python-results-v4-compat.js
v3-panels-bridge.js
v3-left-right-indicator.js
v3-manual-suggestion-diversity.js
v3-generator-elite-rank.js
walk-forward-ui.js
heatmap-fix.js
```

---

## Web V2: componentes activos

### 1. Validador estricto V4.2

Archivo:

```txt
v4-clean-app.js
```

Responsabilidades:

- cargar `resultados.json`;
- validar que sea V4.2;
- inicializar `window.FISICAPAPA_WEB_V2`;
- exponer `evaluateManualComboV4()`;
- renderizar header y KPIs base.

### 2. Evaluador manual V4

Función principal:

```js
evaluateManualComboV4(numbersArray, jsonData)
```

Pesos del score manual:

```txt
40% Score del Modelo
24% Balance Estructural
20% Alineación Pool
16% Física de Gravedad
```

Debe leer física desde:

```txt
manual_suggestion_seed
physics_summary
```

Campos esperados por número:

```txt
real_weight
base_weight
raw_weight
effective_weight
uses_since_calibration
uses_in_window
physics_bonus
weight_calibration_id
weight_calibration_date
weight_calibration_draw_id
```

### 3. Paneles finales V4.2

Archivo:

```txt
v4-results-panels.js
```

Responsabilidades:

- renderizar mejores combinaciones (`top_combinations` o `generator_pool`);
- renderizar top 10 números V4.2;
- validar presencia de física;
- corregir/renderizar panel físico con usos reales, no porcentaje falso.

El panel físico debe decir algo tipo:

```txt
Bola 15: peso real 4.5600g; desde el reset post-sorteo 4213 ha salido 1 veces y su peso efectivo actual es 4.5597g.
```

No debe decir:

```txt
vida 50%
vida 60%
```

### 4. Verificador visual <40

Archivo:

```txt
v4-under40-verifier.js
```

No modifica cruncher ni score oficial.

Al evaluar una combinación manual, añade una tarjeta visual:

```txt
Verificador macroestructura <40
```

Calcula:

- cuántos números del combo son menores a 40;
- cuántos números <40 hubo en los últimos 4 folds reales de `walk_forward.rows`;
- objetivo suave de cierre de bloque típico: 21 números <40 en 5 sorteos / 30 extracciones;
- esperanza neutral del siguiente sorteo: `6 * 39 / 56 = 4.18`.

Importante: es auditoría visual, no regla dura. No tocar el score ni el cruncher con esta lógica salvo que se valide OOS primero.

---

## Bug importante ya corregido

### Error bola 56 / Transformer

Error anterior:

```txt
IndexError: index 56 is out of bounds for axis 1 with size 56
```

Causa:

La función `mat(draws, width=56)` escribía la bola 56 en índice 56, pero una matriz de 56 columnas tiene índices 0-55.

Regla corregida:

```txt
width=57 -> bola n usa columna n, columna 0 queda libre
width=56 -> bola n usa columna n-1
```

Función afectada:

```txt
local_cruncher_v4_deep_stacking.py::mat()
```

No volver a cambiar esta función sin testear bola 56.

---

## Error handling del runner

`local_cruncher_v4_2_calibrated.py` está preparado para no cerrarse si falla.

Si truena:

```txt
- imprime traceback;
- guarda cruncher_error.log;
- espera Enter antes de cerrar.
```

Cuando Codex haga cambios al runner, conservar esta propiedad.

---

## Flujo recomendado de trabajo

### 1. Actualizar repo

```powershell
git pull origin main
```

### 2. Correr cruncher calibrado

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

### 3. Subir resultados

```powershell
git add resultados.json
git commit -m "Update V4.2 calibrated predictions"
git push origin main
```

### 4. Ver web con cache-bust

```txt
https://TU_DEPLOY.vercel.app/?v=17
```

Si algo viejo aparece, probar incógnito o borrar caché del sitio.

---

## Contrato mínimo esperado en resultados.json

```json
{
  "source": "local_cruncher_v4_2_oos_feedback_loop",
  "model_version": "V4.2-oos-feedback-loop",
  "game_mode": "melate | revancha",
  "score_kind": "v4_2_deep_stacking_meta_score",
  "v4_score_kind": "lagged_residual_feature_temporal_decay_warmstart",
  "walk_forward": {
    "feedback_loop": {
      "enabled": true,
      "version": "V4.2",
      "type": "lagged_residual_feature_temporal_decay_warmstart"
    },
    "rows": []
  },
  "physics_summary": {
    "avg_effective_weight": 0,
    "min_weight": 0,
    "max_weight": 0,
    "diff_weight": 0
  },
  "manual_suggestion_seed": [],
  "generator_pool": [],
  "top_combinations": [],
  "number_scores": {}
}
```

---

## Pendientes recomendados para Codex

### Alta prioridad

1. Verificar que `local_cruncher_v4_2_calibrated.py` realmente calcule `uses_since_calibration` usando solo `draw_id > 4213`.
2. Verificar que `physics_summary` exporte metadata global:

```txt
weight_calibration_id
weight_calibration_date
weight_calibration_draw_id
weight_lifecycle_reset_after_draw_id
```

3. Confirmar que `manual_suggestion_seed` tenga 56 entradas con:

```txt
real_weight
effective_weight
uses_since_calibration
```

4. Confirmar que `v4-results-panels.js` muestra salidas reales y desgaste en mg.

### Media prioridad

5. Añadir test rápido de Python para `mat()`:

```python
assert mat([Draw(... numbers=(56, ...))], 56).shape == (1, 56)
assert mat(..., 56)[0, 55] == 1
```

6. Añadir test visual/console para `v4-under40-verifier.js`.
7. Evitar commits que reemplacen `local_cruncher_v4_deep_stacking.py` completo sin necesidad.

### Baja prioridad

8. Renombrar motor base a `local_cruncher_v4_2.py` cuando esté estable.
9. Mover archivos legacy a carpeta `legacy/`.
10. Crear una página `diagnostics.html` para validar JSON y campos físicos.

---

## Regla anti-parches

El usuario pidió explícitamente no seguir creando parches innecesarios que puedan introducir bugs.

Cuando sea posible:

- modificar funciones concretas;
- no reescribir archivos completos;
- no crear `fix_*.py` nuevos;
- preferir módulos web pequeños solo cuando no alteren el motor principal;
- mantener trazabilidad por commit.

---

## Últimas decisiones de diseño

- El cruncher V4.2 es el responsable de generar scores y combinaciones.
- La web no debe hacer Monte Carlo pesado.
- La web sí puede hacer verificadores visuales/manuales.
- La regla `<40` se queda en web, no en cruncher.
- La física calibrada es central y debe mostrarse siempre.
- El score manual no debe confundirse con probabilidad real garantizada.

---

## Comando rápido para Codex

Usar este resumen como prompt inicial:

```txt
Lee CODEX_HANDOFF_V4_2.md. Estamos en Fisicapapa Web V2 / Cruncher V4.2. No reactivar V3. El runner correcto es local_cruncher_v4_2_calibrated.py. Mantén validación V4.2 estricta, física calibrada sorteo 4214 del 2026-05-17, reset de vida útil después del 4213 y verificador <40 solo en web. Antes de cambiar archivos, audita que no rompas mat(), run_pipeline(), resultados.json ni los paneles físicos.
```
