# Real-data results: OSCD (Sentinel-2)

The evaluation plan is in [PROTOCOL.md](PROTOCOL.md) and was committed before any of this was measured; deviations are listed there. Synthetic-scene results are in [RESULTS.md](RESULTS.md).

**Data.** 24 real Sentinel-2 city pairs from OSCD (Onera Satellite Change Detection), 14 for development and 10 for the one-shot test, with human masks of **urban change only** (new buildings and roads). Unlabelled non-urban change counts against precision, so every precision here is pessimistic. The data are not redistributed (licence listed as unknown); `scripts/fetch_oscd.sh` downloads them.

**Models.** `gemma4:12b` (thinking turned off) and `qwen2.5vl:7b`, both local through Ollama, greedy, one fixed prompt, JSON-schema constrained.

## Summary

1. **Gemma's gate reliably raises the precision of the screen's candidates, at a cost in recall.** About +0.24 precision on the NDVI-or-SSIM screen and +0.18 on the RGB-difference screen (pair-level 95% intervals exclude zero), keeping about 70% of the real candidates.
2. **That did not reach statistical significance as an F1 gain or as an advantage over a statistics-only classifier.** With 10 test pairs, those intervals include zero.
3. **Qwen2.5-VL added nothing.** It labels about 97% of candidates as construction, so its gate accepts almost everything.
4. **The VLMs' self-reported confidence is not usable.** Expected calibration error is 0.29-0.47, above the protocol's 0.2 line, and Gemma only ever reports 0.90, 0.95 or 1.00.
5. **The screen, not the gate, is the main limit.** The screens find only about 39% of the labelled change objects, and nothing downstream can recover a change that never became a candidate.
6. **The NDVI-or-SSIM design was not the best screen on development data**, and the plain RGB difference matched it on test.

## The screen (all 10 test pairs)

| Screen | Pixel precision | Pixel recall | Pixel F1 | Objects found (of 668) | Candidates per pair | Candidates that are real change |
| --- | --- | --- | --- | --- | --- | --- |
| NDVI or SSIM (the design) | 0.295 | 0.381 | 0.333 | 39.2% | 74 | 40.5% |
| RGB difference (baseline) | 0.350 | 0.346 | 0.348 | 39.4% | 104 | 33.9% |

Thresholds were chosen on the 14 development pairs. On development data the best F1 per variant was: NDVI only 0.094, SSIM only 0.260, the design 0.227, RGB difference 0.297, and the untuned synthetic-scene defaults 0.176. The cloud mask changed nothing on this data (design 0.227 with and without). Adding the NDVI condition made the design *worse* than SSIM alone on development data (0.227 against 0.260), because NDVI adds vegetation false positives.

The candidates' real-change rate is much higher on the test pairs (34-41%) than on development (22-27%): the test pairs contain more change, so precision should be compared within a split, not across them.

## The gate (400 test candidates sampled per screen, seeded)

All candidate-level, against labels from the human masks (a candidate is real if at least 30% of its pixels are inside the mask). "Screen alone" accepts every candidate. Confidence floors were frozen on development data before the test split was touched.

| Model | Screen | Accepted | Precision | Recall | F1 | Screen-alone precision / F1 | Precision lift, pair-level 95% interval | F1 minus screen-alone F1, pair-level 95% interval |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Gemma 4 12B | design | 179 | 0.665 | 0.704 | 0.684 | 0.422 / 0.594 | **+0.242 [+0.093, +0.330]** | +0.090 [-0.079, +0.198] |
| Gemma 4 12B | RGB | 178 | 0.522 | 0.674 | 0.589 | 0.345 / 0.513 | **+0.177 [+0.049, +0.261]** | +0.076 [-0.086, +0.211] |
| Qwen2.5-VL 7B | design | 393 | 0.425 | 0.988 | 0.594 | 0.422 / 0.594 | +0.002 [-0.006, +0.012] | +0.000 [-0.012, +0.009] |
| Qwen2.5-VL 7B | RGB | 376 | 0.359 | 0.978 | 0.525 | 0.345 / 0.513 | +0.014 [+0.000, +0.034] | +0.012 [-0.006, +0.030] |

Note on F1: "screen alone" has recall 1.0 over candidates by construction, so its F1 is high whenever many candidates are real. Precision lift is the cleaner measure of what the gate adds; the F1 comparison is shown because the protocol asked for it. Intervals resample the 10 test pairs and are wide.

