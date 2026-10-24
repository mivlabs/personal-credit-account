# Фактически выполненные проверки

Дата: 2026-10-24 (перепроверено после сессии 3 на чистом стенде `docker compose down -v && up --build -d`), локальный стенд Windows / Docker Desktop, часовой пояс Europe/Moscow.

| Проверка | Результат |
|---|---|
| docker compose up --build -d api web | Образы собраны; web, api, db и mocks healthy |
| Backend frozen install в образах | uv sync --frozen для runtime и dev выполнен |
| Frontend установка по lock | npm install сформировал package-lock.json; Docker npm ci прошёл |
| docker compose --profile test run --build --rm tests | 199 passed (54 unit + 145 integration), PostgreSQL + настоящий WireMock |
| ruff check . из backend | Все проверки прошли |
| ruff format --check . из backend | 106 Python-файлов соответствуют формату |
| npm run generate:api | Типы сгенерированы из экспортированного OpenAPI |
| npm run typecheck / production build | Прошли локально и в Docker |
| npm run test:e2e | 4 passed, Google Chrome, реальный Nginx/API/PostgreSQL/WireMock (в сценарий ручного решения добавлено подтверждение «выше расчётного лимита» после п.1.3) |
| python -m app.scripts.smoke | Все проверки API, таймлайна, аудита и изоляции ролей прошли |
| python scripts/check-persistence.py | Заявка, оффер и полный аудит сохранились после рестарта четырёх контейнеров и повторного seed |
| git diff --check | Ошибок пробелов нет |

Backend покрывает пороги 39/40/69/70, стоп-факторы и неполные данные, пять исходов, нулевую выручку, лимиты и контроффер, роли, состояния, дозапрос, округление аннуитета, HTTP timeout/503/404/разрыв соединения, бюджет повторов, конкурентные подачи/принятия/подписи, единственную выдачу и откат незавершённого конвейера. Модели сверяются с Alembic, документация OpenAPI и стейт-машины — с приложением.

Браузерные сценарии: одобрение с сохранением черновика после reload; ручное решение со сменой клиент/банк/клиент; дозапрос с повторной оценкой; контроффер и отказ. Screenshots при прогоне сохраняются в frontend/test-results (не коммитятся).

Ограничения проверки: не выполнялось клонирование в новый каталог и полная сборка без Docker-кеша; использован существующий named volume. Не проверялись актуальная ставка ЦБ, реальные банковские интеграции, нагрузочное и независимое security-тестирование. Сборщик сообщает о JS-файле около 1,28 МБ (около 401 КБ gzip); дальнейшее разделение загрузки модулей оставлено следующей итерации. Приложение и зависимости на исполнении не требуют внешних сервисов, но загрузка npm/Python-зависимостей и образов при сборке требует сети.

Перезапуски и тесты создают только синтетические заявки. Основная БД не очищалась; тестовый профиль пересоздаёт отдельную credit_test. Исходные C4 и BPMN сохранены, удалённые репозитории, коммиты и релизы не создавались.

## Аудит P1/P2: сессия 1

Проверка: `ruff check`/`ruff format --check` чисто; `pytest -m "not live_integrations"` — 134 passed (PostgreSQL, без Docker и WireMock); `npm run typecheck` и `npm run build` прошли. Не выполнялись: 9 live-тестов с WireMock и docker compose `tests` (нет Docker в окружении сессии); их нужно прогнать перед сдачей.

