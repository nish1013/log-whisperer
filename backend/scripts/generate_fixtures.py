"""Generate traceback fixtures by running fixtures_src under each pinned Python.

Writes tests/fixtures/<ID>_py<minor>.txt (real stderr, normalised) and
tests/fixtures/expected.json (taken from the live exception objects, not from the parser).
A rerun is byte-identical.
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parent.parent
SOURCE = BACKEND / "fixtures_src"
OUT = BACKEND / "tests" / "fixtures"
PYTHONS = ("3.10.22", "3.11.18", "3.12.16", "3.13.18")
SCENARIOS = ("F01", "F02", "F03", "F04", "F05", "F06", "F07", "F09")
LOG_PREFIX = "2026-11-05 10:00:01,123 ERROR app.worker - "
USER_ROOT = "/srv/"

FIX_KEYWORDS: dict[str, list[str]] = {
    "F01": [".get(", " in ", "KeyError"],
    "F02": ["None", "is not None", "Optional"],
    "F03": ["pip install", "requirements"],
    "F04": ["retry", "timeout", "connection", "reachable"],
    "F05": ["retry", "timeout", "connection", "reachable"],
    "F06": ["recursion", "base case", "iterative"],
    "F07": ["unique", "duplicate", "upsert"],
    "F08": [".get(", " in ", "KeyError"],
    "F09": ["timeout", "wait_for", "cancel"],
}
HAND_WRITTEN: dict[str, dict[str, Any]] = {
    "F10": {"kind": "generic_log", "log_levels": {"ERROR": 3}, "culprit": None},
    "F11": {
        "redaction_count": 5,
        "secret_parts": [
            ["AKIA", "FAKEFAKE", "EXAMPLE0"],
            ["eyJhbGciOiJIUzI1NiJ9", ".eyJzdWIiOiJmYWtlLXVzZXIifQ", ".ZmFrZS1zaWduYXR1cmUtdmFsdWU"],
            ["sk-", "test_", "FAKEonlyFORtestsNOTreal00"],
            ["user", ":", "hunter2-fake"],
            ["ana.fake", "@", "example.org"],
        ],
    },
    "F12": {"kind": "unknown"},
}

_SITE = re.compile(r'"[^"\n]*?/lib/(python3\.\d+)/site-packages/')
_STDLIB = re.compile(r'"[^"\n]*?/lib/(python3\.\d+)/(?!site-packages/)')
_ADDRESS = re.compile(r"\b0x[0-9a-f]{6,}\b")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected: dict[str, Any] = {}
    for python in PYTHONS:
        minor = ".".join(python.split(".")[:2])
        for scenario in SCENARIOS:
            text, described = _run(scenario, python)
            _write(f"{scenario}_py{minor}.txt", text)
            expected.setdefault(scenario, {})[minor] = described
            if scenario == "F01":
                prefixed = "".join(LOG_PREFIX + line for line in text.splitlines(keepends=True))
                _write(f"F08_py{minor}.txt", prefixed)
                expected.setdefault("F08", {})[minor] = described
    result: dict[str, Any] = {
        key: {"versions": expected[key], "fix_keywords": FIX_KEYWORDS[key]}
        for key in sorted(expected)
    }
    result.update(HAND_WRITTEN)
    _write("expected.json", json.dumps(result, indent=2, sort_keys=True) + "\n")


def _run(scenario: str, python: str) -> tuple[str, dict[str, Any]]:
    deps, cutoff = _fixture_deps()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(("UV_", "PYTHON", "VIRTUAL_ENV"))
    }
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "describe.json"
        env.update(PYTHONHASHSEED="0", PYTHONDONTWRITEBYTECODE="1", DESCRIBE_TO=str(target))
        with_args = [arg for dep in deps for arg in ("--with", dep)]
        proc = subprocess.run(
            [
                "uv",
                "run",
                "-q",
                "--no-project",
                "--exclude-newer",
                cutoff,
                "--python",
                python,
                *with_args,
                "python",
                "run.py",
                scenario,
            ],
            cwd=SOURCE,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        if proc.returncode == 0 or not target.exists():
            sys.exit(f"{scenario} on {python} did not fail as expected:\n{proc.stderr}")
        described = json.loads(_normalise(target.read_text(encoding="utf-8")))
    return _normalise(proc.stderr), described


def _fixture_deps() -> tuple[list[str], str]:
    project = tomllib.loads((BACKEND / "pyproject.toml").read_text(encoding="utf-8"))
    deps: list[str] = project["dependency-groups"]["fixtures"]
    cutoff: str = project["tool"]["uv"]["exclude-newer"]
    return deps, cutoff


def _normalise(text: str) -> str:
    text = text.replace(str(SOURCE) + "/", USER_ROOT)
    text = _SITE.sub(r'"/venv/lib/\1/site-packages/', text)
    text = _STDLIB.sub(r'"/usr/lib/\1/', text)
    return _ADDRESS.sub("0x7f0000000000", text)


def _write(name: str, text: str) -> None:
    (OUT / name).write_text(text, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
