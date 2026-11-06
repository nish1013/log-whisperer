"""FastAPI app: POST /api/analyze and GET /healthz."""

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from log_whisperer.adapters.inbound.http.body_limit import MAX_INPUT_BYTES, BodyLimitMiddleware
from log_whisperer.adapters.inbound.http.rate_limit import RateLimitMiddleware, SlidingWindowLimiter
from log_whisperer.adapters.inbound.http.schemas import (
    AnalysisResponse,
    AnalyzeRequest,
    ErrorResponse,
    HealthResponse,
)
from log_whisperer.application.analyze_log import AnalyzeLog
from log_whisperer.domain.errors import DiagnosisUnavailable
from log_whisperer.domain.model import RawLog

logger = logging.getLogger("log_whisperer.http")

_ERRORS: dict[int | str, dict[str, Any]] = {
    status: {"model": ErrorResponse, "description": description}
    for status, description in (
        (400, "Empty input or invalid request"),
        (413, "Input too large"),
        (429, "Rate limit exceeded"),
        (502, "Analysis failed"),
    )
}


def create_app(analyze: AnalyzeLog, rate_limit_per_minute: int) -> FastAPI:
    app = FastAPI(title="log-whisperer", version="0.1.0")

    @app.get("/healthz", response_model=HealthResponse)
    def healthz() -> HealthResponse:
        return HealthResponse(status="ok")

    @app.post("/api/analyze", response_model=AnalysisResponse, responses=_ERRORS)
    def analyze_endpoint(body: AnalyzeRequest, request: Request) -> Any:
        if len(body.input.encode("utf-8")) > MAX_INPUT_BYTES:
            return _error(413, "Input too large")
        if not body.input.strip():
            return _error(400, "Input is empty")
        try:
            result = analyze.execute(RawLog(body.input))
        except DiagnosisUnavailable:
            return _error(502, "Analysis failed")
        except Exception as err:
            logger.error("analysis error class=%s", type(err).__name__)
            return _error(500, "Internal error")
        request.state.kind = result.kind
        request.state.redaction_count = result.redaction_count
        return AnalysisResponse.from_result(result)

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_: Request, __: RequestValidationError) -> JSONResponse:
        return _error(400, "Invalid request")

    app.openapi = lambda: _openapi_without_422(app)  # type: ignore[method-assign]
    limiter = SlidingWindowLimiter(rate_limit_per_minute)
    app.add_middleware(RateLimitMiddleware, limiter=limiter)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(RequestLogMiddleware)
    return app


class RequestLogMiddleware:
    """Logs request id, status, latency, kind and redaction count. Never the body or path."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        start = time.perf_counter()
        status = 500
        state: dict[str, Any] = scope.setdefault("state", {})

        async def capture(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self._app(scope, receive, capture)
        finally:
            logger.info(
                "request id=%s status=%d latency_ms=%.1f kind=%s redaction_count=%s",
                uuid.uuid4().hex,
                status,
                (time.perf_counter() - start) * 1000,
                state.get("kind", "-"),
                state.get("redaction_count", "-"),
            )


def _error(status: int, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": message})


def _openapi_without_422(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema is not None:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi

    schema = get_openapi(title=app.title, version=app.version, routes=app.routes)
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            operation.get("responses", {}).pop("422", None)
    schemas = schema.get("components", {}).get("schemas", {})
    for name in ("HTTPValidationError", "ValidationError"):
        schemas.pop(name, None)
    app.openapi_schema = schema
    return schema
