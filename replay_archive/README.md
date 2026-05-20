# Replay Archive

Esta carpeta guarda snapshots generados por `tools/v4_historical_replay_lab.py`.

Un replay no es un sorteo real ni una prediccion live. Es un examen historico:

```txt
CSV temporal con sorteos < target_draw -> motor principal -> prediccion -> calificacion contra target_draw real
```

Reglas:

- El CSV real no se modifica.
- `target_draw` no entra al CSV temporal.
- Sorteos futuros no entran al CSV temporal.
- `resultados.json` nunca es verdad.
- Replay memory queda separada de live memory.
- Replay prior queda apagado por defecto.

Los snapshots se nombran:

```txt
replay_{game_mode}_{prediction_draw}_to_{target_draw}.json
```
