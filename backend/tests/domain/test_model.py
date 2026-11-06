import pytest

from log_whisperer.domain.model import Confidence, Diagnosis, Fix


def test_fix_needs_one_to_six_steps() -> None:
    with pytest.raises(ValueError, match="1 to 6"):
        Fix((), None, None)
    with pytest.raises(ValueError, match="1 to 6"):
        Fix(tuple("abcdefg"), None, None)
    assert len(Fix(tuple("abcdef"), None, None).steps) == 6


def test_summary_is_at_most_200_characters() -> None:
    fix = Fix(("a",), None, None)
    with pytest.raises(ValueError, match="200"):
        Diagnosis("x" * 201, "c", Confidence.LOW, "e", None, fix, (), ())
    assert len(Diagnosis("x" * 200, "c", Confidence.LOW, "e", None, fix, (), ()).summary) == 200
