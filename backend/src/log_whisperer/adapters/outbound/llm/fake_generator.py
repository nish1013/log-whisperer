from log_whisperer.domain.model import (
    SUMMARY_MAX_CHARS,
    Confidence,
    CulpritRef,
    Diagnosis,
    Fix,
    ParsedLog,
    RedactedLog,
)


class FakeDiagnosisGenerator:
    """Deterministic diagnosis built from the parser output. Used by tests and E2E."""

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis:
        if parsed.root_cause_index is None or not parsed.exceptions:
            return _no_traceback(parsed)
        root = parsed.exceptions[parsed.root_cause_index]
        first_line = root.message.split("\n", 1)[0]
        headline = f"{root.type}: {first_line}" if first_line else root.type
        later = [e.type for e in parsed.exceptions[parsed.root_cause_index + 1 :]]
        likely_cause = f"{headline} (surfaced as {', '.join(later)})" if later else headline
        culprit = parsed.culprit
        if culprit is None:
            steps = (f"Find where {root.type} is raised and handle that case.",)
            return Diagnosis(
                summary=_clip(headline),
                likely_cause=likely_cause,
                confidence=Confidence.MEDIUM,
                explanation=f"The traceback ends in {root.type} with no frame in your code.",
                culprit=None,
                fix=Fix(steps, None, None),
                alternative_causes=(),
                follow_up_checks=("Check which library call raised the error.",),
            )
        return Diagnosis(
            summary=_clip(f"{headline} in {culprit.func}"),
            likely_cause=likely_cause,
            confidence=Confidence.HIGH,
            explanation=(
                f"{culprit.func} raised {root.type} at line {culprit.line} of {culprit.file}."
            ),
            culprit=CulpritRef(culprit.file, culprit.line, culprit.func),
            fix=Fix(
                steps=(
                    f"Open {culprit.file} at line {culprit.line} in {culprit.func}.",
                    f"Handle the case that raises {root.type} before this line runs.",
                    "Add a test that reproduces the failure.",
                ),
                code_snippet=culprit.code,
                language="python" if culprit.code else None,
            ),
            alternative_causes=tuple(f"{t} raised earlier in the chain." for t in later),
            follow_up_checks=("Check the input that reached this frame.",),
        )


def _no_traceback(parsed: ParsedLog) -> Diagnosis:
    errors = parsed.log_levels.get("ERROR", 0)
    noun = "line" if errors == 1 else "lines"
    summary = (
        f"No Python traceback found; {errors} ERROR {noun}."
        if errors
        else ("No Python traceback found.")
    )
    return Diagnosis(
        summary=summary,
        likely_cause="The input has no traceback, so the cause is unclear.",
        confidence=Confidence.LOW,
        explanation="Paste the full traceback for a specific diagnosis.",
        culprit=None,
        fix=Fix(("Capture the full traceback of the failing request.",), None, None),
        alternative_causes=(),
        follow_up_checks=("Look for the first ERROR line and the request it belongs to.",),
    )


def _clip(text: str) -> str:
    return text if len(text) <= SUMMARY_MAX_CHARS else text[: SUMMARY_MAX_CHARS - 1] + "…"
