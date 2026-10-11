"""Calibrated-judge extension with TypeSafe Jev (see docs/PROTOCOL_JEV.md).

    python scripts/real_jev.py probe            # 5 development candidates: format check only
    python scripts/real_jev.py dev              # development stage, freezes thresholds and the stacked baseline
    python scripts/real_jev.py test             # one-shot test stage; refuses without a frozen dev entry

Jev sees TEXT only (candidate statistics, and in arm B the Gemma reply already cached from the main runs).
Its replies are cached per candidate in results/real/jev/*.jsonl so every stage is resumable.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_predict

sys.path.insert(0, str(Path(__file__).parent))
import real_gate as rg
from real_posthoc import pair_bootstrap

from geo_eval_gate.candidate_set import CandidateRecord, cap_records
from geo_eval_gate.jev import JevJudge
from geo_eval_gate.scoring import auroc, expected_calibration_error, gate_score

JEV_DIR = rg.OUT / "jev"
FROZEN = rg.OUT / "frozen_jev.json"
GEMMA = "gemma4:12b"
BUDGET_USD = 1.0
TAUS = [round(0.10 + 0.05 * i, 2) for i in range(17)]  # 0.10 .. 0.90
CLASSES = ["EARTHWORKS", "NEW_STRUCTURE", "ROAD_EXPANSION", "SEASONAL_DEFOLIATION", "CLOUD_ARTIFACT"]
SCREEN_TEXT = {
    "design": "a change detector comparing vegetation index (NDVI) and structural similarity between the dates",
    "rgb": "a change detector thresholding the plain colour difference between the dates",
}
# Frozen before the first call (docs/PROTOCOL_JEV.md): do not edit after any development result is seen.
INSTRUCTION = (
    "Is this region a genuine human-made new building or road built between the two dates, rather than "
    "seasonal vegetation change, cloud, shadow or sensor noise?"
)


def render_state(rec: CandidateRecord, variant: str, vlm: dict[str, Any] | None) -> str:
    c = rec.candidate
    lines = [
        "A region was flagged between two satellite images of the same place (Sentinel-2, 10 metres per pixel).",
        f"Detector: {SCREEN_TEXT[variant]}.",
        f"Size: {c.area_px} pixels (bounding box {c.x1 - c.x0} by {c.y1 - c.y0} pixels).",
        f"Mean absolute NDVI change in the region: {c.mean_abs_dndvi:.3f}.",
        f"Mean structural (SSIM) change in the region: {c.mean_ssim_delta:.3f}.",
    ]
    if vlm is not None:
        if vlm["schema_ok"]:
            reply = json.loads(vlm["raw"])
            lines.append(
                f"An image analyst who looked at the before and after pictures replied: class {vlm['change_class']}, "
                f"stated confidence {vlm['confidence']:.2f}, reason: \"{reply.get('rationale', '')}\""
            )
        else:
            lines.append("An image analyst looked at the pictures but gave no valid reply.")
    return "\n".join(lines)


def load_sample(split: str, variant: str) -> tuple[list[CandidateRecord], list[dict[str, Any]]]:
    """The seeded 400-candidate sample and Gemma's cached reply for each candidate (same order)."""
    records, _, _ = rg.split_candidates(split, variant)
    sample = cap_records(records, rg.CAP, seed=0)
    path = rg.GATE_DIR / f"{split}_{variant}_{GEMMA.replace(':', '_')}.jsonl"
    cache = {(r["pair"], r["index"]): r for r in map(json.loads, path.read_text().splitlines())}
    return sample, [cache[(r.pair, r.index)] for r in sample]


def spent_usd() -> float:
    total = 0
    for f in JEV_DIR.glob("*.jsonl"):
        for line in f.read_text().splitlines():
            total += int(json.loads(line).get("input_tokens", 0))
    return total * 0.042 / 1_000_000


