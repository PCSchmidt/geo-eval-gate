# geo-eval-gate — satellite change detection where an AI may label a change but cannot approve one

**Status: v0.1, portfolio project.** The deterministic screen, the evaluator gate, the GeoTIFF loader and a synthetic-scene generator are built and tested. **No real vision-language model and no real imagery have been used yet**; the only numbers are from synthetic scenes ([Results](#results)).

```text
$ python examples/demo.py
injected: 2 buildings, 1 cloud, global autumn decline
deterministic screen: 2 candidate boxes (cloud masked, season ignored)
  box x78-94 y25-42  area 268px  dNDVI 0.62
  box x58-74 y89-103  area 220px  dNDVI 0.63

evaluator gate on the first candidate, with different (untrusted) model replies:
  building  -> ACCEPT
  unsure    -> REJECT_LOW_CONFIDENCE  0.55 < 0.80
  season    -> REJECT_NOT_ACTIONABLE
  not json  -> REJECT_SCHEMA          Expecting value: line 1 column 1 (char 0)
  bad enum  -> REJECT_SCHEMA          1 validation error for ChangeVerificationResult
```

*Real output of [examples/demo.py](examples/demo.py). The scene is synthetic, and the "model replies" are hand-written strings standing in for a vision-language model, to show how the gate treats each kind of answer. They are not model outputs.*

## What is this? (plain-language overview)

Comparing two satellite photos of the same place taken months apart sounds easy: subtract one from the other. In practice a raw difference lights up everywhere. Crops turn brown in autumn, clouds drift across, the sun is at a different angle, and a few new roofs and a bulldozed field are buried in the noise. Sending every changed patch to an AI that looks at pictures would be slow and costly, and it would make confident mistakes, such as calling a cloud a building.

geo-eval-gate does it in two stages, and keeps the decision away from the AI:

1. **A cheap, fixed screen** takes the two images, checks they line up, measures how much the *vegetation index* (NDVI) and the *structure* (SSIM) changed at each pixel, masks out clouds, cleans up the result and proposes a handful of **candidate boxes**. Seasonal colour shifts are ignored because they change the colour but not the structure.
2. **A vision-language model may then label each candidate** from a fixed list: earthworks, new structure, road expansion, seasonal defoliation, or cloud artifact. But the model's reply is treated as untrusted text. It must be valid JSON in an exact format, its confidence must clear a floor, and its label must be one that counts as a real, actionable change. Otherwise the candidate is rejected, with the reason recorded.

**What it is not.** It is not a finished remote-sensing product. It does not download imagery, run a segmentation model, or contain a real VLM runner yet. It is the screening and gating core, tested on synthetic scenes.

### Who it is for, and when it earns its place

| If you are... | the project gives you... |
| --- | --- |
| building change detection on satellite or aerial imagery | a screening stage that cuts the number of patches an expensive model has to look at |
| putting a VLM or other model into an analysis pipeline | a pattern for accepting its output only through a schema, a confidence floor and an actionability rule |
| an analyst who needs to trust automated alerts | a decision with a recorded reason, not an unexplained model verdict |
| evaluating VLMs on imagery | a harness where the model's answers can be scored against injected, known changes |

It is a poor fit if you need pixel-accurate segmentation, near-real-time processing, or results validated on real imagery today.

### Why a screen first, and why a gate after?

A vision-language model on every tile of a large raster is too slow and expensive, so a cheap deterministic stage narrows the field. A model's confidence is not a probability you can trust by default, so it is not allowed to approve a change by itself: a schema, a floor and a class rule decide, in plain code.

**What's real and what's not.** The screening maths, the cloud mask, the gate and the loader are real, runnable and tested. The imagery in every example and benchmark is **synthetic**, and the VLM is a scripted stand-in. Whether the screen and the gate work on real Sentinel-2 or NAIP scenes is **not yet known**.

## At a glance

| | |
| --- | --- |
| Input | two co-registered GeoTIFFs (red, green, blue, near-infrared bands) |
| Screen | NDVI delta + SSIM delta, cloud mask, morphology, minimum area, candidate boxes and crops |
| Label | any model that returns text, behind a `VLMRunner` interface (none included) |
| Gate | strict schema, confidence floor (default 0.8), actionable classes only |
| Measured (synthetic) | building recall 0.975 with the cloud mask, 0 false candidates per scene; about 4.5 ms per 128x128 scene |
| Tests | 21, including property-based; `mypy --strict`; ruff |

## Architecture at a glance

```mermaid
flowchart LR
    IN[/"two GeoTIFFs<br>t0 and t1"/]
    subgraph screen["1 · Deterministic screen"]
        direction TB
        REG["co-registration check<br>CRS, transform, shape"]
        IDX["NDVI delta + SSIM delta"]
        CLD["cloud mask<br>bright + flat pixels,<br>dilated past the SSIM window"]
        MORPH["morphology + min area<br>to candidate boxes + crops"]
        REG --> IDX --> CLD --> MORPH
    end
    subgraph vlm["2 · Label (probabilistic)"]
        VLM["Vision-language model<br>untrusted text"]
    end
    subgraph gate["3 · Evaluator gate (deterministic)"]
        direction TB
        S{"valid JSON,<br>enum class,<br>confidence in 0-1?"}
        C{"confidence ≥ floor?"}
        A{"class actionable?"}
    end
    OK(["ACCEPT<br>EARTHWORKS · NEW_STRUCTURE<br>ROAD_EXPANSION"])
    R1(["REJECT_SCHEMA"])
    R2(["REJECT_LOW_CONFIDENCE"])
    R3(["REJECT_NOT_ACTIONABLE<br>SEASONAL_DEFOLIATION<br>CLOUD_ARTIFACT"])
    IN --> REG
    MORPH --> VLM --> S
    S -- "yes" --> C
    S -- "no" --> R1
    C -- "yes" --> A
    C -- "no" --> R2
    A -- "yes" --> OK
    A -- "no" --> R3
    classDef det fill:#e8f1fb,stroke:#2f6db5,color:#102a43
    classDef prob fill:#fff1d6,stroke:#c27c0e,color:#3d2500,stroke-width:3px
    classDef bad fill:#fde8e8,stroke:#c0392b,color:#4a1010
    classDef ok fill:#e3f5e8,stroke:#2e8b57,color:#0f3b21
    classDef io fill:#f2f2f2,stroke:#666,color:#222
    class REG,IDX,CLD,MORPH,S,C,A det
    class VLM prob
    class R1,R2,R3 bad
    class OK ok
    class IN io
    style screen fill:#f4f8fd,stroke:#2f6db5,color:#102a43
    style vlm fill:#fff9ec,stroke:#c27c0e,color:#3d2500
    style gate fill:#f4f8fd,stroke:#2f6db5,color:#102a43
```

*Blue is deterministic code; the amber box is the only probabilistic step, and nothing it says is accepted without passing the three checks after it.*

## Quickstart

```bash
git clone https://github.com/PCSchmidt/geo-eval-gate && cd geo-eval-gate
uv venv && uv pip install -e ".[dev]"            # add ".[geo]" for GeoTIFF loading (rasterio)

python examples/demo.py                         # the output shown above
python scripts/benchmark.py 100                 # synthetic screening benchmark
pytest -q                                       # 21 passed
```

```python
from geo_eval_gate import screen, crop, evaluate
from geo_eval_gate.io import load_pair            # needs the [geo] extra

t0, t1 = load_pair("2024-06.tif", "2025-06.tif")  # bands: red, green, blue, nir
for cand in screen(t0, t1):
    outcome = evaluate(my_vlm_runner, crop(t0, cand), crop(t1, cand))
```

A runner is any object with `classify(before_rgb, after_rgb) -> str` returning the model's raw text. `ScriptedVLM` is a test double, not a model.

## Approach: why it is built this way

- **Screen cheaply, judge sparingly.** Deterministic maths narrows a whole raster to a few boxes before any model runs.
- **The model proposes; plain code disposes.** Schema, confidence floor and class rule are ordinary code with tests; a model can never approve a change on its own say-so.
- **Reject for stated reasons.** Every outcome is one of four named decisions, so a rejected candidate explains itself.
- **Don't trust a mask you haven't tested.** The cloud mask, and the bug that its halo originally leaked false candidates, are covered by tests.
- **Synthetic first, honestly labelled.** Known injected changes make recall and false-candidate rates measurable before real data is involved, and the results say they are synthetic.

## Motivation

Remote-sensing change detection is a natural place for the pattern in my other projects: a fast, cheap deterministic stage, a probabilistic stage that is allowed to be wrong, and a gate that decides. The roadmap goal was a pipeline that could sit in front of an analyst and cut false alarms from clouds and seasons without letting a model's confidence stand in for evidence.

## Method (what the pipeline actually does)

1. **Load and check** (`io.py`): read the bands as reflectance; refuse a pair whose CRS, transform or shape differ.
2. **Index maps** (`screening.py`): NDVI = (NIR - red) / (NIR + red); SSIM computed on NIR + red with a 7-pixel mean window. A pixel is a change candidate if its absolute NDVI change exceeds 0.25 **or** its SSIM delta exceeds 0.5.
3. **Cloud mask**: pixels that are bright (mean above 0.75) and nearly flat across red, green and blue, dilated by 6 pixels so the SSIM window's halo around a cloud is also excluded.
4. **Clean and box**: binary opening then closing, connected components, and a minimum area of 25 pixels; each region becomes a box with its mean NDVI and SSIM change, sorted by size.
5. **Crop** each box with padding for the labelling model.
6. **Gate** (`gate.py`): parse the model reply as JSON against `ChangeVerificationResult` (confidence 0-1, one of five classes, rationale of 10-600 characters, no extra keys); reject below the confidence floor; reject classes that are not actionable.

## Results

Synthetic scenes only (`geo_eval_gate.synthetic.make_pair`: 128x128, seeds 1000-1099, two buildings, one cloud and a global seasonal vegetation decline per pair). This measures the deterministic screen, not any model. Reproduce: `python scripts/benchmark.py 100`.

| Config | Building recall | False candidates / scene | Candidates / scene | ms / scene |
| --- | --- | --- | --- | --- |
| NDVI + SSIM, cloud mask on | 0.975 | 0.00 | 1.77 | 4.5 |
| NDVI + SSIM, cloud mask off | 1.000 | 0.61 | 2.42 | 4.2 |

- The cloud mask removes all 0.61 false candidates per scene, at a cost of 2.5 points of recall: a randomly placed cloud sometimes covers a building, and masked pixels are excluded by design.
- A seasonal decline alone produces zero candidates (tested separately).
- With 200 buildings, one missed building is 0.5 points; differences under about 1.5 points are noise.
- Two bugs were found and fixed while building these tests: a cloud mask halo that leaked false candidates, and a generator that applied the seasonal change after painting the cloud.

Full tables and what was not measured: [docs/RESULTS.md](docs/RESULTS.md).

## Limitations

- **Synthetic scenes only.** No terrain shadow, sun-angle change, registration error, haze or real atmospheric effects.
- **No real model.** The VLM is a scripted stand-in; taxonomy accuracy, confidence calibration and gate precision on real patches are unmeasured.
- **The confidence floor (0.8) is a placeholder.** A model's confidence has to be calibrated (reliability curve, ECE) on labelled patches before a floor means anything.
- **Simple cloud mask.** A brightness-and-flatness rule; thin cloud, haze and cloud shadow are not handled.
- **Thresholds are untuned on real data.** NDVI 0.25, SSIM 0.5, minimum area and the window size are starting values.
- **Not implemented:** Sentinel-2 / NAIP download, SAM 2 or Prithvi segmentation, a Florence-2 or Qwen2.5-VL runner.

## Operational notes

### What runs where

Everything is local and CPU-only today; the screen processes a 128x128 synthetic scene in about 4.5 ms. A real VLM runner (not included) would need a GPU or a hosted endpoint, and the gate does not care which.

### Data and keys

No keys and no downloads. The benchmark data is generated from a seed. Any real imagery used later should be public or unclassified (Sentinel-2, NAIP).

### Verify the claims (a reviewer's path)

```bash
pytest -q                          # 21 passed
mypy src tests scripts             # strict, clean
python examples/demo.py            # the screen and gate decisions shown at the top
python scripts/benchmark.py 100    # the table above
docker build -t geo-eval-gate . && docker run --rm --network none geo-eval-gate
```

### Documentation map

| Doc | What it covers |
| --- | --- |
| [docs/RESULTS.md](docs/RESULTS.md) | the synthetic benchmark, how to read it, what is not measured |
| [examples/demo.py](examples/demo.py) | the worked example above |
| [scripts/benchmark.py](scripts/benchmark.py) | the benchmark |
| [src/geo_eval_gate/gate.py](src/geo_eval_gate/gate.py) | the evaluator gate |

## License

MIT. See [LICENSE](LICENSE).

## Author

Chris Schmidt ([PCSchmidt](https://github.com/PCSchmidt)). Part of a portfolio on evaluator-gated AI systems: probabilistic components propose, deterministic gates decide.