## Does the model add anything over statistics?

A logistic regression on three numbers per candidate (log area, mean NDVI change, mean SSIM change), fitted on all development candidates, sees no pixels.

| Model | Screen | VLM AUROC | Statistics AUROC | Difference, pair-level 95% interval | F1 at the same number accepted: VLM vs statistics |
| --- | --- | --- | --- | --- | --- |
| Gemma 4 12B | design | 0.728 | 0.664 | +0.064 [-0.049, +0.156] | 0.684 vs 0.557 |
| Gemma 4 12B | RGB | 0.689 | 0.675 | +0.014 [-0.122, +0.141] | 0.589 vs 0.544 |
| Qwen2.5-VL 7B | design | 0.575 | 0.664 | -0.089 [-0.193, +0.015] | 0.594 vs 0.601 |
| Qwen2.5-VL 7B | RGB | 0.528 | 0.675 | -0.147 [-0.232, +0.018] | 0.525 vs 0.514 |

Gemma's point estimates are ahead of the statistics classifier, most clearly at a matched budget on the design screen (F1 0.684 against 0.557), but the AUROC differences are within noise at 10 pairs. Qwen is no better than, and on the point estimate worse than, three summary statistics.

## Calibration

Expected calibration error of the models' self-reported confidence, on the candidates they called an actionable class: **Gemma 0.292 (design), 0.438 (RGB); Qwen 0.409, 0.473.** All exceed the protocol's 0.2. Gemma reported only 0.90, 0.95 or 1.00 (88% exactly 0.95) on development data, so every floor up to 0.95 produced the same gate; the class label does all the work and the confidence none. A floor on this confidence would not be meaningful. This is the strongest argument for a separately calibrated confidence if the design is developed further.

## Against the protocol's pre-stated failure criteria

| Criterion | Gemma | Qwen |
| --- | --- | --- |
| Gate F1 above screen-alone F1 | Point estimates yes (+0.09, +0.08); intervals include zero, so **not established** | **No** |
| VLM AUROC above the statistics classifier | Point estimates yes (+0.06, +0.01); intervals include zero, so **not established** | **No**, worse |
| Confidence ECE at most 0.2 | **Failed** (0.29, 0.44) | **Failed** (0.41, 0.47) |

## What went wrong along the way

- **A development run crashed** (HTTP 500) while the laptop GPU was at 93 C and clocked down to 210 MHz; calls had slowed from about 1.4 s to 6.6 s. The runner now retries, pauses to cool, and the driver stops on the first failure. No candidate was classified twice.
- **Gemma returned empty answers at first**: it is a thinking model and used its whole token budget reasoning. Thinking is now off (Deviation 2); behaviour with reasoning enabled was not tested.
- **The design was not the best screen**, which changed the plan after development results were seen (Deviation 1). The pair-level intervals above were added after the test results were seen (Deviation 6).

## Limits

- **10 test pairs and 24 pairs in total**; every conclusion carries wide intervals, and most differences of a few points are not distinguishable from noise.
- **Gate figures cover a seeded sample of 400 candidates per screen**, not every candidate (the test split had about 740 and about 1,040).
- **Candidate labels depend on a 30% overlap rule**, and labels cover urban change only.
- **10 m pixels are very coarse** for buildings; the VLM is working at the edge of what the images show.
- **One prompt, one resolution of crop, two models, temperature 0.** No prompt search was done on purpose; a different prompt could behave differently, especially for Qwen.
- **Not measured:** an end-to-end recall of the whole pipeline (screen recall 39% of objects times gate recall of about 70% of candidates suggests roughly a quarter of labelled objects survive both, but that is not a direct measurement); other VLMs; a calibrated judge; other cities or sensors.

## Reproduce

```bash
bash scripts/fetch_oscd.sh                     # downloads the data (not redistributed)
python scripts/real_dev_screen.py              # development screen grid, writes frozen_screen.json
bash scripts/run_dev_gate.sh                   # development gate runs, writes frozen_gate.json
bash scripts/run_test_gate.sh                  # the one-shot test runs
python scripts/real_posthoc.py                 # pair-level bootstrap
```

Every candidate's raw model reply is in `results/real/gate/*.jsonl`.
