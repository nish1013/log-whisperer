from dataclasses import dataclass

from log_whisperer.domain.model import Diagnosis, LogKind


@dataclass(frozen=True)
class AnalysisResult:
    diagnosis: Diagnosis
    kind: LogKind
    truncated: bool
    redaction_count: int
    grounding_stripped: int
