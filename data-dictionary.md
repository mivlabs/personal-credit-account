# Словарь данных · Умный кредитный кабинет

Логическая модель — страница «Логическая модель» в `data-model.drawio`. Концептуальная — страница «Концептуальная модель» там же: только сущности и связи, без атрибутов и ключей.

**Чем логическая модель отличается от концептуальной:**
- появились ключи (PK, FK) и атрибуты;
- «Пользователь» превратился в `app_user`, потому что `user` — зарезервированное слово PostgreSQL;
- роль пользователя и статус заявки вынесены в справочники `dim_user_role` и `dim_application_status` (3НФ: название статуса не зависит от заявки);
- «Кредитное решение» разложено на `credit_decision` и `decision_factor`, потому что факторов скоринга несколько, а в одном атрибуте их хранить нельзя (1НФ);
- «Событие аудита» стало таблицей со стереотипом Audit, `loan_application_aud`: в неё только вставляют строки.

## Соглашения

- Имена: snake_case, английский без транслитерации, единственное число, суффикс по домену (`_id`, `_code`, `_amt` …).
- Стереотипы: `dim_` — справочник (Dimension, обязательны `create_dttm`, `modify_dttm`, `action_ind_code`); `_aud` — аудит (Audit, только вставка, обязателен `create_dttm`). Остальные таблицы — основные сущности.
- **Обязательность = NOT NULL.** UNIQUE указан только там, где он нужен, в описании атрибута. UNIQUE ≠ NOT NULL: он гарантирует только уникальность записанных значений.

## Домены

| Код домена | Шаблон имени | Тип PostgreSQL | По умолчанию | Назначение |
|---|---|---|---|---|
| dIdentifier | `*_id` | bigint | identity | Технический идентификатор сущности |
| dCode | `*_code` | varchar(64) | — | Мнемонический код (статус, роль, источник) или бизнес-идентификатор |
| dName | `*_name` | varchar(256) | — | Название для отображения |
| dDescription | `*_desc` | text | — | Произвольный текст |
| dDate | `*_dt` | date | — | Дата без времени |
| dDateTime | `*_dttm` | timestamptz | now() для `create_dttm` | Дата и время |
| dAmount | `*_amt` | numeric(18,2) | — | Сумма в рублях |
| dQuantity | `*_qnt` | integer | — | Количество (месяцы, баллы) |
| dNumberValue | `*_nval` | numeric(7,4) | — | Произвольное число (ставка, % годовых) |
| dCharValue | `*_cval` | text | — | Произвольное строковое значение (хэш, JSON-ответ) |
| dBoolean | `*_bool` | boolean | false | Признак да/нет |

## Атрибуты

Колонка «Обяз.» — NOT NULL.

### company — Компания
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| company_id | dIdentifier | да | PK |
| inn_code | dCode | да | ИНН, 10 или 12 цифр. UNIQUE |
| ogrn_code | dCode | нет | ОГРН/ОГРНИП, приходит из ЕГРЮЛ |
| company_name | dName | да | Наименование |
| legal_form_code | dCode | да | `IP`, `OOO` |
| registration_dt | dDate | нет | Дата регистрации, из ЕГРЮЛ |
| create_dttm, modify_dttm | dDateTime | да | Технические |

### dim_user_role — Роль
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| role_code | dCode | да | PK: `CLIENT`, `UNDERWRITER` |
| role_name | dName | да | Название роли |

### app_user — Пользователь
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| user_id | dIdentifier | да | PK |
| company_id | dIdentifier | нет | FK → company. Пусто у сотрудников банка |
| role_code | dCode | да | FK → dim_user_role |
| login_code | dCode | да | Логин. UNIQUE |
| password_hash_cval | dCharValue | да | Хэш пароля (bcrypt) |
| user_name | dName | да | ФИО |
| create_dttm | dDateTime | да | Технический |

### dim_credit_product — Кредитный продукт
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| product_id | dIdentifier | да | PK |
| product_code | dCode | да | `WORKING_CAPITAL`, `EQUIPMENT`, `OVERDRAFT`. UNIQUE |
| product_name | dName | да | Название |
| min_amt, max_amt | dAmount | да | Диапазон суммы |
| min_term_qnt, max_term_qnt | dQuantity | да | Диапазон срока, мес. |
| rate_nval | dNumberValue | да | Базовая ставка, % годовых |
| requirement_desc | dDescription | нет | Требования к заёмщику |
| active_bool | dBoolean | да | Показывать в каталоге |
| create_dttm, modify_dttm | dDateTime | да | Технические |
| action_ind_code | dCode | да | Индикатор изменения строки: I, U, D |

