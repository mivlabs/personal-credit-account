"""Описания ошибочных ответов для OpenAPI (тело — ProblemDetail, application/problem+json)."""

from typing import Any

from app.schemas.problem import ProblemDetail


def _problem(description: str) -> dict[str, Any]:
    return {"model": ProblemDetail, "description": description}


R401 = {401: _problem("Нет токена, он недействителен или истёк")}
R403 = {403: _problem("Роль пользователя не позволяет это действие")}
R404 = {404: _problem("Не найдено. Для клиента заявка другой компании тоже отдаёт 404")}
R409 = {409: _problem("Действие недопустимо в текущем статусе заявки или конфликт ключа идемпотентности")}
R422 = {422: _problem("Ошибка валидации: `errors[]` указывает на поля")}
R409_REGISTER = {409: _problem("Логин занят (`LOGIN_TAKEN`) или ИНН уже зарегистрирован (`INN_TAKEN`)")}
R503_EGRUL = {503: _problem("ЕГРЮЛ недоступен (`EGRUL_UNAVAILABLE`), компания не создана")}
R429 = {429: _problem("Слишком много неудачных попыток входа; смотрите заголовок `Retry-After`")}
R503 = {503: _problem("База данных недоступна")}

CLIENT_ERRORS = {**R401, **R403, **R422}
