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

Сессия 2. Новые команды и поля:

- `POST /underwriter/applications/{id}/recheck`, тело `{comment}` (обязателен): повторная проверка источников, только в `MANUAL_REVIEW` (иначе 409), только андеррайтер (клиенту 403). Переход `MANUAL_REVIEW → EXTERNAL_CHECK`, конвейер идёт заново: новые `external_check` и новое AUTO-решение со снимком. Действие `RECHECK` в `availableActions`.
- `POST /applications/{id}/withdraw`, тело `{reason?}`, необязательный `Idempotency-Key`: отзыв из `DRAFT`, `NEEDS_INFO`, `MANUAL_REVIEW` → `WITHDRAWN`. Для `APPROVED`/`COUNTER_OFFER` остаётся `offer/decline`. Действие `WITHDRAW` в `availableActions`. Отозванные заявки не попадают в очередь андеррайтера по умолчанию.
- Сроки: `offer.validUntil` (`OFFER_TTL_DAYS`, 30) и `infoRequests[].dueAt` (`INFO_REQUEST_TTL_DAYS`, 14); у старых строк `null`. Если срок истёк, `offer/accept`, `offer/decline`, `missing-info` и `sign` переводят заявку в `EXPIRED` и возвращают 409 с кодом `EXPIRED`; переход сохраняется. Массовое закрытие: `python -m app.scripts.expire_stale`.
- `POST /products/recommendations`, тело `{purposeCategory, amount?, termMonths?}`, роль клиента. Ответ: `{purposeCategory, purposeLabel, rulesVersion, items[{product, matchScore 0–100, recommended, reasons[], rateFrom}]}`, по убыванию `matchScore`. Категории: `WORKING_CAPITAL_TOPUP`, `GOODS_PURCHASE`, `EQUIPMENT_PURCHASE`, `CASH_GAP`, `SEASONAL`, `EXPANSION`, `OTHER`.

Сессия 4. Регистрация по ИНН:

- `POST /auth/register` без авторизации, тело `{login, password, inn}`; `201` и тело как у `/auth/login` (`accessToken`, `tokenType`, `expiresIn`, `user`). Логин 3–32 символа `a-z0-9_.-`, пароль не короче 8, ИНН — 10 или 12 цифр с верными контрольными числами ФНС (seed-ИНН пропускаются явным списком).
- `422 VALIDATION_ERROR` с `errors[]` по полям `login`, `password`, `inn` (в том числе «Неверная контрольная сумма ИНН»); `409 LOGIN_TAKEN` (поле `login`); `409 INN_TAKEN` (поле `inn`); `503 EGRUL_UNAVAILABLE` (компания не создана); `429 TOO_MANY_REQUESTS` с `Retry-After`.
- Новые значения `ErrorCode`: `LOGIN_TAKEN`, `INN_TAKEN`, `EGRUL_UNAVAILABLE`.
