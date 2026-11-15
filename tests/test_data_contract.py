"""The data contract: the source data looks the way the configs and the dataset README say it does."""

import pytest
from sklearn.metrics import accuracy_score

from pipeline.data import read_raw
from pipeline.evaluate import baseline_predictions
from pipeline.prepare import split
from pipeline.validate import check


def test_no_leakage_in_features(cfg):
    assert not set(cfg.features) & set(cfg.data["leakage"])
    assert cfg.target not in cfg.features


def test_history_passes_validation(cfg):
    report = check(cfg, read_raw(cfg, "history"))
    assert report["passed"], report["errors"]


def test_2026_season_passes_validation(cfg):
    report = check(cfg, read_raw(cfg, "provisional_2026"), label_required=False)
    assert report["passed"], report["errors"]


def test_row_count_matches_readme(cfg):
    assert len(read_raw(cfg, "history")) == cfg.data["facts"]["history_rows"]


def test_baseline_rule_matches_readme(cfg):
    _, holdout = split(cfg, read_raw(cfg, "history"))
    accuracy = accuracy_score(holdout[cfg.target], baseline_predictions(cfg, holdout))
    assert accuracy == pytest.approx(cfg.data["facts"]["baseline_holdout_accuracy"], abs=0.001)


def test_validation_catches_leakage(cfg):
    cfg.data["features"]["numeric"].append(cfg.data["leakage"][0])
    try:
        report = check(cfg, read_raw(cfg, "history"))
    finally:
        cfg.data["features"]["numeric"].pop()
    assert not report["passed"]
    assert "post-event columns" in report["errors"][0]


def test_validation_catches_bad_values(cfg):
    df = read_raw(cfg, "history")
    col, (lo, hi) = next(iter(cfg.data["checks"]["ranges"].items()))
    df.loc[0, col] = hi + 1000
    df.loc[1, cfg.categorical[0]] = "unknown"
    df = df.astype({cfg.numeric[1]: "float64"})
    df.loc[2, cfg.numeric[1]] = None
    errors = " ".join(check(cfg, df)["errors"])
    assert f"{col}: 1 rows outside" in errors
    assert "unknown categories" in errors
    assert "missing values" in errors
