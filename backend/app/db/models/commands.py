"""Persistent command replays and one simulated disbursement per application."""

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import mapped_column

from app.db.base import (
    Amount,
    Base,
    CharValue,
    Code,
    DateTime_,
    Identifier,
    Mapped,
    create_dttm_column,
    pk_column,
)


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_record"
    __table_args__ = (UniqueConstraint("user_id", "operation_code", "key_code"),)
    record_id: Mapped[int] = pk_column()
    user_id: Mapped[Identifier] = mapped_column(ForeignKey("app_user.user_id"))
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    operation_code: Mapped[Code]
    key_code: Mapped[Code]
    request_hash_code: Mapped[Code]
    response_cval: Mapped[CharValue]
    create_dttm: Mapped[DateTime_] = create_dttm_column()


class Disbursement(Base):
    __tablename__ = "disbursement"
    __table_args__ = (UniqueConstraint("application_id"),)
    disbursement_id: Mapped[int] = pk_column()
    application_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_application.application_id"))
    offer_id: Mapped[Identifier] = mapped_column(ForeignKey("loan_offer.offer_id"))
    amount_amt: Mapped[Amount]
    create_dttm: Mapped[DateTime_] = create_dttm_column()
