"""GeoTIFF loading (extra: `geo`). Verifies co-registration before anything is compared."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .scene import Scene


def load_scene(path: Path, bands: tuple[int, int, int, int] = (1, 2, 3, 4), scale: float = 10000.0) -> tuple[Scene, Any, Any]:
    """Read (red, green, blue, nir) bands as reflectance; returns (scene, crs, transform)."""
    import rasterio

    with rasterio.open(path) as src:
        arrays = [src.read(b).astype(np.float64) / scale for b in bands]
        return Scene(*(np.clip(a, 0.0, 1.0) for a in arrays)), src.crs, src.transform


def load_pair(t0: Path, t1: Path) -> tuple[Scene, Scene]:
    s0, crs0, tf0 = load_scene(t0)
    s1, crs1, tf1 = load_scene(t1)
    if crs0 != crs1 or tf0 != tf1 or s0.shape != s1.shape:
        raise ValueError("GeoTIFFs are not co-registered (CRS, transform or shape differ)")
    return s0, s1
