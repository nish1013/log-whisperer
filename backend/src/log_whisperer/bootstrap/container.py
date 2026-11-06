from fastapi import FastAPI

from log_whisperer.adapters.inbound.http.app import create_app
from log_whisperer.bootstrap.settings import Settings


def build_app(settings: Settings | None = None) -> FastAPI:
    _ = settings or Settings.from_env()
    return create_app()
