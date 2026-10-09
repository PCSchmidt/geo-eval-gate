"""Evaluator gate: a VLM may *propose* a label; only schema-valid, confident, actionable ones pass."""

from __future__ import annotations

import json
from enum import Enum
from typing import Protocol

import numpy as np
import numpy.typing as npt
from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ChangeClass(str, Enum):
    EARTHWORKS = "EARTHWORKS"
    NEW_STRUCTURE = "NEW_STRUCTURE"
    ROAD_EXPANSION = "ROAD_EXPANSION"
    SEASONAL_DEFOLIATION = "SEASONAL_DEFOLIATION"
    CLOUD_ARTIFACT = "CLOUD_ARTIFACT"


ACTIONABLE = frozenset({ChangeClass.EARTHWORKS, ChangeClass.NEW_STRUCTURE, ChangeClass.ROAD_EXPANSION})


class ChangeVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    confidence: float = Field(ge=0.0, le=1.0)
    change_class: ChangeClass
    rationale: str = Field(min_length=10, max_length=600)


class Decision(str, Enum):
    ACCEPT = "ACCEPT"
    REJECT_SCHEMA = "REJECT_SCHEMA"
    REJECT_LOW_CONFIDENCE = "REJECT_LOW_CONFIDENCE"
    REJECT_NOT_ACTIONABLE = "REJECT_NOT_ACTIONABLE"


class GateOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: Decision
    result: ChangeVerificationResult | None = None
    detail: str = ""


class VLMRunner(Protocol):
    name: str

    def classify(self, before: npt.NDArray[np.uint8], after: npt.NDArray[np.uint8]) -> str:
        """Return the model's raw text. The gate treats it as untrusted."""
        ...


def evaluate(
    runner: VLMRunner,
    before: npt.NDArray[np.uint8],
    after: npt.NDArray[np.uint8],
    min_confidence: float = 0.8,
) -> GateOutcome:
    raw = runner.classify(before, after)
    try:
        result = ChangeVerificationResult.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError) as exc:
        return GateOutcome(decision=Decision.REJECT_SCHEMA, detail=str(exc).splitlines()[0])
    if result.confidence < min_confidence:
        return GateOutcome(
            decision=Decision.REJECT_LOW_CONFIDENCE,
            result=result,
            detail=f"{result.confidence:.2f} < {min_confidence:.2f}",
        )
    if result.change_class not in ACTIONABLE:
        return GateOutcome(decision=Decision.REJECT_NOT_ACTIONABLE, result=result)
    return GateOutcome(decision=Decision.ACCEPT, result=result)


class ScriptedVLM:
    """Test double returning fixed text. Not a model; never use it to report accuracy."""

    name = "scripted"

    def __init__(self, text: str) -> None:
        self.text = text

    def classify(self, before: npt.NDArray[np.uint8], after: npt.NDArray[np.uint8]) -> str:
        return self.text
