from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
from typing import Literal

LogKind = Literal["python_traceback", "generic_log", "unknown"]
ChainReason = Literal["cause", "context"]

SUMMARY_MAX_CHARS = 200
FIX_STEPS_MIN = 1
FIX_STEPS_MAX = 6


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True)
class RawLog:
    text: str


@dataclass(frozen=True)
class RedactedLog:
    text: str
    redaction_count: int


@dataclass(frozen=True)
class Frame:
    file: str
    line: int
    func: str
    code: str | None
    is_user_code: bool


@dataclass(frozen=True)
class ExceptionBlock:
    type: str
    message: str
    frames: tuple[Frame, ...]
    chain_reason: ChainReason | None


@dataclass(frozen=True)
class ParsedLog:
    kind: LogKind
    exceptions: tuple[ExceptionBlock, ...]
    root_cause_index: int | None
    culprit: Frame | None
    log_levels: Mapping[str, int] = field(default_factory=dict)
    truncated: bool = False


@dataclass(frozen=True)
class Fix:
    steps: tuple[str, ...]
    code_snippet: str | None
    language: str | None

    def __post_init__(self) -> None:
        if not FIX_STEPS_MIN <= len(self.steps) <= FIX_STEPS_MAX:
            raise ValueError(f"a fix has {FIX_STEPS_MIN} to {FIX_STEPS_MAX} steps")


@dataclass(frozen=True)
class CulpritRef:
    file: str
    line: int
    func: str


@dataclass(frozen=True)
class Diagnosis:
    summary: str
    likely_cause: str
    confidence: Confidence
    explanation: str
    culprit: CulpritRef | None
    fix: Fix
    alternative_causes: tuple[str, ...]
    follow_up_checks: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.summary) > SUMMARY_MAX_CHARS:
            raise ValueError(f"a summary has at most {SUMMARY_MAX_CHARS} characters")