| Пункт | Что сделано | Ключевые файлы | Тесты | Не сделано / примечание |
|---|---|---|---|---|
| 1.1 Ставка | Одна функция ставки: ключевая ЦБ (14,0%, 2026-09-11) + спред + риск-надбавка; автооффер, ручное решение, каталог; `rate_nval` заполняет seed той же функцией; `rateFrom`, `rateBreakdown` в продукте и оффере; env `KEY_RATE_PCT`, `KEY_RATE_DATE` | `domain/pricing.py`, `decision/policy.yaml`, `decision/config.py`, `core/config.py`, `services/mappers.py`, `seed/run.py` | `tests/test_pricing.py` | Ожидание ставки в `test_full_path_to_issued` изменено намеренно: 18,5 → 17,5 |
| 1.2 Снимок | Миграция 0003 `decision_snapshot` JSONB с бэкфиллом; структурированный снимок AUTO и MANUAL; `snapshot` в карточке андеррайтера; `decisionExplanation` у клиента; блок «Как принято решение» и вывод снимка | `alembic/versions/0003_decision_snapshot.py`, `decision/snapshot.py`, `decision/service.py`, `services/underwriter.py` | `tests/test_snapshot.py` (пять исходов, скрытие комментария, бэкфилл) | У AUTO теперь `comment_desc = NULL` |
| 1.3 Лимит | `overrideLimit` в `DecisionRequest`, 422 `LIMIT_EXCEEDED`, `autoLimit` в карточке, `limitUnknown`, текст аудита | `services/underwriter.py`, `schemas/underwriter.py` | `tests/test_snapshot.py` | — |
| 1.4 AS_OF_DATE | Возраст от `AS_OF_DATE` или сегодня (Europe/Moscow); `asOfDate` в снимке; фиксация в conftest и compose `tests` | `domain/clock.py`, `decision/engine.py`, `tests/conftest.py`, `docker-compose.yml` | `tests/test_decision_engine.py` | Исходы seed на сегодняшней дате не изменились (`docs/test-accounts.md`) |
| 1.5 Приоритет источников | Источник приоритетнее анкеты; расхождение >20% → `MANUAL_REVIEW`, `DATA_MISMATCH`; выручка только от клиента → лимит × 0,5 | `decision/engine.py`, `policy.yaml` | `tests/test_snapshot.py`, `tests/test_decision_engine.py` | При расхождении `client_counter` с 1 млрд уходит на ручную проверку, а не на контроффер 6 млн |

Для следующей сессии: `credit_decision.decision_snapshot` (JSONB); `domain/pricing.compute_rate` / `rate_from`; `domain/clock.as_of_date`; `decision/snapshot.py` (`build_auto_snapshot`, `build_manual_snapshot`, `explain`); `mappers.latest_auto_snapshot`; `DecisionRequest.overrideLimit`; `ApplicationOut.decisionExplanation`; `UnderwriterApplicationOut.autoLimit`; новые параметры политики `data_mismatch_pct`, `client_declared_limit_factor`; новых статусов нет.

## Аудит P1/P2: сессия 2

Проверка: `ruff check`/`ruff format --check` чисто; `pytest -m "not live_integrations"` локально против PostgreSQL и WireMock из compose — 182 passed (после правки `test_openapi` перепроверены `test_openapi` и `test_recommendation`); `npm run typecheck` и `npm run build` проходят. Docker-прогон `--profile test` не делался (по условию сессии минимум Docker), e2e Playwright не запускался.

