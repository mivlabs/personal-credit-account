"""Сборка схемы OpenAPI: единый формат ошибок application/problem+json и метаданные тегов."""

import copy
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

API_VERSION = "1.0.0"

DESCRIPTION = """
Бэкенд кредитного конвейера для малого бизнеса: клиент проходит путь от выбора продукта до выдачи кредита,
банк ведёт ту же заявку в той же системе.

**Авторизация.** `POST /auth/login` → `accessToken` (новый клиент: `POST /auth/register` по ИНН возвращает то же); дальше заголовок `Authorization: Bearer <token>`.

**Формат данных.** JSON в camelCase. Деньги — число в рублях (до 2 знаков), ставка — число, % годовых.
Даты и время — ISO 8601 с часовым поясом.

**Ошибки.** Формат RFC 7807 (`application/problem+json`): `type`, `title`, `status`, `detail`, машинный `code`
(`VALIDATION_ERROR`, `INVALID_TRANSITION`, `NOT_FOUND`, `FORBIDDEN`, `IDEMPOTENCY_CONFLICT` …) и `errors[]` по полям.

**Идемпотентная подача.** `POST /applications/{id}/submit` требует заголовок `Idempotency-Key`; повтор с тем же
ключом возвращает ту же заявку и ничего не создаёт.

**Статусы.** Меняются только по стейт-машине (`docs/state-machine.md`); недопустимый переход — 409 `INVALID_TRANSITION`.
""".strip()

TAGS_METADATA = [
    {"name": "auth", "description": "Вход и текущий пользователь"},
    {"name": "products", "description": "Каталог кредитных продуктов"},
    {"name": "companies", "description": "Профиль компании клиента"},
    {
        "name": "applications",
        "description": "Кредитные заявки клиента: черновик, подача, статус, оффер, подписание",
    },
    {"name": "underwriter", "description": "Панель банка: очередь, ручное решение, аудит"},
    {"name": "system", "description": "Служебные эндпоинты"},
]


def build_openapi(app: FastAPI) -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title="Умный кредитный кабинет — API ядра",
        version=API_VERSION,
        description=DESCRIPTION,
        routes=app.routes,
        tags=TAGS_METADATA,
        servers=[{"url": "http://localhost:8000", "description": "Локальный запуск через docker compose"}],
    )

    # Автоматический 422 FastAPI (ошибки path/query/header) заменяем на единый формат ProblemDetail
    problem_422 = {
        "description": "Ошибка валидации: `errors[]` указывает на поля",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/ProblemDetail"}}},
    }
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            current = operation.get("responses", {}).get("422")
            if current and "HTTPValidationError" in str(current):
                operation["responses"]["422"] = copy.deepcopy(problem_422)
    for name in ("HTTPValidationError", "ValidationError"):
        schema["components"]["schemas"].pop(name, None)

    # Ошибки отдаём как application/problem+json, а не application/json
    for path_item in schema["paths"].values():
        for operation in path_item.values():
            for status, response in operation.get("responses", {}).items():
                content = response.get("content")
                if status.isdigit() and int(status) >= 400 and content and "application/json" in content:
                    response["content"] = {"application/problem+json": content["application/json"]}

    app.openapi_schema = schema
    return schema
