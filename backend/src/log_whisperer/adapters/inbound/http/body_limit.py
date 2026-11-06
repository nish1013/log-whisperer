"""Caps the raw request body before any parsing, chunked bodies included."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from log_whisperer.adapters.inbound.http.rate_limit import send_error

MAX_INPUT_BYTES = 204_800
# A JSON-escaped character takes at most 6 bytes (\uXXXX), plus room for the envelope.
MAX_BODY_BYTES = 6 * MAX_INPUT_BYTES + 1024


class BodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self._app = app
        self._max = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = _content_length(scope)
        if declared is not None and declared > self._max:
            await send_error(send, 413, "Input too large")
            return
        chunks: list[bytes] = []
        size = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self._app(scope, _replay([], message, receive), send)
                return
            chunk = message.get("body", b"")
            size += len(chunk)
            if size > self._max:
                await send_error(send, 413, "Input too large")
                return
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        await self._app(scope, _replay(chunks, None, receive), send)


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


def _replay(chunks: list[bytes], pending: Message | None, receive: Receive) -> Receive:
    sent = False

    async def replay() -> Message:
        nonlocal sent
        if pending is not None:
            return pending
        if not sent:
            sent = True
            return {"type": "http.request", "body": b"".join(chunks), "more_body": False}
        return await receive()

    return replay
