# Resultados Archive

Esta carpeta guarda snapshots historicos de `resultados.json` para auditoria V4.3.1.

## Que es un snapshot

Un snapshot es una prediccion pasada del cruncher. No es verdad revelada.

La verdad revelada siempre viene del CSV historico actualizado con el sorteo real posterior.

`index.json`, cuando existe, es solo inventario tecnico:

- no es verdad;
- no es scoring;
- no es memoria;
- no activa aprendizaje;
- evita duplicados;
- alimenta el panel web.

## Flujo recomendado

La opcion `[1]` del runner guarda automaticamente una copia local antes de reemplazar `resultados.json`:

```txt
resultados_archive/resultados_4214_YYYYMMDD_HHMMSS.json
```

Ese snapshot incluye:

```json
{
  "snapshot_metadata": {
    "source": "local_pre_run_archive",
    "original_path": "resultados.json"
  }
}
```

Cuando el CSV ya contiene el sorteo posterior real, abre el runner:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Usa la opcion:

```txt
[1] Ejecutar pipeline V4.3 completo
```

El runner intentara importar historico Git, calificar snapshots contra CSV revelado, generar `v4_history_analysis.json`, construir el prior y correr el pipeline normal.

## Recuperar desde GitHub

GitHub conserva el historial por commit:

```txt
https://github.com/EdgarBravo99/fisicapapa/commits/main/resultados.json
```

El runner importa automaticamente con:

```powershell
git log --format=%H -- resultados.json
git show COMMIT_SHA:resultados.json
```

Snapshots Git se nombran asi:

```txt
resultados_archive/resultados_git_{draw_id}_{short_sha}.json
resultados_archive/resultados_git_unknown_{short_sha}.json
```

Cada snapshot Git incluye:

```json
{
  "snapshot_metadata": {
    "source": "git_history",
    "commit_sha": "...",
    "short_sha": "...",
    "original_path": "resultados.json"
  }
}
```

Recuperacion manual opcional:

```powershell
git log -- resultados.json
git show COMMIT_SHA:resultados.json > resultados_archive/resultados_manual_COMMIT.json
```

## Deduplicacion

Un record real unico se identifica por:

- `prediction_draw`;
- `target_draw`;
- `game_mode`;
- `snapshot_source`;
- `commit_sha` o hash de contenido.

Snapshots duplicados no cuentan doble para activar memoria.

## Memoria y overfitting

El prior solo puede aplicarse con 3+ records reales unicos calificados contra CSV real.

Fuerza progresiva:

```txt
3-4 records: 25%
5-7 records: 50%
8-10 records: 75%
10+ records: 100%
```

El ajuste maximo absoluto es +/-5%. Si falta Git, CSV, historial o evidencia suficiente, el runner sigue en `diagnostic_only`.

## Que no hacer

- No usar un snapshot como resultado real.
- No calificar una prediccion contra un sorteo que aun no esta revelado en CSV.
- No crear `v4_feedback_memory.json` vacio.
- No editar snapshots para mejorar una calificacion.
- No usar memoria para afirmar probabilidades garantizadas.
- No usar records mock para activar memoria aplicada.
- No hacer post-score calibration como sustituto silencioso del prior pre-Monte-Carlo.
