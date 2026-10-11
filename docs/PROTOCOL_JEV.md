# Protocol: calibrated-judge extension with TypeSafe Jev (written before any Jev call was made)

Committed before the first request to the API, so the choices below cannot have been made after seeing Jev's output. Anything changed later is listed under [Deviations](#deviations). This extends [PROTOCOL.md](PROTOCOL.md); read that first.

## Why

The main evaluation ([RESULTS_REAL.md](RESULTS_REAL.md)) found that the vision models' self-reported confidence is unusable: expected calibration error 0.29-0.47, and Gemma only ever reports 0.90, 0.95 or 1.00, so every confidence floor up to 0.95 gives the same gate. The class label does the work and the confidence none. A **calibrated** probability would let the deterministic floor threshold something trustworthy, which is the design's whole point.

TypeSafe's Jev is a text-only "System One" model that returns typed decisions with calibrated probabilities ([announcement](https://typesafe.ai/blog/introducing-system-one-models-and-jev)). It cannot see images, so it cannot replace the vision model. This experiment asks whether it can sit **behind** it as a judge.

## Question

1. **Calibration.** Is Jev's probability that a candidate is real change calibrated on these candidates?
2. **Added value.** Does it beat a cheap alternative: a logistic regression stacked on the same inputs?
3. **Does text help at all?** Does a Jev judge that sees only the candidate's statistics beat the three-number logistic regression?

## Caveat stated first: the test split has been seen

The test split was run once for the vision-model gate and analysed, so I know the vision models' test behaviour, including that their confidence is miscalibrated. This extension was motivated by that result. To limit the damage: every design choice (the text template, the question, the threshold) is frozen on development data before any test request; the test candidates are scored once; and the outcome is reported whichever way it falls. The result should still be read as a second look at a split already seen, not as a fresh held-out test.

## Design

**What Jev is shown (text only).** For each candidate, a fixed template with:
- (a) the candidate's statistics: area in pixels, bounding-box width and height, mean absolute NDVI change, mean SSIM change, and which screen produced it;
- (b) the vision model's reply (Gemma 4 12B, already cached from the main runs): its class, its stated confidence, and its one-sentence rationale.

Nothing from the ground truth and no pixel data is sent.

**Two arms:** **A** sees (a) only; **B** sees (a) and (b).

**Question** (Jev type `noul`, a yes/no returning `p(yes)`): *"Is this region a genuine human-made new building or road built between the two dates, rather than seasonal vegetation change, cloud, shadow or sensor noise?"* The instruction text is frozen before the first call except for a format check on 5 development candidates.

**Decision.** Accept when `p >= tau`. `tau` is chosen on the development candidates to maximise F1 over a grid of 0.10 to 0.90 in steps of 0.05, then frozen.

**Data and terms.** Only derived numbers and model-written text about public Sentinel-2 scenes are sent; no imagery. TypeSafe's terms forbid using Jev's output to distil or train a model: here its output is only thresholded and measured, and nothing is fitted to it (the stacked baseline below is fitted on features and vision-model outputs, not on Jev outputs).

## Baselines (all fitted on development candidates, frozen before test)

1. **The existing Gemma gate:** actionable class at the frozen floor.
2. **Statistics-only logistic regression** (already frozen in `results/real/frozen_gate.json`).
3. **Stacked logistic regression:** the three statistics plus the vision model's actionable flag, its stated confidence and its class (one-hot). This is the strong, cheap alternative Jev has to beat.

## Evaluation

The same 400-candidate seeded samples per screen as the main test runs, for both screens, using Gemma's cached replies. Qwen's replies are not used (they do not discriminate).

**Metrics:** precision, recall and F1 at the frozen `tau`; AUROC; Brier score and expected calibration error (10 bins) of `p` over **all** candidates; precision lift over the screen alone; cost (API-reported input tokens at the published $0.042 per million) and latency. Intervals: bootstrap over the 10 test pairs, 2,000 resamples, for differences against each baseline.

## Pre-stated criteria

- **C1, calibration.** ECE of arm B's `p` on the test candidates at most **0.10**. Otherwise Jev's probability is not usable as a floor here.
- **C2, added value.** Arm B AUROC minus the stacked regression's AUROC, with the pair-level 95% interval entirely above zero. A point estimate at or below zero means Jev adds nothing over cheap stacking.
- **C3, does text help.** Arm A AUROC minus the statistics-only regression's AUROC, same rule.
- **C4, what it buys.** Arm B precision lift and recall retention at `tau`, compared with the existing Gemma gate. Reported, no threshold set.

## My expectation, written down so it can be wrong

I expect Jev to be well calibrated (C1 met), but I do **not** expect it to beat the stacked regression (C2 not met) and I am unsure about C3: the candidate statistics are weak features and the regression handles numbers well. If so, the honest finding is that its value is calibrated, zero-shot probabilities and low latency, not extra accuracy.

## Budget and stopping

At most about 3,200 calls (dev and test, two screens, two arms), roughly a million input tokens, about $0.05 at the published price. Stop and report if the running estimate exceeds $1, or if more than 5% of calls fail after retries.

## Limits, stated in advance

Ten test pairs; one vision model's replies; Jev is used zero-shot (only the instruction text is ours to change); the test split was seen; early-access vendor model whose training method (it describes "Reinforcement Learning for Calibrated Decisions") is not disclosed in the announcement, and whose headline claims are the vendor's own.

## Deviations

None yet.
