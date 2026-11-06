from typing import Protocol

from log_whisperer.domain.model import Diagnosis, ParsedLog, RedactedLog


class DiagnosisGenerator(Protocol):
    """Raises DiagnosisUnavailable on unrecoverable failure."""

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis: ...
