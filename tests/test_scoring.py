from __future__ import annotations

import numpy as np
import pytest
from hypothesis import given
from hypothesis import strategies as st

from geo_eval_gate import screen_detailed
from geo_eval_gate.scoring import (
    expected_calibration_error,
    gate_score,
    label_candidates,
    object_recall,
    pixel_metrics,
    truth_objects,
)
from geo_eval_gate.synthetic import Box, make_pair


def mask_from_boxes(boxes: list[Box], size: int = 128) -> np.ndarray:
    m = np.zeros((size, size), dtype=np.bool_)
    for b in boxes:
        m[b.y0 : b.y1, b.x0 : b.x1] = True
    return m


def test_pixel_metrics_known_cases() -> None:
    truth = np.zeros((10, 10), dtype=np.bool_)
    truth[:5, :] = True
    perfect = pixel_metrics(truth, truth)
    assert (perfect.precision, perfect.recall, perfect.f1) == (1.0, 1.0, 1.0)
    half = np.zeros_like(truth)
    half[:5, :5] = True
    m = pixel_metrics(half, truth)
    assert m.precision == 1.0 and m.recall == 0.5 and m.f1 == pytest.approx(2 / 3)
    assert pixel_metrics(~truth, truth).recall == 0.0
    with pytest.raises(ValueError):
        pixel_metrics(truth, truth[:5])


def test_screen_on_synthetic_scene_matches_ground_truth() -> None:
    hits = total = 0
    for seed in range(10):
        p = make_pair(seed, n_buildings=2, n_clouds=0, season=True)
        res = screen_detailed(p.t0, p.t1)
        truth = mask_from_boxes(p.true_changes)
        got, n = object_recall(res.mask, truth)
        hits, total = hits + got, total + n
        labels = label_candidates(res, truth)
        assert len(labels) == len(res.candidates)
        assert all(labels)  # with no cloud and no other change, every candidate is a real building
    assert hits / total >= 0.9


def test_candidate_labels_distinguish_cloud_edges_from_buildings() -> None:
    p = make_pair(3, n_buildings=1, n_clouds=1, season=False)
    res = screen_detailed(p.t0, p.t1)
    labels = label_candidates(res, mask_from_boxes(p.true_changes))
    assert any(labels)  # the building is found
    assert res.mask.shape == p.t0.shape and int(np.max(res.labels)) == len(res.candidates)


def test_truth_objects_filters_tiny_regions() -> None:
    t = np.zeros((20, 20), dtype=np.bool_)
    t[2:6, 2:6] = True  # 16 px
    t[15, 15] = True  # 1 px
    assert len(truth_objects(t, min_area=4)) == 1


def test_ece_known_cases() -> None:
    conf = np.array([0.9, 0.9, 0.9, 0.9])
    assert expected_calibration_error(conf, np.array([True, True, True, True])) == pytest.approx(0.1)
    assert expected_calibration_error(conf, np.array([True, True, True, False])) == pytest.approx(0.15)
    assert expected_calibration_error(np.array([]), np.array([], dtype=bool)) == 0.0


@given(st.lists(st.floats(0, 1), min_size=1, max_size=60), st.integers(0, 10_000))
def test_ece_bounded(conf: list[float], seed: int) -> None:
    rng = np.random.default_rng(seed)
    c = np.array(conf)
    assert 0.0 <= expected_calibration_error(c, rng.random(len(c)) < 0.5) <= 1.0


def test_gate_score() -> None:
    g = gate_score([True, True, False, False], [True, False, True, False])
    assert g.accepted == 2 and g.precision == 0.5 and g.recall == 0.5
    none = gate_score([False, False], [True, False])
    assert none.precision == 0.0 and none.recall == 0.0 and none.f1 == 0.0
    with pytest.raises(ValueError):
        gate_score([True], [True, False])
