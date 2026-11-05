# geo-eval-gate: Evidence Notes

Companion to `geo-eval-gate.md`. Labels: Confirmed, Ran it, Per the docs, My reading, Ask the author, Author says. Paths are relative to the repository clone (read-only); all runs were in a scratch copy made with `git archive HEAD`.

## E1 Fact sheet

| Fact | Value | Label |
| --- | --- | --- |
| Name, licence | geo-eval-gate, MIT (LICENSE), version 0.2.0 (pyproject) | Confirmed |
| Kind | Research prototype: screening + gating library, plus real-data evaluation scripts | Confirmed |
| Language, size | Python >=3.11; src 11 modules about 880 lines; tests 6 files about 570 lines; 9 scripts about 1,100 lines | Confirmed |
| Tests | 54 passed (scratch copy initialised as a git repo); 51 passed + 3 skipped without git (secret-guard tests need a checkout) | Ran it |
| Type check, style | `mypy src tests` clean (17 files); `mypy src tests scripts` clean (24 files, needs the `real` extra); `ruff check src tests` clean | Ran it |
| Commits | 18 at the 2026-11-05 pull, 2026-10-09 to 2026-10-27 (code work 10-09 to 10-13; the last two commits add and then replace an explainer document, not read) | Confirmed |
| Co-author credits | Two AI assistant models credited (17 commits and 1); all 18 carry a credit; all authored as Chris Schmidt. The guide says only 'AI coding agents' | Confirmed |
| Agent instruction files | None in the repository (no agent instruction files or agent configuration folders) | Confirmed |
| Deployed? | No. Dockerfile only runs pytest | Confirmed |
| Users | None shown | Confirmed |
| Needs | Local GPU and Ollama for real runs; about 20 MB per OSCD pair downloaded; optional paid API key for Jev (about $0.06 total per docs) | Per the docs |
| Fresh install | Works; versions unpinned (`>=`). Scratch install pulled numpy 2.5.4, scipy 1.18.1, pydantic 2.14.1 on Python 3.14.6; CI uses 3.12 | Ran it |
| Related projects | VERA (the Jev client comment says "same call VERA uses"), the evaluator-gated roadmap family | Confirmed / Author says |

## E2 Reading and running log

Read: README, docs/PROTOCOL.md, PROTOCOL_JEV.md, RESULTS.md, RESULTS_REAL.md, RESULTS_JEV.md, all src modules, gate/screening/candidate_set/scoring/jev/vlm_ollama in full, test names and several test bodies, scripts/real_gate.py head and real_jev.py head, run scripts, ci.yml, pyproject, Dockerfile, .gitignore, .env.example (template only; no `.env` was opened), result JSON heads (frozen_screen, frozen_gate, frozen_jev, gate_test_*), sample JSONL lines. Not read: `geo-eval-gate_MASTER_EXPLAINER.md` (an earlier explainer in the clone; deliberately skipped, including its history), the bodies of scripts/real_posthoc.py, real_jev_posthoc.py, real_dev_screen.py, benchmark.py and probe_vlm.py beyond headers.

Commands (scratch copy):
- `python -m venv v; pip install -e ".[dev]"`; `pytest -q -p no:cacheprovider` gave 51 passed, 3 skipped; after `git init; git add -A`, 54 passed.
- `python examples/demo.py` reproduced the README output (including the five gate decisions).
- `python scripts/benchmark.py 100` gave recall 0.975 / 0.00 false / 1.77 candidates / 4.0 ms (mask on) and 1.000 / 0.61 / 2.42 / 4.3 ms (mask off), matching RESULTS.md apart from timing.
- `pip install -e ".[real]"` then `mypy src tests scripts`: clean.
- Not run: real-data scripts (large download, GPU, one-shot test stage that refuses to rerun), Jev scripts (paid API key), Docker build/run (not attempted).
- The clone was never written to; `git status --short` there was empty before and after (only reads and `git archive`).

## E3 Claims check (levels: L1 doc matches committed result file; L2 re-run; L3 independent recompute)

