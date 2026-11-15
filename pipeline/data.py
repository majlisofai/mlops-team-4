"""Read the files the ingest stage downloaded and build model inputs."""

from __future__ import annotations

import json

import pandas as pd

from pipeline.config import Config


def raw_path(cfg: Config, key: str):
    return cfg.work_dir / "raw" / cfg.data["source"]["files"][key]


def read_raw(cfg: Config, key: str) -> pd.DataFrame:
    path = raw_path(cfg, key)
    if not path.exists():
        raise FileNotFoundError(f"{path} not found - run the ingest stage first (make ingest)")
    return pd.read_csv(path)


def read_window(cfg: Config, key: str) -> dict:
    """Monitoring scenario windows are JSON: {"about": ..., "rows": [...]} or {"served": [...], "recomputed": [...]}."""
    return json.loads(raw_path(cfg, key).read_text())


def feature_frame(cfg: Config, df: pd.DataFrame) -> pd.DataFrame:
    """Exactly the columns the model sees, with one dtype per column for training, serving and monitoring."""
    X = df[cfg.features].copy()
    X[cfg.numeric] = X[cfg.numeric].astype("float64")
    X[cfg.categorical] = X[cfg.categorical].astype("str")
    return X
