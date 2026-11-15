"""Stage 2 - validate: schema, missing values, duplicates, ranges, categories and leakage. Any error stops the pipeline."""

from __future__ import annotations

import mlflow
import pandas as pd

from pipeline.config import Config
from pipeline.data import read_raw
from pipeline.tracking import stage_run


class ValidationError(RuntimeError):
    pass


def check(cfg: Config, df: pd.DataFrame, label_required: bool = True) -> dict:
    errors: list[str] = []
    warnings: list[str] = []
    keys = cfg.data["keys"]
    season = cfg.data["split"]["season_column"]

    # Leakage guard: a column known only after the event must never be a feature.
    leaked = sorted(set(cfg.features) & (set(cfg.data["leakage"]) | {cfg.target}))
    if leaked:
        errors.append(f"post-event columns used as features: {leaked}")

    required = keys + [season] + cfg.features + ([cfg.target] if label_required else [])
    missing = [c for c in required if c not in df.columns]
    if missing:
        errors.append(f"missing columns: {missing}")
        return {"rows": len(df), "errors": errors, "warnings": warnings, "passed": False}

    nulls = df[required].isna().sum()
    errors += [f"{col}: {n} missing values" for col, n in nulls[nulls > 0].items()]

    duplicates = int(df.duplicated(keys).sum())
    if duplicates:
        errors.append(f"{duplicates} duplicate rows on key {keys}")

    for col, (lo, hi) in cfg.data["checks"]["ranges"].items():
        values = pd.to_numeric(df[col], errors="coerce")
        not_numeric = int(values.isna().sum() - df[col].isna().sum())
        outside = int(((values < lo) | (values > hi)).sum())
        if not_numeric:
            errors.append(f"{col}: {not_numeric} non-numeric values")
        if outside:
            errors.append(f"{col}: {outside} rows outside [{lo}, {hi}]")

    for col, allowed in cfg.data["checks"]["categories"].items():
        unknown = sorted(set(df[col].dropna().astype(str)) - set(allowed))
        if unknown:
            errors.append(f"{col}: unknown categories {unknown}")

    if label_required:
        labels = set(df[cfg.target].unique())
        if not labels <= {0, 1}:
            errors.append(f"{cfg.target}: labels must be 0/1, found {sorted(labels)}")
        rates = df.groupby(season)[cfg.target].mean()
        for s, rate in rates.items():
            if not 0.2 <= rate <= 0.8:
                warnings.append(f"season {s}: positive rate {rate:.2f} is unusual")

    return {"rows": len(df), "errors": errors, "warnings": warnings, "passed": not errors}


def run(cfg: Config) -> dict:
    history = read_raw(cfg, "history")
    season_2026 = read_raw(cfg, "provisional_2026")
    reports = {
        "history": check(cfg, history),
        "provisional_2026": check(cfg, season_2026, label_required=False),
    }
    errors = [f"{name}: {e}" for name, r in reports.items() for e in r["errors"]]
    warnings = [f"{name}: {w}" for name, r in reports.items() for w in r["warnings"]]

    with stage_run(cfg, "validate"):
        mlflow.log_metrics({"validation_errors": len(errors), "validation_warnings": len(warnings)})
        mlflow.log_dict(reports, "validation_report.json")
        mlflow.log_table(history[cfg.features].describe(include="all").T.reset_index(), "feature_profile.json")
        mlflow.set_tag("validation", "passed" if not errors else "failed")
        if errors:
            raise ValidationError("data validation failed:\n  " + "\n  ".join(errors))

    return {
        "errors": 0,
        "warnings": len(warnings),
        "summary": f"passed: {sum(r['rows'] for r in reports.values()):,} rows checked, {len(warnings)} warnings",
    }
