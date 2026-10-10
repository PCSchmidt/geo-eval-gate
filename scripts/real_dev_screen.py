"""Development stage of the real-data screen evaluation. Uses the 14 TRAINING pairs only.

Grid-searches each screen variant (see docs/PROTOCOL.md) for the best micro-averaged pixel F1 and
writes results/real/dev_screen.json plus results/real/frozen_screen.json. The test split is never
loaded here.

    python scripts/real_dev_screen.py
"""

from __future__ import annotations

import itertools
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np

from geo_eval_gate import ChangeMaps, ScreeningConfig, compute_maps, screen_from_maps
from geo_eval_gate.oscd import OscdPair, load_split
from geo_eval_gate.scoring import pixel_metrics

OUT = Path("results/real")
NDVI_GRID = [0.10, 0.15, 0.20, 0.30]
SSIM_GRID = [0.3, 0.5, 0.7]
RGB_GRID = [0.03, 0.05, 0.08, 0.12]
AREA_GRID = [10, 25, 50]
OFF = math.inf


@dataclass(frozen=True)
class Variant:
    name: str
    grid: list[tuple[float, float]]  # (ndvi-or-rgb threshold, ssim threshold); inf = that detector off
    clouds: bool
    rgb: bool = False


VARIANTS = [
    Variant("ndvi_only", [(t, OFF) for t in NDVI_GRID], True),
    Variant("ssim_only", [(OFF, t) for t in SSIM_GRID], True),
    Variant("ndvi_or_ssim (the design)", list(itertools.product(NDVI_GRID, SSIM_GRID + [OFF])), True),
    Variant("design without cloud mask", list(itertools.product(NDVI_GRID, SSIM_GRID + [OFF])), False),
    Variant("rgb_difference", [(t, OFF) for t in RGB_GRID], True, rgb=True),
]


def maps_for(pair: OscdPair, rgb: bool) -> ChangeMaps:
    m = compute_maps(pair.t0, pair.t1)
    if not rgb:
        return m
    diff = (
        np.abs(pair.t1.red - pair.t0.red) + np.abs(pair.t1.green - pair.t0.green) + np.abs(pair.t1.blue - pair.t0.blue)
    ) / 3.0
    return ChangeMaps(dndvi=np.asarray(diff, dtype=np.float64), ssim_delta=np.zeros_like(diff), clouds=m.clouds)


def evaluate(maps: list[ChangeMaps], pairs: list[OscdPair], cfg: ScreeningConfig) -> dict[str, Any]:
    tp = fp = fn = n_cand = 0
    for m, p in zip(maps, pairs, strict=True):
        res = screen_from_maps(m, cfg)
        px = pixel_metrics(res.mask, p.truth)
        tp, fp, fn, n_cand = tp + px.tp, fp + px.fp, fn + px.fn, n_cand + len(res.candidates)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": prec,
        "recall": rec,
        "f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "candidates_per_pair": n_cand / len(pairs),
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pairs = list(load_split(Path("data/oscd/train.parquet")))  # TRAIN ONLY
    print(f"{len(pairs)} development pairs", flush=True)
    base_maps = [maps_for(p, rgb=False) for p in pairs]
    rgb_maps = [maps_for(p, rgb=True) for p in pairs]

    default = evaluate(base_maps, pairs, ScreeningConfig())
    print("untuned library defaults:", {k: round(v, 3) for k, v in default.items()}, flush=True)

    results: dict[str, Any] = {"untuned_default": default, "variants": {}}
    frozen: dict[str, Any] = {}
    for v in VARIANTS:
        maps = rgb_maps if v.rgb else base_maps
        rows = []
        for (a, b), area in itertools.product(v.grid, AREA_GRID):
            cfg = ScreeningConfig(ndvi_threshold=a, ssim_delta_threshold=b, min_area_px=area, mask_clouds=v.clouds)
            rows.append({"ndvi_or_rgb_threshold": a, "ssim_threshold": b, "min_area_px": area, **evaluate(maps, pairs, cfg)})
        best = max(rows, key=lambda r: r["f1"])
        results["variants"][v.name] = {"best": best, "grid_size": len(rows), "grid": rows}
        frozen[v.name] = {
            "ndvi_or_rgb_threshold": best["ndvi_or_rgb_threshold"],
            "ssim_threshold": best["ssim_threshold"],
            "min_area_px": best["min_area_px"],
            "mask_clouds": v.clouds,
            "rgb": v.rgb,
            "dev_f1": best["f1"],
        }
        print(
            f"{v.name:<28} best F1 {best['f1']:.3f}  P {best['precision']:.3f} R {best['recall']:.3f}  "
            f"{best['candidates_per_pair']:.0f} cand/pair  "
            f"(t={best['ndvi_or_rgb_threshold']}, ssim={best['ssim_threshold']}, area={best['min_area_px']})",
            flush=True,
        )
    # JSON has no infinity: encode "off" explicitly
    def clean(o: Any) -> Any:
        if isinstance(o, float) and math.isinf(o):
            return "off"
        if isinstance(o, dict):
            return {k: clean(x) for k, x in o.items()}
        if isinstance(o, list):
            return [clean(x) for x in o]
        return o

    (OUT / "dev_screen.json").write_text(json.dumps(clean(results), indent=1))
    (OUT / "frozen_screen.json").write_text(json.dumps(clean(frozen), indent=1))
    _ = asdict


if __name__ == "__main__":
    main()
