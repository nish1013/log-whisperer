"""Manual AI eval: every fixture through AnalyzeLog with the real model, twice.

Checks structured fields only, never wording. Prints a fixture x check table and the
threshold summary. Needs ANTHROPIC_API_KEY; without it the eval is deferred. Never runs in CI.
"""

import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.fixture_text import expected, fixture_text

from log_whisperer.adapters.outbound.llm.anthropic_generator import (
    AnthropicDiagnosisGenerator,
)
from log_whisperer.application.analyze_log import AnalyzeLog
from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.grounding import ungrounded_paths
from log_whisperer.domain.model import (
    Confidence,
    Diagnosis,
    ParsedLog,
    RawLog,
    RedactedLog,
)

TRACEBACKS = tuple(f"F0{i}" for i in range(1, 10))
CALIBRATION = ("F10", "F12")
RUNS = 2


@dataclass
class Recorder:
    inner: AnthropicDiagnosisGenerator
    calls: list[tuple[Diagnosis, RedactedLog, ParsedLog]] = field(default_factory=list)

    def generate(self, redacted: RedactedLog, parsed: ParsedLog) -> Diagnosis:
        diagnosis = self.inner.generate(redacted, parsed)
        self.calls.append((diagnosis, redacted, parsed))
        return diagnosis


@dataclass(frozen=True)
class Outcome:
    valid: bool
    ungrounded: int = 0
    stripped: int = 0
    culprit: tuple[str, int] | None = None
    culprit_agrees: bool = False
    names_type: bool = False
    fix_relevant: bool = False
    low: bool = False


def main() -> int:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        print("ANTHROPIC_API_KEY is not set: the eval is deferred.")
        return 2
    inputs = _inputs()
    runs = [{name: _run_one(key, name, text) for name, text in inputs.items()} for _ in range(RUNS)]
    _print_table(runs)
    return 0 if _print_summary(runs) else 1


def _inputs() -> dict[str, str]:
    texts = {name: fixture_text(f"{name}_py3.12") for name in TRACEBACKS}
    texts["F10"] = fixture_text("F10_jsonlines")
    texts["F11"] = fixture_text("F11_secrets")
    texts["F12"] = "hello world"
    return texts


def _run_one(key: str, name: str, text: str) -> Outcome:
    recorder = Recorder(AnthropicDiagnosisGenerator.from_api_key(key))
    try:
        result = AnalyzeLog(recorder).execute(RawLog(text))
    except DiagnosisUnavailable as err:
        print(f"{name}: unavailable ({err})")
        return Outcome(valid=False)
    ((raw, focused, parsed),) = recorder.calls
    culprit = None if raw.culprit is None else (raw.culprit.file, raw.culprit.line)
    parser = None if parsed.culprit is None else (parsed.culprit.file, parsed.culprit.line)
    prose = f"{raw.likely_cause}\n{raw.explanation}"
    types = {e.type for e in parsed.exceptions} | {
        e.type.rsplit(".", 1)[-1] for e in parsed.exceptions
    }
    keywords = expected().get(name, {}).get("fix_keywords", [])
    steps = " ".join(raw.fix.steps).lower()
    return Outcome(
        valid=True,
        ungrounded=len(ungrounded_paths(raw, focused)),
        stripped=result.grounding_stripped,
        culprit=culprit,
        culprit_agrees=culprit == parser,
        names_type=any(t in prose for t in types),
        fix_relevant=any(k.lower() in steps for k in keywords),
        low=raw.confidence is Confidence.LOW,
    )


def _print_table(runs: list[dict[str, Outcome]]) -> None:
    header = "fixture run valid ungrounded stripped culprit_ok names_type fix_ok low culprit"
    print(header)
    for index, run in enumerate(runs, start=1):
        for name, o in run.items():
            print(
                f"{name:7} {index:3} {_yn(o.valid):5} {o.ungrounded:10} {o.stripped:8} "
                f"{_yn(o.culprit_agrees):10} {_yn(o.names_type):10} {_yn(o.fix_relevant):6} "
                f"{_yn(o.low):3} {o.culprit}"
            )


def _print_summary(runs: list[dict[str, Outcome]]) -> bool:
    outcomes = [o for run in runs for o in run.values()]
    traceback_runs = [[run[name] for name in TRACEBACKS] for run in runs]
    checks = [
        ("Schema valid", sum(o.valid for o in outcomes), len(outcomes), len(outcomes)),
        ("Paths not in input, before grounding", sum(o.ungrounded for o in outcomes), 0, 0),
    ]
    for index, outcomes_run in enumerate(traceback_runs, start=1):
        checks += [
            (
                f"Run {index} culprit agrees with parser",
                _count(outcomes_run, "culprit_agrees"),
                9,
                8,
            ),
            (f"Run {index} names the exception type", _count(outcomes_run, "names_type"), 9, 9),
            (f"Run {index} fix has a keyword", _count(outcomes_run, "fix_relevant"), 9, 8),
        ]
    for index, run in enumerate(runs, start=1):
        low = sum(run[name].low for name in CALIBRATION)
        checks.append((f"Run {index} F10 and F12 are low", low, 2, 2))
    stable = sum(runs[0][name].culprit == runs[1][name].culprit for name in TRACEBACKS)
    checks.append(("Stable culprit across runs", stable, 9, 8))
    print(f"\ngrounding_stripped total: {sum(o.stripped for o in outcomes)}")
    passed = True
    for label, value, total, threshold in checks:
        ok = value <= threshold if label.startswith("Paths") else value >= threshold
        passed &= ok
        print(f"{'PASS' if ok else 'MISS'}  {label}: {value}/{total} (need {threshold})")
    return passed


def _count(outcomes: list[Outcome], attribute: str) -> int:
    return sum(getattr(o, attribute) for o in outcomes)


def _yn(value: bool) -> str:
    return "yes" if value else "no"


if __name__ == "__main__":
    sys.exit(main())