def run_arm(split: str, variant: str, arm: str, sample: list[CandidateRecord], vlm: list[dict[str, Any]], limit: int | None = None) -> list[dict[str, Any]]:
    JEV_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = JEV_DIR / f"{split}_{variant}_{arm}.jsonl"
    done: dict[tuple[int, int], dict[str, Any]] = {}
    if cache_path.exists():
        for cached in map(json.loads, cache_path.read_text().splitlines()):
            done[(cached["pair"], cached["index"])] = cached
    judge = JevJudge(INSTRUCTION)
    todo = list(zip(sample, vlm, strict=True))[:limit]
    with cache_path.open("a") as fh:
        for k, (rec, v) in enumerate(todo):
            if (rec.pair, rec.index) in done:
                continue
            if spent_usd() > BUDGET_USD:
                raise SystemExit(f"stopping: estimated Jev spend exceeded ${BUDGET_USD:.2f}")
            ans = judge.ask(render_state(rec, variant, v if arm == "B" else None))
            row = {"pair": rec.pair, "index": rec.index, "positive": rec.positive, "p_yes": ans.p_yes,
                   "input_tokens": ans.input_tokens, "latency_s": ans.latency_s}  # fmt: skip
            fh.write(json.dumps(row) + "\n")
            fh.flush()
            done[(rec.pair, rec.index)] = row
            if k % 100 == 0:
                print(f"  {split}/{variant}/arm {arm}: {k}/{len(todo)}  spent ${spent_usd():.4f}", flush=True)
    return [done[(r.pair, r.index)] for r, _ in todo]


def stack_features(sample: list[CandidateRecord], vlm: list[dict[str, Any]]) -> np.ndarray:
    base = rg.features(sample)
    extra = []
    for v in vlm:
        ok = bool(v["schema_ok"])
        extra.append(
            [float(rg.accepted(v, 0.0)), float(v["confidence"]) if ok else 0.0]
            + [float(ok and v["change_class"] == c) for c in CLASSES]
        )
    return np.hstack([base, np.array(extra)])


def best_tau(p: np.ndarray, pos: np.ndarray) -> tuple[float, float]:
    best = (-1.0, 0.5)
    for t in TAUS:
        f1 = gate_score((p >= t).tolist(), pos.tolist()).f1
        if f1 > best[0] + 1e-12 or (abs(f1 - best[0]) <= 1e-12 and abs(t - 0.5) < abs(best[1] - 0.5)):
            best = (f1, t)
    return best[1], best[0]


def brier(p: np.ndarray, pos: np.ndarray) -> float:
    return float(np.mean((p - pos.astype(float)) ** 2))


def probe() -> None:
    sample, vlm = load_sample("train", "design")
    judge = JevJudge(INSTRUCTION)
    print(f"format check on 5 development candidates (instruction frozen: {INSTRUCTION!r})")
    for i in (0, 1, 2, 3, 4):
        for arm in ("A", "B"):
            a = judge.ask(render_state(sample[i], "design", vlm[i] if arm == "B" else None))
            print(f"  cand {i} arm {arm}: truth={'REAL' if sample[i].positive else 'not'}  p_yes={a.p_yes:.3f}  tokens={a.input_tokens}  {a.latency_s * 1000:.0f} ms")
    print("example state (arm B):\n" + render_state(sample[0], "design", vlm[0]))
    print(f"spent so far this probe: ${judge.cost_usd:.6f}")


