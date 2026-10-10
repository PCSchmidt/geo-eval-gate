"""Loader for the multispectral Hugging Face version of OSCD (Onera Satellite Change Detection).

The parquet stores each image as nested lists with its true shape (13 bands, H, W, uint16) and the
mask as PNG bytes. Band order is the Sentinel-2 order B01, B02, B03, B04, B05, B06, B07, B08, B8A,
B09, B10, B11, B12, so blue = 1, green = 2, red = 3 and near-infrared (B08) = 7. Reflectance is
digital number / 10000, clipped to [0, 1].

Data are NOT redistributed with this repository (the dataset licence is listed as unknown); fetch
them with scripts/fetch_oscd.sh.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt
import pyarrow as pa
import pyarrow.parquet as pq
from PIL import Image

from .scene import Scene

BLUE, GREEN, RED, NIR = 1, 2, 3, 7
SCALE = 10_000.0


@dataclass(frozen=True)
class OscdPair:
    index: int
    t0: Scene
    t1: Scene
    truth: npt.NDArray[np.bool_]  # True where the human annotators marked urban change


def _to_cube(column: pa.ChunkedArray, row: int) -> npt.NDArray[np.uint16]:
    """One row of a list<list<list<uint16>>> column as a (bands, H, W) array."""
    chunk = column.chunk(0).slice(row, 1)
    bands = chunk.flatten()  # list<list<uint16>>, one entry per band
    lines = bands.flatten()  # list<uint16>, one entry per image line, all bands
    values = lines.flatten().to_numpy(zero_copy_only=False)
    n_bands = len(bands)
    h = len(lines) // n_bands
    w = len(values) // len(lines)
    return np.asarray(values, dtype=np.uint16).reshape(n_bands, h, w)


def _scene(cube: npt.NDArray[np.uint16]) -> Scene:
    def band(i: int) -> npt.NDArray[np.float64]:
        return np.asarray(np.clip(cube[i].astype(np.float64) / SCALE, 0.0, 1.0), dtype=np.float64)

    return Scene(red=band(RED), green=band(GREEN), blue=band(BLUE), nir=band(NIR))


def load_split(path: Path) -> Iterator[OscdPair]:
    """Yield the pairs of one split, one at a time (each pair is about 20 MB as cubes)."""
    table = pq.read_table(path)
    for i in range(table.num_rows):
        c0, c1 = _to_cube(table["image1"], i), _to_cube(table["image2"], i)
        mask_png = table["mask"].chunk(0)[i].as_py()["bytes"]
        mask = np.asarray(Image.open(io.BytesIO(mask_png)))
        if mask.ndim == 3:
            mask = mask[..., 0]
        truth = np.asarray(mask > 0, dtype=np.bool_)
        if c0.shape[1:] != c1.shape[1:] or c0.shape[1:] != truth.shape:
            raise ValueError(f"pair {i}: shapes differ {c0.shape} {c1.shape} {truth.shape}")
        yield OscdPair(i, _scene(c0), _scene(c1), truth)
