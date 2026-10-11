"""No API key may ever be committed: `.env` must be ignored and no tracked file may hold a key value.

Skipped when the tests run outside a git checkout (for example inside the Docker image).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# A non-empty value after the variable name. Built from parts so this file never matches itself.
ASSIGNMENT = re.compile("TYPESAFE_AI_API" + r"_KEY\s*=\s*[A-Za-z0-9_\-]{8,}")
GENERIC = {
    "OpenRouter": re.compile("sk-" + r"or-v1-[0-9a-f]{32,}"),
    "Anthropic": re.compile("sk-" + r"ant-[A-Za-z0-9_-]{20,}"),
}


def _git(*args: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)


@pytest.fixture(scope="module")
def tracked() -> list[Path]:
    if _git("rev-parse", "--is-inside-work-tree").returncode != 0:
        pytest.skip("not a git checkout")
    out = _git("ls-files", "-z").stdout.decode("utf-8")
    return [ROOT / p for p in out.split("\0") if p]


def test_env_file_is_ignored(tracked: list[Path]) -> None:
    assert _git("check-ignore", "-q", ".env").returncode == 0


def test_env_file_is_not_tracked(tracked: list[Path]) -> None:
    assert not any(p.name == ".env" for p in tracked)


def test_no_key_value_in_any_tracked_file(tracked: list[Path]) -> None:
    found = []
    for path in tracked:
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", errors="ignore")
        rel = path.relative_to(ROOT).as_posix()
        if ASSIGNMENT.search(text):
            found.append(f"{rel}: Jev key assignment")
        found += [f"{rel}: {name} key" for name, rx in GENERIC.items() if rx.search(text)]
    assert not found, "API key in tracked files: " + "; ".join(found)
