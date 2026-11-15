"""Monitoring must raise alerts on the planted scenarios and stay quiet on stable data."""

import numpy as np
import pandas as pd

from pipeline.data import read_window
from pipeline.monitor import alerted, compare, psi, to_frame

# The feature each scenario file changes (see the "about" field of the JSON windows).
DRIFTED = {"f1": "rain_prob", "spl": "kickoff_temp_c"}
SKEWED = {"f1": "quali_gap_ms", "spl": "travel_km"}


def test_psi_is_zero_for_identical_data():
    s = pd.Series(np.random.default_rng(0).normal(size=1000))
    assert psi(s, s) < 0.01


def test_psi_flags_a_shift():
    rng = np.random.default_rng(0)
    assert psi(pd.Series(rng.normal(size=1000)), pd.Series(rng.normal(1.0, size=1000))) > 0.25


def test_drift_scenario_is_detected(cfg):
    reference = to_frame(cfg, read_window(cfg, "reference_window")["rows"])
    current = to_frame(cfg, read_window(cfg, "drift_window")["rows"])
    assert DRIFTED[cfg.dataset] in alerted(compare(cfg, reference, current))


def test_serving_skew_is_detected(cfg):
    window = read_window(cfg, "skew_window")
    table = compare(cfg, to_frame(cfg, window["recomputed"]), to_frame(cfg, window["served"]))
    assert alerted(table) == [SKEWED[cfg.dataset]]
