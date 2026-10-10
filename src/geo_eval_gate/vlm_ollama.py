"""A VLMRunner backed by a local Ollama vision model (localhost only; imagery never leaves the machine).

The reply is returned as raw text and treated as untrusted: `gate.evaluate` is what decides.
"""

from __future__ import annotations

import base64
import io
import json
import time
import urllib.request
from typing import Any

import numpy as np
import numpy.typing as npt
from PIL import Image, ImageDraw

from .gate import ChangeClass, ChangeVerificationResult

SYSTEM = (
    "You are an imagery analyst. You are shown two satellite crops of the same place: BEFORE on the left and "
    "AFTER on the right. The pixels are about 10 metres, so objects look coarse and blurry. Classify what, "
    "if anything, changed between them. Only call something a NEW_STRUCTURE, ROAD_EXPANSION or EARTHWORKS if "
    "you can see human construction that is present in AFTER and absent in BEFORE. Colour changes of fields "
    "and trees are SEASONAL_DEFOLIATION. Bright white or grey patches are CLOUD_ARTIFACT. "
    "Answer with JSON only."
)
CLASSES = [c.value for c in ChangeClass]
SCHEMA: dict[str, Any] = ChangeVerificationResult.model_json_schema()


def side_by_side(before: npt.NDArray[np.uint8], after: npt.NDArray[np.uint8], size: int = 256) -> bytes:
    """One PNG: BEFORE | AFTER, each resized to `size` pixels square, with captions."""
    tiles = []
    for name, arr in (("BEFORE", before), ("AFTER", after)):
        im = Image.fromarray(arr).convert("RGB").resize((size, size), Image.Resampling.BICUBIC)
        ImageDraw.Draw(im).text((6, 4), name, fill=(255, 255, 0))
        tiles.append(im)
    canvas = Image.new("RGB", (size * 2 + 8, size), (0, 0, 0))
    canvas.paste(tiles[0], (0, 0))
    canvas.paste(tiles[1], (size + 8, 0))
    buf = io.BytesIO()
    canvas.save(buf, format="PNG")
    return buf.getvalue()


class OllamaVLM:
    def __init__(
        self,
        model: str,
        host: str = "http://127.0.0.1:11434",
        constrained: bool = True,
        timeout_s: float = 300.0,
        tile: int = 256,
    ) -> None:
        self.name = model
        self._model, self._host = model, host.rstrip("/")
        self._constrained, self._timeout, self._tile = constrained, timeout_s, tile
        self.latencies_s: list[float] = []

    def classify(self, before: npt.NDArray[np.uint8], after: npt.NDArray[np.uint8]) -> str:
        user = (
            "Classes: " + ", ".join(CLASSES) + ". Return {\"confidence\": <0 to 1, how sure you are>, "
            "\"change_class\": <one class>, \"rationale\": <one sentence>}."
        )
        body: dict[str, Any] = {
            "model": self._model,
            "stream": False,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {
                    "role": "user",
                    "content": user,
                    "images": [base64.b64encode(side_by_side(before, after, self._tile)).decode()],
                },
            ],
            "options": {"temperature": 0, "seed": 0, "num_predict": 200},
            "keep_alive": "20m",
        }
        if self._constrained:
            body["format"] = SCHEMA
        req = urllib.request.Request(
            self._host + "/api/chat", data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
        )
        start = time.perf_counter()
        with urllib.request.urlopen(req, timeout=self._timeout) as resp:
            reply = json.load(resp)
        self.latencies_s.append(time.perf_counter() - start)
        return str(reply.get("message", {}).get("content", ""))
