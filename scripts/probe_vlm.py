"""Sanity probe of the VLM prompt on a few DEVELOPMENT candidates (never the test split).

Checks that each model returns schema-valid JSON, how long a call takes, and saves a few before/after
images to results/real/probe/ so a human can see what the model was shown.

    python scripts/probe_vlm.py gemma4:12b qwen2.5vl:7b
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

from geo_eval_gate import ChangeVerificationResult, ScreeningConfig, compute_maps, screen_from_maps
from geo_eval_gate.candidate_set import build_records, cap_records, context_crops, stretch_pair
from geo_eval_gate.oscd import load_split
from geo_eval_gate.vlm_ollama import OllamaVLM, side_by_side

OUT = Path("results/real/probe")


def main() -> None:
    models = sys.argv[1:] or ["gemma4:12b"]
    OUT.mkdir(parents=True, exist_ok=True)
    frozen = json.loads(Path("results/real/frozen_screen.json").read_text())["ndvi_or_ssim (the design)"]
    cfg = ScreeningConfig(
        ndvi_threshold=float("inf") if frozen["ndvi_or_rgb_threshold"] == "off" else frozen["ndvi_or_rgb_threshold"],
        ssim_delta_threshold=float("inf") if frozen["ssim_threshold"] == "off" else frozen["ssim_threshold"],
        min_area_px=frozen["min_area_px"],
        mask_clouds=frozen["mask_clouds"],
    )
    pairs = list(load_split(Path("data/oscd/train.parquet")))[:3]  # DEVELOPMENT pairs only
    recs = []
    images = {}
    for p in pairs:
        res = screen_from_maps(compute_maps(p.t0, p.t1), cfg)
        images[p.index] = stretch_pair(p.t0, p.t1)
        recs += build_records(p.index, res, p.truth)
    pos = [r for r in recs if r.positive]
    neg = [r for r in recs if not r.positive]
    print(f"{len(recs)} candidates in 3 dev pairs: {len(pos)} positive, {len(neg)} negative", flush=True)
    sample = cap_records(pos, 4, seed=0) + cap_records(neg, 4, seed=0)
    for i, r in enumerate(sample):
        a, b = context_crops(*images[r.pair], r.candidate)
        (OUT / f"{i}_{'pos' if r.positive else 'neg'}.png").write_bytes(side_by_side(a, b))

    for model in models:
        vlm = OllamaVLM(model, think=False)
        ok = 0
        print(f"\n== {model}", flush=True)
        for i, r in enumerate(sample):
            a, b = context_crops(*images[r.pair], r.candidate)
            t = time.perf_counter()
            raw = vlm.classify(a, b)
            dt = time.perf_counter() - t
            try:
                verdict = ChangeVerificationResult.model_validate_json(raw)
                ok += 1
                out = f"{verdict.change_class.value:<20} conf {verdict.confidence:.2f}"
            except Exception as exc:  # noqa: BLE001 - the probe reports any parse failure
                out = f"INVALID {str(exc).splitlines()[0][:40]} | {raw[:60]!r}"
            print(f"  {i} truth={'POS' if r.positive else 'neg'} area={r.candidate.area_px:<4} {dt:5.1f}s  {out}", flush=True)
        print(f"  valid JSON: {ok}/{len(sample)}; mean latency {np.mean(vlm.latencies_s):.1f}s")
    _ = Image


if __name__ == "__main__":
    main()
