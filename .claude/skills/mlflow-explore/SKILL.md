---
name: mlflow-explore
description: Query the team's MLflow tracking server and model registry - list pipeline runs, compare train/evaluate metrics across runs, show registered model versions and aliases, inspect one run's params, metrics, tags and artifacts, trace data lineage. Use for any question about runs, experiments, metrics or models.
---

# Explore MLflow

The server is at `$MLFLOW_TRACKING_URI` inside the workspace container. The experiment is `<team>-<dataset>` and the registered model is `<team>-<dataset>-model` (see `team.yaml`).
In GitHub Actions the server is fresh for each job: it only holds runs made in that job. If it is empty, run `./scripts/run make pipeline` first.

## Ready-made views (read-only)

```bash
R=".claude/skills/mlflow-explore/scripts/mlflow_report.py"
./scripts/run python $R runs                 # latest pipeline (parent) runs
./scripts/run python $R compare              # train + evaluate metrics per pipeline run, with model params and gate
./scripts/run python $R models               # registry: versions, @champion/@challenger, holdout_accuracy, git sha
./scripts/run python $R run <run_id>         # one run: tags, params, metrics, artifact list
./scripts/run python $R compare --dataset spl --limit 20
```

## What is where

| Question | Stage run | Look at |
|---|---|---|
| Which data, at which commit? | `ingest` | params `source_ref`, artifact `manifest.json` (sha256 per file), dataset input `<ds>-history` |
| Was the data valid? | `validate` | tag `validation`, artifact `validation_report.json`, `feature_profile.json` |
| How was it split? | `prepare` | params `train_seasons`, `holdout_seasons`; metrics `*_rows`, `*_positive_rate` |
| How was the model trained? | `train` | params `model_type`, `model.*`; metrics `cv_accuracy_mean/std`; the logged model (signature, input example) |
| Is it good enough? | `evaluate` | metrics `holdout_*`, `baseline_accuracy`, `accuracy_lift`, `subgroup_*`; tag `quality_gate`; `confusion_matrix.png`, `subgroup_accuracy.json` |
| Registered? | `register` | tag `decision`; params `registered_version` |
| What did it predict? | `predict` | params `model_version`, `mode`; artifact `predictions/predictions_2026.csv` |
| Is the world changing? | `monitor` | metrics `*_psi_max`, `*_features_alerted`, `season_2026_accuracy_*`; tags `*_alerts`; tables `drift_scenario.json`, `serving_skew.json`, `season_2026.json` |

Every run is tagged with `stage`, `team`, `dataset`, `git_sha` and `runs_on` (`codespaces`, `github-actions` or `local`).

## Custom queries

```bash
./scripts/run python -c "
from mlflow import MlflowClient
c = MlflowClient(); e = c.get_experiment_by_name('team-1-f1')
for r in c.search_runs([e.experiment_id], \"tags.stage = 'evaluate' and metrics.holdout_accuracy > 0.83\",
                       order_by=['metrics.holdout_accuracy DESC'], max_results=5):
    print(r.info.run_id, r.data.metrics['holdout_accuracy'])"
```

Download an artifact: `mlflow.artifacts.download_artifacts(run_id=..., artifact_path="quality_gate.json")`.

When you report, give run ids (8 characters are enough), metric values to 3 decimals and model versions. Do not invent runs that are not in the server.
