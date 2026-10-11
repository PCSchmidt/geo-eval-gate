# Results: calibrated-judge extension with TypeSafe Jev

Plan: [PROTOCOL_JEV.md](PROTOCOL_JEV.md), pushed before the first API call. Main evaluation: [RESULTS_REAL.md](RESULTS_REAL.md).

**Setup.** Jev, a text-only model that returns a calibrated yes/no probability, was asked whether each candidate region was a genuine new building or road. It saw only text: the candidate's statistics (arm A), or the statistics plus the vision model's cached reply (arm B). The thresholds were frozen on development candidates and the 10 test pairs were scored once. The test split had already been analysed for the vision-model gate, so this is a second look at a split already seen.

## Summary

1. **Jev behind the vision model gives a usable probability but no extra discrimination.** Arm B reproduces Gemma's gate: precision lift +0.246 (design screen) and +0.175 (RGB screen) against Gemma's +0.242 and +0.177, with identical recall. Its ranking (AUROC) is no better than Gemma's, and slightly worse on the design screen.
2. **It improves calibration, modestly.** Against Gemma's confidence converted to an implied probability of real change, expected calibration error falls from 0.232 to 0.166 (design) and from 0.284 to 0.124 (RGB). That misses the 0.10 criterion.
3. **A cheap stacked logistic regression is as good or better.** It has the best AUROC of anything tested (0.782 and 0.739) and, on the RGB screen, the best calibration (0.072, meets the criterion).
4. **Jev reading bare numbers is poor, and on the design screen systematically backwards** (AUROC 0.218 on test, 0.363 on development).
5. **It is cheap and fast:** about $0.014 per 800 calls, 240 ms per call; the whole experiment cost about $0.06.

## Test results (400 candidates per screen, 10 test pairs)

| Screen | Method | Threshold | Precision | Recall | F1 | AUROC | Calibration error | Brier |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Design (screen-alone precision 0.422) | Arm A: Jev, statistics only | 0.20 | 0.421 | 0.994 | 0.592 | 0.218 | 0.315 | 0.303 |
| | **Arm B: Jev, statistics + Gemma reply** | 0.50 | 0.669 | 0.704 | 0.686 | 0.701 | 0.166 | 0.223 |
| | Stacked logistic regression | 0.25 | 0.667 | 0.698 | 0.682 | **0.782** | 0.185 | 0.226 |
| | Gemma gate (main evaluation) | frozen floor | 0.665 | 0.704 | 0.684 | 0.728 | 0.232 (implied) | 0.254 |
| | Statistics-only regression | - | - | - | - | 0.664 | - | - |
| RGB (screen-alone precision 0.345) | Arm A: Jev, statistics only | 0.15 | 0.346 | 0.891 | 0.499 | 0.541 | 0.179 | 0.257 |
| | **Arm B: Jev, statistics + Gemma reply** | 0.35 | 0.520 | 0.674 | 0.587 | 0.684 | 0.124 | 0.220 |
| | Stacked logistic regression | 0.20 | 0.500 | 0.783 | 0.610 | **0.739** | **0.072** | 0.197 |
| | Gemma gate (main evaluation) | frozen floor | 0.522 | 0.674 | 0.589 | 0.689 | 0.284 (implied) | 0.301 |
| | Statistics-only regression | - | - | - | - | 0.675 | - | - |

The stacked regression uses the three statistics plus Gemma's actionable flag, stated confidence and class; it was fitted on the 400 development candidates and its threshold was chosen from 5-fold cross-validated development predictions. Calibration error is over all candidates (10 bins) of the probability of real change.

