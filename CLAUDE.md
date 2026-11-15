# MLOps course repo - agent guide

An MLOps pipeline from source data to a served and monitored model, with MLflow tracking every stage. Students work in teams. You usually run in **GitHub Actions** (the `@claude` comments, PR review and the run report), with the same containers as the students' Codespaces.

## Run every repo command through `./scripts/run`

`./scripts/run <command>` executes inside the workspace container, where Python, the packages and `MLFLOW_TRACKING_URI` are set. Never run `python`, `make` or `pip` directly on the runner.

```bash
./scripts/run make pipeline            # all 8 stages; one MLflow parent run with a nested run per stage
./scripts/run make train               # one stage: ingest validate prepare train evaluate register predict monitor
./scripts/run make test                # pytest (downloads the pinned data)
./scripts/run make lint                # ruff check + ruff format --check
./scripts/run make format              # fix style before committing
./scripts/run make pipeline DATASET=spl   # the other dataset (a make variable, not a shell env var)
./scripts/run python .claude/skills/mlflow-explore/scripts/mlflow_report.py compare   # MLflow as tables
```

The MLflow server inside an Actions job is **fresh for every job**: it only holds the runs you make in that job. The students' Codespace MLflow is not reachable from Actions. To compare a change with the current model, run the pipeline on both versions in the same job.

## Map

| Path | What |
|---|---|
| `team.yaml` | The team's settings: team, dataset (`f1`/`spl`), model type and params, quality gate, monitoring thresholds |
| `configs/f1.yaml`, `configs/spl.yaml` | The data contract, owned by the instructors: source commit, features, leakage columns, ranges, baseline rule, published facts |
| `pipeline/<stage>.py` | One file per stage. Each stage logs to MLflow through `tracking.stage_run` |
| `pipeline/data.py` | `feature_frame()`: the exact model inputs, shared by train, serve and monitor |
| `tests/` | Data contract, model vs baseline, monitoring scenarios |
| `work/`, `reports/`, `.mlflow/` | Generated outputs, git-ignored |

Stages share facts through `work/<dataset>/state.json`. The registered model is `<team>-<dataset>-model`, with aliases `@champion` and `@challenger`.

## Rules

- **No leakage.** Never add a column from `leakage:` (known only after the event) or the target to the features. `validate` enforces it.
- **Don't weaken the gate silently.** Lowering `quality_gate` thresholds, removing checks or tests, or changing `facts:` or `source.ref` in `configs/` needs a stated reason in the PR.
- **Split by season, never at random.** Train 2021-2024, holdout 2025.
- **Evidence over opinion.** Quote MLflow numbers (run ids, metrics, model versions) when you claim a model is better or worse.
- Before committing: `./scripts/run make lint test`. Keep the code style of the surrounding file.
- The data is synthetic. Never present it as real people, clubs or results.

## Skills and agents

Skills in `.claude/skills/`: `mlops-pipeline`, `mlflow-explore`, `experiment-tuning`, `data-validation`, `model-serving`, `model-monitoring`.
Agents in `.claude/agents/`: `mlflow-analyst` (read-only analysis of runs and models), `mlops-reviewer` (PR review).
