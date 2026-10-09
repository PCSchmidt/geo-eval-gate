"""Deterministic screening: NDVI delta + SSIM delta -> candidate bounding boxes."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from scipy import ndimage

from .scene import Array, Scene, require_coregistered

_EPS = 1e-9


def ndvi(scene: Scene) -> Array:
    return (scene.nir - scene.red) / (scene.nir + scene.red + _EPS)


def cloud_mask(
    scene: Scene, brightness: float = 0.75, max_saturation: float = 0.08, margin_px: int = 6
) -> npt.NDArray[np.bool_]:
    """Bright, spectrally flat (white) pixels, dilated past the SSIM window so no halo survives."""
    stack = np.stack([scene.red, scene.green, scene.blue], axis=0)
    mean = stack.mean(axis=0)
    spread = stack.max(axis=0) - stack.min(axis=0)
    mask = (mean > brightness) & (spread < max_saturation)
    return np.asarray(ndimage.binary_dilation(mask, iterations=margin_px), dtype=np.bool_)


def ssim_map(a: Array, b: Array, window: int = 7, data_range: float = 1.0) -> Array:
    """Mean-window SSIM (uniform kernel). 1.0 = identical, lower = structurally different."""
    c1, c2 = (0.01 * data_range) ** 2, (0.03 * data_range) ** 2
    mu_a = ndimage.uniform_filter(a, window)
    mu_b = ndimage.uniform_filter(b, window)
    var_a = ndimage.uniform_filter(a * a, window) - mu_a**2
    var_b = ndimage.uniform_filter(b * b, window) - mu_b**2
    cov = ndimage.uniform_filter(a * b, window) - mu_a * mu_b
    num = (2 * mu_a * mu_b + c1) * (2 * cov + c2)
    den = (mu_a**2 + mu_b**2 + c1) * (var_a + var_b + c2)
    return np.asarray(num / den, dtype=np.float64)


@dataclass(frozen=True)
class Candidate:
    x0: int
    y0: int
    x1: int  # exclusive
    y1: int  # exclusive
    area_px: int
    mean_abs_dndvi: float
    mean_ssim_delta: float


@dataclass(frozen=True)
class ScreeningConfig:
    ndvi_threshold: float = 0.25
    ssim_delta_threshold: float = 0.5
    min_area_px: int = 25
    open_iterations: int = 1
    close_iterations: int = 2
    mask_clouds: bool = True


def screen(t0: Scene, t1: Scene, cfg: ScreeningConfig | None = None) -> list[Candidate]:
    """Candidate change boxes. A pixel is a change if NDVI moved a lot AND structure changed."""
    cfg = cfg or ScreeningConfig()
    require_coregistered(t0, t1)
    dndvi = np.abs(ndvi(t1) - ndvi(t0))
    ssim_delta = 1.0 - ssim_map(t0.nir + t0.red, t1.nir + t1.red, data_range=2.0)
    mask = (dndvi > cfg.ndvi_threshold) | (ssim_delta > cfg.ssim_delta_threshold)
    if cfg.mask_clouds:
        mask &= ~(cloud_mask(t0) | cloud_mask(t1))
    if cfg.open_iterations:
        mask = ndimage.binary_opening(mask, iterations=cfg.open_iterations)
    if cfg.close_iterations:
        mask = ndimage.binary_closing(mask, iterations=cfg.close_iterations)
    labels, _ = ndimage.label(mask)
    out: list[Candidate] = []
    for idx, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        region = labels[sl] == idx
        area = int(region.sum())
        if area < cfg.min_area_px:
            continue
        out.append(
            Candidate(
                x0=sl[1].start, y0=sl[0].start, x1=sl[1].stop, y1=sl[0].stop, area_px=area,
                mean_abs_dndvi=float(dndvi[sl][region].mean()),
                mean_ssim_delta=float(ssim_delta[sl][region].mean()),
            )
        )  # fmt: skip
    return sorted(out, key=lambda c: -c.area_px)


def crop(scene: Scene, c: Candidate, pad: int = 8) -> npt.NDArray[np.uint8]:
    h, w = scene.shape
    return scene.rgb()[max(0, c.y0 - pad) : min(h, c.y1 + pad), max(0, c.x0 - pad) : min(w, c.x1 + pad)]
