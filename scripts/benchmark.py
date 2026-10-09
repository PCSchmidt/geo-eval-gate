"""Synthetic screening benchmark: recall of injected buildings and false candidates per scene.

Synthetic data only. This measures the deterministic screen, not any VLM.
Usage: python scripts/benchmark.py [n_seeds]
"""

from __future__ import annotations

import sys
import time

from geo_eval_gate import ScreeningConfig, screen
from geo_eval_gate.synthetic import Box, make_pair


def hit(c: tuple[int, int, int, int], b: Box) -> bool:
    return c[0] < b.x1 and b.x0 < c[2] and c[1] < b.y1 and b.y0 < c[3]


def run(n: int, cfg: ScreeningConfig) -> tuple[float, float, float, float]:
    found = total = false_cand = cands_total = 0
    start = time.perf_counter()
    for seed in range(1000, 1000 + n):
        p = make_pair(seed)
        boxes = [(c.x0, c.y0, c.x1, c.y1) for c in screen(p.t0, p.t1, cfg)]
        total += len(p.true_changes)
        found += sum(any(hit(b, t) for b in boxes) for t in p.true_changes)
        cands_total += len(boxes)
        false_cand += sum(not any(hit(b, t) for t in p.true_changes) for b in boxes)
    elapsed = (time.perf_counter() - start) / n
    return found / total, false_cand / n, cands_total / n, elapsed * 1000


def main() -> None:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100
    print(f"{n} synthetic 128x128 pairs, 2 buildings + 1 cloud + seasonal decline each\n")
    print("| Config | Building recall | False candidates / scene | Candidates / scene | ms / scene |")
    print("|---|---|---|---|---|")
    for name, cfg in [
        ("NDVI+SSIM, cloud mask ON", ScreeningConfig()),
        ("NDVI+SSIM, cloud mask OFF", ScreeningConfig(mask_clouds=False)),
    ]:
        r, f, c, ms = run(n, cfg)
        print(f"| {name} | {r:.3f} | {f:.2f} | {c:.2f} | {ms:.1f} |")


if __name__ == "__main__":
    main()
