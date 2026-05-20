# Resultados Archive

Esta carpeta guarda snapshots historicos de `resultados.json`.

## Que es un snapshot

Un snapshot es una prediccion pasada del cruncher. No es verdad revelada.

La verdad revelada siempre viene del CSV historico actualizado con el sorteo real posterior.

## Flujo recomendado

Antes de reemplazar `resultados.json`, el runner puede guardar una copia:

```txt
resultados_archive/resultados_4214.json
```

Cuando el CSV ya contiene el sorteo posterior real, abre el runner:

```powershell
py -X utf8 .\local_cruncher_v4_2_calibrated.py
```

Usa la opcion:

```txt
[3] Actualizar memoria de predicciones / calificar examenes
```

## Recuperar desde GitHub

GitHub conserva el historial por commit:

```txt
https://github.com/EdgarBravo99/fisicapapa/commits/main/resultados.json
```

Recuperacion manual:

```powershell
git log -- resultados.json
git show COMMIT_SHA:resultados.json > resultados_archive/resultados_manual_COMMIT.json
```

## Que no hacer

- No usar un snapshot como resultado real.
- No calificar una prediccion contra un sorteo que aun no esta revelado en CSV.
- No crear `v4_feedback_memory.json` vacio.
- No editar snapshots para mejorar una calificacion.
- No usar memoria para afirmar probabilidades garantizadas.
