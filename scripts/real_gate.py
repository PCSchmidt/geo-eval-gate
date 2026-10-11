"""Real-data evaluator-gate benchmark on OSCD (see docs/PROTOCOL.md).

    python scripts/real_gate.py dev  --model gemma4:12b --variant design   # development pairs only
    python scripts/real_gate.py test --model gemma4:12b --variant design   # refuses without a frozen dev entry

Variants: "design" (NDVI or SSIM, the pre-registered primary) and "rgb" (plain RGB difference, added
after the development screen results; see PROTOCOL.md, Deviations).
VLM replies are cached per candidate in results/real/gate/*.jsonl so a run can be resumed.
"""

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression

from geo_eval_gate import (
    ChangeMaps,
    ChangeVerificationResult,
    ScreeningConfig,
    compute_maps,
    screen_from_maps,
)
from geo_eval_gate.candidate_set import (
    CandidateRecord,
    build_records,
    cap_records,
    context_crops,
    stretch_pair,
)
from geo_eval_gate.gate import ACTIONABLE
from geo_eval_gate.oscd import OscdPair, load_split
from geo_eval_gate.scoring import (
    auroc,
    bootstrap_ci,
    expected_calibration_error,
    gate_score,
    object_recall,
    pixel_metrics,
)
from geo_eval_gate.vlm_ollama import OllamaVLM

OUT = Path("results/real")
GATE_DIR = OUT / "gate"
VARIANT_KEY = {"design": "ndvi_or_ssim (the design)", "rgb": "rgb_difference"}
CAP = 400
FLOORS = [0.0, 0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 1.0]


def load_screen(variant: str) -> tuple[ScreeningConfig, bool]:
    f = json.loads((OUT / "frozen_screen.json").read_text())[VARIANT_KEY[variant]]

    def th(v: Any) -> float:
        return math.inf if v == "off" else float(v)

    cfg = ScreeningConfig(
        ndvi_threshold=th(f["ndvi_or_rgb_threshold"]),
        ssim_delta_threshold=th(f["ssim_threshold"]),
        min_area_px=int(f["min_area_px"]),
        mask_clouds=bool(f["mask_clouds"]),
    )
    return cfg, bool(f["rgb"])


def maps_for(pair: OscdPair, rgb: bool) -> ChangeMaps:
    m = compute_maps(pair.t0, pair.t1)
    if not rgb:
        return m
    d = (
        np.abs(pair.t1.red - pair.t0.red) + np.abs(pair.t1.green - pair.t0.green) + np.abs(pair.t1.blue - pair.t0.blue)
    ) / 3.0
    return ChangeMaps(dndvi=np.asarray(d, dtype=np.float64), ssim_delta=np.zeros_like(d), clouds=m.clouds)


def split_candidates(split: str, variant: str) -> tuple[list[CandidateRecord], dict[int, Any], dict[str, Any]]:
    """All candidates for a split under the frozen screen, plus pair images and full-pair screen metrics."""
    cfg, rgb = load_screen(variant)
    records: list[CandidateRecord] = []
    images: dict[int, Any] = {}
    tp = fp = fn = hit = objs = 0
    n_pairs = 0
    for p in load_split(Path(f"data/oscd/{split}.parquet")):
        res = screen_from_maps(maps_for(p, rgb), cfg)
        images[p.index] = stretch_pair(p.t0, p.t1)
        records += build_records(p.index, res, p.truth)
        px = pixel_metrics(res.mask, p.truth)
        tp, fp, fn = tp + px.tp, fp + px.fp, fn + px.fn
        h, n = object_recall(res.mask, p.truth)
        hit, objs, n_pairs = hit + h, objs + n, n_pairs + 1
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    screen = {
        "pixel_precision": prec,
        "pixel_recall": rec,
        "pixel_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "object_recall": hit / objs if objs else 0.0,
        "objects": objs,
        "candidates": len(records),
        "candidates_per_pair": len(records) / n_pairs,
        "candidate_positive_rate": float(np.mean([r.positive for r in records])),
    }
    return records, images, screen


def gpu_temp_c() -> float:
    import subprocess

    out = subprocess.run(
        ["nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv,noheader,nounits"],
        capture_output=True, text=True, check=False,
    ).stdout.strip()  # fmt: skip
    try:
        return float(out.splitlines()[0])
    except (ValueError, IndexError):
        return 0.0


def wait_for_cool(max_c: float = 84.0, resume_c: float = 72.0, cap_s: float = 1200.0) -> None:
    """Pause while the laptop GPU is hot: throttled clocks make calls slow and Ollama can return 500s."""
    if gpu_temp_c() <= max_c:
        return
    start = time.monotonic()
    print(f"  GPU at {gpu_temp_c():.0f} C, pausing to cool to {resume_c:.0f} C", flush=True)
    while gpu_temp_c() > resume_c and time.monotonic() - start < cap_s:
        time.sleep(20)


