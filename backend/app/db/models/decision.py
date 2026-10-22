"""Кредитное решение, факторы скоринга и оффер."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
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
    NumberValue,
    Quantity,
    create_dttm_column,
    pk_column,
)


class CreditDecision(Base):
    __tablename__ = "credit_decision"
    __table_args__ = (
        CheckConstraint("decision_type_code IN ('AUTO', 'MANUAL')", name="decision_type"),
        CheckConstraint(
            "outcome_code IN ('APPROVED', 'COUNTER_OFFER', 'NEEDS_INFO', 'MANUAL_REVIEW', 'REJECTED')",
            name="outcome",
        ),
        CheckConstraint("score_qnt IS NULL OR score_qnt BETWEEN 0 AND 100", name="score_range"),
        Index("ix_credit_decision_application_id", "application_id"),
        Index("ix_credit_decision_user_id", "user_id"),
    )

    decision_id: Mapped[int] = pk_column()
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    user_id: Mapped[Identifier | None] = mapped_column(ForeignKey("app_user.user_id"))
    decision_type_code: Mapped[Code]
    outcome_code: Mapped[Code]
    score_qnt: Mapped[Quantity | None]
    reason_desc: Mapped[Description]
    comment_desc: Mapped[Description | None]
    create_dttm: Mapped[DateTime_] = create_dttm_column()

    factors: Mapped[list["DecisionFactor"]] = relationship(order_by="DecisionFactor.factor_id")
    offer: Mapped["LoanOffer | None"] = relationship(uselist=False)


class DecisionFactor(Base):
    __tablename__ = "decision_factor"
    __table_args__ = (Index("ix_decision_factor_decision_id", "decision_id"),)

    factor_id: Mapped[int] = pk_column()
    decision_id: Mapped[Identifier] = mapped_column(ForeignKey("credit_decision.decision_id"))
    factor_code: Mapped[Code]
    factor_cval: Mapped[CharValue | None]
    point_qnt: Mapped[Quantity]


class LoanOffer(Base):
    __tablename__ = "loan_offer"
    __table_args__ = (
        # не больше одного оффера на решение
        UniqueConstraint("decision_id"),
        CheckConstraint(
            "offer_status_code IN ('SENT', 'ACCEPTED', 'DECLINED', 'SIGNED')", name="offer_status"
        ),
    )

    offer_id: Mapped[int] = pk_column()
    decision_id: Mapped[Identifier] = mapped_column(ForeignKey("credit_decision.decision_id"))
    offer_amt: Mapped[Amount]
    term_qnt: Mapped[Quantity]
    rate_nval: Mapped[NumberValue]
    monthly_payment_amt: Mapped[Amount]
    offer_status_code: Mapped[Code]
    accept_dttm: Mapped[DateTime_ | None]
    sign_dttm: Mapped[DateTime_ | None]
    create_dttm: Mapped[DateTime_] = create_dttm_column()
