"""Co-registered surface-reflectance scenes (values in [0, 1])."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

Array = npt.NDArray[np.float64]


@dataclass(frozen=True)
class Scene:
    red: Array
    green: Array
    blue: Array
    nir: Array

    def __post_init__(self) -> None:
        shapes = {self.red.shape, self.green.shape, self.blue.shape, self.nir.shape}
        if len(shapes) != 1 or len(self.red.shape) != 2:
            raise ValueError(f"bands must be 2-D and co-registered, got shapes {shapes}")

    @property
    def shape(self) -> tuple[int, int]:
        return self.red.shape

    def rgb(self) -> npt.NDArray[np.uint8]:
        stack = np.stack([self.red, self.green, self.blue], axis=-1)
        return (np.clip(stack, 0.0, 1.0) * 255).astype(np.uint8)


def require_coregistered(t0: Scene, t1: Scene) -> None:
    if t0.shape != t1.shape:
        raise ValueError(f"scenes are not co-registered: {t0.shape} vs {t1.shape}")
