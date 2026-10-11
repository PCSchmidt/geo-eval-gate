"""Post-hoc uncertainty on the frozen test results: bootstrap over PAIRS (and paired differences).

Run after the test stage; it changes no result. Candidates within one scene pair are correlated, so
resampling the 10 test pairs gives honest, wider intervals than resampling candidates. It was added after
the test results were seen (docs/PROTOCOL.md, Deviations).

    python scripts/real_posthoc.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import real_gate as rg

from geo_eval_gate.candidate_set import cap_records
from geo_eval_gate.scoring import auroc, gate_score

REPS = 2000


def pair_bootstrap(pairs: np.ndarray, stat: Any, seed: int = 0) -> tuple[float, float, float]:
    """(estimate, lo, hi) of stat(mask_of_candidates) over resamples of the distinct pairs."""
    rng = np.random.default_rng(seed)
    ids = np.unique(pairs)
    est = float(stat(np.ones(len(pairs), dtype=bool)))
    vals = []
    for _ in range(REPS):
        draw = rng.choice(ids, len(ids), replace=True)
        idx = np.concatenate([np.flatnonzero(pairs == d) for d in draw])
        vals.append(stat_on(stat, idx, len(pairs)))
    v = np.array([x for x in vals if not np.isnan(x)])
    return est, float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))


def stat_on(stat: Any, idx: np.ndarray, n: int) -> float:
    """Evaluate a statistic on a multiset of candidate indices (a candidate may repeat)."""
    return float(stat(idx))


def main() -> None:
    frozen = json.loads((rg.OUT / "frozen_gate.json").read_text())
    out: dict[str, Any] = {}
    for variant in ("design", "rgb"):
        records, _, _ = rg.split_candidates("test", variant)
        sample = cap_records(records, rg.CAP, seed=0)
        pairs = np.array([r.pair for r in sample])
        for model in ("gemma4:12b", "qwen2.5vl:7b"):
            rows = [
                json.loads(line)
                for line in (rg.GATE_DIR / f"test_{variant}_{model.replace(':', '_')}.jsonl").read_text().splitlines()
            ]
            pos = np.array([r["positive"] for r in rows])
            floor = float(frozen[variant][model]["floor"])
            acc = np.array([rg.accepted(r, floor) for r in rows])
            vlm = np.array([rg.vlm_score(r) for r in rows])
            stats = rg.stats_prob(frozen[variant]["stats_classifier"], sample)

            def gate_f1(idx: np.ndarray, acc: Any = acc, pos: Any = pos) -> float:
                return gate_score(acc[idx].tolist(), pos[idx].tolist()).f1

            def screen_f1(idx: np.ndarray, pos: Any = pos) -> float:
                p = float(pos[idx].mean())
                return 2 * p / (1 + p) if p else 0.0

            def f1_diff(idx: np.ndarray, gf: Any = gate_f1, sf: Any = screen_f1) -> float:
                return float(gf(idx) - sf(idx))

            def auc_diff(idx: np.ndarray, vlm: Any = vlm, stats: Any = stats, pos: Any = pos) -> float:
                return auroc(vlm[idx], pos[idx]) - auroc(stats[idx], pos[idx])

            def prec(idx: np.ndarray, acc: Any = acc, pos: Any = pos) -> float:
                return gate_score(acc[idx].tolist(), pos[idx].tolist()).precision

            def lift(idx: np.ndarray, pr: Any = prec, pos: Any = pos) -> float:
                return float(pr(idx) - pos[idx].mean())

            key = f"{variant}|{model}"
            out[key] = {
                "gate_f1": pair_bootstrap(pairs, gate_f1),
                "gate_minus_screen_alone_f1": pair_bootstrap(pairs, f1_diff),
                "gate_precision_minus_screen_precision": pair_bootstrap(pairs, lift),
                "vlm_minus_stats_auroc": pair_bootstrap(pairs, auc_diff),
            }
            print(f"\n{key}  (pair-level bootstrap, {REPS} resamples of the {len(np.unique(pairs))} test pairs)")
            for k, (e, lo, hi) in out[key].items():
                print(f"   {k:<42} {e:+.3f}  95% [{lo:+.3f}, {hi:+.3f}]")
    (rg.OUT / "posthoc_test.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
