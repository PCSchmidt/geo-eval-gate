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

None yet.
