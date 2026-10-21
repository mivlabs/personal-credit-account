"""Структурированные логи (JSON) с request_id и application_id."""

import json
import logging
import time
import uuid
from contextvars import ContextVar

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
application_id_var: ContextVar[int | None] = ContextVar("application_id", default=None)

_RESERVED = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__) | {"message", "asctime"}

logger = logging.getLogger("app.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_var.get(),
            "application_id": application_id_var.get(),
        }
        for key, value in record.__dict__.items():
            if key not in _RESERVED and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


def setup_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())
    # uvicorn пишет свой access-лог в другом формате, а мы пишем свой
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware:
    """Присваивает запросу request_id, пишет access-лог, отдаёт X-Request-ID в ответе."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        raw = dict(scope["headers"]).get(b"x-request-id", b"").decode("latin-1")[:64]
        request_id = raw or uuid.uuid4().hex[:12]
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status = {"code": 500}

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
                message["headers"] = [*message.get("headers", []), (b"x-request-id", request_id.encode())]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            path = scope["path"]
            level = logging.DEBUG if path == "/health" else logging.INFO
            logger.log(
                level,
                "%s %s -> %s",
                scope["method"],
                path,
                status["code"],
                extra={"duration_ms": round((time.perf_counter() - started) * 1000, 1)},
            )
            request_id_var.reset(token)
