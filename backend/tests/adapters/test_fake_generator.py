import pytest

from log_whisperer.adapters.outbound.llm.fake_generator import FakeDiagnosisGenerator
from log_whisperer.domain.model import Confidence, CulpritRef, RedactedLog
from log_whisperer.domain.parsing import parse
from tests.fixture_text import expected, fixture_text, generated_cases


def _generate(text: str):  # type: ignore[no-untyped-def]
    log = RedactedLog(text, 0)
    return FakeDiagnosisGenerator().generate(log, parse(log))


@pytest.mark.parametrize(("fixture", "version"), generated_cases())
def test_culprit_and_confidence_follow_the_parser(fixture: str, version: str) -> None:
    diagnosis = _generate(fixture_text(f"{fixture}_py{version}"))
    culprit = expected()[fixture]["versions"][version]["culprit"]
    assert diagnosis.culprit == CulpritRef(culprit["file"], culprit["line"], culprit["func"])
    assert diagnosis.confidence is Confidence.HIGH
    assert len(diagnosis.summary) <= 200


@pytest.mark.parametrize("version", ["3.10", "3.11", "3.12", "3.13"])
def test_f04_likely_cause_names_the_requests_error(version: str) -> None:
    diagnosis = _generate(fixture_text(f"F04_py{version}"))
    assert diagnosis.likely_cause.startswith("ConnectionRefusedError")
    assert "requests.exceptions.ConnectionError" in diagnosis.likely_cause


def test_snippet_is_the_culprit_source_line() -> None:
    diagnosis = _generate(fixture_text("F01_py3.12"))
    assert diagnosis.fix.code_snippet == 'return {"name": user["name"], "email": user["email"]}'
    assert diagnosis.fix.language == "python"


@pytest.mark.parametrize("name", ["F10_jsonlines", "F11_secrets"])
def test_logs_without_traceback_are_low(name: str) -> None:
    diagnosis = _generate(fixture_text(name))
    assert diagnosis.confidence is Confidence.LOW
    assert diagnosis.culprit is None


def test_traceback_without_user_frames_is_medium_without_culprit() -> None:
    text = (
        "Traceback (most recent call last):\n"
        '  File "/usr/lib/python3.12/json/decoder.py", line 9, in decode\n'
        "    raise JSONDecodeError\n"
        "json.decoder.JSONDecodeError: bad"
    )
    diagnosis = _generate(text)
    assert diagnosis.culprit is None
    assert diagnosis.confidence is Confidence.MEDIUM
