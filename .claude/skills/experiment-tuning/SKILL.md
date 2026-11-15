---
name: experiment-tuning
description: Improve the model - change the model type or hyperparameters in team.yaml, run the experiments, compare them in MLflow against the baseline and the current champion, and propose the winner in a pull request. Use for "beat the champion", tuning, trying another algorithm or feature engineering.
---

# Tune the model and beat the champion

## 1. Measure the starting point

```bash
./scripts/run make pipeline          # registers the current team.yaml model as @champion in this (fresh) MLflow
```
Record the holdout accuracy, ROC AUC, baseline accuracy and season CV accuracy.

## 2. Run candidates

Edit `model` in `team.yaml`, then run `./scripts/run make train evaluate register` for each candidate. Rerunning ingest, validate and prepare is not needed.

| `type` | Useful `params` |
|---|---|
| `logistic_regression` | `C` (0.01-10), `class_weight: balanced`, `max_iter: 1000` |
| `random_forest` | `n_estimators` (200-500), `max_depth` (3-12), `min_samples_leaf` (1-20), `random_state: 0` |
| `gradient_boosting` | `n_estimators` (100-400), `learning_rate` (0.03-0.2), `max_depth` (2-4), `random_state: 0` |

Always set `random_state` so the result is reproducible. Keep the number of candidates small (3-6) and say why each one is worth trying.

Feature engineering belongs in `pipeline/train.py` (`build_model`), so it is saved inside the logged model and serving gets the same transform. Never add `leakage:` columns.

## 3. Compare

```bash
./scripts/run python .claude/skills/mlflow-explore/scripts/mlflow_report.py compare
./scripts/run python .claude/skills/mlflow-explore/scripts/mlflow_report.py models
```

Choose by **holdout accuracy**, which the registry uses for promotion, and check:
- `cv_accuracy_mean` vs holdout: a big gap means overfitting or luck.
- `accuracy_lift` over the baseline rule must stay positive.
- Subgroup accuracy (`subgroup_*`): no subgroup should get much worse.
- A gain below about 0.005 is noise on a holdout of 480 (F1) or 612 (SPL) rows. Say so instead of claiming a win.

## 4. Propose

Leave `team.yaml` with the winner (or unchanged if nothing beats the champion). Then run `./scripts/run make lint test` and commit. The PR description must include a table of the candidates with run ids, holdout accuracy, ROC AUC and CV accuracy, the chosen one and why, and whether it would replace the current `@champion`.
