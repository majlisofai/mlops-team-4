"""Stage 3 - prepare: split the history into training and holdout seasons."""

from __future__ import annotations

import mlflow

from pipeline.config import Config
from pipeline.data import read_raw
from pipeline.tracking import stage_run


def split(cfg: Config, df):
    """Split by season, not at random: the model must predict a season it has never seen."""
    s = cfg.data["split"]
    keep = cfg.data["keys"] + [s["season_column"]] + cfg.features + cfg.data["subgroups"] + [cfg.target]
    train = df[df[s["season_column"]].isin(s["train_seasons"])][keep].reset_index(drop=True)
    holdout = df[df[s["season_column"]].isin(s["holdout_seasons"])][keep].reset_index(drop=True)
    return train, holdout


def run(cfg: Config) -> dict:
    train, holdout = split(cfg, read_raw(cfg, "history"))
    out = cfg.work_dir / "prepared"
    out.mkdir(parents=True, exist_ok=True)
    train.to_csv(out / "train.csv", index=False)
    holdout.to_csv(out / "holdout.csv", index=False)

    s = cfg.data["split"]
    with stage_run(cfg, "prepare"):
        mlflow.log_params(
            {
                "train_seasons": s["train_seasons"],
                "holdout_seasons": s["holdout_seasons"],
                "features_numeric": cfg.numeric,
                "features_categorical": cfg.categorical,
                "target": cfg.target,
            }
        )
        mlflow.log_metrics(
            {
                "train_rows": len(train),
                "holdout_rows": len(holdout),
                "train_positive_rate": train[cfg.target].mean(),
                "holdout_positive_rate": holdout[cfg.target].mean(),
            }
        )
        for name, df in (("train", train), ("holdout", holdout)):
            mlflow.log_input(
                mlflow.data.from_pandas(df, source=str(out / f"{name}.csv"), name=f"{cfg.dataset}-{name}", targets=cfg.target),
                context=name,
            )
        mlflow.log_artifacts(str(out), "prepared")

    return {
        "train_rows": len(train),
        "holdout_rows": len(holdout),
        "summary": f"train {len(train):,} rows / holdout {len(holdout):,} rows",
    }
