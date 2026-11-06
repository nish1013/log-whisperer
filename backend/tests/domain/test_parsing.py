import random
from typing import Any

import pytest
from hypothesis import given
from hypothesis import strategies as st

from log_whisperer.domain.model import ParsedLog, RedactedLog
from log_whisperer.domain.parsing import MAX_CHARS, TAIL_LINES, focus, parse
from tests.fixture_text import expected, fixture_text, generated_cases


def _parse(text: str) -> ParsedLog:
    return parse(RedactedLog(text, 0))


def _summary(parsed: ParsedLog) -> dict[str, Any]:
    culprit = parsed.culprit
    return {
        "exceptions": [
            {"type": e.type, "message": e.message, "chain_reason": e.chain_reason}
            for e in parsed.exceptions
        ],
        "root_cause_index": parsed.root_cause_index,
        "culprit": None
        if culprit is None
        else {"file": culprit.file, "line": culprit.line, "func": culprit.func},
    }


@pytest.mark.parametrize(("fixture", "version"), generated_cases())
def test_generated_fixture_matches_the_live_exception(fixture: str, version: str) -> None:
    parsed = _parse(fixture_text(f"{fixture}_py{version}"))
    assert parsed.kind == "python_traceback"
    assert parsed.truncated is False
    assert _summary(parsed) == expected()[fixture]["versions"][version]


@pytest.mark.parametrize("version", ["3.10", "3.11", "3.12", "3.13"])
def test_log_prefixed_traceback_parses_like_the_plain_one(version: str) -> None:
    assert _parse(fixture_text(f"F08_py{version}")) == _parse(fixture_text(f"F01_py{version}"))


@pytest.mark.parametrize("version", ["3.10", "3.11", "3.12", "3.13"])
def test_f04_chain_ends_with_explicit_cause_after_requests_error(version: str) -> None:
    parsed = _parse(fixture_text(f"F04_py{version}"))
    types = [e.type for e in parsed.exceptions]
    assert len(types) == 5
    assert types[-2:] == ["requests.exceptions.ConnectionError", "app.errors.UpstreamUnavailable"]
    assert parsed.exceptions[-1].chain_reason == "cause"
    assert parsed.culprit is not None
    assert (parsed.culprit.file, parsed.culprit.line) == ("/srv/app/clients/http.py", 16)


@pytest.mark.parametrize("version", ["3.10", "3.11", "3.12", "3.13"])
def test_f05_without_from_links_by_context(version: str) -> None:
    assert _parse(fixture_text(f"F05_py{version}")).exceptions[-1].chain_reason == "context"


@pytest.mark.parametrize("version", ["3.10", "3.11", "3.12", "3.13"])
def test_recursion_frames_collapse(version: str) -> None:
    frames = _parse(fixture_text(f"F06_py{version}")).exceptions[0].frames
    assert [(f.file, f.func) for f in frames] == [
        ("/srv/run.py", "<module>"),
        ("/srv/run.py", "<lambda>"),
        ("/srv/app/worker.py", "walk_tree"),
    ]


@pytest.mark.parametrize(("fixture", "version"), generated_cases())
def test_caret_lines_never_become_code(fixture: str, version: str) -> None:
    for exception in _parse(fixture_text(f"{fixture}_py{version}")).exceptions:
        for frame in exception.frames:
            assert frame.code is None or frame.code.strip("^~ ") != ""


def test_library_frames_are_not_user_code() -> None:
    frames = _parse(fixture_text("F07_py3.12")).exceptions[0].frames
    assert frames
    assert not any(f.is_user_code for f in frames)


def test_code_line_is_the_source_line() -> None:
    culprit = _parse(fixture_text("F01_py3.12")).culprit
    assert culprit is not None
    assert culprit.code == 'return {"name": user["name"], "email": user["email"]}'


def test_json_lines_log_is_generic_with_three_errors() -> None:
    parsed = _parse(fixture_text("F10_jsonlines"))
    assert parsed.kind == "generic_log"
    assert parsed.log_levels["ERROR"] == 3
    assert parsed.culprit is None
    assert parsed.root_cause_index is None


