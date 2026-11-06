import pytest

from log_whisperer.bootstrap.settings import Settings, SettingsError


def test_defaults_to_fake_provider_and_ten_per_minute() -> None:
    settings = Settings.from_env({})
    assert settings.llm_provider == "fake"
    assert settings.rate_limit_per_minute == 10
    assert settings.anthropic_api_key is None


@pytest.mark.parametrize("key", [None, "", "   "])
def test_anthropic_provider_without_key_fails(key: str | None) -> None:
    env = {"LLM_PROVIDER": "anthropic"}
    if key is not None:
        env["ANTHROPIC_API_KEY"] = key
    with pytest.raises(SettingsError, match="ANTHROPIC_API_KEY"):
        Settings.from_env(env)


def test_anthropic_provider_with_key_is_accepted() -> None:
    settings = Settings.from_env({"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "k"})
    assert settings.llm_provider == "anthropic"
    assert settings.anthropic_api_key == "k"


def test_unknown_provider_fails() -> None:
    with pytest.raises(SettingsError, match="LLM_PROVIDER"):
        Settings.from_env({"LLM_PROVIDER": "openai"})


@pytest.mark.parametrize("raw", ["0", "-1", "ten", "1.5"])
def test_rate_limit_rejects_non_positive_or_non_integer(raw: str) -> None:
    with pytest.raises(SettingsError, match="RATE_LIMIT_PER_MINUTE"):
        Settings.from_env({"RATE_LIMIT_PER_MINUTE": raw})


def test_rate_limit_reads_positive_value() -> None:
    assert Settings.from_env({"RATE_LIMIT_PER_MINUTE": " 600 "}).rate_limit_per_minute == 600