def dev() -> None:
    frozen: dict[str, Any] = json.loads(FROZEN.read_text()) if FROZEN.exists() else {}
    for variant in ("design", "rgb"):
        sample, vlm = load_sample("train", variant)
        pos = np.array([r.positive for r in sample])
        entry: dict[str, Any] = {"n": len(sample), "positive_rate": float(pos.mean())}
        for arm in ("A", "B"):
            rows = run_arm("train", variant, arm, sample, vlm)
            p = np.array([r["p_yes"] for r in rows])
            tau, f1 = best_tau(p, pos)
            entry[f"arm_{arm}"] = {"tau": tau, "dev_f1": f1, "dev_auroc": auroc(p, pos),
                                   "dev_ece": expected_calibration_error(p, pos), "dev_brier": brier(p, pos)}  # fmt: skip
            print(f"dev {variant} arm {arm}: tau {tau} F1 {f1:.3f} AUROC {auroc(p, pos):.3f} ECE {entry[f'arm_{arm}']['dev_ece']:.3f}", flush=True)
        x = stack_features(sample, vlm)
        mu, sd = x.mean(0), x.std(0) + 1e-9
        z = (x - mu) / sd
        cv = cross_val_predict(
            LogisticRegression(random_state=0, max_iter=2000), z, pos,
            cv=StratifiedKFold(5, shuffle=True, random_state=0), method="predict_proba",
        )[:, 1]  # fmt: skip
        tau_s, f1_s = best_tau(cv, pos)  # threshold from cross-validated dev predictions, not in-sample
        clf = LogisticRegression(random_state=0, max_iter=2000).fit(z, pos)
        entry["stacked"] = {"mu": mu.tolist(), "sd": sd.tolist(), "coef": clf.coef_[0].tolist(),
                            "intercept": float(clf.intercept_[0]), "tau": tau_s, "dev_cv_f1": f1_s,
                            "dev_cv_auroc": auroc(cv, pos)}  # fmt: skip
        print(f"dev {variant} stacked regression (5-fold CV): tau {tau_s} F1 {f1_s:.3f} AUROC {auroc(cv, pos):.3f}", flush=True)
        frozen[variant] = entry
    FROZEN.write_text(json.dumps(frozen, indent=1))
    print(f"frozen. estimated Jev spend so far: ${spent_usd():.4f}")


def stacked_prob(model: dict[str, Any], x: np.ndarray) -> np.ndarray:
    z = (x - np.array(model["mu"])) / np.array(model["sd"])
    return np.asarray(1.0 / (1.0 + np.exp(-(z @ np.array(model["coef"]) + model["intercept"]))), dtype=np.float64)


def test() -> None:
    if not FROZEN.exists():
        raise SystemExit("refusing to run the test split: nothing is frozen yet")
    frozen = json.loads(FROZEN.read_text())
    base_frozen = json.loads((rg.OUT / "frozen_gate.json").read_text())
    for variant in ("design", "rgb"):
        score_variant(variant, frozen, base_frozen)
    _ = math


