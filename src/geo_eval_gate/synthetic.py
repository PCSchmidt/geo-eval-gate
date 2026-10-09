"""Seeded synthetic scene pairs with known injected changes, for tests and benchmarks."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage

from .scene import Scene


@dataclass(frozen=True)
class Box:
    x0: int
    y0: int
    x1: int
    y1: int


@dataclass(frozen=True)
class SyntheticPair:
    t0: Scene
    t1: Scene
    true_changes: list[Box]  # real construction only
    nuisance: list[Box]  # clouds / seasonal patches that must NOT count as change


def _vegetated(rng: np.random.Generator, size: int) -> Scene:
    texture = ndimage.gaussian_filter(rng.normal(0, 1, (size, size)), 3)
    texture = (texture - texture.min()) / (np.ptp(texture) + 1e-9)
    red = 0.08 + 0.05 * texture + rng.normal(0, 0.004, (size, size))
    nir = 0.45 + 0.1 * texture + rng.normal(0, 0.004, (size, size))
    green = 0.12 + 0.05 * texture + rng.normal(0, 0.004, (size, size))
    blue = 0.06 + 0.03 * texture + rng.normal(0, 0.004, (size, size))
    return Scene(red=red, green=green, blue=blue, nir=nir)


def make_pair(
    seed: int, size: int = 128, n_buildings: int = 2, n_clouds: int = 1, season: bool = True
) -> SyntheticPair:
    rng = np.random.default_rng(seed)
    t0 = _vegetated(rng, size)
    bands = {k: getattr(t0, k).copy() for k in ("red", "green", "blue", "nir")}
    for arr in bands.values():
        arr += rng.normal(0, 0.003, arr.shape)  # sensor / illumination noise between dates
    if season:
        # Autumn: mild global vegetation decline with smooth spatial pattern, no structural change.
        bands["nir"] *= 0.82
        bands["red"] *= 1.25
    truth: list[Box] = []
    nuisance: list[Box] = []
    for _ in range(n_buildings):
        w, h = (int(v) for v in rng.integers(12, 20, 2))
        x, y = (int(v) for v in rng.integers(4, size - 24, 2))
        bands["red"][y : y + h, x : x + w] = 0.32
        bands["green"][y : y + h, x : x + w] = 0.30
        bands["blue"][y : y + h, x : x + w] = 0.28
        bands["nir"][y : y + h, x : x + w] = 0.33
        truth.append(Box(x, y, x + w, y + h))
    for _ in range(n_clouds):
        w, h = (int(v) for v in rng.integers(16, 26, 2))
        x, y = (int(v) for v in rng.integers(2, size - 30, 2))
        for arr in bands.values():
            arr[y : y + h, x : x + w] = 0.9
        nuisance.append(Box(x, y, x + w, y + h))
    return SyntheticPair(
        t0=t0,
        t1=Scene(bands["red"], bands["green"], bands["blue"], bands["nir"]),
        true_changes=truth,
        nuisance=nuisance,
    )
