import json
import logging
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from log_whisperer.adapters.inbound.http.app import create_app
from log_whisperer.adapters.inbound.http.body_limit import MAX_BODY_BYTES
from log_whisperer.adapters.outbound.llm.fake_generator import FakeDiagnosisGenerator
from log_whisperer.application.analyze_log import AnalyzeLog
from log_whisperer.bootstrap.container import build_app
from log_whisperer.bootstrap.settings import Settings
from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.model import Diagnosis, ParsedLog, RedactedLog
from tests.fixture_text import fixture_text, generated_cases

LIMIT = 204_800


class FailingGenerator:
    def __init__(self, error: Exception) -> None:
        self._error = error

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis:
        raise self._error


def _client(rate_limit: int = 1000) -> TestClient:
    return TestClient(build_app(Settings.from_env({"RATE_LIMIT_PER_MINUTE": str(rate_limit)})))


def _failing_client(error: Exception) -> TestClient:
    app = create_app(AnalyzeLog(FailingGenerator(error)), 1000)
    return TestClient(app, raise_server_exceptions=False)


def test_f01_returns_the_analysis_shape() -> None:
    response = _client().post("/api/analyze", json={"input": fixture_text("F01_py3.12")})
    assert response.status_code == 200
    body = response.json()
    assert set(body) == {"diagnosis", "kind", "truncated", "redaction_count"}
    assert body["kind"] == "python_traceback"
    assert body["truncated"] is False
    assert body["redaction_count"] == 0
    assert body["diagnosis"]["culprit"] == {
        "file": "/srv/app/services/user.py",
        "line": 2,
        "func": "get_profile",
    }
    assert body["diagnosis"]["confidence"] == "high"
    assert set(body["diagnosis"]["fix"]) == {"steps", "code_snippet", "language"}


def test_f11_reports_five_redactions() -> None:
    response = _client().post("/api/analyze", json={"input": fixture_text("F11_secrets")})
    assert response.json()["redaction_count"] == 5


@pytest.mark.parametrize("text", ["", "   \n\t "])
def test_empty_input_is_400(text: str) -> None:
    response = _client().post("/api/analyze", json={"input": text})
    assert (response.status_code, response.json()) == (400, {"error": "Input is empty"})


@pytest.mark.parametrize(
    "content",
    ['{"inp": "x"}', '{"input": 5}', '{"input": null}', "not json", '["input"]', ""],
)
def test_invalid_body_is_400_and_never_echoes(content: str) -> None:
    response = _client().post(
        "/api/analyze", content=content, headers={"content-type": "application/json"}
    )
    assert (response.status_code, response.json()) == (400, {"error": "Invalid request"})


def test_exactly_the_limit_is_accepted() -> None:
    response = _client().post("/api/analyze", json={"input": "a" * LIMIT})
    assert response.status_code == 200


def test_one_byte_over_the_limit_is_413() -> None:
    response = _client().post("/api/analyze", json={"input": "a" * (LIMIT + 1)})
    assert (response.status_code, response.json()) == (413, {"error": "Input too large"})


def test_limit_counts_utf8_bytes() -> None:
    text = "é" * (LIMIT // 2) + "a"
    assert len(text) < LIMIT
    assert _client().post("/api/analyze", json={"input": text}).status_code == 413
    text = "é" * (LIMIT // 2)
    assert _client().post("/api/analyze", json={"input": text}).status_code == 200


def test_oversized_raw_body_is_413_before_parsing() -> None:
    response = _client().post(
        "/api/analyze",
        content=b"x" * (MAX_BODY_BYTES + 1),
        headers={"content-type": "application/json"},
    )
    assert (response.status_code, response.json()) == (413, {"error": "Input too large"})


def test_oversized_chunked_body_without_length_is_413() -> None:
    def chunks() -> Iterator[bytes]:
        for _ in range(MAX_BODY_BYTES // 65_536 + 2):
            yield b"x" * 65_536

    response = _client().post(
        "/api/analyze", content=chunks(), headers={"content-type": "application/json"}
    )
    assert "content-length" not in {k.lower() for k in response.request.headers}
    assert (response.status_code, response.json()) == (413, {"error": "Input too large"})


def test_eleventh_request_in_a_minute_is_429_counting_malformed() -> None:
    client = _client(rate_limit=10)
    for i in range(10):
        content = "bad" if i % 2 else json.dumps({"input": "hello"})
        client.post("/api/analyze", content=content, headers={"content-type": "application/json"})
    response = client.post("/api/analyze", json={"input": "hello"})
    assert (response.status_code, response.json()) == (429, {"error": "Rate limit exceeded"})
    assert client.get("/healthz").status_code == 200


def test_unavailable_diagnosis_is_502_without_traceback() -> None:
    response = _failing_client(DiagnosisUnavailable("APIStatusError status=529")).post(
        "/api/analyze", json={"input": fixture_text("F01_py3.12")}
    )
    assert (response.status_code, response.json()) == (502, {"error": "Analysis failed"})
    assert "Traceback" not in response.text


def test_unexpected_error_is_500_without_traceback() -> None:
    response = _failing_client(RuntimeError("boom")).post(
        "/api/analyze", json={"input": fixture_text("F01_py3.12")}
    )
    assert (response.status_code, response.json()) == (500, {"error": "Internal error"})
    assert "boom" not in response.text


def test_healthz() -> None:
    response = _client().get("/healthz")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_openapi_documents_exactly_the_error_set() -> None:
    schema = _client().get("/openapi.json").json()
    responses = schema["paths"]["/api/analyze"]["post"]["responses"]
    assert set(responses) == {"200", "400", "413", "429", "502"}
    for status in ("400", "413", "429", "502"):
        ref = responses[status]["content"]["application/json"]["schema"]["$ref"]
        assert ref.endswith("/ErrorResponse")
    assert "HTTPValidationError" not in schema["components"]["schemas"]


@pytest.mark.parametrize(("fixture", "version"), generated_cases()[::4])
def test_logs_hold_neither_input_nor_path(
    fixture: str, version: str, caplog: pytest.LogCaptureFixture
) -> None:
    text = fixture_text(f"{fixture}_py{version}")
    with caplog.at_level(logging.DEBUG):
        _client().post("/api/analyze", json={"input": text})
        _client().post("/api/analyze", content="bad", headers={"content-type": "application/json"})
    logged = _app_logs(caplog)
    assert "status=200" in logged
    assert "kind=python_traceback" in logged
    assert "/api/analyze" not in logged
    for line in text.splitlines():
        if line.strip():
            assert line.strip() not in logged


def test_secrets_never_reach_logs(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG):
        _client().post("/api/analyze", json={"input": fixture_text("F11_secrets")})
    logged = _app_logs(caplog)
    assert "redaction_count=5" in logged
    assert "app.config" not in logged


def _app_logs(caplog: pytest.LogCaptureFixture) -> str:
    client_side = ("httpx", "httpcore", "asyncio")
    records = [r for r in caplog.records if not r.name.startswith(client_side)]
    return "\n".join(record.getMessage() for record in records)


def test_fake_provider_is_default() -> None:
    from log_whisperer.bootstrap.container import build_generator

    assert isinstance(build_generator(Settings.from_env({})), FakeDiagnosisGenerator)
