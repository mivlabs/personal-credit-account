# Умный кредитный кабинет предпринимателя

[![CI](https://github.com/mivlabs/personal-credit-account/actions/workflows/ci.yml/badge.svg)](https://github.com/mivlabs/personal-credit-account/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)
![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black)
![PostgreSQL 16](https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

**Кредит для бизнеса без звонков и повторных анкет: подбор продукта, заявка, объяснимое решение и выдача в одном кабинете.**

<p align="center">
  <img src="docs/media/flow-approve.gif" width="860" alt="Клиент: вход, выбор продукта, заявка, одобрение, подписание кодом, кредит выдан">
</p>

Прототип кредитного конвейера для малого бизнеса (хакатон Альфа-Банка). Предприниматель (ИП или ООО) подбирает продукт,
подаёт заявку и видит решение с объяснением: одобрение, контроффер, ручная проверка, запрос данных или отказ.
Банк ведёт ту же заявку в том же продукте: очередь андеррайтера, ручное решение, аудит.
Данные о компании приходят из внешних проверок (ЕГРЮЛ, ФНС, БКИ); в прототипе это локальные моки с синтетическими данными.
Все аккаунты и деньги демонстрационные.

## Как это выглядит

Скриншоты сняты скриптом `npm run media` на синтетических данных (см. [`docs/verification.md`](docs/verification.md#медиа-readme-сессия-7)).

<table>
  <tr><th colspan="2" align="left">Кабинет клиента</th></tr>
  <tr>
    <td width="50%"><img src="docs/media/login.png" width="100%" alt="Экран входа и регистрации по ИНН"><br><sub><b>Вход и регистрация по ИНН.</b> Демо-аккаунты или свой валидный ИНН</sub></td>
    <td width="50%"><img src="docs/media/catalog.png" width="100%" alt="Каталог продуктов с подбором по цели"><br><sub><b>Каталог.</b> Подбор продукта по цели, ставка = ключевая + спред</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/wizard.png" width="100%" alt="Мастер заявки"><br><sub><b>Мастер заявки.</b> Данные компании уже подтянуты, черновик сохраняется сам</sub></td>
    <td><img src="docs/media/decision.png" width="100%" alt="Одобрение с оффером и блоком «Как принято решение»"><br><sub><b>Одобрение.</b> Оффер, разложение ставки, блок «Как принято решение»</sub></td>
  </tr>
  <tr>
    <td><img src="docs/media/counter-offer.png" width="100%" alt="Контроффер с объяснением лимита по платёжной нагрузке"><br><sub><b>Контроффер.</b> 10 млн запрошено, 6 млн доступно по платёжной нагрузке (срок 24 мес.)</sub></td>
    <td><img src="docs/media/timeline.png" width="100%" alt="Таймлайн статуса до «Кредит выдан»"><br><sub><b>Путь заявки.</b> От подачи до «Кредит выдан» (симуляция)</sub></td>
  </tr>
  <tr><th colspan="2" align="left">Панель банка</th></tr>
  <tr>
    <td><img src="docs/media/bank-queue.png" width="100%" alt="Очередь ручной проверки андеррайтера"><br><sub><b>Очередь андеррайтера.</b> Пограничные заявки с баллом и причиной</sub></td>
    <td><img src="docs/media/bank-review.png" width="100%" alt="Карточка заявки: проверки источников и решение специалиста"><br><sub><b>Карточка заявки.</b> Источники данных, факторы балла, решение с комментарием</sub></td>
  </tr>
</table>

<details>
<summary>Ещё экраны</summary>

<img src="docs/media/bank-snapshot.png" width="640" alt="Снимок решения в карточке заявки"><br>
<sub><b>Снимок решения.</b> Входы, лимит и формула, по которым считалось решение (хранится вместе с заявкой)</sub>

</details>

## Требования

| Что | Значение |
|---|---|
| ПО | Docker Desktop или Docker Engine с Compose v2 (`docker compose version`) |
| Свободные порты | `3000` (веб), `8000` (API), `8081` (моки). Порт PostgreSQL на хост не публикуется. Меняются переменными `WEB_PORT`, `API_PORT`, `MOCKS_PORT` |
| Память | Замер `docker stats --no-stream` на поднятом стеке в простое (Windows 10, Docker Desktop, 4 ядра, лимит VM 3,8 ГиБ): api ≈ 69 МиБ, db ≈ 41 МиБ, mocks ≈ 135 МиБ, web ≈ 4 МиБ, всего около 250 МиБ. Под нагрузкой больше; сборка образов (Node) требует больше памяти, чем работа стека |
| Диск | Образы стека: api 316 МБ, web 94 МБ, PostgreSQL 420 МБ, WireMock 462 МБ |
| Интернет | Нужен только для сборки образов и скачивания зависимостей. После сборки стек работает без сети |

## Запуск

```bash
git clone <адрес репозитория>
cd personal-credit-account
docker compose up --build
```

Первая сборка занимает несколько минут. При старте `api` сам накатывает миграции и seed. Готовность видна по
`docker compose ps`: у `db`, `mocks`, `api`, `web` должно быть `healthy`.

| Сервис | Адрес | Что это |
|---|---|---|
| Веб-интерфейс | <http://localhost:3000> | кабинет клиента и панель банка |
| Swagger UI | <http://localhost:8000/docs> | интерактивная документация API |
| Health | <http://localhost:8000/health> | проверка API и БД |
| API | <http://localhost:8000/api/v1> | FastAPI; контракт: [`docs/api/openapi.yaml`](docs/api/openapi.yaml) |
| Моки (WireMock) | <http://localhost:8081> | ЕГРЮЛ / ФНС / БКИ, синтетические данные |
| PostgreSQL | только внутри сети compose (`db:5432`) | на хост не публикуется; для отладки см. [локальные тесты](#тесты-и-линтер), логин и пароль `credit` |

Сброс данных: `docker compose down -v` (удаляет БД и сохранённый секрет JWT).

## Тестовые аккаунты

Пароль у всех: **`demo1234`**. ИНН, компании и ожидаемые исходы: [`docs/test-accounts.md`](docs/test-accounts.md).

| Логин | Роль | Сценарий |
|---|---|---|
| `client_fast` | клиент (ИП) | быстрое одобрение |
| `client_counter` | клиент (ООО) | контроффер |
| `client_manual` | клиент (молодое ООО) | ручная проверка |
| `client_info` | клиент (ООО без отчётности ФНС) | дозапрос данных |
| `client_reject` | клиент (ООО, просрочка 120 дней) | отказ |
| `client_timeout` | клиент (ООО, БКИ не отвечает) | сбой источника → ручная проверка |
| `underwriter` | андеррайтер | очередь и ручное решение |

## Проверьте на своём ИНН

Любой валидный ИНН можно зарегистрировать самому: вкладка «Зарегистрироваться по ИНН» на экране входа или
`POST /api/v1/auth/register`. ИНН проверяется по контрольным числам ФНС. Моки отвечают на любой валидный ИНН,
а сценарий задаёт **9-я цифра** ИНН организации (10 знаков); у ИП (12 знаков) это **10-я цифра**. Последняя цифра
контрольная и свободно не выбирается.

Заявка: «Оборотный кредит», срок 12 месяцев.

| Цифра | Пример ИНН (ООО) | Сумма | Исход |
|---|---|---|---|
| 0 | `7702000004` | 1 млн | отказ: просрочка 120 дней |
| 1 | `7702000011` | 1 млн | одобрение |
| 2 | `7702000029` | 2 млн | одобрение |
| 3 | `7702000036` | 3 млн | одобрение |
| 4 | `7702000043` | 10 млн | контроффер: около 4,7 млн при сроке 12 мес. и **6 млн при сроке от 24 мес.** |
| 5 | `7702000050` | 3 млн | ручная проверка: компании 9 месяцев |
| 6 | `7702000068` | 2 млн | запрос выручки → после ответа одобрение |
| 7 | `7702000075` | 1 млн | БКИ отвечает дольше бюджета 3 с → ручная проверка |
| 8 | `7702000082` | 1 млн | отказ: компания не действует |
| 9 | `7702000090` | 1 млн | БКИ недоступен (503) → ручная проверка |

<p align="center">
  <img src="docs/media/flow-own-inn.gif" width="720" alt="Регистрация по своему ИНН: профиль из ЕГРЮЛ, подача, контроффер">
</p>

Примеры для ИП, запрос `curl` и подробности: [`docs/test-accounts.md`](docs/test-accounts.md#проверка-на-своём-инн).
Логин и ИНН уникальны: повторная регистрация возвращает 409.

## Сценарий проверки на 10 минут

Открыть <http://localhost:3000>, пароль везде `demo1234`.

1. **Одобрение и выдача.** Войти как `client_fast`, выбрать «Оборотный кредит», сумма 1 500 000 ₽, срок 12 мес., подать
   заявку. Конвейер сразу даёт `APPROVED` и блок «Как принято решение» (входы с источниками, факторы, ставка).
   Принять предложение, ввести код `123456`, подписать: статус «Кредит выдан» (`ISSUED`, симуляция).
2. **Контроффер.** `client_counter`, оборотный, 10 000 000 ₽, срок 24 мес.: контроффер на 6 000 000 ₽. При сроке 12 мес.
   сумма ниже (≈ 4,4 млн ₽) из-за платёжной нагрузки. Принять и подписать.
3. **Ручная проверка.** `client_manual`, оборотный, 1 500 000 ₽: статус `MANUAL_REVIEW`. Выйти, войти как `underwriter`,
   открыть заявку в очереди, принять решение с обязательным комментарием. Вернуться под клиентом и принять оффер.
4. **Дозапрос.** `client_info`, оборотный, 1 500 000 ₽: `NEEDS_INFO` (ФНС не отдала выручку). Ввести годовую выручку
   12 000 000 ₽: повторный скоринг даёт одобрение.
5. **Отказ.** `client_reject`, оборотный, 1 500 000 ₽: `REJECTED` с причиной простым языком (просрочка 120 дней).
6. **Свой ИНН.** На экране входа «Зарегистрироваться по ИНН», например `7702000011` (одобрение) или `7702000043` (контроффер).

<p align="center">
  <img src="docs/media/flow-underwriter.gif" width="720" alt="Андеррайтер: очередь, разбор заявки, решение с комментарием, клиент видит оффер">
</p>

Те же сценарии с ожидаемыми цифрами: [`docs/test-scenarios.md`](docs/test-scenarios.md).

## Процесс заявки и архитектура

Статусы и переходы ниже совпадают с таблицей `TRANSITIONS` в коде ([`docs/state-machine.md`](docs/state-machine.md), файл сверяется тестом).

```mermaid
stateDiagram-v2
    [*] --> DRAFT
    DRAFT --> SUBMITTED: Клиент
    SUBMITTED --> CHECKING: Система
    CHECKING --> NEEDS_INFO: Система
    CHECKING --> EXTERNAL_CHECK: Система
    NEEDS_INFO --> CHECKING: Клиент
    EXTERNAL_CHECK --> SCORING: Система
    SCORING --> APPROVED: Система
    SCORING --> COUNTER_OFFER: Система
    SCORING --> NEEDS_INFO: Система
    SCORING --> MANUAL_REVIEW: Система
    SCORING --> REJECTED: Система
    MANUAL_REVIEW --> APPROVED: Андеррайтер
    MANUAL_REVIEW --> COUNTER_OFFER: Андеррайтер
    MANUAL_REVIEW --> NEEDS_INFO: Андеррайтер
    MANUAL_REVIEW --> REJECTED: Андеррайтер
    MANUAL_REVIEW --> EXTERNAL_CHECK: Андеррайтер
    APPROVED --> OFFER_ACCEPTED: Клиент
    APPROVED --> DECLINED_BY_CLIENT: Клиент
    COUNTER_OFFER --> OFFER_ACCEPTED: Клиент
    COUNTER_OFFER --> DECLINED_BY_CLIENT: Клиент
    APPROVED --> EXPIRED: Система
    COUNTER_OFFER --> EXPIRED: Система
    NEEDS_INFO --> EXPIRED: Система
    DRAFT --> WITHDRAWN: Клиент
    NEEDS_INFO --> WITHDRAWN: Клиент
    MANUAL_REVIEW --> WITHDRAWN: Клиент
    OFFER_ACCEPTED --> SIGNING: Система
    SIGNING --> ISSUED: Клиент
    REJECTED --> [*]
    ISSUED --> [*]
    DECLINED_BY_CLIENT --> [*]
    WITHDRAWN --> [*]
    EXPIRED --> [*]
```

Компоненты и вызовы: [`docs/architecture.md`](docs/architecture.md). Сервисы Docker Compose: `web`, `api`, `db`, `mocks`.

```mermaid
flowchart LR
    Client[Клиент] --> Web[React / TypeScript / Ant Design]
    Bank[Андеррайтер] --> Web
    Web --> Nginx[Nginx: SPA и /api]
    Nginx --> API[FastAPI: роли и команды]
    API --> Domain[Стейт-машина / скоринг / политика / офферы]
    API --> DB[(PostgreSQL 16)]
    Domain --> DB
    Domain --> HTTP[HTTP-клиент: таймауты и повторы]
    HTTP --> Mocks[WireMock: ЕГРЮЛ / ФНС / БКИ]
```

## Как принимается решение

Решение детерминированное и объяснимое; подробности и все параметры: [`docs/decision-policy.md`](docs/decision-policy.md).

- **Стоп-факторы:** компания не действует, бизнесу меньше 6 месяцев, просрочка больше 90 дней. Дают отказ без скоринга.
- **Скоринг:** сумма баллов 0–100 по возрасту компании, выручке, долговой нагрузке, просрочкам и отрасли.
  ≥ 70 автоматическое решение, 40–69 ручная проверка, < 40 отказ.
- **Лимит:** минимум из платёжной нагрузки (платежи не больше 40% месячной выручки с учётом текущего долга),
  доли выручки и максимума продукта. Если запрос выше лимита, предлагается контроффер.
- **Приоритет данных:** подтверждённый источник (ФНС, БКИ) важнее анкеты; расхождение больше 20% уходит на ручную проверку.
- **Сбой источника** (ЕГРЮЛ, ФНС, БКИ недоступны или не успели за 3 с) не превращается в отказ, а ведёт к ручной проверке.
- **Ставка** = ключевая ставка Банка России (14% на 23.10.2026, значение нужно сверить с cbr.ru) + спред продукта
  (2,5 / 0,9 / 5 п.п.) + риск-надбавка 1 п.п. при балле ниже 85. Разложение видно в каталоге, в оффере и в блоке
  «Как принято решение». Спреды и надбавка синтетические.

## Искусственный интеллект

В проверяемой версии языковые модели **не используются намеренно**: решение должно быть воспроизводимым и
проверяемым по правилам (`policy.yaml`), а систему запускают без GPU и без внешних сервисов. ИИ не заявлен как
реализованный. В развитии модель можно подключить для задач вокруг решения (разбор документов, пояснения клиенту),
не заменяя детерминированную политику: через OpenAI-совместимый клиент с настройками `LLM_BASE_URL`, `LLM_API_KEY`,
`LLM_MODEL` и open-weights моделью в контуре банка. Это план: в коде этих настроек пока нет.

## Карта документации

| Документ | О чём |
|---|---|
| [`docs/implementation-scope.md`](docs/implementation-scope.md) | объём реализации и соответствие user stories |
| [`docs/architecture.md`](docs/architecture.md) | компоненты, транзакции, идемпотентность |
| [`docs/data-model.md`](docs/data-model.md), [`docs/design/data-dictionary.md`](docs/design/data-dictionary.md) | модель данных и словарь |
| [`docs/api.md`](docs/api.md), [`docs/api/openapi.yaml`](docs/api/openapi.yaml) | API: обзор и контракт |
| [`docs/state-machine.md`](docs/state-machine.md) | статусы заявки и таблица переходов |
| [`docs/decision-policy.md`](docs/decision-policy.md) | кредитная политика, скоринг, лимит, ставка |
| [`docs/test-accounts.md`](docs/test-accounts.md), [`docs/test-scenarios.md`](docs/test-scenarios.md) | аккаунты, ИНН и воспроизводимые сценарии |
| [`docs/assumptions.md`](docs/assumptions.md) | допущения и ограничения прототипа |
| [`docs/targets.md`](docs/targets.md) | целевые показатели и замеры |
| [`docs/production.md`](docs/production.md) | что меняется при переходе в промышленную эксплуатацию |
| [`docs/research.md`](docs/research.md) | обоснование решений, гипотезы для проверки |
| [`docs/verification.md`](docs/verification.md) | фактически выполненные проверки |
| [`docs/decisions.md`](docs/decisions.md) | журнал принятых решений |
| [`THIRD_PARTY_NOTICES`](THIRD_PARTY_NOTICES) | лицензии зависимостей и шрифтов |

## Ограничения и допущения прототипа

Полный список: [`docs/assumptions.md`](docs/assumptions.md); путь в промышленную эксплуатацию: [`docs/production.md`](docs/production.md).

| Область | Как в прототипе |
|---|---|
| ЕГРЮЛ, ФНС, БКИ | локальный WireMock, синтетические ответы по 9-й цифре ИНН |
| Подписание и выдача | симуляция: код `123456`, без SMS, ЭП и реальных денег; подсказка с кодом только при `DEMO_MODE=true` |
| Политика и ставки | синтетические пороги и спреды, не политика банка; ключевая ставка берётся из `policy.yaml` |
| Конвейер | синхронный, в одной транзакции с подачей; HTTP-вызовы к источникам внутри транзакции, бюджет 3 с |
| Ограничение попыток входа и регистрации | счётчики в памяти одного процесса |
| Сроки оффера и запроса данных | истекают при первой команде клиента или скриптом, планировщика нет |
| Аутентификация | логин и пароль, JWT; SSO сотрудников банка нет |
| Языковые модели | не используются |

<!-- backend:start -->

## Бэкенд и разработка

Версии образов зафиксированы точными тегами, зависимости бэкенда — `uv.lock`.

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
Закреплённые ИНН seed и существующий API сохранены; детали совместимости — в [assumptions.md](docs/assumptions.md).

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

Тесты разделены на два набора:

- `tests/unit` — движок решения, ставка, офферы, подбор продукта, стейт-машина (таблица переходов), политика повторов
  HTTP-клиента. Не требует Postgres и WireMock: `cd backend && uv run pytest tests/unit`.
- `tests/integration` — всё остальное, против настоящего PostgreSQL и WireMock. На каждый прогон пересоздаётся отдельная
  БД `credit_test` на сервере из `DATABASE_URL`, миграции накатываются Alembic, затем выполняется настоящий seed.
  Перед стартом проверяются `MOCKS_BASE_URL/__admin/health` и подключение к Postgres; если чего-то нет, pytest
  завершается с кодом 2 и подсказкой, как поднять (`docker compose -f docker-compose.yml -f docker-compose.override.example.yml up -d db mocks`).

```bash
# в Docker (БД поднимается сама)
docker compose --profile test run --rm tests

# локально (нужен uv и запущенная БД из compose); порт БД на хост открывает docker-compose.override.example.yml
# (127.0.0.1:5433, меняется переменной DB_HOST_PORT), в обычном `docker compose up` он не публикуется
docker compose -f docker-compose.yml -f docker-compose.override.example.yml up -d db mocks
cd backend
uv sync
uv run pytest tests/unit        # без инфраструктуры
DATABASE_URL=postgresql+psycopg://credit:credit@127.0.0.1:5433/credit MOCKS_BASE_URL=http://127.0.0.1:8081 uv run pytest
# на Windows указывайте 127.0.0.1, а не localhost: попытка IPv6 (::1) даёт таймаут на каждое подключение

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

Журнал принятых решений: [`docs/decisions.md`](docs/decisions.md). Словарь данных: [`docs/design/data-dictionary.md`](docs/design/data-dictionary.md).

### Переменные окружения

Все переменные имеют значения по умолчанию, `.env` не обязателен. Полный список с описанием: [`.env.example`](.env.example).
Главное: `JWT_SECRET` (пусто = случайный секрет на volume `jwtdata`), `DEMO_MODE` (по умолчанию `true`: `signHint` с кодом подписи в ответе принятия оффера; в `false` подсказки нет), `DEMO_SIGN_CODE`, `CORS_ORIGINS`, `MOCKS_BASE_URL`. Паузы конвейера отключены; `PIPELINE_STEP_DELAY_SECONDS` оставлен только для совместимости окружения.

Ставка по кредиту = ключевая ставка ЦБ + спред продукта + риск-надбавка. Ключевая ставка в [`policy.yaml`](backend/app/domain/decision/policy.yaml): 14,0% на 2026-10-23 (решение Совета директоров Банка России). **Значение нужно сверить с cbr.ru на дату проверки** и при необходимости переопределить переменными `KEY_RATE_PCT` и `KEY_RATE_DATE` (пример: `KEY_RATE_PCT=15.5 KEY_RATE_DATE=2026-10-30 docker compose up --build`).

### Сроки, отзыв и подбор продукта

- Оффер действует `OFFER_TTL_DAYS` (30) дней, запрос данных `INFO_REQUEST_TTL_DAYS` (14). Истёкшие заявки получают статус `EXPIRED` при первой команде клиента (ответ 409 `EXPIRED`) или разом скриптом:
  `cd backend && uv run python -m app.scripts.expire_stale` (в Docker: `docker compose run --rm api python -m app.scripts.expire_stale`).
- Клиент может отозвать заявку (`POST /applications/{id}/withdraw`), андеррайтер может повторно проверить источники (`POST /underwriter/applications/{id}/recheck`).
- Подбор продукта: `POST /products/recommendations`, правила в [`recommendation.yaml`](backend/app/domain/recommendation.yaml).

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
  tests/unit/     быстрые тесты без инфраструктуры
  tests/integration/  pytest против PostgreSQL и WireMock
```

<!-- backend:end -->
