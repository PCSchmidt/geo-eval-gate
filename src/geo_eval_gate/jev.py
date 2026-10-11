"""Client for TypeSafe Jev, a text-only 'System One' model that returns calibrated yes/no probabilities.

API (same call VERA uses): POST https://api.typesafe.ai/v1/systemone with a text `state` and typed
`questions`; a `noul` question returns p(yes). Auth is a bearer key in TYPESAFE_AI_API_KEY, read from the
environment or from a git-ignored `.env`. The key is never logged, printed, or put in an exception message.

Terms (typesafe.ai/legal/mca, section 2.3(b)): Jev's output must not be used to distil or train a model.
Here it is only thresholded and measured.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

API = "https://api.typesafe.ai/v1/systemone"
KEY_VAR = "TYPESAFE_AI_API_KEY"
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000  # USD, as published by TypeSafe (output tokens are free)


def read_dotenv(path: Path) -> dict[str, str]:
    """Minimal KEY=VALUE parser: comments and blank lines ignored, optional surrounding quotes stripped."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        out[name.strip()] = value.strip().strip('"').strip("'")
    return out


def api_key(env_file: Path | None = None) -> str:
    """The key from the environment, else from `.env` (repo root, then the working directory)."""
    key = os.environ.get(KEY_VAR, "").strip()
    if not key:
        for candidate in [env_file, Path(__file__).resolve().parents[2] / ".env", Path.cwd() / ".env"]:
            if candidate and (key := read_dotenv(candidate).get(KEY_VAR, "").strip()):
                break
    if not key:
        raise RuntimeError(f"{KEY_VAR} is not set (put it in .env or the environment)")
    return key


@dataclass(frozen=True)
class JevAnswer:
    p_yes: float
    input_tokens: int
    latency_s: float


class JevError(RuntimeError):
    """A failed or malformed Jev call. The message never contains the key or request headers."""


class JevJudge:
    def __init__(
        self,
        instruction: str,
        *,
        model: str = "jev-latest",
        url: str = API,
        key: str | None = None,
        timeout_s: float = 60.0,
        retries: int = 4,
    ) -> None:
        self.instruction, self.model, self.url = instruction, model, url
        self._key = key or api_key()
        self._timeout, self._retries = timeout_s, retries
        self.calls = 0
        self.input_tokens = 0

    @property
    def cost_usd(self) -> float:
        return self.input_tokens * PRICE_PER_INPUT_TOKEN

    def ask(self, state: str) -> JevAnswer:
        body = {
            "state": state,
            "model": self.model,
            "questions": {"q0": {"type": "noul", "instructions": self.instruction}},
        }
        data = json.dumps(body).encode()
        last = "unknown error"
        for attempt in range(1, self._retries + 1):
            req = urllib.request.Request(
                self.url, data=data, headers={"Content-Type": "application/json", "Authorization": f"Bearer {self._key}"}
            )
            start = time.perf_counter()
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    reply = json.load(resp)
            except urllib.error.HTTPError as exc:
                last = f"HTTP {exc.code}"
                if exc.code not in (408, 429, 500, 502, 503, 504):
                    raise JevError(f"Jev request rejected: {last}") from None
            except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
                last = type(exc).__name__
            else:
                latency = time.perf_counter() - start
                try:
                    p = float(reply["answers"]["q0"]["noul"])
                except (KeyError, TypeError, ValueError):
                    raise JevError("Jev reply did not contain a numeric answer for the question") from None
                if not 0.0 <= p <= 1.0:
                    raise JevError("Jev returned a probability outside [0, 1]")
                tokens = int((reply.get("usage") or {}).get("input_tokens") or 0)
                self.calls += 1
                self.input_tokens += tokens
                return JevAnswer(p, tokens, latency)
            time.sleep(min(30.0, 2.0**attempt))
        raise JevError(f"Jev call failed after {self._retries} attempts ({last})")
