# Умный кредитный кабинет предпринимателя

Прототип кредитного конвейера для малого бизнеса (хакатон Альфа-Банка): клиент проходит путь от выбора продукта
до выдачи кредита, а банк ведёт ту же заявку в том же продукте.

Веб-интерфейс: **http://localhost:3000**. Запуск всех четырёх сервисов: `docker compose up --build`.
Все аккаунты и деньги демонстрационные, пароль **demo1234**. Начните с **client_fast** или откройте панель банка как **underwriter**.

Реализованы пять исходов, HTTP-проверки WireMock, конфигурируемый скоринг, кабинет клиента и панель банка.
Объём и соответствие user stories: [implementation-scope](docs/implementation-scope.md).
Архитектура: [architecture](docs/architecture.md), расхождения: [assumptions](docs/assumptions.md),
сценарии: [test-scenarios](docs/test-scenarios.md), фактические проверки: [verification](docs/verification.md).

<!-- backend:start -->

## Бэкенд: запуск и проверка

Нужен только Docker (Compose v2). Всё остальное внутри образов, версии зафиксированы точными тегами и `uv.lock`.

### Запуск одной командой

```bash
docker compose up --build
```

Первая сборка занимает несколько минут. При старте контейнер `api` сам накатывает миграции Alembic и seed
(справочники, демо-компании, аккаунты), затем запускает сервер. Готовность видна по healthcheck:
`docker compose ps` показывает `healthy` у `db`, `api`, `mocks`, `web`.

| Сервис | Адрес | Что это |
|---|---|---|
| API ядра | <http://localhost:8000> | FastAPI, префикс `/api/v1` |
| Swagger UI | <http://localhost:8000/docs> | интерактивная документация |
| OpenAPI | [`docs/api/openapi.yaml`](docs/api/openapi.yaml) | зафиксированный контракт |
| Health | <http://localhost:8000/health> | проверка БД |
| Моки (WireMock) | <http://localhost:8081> | ЕГРЮЛ / ФНС / БКИ (синтетические данные) |
| PostgreSQL | `127.0.0.1:55432` | только для отладки, логин и пароль `credit` |

Полный сброс данных: `docker compose down -v`.

### Тестовые аккаунты

Пароль у всех: **`demo1234`**. Подробности, ИНН и ожидаемые исходы: [`docs/test-accounts.md`](docs/test-accounts.md).

| Логин | Роль | Сценарий |
|---|---|---|
| `client_fast` | клиент (ИП) | быстрое одобрение |
| `client_counter` | клиент (ООО) | контроффер |
| `client_manual` | клиент (молодое ООО) | ручная проверка |
| `client_info` | клиент (ООО без отчётности ФНС) | дозапрос данных |
| `client_reject` | клиент (ООО, просрочка 120 дн.) | отказ |
| `client_timeout` | клиент (ООО, БКИ не отвечает) | таймаут → ручная проверка |
| `underwriter` | андеррайтер | очередь и ручное решение |

### Быстрая проверка

Сквозной прогон (вход → каталог → профиль → черновик → подача → конвейер → аудит), без зависимостей, на стандартной
библиотеке Python:

```bash
cd backend
uv run python -m app.scripts.smoke        # или: python -m app.scripts.smoke
```

Вручную через curl:

```bash
TOKEN=$(curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"login":"client_fast","password":"demo1234"}' | python -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")
curl -s localhost:8000/api/v1/products -H "Authorization: Bearer $TOKEN"
```

В Swagger UI нажмите **Authorize** и вставьте `accessToken` из `POST /auth/login`.

### Что уже работает

- Вход по логину и паролю, JWT, две роли: клиент видит только заявки своей компании (чужая — 404),
  панель банка доступна только андеррайтеру (403 для клиента).
- Каталог продуктов, профиль компании, черновик заявки с шагом мастера, подача с `Idempotency-Key`.
- Стейт-машина: статус меняется только через `transition()` по таблице переходов
  ([`docs/state-machine.md`](docs/state-machine.md)), каждый переход пишется в неизменяемый аудит
  (`loan_application_aud`: UPDATE, DELETE и TRUNCATE запрещены триггером БД).
