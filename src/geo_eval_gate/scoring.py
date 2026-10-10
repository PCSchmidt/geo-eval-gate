"""Scoring a screen and an evaluator gate against pixel-level ground truth.

Candidate-level labels: a candidate is *positive* when at least `min_overlap` of its own pixels
fall inside the ground-truth change mask. Object-level recall: a ground-truth object counts as
detected when at least `min_overlap` of its pixels fall inside the screen's change mask.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import ndimage

from .screening import ScreenResult

BoolArray = npt.NDArray[np.bool_]
FloatArray = npt.NDArray[np.float64]


@dataclass(frozen=True)
class PixelMetrics:
    tp: int
    fp: int
    fn: int
    precision: float
    recall: float
    f1: float


def pixel_metrics(pred: BoolArray, truth: BoolArray) -> PixelMetrics:
    if pred.shape != truth.shape:
        raise ValueError(f"shape mismatch {pred.shape} vs {truth.shape}")
    tp = int((pred & truth).sum())
    fp = int((pred & ~truth).sum())
    fn = int((~pred & truth).sum())
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return PixelMetrics(tp, fp, fn, p, r, 2 * p * r / (p + r) if p + r else 0.0)


def label_candidates(res: ScreenResult, truth: BoolArray, min_overlap: float = 0.3) -> list[bool]:
    """True for each candidate (same order as `res.candidates`) that overlaps ground truth."""
    out: list[bool] = []
    for i in range(len(res.candidates)):
        region = res.labels == i + 1
        out.append(bool((region & truth).sum() >= min_overlap * region.sum()))
    return out


def truth_objects(truth: BoolArray, min_area: int = 4) -> list[BoolArray]:
    labels, n = ndimage.label(truth)
    objs = [np.asarray(labels == i, dtype=np.bool_) for i in range(1, n + 1)]
    return [o for o in objs if int(o.sum()) >= min_area]


def object_recall(pred: BoolArray, truth: BoolArray, min_overlap: float = 0.3, min_area: int = 4) -> tuple[int, int]:
    """(ground-truth objects detected, ground-truth objects) using the screen's change mask."""
    objs = truth_objects(truth, min_area)
    hit = sum(int((o & pred).sum() >= min_overlap * o.sum()) for o in objs)
    return hit, len(objs)


def expected_calibration_error(conf: FloatArray, correct: BoolArray, bins: int = 10) -> float:
    """ECE of a confidence that claims to be P(correct): weighted mean |accuracy - confidence|."""
    if len(conf) == 0:
        return 0.0
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for lo, hi in itertools.pairwise(edges):
        m = (conf >= lo) & ((conf <= hi) if hi == 1.0 else (conf < hi))
        if m.any():
            total += float(m.mean()) * abs(float(correct[m].mean()) - float(conf[m].mean()))
    return total


@dataclass(frozen=True)
class GateScore:
    n: int
    accepted: int
    precision: float  # of accepted candidates, the share that are real change
    recall: float  # of real-change candidates, the share accepted
    f1: float


def gate_score(accepted: list[bool], positive: list[bool]) -> GateScore:
    if len(accepted) != len(positive):
        raise ValueError("length mismatch")
    tp = sum(a and p for a, p in zip(accepted, positive, strict=True))
    n_acc, n_pos = sum(accepted), sum(positive)
    prec = tp / n_acc if n_acc else 0.0
    rec = tp / n_pos if n_pos else 0.0
    return GateScore(len(accepted), n_acc, prec, rec, 2 * prec * rec / (prec + rec) if prec + rec else 0.0)