| ID | Claim (source) | Check | Verdict |
| --- | --- | --- | --- |
| CL-01 | 54 tests pass (README) | L2 | Supported (needs git checkout for all 54) |
| CL-02 | mypy --strict clean over src, tests, scripts (README) | L2 | Supported with the `real` extra installed. CI runs only `mypy src tests` |
| CL-03 | ruff clean (README, RESULTS.md) | L2 | Supported; CI does not run ruff |
| CL-04 | Synthetic: recall 0.975, 0 false/scene, 1.77 candidates, 4.5 ms; mask off 1.000, 0.61, 2.42 (README, RESULTS.md) | L2 | Supported (timing 4.0 ms in my run) |
| CL-05 | Demo output as shown (README) | L2 | Supported |
| CL-06 | Screen test: pixel F1 0.333 design, 0.348 RGB; both find about 39% of 668 objects (README, RESULTS_REAL) | L1 (gate_test_*.json screen_full_test_split: 0.3328, object_recall 0.392, objects 668, candidates 735 / 1036) | Supported at L1 |
| CL-07 | Gemma design: accepted 179, precision 0.665, recall 0.704, screen-alone precision 0.422 (RESULTS_REAL) | L1 (gate_test_design_gemma4_12b.json), plus L3 arithmetic: 0.422 x 400 = 169 real; 0.665 x 179 = 119; 119/169 = 0.704 | Supported |
| CL-08 | Qwen design accepts 393, precision 0.425 (RESULTS_REAL) | Only the 0.8-floor figures (385, 0.434) were seen in JSON; 393 is at the frozen floor, not re-derived | Partly checked (L1 not completed) |
| CL-09 | Qwen labels about 97% of candidates construction (docs, dev) | Test class counts: 237 + 158 of 400 = 98.75% | Supported (test figure differs slightly) |
| CL-10 | Gemma class counts on test: 202 seasonal, 167 new structure, 19 cloud, 7 earthworks, 5 road (design) | L1 | Supported |
| CL-11 | Gemma confidences only 0.90, 0.95, 1.00; 88% exactly 0.95 (dev) | Not recomputed (JSONL available); test sample lines consistent | Per the docs |
| CL-12 | ECE 0.29 / 0.44 Gemma, 0.41 / 0.47 Qwen (RESULTS_REAL) | L1: 0.292, 0.438 (Gemma), 0.409 (Qwen design) | Supported |
| CL-13 | Pair-level ranges (RESULTS_REAL) | Not recomputed | Per the docs |
| CL-14 | Jev arm B ECE 0.166 / 0.124 vs Gemma implied 0.232 / 0.284; stacked AUROC 0.782 / 0.739; Jev arm A AUROC 0.218 (RESULTS_JEV) | Spot-read frozen_jev.json (dev: arm B AUROC 0.699, ECE 0.162); test values not recomputed | Per the docs |
| CL-15 | Whole Jev experiment cost about $0.06; price $0.042 per million input tokens | Price is a code constant; spend computed from token counts in JSONL (about 440 tokens per call) is consistent in order of magnitude; no invoice | Per the docs |
| CL-16 | Plan committed before results (PROTOCOL: "before any result was seen") | History: protocol 2026-10-10 10:28, dev results commit 11:34, freeze 10-11 07:34, test results 08:56; Jev protocol 10-11 11:30, Jev test results 12:37 | Supported by commit times only (push times not checked; no way to show test data were unseen) |
| CL-17 | README "What it is not: ... does not contain a real VLM runner yet" | `vlm_ollama.py` exists and was used | Contradicted (stale) |
| CL-18 | README "Not done: ... a calibrated judge" | Jev extension built and reported | Contradicted (stale) |
| CL-19 | README "21 tests" in RESULTS.md "Verified" says 21 and notes now 54 | Noted in the file itself | Supported |

## E4 Rule attacks (scratch copy, `probe.py`)

Gate: exact floor 0.8 accepted; string "0.95" accepted (pydantic lax coercion); `true` accepted as 1.0; NaN, 1.5, extra key, 2-letter rationale, lowercase label, JSON list, empty string, code-fenced JSON: all REJECT_SCHEMA; CLOUD_ARTIFACT at 1.0 REJECT_NOT_ACTIONABLE. Screen: flat scene gives no candidates; different shapes raise ValueError; all-NaN scene gives zero candidates with no error (NaN comparisons are false). The loader's co-registration check (CRS, transform, shape) was read, not run (needs rasterio and a GeoTIFF).

## E5 Code map