- Конвейер после подачи: `SUBMITTED → CHECKING → EXTERNAL_CHECK → SCORING` и один из пяти исходов.
- Правила, факторы и лимиты из YAML, снимки проверок и происхождение полей, идемпотентные команды и единственная выдача в БД.
- Очередь андеррайтера, ручное решение (комментарий обязателен), дозапрос данных и дозаполнение,
  оффер с аннуитетным платежом, принятие, подписание кодом, «Кредит выдан».
- Таймлайн статуса для клиента, аудит заявки для андеррайтера.
- Ошибки в формате RFC 7807 (`application/problem+json`), структурированные JSON-логи с `requestId` и `applicationId`.

### Демонстрационные ограничения

ЕГРЮЛ, ФНС и БКИ доступны через локальный WireMock; скоринг и политика выполняются по YAML-конфигурации.
Ставки синтетические. Подписание и выдача — симуляция, без SMS и реальных денег; код `123456` задаётся DEMO_SIGN_CODE.
Командные ИНН и существующий API сохранены; детали совместимости — в [assumptions.md](docs/assumptions.md).

### Фронтенд и браузерные проверки

```bash
cd frontend
npm ci
npm run generate:api
npm run typecheck
npm run build
npm run test:e2e
```

Для dev-режима: `npm run dev`, адрес http://localhost:5173, API должен работать на localhost:8000.
Playwright проверяет реальные Docker web/API в Google Chrome. Типы генерируются из OpenAPI.

### Тесты и линтер

Тесты идут против настоящего PostgreSQL. На каждый прогон пересоздаётся отдельная БД `credit_test` на сервере из
`DATABASE_URL`, миграции накатываются Alembic, затем выполняется настоящий seed.

```bash
# в Docker (БД поднимается сама)
docker compose --profile test run --rm tests

# локально (нужен uv и запущенная БД из compose)
cd backend
uv sync
DATABASE_URL=postgresql+psycopg://credit:credit@127.0.0.1:55432/credit uv run pytest

uv run ruff check . && uv run ruff format --check .
```

Среди тестов: все допустимые и недопустимые переходы стейт-машины, запись аудита и его неизменяемость, идемпотентная
подача, проверка суммы и срока по продукту, права доступа, формула аннуитета, идемпотентность seed, сверка моделей
с миграциями, а также совпадение `docs/api/openapi.yaml` и `docs/state-machine.md` с кодом.

### Контракт и документы

После изменения API или таблицы переходов перегенерируйте файлы (иначе тест упадёт):

```bash
cd backend
uv run python -m app.scripts.export_openapi        # docs/api/openapi.yaml
uv run python -m app.scripts.export_state_machine  # docs/state-machine.md
```

Журнал принятых решений: [`docs/decisions.md`](docs/decisions.md). Словарь данных: [`data-dictionary.md`](data-dictionary.md).

### Переменные окружения

Все переменные имеют значения по умолчанию, `.env` не обязателен. Полный список с описанием: [`.env.example`](.env.example).
Главное: `JWT_SECRET` (сменить), `DEMO_SIGN_CODE`, `CORS_ORIGINS`, `MOCKS_BASE_URL`. Паузы конвейера отключены; `PIPELINE_STEP_DELAY_SECONDS` оставлен только для совместимости окружения.

Ставка по кредиту = ключевая ставка ЦБ + спред продукта + риск-надбавка. Ключевая ставка в [`policy.yaml`](backend/app/domain/decision/policy.yaml): 14,0% на 2026-09-11 (решение Совета директоров Банка России). **Значение нужно сверить с cbr.ru на дату проверки** и при необходимости переопределить переменными `KEY_RATE_PCT` и `KEY_RATE_DATE` (пример: `KEY_RATE_PCT=15.5 KEY_RATE_DATE=2026-10-30 docker compose up --build`).

### Структура бэкенда

```
backend/
  app/
    api/          роутеры FastAPI, зависимости авторизации, сборка OpenAPI
    services/     сценарии клиента и андеррайтера (одна транзакция на действие)
    domain/       стейт-машина, конвейер, движок решения, оффер, таймлайн
    integrations/ интерфейс внешних проверок (ЕГРЮЛ, ФНС, БКИ)
    schemas/      Pydantic-схемы (camelCase снаружи)
    db/           модели SQLAlchemy
    seed/         идемпотентный seed
    scripts/      экспорт OpenAPI и стейт-машины, smoke-проверка
  alembic/        миграции
  tests/          pytest против PostgreSQL
```

<!-- backend:end -->
