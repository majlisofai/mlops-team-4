---
name: model-monitoring
description: Interpret and extend model monitoring - input drift (PSI, KS), training-serving skew, delayed labels and performance decay on the 2026 season - and decide whether to retrain, fix a data feed or do nothing. Use for drift, skew, alerts, monitoring reports or retraining decisions.
---

# Monitoring: drift, skew and delayed labels

```bash
./scripts/run make monitor     # needs ingest and a @champion; writes reports/monitoring_<ds>.md and a 'monitor' MLflow run
```

## What it checks (`pipeline/monitor.py`)

| Check | Reference → current | Question it answers |
|---|---|---|
| `drift_scenario` | `reference_window` → drift window (F1 wet race, `rain_prob` 0.92; SPL heatwave, `kickoff_temp_c` 44) | Did the inputs move? |
| `serving_skew` | `recomputed` → `served` for the same requests | Does the API receive what training computed? |
| `season_2026` | `reference_window` → 2026 provisional season | Is the new season different from what the model learned? |
| delayed labels | 2026 predictions vs provisional and final labels | How accurate are we, now that the true labels have arrived? |

Per feature: PSI (`< psi_warning` ok, `> psi_alert` large shift) and, for numeric features, a KS test. A numeric **alert** needs PSI above `psi_alert` **and** KS p-value below `ks_pvalue` (`team.yaml` → `monitoring`). On small windows, PSI alone raises false alarms.

## Read an alert

1. **Is it real?** Look at `reference_mean` vs `current_mean` and the window size: the F1 wet window has 20 rows, the SPL heatwave 18.
2. **Is it drift or skew?** If the same requests differ between `served` and `recomputed`, that's skew: a broken feed or a unit change. Fix the feed or add a validation guard (`data-validation`). Do not retrain on broken inputs.
3. **Does it hurt?** Compare `season_2026_accuracy_final` with the holdout accuracy. A large drop plus an alert on the features the model relies on means the model is stale.
4. **Delayed labels:** `season_2026_label_corrections` counts results that the stewards (F1) or the disciplinary committee (SPL) changed after the event. Accuracy on provisional labels is not the real number; always report the final-label accuracy.

## Decide and report

| Situation | Action |
|---|---|
| Skew in one feature | Fix the input or block it. Do not retrain |
| Drift with stable accuracy on final labels | Watch: write it down, no action |
| Drift with an accuracy drop (for example, SPL `squad_value_m` after the spending wave) | Retrain with recent data, or features that are robust to the shift. Validate on final labels |
| Accuracy drop without input drift | Concept drift: the relation between inputs and outcome changed. Investigate before retraining |

Report the alerted features with PSI, KS p-value and means, the classification (drift, skew, concept drift or noise), the accuracy on provisional vs final labels, and one recommended action with its evidence.

## Extend

New checks go into `compare()` or a new function in `pipeline/monitor.py`, logged with `mlflow.log_metric`, `mlflow.log_table` and an `*_alerts` tag. Add a test in `tests/test_monitor.py` that the planted scenario is detected and that stable data is not flagged.
