"""Ошибки в формате RFC 7807 (application/problem+json)."""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.enums import ErrorCode

PROBLEM_MEDIA_TYPE = "application/problem+json"
logger = logging.getLogger(__name__)

_DEFAULT_TITLES = {
    400: "Некорректный запрос",
    401: "Требуется авторизация",
    403: "Недостаточно прав",
    404: "Не найдено",
    405: "Метод не поддерживается",
    409: "Конфликт состояния",
    422: "Ошибка валидации",
    500: "Внутренняя ошибка сервера",
    501: "Не реализовано",
    503: "Сервис недоступен",
}

_CODE_BY_STATUS = {
    401: ErrorCode.UNAUTHORIZED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    422: ErrorCode.VALIDATION_ERROR,
    501: ErrorCode.NOT_IMPLEMENTED,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


class ProblemError(Exception):
    """Базовое исключение: превращается в ответ problem+json."""

    status = 500
    code = ErrorCode.INTERNAL_ERROR
    title = _DEFAULT_TITLES[500]

    def __init__(
        self,
        detail: str | None = None,
        *,
        errors: list[dict[str, Any]] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(detail or self.title)
        self.detail = detail
        self.errors = errors or []
        self.headers = headers


class UnauthorizedError(ProblemError):
    status = 401
    code = ErrorCode.UNAUTHORIZED
    title = _DEFAULT_TITLES[401]

    def __init__(self, detail: str | None = None, *, code: ErrorCode | None = None) -> None:
        super().__init__(detail, headers={"WWW-Authenticate": "Bearer"})
        if code is not None:
            self.code = code


class ForbiddenError(ProblemError):
    status = 403
    code = ErrorCode.FORBIDDEN
    title = _DEFAULT_TITLES[403]


class NotFoundError(ProblemError):
    status = 404
    code = ErrorCode.NOT_FOUND
    title = _DEFAULT_TITLES[404]


class InvalidTransitionError(ProblemError):
    status = 409
    code = ErrorCode.INVALID_TRANSITION
    title = "Недопустимый переход статуса"


class IdempotencyConflictError(ProblemError):
    status = 409
    code = ErrorCode.IDEMPOTENCY_CONFLICT
    title = "Конфликт идемпотентности"


class ValidationProblem(ProblemError):
    status = 422
    code = ErrorCode.VALIDATION_ERROR
    title = _DEFAULT_TITLES[422]


class NotImplementedProblem(ProblemError):
    status = 501
    code = ErrorCode.NOT_IMPLEMENTED
    title = _DEFAULT_TITLES[501]

    def __init__(self, detail: str = "Эндпоинт ещё не реализован") -> None:
        super().__init__(detail)


class ServiceUnavailableError(ProblemError):
    status = 503
    code = ErrorCode.SERVICE_UNAVAILABLE
    title = _DEFAULT_TITLES[503]


def field_error(field: str, message: str, code: str | None = None) -> dict[str, Any]:
    return {"field": field, "message": message, "code": code}


def problem_response(
    request: Request,
    *,
    status: int,
    code: ErrorCode,
    title: str,
    detail: str | None = None,
    errors: list[dict[str, Any]] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    body = {
        "type": f"urn:problem:{code.value.lower().replace('_', '-')}",
        "title": title,
        "status": status,
        "detail": detail,
        "code": code.value,
        "instance": request.url.path,
        "errors": errors or [],
        "requestId": getattr(request.state, "request_id", None),
    }
    return JSONResponse(body, status_code=status, media_type=PROBLEM_MEDIA_TYPE, headers=headers)


def _loc_to_field(loc: tuple[Any, ...]) -> str:
    # ("body", "requestedAmount") -> "requestedAmount"; ("header", "Idempotency-Key") -> "Idempotency-Key"
    parts = [str(p) for p in loc if p not in ("body", "query", "path", "header")]
    return ".".join(parts) or "body"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ProblemError)
    async def _problem(request: Request, exc: ProblemError) -> JSONResponse:
        return problem_response(
            request,
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            errors=exc.errors,
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            field_error(_loc_to_field(tuple(e["loc"])), e.get("msg", ""), e.get("type")) for e in exc.errors()
        ]
        return problem_response(
            request,
            status=422,
            code=ErrorCode.VALIDATION_ERROR,
            title=_DEFAULT_TITLES[422],
            detail="Запрос не прошёл проверку: исправьте отмеченные поля",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODE_BY_STATUS.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return problem_response(
            request,
            status=exc.status_code,
            code=code,
            title=_DEFAULT_TITLES.get(exc.status_code, "Ошибка"),
            detail=str(exc.detail) if exc.detail else None,
            headers=dict(exc.headers) if exc.headers else None,
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Необработанная ошибка: %s %s", request.method, request.url.path)
        return problem_response(
            request,
            status=500,
            code=ErrorCode.INTERNAL_ERROR,
            title=_DEFAULT_TITLES[500],
            detail="Что-то пошло не так. Назовите поддержке requestId из ответа.",
        )
