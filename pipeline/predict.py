"""Stage 7 - predict: score the 2026 season with the @champion model, or through the live model API with --endpoint."""

from __future__ import annotations

import mlflow
import pandas as pd
import requests
from mlflow.exceptions import MlflowException

from pipeline.config import Config
from pipeline.data import feature_frame, read_raw
from pipeline.tracking import stage_run


def champion_uri(cfg: Config) -> str:
    return f"models:/{cfg.model_name}@champion"


def score(cfg: Config, X: pd.DataFrame, endpoint: str | None = None):
    """Predictions from the registry (batch) or from `make serve` (online). Both must agree."""
    if endpoint:
        resp = requests.post(endpoint, json={"dataframe_split": X.to_dict(orient="split")}, timeout=60)
        resp.raise_for_status()
        return resp.json()["predictions"]
    return mlflow.pyfunc.load_model(champion_uri(cfg)).predict(X)


def run(cfg: Config, endpoint: str | None = None) -> dict:
    season = read_raw(cfg, "provisional_2026")
    X = feature_frame(cfg, season)

    with stage_run(cfg, "predict"):
        try:
            champion = mlflow.MlflowClient().get_model_version_by_alias(cfg.model_name, "champion")
        except MlflowException:
            mlflow.set_tag("skipped", "no champion model")
            return {"summary": "skipped: no @champion model in the registry yet"}

        preds = score(cfg, X, endpoint)
        columns = cfg.data["keys"] + ["season", "round"] + cfg.data["subgroups"]
        out = season[columns].assign(prediction=preds)
        path = cfg.work_dir / "predictions" / "predictions_2026.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        out.to_csv(path, index=False)

        mlflow.log_params(
            {"model_uri": champion_uri(cfg), "model_version": champion.version, "mode": "api" if endpoint else "batch"}
        )
        mlflow.log_input(mlflow.data.from_pandas(X, name=f"{cfg.dataset}-2026-provisional"), context="inference")
        mlflow.log_metrics({"rows_scored": len(out), "predicted_positive_rate": float(out["prediction"].mean())})
        mlflow.log_artifact(str(path), "predictions")

    how = f"via {endpoint}" if endpoint else "in batch"
    return {"rows": len(out), "summary": f"{len(out)} rows of 2026 scored {how} with @champion v{champion.version}"}
