import json
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from log_whisperer.adapters.outbound.llm.anthropic_generator import (
    MODEL,
    TOOL,
    TOOL_NAME,
    AnthropicDiagnosisGenerator,
)
from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.model import Confidence, CulpritRef, RawLog, RedactedLog
from log_whisperer.domain.parsing import parse
from log_whisperer.domain.redaction import redact
from tests.fixture_text import fixture_text, secrets

VALID: dict[str, Any] = {
    "summary": "KeyError: 'email' in get_profile",
    "likely_cause": "KeyError: the user dict has no 'email' key.",
    "confidence": "high",
    "explanation": "get_profile reads user['email'] but the caller omits it.",
    "culprit": {"file": "/srv/app/services/user.py", "line": 2, "func": "get_profile"},
    "fix": {
        "steps": ["Use user.get('email')."],
        "code_snippet": "user.get('email')",
        "language": "python",
    },
    "alternative_causes": [],
    "follow_up_checks": ["Check the caller."],
}


def _response(*blocks: Any) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks), stop_reason="tool_use")


def _tool(payload: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", name=TOOL_NAME, input=payload)


class FakeCreate:
    def __init__(self, *outcomes: Any) -> None:
        self._outcomes = list(outcomes)
        self.requests: list[dict[str, Any]] = []

    def __call__(self, **kwargs: Any) -> Any:
        self.requests.append(kwargs)
        outcome = self._outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def _inputs(name: str = "F01_py3.12") -> tuple[RedactedLog, Any]:
    redacted = redact(RawLog(fixture_text(name)))
    return redacted, parse(redacted)


def test_valid_tool_call_maps_to_domain() -> None:
    create = FakeCreate(_response(_tool(VALID)))
    diagnosis = AnthropicDiagnosisGenerator(create).generate(*_inputs())
    assert diagnosis.culprit == CulpritRef("/srv/app/services/user.py", 2, "get_profile")
    assert diagnosis.confidence is Confidence.HIGH
    assert len(create.requests) == 1


def test_request_uses_strict_tool_and_auto_choice() -> None:
    create = FakeCreate(_response(_tool(VALID)))
    AnthropicDiagnosisGenerator(create).generate(*_inputs())
    (request,) = create.requests
    assert request["model"] == MODEL
    assert request["tool_choice"] == {"type": "auto"}
    assert request["tools"] == [TOOL]
    assert TOOL["strict"] is True
    assert "/srv/app/services/user.py" in request["messages"][0]["content"]


def test_invalid_then_valid_retries_once() -> None:
    long_summary = {**VALID, "summary": "x" * 201}
    create = FakeCreate(_response(_tool(long_summary)), _response(_tool(VALID)))
    diagnosis = AnthropicDiagnosisGenerator(create).generate(*_inputs())
    assert diagnosis.summary == VALID["summary"]
    assert len(create.requests) == 2


@pytest.mark.parametrize(
    "bad",
    [
        _response(SimpleNamespace(type="text", text="I cannot help.")),
        _response(_tool({**VALID, "fix": {**VALID["fix"], "steps": []}})),
        _response(_tool({**VALID, "fix": {**VALID["fix"], "steps": ["s"] * 7}})),
        _response(_tool({**VALID, "confidence": "certain"})),
        _response(_tool(VALID), _tool(VALID)),
    ],
    ids=["text-reply", "no-steps", "seven-steps", "bad-enum", "two-calls"],
)
def test_invalid_twice_is_unavailable(bad: Any) -> None:
    create = FakeCreate(bad, bad)
    with pytest.raises(DiagnosisUnavailable):
        AnthropicDiagnosisGenerator(create).generate(*_inputs())
    assert len(create.requests) == 2


def test_api_error_fails_at_once_with_class_and_status_only() -> None:
    request = httpx2.Request("POST", "https://api.example.invalid/v1/messages")
    response = httpx2.Response(529, request=request, text="overloaded secret-body")
    error = anthropic.APIStatusError("overloaded secret-body", response=response, body=None)
    create = FakeCreate(error)
    with pytest.raises(DiagnosisUnavailable) as caught:
        AnthropicDiagnosisGenerator(create).generate(*_inputs())
    assert str(caught.value) == "APIStatusError status=529"
    assert caught.value.__cause__ is None
    assert len(create.requests) == 1


def test_timeout_is_unavailable() -> None:
    request = httpx2.Request("POST", "https://api.example.invalid/v1/messages")
    create = FakeCreate(anthropic.APITimeoutError(request=request))
    with pytest.raises(DiagnosisUnavailable, match="APITimeoutError"):
        AnthropicDiagnosisGenerator(create).generate(*_inputs())


def test_request_payload_holds_no_raw_secret() -> None:
    create = FakeCreate(_response(_tool({**VALID, "culprit": None, "confidence": "low"})))
    AnthropicDiagnosisGenerator(create).generate(*_inputs("F11_secrets"))
    payload = json.dumps(create.requests[0])
    for secret in secrets():
        assert secret not in payload


def test_client_is_built_without_retries_and_with_timeout() -> None:
    generator = AnthropicDiagnosisGenerator.from_api_key("test-key")
    client = generator._create.__self__._client  # type: ignore[attr-defined]
    assert client.max_retries == 0
    assert client.timeout == 30.0
