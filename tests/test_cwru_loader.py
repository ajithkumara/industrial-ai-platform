"""
Offline tests for ml/cwru_loader.py. No .mat files or Azure connection
required — feature formulas and windowing/labeling logic are tested on
synthetic numpy arrays.
"""

from __future__ import annotations

import numpy as np
import pytest

from ml import cwru_loader as loader


def test_label_for_filename_matches_all_four_classes():
    assert loader._label_for_filename("normal_0hp.mat") == "normal"
    assert loader._label_for_filename("inner_race_007_0hp.mat") == "inner_race"
    assert loader._label_for_filename("ball_021_3hp.mat") == "ball"
    assert loader._label_for_filename("outer_race_007_2hp.mat") == "outer_race"


def test_label_for_filename_rejects_unknown_prefix():
    with pytest.raises(ValueError):
        loader._label_for_filename("mystery_0hp.mat")


def test_windows_for_recording_drops_incomplete_final_window():
    # 5000 samples / 2048 = 2 complete windows, 904 samples dropped.
    signal = np.arange(5000, dtype=float)
    windows = loader._windows_for_recording(signal, loader.WINDOW_SAMPLES)
    assert len(windows) == 2
    assert len(windows[0]) == loader.WINDOW_SAMPLES
    assert len(windows[1]) == loader.WINDOW_SAMPLES
    # windows are non-overlapping and in order
    assert windows[0][0] == 0
    assert windows[1][0] == loader.WINDOW_SAMPLES


def test_windows_for_recording_empty_when_shorter_than_one_window():
    signal = np.arange(100, dtype=float)
    assert loader._windows_for_recording(signal, loader.WINDOW_SAMPLES) == []


def test_compute_features_on_a_known_constant_signal():
    # A constant signal has zero variance, so rms == |constant|, crest == 1.
    window = np.full(loader.WINDOW_SAMPLES, 2.0)
    features = loader._compute_features(window)
    assert features["rms"] == pytest.approx(2.0)
    assert features["peak"] == pytest.approx(2.0)
    assert features["crest"] == pytest.approx(1.0)
    assert features["variance"] == pytest.approx(0.0)
    assert features["mean_abs"] == pytest.approx(2.0)


def test_compute_features_crest_factor_definition():
    # A single large spike among near-zero samples should give a high
    # crest factor (peak far exceeds rms) -- this is the property crest
    # factor is meant to detect (impulsive bearing fault signatures).
    window = np.zeros(loader.WINDOW_SAMPLES)
    window[0] = 10.0
    features = loader._compute_features(window)
    assert features["peak"] == pytest.approx(10.0)
    assert features["crest"] > 20  # rms is small relative to the spike


def test_compute_features_never_produces_null_or_nan():
    rng = np.random.default_rng(42)
    window = rng.normal(size=loader.WINDOW_SAMPLES)
    features = loader._compute_features(window)
    for name, value in features.items():
        assert value is not None, name
        assert not (isinstance(value, float) and np.isnan(value)), name


def test_compute_features_zero_signal_does_not_raise_on_crest():
    # rms == 0 would make peak/rms a ZeroDivisionError -- must be handled,
    # not crash the whole recording's feature extraction.
    window = np.zeros(loader.WINDOW_SAMPLES)
    features = loader._compute_features(window)
    assert features["crest"] == 0.0


def test_assign_splits_is_recording_level_not_window_level():
    # Every recording of one label must land in exactly one split; the
    # function operates on filenames, not on individual windows, so this
    # is really testing that no filename can appear ambiguously.
    filenames = [
        "normal_0hp.mat", "normal_1hp.mat", "normal_2hp.mat", "normal_3hp.mat",
        "ball_007_0hp.mat", "ball_007_1hp.mat",
    ]
    splits = loader.assign_splits(filenames)
    assert set(splits) == set(filenames)
    assert all(v in ("TRAIN", "VALIDATION", "TEST") for v in splits.values())


def test_assign_splits_normal_four_files_populates_all_three_splits():
    # Regression guard mirroring test_feature_spec.py's equivalent test --
    # this is the exact real-world case (CWRU's 4-file Normal Baseline)
    # that motivated the small-N split fix.
    filenames = ["normal_0hp.mat", "normal_1hp.mat", "normal_2hp.mat", "normal_3hp.mat"]
    splits = loader.assign_splits(filenames)
    values = list(splits.values())
    assert "TRAIN" in values
    assert "VALIDATION" in values
    assert "TEST" in values


def test_assign_splits_fault_recordings_never_reach_train():
    filenames = [f"ball_007_{i}hp.mat" for i in range(4)] + [f"ball_021_{i}hp.mat" for i in range(4)]
    splits = loader.assign_splits(filenames)
    assert "TRAIN" not in splits.values()


def test_find_de_channel_prefers_highest_numeric_id_when_multiple_present():
    # Reproduces the real normal_2hp.mat quirk (bundles X098 and X099)
    # without needing the actual .mat file.
    mat = {
        "X098_DE_time": np.array([[1.0], [2.0]]),
        "X099_DE_time": np.array([[3.0], [4.0], [5.0]]),
        "__header__": b"stub",
    }
    signal = loader._find_de_channel(mat, "normal_2hp.mat")
    assert list(signal) == [3.0, 4.0, 5.0]


def test_find_de_channel_raises_when_no_de_variable_present():
    with pytest.raises(ValueError):
        loader._find_de_channel({"__header__": b"stub"}, "broken.mat")