| Пункт | Что сделано | Ключевые файлы | Тесты | Не сделано / примечание |
|---|---|---|---|---|
| 2.1 Мёртвый переход | Удалён `EXTERNAL_CHECK → MANUAL_REVIEW`; `assumptions.md` п.3 описывает путь «сбой → SCORING → MANUAL_REVIEW (EXTERNAL_UNAVAILABLE)» | `domain/state_machine.py`, `docs/assumptions.md` | `test_state_machine.py` | — |
| 2.2 Recheck | `POST /underwriter/applications/{id}/recheck`, переход `MANUAL_REVIEW → EXTERNAL_CHECK`, конвейер заново, `RECHECK` в `availableActions`, кнопка в панели банка | `services/underwriter.py`, `api/routers/underwriter.py`, `services/mappers.py` | `test_recheck.py` (timeout→снова MANUAL_REVIEW с новыми проверками, 409, 403) | — |
| 2.3 Отзыв | Статус `WITHDRAWN`, `POST /applications/{id}/withdraw` с `Idempotency-Key`, `WITHDRAW` в `availableActions`, пропадает из очереди по умолчанию | `services/applications.py`, `domain/enums.py`, `domain/state_machine.py` | `test_withdraw.py` | — |
| 2.4 Сроки | Миграция 0004 (`loan_offer.valid_until_dttm`, `info_request.due_dttm`), `OFFER_TTL_DAYS`/`INFO_REQUEST_TTL_DAYS`, статус `EXPIRED`, ленивая проверка, `ErrorCode.EXPIRED`, `core/clock.now()`, `python -m app.scripts.expire_stale`, `offer.validUntil`, `infoRequests[].dueAt` | `services/expiry.py`, `core/clock.py`, `scripts/expire_stale.py`, `alembic/versions/0004_expiry_deadlines.py` | `test_expiry.py` (фикстура `travel`) | Ожидание `dim_application_status` в `test_seed_and_schema` изменено 14→16 намеренно (WITHDRAWN, EXPIRED). Планировщика нет |
| 2.5 Подбор продукта | `domain/recommendation.yaml` + pydantic-валидация, `POST /products/recommendations` (`matchScore`, `recommended`, `reasons`, `rateFrom`), каталог на фронте вызывает эндпоинт и показывает причины | `domain/recommendation.py`, `services/catalog.py`, `api/routers/products.py`, `frontend/src/Catalog.tsx` | `test_recommendation.py` (7 категорий, сумма/срок вне диапазона, 401/403/422) | `test_openapi` дополнен тремя новыми эндпоинтами намеренно |

Для следующей сессии: статусы `WITHDRAWN` и `EXPIRED` (конечные); `app.core.clock.now()` вместо `datetime.now` в бизнес-коде; `services/expiry.ensure_not_expired` и `expire_all_stale`; действия `RECHECK`, `WITHDRAW`; `ErrorCode.EXPIRED`; `PurposeCategory`; фикстура `travel(days)` в `tests/conftest.py`; миграция 0004 — следующая свободная 0005. Не-бизнес-вызовы `datetime.now` остались в `core/security.py` (JWT) и `integrations/http.py` (логи вызовов).

## Аудит P1/P2: сессия 3

Проверка (2026-10-24, чистый стенд `docker compose down -v && docker compose up --build -d`, все четыре сервиса healthy): `ruff check`/`ruff format --check` чисто; `docker compose --profile test run --build --rm tests` — 199 passed; `uv run pytest tests/unit` — 54 passed без Postgres и WireMock; `npm run typecheck` и `npm run build` прошли; `python -m app.scripts.smoke` — «всё в порядке» (на Windows запускать с `PYTHONIOENCODING=utf-8`, иначе вывод кириллицы падает в cp1251); `npm run test:e2e` — 4 passed; `scripts/check-persistence.py` — PASS. Перезапуск api сохранил JWT-секрет с volume `jwtdata`: токен, выданный до рестарта, остался действительным. Проверка не выполнялась в Docker-контексте для `docker compose build web` с холодным кешем сверх уже пройденной сборки.

