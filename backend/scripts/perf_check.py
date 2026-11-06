"""Manual timing report for the redactor and parser. Prints results; never gates CI."""

import sys
import time
from collections.abc import Callable
from functools import partial
from pathlib import Path

from log_whisperer.domain.model import RawLog, RedactedLog
from log_whisperer.domain.parsing import parse
from log_whisperer.domain.redaction import redact

SIZE = 200 * 1024
REDACT_BUDGET_S = 1.0
PARSE_BUDGET_S = 0.1
FIXTURES = Path(__file__).resolve().parent.parent / "tests" / "fixtures"


def _timed(action: Callable[[], object]) -> float:
    start = time.perf_counter()
    action()
    return time.perf_counter() - start


def main() -> int:
    failures = 0
    adversarial = {
        "aaaa": "a" * SIZE,
        "a@a@": ("a@" * SIZE)[:SIZE],
        "a://": ("a://" * SIZE)[:SIZE],
        "a.a.": ("a." * SIZE)[:SIZE],
        "a:a@": ("a://a:" * SIZE)[:SIZE],
        "Ab3_": ("Ab3_" * SIZE)[:SIZE],
    }
    for name, text in adversarial.items():
        seconds = _timed(partial(redact, RawLog(text)))
        ok = seconds < REDACT_BUDGET_S
        failures += not ok
        print(f"redact {name:6} {seconds * 1000:8.1f} ms  {'ok' if ok else 'SLOW'}")
    for path in sorted(FIXTURES.glob("F06_py*.txt")):
        text = path.read_text(encoding="utf-8")
        seconds = _timed(partial(parse, RedactedLog(text, 0)))
        ok = seconds < PARSE_BUDGET_S
        failures += not ok
        print(f"parse  {path.stem:12} {seconds * 1000:8.1f} ms  {'ok' if ok else 'SLOW'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