**A figure not to use.** `jev_test_*.json` contains `ece_stated_confidence` for Gemma (0.534 and 0.611). It treats Gemma's confidence in its own label as a probability of real change, so it is not comparable to Jev's; it is kept unaltered for transparency. The fair comparison is the "implied" column above (Gemma's confidence converted to a probability of real change), computed by `scripts/real_jev_posthoc.py` after the test results were seen (Deviation 1).

## Against the criteria set in advance

| Criterion | Design screen | RGB screen | Verdict |
| --- | --- | --- | --- |
| C1: arm B calibration error at most 0.10 | 0.166 | 0.124 | **Not met** (RGB is close) |
| C2: arm B AUROC minus stacked regression, pair-level 95% interval entirely above zero | -0.081 [-0.129, +0.010] | -0.055 [-0.133, -0.005] | **Not met**; Jev is slightly worse (the RGB interval is entirely below zero) |
| C3: arm A AUROC minus statistics-only regression | -0.446 [-0.563, -0.141] | -0.134 [-0.218, -0.007] | **Not met**; far worse |
| C4: arm B precision lift (pair-level 95%) | +0.246 [+0.096, +0.335] | +0.175 [+0.048, +0.260] | Same as Gemma's gate |

Also: arm B minus Gemma AUROC is -0.027 [-0.043, -0.001] (design) and -0.005 [-0.039, +0.025] (RGB), so Jev adds no ranking ability over the model whose reply it is reading.

**My written expectation against the outcome.** I expected C1 met (wrong: close on RGB, not met), C2 not met (right), and was unsure about C3 (it failed, badly).

## Calibration in detail

Reliability on the test candidates (mean predicted probability against the actual share that are real change):

| Screen | Probability bin | Jev arm B: n, predicted / actual | Gemma implied probability: n, predicted / actual |
| --- | --- | --- | --- |
| Design | below 0.10 | 210, 0.07 / 0.21 | 221, 0.04 / 0.23 |
| | 0.65 to 0.80 | 60, 0.76 / 0.82 | none |
| | 0.80 to 1.00 | 115, 0.84 / 0.60 | 179, 0.96 / 0.66 |
| RGB | below 0.10 | 221, 0.04 / 0.20 | 221, 0.04 / 0.20 |
| | 0.35 to 0.50 | 37, 0.46 / 0.43 | none |
| | 0.50 to 0.65 | 85, 0.57 / 0.54 | none |
| | 0.65 to 0.80 | 57, 0.68 / 0.54 | none |
| | 0.80 to 1.00 | none | 179, 0.96 / 0.52 |

What this shows: Gemma's implied probability takes essentially two values (about 0.04 and 0.96), and the "real change" candidates it calls seasonal (about 20% of that bin) are invisible to any downstream judge. Jev spreads the probability into the middle using the statistics, and on the RGB screen those middle bins are well calibrated (0.46 against 0.43, 0.57 against 0.54). It stays overconfident at the top of the design screen (0.84 predicted, 0.60 actual) and, like the model it reads, cannot recover the real changes the vision model already dismissed.

## What this means

- **For this task, Jev behind a vision model is a calibration layer, not a better judge.** It gives an adjustable threshold with the same precision and recall as the vision gate, at negligible cost.
- **If labelled data exist, the stacked regression is the better calibrator** here: higher AUROC, and equal or better calibration. Jev's possible advantage is the case with no labelled data at all (it used labels only to choose one threshold); that case was not tested here, because the baseline it would be compared against does require labels.
- **A text-only judge should not be handed bare numeric features.** The design-screen arm A result (AUROC 0.218 on test, 0.363 on development) means its reading of those statistics is systematically backwards. I did not exploit that (flipping its ranking would mean fitting to its output, and would be forking paths on a split already seen). Why it is backwards is untested; one guess is that it associates a large structural change with vegetation, but that is only a guess.

## Limits

- **The test split was seen** before this extension was designed (it was motivated by the vision models' miscalibration there). Read this as a second look, not a fresh held-out test.
- **Ten test pairs**, one vision model's replies, and wide pair-level intervals; the stacked regression's AUROC advantage over Gemma was not significance-tested.
- **Zero-shot with one fixed instruction.** A different wording, or giving Jev more context, may behave differently; no wording search was done on purpose.
- **Early-access vendor model**; its training method is not disclosed in the announcement and its headline claims are the vendor's own.
- **Stacked regression fitted on only 400 development candidates.** More data could help it or overfit it.
- **Labels are OSCD's urban-change masks**, so "real change" excludes other genuine change.
- Jev's terms forbid using its output to train or distil a model. Nothing was fitted to its output; its probabilities were thresholded (one threshold per arm and screen, chosen on development data) and measured.

## Reproduce

```bash
# needs TYPESAFE_AI_API_KEY in the environment or a git-ignored .env
python scripts/real_jev.py probe     # 5-candidate format check
python scripts/real_jev.py dev       # development stage, writes results/real/frozen_jev.json
python scripts/real_jev.py test      # one-shot test stage, writes results/real/jev_test_*.json
python scripts/real_jev_posthoc.py   # the fair calibration comparison
```

Every Jev reply is in `results/real/jev/*.jsonl`. Total cost about $0.06 at the published $0.042 per million input tokens.
