import pytest
from hypothesis import given
from hypothesis import strategies as st

from log_whisperer.domain.model import RawLog
from log_whisperer.domain.redaction import redact
from tests.fixture_text import fixture_text, generated_cases, secrets

AWS_PREFIX = "AKIA"


def test_f11_masks_all_five_secrets() -> None:
    result = redact(RawLog(fixture_text("F11_secrets")))
    assert result.redaction_count == 5
    for secret in secrets():
        assert secret not in result.text
    for name in ("aws_key", "bearer", "api_key", "url_credentials", "email"):
        assert f"[REDACTED:{name}]" in result.text


@pytest.mark.parametrize(("fixture", "version"), generated_cases())
def test_tracebacks_have_no_false_positives(fixture: str, version: str) -> None:
    text = fixture_text(f"{fixture}_py{version}")
    result = redact(RawLog(text))
    assert result.redaction_count == 0
    assert result.text == text


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (f"key={AWS_PREFIX}ABCDEFGHIJ012345", "key=[REDACTED:aws_key]"),
        ("Authorization: Bearer abc.def-ghi_123", "Authorization: Bearer [REDACTED:bearer]"),
        ("token eyJhbGci.eyJzdWIi.c2lnbmF0dXJl end", "token [REDACTED:jwt] end"),
        ("sk" + "_live_" + "abcdefghijklmnop12", "[REDACTED:api_key]"),
        ("pk" + "-" + "abcdefghijklmnop12", "[REDACTED:api_key]"),
        ("disk" + "-" + "abcdefghijklmnop12", "disk-abcdefghijklmnop12"),
        ("redis://u:p@cache:6379/0", "redis://[REDACTED:url_credentials]@cache:6379/0"),
        ("1xredis+tls://a:b@c", "1xredis+tls://[REDACTED:url_credentials]@c"),
        ("mail ana@example.org now", "mail [REDACTED:email] now"),
        ("x.y@ex.org%me@mail.example.com", "[REDACTED:email][REDACTED:email]"),
        ("host 10.0.0.12 down", "host [REDACTED:ipv4] down"),
        ("version 1.2.3.4.5", "version 1.2.3.4.5"),
        ("sha " + "a1" * 20, "sha [REDACTED:high_entropy]"),
        ("blob " + "Ab3" * 12, "blob [REDACTED:high_entropy]"),
        ("call _very_long_snake_case_function_name_here()", None),
    ],
)
def test_single_rules(text: str, expected: str | None) -> None:
    result = redact(RawLog(text))
    assert result.text == (text if expected is None else expected)
    assert result.redaction_count == (0 if expected is None else expected.count("[REDACTED:"))


def test_bearer_jwt_counts_once() -> None:
    result = redact(RawLog("Authorization: Bearer eyJhbGci.eyJzdWIi.c2lnbmF0dXJl"))
    assert result.redaction_count == 1


def test_placeholder_is_never_matched_again() -> None:
    result = redact(RawLog("contact ana@" + AWS_PREFIX + "ABCDEFGHIJ012345.example.org"))
    assert result.text.count("[REDACTED:") == result.redaction_count


def test_email_local_part_extension_is_bounded() -> None:
    result = redact(RawLog("x" * 500 + "@example.org"))
    assert result.text == "x" * 436 + "[REDACTED:email]"


@given(
    st.text(),
    st.text(alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", min_size=16, max_size=16),
    st.text(),
)
def test_generated_aws_key_never_survives(before: str, body: str, after: str) -> None:
    key = AWS_PREFIX + body
    assert key not in redact(RawLog(before + key + after)).text
