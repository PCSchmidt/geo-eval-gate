from __future__ import annotations

import json
import threading
import time
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import pytest

from geo_eval_gate import jev
from geo_eval_gate.jev import JevError, JevJudge, api_key, read_dotenv

SEEN: list[dict[str, Any]] = []
HEADERS: list[str] = []
MODE: dict[str, Any] = {"fail_first": 0, "status": 200, "body": None}
FAKE_KEY = "test-key-not-a-real-credential-0123456789"


class Fake(BaseHTTPRequestHandler):
    def log_message(self, *args: Any) -> None:
        pass

    def do_POST(self) -> None:
        SEEN.append(json.loads(self.rfile.read(int(self.headers["Content-Length"]))))
        HEADERS.append(self.headers.get("Authorization", ""))
        if MODE["fail_first"] > 0:
            MODE["fail_first"] -= 1
            self.send_response(503)
            self.end_headers()
            return
        body = MODE["body"] or {"answers": {"q0": {"noul": 0.83}}, "usage": {"input_tokens": 120, "output_tokens": 0}}
        self.send_response(int(MODE["status"]))
        self.end_headers()
        self.wfile.write(json.dumps(body).encode())


@pytest.fixture(scope="module")
def url() -> Iterator[str]:
    httpd = HTTPServer(("127.0.0.1", 0), Fake)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()


@pytest.fixture(autouse=True)
def reset() -> None:
    SEEN.clear()
    HEADERS.clear()
    MODE.update(fail_first=0, status=200, body=None)


def test_request_shape_and_answer(url: str) -> None:
    j = JevJudge("Is it real?", url=url, key=FAKE_KEY)
    a = j.ask("some state")
    assert a.p_yes == pytest.approx(0.83) and a.input_tokens == 120 and a.latency_s >= 0
    assert SEEN[0]["state"] == "some state" and SEEN[0]["questions"]["q0"] == {"type": "noul", "instructions": "Is it real?"}
    assert HEADERS[0] == f"Bearer {FAKE_KEY}"
    assert j.calls == 1 and j.cost_usd == pytest.approx(120 * 0.042 / 1_000_000)


def test_retries_transient_errors_then_succeeds(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda s: None)
    MODE["fail_first"] = 2
    assert JevJudge("q", url=url, key=FAKE_KEY).ask("s").p_yes == pytest.approx(0.83)
    assert len(SEEN) == 3


def test_gives_up_after_retries_without_leaking_the_key(url: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda s: None)
    MODE["fail_first"] = 99
    with pytest.raises(JevError) as ei:
        JevJudge("q", url=url, key=FAKE_KEY, retries=3).ask("s")
    assert FAKE_KEY not in str(ei.value) and "Bearer" not in str(ei.value)


@pytest.mark.parametrize(
    "body",
    [{"answers": {}}, {"answers": {"q0": {"noul": "high"}}}, {"answers": {"q0": {"noul": 1.4}}}, {"nope": 1}],
)
def test_malformed_or_out_of_range_replies_are_errors(url: str, body: dict[str, Any]) -> None:
    MODE["body"] = body
    with pytest.raises(JevError):
        JevJudge("q", url=url, key=FAKE_KEY).ask("s")


def test_client_error_is_not_retried(url: str) -> None:
    MODE["status"] = 401
    with pytest.raises(JevError) as ei:
        JevJudge("q", url=url, key=FAKE_KEY).ask("s")
    assert "401" in str(ei.value) and FAKE_KEY not in str(ei.value) and len(SEEN) == 1


def test_dotenv_parsing(tmp_path: Path) -> None:
    f = tmp_path / ".env"
    f.write_text("# comment\n\nA=1\nTYPESAFE_AI_API_KEY = \"quoted-value\"\nB='x'\nnoequals\n", encoding="utf-8")
    d = read_dotenv(f)
    assert d == {"A": "1", "TYPESAFE_AI_API_KEY": "quoted-value", "B": "x"}
    assert read_dotenv(tmp_path / "missing") == {}


def test_api_key_prefers_environment_then_file_and_errors_clearly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    f = tmp_path / ".env"
    f.write_text("TYPESAFE_AI_API" + "_KEY=from-file\n", encoding="utf-8")
    monkeypatch.delenv("TYPESAFE_AI_API_KEY", raising=False)
    assert api_key(f) == "from-file"
    monkeypatch.setenv("TYPESAFE_AI_API_KEY", "from-env")
    assert api_key(f) == "from-env"
    monkeypatch.delenv("TYPESAFE_AI_API_KEY")
    monkeypatch.setattr(jev, "__file__", str(tmp_path / "a" / "b" / "jev.py"))
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").unlink()
    with pytest.raises(RuntimeError, match="not set"):
        api_key(None)
