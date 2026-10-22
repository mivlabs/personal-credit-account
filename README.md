# Умный кредитный кабинет предпринимателя

Прототип кредитного конвейера для малого бизнеса (хакатон Альфа-Банка): клиент проходит путь от выбора продукта
до выдачи кредита, а банк ведёт ту же заявку в том же продукте.

> Общие разделы README (назначение, архитектура, сценарии проверки, THIRD_PARTY_NOTICES) пишет Миша.
> Раздел ниже про бэкенд ведёт Никита: между маркерами `backend:start` и `backend:end`.

<!-- backend:start -->

## Бэкенд: запуск и проверка

Нужен только Docker (Compose v2). Всё остальное внутри образов, версии зафиксированы точными тегами и `uv.lock`.

### Запуск одной командой

```bash
docker compose up --build
```

Первая сборка занимает несколько минут. При старте контейнер `api` сам накатывает миграции Alembic и seed
(справочники, демо-компании, аккаунты), затем запускает сервер. Готовность видна по healthcheck:
`docker compose ps` показывает `healthy` у `db`, `api`, `mocks`.

| Сервис | Адрес | Что это |
|---|---|---|
| API ядра | <http://localhost:8000> | FastAPI, префикс `/api/v1` |
| Swagger UI | <http://localhost:8000/docs> | интерактивная документация |
| OpenAPI | [`docs/api/openapi.yaml`](docs/api/openapi.yaml) | зафиксированный контракт |
| Health | <http://localhost:8000/health> | проверка БД |
| Моки (WireMock) | <http://localhost:8081> | ЕГРЮЛ / ФНС / БКИ (стабы пишет Миша) |
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
- Конвейер после подачи: `SUBMITTED → CHECKING → EXTERNAL_CHECK → SCORING → MANUAL_REVIEW`.
- Очередь андеррайтера, ручное решение (комментарий обязателен), дозапрос данных и дозаполнение,
  оффер с аннуитетным платежом, принятие, подписание кодом, «Кредит выдан».
- Таймлайн статуса для клиента, аудит заявки для андеррайтера.
- Ошибки в формате RFC 7807 (`application/problem+json`), структурированные JSON-логи с `requestId` и `applicationId`.

### Что пока заглушка

- **Внешние проверки (ЕГРЮЛ, ФНС, БКИ) отключены:** клиент к WireMock появится позже, интерфейс готов
  (`app/integrations/base.py`).
- **Скоринг не подключён:** движок решения (`app/domain/decision/engine.py`) отправляет любую заявку на ручную проверку.
  Пока для демо-пути заявку решает андеррайтер вручную.
- Подписание — симуляция: код берётся из `DEMO_SIGN_CODE` (по умолчанию `123456`), реальных SMS нет.

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
Главное: `JWT_SECRET` (сменить), `DEMO_SIGN_CODE`, `CORS_ORIGINS`, `PIPELINE_STEP_DELAY_SECONDS` (пауза между шагами
конвейера, чтобы на демо были видны этапы; по умолчанию 1 с).

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
