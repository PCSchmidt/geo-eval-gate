from __future__ import annotations

import numpy as np
from hypothesis import given
from hypothesis import strategies as st

from geo_eval_gate import screen_detailed
from geo_eval_gate.candidate_set import (
    CandidateRecord,
    build_records,
    cap_records,
    context_crops,
    context_window,
    stretch_pair,
)
from geo_eval_gate.screening import Candidate
from geo_eval_gate.synthetic import make_pair


def cand(x0: int, y0: int, x1: int, y1: int) -> Candidate:
    return Candidate(x0, y0, x1, y1, (x1 - x0) * (y1 - y0), 0.5, 0.5)


def test_stretch_is_shared_so_brightness_change_survives() -> None:
    p = make_pair(0, season=False, n_clouds=0)
    a, b = stretch_pair(p.t0, p.t1)
    assert a.dtype == np.uint8 and a.shape == b.shape == (*p.t0.shape, 3)
    # a building brightens pixels between dates, and the shared window keeps that visible
    box = p.true_changes[0]
    assert b[box.y0 : box.y1, box.x0 : box.x1].mean() != a[box.y0 : box.y1, box.x0 : box.x1].mean()
    assert int(np.max(a)) <= 255 and int(np.min(a)) >= 0


@given(st.integers(0, 90), st.integers(0, 90), st.integers(2, 30), st.integers(2, 30))
def test_window_is_inside_image_and_contains_candidate_centre(x: int, y: int, w: int, h: int) -> None:
    shape = (100, 120)
    c = cand(x, y, min(x + w, 120), min(y + h, 100))
    y0, y1, x0, x1 = context_window(shape, c)
    assert 0 <= y0 < y1 <= shape[0] and 0 <= x0 < x1 <= shape[1]
    cy, cx = (c.y0 + c.y1) // 2, (c.x0 + c.x1) // 2
    assert y0 <= cy < y1 and x0 <= cx < x1


def test_window_on_a_tiny_image_is_the_whole_image() -> None:
    assert context_window((20, 30), cand(5, 5, 9, 9)) == (0, 20, 0, 30)


def test_crops_have_matching_shapes() -> None:
    p = make_pair(1)
    a, b = stretch_pair(p.t0, p.t1)
    ca, cb = context_crops(a, b, cand(30, 30, 45, 45))
    assert ca.shape == cb.shape and ca.shape[2] == 3


def test_records_label_buildings_positive_and_cap_is_seeded() -> None:
    p = make_pair(2, n_buildings=2, n_clouds=0, season=True)
    res = screen_detailed(p.t0, p.t1)
    truth = np.zeros(p.t0.shape, dtype=bool)
    for box in p.true_changes:
        truth[box.y0 : box.y1, box.x0 : box.x1] = True
    recs = build_records(7, res, truth)
    assert recs and all(r.pair == 7 for r in recs) and all(r.positive for r in recs)
    many = [CandidateRecord(7, i, recs[0].candidate, True) for i in range(30)]  # 30 distinct records
    first, again = cap_records(many, 5, seed=0), cap_records(many, 5, seed=0)
    assert first == again and len(first) == 5
    assert cap_records(many, 5, seed=1) != first  # a different seed draws a different subset
    assert [r.index for r in first] == sorted(r.index for r in first)  # stable order
    assert cap_records(recs, 1000) == recs
