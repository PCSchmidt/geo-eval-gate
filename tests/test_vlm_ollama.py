from __future__ import annotations

import base64
import io
import json
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import numpy as np
import pytest
from PIL import Image

from geo_eval_gate import Decision, evaluate
from geo_eval_gate.vlm_ollama import SCHEMA, OllamaVLM, side_by_side

REQUESTS: list[dict[str, Any]] = []
REPLY = {"confidence": 0.9, "change_class": "NEW_STRUCTURE", "rationale": "A new rectangular roof appears."}


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        REQUESTS.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        body = json.dumps({"message": {"content": json.dumps(REPLY)}}).encode()
        self.send_response(200)
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def server() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


def tile(v: int, n: int = 20) -> np.ndarray:
    return np.full((n, n, 3), v, dtype=np.uint8)


def test_side_by_side_is_one_png_with_both_tiles() -> None:
    png = side_by_side(tile(0), tile(255), size=64)
    im = Image.open(io.BytesIO(png))
    assert im.size == (64 * 2 + 8, 64)


def test_request_carries_image_schema_and_greedy_options(server: str) -> None:
    REQUESTS.clear()
    vlm = OllamaVLM("fake-vlm", host=server)
    raw = vlm.classify(tile(10), tile(200))
    body = REQUESTS[0]
    assert body["format"] == SCHEMA and body["options"]["temperature"] == 0 and body["stream"] is False
    img = Image.open(io.BytesIO(base64.b64decode(body["messages"][1]["images"][0])))
    assert img.size[0] > img.size[1]  # two tiles side by side
    assert json.loads(raw) == REPLY and len(vlm.latencies_s) == 1


def test_unconstrained_mode_omits_the_schema(server: str) -> None:
    REQUESTS.clear()
    OllamaVLM("fake-vlm", host=server, constrained=False).classify(tile(1), tile(2))
    assert "format" not in REQUESTS[0]


def test_reply_flows_through_the_gate(server: str) -> None:
    out = evaluate(OllamaVLM("fake-vlm", host=server), tile(1), tile(2), min_confidence=0.8)
    assert out.decision is Decision.ACCEPT
    assert evaluate(OllamaVLM("fake-vlm", host=server), tile(1), tile(2), min_confidence=0.95).decision is (
        Decision.REJECT_LOW_CONFIDENCE
    )