def classify_retry(vlm: OllamaVLM, a: Any, b: Any, tries: int = 4) -> str:
    """One VLM call with retries on server errors (kept out of results: a retry is not a verdict)."""
    for attempt in range(1, tries + 1):
        try:
            return vlm.classify(a, b)
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == tries:
                raise
            print(f"  VLM call failed ({exc!r}); retry {attempt}/{tries - 1} after cooling", flush=True)
            time.sleep(30 * attempt)
            wait_for_cool(max_c=75.0)
    raise AssertionError("unreachable")


def run_vlm(
    records: list[CandidateRecord], images: dict[int, Any], model: str, cache: Path
) -> list[dict[str, Any]]:
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    done: dict[tuple[int, int], dict[str, Any]] = {}
    if cache.exists():
        for line in cache.read_text().splitlines():
            cached = json.loads(line)
            done[(cached["pair"], cached["index"])] = cached
    vlm = OllamaVLM(model, think=False)
    start = time.perf_counter()
    with cache.open("a") as fh:
        for k, r in enumerate(records):
            if (r.pair, r.index) in done:
                continue
            rgb0, rgb1 = images[r.pair]
            a, b = context_crops(rgb0, rgb1, r.candidate)
            t = time.perf_counter()
            if k % 10 == 0:
                wait_for_cool()
            raw = classify_retry(vlm, a, b)
            row: dict[str, Any] = {
                "pair": r.pair,
                "index": r.index,
                "positive": r.positive,
                "raw": raw,
                "latency_s": time.perf_counter() - t,
            }
            try:
                v = ChangeVerificationResult.model_validate_json(raw)
                row.update(schema_ok=True, change_class=v.change_class.value, confidence=v.confidence)
            except ValueError:
                row.update(schema_ok=False, change_class=None, confidence=None)
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            done[(r.pair, r.index)] = row
            if k % 50 == 0:
                print(f"  {k}/{len(records)}  {time.perf_counter() - start:.0f}s", flush=True)
    return [done[(r.pair, r.index)] for r in records]


def accepted(row: dict[str, Any], floor: float) -> bool:
    return bool(
        row["schema_ok"]
        and row["change_class"] in {c.value for c in ACTIONABLE}
        and row["confidence"] >= floor
    )


def vlm_score(row: dict[str, Any]) -> float:
    """Ranking score: confidence if the class is actionable, else 0 (also 0 for a schema failure)."""
    return float(row["confidence"]) if accepted(row, 0.0) else 0.0


def features(records: list[CandidateRecord]) -> np.ndarray:
    return np.array(
        [[math.log(r.candidate.area_px), r.candidate.mean_abs_dndvi, r.candidate.mean_ssim_delta] for r in records]
    )


def fit_stats_classifier(records: list[CandidateRecord]) -> dict[str, Any]:
    x, y = features(records), np.array([r.positive for r in records])
    mu, sd = x.mean(0), x.std(0) + 1e-9
    clf = LogisticRegression(random_state=0, max_iter=1000, class_weight=None).fit((x - mu) / sd, y)
    return {"mu": mu.tolist(), "sd": sd.tolist(), "coef": clf.coef_[0].tolist(), "intercept": float(clf.intercept_[0])}


def stats_prob(model: dict[str, Any], records: list[CandidateRecord]) -> np.ndarray:
    z = (features(records) - np.array(model["mu"])) / np.array(model["sd"])
    return np.asarray(1.0 / (1.0 + np.exp(-(z @ np.array(model["coef"]) + model["intercept"]))), dtype=np.float64)


