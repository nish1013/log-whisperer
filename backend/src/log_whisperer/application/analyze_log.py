from log_whisperer.application.dto import AnalysisResult
from log_whisperer.domain.grounding import enforce
from log_whisperer.domain.model import RawLog
from log_whisperer.domain.parsing import focus, parse
from log_whisperer.domain.ports import DiagnosisGenerator
from log_whisperer.domain.redaction import redact


class AnalyzeLog:
    """Redact, parse and focus a log, ask the generator, then ground its answer."""

    def __init__(self, generator: DiagnosisGenerator) -> None:
        self._generator = generator

    def execute(self, raw: RawLog) -> AnalysisResult:
        redacted = redact(raw)
        parsed = parse(redacted)
        focused = focus(redacted)
        diagnosis = self._generator.generate(focused, parsed)
        grounded = enforce(diagnosis, focused, parsed.kind)
        return AnalysisResult(
            diagnosis=grounded.diagnosis,
            kind=parsed.kind,
            truncated=parsed.truncated,
            redaction_count=redacted.redaction_count,
            grounding_stripped=grounded.stripped,
        )
