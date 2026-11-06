import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

Provider = Literal["fake", "anthropic"]

_PROVIDERS: tuple[Provider, ...] = ("fake", "anthropic")
_DEFAULT_RATE_LIMIT = 10


class SettingsError(ValueError):
    pass


@dataclass(frozen=True)
class Settings:
    llm_provider: Provider
    anthropic_api_key: str | None
    rate_limit_per_minute: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Settings":
        source = os.environ if env is None else env
        provider = _provider(source.get("LLM_PROVIDER", "fake"))
        key = (source.get("ANTHROPIC_API_KEY") or "").strip() or None
        if provider == "anthropic" and key is None:
            raise SettingsError("LLM_PROVIDER=anthropic needs a non-blank ANTHROPIC_API_KEY")
        return cls(
            llm_provider=provider,
            anthropic_api_key=key,
            rate_limit_per_minute=_rate_limit(source.get("RATE_LIMIT_PER_MINUTE")),
        )


def _provider(raw: str) -> Provider:
    value = raw.strip().lower() or "fake"
    for provider in _PROVIDERS:
        if provider == value:
            return provider
    raise SettingsError(f"LLM_PROVIDER must be one of {', '.join(_PROVIDERS)}")


def _rate_limit(raw: str | None) -> int:
    if raw is None or not raw.strip():
        return _DEFAULT_RATE_LIMIT
    try:
        value = int(raw.strip())
    except ValueError:
        raise SettingsError("RATE_LIMIT_PER_MINUTE must be a positive integer") from None
    if value <= 0:
        raise SettingsError("RATE_LIMIT_PER_MINUTE must be a positive integer")
    return value
