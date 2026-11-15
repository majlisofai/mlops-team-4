---
name: mlops-pipeline
description: Run the MLOps pipeline (all stages or one) and explain or troubleshoot the result. Use when asked to run the pipeline, a stage (ingest, validate, prepare, train, evaluate, register, predict, monitor), or why a run, CI job or stage failed.
---

# Run and troubleshoot the pipeline

## Run

```bash
./scripts/run make pipeline                 # all stages; dataset from team.yaml
./scripts/run make pipeline DATASET=spl     # the other dataset
./scripts/run make <stage>                  # one stage; needs the earlier stages' outputs in work/<dataset>/
```

Stage order and hand-offs: `ingest` (writes `work/<ds>/raw/`) → `validate` → `prepare` (writes `work/<ds>/prepared/`) → `train` (writes `model_uri` to `state.json`) → `evaluate` (writes `gate_passed`) → `register` → `predict` → `monitor`.
A single stage fails with `FileNotFoundError ... run the ingest stage first` when its inputs are missing: run the earlier stages, or `make pipeline`.

## Report the result

The run prints a summary table, which is also written to `reports/summary.md`. Report:
1. The gate verdict, with holdout accuracy vs baseline accuracy and ROC AUC.
2. The registry decision: promoted to `@champion`, kept as `@challenger`, or rejected.
3. Monitoring alerts and the 2026 accuracy on final labels.
4. Anything that failed, with the stage and the first error line.

For details, use the `mlflow-explore` skill (`mlflow_report.py run <run_id>`).

## Troubleshoot

| Symptom | Cause | Fix |
|---|---|---|
| `MLflow server is not reachable` | The mlflow container is down | In Actions: `docker compose -f .devcontainer/docker-compose.yml up -d --wait mlflow workspace`. In a Codespace: rebuild the container |
| `data validation failed:` followed by a list | A data or feature-config problem; the `validate` run is FAILED in MLflow | Read the list. Leakage → fix the features. Range/category → see the `data-validation` skill |
| Exit code 1 with `Quality gate FAILED` | The model is not good enough; nothing was registered | Compare with the baseline and decide (see `experiment-tuning`). Do not lower the gate to make it pass without a stated reason |
| `skipped: no @champion model` | No model has passed the gate yet in this MLflow | Expected on a fresh MLflow if the gate failed |
| `ValueError: model.type must be one of` | A typo in `team.yaml` | `logistic_regression`, `random_forest` or `gradient_boosting` |
| `TypeError: ... unexpected keyword argument` in train | A param the estimator does not accept | Check the scikit-learn signature for that estimator |
| HTTP 404 in ingest | `source.ref` or a file name in `configs/` is wrong | Restore the pinned commit |

To read a failed CI run: `gh run view <id> --log-failed` (needs the `actions: read` permission).
