# Контракт API

Авторитетная схема: [OpenAPI](api/openapi.yaml), экспортируется из FastAPI командой `cd backend && uv run python -m app.scripts.export_openapi`. Типы frontend: `cd frontend && npm run generate:api`. Сгенерированный src/api-types.ts фиксируется в git.

Сохранены /api/v1, camelCase, JWT, CLIENT/UNDERWRITER и RFC 7807. Деньги в JSON — числа в рублях до 2 знаков, процент в годовых, срок в месяцах. Даты UTC с часовым поясом. Внутренние вычисления Decimal/NUMERIC. Овердрафт не имеет аннуитетного monthlyPayment.

Дополнения: POST /companies/me/enrich; availableActions в полной карточке, вычисляется из роли и статуса; status/limit/offset у GET /applications; status у /underwriter/queue (по умолчанию MANUAL_REVIEW, ALL для всех).

Подача требует Idempotency-Key. Команды PATCH /applications/{id}/missing-info, POST /applications/{id}/offer/accept и POST /applications/{id}/sign принимают необязательный Idempotency-Key; UI его отправляет. Смысл повторов и совместимость описаны в assumptions.md.

Существующий путь: /applications → /submit → /missing-info при необходимости → /offer/accept → /sign. Последняя команда моделирует подпись и выдачу вместе, как в BPMN. Решения банка: POST /underwriter/applications/{id}/decision, значения APPROVED, COUNTER_OFFER, NEEDS_INFO, REJECTED, непустой comment обязателен. Ошибки: 401, 403, 404 для чужой заявки, 409 состояние/ключ, 422 поля, 503 обогащение компании.

Ставка. Продукт: `rate` (= `rateFrom`, «от X %») и `rateBreakdown {keyRate, keyRateDate, keyRateSource, productSpread, riskSurcharge, total}`. Оффер: `offer.rateBreakdown` (из снимка решения).

Прозрачность решения. Клиент: `GET /applications/{id}` → `decisionExplanation {ruleCode, ruleText, decidedBySpecialist, score, thresholds, inputs[{code,label,value,source,sourceName}], factors[{label,points,maxPoints,impact,impactLabel,explanation}], limit{value,text,components}, rate, asOfDate, policyVersion}`; без конфига и внутреннего комментария. Андеррайтер: `GET /underwriter/applications/{id}` → у каждого решения `snapshot`, на карточке `autoLimit`.

Ручное решение выше расчётного лимита: `DecisionRequest.overrideLimit` (по умолчанию false). APPROVED на запрошенную сумму или COUNTER_OFFER выше `autoLimit` без `overrideLimit: true` возвращает 422 с полем `overrideLimit` (`LIMIT_EXCEEDED`). Если AUTO-лимита нет, решение не блокируется, в снимок пишется `limitUnknown: true`.

Примеры запросов: [demo.http](api/demo.http).
