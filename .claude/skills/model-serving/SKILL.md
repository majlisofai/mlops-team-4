---
name: model-serving
description: Serve the @champion model as a REST API with MLflow, call it, check that online and batch predictions agree, and debug schema or payload errors. Use for serving, deployment, inference, the /invocations endpoint or prediction mismatches.
---

# Serve and call the model

The model is served from the registry by alias, so promoting a new `@champion` and restarting the server deploys it.

```bash
./scripts/run make serve           # mlflow models serve -m models:/<team>-<ds>-model@champion on port 5001 (blocks)
```

In GitHub Actions, start it in the background and wait for it:

```bash
docker compose -f .devcontainer/docker-compose.yml exec -d workspace make serve
for i in $(seq 30); do ./scripts/run python -c "import urllib.request as u; u.urlopen('http://localhost:5001/ping')" && break; sleep 3; done
```

## Call it

```bash
./scripts/run make predict-api     # scores the 2026 season through the API and logs a 'predict' run (mode=api)
./scripts/run curl -s localhost:5001/invocations -H 'Content-Type: application/json' \
  -d '{"dataframe_records": [{"grid": 1, "quali_gap_ms": 0, "driver_form": 2, "team_form": 25, "team_dnf_rate": 0.05, "rain_prob": 0.1, "circuit_type": "street"}]}'
```

The payload is `dataframe_records` (a list of row objects) or `dataframe_split` (`columns` + `data`). The response is `{"predictions": [0|1, ...]}`.
Features: F1 `grid, quali_gap_ms, driver_form, team_form, team_dnf_rate, rain_prob, circuit_type`; SPL `home, league_position, opponent_position, form_points, squad_value_m, travel_km, kickoff_temp_c, kickoff_slot`.

## Online and batch parity

`make predict` (batch, loads the model from the registry) and `make predict-api` (through the server) must give identical predictions. Both write `work/<ds>/predictions/predictions_2026.csv`, so copy the first file before running the second, then compare. A difference means the two paths build inputs differently. Both must go through `pipeline.data.feature_frame`.

## Errors

| Error | Meaning |
|---|---|
| `RESOURCE_DOES_NOT_EXIST ... alias champion` | No model has been promoted yet: run `make pipeline` |
| HTTP 400 `Failed to enforce schema` / missing column | The payload does not match the model signature (logged by `train`). Check column names and types |
| Plausible but wrong predictions | Units or semantics differ from training (skew). The schema check cannot catch it: see `data-validation` and `model-monitoring` |
| `Connection refused` on 5001 | The server is not running or still starting |
