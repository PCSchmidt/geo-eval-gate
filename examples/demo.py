"""Synthetic scene pair -> deterministic screen -> evaluator gate. The VLM is a scripted stand-in."""

from __future__ import annotations

import json

from geo_eval_gate import ScriptedVLM, crop, evaluate, screen
from geo_eval_gate.synthetic import make_pair

REPLIES = {
    "building": {"confidence": 0.93, "change_class": "NEW_STRUCTURE", "rationale": "A new rectangular roof."},
    "unsure": {"confidence": 0.55, "change_class": "EARTHWORKS", "rationale": "Disturbed soil, maybe."},
    "season": {"confidence": 0.97, "change_class": "SEASONAL_DEFOLIATION", "rationale": "Leaf loss only."},
}


def main() -> None:
    pair = make_pair(seed=7, n_buildings=2, n_clouds=1, season=True)
    print(f"injected: {len(pair.true_changes)} buildings, {len(pair.nuisance)} cloud, global autumn decline")
    candidates = screen(pair.t0, pair.t1)
    print(f"deterministic screen: {len(candidates)} candidate boxes (cloud masked, season ignored)")
    for c in candidates:
        print(f"  box x{c.x0}-{c.x1} y{c.y0}-{c.y1}  area {c.area_px}px  dNDVI {c.mean_abs_dndvi:.2f}")
    before, after = crop(pair.t0, candidates[0]), crop(pair.t1, candidates[0])
    print("\nevaluator gate on the first candidate, with different (untrusted) model replies:")
    replies = {k: json.dumps(v) for k, v in REPLIES.items()}
    replies["not json"] = "It looks like a new building to me."
    replies["bad enum"] = json.dumps({**REPLIES["building"], "change_class": "TANK"})
    for name, raw in replies.items():
        out = evaluate(ScriptedVLM(raw), before, after)
        print(f"  {name:<9} -> {out.decision.value:<22} {out.detail}")


if __name__ == "__main__":
    main()
