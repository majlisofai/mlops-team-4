# Exercises

Each exercise ends with something visible in MLflow or in CI. Work on a branch and open a pull request.
In any exercise you can ask the agents in GitHub Actions: comment `@claude ...` on an issue or PR. Check what they claim against MLflow and the CI run, just as you would a teammate's work.

## 1. Run it and read it (stages 1-8)
Run `make pipeline`. In the MLflow UI, find the parent run and its 8 child runs.
- Which commit of the source data did the model train on? (Hint: the `ingest` run, then `manifest.json`.)
- Open the registered model. Which version is `@champion`, and what is its `holdout_accuracy` tag?

## 2. The leakage trap (validate)
Add a post-event column, such as `finish_position` or `goals_for`, to `features.numeric` in `configs/<dataset>.yaml` and run `make validate`.
- Why does the pipeline stop? Read the failed run in MLflow.
- Now also remove that column from the `leakage` list. Does validation pass? Check what happens to holdout accuracy, and explain why this model would fail in production.

## 3. Beat the champion (train, evaluate, register)
Change `model` in `team.yaml`: try `random_forest` or `gradient_boosting` with different `params`.
- Compare runs in MLflow: select the train runs ▸ **Compare**.
- Does your new version become `@champion` or stay `@challenger`? Why?
- Open a pull request and read the metrics table in the CI job summary.

## 4. A gate that means something (evaluate)
Raise `quality_gate.min_roc_auc` until the gate fails. What does CI do?
Add a subgroup rule: the model must not be more than 5 points less accurate for `rookie` drivers or `promoted` clubs. Implement it in `pipeline/evaluate.py` and cover it with a test.

## 5. Serve it (predict)
Run `make serve` in one terminal and `make predict-api` in another. Do the batch predictions and the API predictions match?
Send the API a request with `quali_gap_ms` in seconds or `travel_km` in miles. What does the model answer, and how would you catch this before it reaches the model?

## 6. Drift and skew (monitor)
Run `make monitor` and open `reports/monitoring_<dataset>.md`.
- Which features drift in the scenario window, and is the model wrong because of it?
- The skew window shows one feature with a unit change. Write a test or a validation rule that would have blocked it.
- Why does a numeric alert need both PSI and a significant KS test? Try `ks_pvalue: 1.0` in `team.yaml`.

## 7. Delayed labels (monitor, Day 3)
The 2026 results come in provisional; the corrections arrive hours (F1) or days (SPL) later.
- Compare `season_2026_accuracy_provisional` with `season_2026_accuracy_final`.
- Which predictions did the corrections flip? Use `corrections_2026` in `work/<dataset>/raw/`.
- Should you retrain on 2026 data now? Write the argument as a pull request description.

## 8. Work with the agents
- Open an issue: `@claude try three models with experiment-tuning and open a PR with the best one`. Read the PR: are the numbers in the description the same as in the CI job summary?
- Open a PR that quietly lowers `quality_gate.min_roc_auc`. Does the **mlops-reviewer** catch it?
- Improve a skill in `.claude/skills/` (for example, add a troubleshooting row to `mlops-pipeline`) and show that the agent's answer gets better.
