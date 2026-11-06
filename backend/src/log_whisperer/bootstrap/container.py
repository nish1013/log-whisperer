import logging

from fastapi import FastAPI

from log_whisperer.adapters.inbound.http.app import create_app
from log_whisperer.adapters.outbound.llm.anthropic_generator import AnthropicDiagnosisGenerator
from log_whisperer.adapters.outbound.llm.fake_generator import FakeDiagnosisGenerator
from log_whisperer.application.analyze_log import AnalyzeLog
from log_whisperer.bootstrap.settings import Settings
from log_whisperer.domain.ports import DiagnosisGenerator


def build_generator(settings: Settings) -> DiagnosisGenerator:
    if settings.llm_provider == "anthropic" and settings.anthropic_api_key is not None:
        return AnthropicDiagnosisGenerator.from_api_key(settings.anthropic_api_key)
    return FakeDiagnosisGenerator()


def build_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    logging.getLogger("log_whisperer").setLevel(logging.INFO)
    analyze = AnalyzeLog(build_generator(settings))
    return create_app(analyze, settings.rate_limit_per_minute)
