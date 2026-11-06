"""DiagnosisGenerator backed by the Messages API with one strict tool."""

import json
from collections.abc import Callable
from dataclasses import asdict
from typing import Any, Literal

import anthropic
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.model import (
    FIX_STEPS_MAX,
    FIX_STEPS_MIN,
    SUMMARY_MAX_CHARS,
    Confidence,
    CulpritRef,
    Diagnosis,
    Fix,
    ParsedLog,
    RedactedLog,
)

MODEL = "claude-sonnet-5-5"
TOOL_NAME = "report_diagnosis"
MAX_TOKENS = 8000
TIMEOUT_SECONDS = 30.0
ATTEMPTS = 2

SYSTEM_PROMPT = f"""\
You diagnose Python failures from a pasted traceback or log for a backend developer \
during an incident. Call the {TOOL_NAME} tool exactly once and write nothing else.

Rules:
- The user message holds the redacted log and the parser output as JSON. Use the parser \
culprit unless the log clearly contradicts it. If you disagree, say why in explanation.
- Only reference files, line numbers and functions that appear in the log. Never invent a path.
- Set confidence to "low" unless kind is "python_traceback" and the cause is clear.
- summary: one line, at most {SUMMARY_MAX_CHARS} characters, naming the exception type.
- likely_cause and explanation name the exception type.
- fix.steps: {FIX_STEPS_MIN} to {FIX_STEPS_MAX} concrete, code-level steps. code_snippet is \
the corrected code, or null. language is "python" for Python code, else null.
- [REDACTED:...] marks a masked secret. Never try to recover it.
"""


class _Culprit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file: str = Field(min_length=1)
    line: int = Field(ge=1)
    func: str = Field(min_length=1)


class _Fix(BaseModel):
    model_config = ConfigDict(extra="forbid")
    steps: list[str] = Field(min_length=FIX_STEPS_MIN, max_length=FIX_STEPS_MAX)
    code_snippet: str | None
    language: str | None


class DiagnosisPayload(BaseModel):
    """The report_diagnosis tool input. Pydantic checks the limits strict mode drops."""

    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=SUMMARY_MAX_CHARS)
    likely_cause: str
    confidence: Literal["high", "medium", "low"]
    explanation: str
    culprit: _Culprit | None
    fix: _Fix
    alternative_causes: list[str]
    follow_up_checks: list[str]

    def to_domain(self) -> Diagnosis:
        culprit = self.culprit
        return Diagnosis(
            summary=self.summary,
            likely_cause=self.likely_cause,
            confidence=Confidence(self.confidence),
            explanation=self.explanation,
            culprit=None
            if culprit is None
            else CulpritRef(culprit.file, culprit.line, culprit.func),
            fix=Fix(tuple(self.fix.steps), self.fix.code_snippet, self.fix.language),
            alternative_causes=tuple(self.alternative_causes),
            follow_up_checks=tuple(self.follow_up_checks),
        )


_STRING = {"type": "string"}
_NULLABLE_STRING = {"type": ["string", "null"]}
_STRING_LIST = {"type": "array", "items": _STRING}

TOOL: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": "Report the diagnosis of the pasted traceback or log.",
    "strict": True,
    "input_schema": {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary",
            "likely_cause",
            "confidence",
            "explanation",
            "culprit",
            "fix",
            "alternative_causes",
            "follow_up_checks",
        ],
        "properties": {
            "summary": _STRING,
            "likely_cause": _STRING,
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "explanation": _STRING,
            "culprit": {
                "anyOf": [
                    {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["file", "line", "func"],
                        "properties": {
                            "file": _STRING,
                            "line": {"type": "integer"},
                            "func": _STRING,
                        },
                    },
                    {"type": "null"},
                ]
            },
            "fix": {
                "type": "object",
                "additionalProperties": False,
                "required": ["steps", "code_snippet", "language"],
                "properties": {
                    "steps": _STRING_LIST,
                    "code_snippet": _NULLABLE_STRING,
                    "language": _NULLABLE_STRING,
                },
            },
            "alternative_causes": _STRING_LIST,
            "follow_up_checks": _STRING_LIST,
        },
    },
}


CreateMessage = Callable[..., Any]


class AnthropicDiagnosisGenerator:
    def __init__(self, create_message: CreateMessage) -> None:
        self._create = create_message

    @classmethod
    def from_api_key(cls, api_key: str) -> "AnthropicDiagnosisGenerator":
        client = anthropic.Anthropic(api_key=api_key, timeout=TIMEOUT_SECONDS, max_retries=0)
        return cls(client.messages.create)

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis:
        request = build_request(redacted, parsed)
        for _ in range(ATTEMPTS):
            try:
                response = self._create(**request)
            except anthropic.APIError as err:
                status = getattr(err, "status_code", None)
                raise DiagnosisUnavailable(f"{type(err).__name__} status={status}") from None
            diagnosis = _diagnosis_from(response)
            if diagnosis is not None:
                return diagnosis
        raise DiagnosisUnavailable(f"no valid {TOOL_NAME} call after {ATTEMPTS} attempts")


def build_request(redacted: RedactedLog, parsed: ParsedLog) -> dict[str, Any]:
    parsed_json = json.dumps(asdict(parsed), indent=1, default=str)
    content = f"<log>\n{redacted.text}\n</log>\n\n<parsed>\n{parsed_json}\n</parsed>"
    return {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "tools": [TOOL],
        "tool_choice": {"type": "auto"},
        "messages": [{"role": "user", "content": content}],
    }


def _diagnosis_from(response: Any) -> Diagnosis | None:
    calls = [
        block
        for block in getattr(response, "content", None) or []
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", None) == TOOL_NAME
    ]
    if len(calls) != 1:
        return None
    try:
        return DiagnosisPayload.model_validate(calls[0].input).to_domain()
    except (ValidationError, ValueError):
        return None