| Пункт | Что сделано | Ключевые файлы | Тесты | Не сделано / примечание |
|---|---|---|---|---|
| 3.1 Параллельные проверки | ЕГРЮЛ/ФНС/БКИ в `ThreadPoolExecutor`, общий бюджет `EXTERNAL_CHECKS_BUDGET_SECONDS` (3 с), ретраи внутри бюджета; записи `external_check` создаются в основной сессии; стаб ИНН `7701000099` (БКИ с задержкой 2 с); `client_timeout` в документации = «БКИ недоступен (503)» | `integrations/http.py`, `core/config.py`, `mocks/wiremock/mappings/*-7701000099.json`, `docs/test-accounts.md` | `test_slow_source_is_timeout_within_budget`, `test_sources_are_polled_in_parallel` | HTTP-вызовы остались внутри транзакции под блокировкой строки (вынос потребовал бы переделки атомарной подачи): описано в `assumptions.md` |
| 3.2 Безопасность | JWT-секрет: пустой/демо/короче 32 → случайный в `/app/data/jwt_secret` (volume `jwtdata`); лимит входа 5 неудач/5 мин на логин+IP → 429 `TOO_MANY_REQUESTS` + `Retry-After`; `signHint` только при `DEMO_MODE=true` | `core/security.py`, `services/auth.py`, `core/errors.py`, `docker-compose.yml`, `backend/Dockerfile`, `.env.example` | `test_token_signed_with_old_demo_secret_is_rejected`, `test_weak_secret_is_replaced_and_persisted`, `test_login_rate_limit_and_reset`, `test_successful_login_resets_failure_counter`, `test_sign_hint_only_in_demo_mode` | Лимитер в памяти одного процесса (в `assumptions.md`) |
| 3.3 Тесты | `tests/unit` (без инфраструктуры) и `tests/integration`; проверка `MOCKS_BASE_URL/__admin/health` и Postgres перед интеграционной сессией, иначе `pytest.exit(returncode=2)` с подсказкой | `tests/conftest.py`, `tests/integration/conftest.py`, `tests/unit/*` | 54 unit + 145 integration | На Windows в `DATABASE_URL`/`MOCKS_BASE_URL` нужен `127.0.0.1`, а не `localhost` (иначе таймаут IPv6 на каждое подключение, прогон 265 с вместо 5 с): отмечено в README |
| 3.4 Уборка | Внутренние материалы вынесены в `../_internal/`, убраны из индекса; артефакты проектирования в `docs/design/`; `data-model-conceptual.png`; ссылки поправлены, битых относительных ссылок в markdown нет | `docs/design/*`, `README.md`, `docs/architecture.md`, `docs/data-model.md`, `docs/source/README.md` | скрипт проверки ссылок | — |
| 3.5 Образы | `node:22.23.4-alpine3.24`, `nginx:1.30.6-alpine3.24` (наличие тегов проверено `docker manifest inspect`) | `frontend/Dockerfile` | `docker compose build web`, web healthy | Версий этих образов нет в `export-notices.py` и `third-party-inventory.json`, обновлять нечего |
| Прочее | Исправлен e2e «Ручное решение»: после п.1.3 нужна отметка «выше расчётного лимита» | `frontend/e2e/credit.spec.ts` | `npm run test:e2e` 4 passed | — |

Для следующей сессии: `HttpExternalChecks._call` (только HTTP, возвращает попытки) и `_record` (запись в сессию); `Settings.external_checks_budget_seconds`, `demo_mode`, `login_max_failures`, `login_window_seconds`, `jwt_secret_file`; `core.security.get_jwt_secret()`; `ErrorCode.TOO_MANY_REQUESTS`; `services.auth.reset_login_limiter()`; `AcceptOfferResponse.signHint` теперь необязателен; тестовые хелперы (`Flow`, `fakes`) живут в `tests/integration/`.

## Сводка по трём сессиям

| Сессия | Содержание | Коммиты |
|---|---|---|
| 1 | Единая ставка, возраст от `AS_OF_DATE`, снимок решения, переопределение лимита, приоритет источников | 9e6775c, d70ebfd, 43b5d30, a6a5861, 8ff7384 |
| 2 | Мёртвый переход, recheck, `WITHDRAWN`, сроки и `EXPIRED`, подбор продукта | ed26341, f5b57e2, 227ac6e, 0a05809, bd02c5f |
| 3 | Параллельные проверки, безопасность, unit/integration, уборка репозитория, закреплённые образы | ab6875f, b36f557, aa4fb43, b5135f3, e5a91c3 |
