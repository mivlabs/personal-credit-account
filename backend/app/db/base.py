"""Базовый класс моделей и типы доменов из data-dictionary.md."""

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Identity,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, MappedColumn, mapped_column

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Домены словаря: Mapped[Code] -> NOT NULL, Mapped[Code | None] -> NULL
Identifier = Annotated[int, mapped_column(BigInteger)]  # dIdentifier
Code = Annotated[str, mapped_column(String(64))]  # dCode
Name = Annotated[str, mapped_column(String(256))]  # dName
Description = Annotated[str, mapped_column(Text)]  # dDescription
DateValue = Annotated[date, mapped_column(Date)]  # dDate
DateTime_ = Annotated[datetime, mapped_column(DateTime(timezone=True))]  # dDateTime
Amount = Annotated[Decimal, mapped_column(Numeric(18, 2))]  # dAmount
Quantity = Annotated[int, mapped_column(Integer)]  # dQuantity
NumberValue = Annotated[Decimal, mapped_column(Numeric(7, 4))]  # dNumberValue
CharValue = Annotated[str, mapped_column(Text)]  # dCharValue
Bool = Annotated[bool, mapped_column(Boolean)]  # dBoolean


def pk_column() -> MappedColumn[int]:
    """Технический идентификатор: bigint identity."""
    return mapped_column(BigInteger, Identity(), primary_key=True)


def create_dttm_column() -> MappedColumn[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def modify_dttm_column() -> MappedColumn[datetime]:
    # Обновляется триггером БД set_modify_dttm() при любом UPDATE строки
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def false_column() -> MappedColumn[bool]:
    return mapped_column(Boolean, server_default=text("false"), nullable=False)


def action_ind_column() -> MappedColumn[str]:
    """Индикатор изменения строки справочника: I, U, D."""
    return mapped_column(String(64), server_default=text("'I'"), nullable=False)


__all__ = [
    "Amount",
    "Base",
    "Bool",
    "CharValue",
    "Code",
    "DateTime_",
    "DateValue",
    "Description",
    "Identifier",
    "Mapped",
    "Name",
    "NumberValue",
    "Quantity",
    "action_ind_column",
    "create_dttm_column",
    "false_column",
    "modify_dttm_column",
    "pk_column",
]