`src/geo_eval_gate/`: `scene.py` (Scene dataclass, coregistration check), `screening.py` (ndvi, cloud_mask, ssim_map, compute_maps, screen_from_maps, crop), `gate.py` (schema, evaluate, ScriptedVLM), `io.py` (GeoTIFF load), `synthetic.py` (make_pair), `scoring.py` (pixel metrics, label_candidates, object_recall, ECE, gate_score, auroc, bootstrap_ci), `candidate_set.py` (records, stretch_pair, context crops, seeded cap of 400), `oscd.py` (parquet loader), `vlm_ollama.py` (OllamaVLM, SYSTEM prompt, schema), `jev.py` (JevJudge client, retries, key handling). Entry points: `examples/demo.py`, `scripts/benchmark.py`, `scripts/real_*.py`, `run_dev_gate.sh`, `run_test_gate.sh`. Settings: pyproject (extras geo, real, vlm, dev). Tuned thresholds: results/real/frozen_screen.json (design: NDVI 0.3, SSIM 0.7, min area 50; RGB: 0.05, 25).

## E6 Model call sites

| Model | Where | Settings | Cost | Notes |
| --- | --- | --- | --- | --- |
| gemma4:12b via Ollama (localhost:11434) | `OllamaVLM.classify`, `scripts/real_gate.py` | temperature 0, seed 0, num_predict 200, JSON-schema format, `think: false`, image = BEFORE\|AFTER PNG 256 px tiles | Local, no fee; mean latency 2.1 s (design) and 2.4 s (RGB) per candidate | No model digest recorded; replies cached in results/real/gate/*.jsonl |
| qwen2.5vl:7b via Ollama | same | same | Local; mean latency 3.4 s (design) | Same |
| TypeSafe Jev (`jev-latest`, POST api.typesafe.ai/v1/systemone, question type `noul`) | `jev.py`, `scripts/real_jev.py` | one fixed instruction; 4 retries with backoff; budget stop at $1 | $0.042 per million input tokens (code constant), about 440 input tokens per call, about 0.2-0.26 s per call | Key from `TYPESAFE_AI_API_KEY` env or git-ignored `.env`; never read by this run; vendor terms forbid distillation (code comment cites section 2.3(b)) |

Vendor and family attributions in the Explainer (Google for Gemma, Alibaba for Qwen) come from general knowledge, not from the repository: My reading.

## E7 Tests and CI

54 tests: test_geo 12 defs (parametrised gate cases, property tests), test_scoring 10, test_candidate_set 5, test_vlm_ollama 5 (fake HTTP server), test_jev 7, test_no_secrets 3. Spot checks: (1) `test_gate_decisions` asserts ten exact reply-to-decision cases (real behaviour); (2) `test_gate_never_accepts_unvalidated_text` uses random text, which almost never reaches ACCEPT, so its assertion is weak; (3) `test_request_carries_image_schema_and_greedy_options` checks the request body the fake server received (real behaviour, no model). Tests for the study scripts: none. Coverage not measured. CI (.github/workflows/ci.yml): checkout, Python 3.12, `pip install -e ".[dev]"`, `mypy src tests`, `pytest -q`. No ruff, no coverage, no quality gate, no branch protection checked. Dependabot monthly for Actions and pip.

## E8 Plan-versus-results and history

Commit times (author time, -0400): scaffold 10-09 16:53; README 10-10 07:52; protocol 10-10 10:28; dev stage 10-10 11:34; freeze 10-11 07:34; test results 10-11 08:56; Jev protocol 10-11 11:30; Jev client and tests 11:39; Jev freeze 12:26; Jev results 12:37; later doc fixes 10-11 to 10-13. Push times not checked (event feed limit). Deviations are listed in docs with what had been seen: RGB screen added after dev results; Gemma thinking off; runner robustness; no Qwen prompt change; floors meaningless; pair-level bootstrap added after test results; Jev: fair calibration comparison added after test results. Credits: two AI assistant models (see E1). Several commits are large result-file drops (results JSONL), so step-by-step history is partly unrecoverable. My reading.

## E9 Gates and approvals

No gate-engine or approval records in this repository. The "gate" is the runtime evaluator gate. No approver identity to check.

## E10 Environment

Installed (scratch): numpy 2.5.4, scipy 1.18.1, pydantic 2.14.1, Python 3.14.6. Declared: lower bounds only; no lockfile. Results files do not record package versions or Ollama model digests. `vlm` extra (transformers, torch) is not imported anywhere in src, scripts or tests (grep). My reading: a fresh install should reproduce the deterministic screen; model replies depend on the Ollama model build.

## E11 Security and privacy

Secret scan: regex over HEAD for `sk-` style keys and `api_key = "..."` found nothing; no `.env` in any commit (ls-tree over all commits); `.gitignore` ignores `.env` and `.env.*`; tests guard it. Outside services: Ollama on localhost; Jev over HTTPS (only derived numbers and model text sent, per docs, not imagery). Data licence: OSCD licence unknown; not redistributed. Key handling in `jev.py` avoids logging the key (tests check). No GitHub security settings checked.

## E12 Shortcomings register

| ID | Shortcoming | Evidence | Severity | Disclosed? | Options and recommendation |
| --- | --- | --- | --- | --- | --- |
| S1 | Screen finds only about 39% of labelled objects; design not better than plain RGB difference | RESULTS_REAL | High | Yes | A) trained outlining model (large effort, high payoff, adds dependency); B) tune the plain screen (small); C) keep as cheap filter and document. Recommend A or B, test on more imagery first |
| S2 | Confidence floor does nothing for the tested models | RESULTS_REAL, Gemma 3 values | Medium | Yes | A) drop floor from claims; B) calibrated layer (Jev or stacked regression); C) rank-based cut. Recommend B with labelled data |
| S3 | Reply check accepts text "0.95" and `true` | E4 probe | Low | No | A) strict mode in the model; B) leave. Recommend A (small) |
| S4 | All-NaN input gives zero boxes silently | E4 probe | Low | No | Add a validity check |
| S5 | README stale (CL-17, CL-18); RESULTS.md scope text; unused `vlm` extra | E3, E10 | Low | No | Edit docs and pyproject |
| S6 | CI runs no ruff and no quality gate | ci.yml | Medium | No | Add ruff and a synthetic-benchmark regression check |
| S7 | No decision log saved by the program | code | Medium | No | Write each decision and reason to a file |
| S8 | Versions unpinned; no model digests | E10 | Medium | No | Lockfile; record model digests in result files |
| S9 | Only 10 test pairs, one prompt, two models | docs | High | Yes | More pairs or datasets; prompt study |
| S10 | Tuned thresholds sit at the edge of the search grids (NDVI 0.30, SSIM 0.7, area 50 for the design) | frozen_screen.json vs PROTOCOL grid | Medium | No | Widen grid on development data only |
| S11 | Study scripts have no tests | tests/ | Medium | No | Add small fixtures |

## E13 Math and method detail

NDVI = (NIR - R) / (NIR + R + 1e-9). SSIM map: uniform 7x7 window means, c1 = (0.01 L)^2, c2 = (0.03 L)^2, computed on NIR+red with data range 2.0; the screen uses 1 - SSIM. Change pixel: |dNDVI| > t_ndvi OR (1 - SSIM) > t_ssim (defaults 0.25 and 0.5; tuned 0.3 and 0.7 for the design). Cloud mask: mean(RGB) > 0.75 and (max - min of RGB) < 0.08, dilated 6 px, in either date. Clean-up: binary opening 1, closing 2, min area 25 by default. Candidate label: positive if at least 30% of pixels inside the human mask. Object found: at least 30% of object pixels inside the predicted mask, objects of at least 4 px. ECE: 10 equal-width bins, weighted mean |accuracy - confidence|; for Gemma and Qwen "correct" means accepted-and-positive. Jev "implied probability" for Gemma: confidence if actionable class else 1 - confidence. AUROC via rank statistic. Bootstrap: percentile, resampling the 10 pairs 2,000 times (pair-level). My toy NDVI example in the Explainer uses invented readings (labelled toy).

## E14 Discrepancies

README says 54 tests (true only in a git checkout); "no real VLM runner" and "calibrated judge not done" are stale; README says CI-like verify path runs `mypy src tests scripts` while CI runs `mypy src tests`; RESULTS.md says 21 tests when written (notes it is now 54); gate JSON at floor 0.8 shows Qwen design accepted 385 (precision 0.434) while RESULTS_REAL reports 393 (0.425) at the frozen floor (explained by different floors, not re-derived); the Jev results note an unfair stored `ece_stated_confidence` value left in JSON.

## E15 Production readiness

Placement: Works locally. Traits: runs from clean start Yes (documented, versions unpinned: Partly); checks block a bad change Partly (tests and types only); quality measured against goal and baseline Yes (study); safe on failure Partly (retries, cool-down pause, first-failure stop, stateless; no cost cap except the Jev $1 stop); human review Not applicable/No; prompts versioned Partly (in git, frozen, no model digest); logs No (only saved replies); data and secrets Yes (guard test, git-ignored env, no imagery sent out). Gap: hosting, service wrapper, auth, monitoring, rollback, pinned versions, licence review, runbook.

## E16 Review dispositions

Self-review pass applied to the draft: removed an unsupported claim about agent claims; corrected the Jev expectation count; removed a stale-scope complaint about RESULTS.md; reworded the rules paragraph. No outside review run.

## E17 Completeness and backlog

Promised versus built: screen (done, tested); gate (done, tested); loader (done, untested by test data; needs rasterio); OSCD loader and scoring (done; scripts untested); Ollama runner (done, fake-server tests); Jev client (done, fake-server tests); synthetic benchmark (done); real study (done, results committed); Jev extension (done). Planned only: segmentation models, Florence-2 patch verifier, imagery download clients, other sensors, end-to-end recall. Backlog. Finish: README and pyproject fixes. Fix: strict reply typing, NaN guard. Improve: CI quality check, pin versions, record model digests, prompt study, widen grids. Add: decision log, stronger screen, more imagery, service wrapper. Order: (1) docs and CI fixes (small); (2) stronger screen and more imagery (large); (3) deployment steps. Earlier judgement (polish and freeze) was withdrawn from the guide after the author's answers; no recommendation is made for him there.

Image diagram sources: matplotlib script (boxes and bars) kept outside the repository; chart numbers come from RESULTS_REAL (precision, recall kept) and RESULTS_JEV (calibration bins; Gemma implied probability bin 0.80 to 1.00: 0.96 stated, 0.66 actual design, 0.52 RGB; Jev arm B top bin design 0.84 stated, 0.60 actual).

---

## Revision log (v1 draft to current)

The previous text is kept as `geo-eval-gate.v1draft.md`. All ten fixes in `geo-eval-gate.readercheck.md` were applied. Word count by plain `wc -w`: v1 7,046; current 5,972 (target 5,800 to 6,200; cap 8,000).

| Fix | What changed |
| --- | --- |
| 1. Precision before headline | Opening now defines precision and recall in plain words (10 accepted, 6 real = 0.6) before any headline number; 42% base rate stated, then 0.67 and 70%. |
| 2. Determinism paragraph | Split into short pieces; seed and 95% range defined in a clause where first used. |
| 3. Model names | Gemma 4 12B and Qwen2.5-VL 7B explained once at first use (free downloadable models; 12B and 7B are billions of adjustable numbers). |
| 4. Jev | Models chapter shortened; Jev is three short paragraphs (what it is, why tested, what it cost); per-token price and detailed terms cut; the project records no expansion of the name Jev, stated. |
| 5. Toy examples | NDVI example cut to one sentence with made-up readings; one worked precision case (real: 179 accepted, 119 real). Formula paragraph removed. |
| 6. Test jargon | Property tests, type checker, CI, style checker, parameterized test, Dependabot replaced by plain wording or a one-clause definition; weak-spot list kept (strings "0.95" accepted, all-missing photo silent). |
| 7. Results | Opens with a three-part plain summary; AUROC and ECE values moved to one "for the curious" paragraph; fewer ranges. |
| 8. Glossary | Now includes precision/recall/F1, baseline, held-out, seed, 95% range, calibrated and Jev; GPU, Sentinel-2, Hugging Face, Docker, Ollama defined at first use; tokens dropped. |
| 9. Q&A | The ten candidate answers removed; the five tough questions kept. "In short" lines kept in three chapters. |
| 10. Softened claims | "Demonstrated" replaced by "Reasonable evidence, on 10 pairs" and "Format and label checks worked; the confidence control failed"; "well tested and hard to break" replaced by "held up against the cases I tried"; "usable probability" replaced by "better-behaved number" (calibration gap 0.12 to 0.17 still above the 0.10 bar). Four outcomes versus three checks reconciled in one sentence. |

Image regenerated with a script kept outside the repo: `geo-eval-gate-learned-vs-rules.png` (seed and 95% range wording made plain; boxes enlarged so no text is clipped; viewed after rendering). The parts, gate-results and calibration images are unchanged because their numbers and labels did not change (0.42/0.67/0.43, 0.35/0.52/0.36; 70, 67, 99, 98; 0.96/0.66, 0.96/0.52, 0.84/0.60).

Not re-verified: no study was re-run; numbers carried over from v1 and the committed result files. Removed from the text: the Jev unit price (a claim not checked against an invoice anyway) and the 400-box detail "out of about 740 and 1,040".


## Author answers folded in, 2026-11-05

Source: answers appended to the 19 questions in geo-eval-gate.questions.md. Label: Author says. Clone pulled to HEAD 48f915f (18 commits). Guide edited; no repository change.

- Q1: Built because it fits his portfolio and interests; satellite change detection chosen for that reason. Stated in the problem chapter.
- Q2: Does not recall where the original roadmap item file is; maybe the top level of the directory the repos sit in. Check (read-only) of that top level: `ai_engineering_project_roadmap_execution_template.md` (dated 9 Oct 2026, 15:57, before the first commit) has section "1. Evaluator-Gated Geospatial Change Detection" matching the README's description (NDVI + SSIM screen, VLM gate, labels EARTHWORKS / NEW_STRUCTURE / ROAD_EXPANSION / SEASONAL_DEFOLIATION / CLOUD_ARTIFACT, SAM 2 or Prithvi, Qwen2.5-VL-7B or Florence-2, Sentinel-2 or NAIP). Likely the source; the author has not confirmed it. Guide says only that he does not recall where the file is; no path quoted.
- Q3: Probably nobody besides him is meant to use it, nobody has tried it ("probably not"). Stated as his answer.
- Q4: Defense-interest sentence kept as is.
- Q5: The two commit credits are "the full picture, I think". Guide says 'AI coding agents' and 'two AI assistant models'; no model named as build tool.
- Q6: Gemma 4 12B and Qwen2.5-VL 7B chosen because inexpensive and locally hosted, "I think". Stated with that hedge next to the protocol's reason.
- Q7: Drawn to Jev by a novel idea he wanted to test and learn more about. Whether he paid from his own account: not answered; guide says so.
- Q8: He thinks the makers are Google (Gemma) and Alibaba (Qwen). Not confirmed from official sources: web search returned only third-party pages (Roboflow, aggregators), consistent with Google DeepMind and Alibaba's Qwen team, and no official model card was reached. Stays 'My reading' (E6).
- Q9 finding: The protocol and results documents use first-person statements. PROTOCOL_JEV.md line 19 ("so I know the vision models' test behaviour"), line 56 section "My expectation, written down so it can be wrong", line 58 ("I expect Jev to be well calibrated..."), and RESULTS_JEV.md lines 45 and 68 ("I expected C1 met", "I did not exploit that") read as his own. By his answer the agents drafted them and he approved or edited them. The repository's first-person wording therefore differs from how they were written; no blame. Guide rewritten where it implied he wrote or decided (including "I directed", "the design I planned", "the bar I had set") and states the finding in the study-design section.
- Q10: Real imagery, failure criteria, plain RGB screen, Jev extension were agent suggestions he approved or adapted. Guide credits no decision to him alone.
- Q11: Overrode or caught an agent "sometimes"; no case remembered. Stated.
- Q12: Does not recall whether he ran the real-data study himself or how long runs took. Stated as not recalled; the repository does not record who ran it.
- Q13: Needs to refresh his memory of NDVI, SSIM, calibration and the bootstrap. Stated.
- Q14: Does not recall what surprised him. Stated.
- Q15: Unsure what was hardest. Stated.
- Q16: Probably still needs some work and improvements. The guide's 'polish and freeze' suggestion removed; his answer stated.
- Q17: Time is not an issue; goal is the best project it can be; backlog choices not made. Stated.
- Q18: Wants the stale README lines (no real VLM runner, calibrated judge not done) corrected in the repository; README lines 33 and 217 still stale at 48f915f. Stated as his wish; repository not changed.
- Q19: The earlier explainer was to be replaced or updated by this one. Repository check: `geo-eval-gate_MASTER_EXPLAINER.md` was added in 71455a0 (2026-10-19) and replaced in 48f915f (2026-10-27, "Replace master explainer with plain-language narrative version", with evidence notes and four images). Stated plainly in the guide.
