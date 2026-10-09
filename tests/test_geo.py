from __future__ import annotations

import json

import numpy as np
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from geo_eval_gate import (
    Decision,
    Scene,
    ScreeningConfig,
    ScriptedVLM,
    crop,
    evaluate,
    screen,
)
from geo_eval_gate.screening import cloud_mask, ndvi, ssim_map
from geo_eval_gate.synthetic import Box, make_pair

IMG = np.zeros((8, 8, 3), dtype=np.uint8)


def overlaps(c_box: tuple[int, int, int, int], b: Box) -> bool:
    x0, y0, x1, y1 = c_box
    return x0 < b.x1 and b.x0 < x1 and y0 < b.y1 and b.y0 < y1


def test_ssim_identity_and_difference() -> None:
    rng = np.random.default_rng(0)
    a = rng.random((32, 32))
    assert np.allclose(ssim_map(a, a), 1.0)
    assert ssim_map(a, 1.0 - a).mean() < 0.5


def test_ndvi_range() -> None:
    p = make_pair(1)
    v = ndvi(p.t0)
    assert (v >= -1).all() and (v <= 1).all() and v.mean() > 0.5


def test_seasonal_change_alone_yields_no_candidates() -> None:
    p = make_pair(2, n_buildings=0, n_clouds=0, season=True)
    assert screen(p.t0, p.t1) == []


def test_buildings_found_and_cloud_suppressed() -> None:
    hits = false_cloud = 0
    total = 0
    for seed in range(20):
        p = make_pair(seed, n_buildings=2, n_clouds=1)
        cands = screen(p.t0, p.t1)
        boxes = [(c.x0, c.y0, c.x1, c.y1) for c in cands]
        total += len(p.true_changes)
        hits += sum(any(overlaps(b, t) for b in boxes) for t in p.true_changes)
        false_cloud += sum(
            any(overlaps(b, n) for n in p.nuisance) and not any(overlaps(b, t) for t in p.true_changes)
            for b in boxes
        )
    assert hits / total >= 0.9
    assert false_cloud == 0


def test_cloud_masking_matters() -> None:
    p = make_pair(3, n_buildings=0, n_clouds=1, season=False)
    assert screen(p.t0, p.t1, ScreeningConfig(mask_clouds=False)) != []
    assert screen(p.t0, p.t1) == []


def test_coregistration_enforced() -> None:
    a, b = make_pair(4, size=64), make_pair(4, size=96)
    with pytest.raises(ValueError):
        screen(a.t0, b.t1)


def test_crop_within_bounds() -> None:
    p = make_pair(5)
    for c in screen(p.t0, p.t1):
        out = crop(p.t1, c)
        assert 0 < out.shape[0] <= 128 and out.shape[2] == 3


GOOD = {"confidence": 0.93, "change_class": "NEW_STRUCTURE", "rationale": "Rectangular roof appears."}


@pytest.mark.parametrize(
    ("raw", "decision"),
    [
        (json.dumps(GOOD), Decision.ACCEPT),
        (json.dumps({**GOOD, "confidence": 0.5}), Decision.REJECT_LOW_CONFIDENCE),
        (json.dumps({**GOOD, "change_class": "CLOUD_ARTIFACT"}), Decision.REJECT_NOT_ACTIONABLE),
        (json.dumps({**GOOD, "change_class": "SEASONAL_DEFOLIATION"}), Decision.REJECT_NOT_ACTIONABLE),
        (json.dumps({**GOOD, "confidence": 1.4}), Decision.REJECT_SCHEMA),
        (json.dumps({**GOOD, "change_class": "TANK"}), Decision.REJECT_SCHEMA),
        (json.dumps({**GOOD, "rationale": "short"}), Decision.REJECT_SCHEMA),
        (json.dumps({**GOOD, "extra": 1}), Decision.REJECT_SCHEMA),
        ("The image shows a new building.", Decision.REJECT_SCHEMA),
        ("", Decision.REJECT_SCHEMA),
    ],
)
def test_gate_decisions(raw: str, decision: Decision) -> None:
    assert evaluate(ScriptedVLM(raw), IMG, IMG).decision is decision


@given(st.text(max_size=300))
def test_gate_never_accepts_unvalidated_text(raw: str) -> None:
    out = evaluate(ScriptedVLM(raw), IMG, IMG)
    if out.decision is Decision.ACCEPT:
        assert out.result is not None and 0.8 <= out.result.confidence <= 1.0


@settings(max_examples=25, deadline=None)
@given(st.integers(0, 10_000))
def test_screen_boxes_are_in_bounds(seed: int) -> None:
    p = make_pair(seed, size=64, n_buildings=1, n_clouds=1)
    for c in screen(p.t0, p.t1):
        assert 0 <= c.x0 < c.x1 <= 64 and 0 <= c.y0 < c.y1 <= 64 and c.area_px >= 25


def test_cloud_mask_flags_white_only() -> None:
    p = make_pair(6, n_buildings=0, n_clouds=1)
    m = cloud_mask(p.t1)
    n = p.nuisance[0]
    assert m[n.y0 + 3 : n.y1 - 3, n.x0 + 3 : n.x1 - 3].all()
    assert not cloud_mask(p.t0).any()


def test_scene_rejects_mismatched_bands() -> None:
    with pytest.raises(ValueError):
        Scene(np.zeros((4, 4)), np.zeros((4, 4)), np.zeros((4, 5)), np.zeros((4, 4)))
