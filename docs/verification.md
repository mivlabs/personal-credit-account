# Фактически выполненные проверки

Дата: 2026-10-24, локальный стенд Windows / Docker Desktop, часовой пояс Europe/Moscow.

| Проверка | Результат |
|---|---|
| docker compose up --build -d api web | Образы собраны; web, api, db и mocks healthy |
| Backend frozen install в образах | uv sync --frozen для runtime и dev выполнен |
| Frontend установка по lock | npm install сформировал package-lock.json; Docker npm ci прошёл |
| docker compose --profile test run --build --rm tests | 107 passed, PostgreSQL + настоящий WireMock |
| ruff check . из backend | Все проверки прошли |
| ruff format --check . из backend | 83 Python-файла соответствуют формату |
| npm run generate:api | Типы сгенерированы из экспортированного OpenAPI |
| npm run typecheck / production build | Прошли локально и в Docker |
| npm run test:e2e | 4 passed, Google Chrome, реальный Nginx/API/PostgreSQL/WireMock |
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
