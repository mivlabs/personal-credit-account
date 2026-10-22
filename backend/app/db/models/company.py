"""Компания и пользователь."""

from sqlalchemy import CheckConstraint, ForeignKey, Index, UniqueConstraint
from sqlalchemy.orm import mapped_column

from app.db.base import (
    Base,
    CharValue,
    Code,
    DateTime_,
    DateValue,
    Description,
    Identifier,
    Mapped,
    Name,
    create_dttm_column,
    modify_dttm_column,
    pk_column,
)


class Company(Base):
    __tablename__ = "company"
    __table_args__ = (
        UniqueConstraint("inn_code"),
        CheckConstraint("inn_code ~ '^[0-9]{10}([0-9]{2})?$'", name="inn_format"),
        CheckConstraint("legal_form_code IN ('IP', 'OOO')", name="legal_form"),
    )

    company_id: Mapped[int] = pk_column()
    inn_code: Mapped[Code]
    ogrn_code: Mapped[Code | None]
    company_name: Mapped[Name]
    legal_form_code: Mapped[Code]
    registration_dt: Mapped[DateValue | None]
    legal_address_desc: Mapped[Description | None]  # не из исходного словаря: адрес из ЕГРЮЛ (US-02)
    create_dttm: Mapped[DateTime_] = create_dttm_column()
    modify_dttm: Mapped[DateTime_] = modify_dttm_column()


class AppUser(Base):
    __tablename__ = "app_user"
    __table_args__ = (
        UniqueConstraint("login_code"),
        Index("ix_app_user_company_id", "company_id"),
        Index("ix_app_user_role_code", "role_code"),
    )

    user_id: Mapped[int] = pk_column()
    company_id: Mapped[Identifier | None] = mapped_column(ForeignKey("company.company_id"))
    role_code: Mapped[Code] = mapped_column(ForeignKey("dim_user_role.role_code"))
    login_code: Mapped[Code]
    password_hash_cval: Mapped[CharValue]
    user_name: Mapped[Name]
    create_dttm: Mapped[DateTime_] = create_dttm_column()
