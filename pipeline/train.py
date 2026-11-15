"""Stage 4 - train: fit a scikit-learn pipeline and log it to MLflow with its signature."""

from __future__ import annotations

import mlflow
import pandas as pd
from mlflow.models import infer_signature
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold, cross_val_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from pipeline.config import Config
from pipeline.data import feature_frame
from pipeline.tracking import stage_run

ESTIMATORS = {
    "logistic_regression": LogisticRegression,
    "random_forest": RandomForestClassifier,
    "gradient_boosting": GradientBoostingClassifier,
}


def build_model(cfg: Config) -> Pipeline:
    spec = cfg.team["model"]
    if spec["type"] not in ESTIMATORS:
        raise ValueError(f"model.type must be one of {list(ESTIMATORS)}, got {spec['type']!r}")
    estimator = ESTIMATORS[spec["type"]](**(spec.get("params") or {}))
    prepare = ColumnTransformer(
        [
            ("numeric", StandardScaler(), cfg.numeric),
            ("categorical", OneHotEncoder(handle_unknown="ignore"), cfg.categorical),
        ]
    )
    return Pipeline([("prepare", prepare), ("model", estimator)])


def run(cfg: Config) -> dict:
    train = pd.read_csv(cfg.work_dir / "prepared" / "train.csv")
    X, y = feature_frame(cfg, train), train[cfg.target]
    seasons = train[cfg.data["split"]["season_column"]]
    model = build_model(cfg)
    spec = cfg.team["model"]

    with stage_run(cfg, "train") as run:
        mlflow.log_params({"model_type": spec["type"], **{f"model.{k}": v for k, v in (spec.get("params") or {}).items()}})

        # Leave-one-season-out: each fold predicts a season the model did not train on.
        cv = cross_val_score(model, X, y, groups=seasons, cv=GroupKFold(n_splits=seasons.nunique()), scoring="accuracy")
        model.fit(X, y)

        info = mlflow.sklearn.log_model(
            model,
            name="model",
            signature=infer_signature(X, model.predict(X)),
            input_example=X.head(5),
        )
        metrics = {
            "cv_accuracy_mean": float(cv.mean()),
            "cv_accuracy_std": float(cv.std()),
            "train_accuracy": float(model.score(X, y)),
        }
        mlflow.log_metrics(metrics, model_id=info.model_id)

    cfg.save_state(train_run_id=run.info.run_id, model_uri=info.model_uri, model_id=info.model_id)
    return metrics | {"summary": f"{spec['type']}, season CV accuracy {cv.mean():.3f} ± {cv.std():.3f}"}