@pytest.mark.parametrize(
    "text",
    [
        "",
        "hello world",
        random.Random(12).randbytes(1 << 20).decode("latin-1"),
    ],
    ids=["empty", "hello", "random-1mb"],
)
def test_garbage_is_unknown(text: str) -> None:
    parsed = _parse(text)
    assert parsed.kind == "unknown"
    assert parsed.exceptions == ()
    assert parsed.culprit is None


def test_new_log_record_after_traceback_does_not_join_the_message() -> None:
    text = fixture_text("F08_py3.12") + "2026-11-05 10:00:02,000 INFO app.worker - next job\n"
    assert _parse(text).exceptions[0].message == "'email'"


def test_unprefixed_line_after_prefixed_exception_does_not_join() -> None:
    text = fixture_text("F08_py3.12") + "worker restarted\n"
    assert _parse(text).exceptions[0].message == "'email'"


def test_python_logging_default_prefix_is_stripped() -> None:
    lines = fixture_text("F01_py3.12").splitlines()
    text = "\n".join(f"ERROR:app.worker:{line}" for line in lines)
    assert _parse(text) == _parse(fixture_text("F01_py3.12"))


def test_separate_tracebacks_keep_the_last_chain() -> None:
    text = fixture_text("F02_py3.12") + "\nretrying\n" + fixture_text("F01_py3.12")
    parsed = _parse(text)
    assert [e.type for e in parsed.exceptions] == ["KeyError"]


def test_header_without_exception_line_is_not_a_traceback() -> None:
    text = 'Traceback (most recent call last):\n  File "/srv/a.py", line 1, in f\n    x()\n'
    assert _parse(text).kind == "unknown"


def test_exception_message_without_colon() -> None:
    text = 'Traceback (most recent call last):\n  File "/srv/a.py", line 3, in f\n    raise E\nE\n'
    parsed = _parse(text)
    assert (parsed.exceptions[0].type, parsed.exceptions[0].message) == ("E", "")


def test_frame_without_code_line() -> None:
    text = (
        'Traceback (most recent call last):\n  File "<stdin>", line 1, in <module>\nValueError: x'
    )
    culprit = _parse(text).culprit
    assert culprit is not None
    assert culprit.code is None


def test_chain_without_user_frames_has_no_culprit() -> None:
    text = (
        "Traceback (most recent call last):\n"
        '  File "/usr/lib/python3.12/json/decoder.py", line 9, in decode\n'
        "    raise JSONDecodeError\n"
        "json.decoder.JSONDecodeError: bad"
    )
    assert _parse(text).culprit is None


def _long_log() -> tuple[str, str]:
    filler = [f"2026-11-05 10:00:00,000 INFO app.worker - tick {i}" for i in range(3000)]
    traceback = fixture_text("F04_py3.12").rstrip("\n")
    text = "\n".join([*filler[:1500], traceback, *filler[1500:]])
    return text, traceback


def test_long_input_is_focused_on_tracebacks_and_the_tail() -> None:
    text, traceback = _long_log()
    assert len(text) > MAX_CHARS
    focused = focus(RedactedLog(text, 2))
    lines = focused.text.split("\n")
    assert focused.redaction_count == 2
    assert traceback in focused.text
    assert lines[-TAIL_LINES:] == text.split("\n")[-TAIL_LINES:]
    assert len(lines) == len(traceback.split("\n")) + TAIL_LINES
    assert _parse(focused.text).exceptions == _parse(traceback).exceptions
    parsed = _parse(text)
    assert parsed.truncated is True
    assert len(parsed.exceptions) == 5


def test_short_input_is_not_focused() -> None:
    log = RedactedLog(fixture_text("F01_py3.12"), 0)
    assert focus(log) is log


@given(st.text())
def test_parse_never_raises(text: str) -> None:
    parsed = _parse(text)
    assert parsed.kind in ("python_traceback", "generic_log", "unknown")
