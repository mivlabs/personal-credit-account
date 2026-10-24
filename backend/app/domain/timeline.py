"""Таймлайн статуса для клиента: этапы, состояние каждого и «нужно ли действие от меня»."""

from collections.abc import Sequence
from datetime import datetime

from app.domain.enums import ApplicationStatus, StageCode, StageState

S = ApplicationStatus

# Этапы в порядке прохождения: (код, название, что происходит на этапе)
STAGES: tuple[tuple[StageCode, str, str], ...] = (
    (StageCode.DRAFT, "Заявка", "Вы заполняете заявку: она сохраняется как черновик"),
    (StageCode.SUBMITTED, "Подана", "Банк получил вашу заявку"),
    (StageCode.REVIEW, "Проверка", "Банк проверяет данные и оценивает заявку"),
    (StageCode.DECISION, "Решение", "Банк сообщает решение по заявке"),
    (StageCode.SIGNING, "Подписание", "Вы подписываете договор в кабинете"),
    (StageCode.ISSUED, "Кредит выдан", "Деньги зачислены на счёт компании"),
)

STAGE_OF_STATUS: dict[ApplicationStatus, StageCode] = {
    S.DRAFT: StageCode.DRAFT,
    S.SUBMITTED: StageCode.SUBMITTED,
    S.CHECKING: StageCode.REVIEW,
    S.EXTERNAL_CHECK: StageCode.REVIEW,
    S.SCORING: StageCode.REVIEW,
    S.NEEDS_INFO: StageCode.REVIEW,
    S.MANUAL_REVIEW: StageCode.REVIEW,
    S.APPROVED: StageCode.DECISION,
    S.COUNTER_OFFER: StageCode.DECISION,
    S.REJECTED: StageCode.DECISION,
    S.DECLINED_BY_CLIENT: StageCode.DECISION,
    S.WITHDRAWN: StageCode.DECISION,
    S.OFFER_ACCEPTED: StageCode.SIGNING,
    S.SIGNING: StageCode.SIGNING,
    S.ISSUED: StageCode.ISSUED,
}

# Статусы, в которых от клиента нужно действие
ACTION_REQUIRED_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {S.DRAFT, S.NEEDS_INFO, S.APPROVED, S.COUNTER_OFFER, S.SIGNING}
)

# Что происходит сейчас и что дальше: описание текущего этапа в зависимости от статуса
STATUS_HINTS: dict[ApplicationStatus, str] = {
    S.DRAFT: "Заполните заявку и подайте её. Черновик сохраняется, можно вернуться позже",
    S.SUBMITTED: "Заявка принята, сейчас начнём проверку",
    S.CHECKING: "Проверяем, что в заявке есть все нужные данные",
    S.EXTERNAL_CHECK: "Запрашиваем данные о компании во внешних сервисах",
    S.SCORING: "Оцениваем заявку, решение появится через несколько секунд",
    S.NEEDS_INFO: "Банку нужно уточнить данные: заполните запрошенные поля, и мы продолжим проверку",
    S.MANUAL_REVIEW: "Заявку рассматривает специалист банка, мы сообщим решение здесь",
    S.APPROVED: "Кредит одобрен. Проверьте условия и примите предложение",
    S.COUNTER_OFFER: "Банк предлагает другие условия. Посмотрите их и примите или откажитесь",
    S.REJECTED: "К сожалению, кредит не одобрен. Причина указана в решении",
    S.DECLINED_BY_CLIENT: "Вы отказались от предложения банка",
    S.WITHDRAWN: "Вы отозвали заявку. Можно создать новую",
    S.OFFER_ACCEPTED: "Предложение принято, готовим договор",
    S.SIGNING: "Подпишите договор: введите код подтверждения",
    S.ISSUED: "Договор подписан, кредит выдан",
}

_ORDER = {code: i for i, (code, _, _) in enumerate(STAGES)}


def build_stages(
    status: ApplicationStatus,
    history: Sequence[tuple[ApplicationStatus, datetime]],
) -> list[dict]:
    """Собирает этапы таймлайна. history — пары (статус, когда вошли в него), от старых к новым."""
    current = STAGE_OF_STATUS[status]
    current_idx = _ORDER[current]
    action = status in ACTION_REQUIRED_STATUSES

    entered: dict[StageCode, datetime] = {}
    for st, at in history:
        entered.setdefault(STAGE_OF_STATUS[st], at)

    stages = []
    for idx, (code, name, description) in enumerate(STAGES):
        if idx < current_idx:
            state = StageState.DONE
        elif idx == current_idx:
            # Финальный успешный этап считаем пройденным: дальше идти некуда
            state = StageState.DONE if status == S.ISSUED else StageState.CURRENT
        else:
            state = StageState.UPCOMING
        is_current = idx == current_idx
        stages.append(
            {
                "code": code,
                "name": name,
                "description": STATUS_HINTS[status] if is_current else description,
                "state": state,
                "action_required": is_current and action,
                "entered_at": entered.get(code),
            }
        )
    return stages
