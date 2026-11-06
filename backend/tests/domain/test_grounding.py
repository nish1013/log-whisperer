from dataclasses import replace

from log_whisperer.domain.grounding import FALLBACK_STEP, enforce, ungrounded_paths
from log_whisperer.domain.model import Confidence, CulpritRef, Diagnosis, Fix, RedactedLog
from tests.fixture_text import fixture_text

F01 = RedactedLog(fixture_text("F01_py3.12"), 0)
GOOD_CULPRIT = CulpritRef("/srv/app/services/user.py", 2, "get_profile")


def _diagnosis(**changes: object) -> Diagnosis:
    base = Diagnosis(
        summary="KeyError: 'email' in get_profile",
        likely_cause="The user dict has no 'email' key.",
        confidence=Confidence.HIGH,
        explanation="get_profile reads user['email'] in app/services/user.py. The key is absent.",
        culprit=GOOD_CULPRIT,
        fix=Fix(("Use user.get('email').",), 'user.get("email")', "python"),
        alternative_causes=(),
        follow_up_checks=(),
    )
    return replace(base, **changes)  # type: ignore[arg-type]


def test_invented_culprit_is_stripped_and_confidence_drops() -> None:
    result = enforce(
        _diagnosis(culprit=CulpritRef("app/fake/nowhere.py", 10, "get_profile")),
        F01,
        "python_traceback",
    )
    assert result.diagnosis.culprit is None
    assert result.diagnosis.confidence is Confidence.LOW
    assert result.stripped == 1


def test_grounded_diagnosis_is_unchanged() -> None:
    diagnosis = _diagnosis()
    result = enforce(diagnosis, F01, "python_traceback")
    assert result.diagnosis == diagnosis
    assert result.stripped == 0


def test_relative_culprit_with_colon_line_form_is_grounded() -> None:
    log = RedactedLog("error at app/services/user.py:2 in get_profile", 0)
    result = enforce(
        _diagnosis(culprit=CulpritRef("app/services/user.py", 2, "get_profile")),
        log,
        "python_traceback",
    )
    assert result.diagnosis.culprit is not None


def test_culprit_with_wrong_line_is_stripped() -> None:
    result = enforce(_diagnosis(culprit=replace(GOOD_CULPRIT, line=3)), F01, "python_traceback")
    assert result.diagnosis.culprit is None


def test_culprit_with_unknown_function_is_stripped() -> None:
    result = enforce(
        _diagnosis(culprit=replace(GOOD_CULPRIT, func="load_user")), F01, "python_traceback"
    )
    assert result.diagnosis.culprit is None


def test_sentence_with_invented_path_is_dropped() -> None:
    result = enforce(
        _diagnosis(
            explanation="The key is absent. See app/models/profile.py for the schema. Add it."
        ),
        F01,
        "python_traceback",
    )
    assert result.diagnosis.explanation == "The key is absent. Add it."
    assert result.diagnosis.culprit == GOOD_CULPRIT
    assert result.stripped == 1


def test_fix_step_with_invented_path_is_dropped_and_fallback_keeps_one_step() -> None:
    result = enforce(
        _diagnosis(fix=Fix(("Edit settings.py.",), None, None)), F01, "python_traceback"
    )
    assert result.diagnosis.fix.steps == (FALLBACK_STEP,)
    assert result.stripped == 1


def test_bare_config_file_names_are_not_paths() -> None:
    steps = ("Add backoff to requirements.txt and pyproject.toml.",)
    result = enforce(_diagnosis(fix=Fix(steps, None, None)), F01, "python_traceback")
    assert result.diagnosis.fix.steps == steps


def test_non_traceback_caps_confidence_at_low() -> None:
    diagnosis = _diagnosis(culprit=None, explanation="The key is absent.")
    result = enforce(diagnosis, RedactedLog("ERROR boom", 0), "generic_log")
    assert result.diagnosis.confidence is Confidence.LOW
    assert result.stripped == 0


def test_ungrounded_paths_lists_invented_paths() -> None:
    diagnosis = _diagnosis(
        likely_cause="Bug in app/fake/nowhere.py.",
        culprit=CulpritRef("app/x.py", 1, "f"),
    )
    assert ungrounded_paths(diagnosis, F01) == ["app/fake/nowhere.py", "app/x.py"]


def test_sentence_with_invented_absolute_path_is_dropped() -> None:
    result = enforce(
        _diagnosis(explanation="The key is absent. The loader in /opt/app/loader.py drops it."),
        F01,
        "python_traceback",
    )
    assert result.diagnosis.explanation == "The key is absent."
    assert result.stripped == 1


def test_absolute_path_from_the_log_is_kept() -> None:
    explanation = "/srv/app/services/user.py reads the key."
    result = enforce(_diagnosis(explanation=explanation), F01, "python_traceback")
    assert result.diagnosis.explanation == explanation