def score_variant(variant: str, frozen: dict[str, Any], base_frozen: dict[str, Any]) -> None:
    out_path = rg.OUT / f"jev_test_{variant}.json"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists: the test split is scored once. Delete it deliberately to rerun.")
    fz = frozen[variant]
    sample, vlm = load_sample("test", variant)
    pairs = np.array([r.pair for r in sample])
    pos = np.array([r.positive for r in sample])
    pa = np.array([r["p_yes"] for r in run_arm("test", variant, "A", sample, vlm)])
    rows_b = run_arm("test", variant, "B", sample, vlm)
    pb = np.array([r["p_yes"] for r in rows_b])
    stack = stacked_prob(fz["stacked"], stack_features(sample, vlm))
    stats = rg.stats_prob(base_frozen[variant]["stats_classifier"], sample)
    gemma_score = np.array([rg.vlm_score(v) for v in vlm])
    gemma_acc = np.array([rg.accepted(v, float(base_frozen[variant][GEMMA]["floor"])) for v in vlm])
    gemma_conf = np.array([float(v["confidence"]) if v["schema_ok"] else 0.0 for v in vlm])
    all_rows = [json.loads(x) for arm in ("A", "B") for x in (JEV_DIR / f"test_{variant}_{arm}.jsonl").read_text().splitlines()]

    def at(prob: np.ndarray, tau: float) -> dict[str, float]:
        acc = prob >= tau
        g = gate_score(acc.tolist(), pos.tolist())
        return {"tau": tau, "accepted": g.accepted, "precision": g.precision, "recall": g.recall, "f1": g.f1,
                "precision_lift": g.precision - float(pos.mean())}  # fmt: skip

    def diff(f: Any) -> tuple[float, float, float]:
        return pair_bootstrap(pairs, f)

    res: dict[str, Any] = {
        "variant": variant, "n": len(sample), "screen_alone_precision": float(pos.mean()),
        "arm_A": {**at(pa, fz["arm_A"]["tau"]), "auroc": auroc(pa, pos), "ece": expected_calibration_error(pa, pos), "brier": brier(pa, pos)},
        "arm_B": {**at(pb, fz["arm_B"]["tau"]), "auroc": auroc(pb, pos), "ece": expected_calibration_error(pb, pos), "brier": brier(pb, pos)},
        "stacked_regression": {**at(stack, fz["stacked"]["tau"]), "auroc": auroc(stack, pos), "ece": expected_calibration_error(stack, pos), "brier": brier(stack, pos)},
        "stats_regression": {"auroc": auroc(stats, pos)},
        "gemma_gate": {"auroc": auroc(gemma_score, pos), "precision": gate_score(gemma_acc.tolist(), pos.tolist()).precision,
                       "recall": gate_score(gemma_acc.tolist(), pos.tolist()).recall,
                       "ece_stated_confidence": expected_calibration_error(gemma_conf, pos)},
        "C2_armB_minus_stacked_auroc_pair95": diff(lambda i: auroc(pb[i], pos[i]) - auroc(stack[i], pos[i])),
        "C3_armA_minus_stats_auroc_pair95": diff(lambda i: auroc(pa[i], pos[i]) - auroc(stats[i], pos[i])),
        "armB_minus_gemma_auroc_pair95": diff(lambda i: auroc(pb[i], pos[i]) - auroc(gemma_score[i], pos[i])),
        "armB_precision_lift_pair95": diff(lambda i: gate_score((pb[i] >= fz["arm_B"]["tau"]).tolist(), pos[i].tolist()).precision - float(pos[i].mean())),
        "cost_usd": sum(r["input_tokens"] for r in all_rows) * 0.042 / 1_000_000,
        "mean_latency_s": float(np.mean([r["latency_s"] for r in all_rows])),
        "calls": len(all_rows),
    }
    out_path.write_text(json.dumps(res, indent=1, default=float))
    print(f"\n=== TEST {variant}: {len(sample)} candidates, screen-alone precision {res['screen_alone_precision']:.3f}")
    for k in ("arm_A", "arm_B", "stacked_regression"):
        r = res[k]
        print(f"  {k:<19} tau {r['tau']:.2f}  P {r['precision']:.3f} R {r['recall']:.3f} F1 {r['f1']:.3f} | AUROC {r['auroc']:.3f} ECE {r['ece']:.3f} Brier {r['brier']:.3f}")
    print(f"  gemma gate (frozen) P {res['gemma_gate']['precision']:.3f} R {res['gemma_gate']['recall']:.3f} AUROC {res['gemma_gate']['auroc']:.3f}; stated-confidence ECE {res['gemma_gate']['ece_stated_confidence']:.3f}; stats regression AUROC {res['stats_regression']['auroc']:.3f}")
    for k in ("C2_armB_minus_stacked_auroc_pair95", "C3_armA_minus_stats_auroc_pair95", "armB_minus_gemma_auroc_pair95", "armB_precision_lift_pair95"):
        e, lo, hi = res[k]
        print(f"  {k:<38} {e:+.3f}  95% [{lo:+.3f}, {hi:+.3f}]")
    print(f"  cost ${res['cost_usd']:.4f}, {res['calls']} calls, {res['mean_latency_s'] * 1000:.0f} ms mean")


def main() -> None:
    stage = sys.argv[1] if len(sys.argv) > 1 else ""
    {"probe": probe, "dev": dev, "test": test}.get(stage, lambda: sys.exit(__doc__))()


if __name__ == "__main__":
    main()
