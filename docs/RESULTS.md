# Results

All numbers are on **synthetic** scenes from `geo_eval_gate.synthetic.make_pair` (128x128, seeds 1000-1099, 2 buildings + 1 cloud + a global seasonal vegetation decline per pair). They measure the deterministic screen only. No VLM has been evaluated and no real imagery has been used.

Reproduce: `python scripts/benchmark.py 100`

| Config | Building recall | False candidates / scene | Candidates / scene | ms / scene |
|---|---|---|---|---|
| NDVI+SSIM, cloud mask ON | 0.975 | 0.00 | 1.77 | 4.5 |
| NDVI+SSIM, cloud mask OFF | 1.000 | 0.61 | 2.42 | 4.2 |

## Reading it

- The cloud mask removes all 0.61 false candidates per scene, at a cost of 2.5 points of recall. Recall drops because a randomly placed cloud sometimes covers a building in t1, and masked pixels are excluded by design.
- Seasonal decline alone produces zero candidates (tested separately), because SSIM sees no structural change.
- "Candidates / scene" is below the 2 injected buildings because overlapping buildings merge into one box.
- N=100 pairs, 200 buildings: one missed building is 0.5 points. Differences under about 1.5 points are noise.

## Not measured

VLM taxonomy accuracy, confidence calibration (ECE), gate precision on real patches, real-imagery false-positive rate, sun-angle and registration-error robustness.

## Verified

- 21 tests passed when this page was written (the suite is now 54 tests; see the README). The cloud halo bug and a synthetic-generator ordering bug were found and fixed while writing them. `mypy --strict` and `ruff` clean.
