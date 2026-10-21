from datetime import date

from pydantic import ConfigDict, Field

from app.domain.enums import LegalForm
from app.schemas.base import ApiModel


class CompanyOut(ApiModel):
    id: int
    inn: str = Field(description="ИНН: 10 цифр у ООО, 12 у ИП")
    ogrn: str | None = Field(default=None, description="ОГРН / ОГРНИП из ЕГРЮЛ")
    name: str = Field(description="Наименование")
    legal_form: LegalForm
    registration_date: date | None = Field(default=None, description="Дата регистрации из ЕГРЮЛ")
    legal_address: str | None = Field(default=None, description="Юридический адрес из ЕГРЮЛ")

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "id": 1,
                    "inn": "770100000001",
                    "ogrn": "3217700000011",
                    "name": "ИП Иванов Пётр Сергеевич",
                    "legalForm": "IP",
                    "registrationDate": "2018-04-12",
                    "legalAddress": "г. Москва, ул. Тверская, д. 1",
                }
            ]
        }
    )
