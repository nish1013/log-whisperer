from dataclasses import dataclass, field

import pytest

from log_whisperer.adapters.outbound.llm.fake_generator import FakeDiagnosisGenerator
from log_whisperer.application.analyze_log import AnalyzeLog
from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.model import (
    Confidence,
    CulpritRef,
    Diagnosis,
    Fix,
    ParsedLog,
    RawLog,
    RedactedLog,
)
from log_whisperer.domain.parsing import MAX_CHARS
from tests.fixture_text import fixture_text, secrets


@dataclass
class SpyGenerator:
    diagnosis: Diagnosis | None = None
    error: Exception | None = None
    calls: list[tuple[RedactedLog, ParsedLog]] = field(default_factory=list)

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis:
        self.calls.append((redacted, parsed))
        if self.error is not None:
            raise self.error
        if self.diagnosis is not None:
            return self.diagnosis
        return FakeDiagnosisGenerator().generate(redacted, parsed)


def test_generator_never_receives_a_secret() -> None:
    spy = SpyGenerator()
    result = AnalyzeLog(spy).execute(RawLog(fixture_text("F11_secrets")))
    ((redacted, _),) = spy.calls
    for secret in secrets():
        assert secret not in redacted.text
    assert result.redaction_count == 5


def test_invented_culprit_is_removed() -> None:
    invented = Diagnosis(
        summary="KeyError",
        likely_cause="KeyError on email",
        confidence=Confidence.HIGH,
        explanation="KeyError.",
        culprit=CulpritRef("app/fake/nowhere.py", 10, "get_profile"),
        fix=Fix(("Use dict.get.",), None, None),
        alternative_causes=(),
        follow_up_checks=(),
    )
    generator = SpyGenerator(diagnosis=invented)
    result = AnalyzeLog(generator).execute(RawLog(fixture_text("F01_py3.12")))
    assert result.diagnosis.culprit is None
    assert result.diagnosis.confidence is Confidence.LOW
    assert result.grounding_stripped == 1


def test_generator_failure_propagates_as_domain_error() -> None:
    with pytest.raises(DiagnosisUnavailable):
        AnalyzeLog(SpyGenerator(error=DiagnosisUnavailable("down"))).execute(RawLog("ERROR x"))


def test_long_input_reaches_the_generator_focused() -> None:
    filler = "\n".join(f"INFO tick {i}" for i in range(9000))
    text = filler + "\n" + fixture_text("F01_py3.12")
    assert len(text) > MAX_CHARS
    spy = SpyGenerator()
    result = AnalyzeLog(spy).execute(RawLog(text))
    ((redacted, parsed),) = spy.calls
    assert result.truncated is True
    assert parsed.truncated is True
    assert len(redacted.text) < len(text)
    assert "INFO tick 0\n" not in redacted.text
    assert result.diagnosis.culprit == CulpritRef("/srv/app/services/user.py", 2, "get_profile")


def test_result_reports_kind() -> None:
    result = AnalyzeLog(SpyGenerator()).execute(RawLog(fixture_text("F10_jsonlines")))
    assert result.kind == "generic_log"
    assert result.diagnosis.confidence is Confidence.LOW
