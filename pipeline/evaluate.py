"""Stage 5 - evaluate: score the holdout season, compare with the baseline rule and subgroups, apply the quality gate."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import mlflow  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    log_loss,
    precision_score,
    recall_score,
    roc_auc_score,
)

from pipeline.config import Config  # noqa: E402
from pipeline.data import feature_frame  # noqa: E402
from pipeline.tracking import stage_run  # noqa: E402


def baseline_predictions(cfg: Config, df: pd.DataFrame) -> pd.Series:
    """The simple rule from the dataset README. A model that cannot beat it is not worth deploying."""
    return df.eval(cfg.data["baseline"]["rule"]).astype(int)


def subgroup_accuracy(cfg: Config, df: pd.DataFrame, pred) -> pd.DataFrame:
    rows = []
    scored = df.assign(prediction=pred)
    for col in cfg.data["subgroups"]:
        for value, group in scored.groupby(col):
            rows.append(
                {
                    "subgroup": col,
                    "value": str(value),
                    "rows": len(group),
                    "accuracy": accuracy_score(group[cfg.target], group["prediction"]),
                }
            )
    return pd.DataFrame(rows)


def run(cfg: Config) -> dict:
    state = cfg.load_state()
    holdout = pd.read_csv(cfg.work_dir / "prepared" / "holdout.csv")
    X, y = feature_frame(cfg, holdout), holdout[cfg.target]
    model = mlflow.sklearn.load_model(state["model_uri"])
    proba = model.predict_proba(X)[:, 1]
    pred = (proba >= 0.5).astype(int)
    baseline_accuracy = accuracy_score(y, baseline_predictions(cfg, holdout))

    metrics = {
        "holdout_accuracy": accuracy_score(y, pred),
        "holdout_roc_auc": roc_auc_score(y, proba),
        "holdout_f1": f1_score(y, pred),
        "holdout_precision": precision_score(y, pred),
        "holdout_recall": recall_score(y, pred),
        "holdout_log_loss": log_loss(y, proba),
        "baseline_accuracy": baseline_accuracy,
    }
    metrics["accuracy_lift"] = metrics["holdout_accuracy"] - baseline_accuracy
    subgroups = subgroup_accuracy(cfg, holdout, pred)
    for row in subgroups.itertuples():
        metrics[f"subgroup_{row.subgroup}_{row.value}_accuracy"] = row.accuracy
    metrics = {k: float(v) for k, v in metrics.items()}

    gate = cfg.team["quality_gate"]
    checks = {
        "accuracy_lift": metrics["accuracy_lift"] >= gate["min_accuracy_lift_over_baseline"],
        "roc_auc": metrics["holdout_roc_auc"] >= gate["min_roc_auc"],
    }
    passed = all(checks.values())

    with stage_run(cfg, "evaluate") as run:
        mlflow.log_input(
            mlflow.data.from_pandas(holdout, name=f"{cfg.dataset}-holdout", targets=cfg.target), context="evaluation"
        )
        mlflow.log_metrics(metrics, model_id=state["model_id"])
        mlflow.log_params({f"gate.{k}": v for k, v in gate.items()})
        mlflow.log_dict({"passed": passed, "checks": checks, "thresholds": gate}, "quality_gate.json")
        mlflow.log_table(subgroups, "subgroup_accuracy.json")
        fig, ax = plt.subplots(figsize=(4, 4))
        ConfusionMatrixDisplay.from_predictions(y, pred, ax=ax, colorbar=False)
        ax.set_title(f"{cfg.experiment} holdout")
        mlflow.log_figure(fig, "confusion_matrix.png")
        plt.close(fig)
        mlflow.set_tag("quality_gate", "passed" if passed else "failed")

    cfg.save_state(eval_run_id=run.info.run_id, gate_passed=passed, holdout_accuracy=metrics["holdout_accuracy"])
    verdict = "PASSED" if passed else f"FAILED ({', '.join(k for k, ok in checks.items() if not ok)})"
    return metrics | {
        "gate_passed": passed,
        "summary": (
            f"accuracy {metrics['holdout_accuracy']:.3f} vs baseline {baseline_accuracy:.3f}, "
            f"ROC AUC {metrics['holdout_roc_auc']:.3f} - gate {verdict}"
        ),
    }
