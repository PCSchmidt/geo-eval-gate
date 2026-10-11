"""Candidates with ground-truth labels, and the image crops a vision model is shown.

Satellite reflectance is dark, so crops are contrast-stretched with ONE percentile window per scene
pair, shared by the before and after images; a change in brightness between dates therefore stays
visible instead of being normalised away.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from .scene import Scene
from .scoring import label_candidates
from .screening import Candidate, ScreenResult

U8 = npt.NDArray[np.uint8]
BoolArray = npt.NDArray[np.bool_]


def stretch_pair(t0: Scene, t1: Scene, lo: float = 2.0, hi: float = 98.0) -> tuple[U8, U8]:
    """RGB uint8 images of both dates, stretched with one shared percentile window."""
    cubes = [np.stack([s.red, s.green, s.blue], axis=-1) for s in (t0, t1)]
    both = np.concatenate([c.reshape(-1, 3) for c in cubes])
    low, high = np.percentile(both, [lo, hi])
    if high <= low:
        high = low + 1e-6
    return tuple(  # type: ignore[return-value]
        np.asarray(np.clip((c - low) / (high - low), 0.0, 1.0) * 255.0, dtype=np.uint8) for c in cubes
    )


def context_window(shape: tuple[int, int], c: Candidate, min_window: int = 48, scale: float = 3.0) -> tuple[int, int, int, int]:
    """(y0, y1, x0, x1) of a square-ish window centred on the candidate, shifted to stay in the image."""
    h, w = shape
    side = int(max(min_window, scale * max(c.x1 - c.x0, c.y1 - c.y0)))
    side_y, side_x = min(side, h), min(side, w)
    cy, cx = (c.y0 + c.y1) // 2, (c.x0 + c.x1) // 2
    y0 = int(np.clip(cy - side_y // 2, 0, h - side_y))
    x0 = int(np.clip(cx - side_x // 2, 0, w - side_x))
    return y0, y0 + side_y, x0, x0 + side_x


def context_crops(rgb0: U8, rgb1: U8, c: Candidate, min_window: int = 48, scale: float = 3.0) -> tuple[U8, U8]:
    h, w = int(rgb0.shape[0]), int(rgb0.shape[1])
    y0, y1, x0, x1 = context_window((h, w), c, min_window, scale)
    return rgb0[y0:y1, x0:x1], rgb1[y0:y1, x0:x1]


@dataclass(frozen=True)
class CandidateRecord:
    pair: int
    index: int  # position within the pair's candidate list
    candidate: Candidate
    positive: bool  # at least `min_overlap` of its pixels are inside the human change mask


def build_records(pair_index: int, res: ScreenResult, truth: BoolArray, min_overlap: float = 0.3) -> list[CandidateRecord]:
    labels = label_candidates(res, truth, min_overlap)
    return [CandidateRecord(pair_index, i, c, lab) for i, (c, lab) in enumerate(zip(res.candidates, labels, strict=True))]


def cap_records(records: list[CandidateRecord], cap: int, seed: int = 0) -> list[CandidateRecord]:
    """A uniform random subset of at most `cap` records, in a stable order."""
    if len(records) <= cap:
        return list(records)
    rng = np.random.default_rng(seed)
    keep = sorted(rng.choice(len(records), cap, replace=False).tolist())
    return [records[i] for i in keep]
