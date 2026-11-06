"""Load fixture text. Fills {{secret:N}} placeholders from expected.json secret parts."""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

FIXTURES = Path(__file__).resolve().parent / "fixtures"
PYTHON_VERSIONS = ("3.10", "3.11", "3.12", "3.13")
GENERATED = ("F01", "F02", "F03", "F04", "F05", "F06", "F07", "F08", "F09")
_PLACEHOLDER = re.compile(r"\{\{secret:(\d+)\}\}")


@cache
def expected() -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES / "expected.json").read_text(encoding="utf-8"))
    return data


def secrets() -> list[str]:
    return ["".join(parts) for parts in expected()["F11"]["secret_parts"]]


def fixture_text(name: str) -> str:
    text = (FIXTURES / f"{name}.txt").read_text(encoding="utf-8")
    values = secrets()
    return _PLACEHOLDER.sub(lambda match: values[int(match.group(1))], text)


def generated_cases() -> list[tuple[str, str]]:
    return [(fixture, version) for fixture in GENERATED for version in PYTHON_VERSIONS]