def dev(model: str, variant: str) -> None:
    records, images, screen = split_candidates("train", variant)
    sample = cap_records(records, CAP, seed=0)
    print(f"dev {variant}: {len(records)} candidates, sampling {len(sample)}; screen {screen['pixel_f1']:.3f} F1", flush=True)
    rows = run_vlm(sample, images, model, GATE_DIR / f"train_{variant}_{model.replace(':', '_')}.jsonl")
    pos = [r["positive"] for r in rows]
    sweep = []
    for fl in FLOORS:
        g = gate_score([accepted(r, fl) for r in rows], pos)
        sweep.append({"floor": fl, "accepted": g.accepted, "precision": g.precision, "recall": g.recall, "f1": g.f1})
        print(f"  floor {fl:.2f}: accepted {g.accepted:3d}  P {g.precision:.3f} R {g.recall:.3f} F1 {g.f1:.3f}", flush=True)
    best = max(sweep, key=lambda s: (s["f1"], s["floor"]))
    frozen_path = OUT / "frozen_gate.json"
    frozen = json.loads(frozen_path.read_text()) if frozen_path.exists() else {}
    entry = frozen.setdefault(variant, {})
    entry["stats_classifier"] = fit_stats_classifier(records)  # fitted on ALL development candidates
    entry[model] = {
        "floor": best["floor"],
        "dev_f1": best["f1"],
        "dev_precision": best["precision"],
        "dev_recall": best["recall"],
        "dev_positive_rate": float(np.mean(pos)),
        "dev_schema_valid": float(np.mean([r["schema_ok"] for r in rows])),
        "dev_sweep": sweep,
    }
    frozen_path.write_text(json.dumps(frozen, indent=1))
    print(f"frozen floor {best['floor']} (dev F1 {best['f1']:.3f}); screen-alone dev precision {np.mean(pos):.3f}")


def test(model: str, variant: str) -> None:
    frozen = json.loads((OUT / "frozen_gate.json").read_text()) if (OUT / "frozen_gate.json").exists() else {}
    if variant not in frozen or model not in frozen[variant]:
        raise SystemExit("refusing to run the test split: no frozen development entry for this variant and model")
    floor = float(frozen[variant][model]["floor"])
    out_path = OUT / f"gate_test_{variant}_{model.replace(':', '_')}.json"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists: the test split is run once. Delete it deliberately to rerun.")
    records, images, screen = split_candidates("test", variant)
    sample = cap_records(records, CAP, seed=0)
    print(f"test {variant}: {len(records)} candidates, using {len(sample)}", flush=True)
    rows = run_vlm(sample, images, model, GATE_DIR / f"test_{variant}_{model.replace(':', '_')}.jsonl")
    pos = np.array([r["positive"] for r in rows])
    scores = np.array([vlm_score(r) for r in rows])
    probs = stats_prob(frozen[variant]["stats_classifier"], sample)

    def at(fl: float) -> dict[str, Any]:
        acc = np.array([accepted(r, fl) for r in rows])
        g = gate_score(acc.tolist(), pos.tolist())

        def f1_of(idx: np.ndarray) -> float:
            return gate_score(acc[idx].tolist(), pos[idx].tolist()).f1

        def prec_of(idx: np.ndarray) -> float:
            return gate_score(acc[idx].tolist(), pos[idx].tolist()).precision

        return {
            "floor": fl,
            "accepted": g.accepted,
            "precision": g.precision,
            "recall": g.recall,
            "f1": g.f1,
            "f1_ci95": bootstrap_ci(f1_of, len(rows), seed=0),
            "precision_ci95": bootstrap_ci(prec_of, len(rows), seed=0),
        }

    frozen_floor = at(floor)
    k = frozen_floor["accepted"]
    top = np.argsort(-probs)[:k] if k else np.array([], dtype=int)
    matched = gate_score([i in set(top.tolist()) for i in range(len(rows))], pos.tolist())
    acted = [(r["confidence"], bool(r["positive"])) for r in rows if accepted(r, 0.0)]
    result = {
        "model": model,
        "variant": variant,
        "n_candidates_used": len(rows),
        "screen_full_test_split": screen,
        "screen_alone_precision": float(pos.mean()),
        "gate_at_frozen_floor": frozen_floor,
        "gate_at_default_floor_0.8": at(0.8),
        "schema_valid_rate": float(np.mean([r["schema_ok"] for r in rows])),
        "mean_latency_s": float(np.mean([r["latency_s"] for r in rows])),
        "vlm_auroc": auroc(scores, pos),
        "stats_classifier_auroc": auroc(probs, pos),
        "stats_classifier_at_same_budget": {"accepted": k, "precision": matched.precision, "recall": matched.recall, "f1": matched.f1},
        "ece_confidence_of_actionable_calls": expected_calibration_error(
            np.array([c for c, _ in acted]), np.array([p for _, p in acted])
        ) if acted else None,
        "n_actionable_calls": len(acted),
        "class_counts": {c: sum(1 for r in rows if r["change_class"] == c) for c in sorted({r["change_class"] for r in rows if r["change_class"]})},
    }
    out_path.write_text(json.dumps(result, indent=1, default=float))
    print(json.dumps({k: v for k, v in result.items() if k not in ("screen_full_test_split",)}, indent=1, default=float))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=["dev", "test"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--variant", choices=list(VARIANT_KEY), required=True)
    args = ap.parse_args()
    (dev if args.stage == "dev" else test)(args.model, args.variant)


if __name__ == "__main__":
    main()