### dim_application_status — Статус заявки
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| status_code | dCode | да | PK: `DRAFT`, `SUBMITTED`, `CHECKING`, `EXTERNAL_CHECK`, `SCORING`, `NEEDS_INFO`, `MANUAL_REVIEW`, `APPROVED`, `COUNTER_OFFER`, `REJECTED`, `OFFER_ACCEPTED`, `SIGNING`, `ISSUED`, `DECLINED_BY_CLIENT` |
| status_name | dName | да | Название для клиента |
| final_bool | dBoolean | да | Конечный статус |

### loan_application — Кредитная заявка
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| application_id | dIdentifier | да | PK |
| company_id | dIdentifier | да | FK → company |
| product_id | dIdentifier | да | FK → dim_credit_product |
| status_code | dCode | да | FK → dim_application_status, по умолчанию `DRAFT` |
| requested_amt | dAmount | нет | Запрошенная сумма. Обязательна к подаче, но не в черновике |
| term_qnt | dQuantity | нет | Срок, мес. Так же |
| purpose_desc | dDescription | нет | Цель кредита |
| revenue_amt | dAmount | нет | Годовая выручка со слов клиента |
| debt_amt | dAmount | нет | Текущая долговая нагрузка |
| idempotency_key_code | dCode | нет | Ключ идемпотентной подачи. UNIQUE |
| submit_dttm | dDateTime | нет | Когда подана |
| create_dttm, modify_dttm | dDateTime | да | Технические |

### external_check — Внешняя проверка
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| check_id | dIdentifier | да | PK |
| application_id | dIdentifier | да | FK → loan_application |
| source_code | dCode | да | `EGRUL`, `FNS`, `BKI` |
| check_status_code | dCode | да | `OK`, `TIMEOUT`, `ERROR` |
| response_cval | dCharValue | нет | Ответ сервиса (JSON) |
| request_dttm | dDateTime | да | Время запроса |
| response_dttm | dDateTime | нет | Время ответа |

### credit_decision — Кредитное решение
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| decision_id | dIdentifier | да | PK |
| application_id | dIdentifier | да | FK → loan_application |
| user_id | dIdentifier | нет | FK → app_user. Пусто для автоматического решения |
| decision_type_code | dCode | да | `AUTO`, `MANUAL` |
| outcome_code | dCode | да | `APPROVED`, `COUNTER_OFFER`, `NEEDS_INFO`, `MANUAL_REVIEW`, `REJECTED` |
| score_qnt | dQuantity | нет | Балл скоринга 0–100. Пусто при стоп-факторе |
| reason_desc | dDescription | да | Причина простым языком для клиента |
| comment_desc | dDescription | нет | Комментарий андеррайтера, обязателен для `MANUAL` (проверка в API) |
| create_dttm | dDateTime | да | Технический |

### decision_factor — Фактор решения
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| factor_id | dIdentifier | да | PK |
| decision_id | dIdentifier | да | FK → credit_decision |
| factor_code | dCode | да | `REVENUE`, `COMPANY_AGE`, `OVERDUE_DAYS`, `DEBT_LOAD` … |
| factor_cval | dCharValue | нет | Значение фактора на момент решения |
| point_qnt | dQuantity | да | Баллы по скоринг-карте |

### loan_offer — Оффер
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| offer_id | dIdentifier | да | PK |
| decision_id | dIdentifier | да | FK → credit_decision. UNIQUE: не больше одного оффера на решение |
| offer_amt | dAmount | да | Сумма (для контроффера — меньше запрошенной) |
| term_qnt | dQuantity | да | Срок, мес. |
| rate_nval | dNumberValue | да | Ставка, % годовых |
| monthly_payment_amt | dAmount | да | Ежемесячный платёж |
| offer_status_code | dCode | да | `SENT`, `ACCEPTED`, `DECLINED`, `SIGNED` |
| accept_dttm, sign_dttm | dDateTime | нет | Когда принят и подписан |
| create_dttm | dDateTime | да | Технический |

### info_request — Запрос данных
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| request_id | dIdentifier | да | PK |
| application_id | dIdentifier | да | FK → loan_application |
| user_id | dIdentifier | нет | FK → app_user. Пусто, если запрос создала система |
| request_desc | dDescription | да | Что нужно дозаполнить |
| request_status_code | dCode | да | `OPEN`, `ANSWERED` |
| answer_dttm | dDateTime | нет | Когда клиент ответил |
| create_dttm | dDateTime | да | Технический |

### loan_application_aud — История заявки (Audit)
| Атрибут | Домен | Обяз. | Описание |
|---|---|---|---|
| audit_id | dIdentifier | да | PK |
| application_id | dIdentifier | да | FK → loan_application |
| user_id | dIdentifier | нет | FK → app_user. Пусто для системных переходов |
| from_status_code | dCode | нет | FK → dim_application_status. Пусто при создании |
| to_status_code | dCode | да | FK → dim_application_status |
| event_desc | dDescription | нет | Комментарий к переходу |
| create_dttm | dDateTime | да | Когда произошло. Строки только добавляются |
