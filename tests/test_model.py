"""The default model must beat the baseline rule on the holdout season (no MLflow needed)."""

from sklearn.metrics import accuracy_score

from pipeline.data import feature_frame, read_raw
from pipeline.evaluate import baseline_predictions
from pipeline.prepare import split
from pipeline.train import build_model


def test_model_beats_baseline(cfg):
    train, holdout = split(cfg, read_raw(cfg, "history"))
    model = build_model(cfg).fit(feature_frame(cfg, train), train[cfg.target])
    accuracy = accuracy_score(holdout[cfg.target], model.predict(feature_frame(cfg, holdout)))
    baseline = accuracy_score(holdout[cfg.target], baseline_predictions(cfg, holdout))
    assert accuracy > baseline
