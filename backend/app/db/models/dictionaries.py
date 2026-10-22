"""Справочники (стереотип dim_): роль, статус заявки, кредитный продукт."""

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlalchemy.orm import mapped_column

from app.db.base import (
    Amount,
    Base,
    Bool,
    Code,
    DateTime_,
    Description,
    Mapped,
    Name,
    NumberValue,
    Quantity,
    action_ind_column,
    create_dttm_column,
    false_column,
    modify_dttm_column,
    pk_column,
)

_ACTION_IND_CHECK = "action_ind_code IN ('I', 'U', 'D')"


class DimUserRole(Base):
    __tablename__ = "dim_user_role"
    __table_args__ = (CheckConstraint(_ACTION_IND_CHECK, name="action_ind"),)

    role_code: Mapped[Code] = mapped_column(primary_key=True)
    role_name: Mapped[Name]
    create_dttm: Mapped[DateTime_] = create_dttm_column()
    modify_dttm: Mapped[DateTime_] = modify_dttm_column()
    action_ind_code: Mapped[Code] = action_ind_column()


class DimApplicationStatus(Base):
    __tablename__ = "dim_application_status"
    __table_args__ = (CheckConstraint(_ACTION_IND_CHECK, name="action_ind"),)

    status_code: Mapped[Code] = mapped_column(primary_key=True)
    status_name: Mapped[Name]
    final_bool: Mapped[Bool] = false_column()
    create_dttm: Mapped[DateTime_] = create_dttm_column()
    modify_dttm: Mapped[DateTime_] = modify_dttm_column()
    action_ind_code: Mapped[Code] = action_ind_column()


class DimCreditProduct(Base):
    __tablename__ = "dim_credit_product"
    __table_args__ = (
        UniqueConstraint("product_code"),
        CheckConstraint("min_amt <= max_amt", name="amt_range"),
        CheckConstraint("min_term_qnt <= max_term_qnt", name="term_range"),
        CheckConstraint(_ACTION_IND_CHECK, name="action_ind"),
    )

    product_id: Mapped[int] = pk_column()
    product_code: Mapped[Code]
    product_name: Mapped[Name]
    min_amt: Mapped[Amount]
    max_amt: Mapped[Amount]
    min_term_qnt: Mapped[Quantity]
    max_term_qnt: Mapped[Quantity]
    rate_nval: Mapped[NumberValue]
    requirement_desc: Mapped[Description | None]
    active_bool: Mapped[Bool] = false_column()
    create_dttm: Mapped[DateTime_] = create_dttm_column()
    modify_dttm: Mapped[DateTime_] = modify_dttm_column()
    action_ind_code: Mapped[Code] = action_ind_column()
