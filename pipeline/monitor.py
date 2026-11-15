"""Stage 8 - monitor: input drift, training-serving skew and delayed labels for the 2026 season."""

from __future__ import annotations

import mlflow
import numpy as np
import pandas as pd
from mlflow.exceptions import MlflowException
from scipy.stats import ks_2samp
from sklearn.metrics import accuracy_score

from pipeline.config import Config
from pipeline.data import feature_frame, read_raw, read_window
from pipeline.predict import score
from pipeline.tracking import stage_run

EPS = 1e-4


def psi(expected: pd.Series, actual: pd.Series, bins: int = 10) -> float:
    """Population Stability Index. < 0.10 stable, 0.10-0.25 moderate shift, > 0.25 large shift."""
    if not (pd.api.types.is_numeric_dtype(expected) and pd.api.types.is_numeric_dtype(actual)):
        cats = sorted(set(expected) | set(actual))
        e = expected.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
        a = actual.value_counts(normalize=True).reindex(cats, fill_value=0).to_numpy()
    else:
        edges = np.unique(np.quantile(expected, np.linspace(0, 1, bins + 1)))
        edges[0], edges[-1] = -np.inf, np.inf
        if len(edges) < 3:  # (near-)constant reference: compare "same value" vs "different value"
            ref = expected.iloc[0]
            e = np.array([(expected == ref).mean(), (expected != ref).mean()])
            a = np.array([(actual == ref).mean(), (actual != ref).mean()])
        else:
            e = np.histogram(expected, edges)[0] / len(expected)
            a = np.histogram(actual, edges)[0] / len(actual)
    e, a = np.clip(e, EPS, None), np.clip(a, EPS, None)
    return float(np.sum((a - e) * np.log(a / e)))


def compare(cfg: Config, reference: pd.DataFrame, current: pd.DataFrame) -> pd.DataFrame:
    thresholds = cfg.team["monitoring"]
    rows = []
    for col in cfg.features:
        value = psi(reference[col], current[col])
        numeric = col in cfg.numeric
        pvalue = float(ks_2samp(reference[col], current[col]).pvalue) if numeric else None
        # PSI is noisy on small windows: a numeric alert also needs a significant KS test.
        significant = pvalue is None or pvalue < thresholds["ks_pvalue"]
        if value > thresholds["psi_alert"] and significant:
            status = "alert"
        elif value > thresholds["psi_warning"]:
            status = "warning"
        else:
            status = "ok"
        rows.append(
            {
                "feature": col,
                "psi": round(value, 4),
                "ks_pvalue": round(pvalue, 4) if numeric else None,
                "reference_mean": round(float(reference[col].mean()), 3) if numeric else None,
                "current_mean": round(float(current[col].mean()), 3) if numeric else None,
                "status": status,
            }
        )
    return pd.DataFrame(rows)


def alerted(table: pd.DataFrame) -> list[str]:
    return table.loc[table["status"] == "alert", "feature"].tolist()


def delayed_labels(cfg: Config) -> dict | None:
    """Predictions are made on provisional results; the true labels arrive days later. How wrong were we?"""
    season = read_raw(cfg, "provisional_2026")
    final = read_raw(cfg, "final_2026")
    try:
        preds = score(cfg, feature_frame(cfg, season))
    except MlflowException:
        return None
    joined = season.assign(prediction=preds).merge(final[cfg.data["keys"] + [cfg.data["final_label"]]], on=cfg.data["keys"])
    return {
        "season_2026_rows": len(joined),
        "season_2026_label_corrections": int((joined[cfg.target] != joined[cfg.data["final_label"]]).sum()),
        "season_2026_accuracy_provisional": accuracy_score(joined[cfg.target], joined["prediction"]),
        "season_2026_accuracy_final": accuracy_score(joined[cfg.data["final_label"]], joined["prediction"]),
    }


def markdown_table(table: pd.DataFrame) -> str:
    header = "| " + " | ".join(table.columns) + " |"
    rule = "|" + "---|" * len(table.columns)
    body = ["| " + " | ".join("" if pd.isna(v) else str(v) for v in row) + " |" for row in table.itertuples(index=False)]
    return "\n".join([header, rule, *body])


def to_frame(cfg: Config, rows: list[dict]) -> pd.DataFrame:
    return feature_frame(cfg, pd.DataFrame(rows))


def run(cfg: Config) -> dict:
    reference = to_frame(cfg, read_window(cfg, "reference_window")["rows"])
    drift_window = read_window(cfg, "drift_window")
    skew_window = read_window(cfg, "skew_window")
    season = feature_frame(cfg, read_raw(cfg, "provisional_2026"))

    checks = {
        "drift_scenario": compare(cfg, reference, to_frame(cfg, drift_window["rows"])),
        "serving_skew": compare(cfg, to_frame(cfg, skew_window["recomputed"]), to_frame(cfg, skew_window["served"])),
        "season_2026": compare(cfg, reference, season),
    }
    labels = delayed_labels(cfg)

    lines = [f"# Monitoring report - {cfg.experiment}", ""]
    lines += [f"- **Drift scenario:** {drift_window['about']}", f"- **Skew scenario:** {skew_window['about']}", ""]
    for name, table in checks.items():
        lines += [f"## {name}", "", markdown_table(table), ""]
    if labels:
        lines += ["## delayed labels (2026)", ""] + [
            f"- {k}: {v:.3f}" if isinstance(v, float) else f"- {k}: {v}" for k, v in labels.items()
        ]
    report = cfg.reports_dir / f"monitoring_{cfg.dataset}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n")

    with stage_run(cfg, "monitor"):
        for name, table in checks.items():
            mlflow.log_table(table, f"{name}.json")
            mlflow.log_metric(f"{name}_psi_max", float(table["psi"].max()))
            mlflow.log_metric(f"{name}_features_alerted", len(alerted(table)))
            mlflow.set_tag(f"{name}_alerts", ",".join(alerted(table)) or "none")
        if labels:
            mlflow.log_metrics({k: float(v) for k, v in labels.items()})
        mlflow.log_artifact(str(report))

    parts = [f"{name}: {', '.join(alerted(t)) or 'no'} alerts" for name, t in checks.items()]
    if labels:
        parts.append(
            f"2026 accuracy {labels['season_2026_accuracy_provisional']:.3f} provisional "
            f"/ {labels['season_2026_accuracy_final']:.3f} final labels"
        )
    return {**(labels or {}), "summary": "; ".join(parts)}
