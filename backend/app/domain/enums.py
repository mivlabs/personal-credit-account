from enum import StrEnum


class ApplicationStatus(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    CHECKING = "CHECKING"
    EXTERNAL_CHECK = "EXTERNAL_CHECK"
    SCORING = "SCORING"
    NEEDS_INFO = "NEEDS_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    REJECTED = "REJECTED"
    OFFER_ACCEPTED = "OFFER_ACCEPTED"
    SIGNING = "SIGNING"
    ISSUED = "ISSUED"
    DECLINED_BY_CLIENT = "DECLINED_BY_CLIENT"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


# Названия статусов для клиента (источник и для API, и для seed справочника dim_application_status)
STATUS_NAMES: dict[ApplicationStatus, str] = {
    ApplicationStatus.DRAFT: "Черновик",
    ApplicationStatus.SUBMITTED: "Подана",
    ApplicationStatus.CHECKING: "Проверяем заявку",
    ApplicationStatus.EXTERNAL_CHECK: "Получаем данные из внешних сервисов",
    ApplicationStatus.SCORING: "Оцениваем заявку",
    ApplicationStatus.NEEDS_INFO: "Нужны данные",
    ApplicationStatus.MANUAL_REVIEW: "На рассмотрении у специалиста",
    ApplicationStatus.APPROVED: "Одобрено",
    ApplicationStatus.COUNTER_OFFER: "Встречное предложение",
    ApplicationStatus.REJECTED: "Отказ",
    ApplicationStatus.OFFER_ACCEPTED: "Предложение принято",
    ApplicationStatus.SIGNING: "Подписание",
    ApplicationStatus.ISSUED: "Кредит выдан",
    ApplicationStatus.DECLINED_BY_CLIENT: "Вы отказались",
    ApplicationStatus.WITHDRAWN: "Заявка отозвана",
    ApplicationStatus.EXPIRED: "Срок истёк",
}

FINAL_STATUSES: frozenset[ApplicationStatus] = frozenset(
    {
        ApplicationStatus.REJECTED,
        ApplicationStatus.ISSUED,
        ApplicationStatus.DECLINED_BY_CLIENT,
        ApplicationStatus.WITHDRAWN,
        ApplicationStatus.EXPIRED,
    }
)


class DecisionOutcome(StrEnum):
    """Исход решения по заявке (credit_decision.outcome_code)."""

    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    NEEDS_INFO = "NEEDS_INFO"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    REJECTED = "REJECTED"


class ManualOutcome(StrEnum):
    """Исходы, доступные андеррайтеру при ручном решении."""

    APPROVED = "APPROVED"
    COUNTER_OFFER = "COUNTER_OFFER"
    NEEDS_INFO = "NEEDS_INFO"
    REJECTED = "REJECTED"


class DecisionType(StrEnum):
    AUTO = "AUTO"
    MANUAL = "MANUAL"


class UserRole(StrEnum):
    CLIENT = "CLIENT"
    UNDERWRITER = "UNDERWRITER"


class ProductCode(StrEnum):
    WORKING_CAPITAL = "WORKING_CAPITAL"
    EQUIPMENT = "EQUIPMENT"
    OVERDRAFT = "OVERDRAFT"


class LegalForm(StrEnum):
    IP = "IP"
    OOO = "OOO"


class OfferStatus(StrEnum):
    SENT = "SENT"
    ACCEPTED = "ACCEPTED"
    DECLINED = "DECLINED"
    SIGNED = "SIGNED"


class InfoRequestStatus(StrEnum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"


class CheckSource(StrEnum):
    EGRUL = "EGRUL"
    FNS = "FNS"
    BKI = "BKI"


class CheckStatus(StrEnum):
    OK = "OK"
    TIMEOUT = "TIMEOUT"
    ERROR = "ERROR"


class ApplicationField(StrEnum):
    """Поля анкеты, которые клиент заполняет сам и которые банк может запросить повторно."""

    REQUESTED_AMOUNT = "requestedAmount"
    TERM_MONTHS = "termMonths"
    PURPOSE = "purpose"
    REVENUE_AMOUNT = "revenueAmount"
    DEBT_AMOUNT = "debtAmount"


class StageCode(StrEnum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    REVIEW = "REVIEW"
    DECISION = "DECISION"
    SIGNING = "SIGNING"
    ISSUED = "ISSUED"


class StageState(StrEnum):
    DONE = "done"
    CURRENT = "current"
    UPCOMING = "upcoming"


class ErrorCode(StrEnum):
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_TRANSITION = "INVALID_TRANSITION"
    EXPIRED = "EXPIRED"
    NOT_FOUND = "NOT_FOUND"
    FORBIDDEN = "FORBIDDEN"
    UNAUTHORIZED = "UNAUTHORIZED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOO_MANY_REQUESTS = "TOO_MANY_REQUESTS"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class PurposeCategory(StrEnum):
    """Категория цели кредита для подбора продукта (domain/recommendation.yaml)."""

    WORKING_CAPITAL_TOPUP = "WORKING_CAPITAL_TOPUP"
    GOODS_PURCHASE = "GOODS_PURCHASE"
    EQUIPMENT_PURCHASE = "EQUIPMENT_PURCHASE"
    CASH_GAP = "CASH_GAP"
    SEASONAL = "SEASONAL"
    EXPANSION = "EXPANSION"
    OTHER = "OTHER"
