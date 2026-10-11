"""Post-hoc, fair calibration comparison for the Jev extension (docs/PROTOCOL_JEV.md, Deviation 1).

`results/real/jev_test_*.json` contains an `ece_stated_confidence` for the Gemma gate that treats Gemma's
confidence-in-its-own-label as if it were a probability of real change. That is not comparable to Jev's
probability of real change (a candidate Gemma calls seasonal with 0.95 implies P(real) = 0.05, not 0.95).
This script converts Gemma's stated confidence into an implied P(real) and recomputes ECE and Brier for a
fair comparison. It changes no stored result. Run after the test stage:

    python scripts/real_jev_posthoc.py
"""

from __future__ import annotations

import itertools
import json
from pathlib import Path
from typing import Any

import numpy as np

from geo_eval_gate.scoring import expected_calibration_error

OUT = Path("results/real")
ACTIONABLE = {"EARTHWORKS", "NEW_STRUCTURE", "ROAD_EXPANSION"}
EDGES = [0.0, 0.1, 0.2, 0.35, 0.5, 0.65, 0.8, 1.01]


def brier(p: np.ndarray, y: np.ndarray) -> float:
    return float(np.mean((p - y.astype(float)) ** 2))


def main() -> None:
    result: dict[str, Any] = {}
    for variant in ("design", "rgb"):
        rows = [json.loads(line) for line in (OUT / "gate" / f"test_{variant}_gemma4_12b.jsonl").read_text().splitlines()]
        y = np.array([r["positive"] for r in rows])
        conf = np.array([r["confidence"] for r in rows])
        actionable = np.array([r["change_class"] in ACTIONABLE for r in rows])
        implied = np.where(actionable, conf, 1.0 - conf)  # confidence in own label -> implied P(real change)
        jev = json.loads((OUT / f"jev_test_{variant}.json").read_text())
        pb = np.array([json.loads(x)["p_yes"] for x in (OUT / "jev" / f"test_{variant}_B.jsonl").read_text().splitlines()])
        bins = []
        for lo, hi in itertools.pairwise(EDGES):
            m, g = (pb >= lo) & (pb < hi), (implied >= lo) & (implied < hi)
            bins.append({
                "bin": [lo, min(hi, 1.0)],
                "jev_n": int(m.sum()), "jev_mean_p": float(pb[m].mean()) if m.any() else None,
                "jev_actual": float(y[m].mean()) if m.any() else None,
                "gemma_n": int(g.sum()), "gemma_mean_p": float(implied[g].mean()) if g.any() else None,
                "gemma_actual": float(y[g].mean()) if g.any() else None,
            })  # fmt: skip
        result[variant] = {
            "gemma_implied_ece": expected_calibration_error(implied, y), "gemma_implied_brier": brier(implied, y),
            "jev_armB_ece": jev["arm_B"]["ece"], "jev_armB_brier": jev["arm_B"]["brier"],
            "stacked_ece": jev["stacked_regression"]["ece"], "stacked_brier": jev["stacked_regression"]["brier"],
            "not_comparable_ece_stated_confidence": jev["gemma_gate"]["ece_stated_confidence"],
            "reliability": bins,
        }  # fmt: skip
        r = result[variant]
        print(f"{variant}: Gemma implied P(real) ECE {r['gemma_implied_ece']:.3f} Brier {r['gemma_implied_brier']:.3f} | "
              f"Jev arm B ECE {r['jev_armB_ece']:.3f} Brier {r['jev_armB_brier']:.3f} | "
              f"stacked ECE {r['stacked_ece']:.3f} Brier {r['stacked_brier']:.3f}")  # fmt: skip
    (OUT / "jev_posthoc.json").write_text(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
