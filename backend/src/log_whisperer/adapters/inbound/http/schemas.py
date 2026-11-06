from typing import Literal

from pydantic import BaseModel, ConfigDict

from log_whisperer.application.dto import AnalysisResult


class AnalyzeRequest(BaseModel):
    model_config = ConfigDict(strict=True)
    input: str


class ErrorResponse(BaseModel):
    error: str


class HealthResponse(BaseModel):
    status: str


class CulpritOut(BaseModel):
    file: str
    line: int
    func: str


class FixOut(BaseModel):
    steps: list[str]
    code_snippet: str | None
    language: str | None


class DiagnosisOut(BaseModel):
    summary: str
    likely_cause: str
    confidence: Literal["high", "medium", "low"]
    explanation: str
    culprit: CulpritOut | None
    fix: FixOut
    alternative_causes: list[str]
    follow_up_checks: list[str]


class AnalysisResponse(BaseModel):
    diagnosis: DiagnosisOut
    kind: Literal["python_traceback", "generic_log", "unknown"]
    truncated: bool
    redaction_count: int

    @classmethod
    def from_result(cls, result: AnalysisResult) -> "AnalysisResponse":
        d = result.diagnosis
        culprit = d.culprit
        return cls(
            diagnosis=DiagnosisOut(
                summary=d.summary,
                likely_cause=d.likely_cause,
                confidence=d.confidence.value,
                explanation=d.explanation,
                culprit=None
                if culprit is None
                else CulpritOut(file=culprit.file, line=culprit.line, func=culprit.func),
                fix=FixOut(
                    steps=list(d.fix.steps),
                    code_snippet=d.fix.code_snippet,
                    language=d.fix.language,
                ),
                alternative_causes=list(d.alternative_causes),
                follow_up_checks=list(d.follow_up_checks),
            ),
            kind=result.kind,
            truncated=result.truncated,
            redaction_count=result.redaction_count,
        )
