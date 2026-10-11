# Evaluation protocol (written before any real-data result was seen)

This file is committed before the OSCD data have been analysed, so the choices below cannot have been made after seeing results. Anything changed later is listed under [Deviations](#deviations).

## Question

On real Sentinel-2 imagery with human labels, does the evaluator-gated design do what it claims?

1. **Screen.** Does the deterministic NDVI + SSIM screen find labelled change, and is it better than simpler alternatives?
2. **Gate.** Does a vision-language model behind the schema, confidence and class gate raise the precision of the screen's candidates, and at what cost in recall?
3. **Value of the model.** Does the VLM add anything over a trivial classifier that sees only the candidate's own statistics?
4. **Calibration.** Is the VLM's self-reported confidence usable, i.e. is the 0.8 floor meaningful?

## Data

OSCD (Onera Satellite Change Detection), the multispectral Hugging Face version `blanchon/OSCD_MSI`: 24 Sentinel-2 city pairs (2015-2018), 13 bands, pixel masks of **urban change only** (new buildings and roads), per its dataset card.

- **Development:** the 14 training pairs. All tuning and all choices of thresholds happen here.
- **Test:** the 10 test pairs, evaluated **once**, after the configuration is frozen in `results/real/frozen.json` and committed.
- **Licence:** listed as unknown, so the data are not redistributed; they are downloaded by `scripts/fetch_oscd.sh` into a git-ignored folder. Only derived metrics are published.
- **Label caveat:** non-urban change (crops, vegetation clearing, water) is unlabelled, so any real non-urban change the screen finds counts against precision. Measured precision is therefore pessimistic for any method.

## Screen

Variants compared (all use the same cleanup and minimum-area rule):

| Variant | Definition |
| --- | --- |
| NDVI only | `abs(dNDVI) > t_ndvi` |
| SSIM only | `SSIM delta > t_ssim` |
| NDVI or SSIM (the design) | either condition |
| The design without the cloud mask | to see what the mask costs or buys |
| RGB difference | mean absolute RGB difference above a threshold, the plain-difference baseline |

**Tuning (development pairs only):** grid over `t_ndvi` in {0.10, 0.15, 0.20, 0.30}, `t_ssim` in {0.3, 0.5, 0.7, off}, minimum area in {10, 25, 50} pixels; objective is pixel-level F1 averaged over the 14 pairs. The best configuration per variant is frozen. The default configuration from the synthetic work is also reported untuned.

**Metrics (test pairs):** pixel precision, recall, F1 (micro-averaged over pairs); object recall (a labelled change object counts as found when at least 30% of its pixels are inside the screen's mask; objects under 4 pixels ignored); candidates per pair.

## Candidates and their labels

A candidate is a connected region of the frozen screen's mask. It is **positive** when at least 30% of its pixels are inside the human change mask, otherwise **negative**. If a split has more than 400 candidates, 400 are drawn uniformly at random with seed 0 (the same draw for every model), and the cap is reported.

## Gate

- **Models:** `gemma4:12b` (vision-capable, already installed) and `qwen2.5vl:7b` if it can be downloaded. Local Ollama, greedy decoding (temperature 0, seed 0), JSON-schema constrained output, one fixed prompt written before any data were seen (`src/geo_eval_gate/vlm_ollama.py`). Each candidate is shown as a single before/after image, padded context included, enlarged to 256 px per side.
- **Gate rule:** unchanged from the library: valid schema, confidence at or above a floor, an actionable class (EARTHWORKS, NEW_STRUCTURE, ROAD_EXPANSION).
- **Floor:** reported at the library default (0.8) **and** at the floor that maximises F1 on the development candidates (frozen before the test run).
- **Prompt changes:** none planned. If the development results show the prompt is clearly broken (for example a model that cannot produce the schema), it may be edited **using development candidates only**, and the edit is listed under Deviations.

**Metrics (test candidates):** gate precision, recall and F1 against the candidate labels; precision and recall of the screen alone (accept everything) for comparison; schema-failure rate; expected calibration error of the confidence (accepted-and-positive treated as correct); mean seconds per candidate.

## Baselines for the gate

- **Accept everything** (the screen alone).
- **Statistics classifier:** logistic regression on three features of the candidate (log area, mean abs dNDVI, mean SSIM delta), fitted on the development candidates, evaluated on the test candidates. This answers "does the VLM beat a model that has never seen a pixel?".
- Compared by AUROC where a score exists (VLM confidence for accepted-class candidates, regression probability) and by precision at matched recall.

## What would count as the design failing

State now, so it cannot be argued afterwards:

- If the gate's test F1 is not above the screen-alone F1, the gate has not helped on this data.
- If the VLM's AUROC is not above the statistics classifier's, the VLM adds nothing over cheap statistics.
- If the expected calibration error of the VLM confidence exceeds 0.2, its confidence should not be used as a floor.

All of these will be reported whichever way they come out.

## Known limits, stated in advance

Sentinel-2 at 10 m is coarse: a house is a few pixels, so the VLM is working at the edge of what the images can show. Labels are urban-only. 24 pairs is small. Intervals are not computed across pairs beyond a bootstrap over test pairs (10 pairs) and over candidates; both will be wide.

## Deviations

Listed in the order they happened, each with what had been seen at the time.

1. **Second screen for the gate evaluation (decided after the development screen results).** The development grid showed the pre-registered design (NDVI or SSIM) was *not* the best screen: best development pixel F1 was 0.227 for the design against 0.297 for the plain RGB-difference baseline and 0.260 for SSIM alone (NDVI alone 0.094). The gate is therefore evaluated on candidates from **both** screens. The pre-registered evaluation (candidates from the design) remains the primary result; the RGB-difference screen is an added, clearly labelled secondary analysis whose choice was informed by development results. The test split had not been touched when this was decided.
2. **Thinking turned off for Gemma (decided on development candidates).** `gemma4:12b` is a thinking model; with the 200-token budget it spent all of it reasoning and returned an empty answer on every call (0 of 8 valid in the probe). Calls now send `think: false`, after which it returned valid JSON (8 of 8, then 400 of 400 on both development runs). This applies to both models' calls (Qwen2.5-VL is not a thinking model and is unaffected). Reasoning-enabled behaviour was not evaluated.
3. **Runner robustness changes (no effect on results).** One development run crashed on an HTTP 500 while the laptop GPU was thermally throttled (93 C, 210 MHz). Added: retries on server errors, a pause while the GPU is above 84 C, and a driver that stops on the first failure. Cached replies are reused, so no candidate was classified twice.
4. **No prompt change for Qwen2.5-VL.** On development candidates it labelled 97% of candidates NEW_STRUCTURE or ROAD_EXPANSION (gate precision equals screen-alone precision), a non-discriminating result but not a broken one (valid JSON every time). Per the protocol the prompt is left unchanged and Qwen is evaluated on the test split as planned.
5. **Confidence floors are effectively meaningless for Gemma.** It reports only 0.90, 0.95 or 1.00 (88% exactly 0.95), so every floor up to 0.95 yields the same gate. The frozen floors (design 0.9, RGB 0.95) are recorded as selected, and the calibration result on the test split is the informative one.
6. **Pair-level bootstrap added after the test results were seen.** The test stage reported candidate-level intervals only. Because candidates within a scene pair are correlated, `scripts/real_posthoc.py` was added afterwards to bootstrap over the 10 test pairs (2,000 resamples) for the gate F1, the F1 and precision differences from the screen alone, and the AUROC difference from the statistics classifier. It changes no result. These intervals are wider and are the ones used for conclusions.

