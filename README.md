# geo-eval-gate

Evaluator-gated geospatial change detection. Cheap, deterministic screening (NDVI delta + SSIM delta + morphology, with cloud masking) proposes candidate boxes; a vision-language model may then *label* a candidate, but its output is accepted only if it passes a schema, a calibrated confidence floor and an actionability rule. Seasonal and cloud labels are rejected as non-actionable.

**Status:** v0.1 scaffold. Screening, gate, GeoTIFF loader and synthetic generator are implemented and tested. **No real VLM (Florence-2 / Qwen2.5-VL) is wired in and no real imagery has been run**, so the only numbers are synthetic screening results in [docs/RESULTS.md](docs/RESULTS.md).

## Pipeline

```
GeoTIFF t0, t1 --(co-registration check)--> NDVI delta + SSIM delta --> cloud mask
   --> morphology --> candidate boxes --> crops --> VLM (untrusted text)
   --> ChangeVerificationResult schema --> confidence >= floor --> actionable class --> ACCEPT
```

| Gate outcome | Cause |
|---|---|
| REJECT_SCHEMA | not JSON, bad enum, confidence outside [0,1], short rationale, extra keys |
| REJECT_LOW_CONFIDENCE | confidence below `min_confidence` (default 0.8; not yet calibrated on real data) |
| REJECT_NOT_ACTIONABLE | SEASONAL_DEFOLIATION or CLOUD_ARTIFACT |
| ACCEPT | EARTHWORKS, NEW_STRUCTURE or ROAD_EXPANSION above the floor |

## Use

```bash
uv pip install -e ".[geo,dev]"
```

```python
from geo_eval_gate import screen, crop, evaluate
from geo_eval_gate.io import load_pair

t0, t1 = load_pair("2024-06.tif", "2025-06.tif")      # band order red, green, blue, nir
for cand in screen(t0, t1):
    outcome = evaluate(my_vlm_runner, crop(t0, cand), crop(t1, cand))
```

A runner is any object with `classify(before_rgb, after_rgb) -> str`. `ScriptedVLM` is a test double, not a model.

## Checks

```bash
pytest                          # 21 tests incl. hypothesis
mypy src tests scripts          # strict
python scripts/benchmark.py 100 # synthetic screening benchmark
```

## Limits

- Synthetic scenes have no terrain shadow, sun-angle change, registration error or real atmospheric effects.
- The cloud mask is a brightness/flatness heuristic; thin cloud, haze and cloud shadow are not handled.
- The confidence floor is a placeholder until a VLM's confidence is calibrated (ECE / reliability curve) on labelled patches.
- Sentinel-2 / NAIP download, SAM 2 / Prithvi segmentation and a Florence-2 or Qwen2.5-VL runner are not implemented.
