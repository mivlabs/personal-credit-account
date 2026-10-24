"""Заявка, внешние проверки, запросы данных и аудит."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint, func
from sqlalchemy.orm import mapped_column, relationship

from app.db.base import (
    Amount,
    Base,
    CharValue,
    Code,
    DateTime_,
    Description,
    Identifier,
    Mapped,
    Quantity,
    create_dttm_column,
    modify_dttm_column,
    pk_column,
)
from app.db.models.company import Company
from app.db.models.dictionaries import DimCreditProduct


class LoanApplication(Base):
    __tablename__ = "loan_application"
    __table_args__ = (
        UniqueConstraint("idempotency_key_code"),
        Index("ix_loan_application_company_id", "company_id"),
        Index("ix_loan_application_product_id", "product_id"),
        Index("ix_loan_application_status_code", "status_code"),
    )

    application_id: Mapped[int] = pk_column()
    company_id: Mapped[Identifier] = mapped_column(ForeignKey("company.company_id"))
    product_id: Mapped[Identifier] = mapped_column(ForeignKey("dim_credit_product.product_id"))
    status_code: Mapped[Code] = mapped_column(
        ForeignKey("dim_application_status.status_code"), server_default="DRAFT"
    )
    requested_amt: Mapped[Amount | None]
    term_qnt: Mapped[Quantity | None]
    purpose_desc: Mapped[Description | None]
    revenue_amt: Mapped[Amount | None]
    debt_amt: Mapped[Amount | None]
    idempotency_key_code: Mapped[Code | None]
    submit_dttm: Mapped[DateTime_ | None]
    draft_step_qnt: Mapped[Quantity | None]  # не из исходного словаря: шаг мастера черновика (US-03)
    create_dttm: Mapped[DateTime_] = create_dttm_column()
    modify_dttm: Mapped[DateTime_] = modify_dttm_column()

    # innerjoin: FK обязательны, а INNER JOIN допускает SELECT … FOR UPDATE
    company: Mapped[Company] = relationship(lazy="joined", innerjoin=True)
    product: Mapped[DimCreditProduct] = relationship(lazy="joined", innerjoin=True)


class ExternalCheck(Base):
    __tablename__ = "external_check"
    __table_args__ = (
        CheckConstraint("source_code IN ('EGRUL', 'FNS', 'BKI')", name="source"),
        CheckConstraint("check_status_code IN ('OK', 'TIMEOUT', 'ERROR')", name="check_status"),
        Index("ix_external_check_application_id", "application_id"),
    )

    check_id: Mapped[int] = pk_column()
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    source_code: Mapped[Code]
    check_status_code: Mapped[Code]
    response_cval: Mapped[CharValue | None]
    request_dttm: Mapped[DateTime_] = mapped_column(server_default=func.now())
    response_dttm: Mapped[DateTime_ | None]


class InfoRequest(Base):
    __tablename__ = "info_request"
    __table_args__ = (
        CheckConstraint("request_status_code IN ('OPEN', 'ANSWERED')", name="request_status"),
        Index("ix_info_request_application_id", "application_id"),
        Index("ix_info_request_user_id", "user_id"),
    )

    request_id: Mapped[int] = pk_column()
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    user_id: Mapped[Identifier | None] = mapped_column(ForeignKey("app_user.user_id"))
    request_desc: Mapped[Description]
    # не из исходного словаря: JSON-массив имён полей анкеты, которые нужно дозаполнить (US-06)
    field_list_cval: Mapped[CharValue] = mapped_column(server_default="[]")
    request_status_code: Mapped[Code]
    answer_dttm: Mapped[DateTime_ | None]
    due_dttm: Mapped[DateTime_ | None]
    create_dttm: Mapped[DateTime_] = create_dttm_column()


class LoanApplicationAud(Base):
    """История заявки: только вставка (UPDATE/DELETE запрещены триггером БД)."""

    __tablename__ = "loan_application_aud"
    __table_args__ = (
        Index("ix_loan_application_aud_application_id_create_dttm", "application_id", "create_dttm"),
        Index("ix_loan_application_aud_user_id", "user_id"),
        Index("ix_loan_application_aud_from_status_code", "from_status_code"),
        Index("ix_loan_application_aud_to_status_code", "to_status_code"),
    )

    audit_id: Mapped[int] = pk_column()
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    user_id: Mapped[Identifier | None] = mapped_column(ForeignKey("app_user.user_id"))
    from_status_code: Mapped[Code | None] = mapped_column(ForeignKey("dim_application_status.status_code"))
    to_status_code: Mapped[Code] = mapped_column(ForeignKey("dim_application_status.status_code"))
    event_desc: Mapped[Description | None]
    create_dttm: Mapped[DateTime_] = create_dttm_column()
