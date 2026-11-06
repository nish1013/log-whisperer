"""Grounding: a diagnosis cites only files, lines and functions found in the analysed log."""

import re
from dataclasses import dataclass, replace

from log_whisperer.domain.model import (
    Confidence,
    CulpritRef,
    Diagnosis,
    Fix,
    LogKind,
    RedactedLog,
)

FALLBACK_STEP = "Review the frames shown in the traceback before changing code."

_PATH = re.compile(
    r"(?<![\w/.\-])/?(?:[\w.\-]+/)+[\w\-]+\.[A-Za-z]{1,8}\b|(?<![\w/.\-])[\w\-]+\.py\b"
)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass(frozen=True)
class GroundingResult:
    diagnosis: Diagnosis
    stripped: int


def enforce(diagnosis: Diagnosis, log: RedactedLog, kind: LogKind) -> GroundingResult:
    text = log.text
    stripped = 0
    culprit = diagnosis.culprit
    confidence = diagnosis.confidence
    if culprit is not None and not _culprit_grounded(culprit, text):
        culprit = None
        confidence = Confidence.LOW
        stripped += 1
    likely_cause, removed_cause = _ground_prose(diagnosis.likely_cause, text)
    explanation, removed_explanation = _ground_prose(diagnosis.explanation, text)
    steps, removed_steps = _ground_steps(diagnosis.fix.steps, text)
    stripped += removed_cause + removed_explanation + removed_steps
    if kind != "python_traceback":
        confidence = Confidence.LOW
    grounded = replace(
        diagnosis,
        likely_cause=likely_cause,
        explanation=explanation,
        culprit=culprit,
        confidence=confidence,
        fix=Fix(steps, diagnosis.fix.code_snippet, diagnosis.fix.language),
    )
    return GroundingResult(grounded, stripped)


def ungrounded_paths(diagnosis: Diagnosis, log: RedactedLog) -> list[str]:
    """Paths the diagnosis cites that the log does not contain. Used by the eval."""
    fields = [diagnosis.likely_cause, diagnosis.explanation, *diagnosis.fix.steps]
    if diagnosis.culprit is not None:
        fields.append(diagnosis.culprit.file)
    return [path for field in fields for path in _paths(field) if path not in log.text]


def _culprit_grounded(culprit: CulpritRef, text: str) -> bool:
    if not culprit.file or culprit.file not in text or culprit.func not in text:
        return False
    return (
        f'{culprit.file}", line {culprit.line}' in text or f"{culprit.file}:{culprit.line}" in text
    )


def _ground_prose(prose: str, text: str) -> tuple[str, int]:
    sentences = [s for s in _SENTENCE_END.split(prose.strip()) if s]
    kept = [s for s in sentences if all(path in text for path in _paths(s))]
    return " ".join(kept), len(sentences) - len(kept)


def _ground_steps(steps: tuple[str, ...], text: str) -> tuple[tuple[str, ...], int]:
    kept: list[str] = []
    removed = 0
    for step in steps:
        grounded, dropped = _ground_prose(step, text)
        removed += dropped
        if grounded:
            kept.append(grounded)
    return tuple(kept) or (FALLBACK_STEP,), removed


def _paths(prose: str) -> list[str]:
    return [match.group(0) for match in _PATH.finditer(prose)]
