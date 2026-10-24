# Контракт API

Авторитетная схема: [OpenAPI](api/openapi.yaml), экспортируется из FastAPI командой `cd backend && uv run python -m app.scripts.export_openapi`. Типы frontend: `cd frontend && npm run generate:api`. Сгенерированный src/api-types.ts фиксируется в git.

Сохранены /api/v1, camelCase, JWT, CLIENT/UNDERWRITER и RFC 7807. Деньги в JSON — числа в рублях до 2 знаков, процент в годовых, срок в месяцах. Даты UTC с часовым поясом. Внутренние вычисления Decimal/NUMERIC. Овердрафт не имеет аннуитетного monthlyPayment.

Дополнения: POST /companies/me/enrich; availableActions в полной карточке, вычисляется из роли и статуса; status/limit/offset у GET /applications; status у /underwriter/queue (по умолчанию MANUAL_REVIEW, ALL для всех).

Подача требует Idempotency-Key. Команды PATCH /applications/{id}/missing-info, POST /applications/{id}/offer/accept и POST /applications/{id}/sign принимают необязательный Idempotency-Key; UI его отправляет. Смысл повторов и совместимость описаны в assumptions.md.

Существующий путь: /applications → /submit → /missing-info при необходимости → /offer/accept → /sign. Последняя команда моделирует подпись и выдачу вместе, как в BPMN. Решения банка: POST /underwriter/applications/{id}/decision, значения APPROVED, COUNTER_OFFER, NEEDS_INFO, REJECTED, непустой comment обязателен. Ошибки: 401, 403, 404 для чужой заявки, 409 состояние/ключ, 422 поля, 503 обогащение компании.

Примеры запросов: [demo.http](api/demo.http).
